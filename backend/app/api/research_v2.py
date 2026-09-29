"""Research V2 API router.

Mounted from backend/main.py with prefix="/api", so routes resolve under
/api/labs/research/v2. Feature runs are background jobs (reusing the durable
Studio JobStore with its own file) because permutation and bootstrap
batteries can take tens of seconds; results are written to one JSON file per
job so the job index stays small.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services.research_v2.core.data_loader import BACKEND_DATA, UPLOAD_DIR, UnknownSymbolsError, available_symbols, static_sectors
from app.services.research_v2.core.holdout import all_locks, all_windows, lock_specification, release_window
from app.services.research_v2.registry import feature_manifest, get_feature, run_feature
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/labs/research/v2", tags=["research-v2"])

RESULTS_DIR = BACKEND_DATA / "research_v2" / "results"
JOBS = JobStore(path=BACKEND_DATA / "research_v2" / "jobs.json")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_KINDS = {
    "signal": {"date", "ticker", "signal"},
    "event": {"ticker", "treatment_date"},
    "instrument": {"date", "instrument"},
    "factors": {"date"},
}
ALIASES = {"symbol": "ticker", "asset": "ticker", "rank": "signal", "score": "signal", "event_date": "treatment_date", "month": "date"}


class RunRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class LockRequest(BaseModel):
    spec: Dict[str, Any]
    note: str = ""


def _clean(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in payload.items() if v not in ("", None, [])}


def _execute(job_id: str, feature_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = run_feature(feature_id, payload)
    except UnknownSymbolsError as exc:
        raise ValueError(str(exc)) from exc
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, default=str))
    tmp.replace(path)
    return {"result_file": path.name, "bytes": path.stat().st_size}


@router.get("/features")
def list_features() -> Dict[str, Any]:
    return {"status": "ok", "features": feature_manifest()}


@router.get("/symbols")
def search_symbols(q: str = Query("", max_length=40), limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    query = q.strip().upper().replace(".", "_").replace("-", "_")
    sectors = static_sectors()
    hits = [s for s in available_symbols() if s.startswith(query)] if query else []
    hits += [s for s in available_symbols() if query and query in s and s not in hits]
    return {"results": [{"ticker": s, "sector": sectors.get(s)} for s in hits[:limit]]}


@router.post("/uploads")
async def upload(kind: str = Query(..., pattern="^(signal|event|instrument|factors)$"), file: UploadFile = File(...)) -> Dict[str, Any]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".parquet"}:
        raise HTTPException(status_code=422, detail="Upload a .csv or .parquet file.")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploads are limited to 20 MB.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = f"{kind}_{uuid.uuid4().hex[:12]}{suffix}"
    path = UPLOAD_DIR / upload_id
    path.write_bytes(raw)
    try:
        df = pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not parse the file: {exc}") from exc
    cols = {ALIASES.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns}
    missing = UPLOAD_KINDS[kind] - cols
    if missing:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"The {kind} file needs columns {sorted(UPLOAD_KINDS[kind])}; missing {sorted(missing)}.")
    return {"upload_id": upload_id, "rows": int(len(df)), "columns": list(map(str, df.columns))}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: RunRequest) -> Dict[str, Any]:
    try:
        feature = get_feature(feature_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = _clean(request.payload)
    job = JOBS.create(job_type=f"research_v2_{feature.id}", params={"feature_id": feature.id, "payload": payload})
    if job["status"] == "queued":
        JOBS.submit(job["job_id"], _execute, job["job_id"], feature.id, payload)
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": feature.id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    out = {k: job[k] for k in ("job_id", "type", "status", "created_at", "updated_at", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        path = RESULTS_DIR / job["result"]["result_file"]
        if path.exists():
            out["result"] = json.loads(path.read_text())
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"job_id": job_id, "status": job["status"], "note": "Cancellation stops the result from being published; a computation already running finishes in the background."}


@router.get("/holdouts")
def list_holdouts() -> Dict[str, Any]:
    return {"holdouts": all_windows()}


@router.delete("/holdouts/{study_key:path}")
def release_holdout(study_key: str) -> Dict[str, Any]:
    if not release_window(study_key):
        raise HTTPException(status_code=404, detail="No protected window for that study")
    return {"released": study_key}


@router.get("/locks")
def list_locks() -> Dict[str, Any]:
    return {"locks": all_locks()}


@router.post("/locks")
def create_lock(request: LockRequest) -> Dict[str, Any]:
    return lock_specification(request.spec, request.note)
