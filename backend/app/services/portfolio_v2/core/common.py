"""Portfolio V2 common engine."""

from __future__ import annotations
from typing import Any, Iterable
import math
import numpy as np
import pandas as pd
from scipy.linalg import pinv as scipy_pinv
from .performance import (
    compact_table,
    fast_matrix_records,
)


def fast_pinv(mat: np.ndarray) -> np.ndarray:
    a = np.asfortranarray(mat, dtype=np.float64)
    return scipy_pinv(a, check_finite=False, atol=1e-12, rtol=0.0)


def fast_solve(mat: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(mat, dtype=np.float64)
    b = np.ascontiguousarray(rhs, dtype=np.float64)
    try:
        return np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        return fast_pinv(a) @ b


def clean_json(value: Any) -> Any:
    if value is None:
        return None
    t = type(value)
    if t is str or t is bool:
        return value
    if t is int:
        return value
    if t is float:
        return value if math.isfinite(value) else None
    if t is dict:
        return {str(k): clean_json(v) for k, v in value.items()}
    if t is list:
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.to_dict())
    if isinstance(value, pd.DataFrame):
        out = value.copy()
        for col in out.select_dtypes(
            include=["datetime64[ns]", "datetime64[ns, UTC]"]
        ).columns:
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        return clean_json(out.to_dict("records"))
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value


def number_like(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def compact_records(df: pd.DataFrame, limit: int = 600) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    tbl = compact_table(df, limit)
    dt_cols = [c for c in tbl.columns if pd.api.types.is_datetime64_any_dtype(tbl[c])]
    if dt_cols:
        tbl = tbl.copy()
        for col in dt_cols:
            tbl[col] = tbl[col].dt.strftime("%Y-%m-%d")
    return clean_json(tbl.to_dict("records"))


def matrix_records(
    matrix: pd.DataFrame | np.ndarray,
    labels: Iterable[str] | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    return clean_json(fast_matrix_records(matrix, labels, limit))


def response(
    feature_id, summary_cards, charts, tables, meta=None, alerts=None, status="ok"
):
    from ..registry import contract_for

    meta = meta or {}
    output_status = {}
    for item in contract_for(feature_id)["outputs"]:
        value = (
            {"charts": charts, "tables": tables, "summary_cards": summary_cards}.get(
                item["source"], {}
            ).get(item["key"])
            if item["source"] != "summary_cards"
            else summary_cards
        )
        output_status[item["key"]] = {
            "status": "produced"
            if value is not None and len(value) > 0
            else "not_produced",
            "reason": None
            if value is not None and len(value) > 0
            else "; ".join(meta.get("access_issues", []))
            or "Insufficient matching observed data for this optional output",
        }
    return clean_json(
        {
            "feature_id": "feature_" + str(feature_id).zfill(2),
            "status": "warning"
            if meta.get("access_issues") and status == "ok"
            else status,
            "summary_cards": summary_cards,
            "charts": charts,
            "tables": tables,
            "alerts": alerts or [],
            "meta": meta,
            "output_status": output_status,
        }
    )
