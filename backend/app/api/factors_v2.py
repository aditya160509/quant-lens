"""Strict Factors V2 runs, validated uploads and durable local jobs."""

from __future__ import annotations
import asyncio
import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, File, UploadFile
from app.services.factors_v2.registry import (
    feature_manifest,
    run_feature,
    prepare_payload,
    normalize_feature_id,
)
from app.services.factors_v2.core.data_loader import (
    search_symbol_directory,
    BACKEND_DATA,
    source_version,
)
from app.services.factors_v2.core.uploads import save_upload
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/labs/factors/v2", tags=["factors-v2"])
JOBS = JobStore(path=BACKEND_DATA / "factors_v2/jobs.json")
RESULTS = BACKEND_DATA / "factors_v2/results"


def envelope(request):
    if set(request) != {"payload"} or not isinstance(request["payload"], dict):
        raise ValueError(
            "Expected exactly {payload: {...}}; flat inputs are not accepted"
        )
    return request["payload"]


def mapped(exc):
    return HTTPException(404 if isinstance(exc, KeyError) else 422, str(exc))


@router.get("/features")
def features():
    return {"status": "ok", "features": feature_manifest()}


@router.get("/symbols")
def symbols(
    q: str = Query("", max_length=80),
    limit: int = Query(25, ge=1, le=100),
    asset_type: str | None = None,
):
    return {"status": "ok", "symbols": search_symbol_directory(q, limit, asset_type)}


@router.post("/feature/{feature_id}/run")
async def execute(feature_id: str, request: dict):
    try:
        fid = normalize_feature_id(feature_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        return await asyncio.to_thread(run_feature, fid, envelope(request))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/export/{feature_id}")
async def export(feature_id: str, request: dict):
    result = await execute(feature_id, request)
    return {
        "status": result["status"],
        "formats": ["json", "csv_tables"],
        "json": result,
        "csv_tables": {
            key: pd.DataFrame(rows).to_csv(index=False)
            for key, rows in result["tables"].items()
            if isinstance(rows, list)
        },
    }


def verify_sources(job_id):
    expected = JOBS.get(job_id)["params"]["source_versions"]
    if json.dumps(expected) != json.dumps(source_version()):
        raise ValueError(
            "Data files changed after this job was queued; rerun against a consistent source version"
        )


def _execute(job_id, feature_id, payload):
    verify_sources(job_id)
    result = run_feature(feature_id, payload)
    if result["status"] == "error":
        raise ValueError(result.get("meta", {}).get("error", "Feature failed"))
    verify_sources(job_id)
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{job_id}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, allow_nan=False))
    temp.replace(path)
    return {"result_file": path.name}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: dict):
    try:
        fid = normalize_feature_id(feature_id)
        payload = prepare_payload(fid, envelope(request))
    except (KeyError, ValueError, TypeError) as exc:
        raise mapped(exc) from exc
    job = JOBS.create(
        job_type=f"factors_v2_{fid}",
        params={
            "feature_id": fid,
            "payload": payload,
            "source_versions": source_version(),
        },
    )
    JOBS.submit(job["job_id"], _execute, job["job_id"], fid, payload)
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": fid}


@router.get("/jobs/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    out = {
        k: job[k]
        for k in ["job_id", "status", "progress", "error", "created_at", "updated_at"]
    }
    if job["status"] == "completed":
        out["result"] = json.loads((RESULTS / job["result"]["result_file"]).read_text())
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str):
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return {
        "job_id": job_id,
        "status": job["status"],
        "note": "Cancellation suppresses publication; active computation finishes in background",
    }


@router.post("/uploads")
async def upload(kind: str = Query(...), file: UploadFile = File(...)):
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "Uploads are limited to 2 MB")
    try:
        return save_upload(raw, kind)
    except (ValueError, TypeError, OSError) as exc:
        raise mapped(exc) from exc


def _run_all(job_id, payloads):
    verify_sources(job_id)
    results = {}
    for i, (fid, payload) in enumerate(payloads.items()):
        job = JOBS.get(job_id)
        if job and job["status"] == "cancelled":
            return {}
        JOBS.update(
            job_id,
            progress={
                "percent": round(i / len(payloads) * 100),
                "message": f"Running feature {fid}",
            },
        )
        results[f"feature_{fid}"] = run_feature(fid, payload)
    result = {
        "status": "partial"
        if any(r["status"] != "ok" for r in results.values())
        else "ok",
        "results": results,
    }
    verify_sources(job_id)
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{job_id}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, allow_nan=False))
    temp.replace(path)
    return {"result_file": path.name}


@router.post("/run-all")
def run_all(request: dict):
    # An async batch requires explicit payloads, never fourteen implicit default portfolios.
    if set(request) != {"feature_payloads"}:
        raise HTTPException(
            422,
            "Expected exactly feature_payloads; common inputs must be merged into explicit feature payloads",
        )
    payloads = request.get("feature_payloads")
    if not isinstance(payloads, dict) or not payloads:
        raise HTTPException(422, "Supply feature_payloads keyed by feature id")
    try:
        prepared = {
            normalize_feature_id(fid): prepare_payload(fid, p)
            for fid, p in payloads.items()
        }
    except (KeyError, ValueError, TypeError) as exc:
        raise mapped(exc) from exc
    job = JOBS.create(
        job_type="factors_v2_batch",
        params={"feature_payloads": prepared, "source_versions": source_version()},
    )
    JOBS.submit(job["job_id"], _run_all, job["job_id"], prepared)
    return {"job_id": job["job_id"], "status": job["status"]}


@router.post("/alert-subscription")
def alert_subscription(request: dict):
    raise HTTPException(
        422,
        "Email, Slack and webhook delivery are unavailable; no subscription has been registered",
    )
