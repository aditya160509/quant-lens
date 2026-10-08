"""Portfolio V2 context engine."""

from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import (
    annualization_factor,
    normalize_symbol,
    parse_symbols,
    returns_matrix,
    sector_map,
    source_version,
)
from .performance import (
    performance_snapshot,
)


def parse_compute_mode(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    return (
        "research"
        if str(payload.get("compute_mode") or "").lower() == "research"
        or payload.get("research_mode") is True
        else "realtime"
    )


def load_context(payload=None, *, min_symbols=1, default_limit=12):
    payload = dict(payload or {})
    if "aum" in payload:
        if "portfolio_nav" in payload and payload["aum"] != payload["portfolio_nav"]:
            raise ValueError("Conflicting aum and portfolio_nav")
        payload["portfolio_nav"] = payload.pop("aum")
    lookback = int(payload.get("lookback_days", 756))
    if lookback < 30:
        raise ValueError("lookback_days must be at least 30")
    frequency = payload.get("frequency", "daily")
    symbols = parse_symbols(payload, default_limit=default_limit)
    raw_returns = returns_matrix(symbols, lookback, frequency).reindex(columns=symbols)
    rets = raw_returns.dropna()
    if len(rets) < 30:
        raise ValueError(
            "At least 30 complete observed return intervals are required for every requested asset"
        )
    weights = parse_weights(payload, symbols)
    if weights is None:
        weights = pd.Series(1 / len(symbols), index=symbols)
    if (
        payload.get("sector_max_weights")
        and payload.get("as_of_date")
        and pd.Timestamp(payload["as_of_date"]).normalize()
        < pd.Timestamp.today().normalize()
    ):
        raise ValueError(
            "Historical sector constraints require point-in-time sector classifications"
        )
    sectors = sector_map(symbols)
    payload["sector_map"] = sectors
    return {
        "payload": payload,
        "symbols": symbols,
        "returns": rets,
        "raw_returns": raw_returns,
        "weights": weights,
        "lookback_days": lookback,
        "frequency": frequency,
        "annualization_factor": annualization_factor(frequency),
        "sectors": sectors,
        "market_caps": {},
        "compute_mode": parse_compute_mode(payload),
        "inventory": {"source_versions": source_version()},
        "data_issues": [
            f"Complete-case analysis excludes {len(raw_returns) - len(rets)} incomplete intervals",
            "Default weights, when omitted, are explicitly equal-weight; sectors are static current classifications",
            "Default universe is ranked by observed history, not historical index membership",
        ],
    }


def parse_weights(payload, symbols):
    raw = payload.get("weights", payload.get("portfolio_weights"))
    if raw is None:
        return None
    if isinstance(raw, str):
        pairs = []
        for part in raw.replace(";", ",").split(","):
            if ":" not in part:
                raise ValueError("Weights must be SYMBOL:value pairs")
            key, value = part.split(":", 1)
            pairs.append((key, value))
    elif isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, list):
        pairs = [
            (r.get("ticker", r.get("symbol")), r.get("weight", r.get("target_weight")))
            for r in raw
        ]
    else:
        raise ValueError("Weights must be a mapping or SYMBOL:value pairs")
    out = {}
    for key, value in pairs:
        key = normalize_symbol(key)
        if key not in symbols or key in out:
            raise ValueError(f"Unknown or duplicate weight symbol: {key}")
        value = float(value)
        if not np.isfinite(value):
            raise ValueError("Weights must be finite")
        out[key] = value
    if not out:
        raise ValueError("Weights cannot be empty")
    # Signed exposures and cash are preserved exactly; no normalization.
    return pd.Series(out, dtype=float).reindex(symbols, fill_value=0.0)


def feature_meta(
    ctx: dict[str, Any], access_issues: list[str] | None = None
) -> dict[str, Any]:
    return {
        "symbols": ctx["symbols"],
        "lookback_days": ctx["lookback_days"],
        "frequency": ctx["frequency"],
        "compute_mode": ctx["compute_mode"],
        "data_inventory": ctx["inventory"],
        "performance": performance_snapshot(),
        "access_issues": ctx.get("data_issues", []) + (access_issues or []),
        "warnings": ctx.get("data_issues", []) + (access_issues or []),
        "engine": "portfolio_v2",
        "as_of_date": ctx["payload"].get("as_of_date"),
    }
