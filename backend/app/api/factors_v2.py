"""Factors V2 API router.

Mounted from backend/main.py with prefix="/api", so routes resolve under
/api/labs/factors/v2 while legacy /api/labs/factors remains untouched.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.factors_v2.core.analytics import clean_json, governance_metadata
from app.services.factors_v2.core.contracts import FEATURE_CONTRACTS, FEATURE_MODULES, FEATURE_OUTPUT_KEYS, STANDARD_OUTPUT_SCHEMA
from app.services.factors_v2.core.data_loader import search_symbol_directory

router = APIRouter(prefix="/labs/factors/v2", tags=["factors-v2"])
logger = logging.getLogger(__name__)


class FactorsV2RunRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict, description="Feature-specific input payload from computation document")


class FactorsV2DirectPayload(BaseModel):
    class Config:
        extra = "allow"


def _normalize_feature_id(feature_id: str) -> str:
    raw = str(feature_id).lower().replace("feature_", "").replace("feature-", "").strip()
    if raw.isdigit():
        raw = raw.zfill(2)
    if raw not in FEATURE_CONTRACTS:
        raise HTTPException(status_code=404, detail=f"Unknown Factors V2 feature: {feature_id}")
    return raw


def _feature_module(feature_id: str):
    normalized = _normalize_feature_id(feature_id)
    module_name = FEATURE_MODULES.get(normalized, f"feature_{normalized}")
    return importlib.import_module(f"app.services.factors_v2.features.{module_name}")


def _clean_payload_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: cleaned for key, item in value.items() if (cleaned := _clean_payload_value(item)) is not None}
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _clean_payload_value(item)) is not None]
    if value == "":
        return None
    return value


def _sanitize_payload(payload: Any) -> Dict[str, Any]:
    cleaned = _clean_payload_value(payload or {})
    return cleaned if isinstance(cleaned, dict) else {}


@router.get("/features")
def list_features() -> Dict[str, Any]:
    return clean_json(
        {
            "status": "ok",
            "schema": STANDARD_OUTPUT_SCHEMA,
            "required_output_keys": FEATURE_OUTPUT_KEYS,
            "features": [
                {
                    "feature_id": f"feature_{feature_id}",
                    "route_id": feature_id,
                    "module": FEATURE_MODULES.get(feature_id),
                    **contract,
                }
                for feature_id, contract in FEATURE_CONTRACTS.items()
            ],
            "activation_note": "Router is mounted from backend/main.py under /api/labs/factors/v2.",
        }
    )


@router.get("/governance")
def governance() -> Dict[str, Any]:
    return clean_json({"status": "ok", **governance_metadata({"api_scope": "Dormant Factors V2 governance, lineage, and model-risk metadata"})})


@router.get("/symbols")
def search_symbols(
    q: str = Query(default="", description="Ticker, index, sector, or industry prefix/substring"),
    limit: int = Query(default=25, ge=1, le=75),
    asset_type: Optional[str] = Query(default=None, description="Optional filter: equity or index"),
) -> Dict[str, Any]:
    return clean_json(
        {
            "status": "ok",
            "query": q,
            "symbols": search_symbol_directory(q, limit=limit, asset_type=asset_type),
            "source": "backend/data/market_universe.parquet + backend/data/fundamentals/master_fundamentals.parquet",
        }
    )


@router.post("/feature/{feature_id}/run")
def run_feature(feature_id: str, request: FactorsV2RunRequest) -> Dict[str, Any]:
    normalized = _normalize_feature_id(feature_id)
    payload = _sanitize_payload(request.payload)
    try:
        result = _feature_module(normalized).run(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Factors V2 feature_%s failed", normalized)
        raise HTTPException(status_code=500, detail=f"Factors V2 feature_{normalized} failed") from exc
    return clean_json(result)


@router.post("/run-all")
def run_all(request: Dict[str, Any]) -> Dict[str, Any]:
    base_payload = _sanitize_payload(request.get("payload", request))
    feature_payloads = request.get("feature_payloads", {}) or {}
    results = {}
    for feature_id in FEATURE_CONTRACTS:
        payload = _sanitize_payload({**base_payload, **feature_payloads.get(feature_id, {}), **feature_payloads.get(f"feature_{feature_id}", {})})
        try:
            results[f"feature_{feature_id}"] = _feature_module(feature_id).run(payload)
        except Exception as exc:
            results[f"feature_{feature_id}"] = {
                "feature_id": f"feature_{feature_id}",
                "status": "error",
                "summary_cards": [],
                "charts": {},
                "tables": {},
                "alerts": [{"level": "error", "message": str(exc)}],
                "meta": {"error": str(exc)},
            }
    return clean_json({"status": "ok", "results": results, "contracts": FEATURE_CONTRACTS})


@router.post("/export/{feature_id}")
def export_feature(feature_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
    """Dormant export endpoint returning JSON plus CSV-ready table payloads."""
    normalized = _normalize_feature_id(feature_id)
    result = clean_json(_feature_module(normalized).run(_sanitize_payload(request.get("payload", request))))
    return clean_json(
        {
            "status": "ok",
            "feature_id": result.get("feature_id"),
            "formats": ["json", "csv_tables", "parquet_future"],
            "json": result,
            "csv_tables": result.get("tables", {}),
            "lineage": result.get("meta", {}).get("governance"),
        }
    )


@router.post("/alert-subscription")
def alert_subscription(request: Dict[str, Any]) -> Dict[str, Any]:
    return clean_json(
        {
            "status": "registered_dormant",
            "channels": request.get("channels", ["in_app"]),
            "webhook_url_present": bool(request.get("webhook_url")),
            "cooldown_hours": request.get("cooldown_hours", 24),
            "activation_note": "Subscription schema is ready; delivery worker remains disabled until router is wired.",
        }
    )
