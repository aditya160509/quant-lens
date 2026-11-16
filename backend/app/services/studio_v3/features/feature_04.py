"""st04 Portfolio."""

from __future__ import annotations

from typing import Any

from ..core import backtest, portfolio
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st04"
FEATURE_NAME = "Portfolio"
INPUTS = [field("strategy_ids", "Strategies", "text", None, "Strategy"), *[f for f in shared_inputs() if f["key"] not in ("strategy_id", "version", "spec")],
          field("method", "Allocation", "select", "equal", "Allocation", options=list(portfolio.METHODS)),
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
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    ids = payload.get("strategy_ids") or []
    if isinstance(ids, str):
        ids = [s for s in ids.replace(",", " ").split() if s]
    first = ids[0] if ids else None
    _, settings, _, _ = parse({**payload, "strategy_id": first} if first else {**payload, "spec": {"entry_long": "close > 0"}})
    out = portfolio.run_portfolio(portfolio.members_from(ids), settings, str(payload.get("method") or "equal"), str(payload.get("switch") or ""), payload.get("switch_off") or None, progress)
    out["meta"]["strategy"] = {"id": None, "version": None, "name": "Portfolio"}
    return backtest._clean(out)
