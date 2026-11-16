"""st04 Portfolio."""

from __future__ import annotations

from typing import Any

from ..core import backtest, portfolio
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st04"
FEATURE_NAME = "Portfolio"
INPUTS = [field("strategy_ids", "Strategies", "text", None, "Strategy"), *[f for f in shared_inputs() if f["key"] not in ("strategy_id", "version", "spec")],
          field("method", "Allocation", "select", "equal", "Allocation", options=[*portfolio.METHODS, "fixed"]),
          field("rebalance", "Weights", "select", "in_sample", "Allocation", options=["in_sample", "quarterly"]),
          field("fixed", "Fixed weights (name=weight, …)", "text", "", "Allocation"),
          field("rotate_top", "Rotate: hold the top N by 3-month return (0 = off)", "number", 0, "Allocation"),
          field("switch", "Switch rule (on the benchmark)", "text", "", "Allocation"),
          field("switch_off", "Hold when the rule is false", "text", "", "Allocation")]
OUTPUTS = [
    {"key": "combined", "source": "charts", "render": "lineChart", "label": "Combined vs each", "primary": True},
    {"key": "correlation", "source": "tables", "render": "table", "label": "Correlation"},
    {"key": "weights", "source": "tables", "render": "table", "label": "Weights"},
    {"key": "methods", "source": "tables", "render": "table", "label": "Allocation methods"},
    {"key": "members", "source": "tables", "render": "table", "label": "Members"},
    {"key": "marginal", "source": "tables", "render": "table", "label": "Marginal contribution"},
    {"key": "overlap", "source": "tables", "render": "table", "label": "Overlap"},
    {"key": "weights_over_time", "source": "tables", "render": "table", "label": "Weights over time"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    ids = payload.get("strategy_ids") or []
    if isinstance(ids, str):
        ids = [s for s in ids.replace(",", " ").split() if s]
    first = ids[0] if ids else None
    _, settings, _, _ = parse({**payload, "strategy_id": first} if first else {**payload, "spec": {"entry_long": "close > 0"}})
    fixed = payload.get("fixed") or {}
    if isinstance(fixed, str):
        fixed = {k.strip(): float(v) for k, v in (x.split("=", 1) for x in fixed.split(",") if "=" in x)}
    out = portfolio.run_portfolio(portfolio.members_from(ids), settings, str(payload.get("method") or "equal"), str(payload.get("switch") or ""), payload.get("switch_off") or None, progress,
                                  str(payload.get("rebalance") or "in_sample"), fixed, int(payload.get("rotate_top") or 0))
    out["meta"]["strategy"] = {"id": None, "version": None, "name": "Portfolio"}
    return backtest._clean(out)
