"""ML V2 common implementation."""
from __future__ import annotations
from contextvars import ContextVar
from typing import Any, Callable, Iterable
import math
import numpy as np
import pandas as pd


PROGRESS: ContextVar[Callable[[int, str], None] | None] = ContextVar("ml_v2_progress", default=None)


class JobCancelled(RuntimeError):
    """Raised at a progress checkpoint after the caller cancelled the job."""


def report_progress(percent: int, message: str) -> None:
    """Publish a coarse stage to the running job (no-op outside a job); raises JobCancelled once cancelled."""
    callback = PROGRESS.get()
    if callback is not None:
        callback(percent, message)


def clean_json(value: Any) -> Any:  # A01 — type-identity checks, no isinstance MRO
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    t = type(value)
    if t is float:
        return value if (value == value and value != float("inf") and value != float("-inf")) else None
    if t is int or t is str or t is bool or value is None:
        return value
    if t is np.float64 or t is np.float32:
        v = float(value)
        return v if math.isfinite(v) else None
    if t is np.int64 or t is np.int32 or t is np.intp or t is np.int8 or t is np.int16:
        return int(value)
    if t is list:
        return [clean_json(v) for v in value]
    if t is dict:
        return {k if t is str else str(k): clean_json(v) for k, v in value.items()}
    if t is np.ndarray:
        return clean_json(value.tolist())
    if t is pd.Timestamp:
        return value.strftime("%Y-%m-%d")
    if t is pd.Series:
        return clean_json(value.tolist())
    if t is pd.DataFrame:
        return clean_json(value.to_dict("records"))
    if t is tuple:
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    return str(value)



def number_like(value: Any, default: float | None = None) -> float | None:  # A25
    if value is None:
        return default
    try:
        out = float(value)
        # NaN/inf check without math.isfinite call overhead (out==out is False for NaN)
        return out if (out == out and out != float("inf") and out != float("-inf")) else default
    except (TypeError, ValueError):
        return default



def compact_records(df: pd.DataFrame | None, limit: int = 500) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if len(out) > limit:
        idx = np.unique(np.round(np.linspace(0, len(out) - 1, limit)).astype(int))
        out = out.iloc[idx]
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    return clean_json(out.to_dict("records"))



def matrix_records(matrix: pd.DataFrame | np.ndarray, labels: Iterable[str] | None = None, limit: int = 80) -> list[dict[str, Any]]:
    # S09 — vectorized, no per-cell float() call
    if isinstance(matrix, pd.DataFrame):
        rows_lbl = [str(x) for x in matrix.index[:limit]]
        cols_lbl = [str(x) for x in matrix.columns[:limit]]
        arr = matrix.iloc[: len(rows_lbl), : len(cols_lbl)].to_numpy(dtype=float)
    else:
        arr = np.asarray(matrix, dtype=float)
        base = list(labels or [f"A{i+1}" for i in range(arr.shape[0])])
        rows_lbl = base[: min(limit, arr.shape[0])]
        cols_lbl = base[: min(limit, arr.shape[1])]
        arr = arr[: len(rows_lbl), : len(cols_lbl)]
    n_r, n_c = arr.shape
    return [
        {"row": rows_lbl[i], "col": cols_lbl[j], "value": arr[i, j]}
        for i in range(n_r) for j in range(n_c)
    ]



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



def merge_feature_contract(
    result: dict[str, Any],
    *,
    feature_title: str,
    input_contract: list[dict[str, Any]],
    output_contract: list[dict[str, Any]],
    research_only: list[str] | None = None,
    implementation_notes: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach feature-local contract metadata to a computed response.

    A23: skip full contract attachment on error paths to avoid wasting
    serialization cycles on ~2 KB of metadata per failed request.
    """
    out = dict(result)
    # A23 — fast path for error responses
    if out.get("status") == "error":
        out.setdefault("meta", {})["feature_title"] = feature_title
        return clean_json(out)

    meta = dict(out.get("meta") or {})
    meta.update(
        {
            "feature_title": feature_title,
            "input_contract": input_contract,
            "output_contract": output_contract,
            "research_only_components": research_only or [],
            "implementation_notes": implementation_notes or [],
            "contract_version": "ml_v2.2026-10-05",
        }
    )
    out["meta"] = clean_json(meta)
    return clean_json(out)



def summary(label: str, value: Any, unit: str = "", detail: str | None = None) -> dict[str, Any]:
    row = {"label": label, "value": value, "unit": unit}
    if detail:
        row["detail"] = detail
    return row






def date_str(x: Any) -> str:
    return pd.Timestamp(x).strftime("%Y-%m-%d")

