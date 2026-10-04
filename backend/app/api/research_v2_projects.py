"""Research V2 projects, trial ledger, holdout seal, preregistration and share links."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.research_v2.store import get_store

router = APIRouter(prefix="/labs/research/v2", tags=["research-v2-projects"])


class ProjectIn(BaseModel):
    name: str
    description: str = ""


class HoldoutIn(BaseModel):
    sealed_after: Optional[str] = None
    unseal: bool = False


class PreregIn(BaseModel):
    project_id: str
    hypothesis: str
    expected_sign: str
    primary_test: str
    signal: str


class ShareIn(BaseModel):
    job_id: str


def _project(pid: str) -> Dict[str, Any]:
    p = get_store().get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="Unknown project")
    return p


@router.get("/projects")
def list_projects() -> Dict[str, Any]:
    return {"projects": get_store().list_projects()}


@router.post("/projects")
def create_project(body: ProjectIn) -> Dict[str, Any]:
    return get_store().create_project(body.name, body.description)


@router.get("/projects/{pid}")
def get_project(pid: str) -> Dict[str, Any]:
    p = _project(pid)
    s = get_store()
    runs = [{"job_id": j["id"], "feature_id": j["feature_id"], "status": j["status"], "created_at": j["created_at"], "signal": (j["payload"] or {}).get("signal")} for j in s.project_jobs(pid)]
    return {**p, "runs": runs, "signals": sorted({r["signal"] for r in runs if r["signal"]}), "preregistrations": s.preregs(pid)}


@router.get("/projects/{pid}/ledger")
def ledger(pid: str) -> Dict[str, Any]:
    _project(pid)
    return get_store().ledger(pid)


@router.get("/projects/{pid}/holdout")
def get_holdout(pid: str) -> Dict[str, Any]:
    _project(pid)
    return get_store().holdout(pid)


@router.post("/projects/{pid}/holdout")
def set_holdout(pid: str, body: HoldoutIn) -> Dict[str, Any]:
    _project(pid)
    s = get_store()
    if body.unseal:
        s.set_holdout(pid, None)
    elif body.sealed_after:
        s.set_holdout(pid, body.sealed_after)
    else:
        raise HTTPException(status_code=422, detail="Provide sealed_after or unseal:true")
    return s.holdout(pid)


@router.post("/preregistrations")
def create_prereg(body: PreregIn) -> Dict[str, Any]:
    _project(body.project_id)
    return get_store().create_prereg(body.project_id, body.hypothesis, body.expected_sign, body.primary_test, body.signal)


@router.post("/share")
def create_share(body: ShareIn) -> Dict[str, Any]:
    token = get_store().create_share(body.job_id)
    if not token:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"token": token}


@router.get("/share/{token}")
def read_share(token: str) -> Dict[str, Any]:
    out = get_store().get_share(token)
    if not out:
        raise HTTPException(status_code=404, detail="Unknown share link")
    return out
