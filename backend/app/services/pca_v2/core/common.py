"""PCA V2 common helpers."""
from __future__ import annotations
import math
from typing import Any, Iterable
import numpy as np
import pandas as pd
from .data_loader import annualization_factor


def clean_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict("records"))
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value



def number_like(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default



def response(
    feature_id: str,
    summary_cards: list[dict[str, Any]],
    charts: dict[str, Any],
    tables: dict[str, Any],
    alerts: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    return clean_json(
        {
            "feature_id": f"feature_{str(feature_id).zfill(2)}",
            "status": status,
            "summary_cards": summary_cards,
            "charts": charts,
            "tables": tables,
            "alerts": alerts or [],
            "meta": meta or {},
        }
    )



def compact_records(df: pd.DataFrame, limit: int = 500) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if len(out) > limit:
        idx = np.unique(np.round(np.linspace(0, len(out) - 1, limit)).astype(int))
        out = out.iloc[idx]
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return clean_json(out.to_dict("records"))



def matrix_records(matrix: pd.DataFrame | np.ndarray, labels: Iterable[str] | None = None, limit: int = 120) -> list[dict[str, Any]]:
    if isinstance(matrix, pd.DataFrame):
        row_labels = [str(x) for x in matrix.index]
        col_labels = [str(x) for x in matrix.columns]
        arr = matrix.to_numpy(dtype=float)
    else:
        arr = np.asarray(matrix, dtype=float)
        base = list(labels or [f"A{i+1}" for i in range(arr.shape[0])])
        row_labels = base[: arr.shape[0]]
        col_labels = base[: arr.shape[1]]
    n = min(arr.shape[0], limit)
    m = min(arr.shape[1], limit)
    rows = []
    for i in range(n):
        for j in range(m):
            rows.append({"row": row_labels[i], "col": col_labels[j], "value": float(arr[i, j])})
    return clean_json(rows)



def metadata(model: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "requested_symbol_count": len(model.get("requested_symbols",model["symbols"])),
        "resolved_symbol_count": len(model["symbols"]),
        "data_coverage": model.get("data_coverage", {}),
        "matrix_type": model.get("matrix_type", "covariance"),
        "outlier_method": model.get("outlier_method", "none"),
        "default_universe_rule": model.get("default_universe_rule"),
        "bootstrap_runs_requested": model.get("bootstrap_runs_requested"),
        "bootstrap_runs_executed": model.get("bootstrap_runs_executed"),
        "symbols": model["symbols"],
        "n_assets": len(model["symbols"]),
        "n_observations": int(model["returns"].shape[0]),
        "date_start": str(pd.Timestamp(model["returns"].index.min()).date()) if len(model["returns"]) else None,
        "date_end": str(pd.Timestamp(model["returns"].index.max()).date()) if len(model["returns"]) else None,
        "k_selected": int(model["k"]),
        "k_criteria": model["k_info"],
        "mp": model["mp"],
        "covariance": model["cov_meta"],
        "frequency": model.get("frequency", "daily"),
        "annualization_factor": model_annualization(model),
        "default_portfolio_rule": "equal_weight; historical shares unavailable",
        "data_sources": ["backend/data/market_universe.parquet", "backend/data/fundamentals/master_fundamentals.parquet", "factors/data/processed/category7_macro_regime.parquet"],
    }
    if extra:
        out.update(extra)
    return out



def model_annualization(model: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> float:
    if model and model.get("annualization_factor"):
        return float(model["annualization_factor"])
    frequency = (model or {}).get("frequency") or (payload or {}).get("sampling_frequency") or (payload or {}).get("frequency") or "daily"
    return float(annualization_factor(frequency))



def parse_compute_mode(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    raw = str(payload.get("compute_mode") or payload.get("mode") or "realtime").lower()
    if raw == "research" or payload.get("research_mode") is True:
        return "research"
    return "realtime"

