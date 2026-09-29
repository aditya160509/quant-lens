"""Shared scaffold response for Volatility V2 feature placeholders."""

from __future__ import annotations

from typing import Any

from app.services.volatility_v2.core.contracts import contract_for
from app.services.volatility_v2.core.data_pooling import missing_data_report


def scaffold_response(feature_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract_for(feature_id)
    payload = payload or {}
    requested = payload.get("symbols") or payload.get("tickers") or [payload.get("asset", "SPY")]
    if isinstance(requested, str):
        requested = [item.strip() for item in requested.split(",") if item.strip()]
    return {
        "feature_id": f"volatility_v2_feature_{feature_id}",
        "status": "scaffolded_not_wired",
        "summary_cards": [
            {"label": "Feature", "value": feature_id},
            {"label": "Required datasets", "value": len(contract["required_data"])},
            {"label": "Output contract", "value": len(contract["outputs"])},
        ],
        "charts": {},
        "tables": {
            "required_data": [{"dataset": item, "status": "required"} for item in contract["required_data"]],
            "planned_outputs": [{"output": item, "status": "planned"} for item in contract["outputs"]],
        },
        "alerts": [],
        "meta": {
            "title": contract["title"],
            "data_gap_report": missing_data_report(requested),
            "router_status": "not_integrated",
            "implementation_policy": "daily OHLCV and public macro only; no intraday/options dependency",
        },
    }
