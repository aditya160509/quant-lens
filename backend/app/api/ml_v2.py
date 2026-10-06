"""Dedicated ML V2 API with durable module-owned jobs."""
from __future__ import annotations
import asyncio
import csv
import io
import json
import importlib
import uuid
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from app.services.ml_v2.core import uploads
from app.services.ml_v2.core.common import PROGRESS, JobCancelled
from app.services.ml_v2.features.inputs import DEPRECATED_INPUTS, validate
from app.services.ml_v2.registry import CONTRACT_VERSION, feature_manifest, get_ml_v2_feature, run_feature
from app.services.ml_v2.core.data_loader import BACKEND_DATA, available_symbols, parse_symbols
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/ml/v2")
ROOT = BACKEND_DATA / "ml_v2"
JOBS = JobStore(path=ROOT / "jobs.json")

def _feature_module(feature_id: str):
    return importlib.import_module(f"app.services.ml_v2.features.{get_ml_v2_feature(feature_id).module}")


def _validated(feature_id: str, payload: dict) -> dict:
    module = _feature_module(feature_id)
    checked = validate(module.normalize_feature_payload(payload), module.INPUTS)
    if feature_id in ("validate", "04") and not checked.get("upload_id") and not checked.get("source_result"):
        if feature_id == "validate":
            raise ValueError("Upload your returns, predictions, feature panel or trial matrix first")
    if feature_id == "validate" or checked.get("upload_id"):
        return checked
    parse_symbols(checked)
    return checked


@router.get("/features")
def list_features():
    return {"contract_version": CONTRACT_VERSION, "deprecated_inputs": list(DEPRECATED_INPUTS), "features": feature_manifest()}


@router.get("/features/{feature_id}")
def get_feature(feature_id: str):
    try:
        feature = get_ml_v2_feature(feature_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return next(row for row in feature_manifest() if row["id"] == feature.id)


@router.post("/features/{feature_id}/validate")
def validate_inputs(feature_id: str, payload: dict = Body(default={})):
    """Check a form payload without running anything; returns the payload with defaults applied."""
    try:
        return {"valid": True, "payload": _validated(feature_id, payload)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc

@router.get("/symbols")
def symbols(q: str = Query("", max_length=40), limit: int = Query(25, ge=1, le=100)):
    query = q.upper().replace(".", "_").replace("-", "_")
    hits = sorted((s for s in available_symbols() if query in s), key=lambda s: (not s.startswith(query), s))
    return {"results": [{"ticker": s} for s in hits[:limit]]}

@router.post("/features/{feature_id}/run")
async def execute(feature_id: str, payload: dict = Body(default={})):
    try:
        return await asyncio.to_thread(run_feature, feature_id, payload)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc

def _checkpoint(job_id: str):
    def report(percent: int, message: str) -> None:
        job = JOBS.get(job_id)
        if job is None or job["status"] == "cancelled":
            raise JobCancelled("Job cancelled")
        JOBS.update(job_id, progress={"percent": percent, "message": message})
    return report


def _execute_job(job_id, feature_id, payload):
    token = PROGRESS.set(_checkpoint(job_id))
    try:
        result = run_feature(feature_id, payload)
    finally:
        PROGRESS.reset(token)
    _checkpoint(job_id)(95, "Writing result")
    directory = ROOT / "results"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{job_id}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    return {"result_file": path.name}

@router.post("/feature/{feature_id}/jobs")
@router.post("/features/{feature_id}/jobs")
def create_job(feature_id: str, payload: dict = Body(default={})):
    try:
        feature = get_ml_v2_feature(feature_id)
        payload = _validated(feature_id, payload)
        job = JOBS.create(job_type=f"ml_v2_{feature.id}", params={"feature_id": feature.id, "payload": payload})
        JOBS.submit(job["job_id"], _execute_job, job["job_id"], feature.id, payload)
        return {"job_id": job["job_id"], "status": job["status"]}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc

def _read_result(job: dict) -> dict:
    path = ROOT / "results" / job["result"]["result_file"]
    if not path.is_file():
        raise HTTPException(503, "Completed result artifact is missing")
    return json.loads(path.read_text())

@router.get("/jobs/{job_id}")
def job_status(job_id: str, include_result: bool = Query(True)):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown ML V2 job")
    out = {key: job[key] for key in ["job_id", "status", "progress", "error"]}
    out.update(feature_id=job["params"]["feature_id"], created_at=job["created_at"], updated_at=job["updated_at"])
    if job["status"] == "completed" and include_result:
        out["result"] = _read_result(job)
    return out

@router.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown ML V2 job")
    if job["status"] != "completed":
        raise HTTPException(409, f"Job is {job['status']}; no result available")
    return _read_result(job)

@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = JOBS.cancel(job_id)
    if job is None:
        raise HTTPException(404, "Unknown ML V2 job")
    return {"job_id": job_id, "status": job["status"],
            "note": "Cancellation takes effect at the next stage checkpoint; a model fit already running completes before the job stops."}

@router.post("/uploads")
async def upload(kind: str = Query("universe"), file: UploadFile = File(...)):
    """kind=universe stores a ticker list; returns, predictions, trial_matrix and feature_panel are parsed
    into a validated in-memory frame (10 MB cap enforced while streaming, 24 h TTL)."""
    if kind != "universe" and kind not in uploads.KINDS:
        raise HTTPException(422, f"kind must be universe or one of {list(uploads.KINDS)}")
    limit = 2_000_000 if kind == "universe" else uploads.MAX_BYTES
    chunks, size = [], 0
    while chunk := await file.read(65536):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"Upload exceeds {limit // 1_000_000} MB")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if kind != "universe":
        try:
            return await asyncio.to_thread(uploads.store_csv, raw, kind)
        except uploads.UploadError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
    try:
        rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        tickers = [row[0].strip() for row in rows if row and row[0].strip().lower() not in {"ticker", "symbol"}]
        if not tickers or len(tickers) > 5000:
            raise ValueError("Universe must contain 1 to 5000 symbols")
        resolved = parse_symbols({"symbols": tickers, "max_symbols": len(tickers)})
    except (ValueError, UnicodeError, csv.Error) as exc:
        raise HTTPException(422, str(exc)) from exc
    directory = ROOT / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    (directory / f"{identifier}.json").write_text(json.dumps({"symbols": resolved}), encoding="utf-8")
    return {"upload_id": identifier, "kind": kind, "symbols": resolved}
