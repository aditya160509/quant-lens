"""Dedicated ML V2 API with durable module-owned jobs."""
from __future__ import annotations
import asyncio
import csv
import io
import json
import uuid
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from app.services.ml_v2.registry import feature_manifest, get_ml_v2_feature, run_feature
from app.services.ml_v2.core.data_loader import BACKEND_DATA, available_symbols, parse_symbols
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/ml/v2")
ROOT = BACKEND_DATA / "ml_v2"
JOBS = JobStore(path=ROOT / "jobs.json")

@router.get("/features")
def list_features():
    return {"features": feature_manifest()}

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

def _execute_job(job_id, feature_id, payload):
    result = run_feature(feature_id, payload)
    if result.get("status") == "error":
        raise ValueError(result.get("alerts") or "Feature execution failed")
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
        parse_symbols(payload)
        job = JOBS.create(job_type=f"ml_v2_{feature.id}", params={"feature_id": feature.id, "payload": payload})
        JOBS.submit(job["job_id"], _execute_job, job["job_id"], feature.id, payload)
        return {"job_id": job["job_id"], "status": job["status"]}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc

@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown ML V2 job")
    out = {key: job[key] for key in ["job_id", "status", "progress", "error"]}
    if job["status"] == "completed":
        path = ROOT / "results" / job["result"]["result_file"]
        if not path.is_file():
            raise HTTPException(503, "Completed result artifact is missing")
        out["result"] = json.loads(path.read_text())
    return out

@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = JOBS.cancel(job_id)
    if job is None:
        raise HTTPException(404, "Unknown ML V2 job")
    return {"job_id": job_id, "status": job["status"],
            "note": "Cancellation suppresses publication; an active estimator finishes."}

@router.post("/uploads")
async def upload(kind: str = Query("universe"), file: UploadFile = File(...)):
    if kind != "universe":
        raise HTTPException(422, "Only ticker universe CSV uploads are supported")
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Upload exceeds 2 MB")
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
