"""Research V2 reports, protocol, batch screening, validation, universes and literature routes.

Mounted next to research_v2.router under /api/labs/research/v2. Jobs reuse the
Research V2 job store, results directory and worker pool.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.api import research_v2 as core_api
from app.services.research_v2 import reports, universes
from app.services.research_v2.core.data_loader import UnknownSymbolsError
from app.services.research_v2.worker import run_special
from app.services.research_v2.store import get_store

router = APIRouter(prefix="/labs/research/v2", tags=["research-v2-reports"])


class ReportCardRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class BatchRequest(BaseModel):
    signals: List[str] = Field(min_length=1, max_length=500)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ValidationRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    method: str = Field("walk_forward", pattern="^(walk_forward|cpcv)$")
    folds: int = Field(5, ge=3, le=12)
    embargo_days: int = Field(30, ge=0, le=365)


def _execute(job_id: str, kind: str, payload: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = core_api._pool().submit(run_special, kind, payload, args).result()
    except UnknownSymbolsError as exc:
        raise ValueError(str(exc)) from exc
    core_api.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = core_api.RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, default=str))
    tmp.replace(path)
    # Persist like feature jobs so report cards, screens and validations survive restarts and can be shared.
    get_store().save_job(job_id, kind, payload, "completed", 1.0, result, project_id=payload.get("project_id"))
    return {"result_file": path.name, "bytes": path.stat().st_size}


def _submit(kind: str, payload: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    payload = core_api._clean(payload)
    job = core_api.JOBS.create(job_type=f"research_v2_{kind}", params={"kind": kind, "payload": payload, "args": args})
    if job["status"] == "queued":
        get_store().save_job(job["job_id"], kind, payload, job["status"], project_id=payload.get("project_id"))
        core_api.JOBS.submit(job["job_id"], _execute, job["job_id"], kind, payload, args)
    return {"job_id": job["job_id"], "status": job["status"], "kind": kind}


@router.post("/report-card/jobs")
def report_card_job(request: ReportCardRequest) -> Dict[str, Any]:
    return _submit("report_card", request.payload, {})


@router.post("/batch/jobs")
def batch_job(request: BatchRequest) -> Dict[str, Any]:
    return _submit("batch", request.payload, {"signals": request.signals})


@router.post("/validation/jobs")
def validation_job(request: ValidationRequest) -> Dict[str, Any]:
    return _submit("validation", request.payload, {"method": request.method, "folds": request.folds, "embargo_days": request.embargo_days})


@router.get("/universes")
def list_universes() -> List[Dict[str, Any]]:
    return universes.list_universes()


@router.get("/literature/match")
def literature_match(expr: str = Query(..., min_length=1, max_length=500), limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    try:
        return reports.literature_match(expr, limit=limit)
    except (ValueError, UnknownSymbolsError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/report/{name}")
def report(name: str) -> Response:
    job_id, _, ext = name.rpartition(".")
    if ext not in {"tex", "pdf", "md"} or not job_id:
        raise HTTPException(status_code=404, detail="Use /report/{job_id}.tex, .pdf or .md")
    path = core_api.RESULTS_DIR / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Unknown or unfinished job")
    job = json.loads(path.read_text())
    if "grades" not in job:
        raise HTTPException(status_code=422, detail="Reports exist only for report-card jobs")
    if ext == "tex":
        return Response(reports.report_tex(job), media_type="application/x-tex")
    if ext == "md":
        return Response(reports.report_markdown(job), media_type="text/markdown")
    try:
        return Response(reports.report_pdf(job), media_type="application/pdf")
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF export needs reportlab; use .tex or .md")
