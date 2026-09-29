"""Shared response and formatting helpers for Research V2 features."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .performance import cached_data_inventory


def number(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def records(df: pd.DataFrame | pd.Series | list[dict[str, Any]] | dict[str, Any] | None, limit: int | None = None) -> list[dict[str, Any]]:
    """JSON-safe list of row dicts. NaN and inf become None; timestamps become ISO dates."""

    if df is None:
        return []
    if isinstance(df, list):
        out = [_clean_row(r) for r in df]
    elif isinstance(df, dict):
        out = [_clean_row(df)]
    else:
        frame = df.reset_index() if isinstance(df, pd.Series) else df
        if isinstance(df, pd.Series):
            frame = frame.rename(columns={0: "value"})
        out = [_clean_row(r) for r in frame.to_dict("records")]
    return out if limit is None else out[:limit]


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _clean_value(v) for k, v in row.items()}


def _clean_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts.strftime("%Y-%m-%d")
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, dict):
        return _clean_row(value)
    if isinstance(value, (list, tuple)):
        return [_clean_value(v) for v in value]
    if value is pd.NaT or (not isinstance(value, str) and pd.api.types.is_scalar(value) and pd.isna(value)):
        return None
    return value


def response(feature_id: str, summary_cards: list[dict[str, Any]], charts: dict[str, Any], tables: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    return {
        "feature_id": str(feature_id).zfill(2),
        "status": "ok",
        "summary_cards": [_clean_row(c) for c in summary_cards],
        "charts": {k: records(v) for k, v in charts.items()},
        "tables": {k: records(v) for k, v in tables.items()},
        "meta": _clean_row({"data_inventory": cached_data_inventory(), "research_caveats": meta.pop("research_caveats", []), **meta}),
    }


def stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def latex_table(caption: str, df: pd.DataFrame, float_format: str = "{:.4f}") -> str:
    """booktabs LaTeX table from a DataFrame."""

    if df is None or df.empty:
        return f"% {caption}: no rows"
    cols = list(df.columns)

    def fmt(v: Any) -> str:
        if isinstance(v, (float, np.floating)):
            return float_format.format(v) if np.isfinite(v) else ""
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d")
        return str(v).replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")

    lines = [
        "\\begin{table}[htbp]\\centering",
        f"\\caption{{{fmt(caption)}}}",
        f"\\begin{{tabular}}{{l{'c' * (len(cols) - 1)}}}",
        "\\toprule",
        " & ".join(fmt(c) for c in cols) + " \\\\",
        "\\midrule",
        *[" & ".join(fmt(v) for v in row) + " \\\\" for row in df.itertuples(index=False)],
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ]
    return "\n".join(lines)


def verdict_color(p: float, good_when_small: bool = True) -> str:
    if not np.isfinite(p):
        return "grey"
    significant = p < 0.05
    return "green" if significant == good_when_small else "red"
