"""Screener V2 common computations."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (pd.Timedelta, np.timedelta64)):
        return str(pd.Timedelta(value))
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (complex, np.complexfloating)):
        return {"real": clean_json(value.real), "imag": clean_json(value.imag)}
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def response(
    feature_id: str,
    summary_cards: list[dict[str, Any]] | None = None,
    charts: dict[str, Any] | None = None,
    tables: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return clean_json(
        {
            "feature_id": feature_id,
            "status": "ok",
            "summary_cards": summary_cards or [],
            "charts": charts or {},
            "tables": tables or {},
            "meta": meta or {},
        }
    )


def number_like(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    if limit:
        out = out.head(int(limit))
    return clean_json(out.replace([np.inf, -np.inf], np.nan).where(pd.notna(out), None).to_dict("records"))


def matrix_records(matrix: pd.DataFrame, value_name: str = "value") -> list[dict[str, Any]]:
    if matrix is None or matrix.empty:
        return []
    rows = []
    for r in matrix.index:
        for c in matrix.columns:
            v = number_like(matrix.loc[r, c])
            if v is not None:
                rows.append({"row": str(r), "col": str(c), value_name: v})
    return clean_json(rows)


def access_meta(payload: dict | None = None, issues: list[str] | None = None) -> dict[str, Any]:
    from .data_loader import AS_OF, MARKET_UNIVERSE, MASTER_FUNDAMENTALS, available_symbols, parse_symbols
    payload = payload or {}
    def version(path):
        return {"path": str(path), "exists": path.exists(), "modified_ns": path.stat().st_mtime_ns if path.exists() else None}
    requested = parse_symbols(payload)
    current = len(available_symbols())
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or 5000)
    return {"compute_mode": "local", "data_policy": "observed prices; no filling; conservative statement availability",
            "as_of_date": str((AS_OF.get() or pd.Timestamp(payload.get("as_of_date"))).date()),
            "data_sources": {"prices": version(MARKET_UNIVERSE), "fundamentals": version(MASTER_FUNDAMENTALS)},
            "universe_count": len(requested), "local_universe_count": current, "universe_cap": cap,
            "universe_order": "fixed local coverage order; not historical index membership",
            "fundamental_availability_lag_days": 90, "access_issues": issues or [],
            "limitations": ["No historical filing vintages or revision timestamps; 90-day lag does not eliminate restatement bias.",
                            "No historical index membership or delisting payoff data; results are conditional on the chosen local universe.",
                            "Current descriptive sector and industry labels are not historical classifications."]}
