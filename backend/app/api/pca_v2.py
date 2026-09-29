"""HTTP API for PCA V2 feature discovery and execution."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.pca_v2.registry import PCA_V2_FEATURES, run_feature


router = APIRouter(prefix="/labs/pca/v2", tags=["pca-v2"])


@router.get("/features")
async def list_features() -> Dict[str, Any]:
    return {
        "status": "ok",
        "features": [
            {"id": item.id, "title": item.title, "status": item.status}
            for item in PCA_V2_FEATURES.values()
        ],
    }


@router.post("/feature/{feature_id}/run")
async def execute_feature(feature_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
    payload = request.get("payload", request)
    try:
        return await asyncio.to_thread(run_feature, feature_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
