"""Factors V2 common helpers."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List
import numpy as np
import pandas as pd

FACTOR_ALIASES = {
    "value": "value_pb",
    "value_pb": "value_pb",
    "value_ep": "value_ep",
    "momentum": "momentum_12_1",
    "momentum_12_1": "momentum_12_1",
    "momentum_6_1": "momentum_6_1",
    "quality": "quality_roe",
    "quality_roe": "quality_roe",
    "low_vol": "low_vol",
    "size": "size",
    "growth": "growth",
    "investment": "investment",
    "profitability": "profitability",
}
DEFAULT_FACTORS = ["value_pb", "momentum_12_1", "quality_roe", "low_vol", "size"]


def clean_json(value: Any) -> Any:
    # Fast path for the most common scalar types to reduce isinstance overhead.
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict(orient="records"))
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def governance_metadata(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = {
        "model_risk": {
            "model_version": "factors_v2.2026-05-08",
            "output_use": "informational analytics only; not an investment recommendation",
            "validation_required": "user must review model assumptions, input data quality, and suitability before use",
            "revalidation_policy": "annual model review plus revalidation after formula, dependency, or data-source changes",
            "audit_trail": "feature response includes payload, data lineage, model version, and generated timestamp",
        },
        "data_quality_policy": {
            "target_completeness": 0.995,
            "missing_data_protocol": "complete-case universe for cross-section factors; pairwise/listwise covariance handling by estimator",
            "latency_target": "T+1 local data availability",
            "reduced_universe_flag": "outputs expose available row counts and warnings when local data are incomplete",
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    if extra:
        base.update(extra)
    return base


def response(
    feature_id: str,
    status: str = "ok",
    summary_cards: List[Dict[str, Any]] | None = None,
    charts: Dict[str, Any] | None = None,
    tables: Dict[str, Any] | None = None,
    alerts: List[Dict[str, Any]] | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    contract_meta: Dict[str, Any] = {}
    from .contracts import FEATURE_CONTRACTS

    fid = feature_id.replace("feature_", "").replace("feature-", "").zfill(2)
    contract = FEATURE_CONTRACTS.get(fid, {})
    from ..features.inputs import inputs, outputs

    contract_meta = {
        "contract": {
            "title": contract.get("title"),
            "inputs": inputs(fid),
            "outputs": outputs(fid),
            "math_source": contract.get("math_source"),
            "status": "supported_contract",
        }
    }
    merged_meta = {
        "governance": governance_metadata(),
        "compute_mode": "realtime",
        "data_lineage": {
            "factor_returns": "backend/data/factors_us plus factors/data/processed/aqr_csv when include_aqr=true",
            "market_universe": "backend/data/market_universe.parquet",
            "fundamentals": "backend/data/fundamentals/master_fundamentals.parquet",
            "macro": "factors/data/processed/category7_macro_regime.parquet",
        },
        "as_of_date": __import__(
            "app.services.factors_v2.core.data_loader", fromlist=["request_payload"]
        )
        .request_payload()
        .get("as_of_date"),
        "source_limitations": [
            "90-day statement lag is an availability assumption, not a verified filing vintage",
            "Historical constituent/delisted coverage is incomplete",
            "Stored Close adjustment provenance is unverified",
            "Static instrument declarations must be valid throughout the run",
        ],
        "characteristic_return_currency": "USD when instrument_metadata is supplied; otherwise explicitly native quote returns",
        "missing_data_policy": "complete local observations are used; outputs expose reduced sample counts and explicit warnings for unavailable data",
        **contract_meta,
    }
    if meta:
        merged_meta.update(meta)
    return clean_json(
        {
            "feature_id": feature_id,
            "status": status,
            "summary_cards": summary_cards or [],
            "charts": charts or {},
            "tables": tables or {},
            "alerts": alerts or [],
            "meta": merged_meta,
        }
    )


def normalize_factor_name(name: str | None) -> str:
    return FACTOR_ALIASES.get(
        (name or "value_pb").lower(), (name or "value_pb").lower()
    )


def compact_series(s: pd.Series, limit: int = 260) -> List[Dict[str, Any]]:
    s = s.dropna()
    if len(s) > limit:
        s = s.iloc[np.round(np.linspace(0, len(s) - 1, limit)).astype(int, copy=False)]
    # Fix #9: avoid per-item hasattr check — vectorize index stringification.
    dates = [str(idx.date()) if hasattr(idx, "date") else str(idx) for idx in s.index]
    values = s.values.tolist()
    return [{"date": d, "value": v} for d, v in zip(dates, values)]


def matrix_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    # Fix #10: vectorized unravel instead of O(N*M) nested Python loop.
    idx_arr = np.repeat(df.index.tolist(), len(df.columns))
    col_arr = np.tile(df.columns.tolist(), len(df.index))
    val_arr = df.values.ravel()
    return [
        {"row": r, "column": c, "value": v.item() if np.isfinite(v) else None}
        for r, c, v in zip(idx_arr, col_arr, val_arr)
    ]
