"""HTTP access to the modular Screener V2 feature registry."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.screener_v2.registry import feature_manifest, get_feature, run_feature


from app.services.screener_v2.core.data_loader import BACKEND_DATA, available_symbols, parse_symbols
from app.services.studio.jobs import JobStore

RESULTS_DIR = BACKEND_DATA / "screener_v2" / "results"
JOBS = JobStore(path=BACKEND_DATA / "screener_v2" / "jobs.json")

router = APIRouter(prefix="/screener-v2")


class FeatureRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/features")
async def list_features() -> dict[str, Any]:
    return {"features": feature_manifest()}


@router.post("/run/{feature_id}")
async def run_screener_feature(feature_id: str, request: FeatureRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(run_feature, feature_id, request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/run/{feature_id}/csv")
async def run_screener_feature_csv(
    feature_id: str,
    file: UploadFile = File(...),
    payload: str = Form("{}"),
) -> dict[str, Any]:
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 2 MB limit")
    try:
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail="Invalid UTF-8 CSV") from exc
    tickers = []
    for row in rows:
        if not row:
            continue
        candidate = row[0].strip()
        if candidate and candidate.lower() not in {"ticker", "tickers", "symbol", "symbols"}:
            tickers.append(candidate)
    if not tickers:
        raise HTTPException(status_code=422, detail="CSV contains no ticker symbols in its first column")
    try:
        fields = json.loads(payload)
        if not isinstance(fields, dict):
            raise ValueError("payload must be a JSON object")
        return await asyncio.to_thread(run_feature, feature_id, {**fields, "tickers": tickers, "max_symbols": min(len(tickers), 5000)})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/export/{feature_id}.csv")
async def export_screener_feature_csv(feature_id: str, request: FeatureRequest) -> Response:
    try:
        feature = get_feature(feature_id)
        if feature.id != "08":
            raise ValueError("CSV export requires feature 08")
        result = await asyncio.to_thread(run_feature, feature_id, {**request.payload, "export_format": "csv"})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    downloads = result.get("tables", {}).get("instant_download", [])
    csv_text = downloads[0].get("csv", "") if downloads else ""
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="screener-v2-{feature_id}.csv"'},
    )


@router.get("/symbols")
def search_symbols(q: str = Query("", max_length=40), limit: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    query = q.strip().upper().replace(".", "_").replace("-", "_")
    hits = [s for s in available_symbols() if query in s]
    hits.sort(key=lambda s: (not s.startswith(query), s))
    return {"results": [{"ticker": s} for s in hits[:limit]]}


def _execute(job_id: str, feature_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = run_feature(feature_id, payload)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, allow_nan=False))
    tmp.replace(path)
    return {"result_file": path.name}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: FeatureRequest) -> dict[str, Any]:
    try:
        feature = get_feature(feature_id)
        parse_symbols(request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = JOBS.create(job_type=f"screener_v2_{feature.id}", params={"feature_id": feature.id, "payload": request.payload})
    if job["status"] == "queued":
        JOBS.submit(job["job_id"], _execute, job["job_id"], feature.id, request.payload)
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": feature.id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    out = {k: job[k] for k in ("job_id", "status", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        path = RESULTS_DIR / job["result"]["result_file"]
        if path.exists():
            out["result"] = json.loads(path.read_text())
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"job_id": job_id, "status": job["status"], "note": "Running computation finishes; cancellation suppresses publication."}
