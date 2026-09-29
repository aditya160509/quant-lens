"""Portfolio V2 API router."""
from __future__ import annotations
import asyncio
import importlib
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/labs/portfolio/v2", tags=["portfolio-v2"])
FEATURES = {str(i).zfill(2): f"feature_{i:02d}" for i in range(1, 14)}

@router.get("/features")
async def list_features():
    return {"status": "ok", "features": [{"id": key, "module": module} for key, module in FEATURES.items()]}

@router.post("/feature/{feature_id}/run")
async def run_feature(feature_id: str, request: Dict[str, Any]):
    key = str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)
    if key not in FEATURES:
        raise HTTPException(status_code=404, detail=f"Unknown Portfolio V2 feature: {feature_id}")
    payload = request.get("payload", request)
    try:
        module = importlib.import_module(f"app.services.portfolio_v2.features.{FEATURES[key]}")
        return await asyncio.to_thread(module.run, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

