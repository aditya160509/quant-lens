"""Research V2 signal endpoints: formula validation, operators, fields, library, saved signals."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.research_v2.core import signal_lang as sl
from app.services.research_v2.core import signal_service as svc
from app.services.research_v2.core import signal_store as store
from app.services.research_v2.core.signal_library import LIBRARY

router = APIRouter(prefix="/labs/research/v2", tags=["research-v2-signals"])


class ExprBody(BaseModel):
    expr: str


class SaveBody(BaseModel):
    name: str
    expr: str
    project_id: Optional[str] = None


class CombineBody(BaseModel):
    exprs: List[str]
    method: str = "equal"


@router.get("/signals/operators")
def operators() -> list[dict[str, Any]]:
    return [{"name": k, "args": v[1], "doc": v[2], "example": v[3], "category": v[4]} for k, v in sl.OPERATORS.items()]


@router.get("/signals/fields")
def fields() -> list[dict[str, Any]]:
    cov = sl.field_coverage()
    out = [{"name": k, "source": "price", "doc": d, "coverage": cov.get(k, 1.0)} for k, d in sl.PRICE_FIELDS.items()]
    out += [{"name": k, "source": "derived", "doc": d, "coverage": cov.get(k, 0.0)} for k, d in sl.DERIVED_FIELDS.items()]
    out += [{"name": k, "source": "fundamental", "doc": f"{d} (point in time, 90-day filing lag)", "coverage": cov.get(k, 0.0)} for k, (_, d) in sl.FUNDAMENTAL_FIELDS.items()]
    return out


@router.post("/signals/validate")
def validate(body: ExprBody) -> dict[str, Any]:
    try:
        return svc.validate(body.expr)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/signals/library")
def library() -> list[dict[str, Any]]:
    return LIBRARY


@router.post("/signals/saved")
def save_signal(body: SaveBody) -> dict[str, Any]:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    try:
        sl.parse(body.expr)
    except sl.SignalError as e:
        raise HTTPException(status_code=422, detail=e.as_dict())
    return store.save(body.name.strip(), body.expr, body.project_id)


@router.get("/signals/saved")
def list_saved() -> list[dict[str, Any]]:
    return store.list_saved()


@router.get("/signals/saved/{signal_id}")
def get_saved(signal_id: int) -> dict[str, Any]:
    rec = store.get(signal_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Unknown signal")
    return rec


@router.post("/signals/combine")
def combine(body: CombineBody) -> dict[str, str]:
    try:
        return {"expr": svc.combine(body.exprs, body.method)}
    except sl.SignalError as e:
        raise HTTPException(status_code=422, detail=e.as_dict())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
