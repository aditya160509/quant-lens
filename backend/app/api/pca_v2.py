"""PCA V2 manifest, strict runs and durable background jobs."""
from __future__ import annotations
import asyncio
import json
from typing import Any
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from app.services.pca_v2.registry import feature_manifest, get_pca_v2_feature, run_feature, validate_payload
from app.services.pca_v2.core.data_loader import BACKEND_DATA, available_symbols, parse_symbols
from app.services.pca_v2.core.uploads import save_upload, resolve_payload
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/labs/pca/v2", tags=["pca-v2"])
JOBS = JobStore(path=BACKEND_DATA / "pca_v2" / "jobs.json")
RESULTS_DIR = BACKEND_DATA / "pca_v2" / "results"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _payload(feature_id, request):
    get_pca_v2_feature(feature_id)
    payload = request.get("payload", request)
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    payload = validate_payload(feature_id, payload)
    payload = resolve_payload({k: v for k, v in payload.items() if v is not None and v != ""})
    if feature_id != "10" and not payload.get("returns_upload_id"):
        parse_symbols(payload)
    return payload


@router.get("/features")
def list_features():
    return {"status": "ok", "features": feature_manifest()}


@router.get("/symbols")
def search_symbols(q: str = Query("", max_length=40), limit: int = Query(20, ge=1, le=100)):
    hits = [s for s in available_symbols() if q.upper() in s]
    return {"results": [{"ticker": s} for s in hits[:limit]]}


@router.post("/uploads")
async def upload(kind: str = Query(...), file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Upload a CSV file")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Uploads are limited to 20 MB")
    try:
        return save_upload(raw, kind)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/feature/{feature_id}/run")
async def execute_feature(feature_id: str, request: dict[str, Any]):
    try:
        payload = _payload(feature_id, request)
        return await asyncio.to_thread(run_feature, feature_id, payload)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _execute(job_id, feature_id, payload):
    result = run_feature(feature_id, payload)
    if result.get("status") == "error":
        raise ValueError(result.get("meta", {}).get("error", "Feature failed"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, allow_nan=False))
    temp.replace(path)
    return {"result_file": path.name}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: dict[str, Any]):
    try:
        payload = _payload(feature_id, request)
        feature = get_pca_v2_feature(feature_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    job = JOBS.create(job_type=f"pca_v2_{feature.id}", params={"feature_id": feature.id, "payload": payload})
    JOBS.submit(job["job_id"], _execute, job["job_id"], feature.id, payload)
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": feature.id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    out = {k: job[k] for k in ("job_id", "type", "status", "created_at", "updated_at", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        out["result"] = json.loads((RESULTS_DIR / job["result"]["result_file"]).read_text())
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return {"job_id": job_id, "status": job["status"], "note": "Cancellation suppresses publication; running computation finishes in background."}
