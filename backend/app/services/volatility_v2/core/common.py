"""JSON-safe Volatility response envelopes and record serialization."""

from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd


def clean_json(value: Any) -> Any:
    t = type(value)
    if t is float:
        return value if math.isfinite(value) else None
    if t is int or t is str or t is bool or value is None:
        return value
    if t is list:
        return [clean_json(v) for v in value]
    if t is dict:
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict("records"))
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def compact_records(df: pd.DataFrame, limit: int = 420) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    if len(out) > limit:
        idx = np.unique(np.round(np.linspace(0, len(out) - 1, limit)).astype(int))
        out = out.iloc[idx]
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].to_numpy(dtype="datetime64[D]").astype(str)
    return clean_json(out.to_dict("records"))


def response(
    feature_id: str,
    summary_cards: list[dict],
    charts: dict,
    tables: dict,
    alerts: list[dict] | None = None,
    meta: dict | None = None,
) -> dict:
    from ..registry import contract_for

    output_status = []
    for definition in contract_for(feature_id)["outputs"]:
        value = {"charts": charts, "tables": tables}[definition["source"]].get(
            definition["key"]
        )
        produced = value is not None and (
            not isinstance(value, (list, dict)) or bool(value)
        )
        output_status.append(
            {
                "key": definition["key"],
                "source": definition["source"],
                "status": "produced" if produced else "not_produced",
                "reason": None
                if produced
                else definition.get("empty_reason", "No complete observations"),
            }
        )
    return clean_json(
        {
            "output_status": output_status,
            "feature_id": f"feature_{feature_id}",
            "status": "ok",
            "summary_cards": summary_cards,
            "charts": charts,
            "tables": tables,
            "alerts": alerts or [],
            "meta": {
                "engine": "volatility_v2",
                "data_policy": "local parquet only; no runtime mutation",
                **(meta or {}),
            },
        }
    )


def matrix_records(
    mat: pd.DataFrame, value_name: str = "value"
) -> list[dict[str, Any]]:
    rows = []
    for r in mat.index:
        for c in mat.columns:
            rows.append(
                {"row": str(r), "col": str(c), value_name: float(mat.loc[r, c])}
            )
    return clean_json(rows)


def summary_card(
    label: str, value: Any, unit: str = "", **extra: Any
) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, **extra}


def mapping_from_pairs(pairs):
    """Reject duplicate JSON/text keys rather than silently overwriting controls."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate mapping key: {key}")
        result[key] = value
    return result
