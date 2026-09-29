"""HTTP API for Volatility V2 feature discovery and execution."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.volatility_v2.core.contracts import all_contracts
from app.services.volatility_v2.registry import run_feature


router = APIRouter(prefix="/labs/volatility/v2", tags=["volatility-v2"])


@router.get("/features")
async def list_features() -> Dict[str, Any]:
    return {"status": "ok", "features": all_contracts()}


@router.post("/feature/{feature_id}/run")
async def execute_feature(feature_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
    payload = request.get("payload", request)
    try:
        return await asyncio.to_thread(run_feature, feature_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

