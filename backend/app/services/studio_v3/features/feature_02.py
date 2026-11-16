"""st02 Optimise."""

from __future__ import annotations

from typing import Any

from ..core import backtest, optimise
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st02"
FEATURE_NAME = "Optimise"
INPUTS = [*shared_inputs(),
          field("method", "Search", "select", "grid", "Search", options=["grid", "random", "optuna"]),
          field("objective", "Objective", "select", "sharpe", "Search", options=list(optimise.OBJECTIVES)),
          field("max_cells", "Cells", "number", 200, "Search", min=4, max=2000),
          field("budget_s", "Time budget (s)", "number", 0, "Search", min=0, max=3600),
          field("custom", "Custom objective", "text", "", "Objective"),
          field("link", "Link parameters", "text", "", "Parameters"),
          field("min_trades", "Min trades", "number", 0, "Constraints", min=0),
          field("max_dd", "Max drawdown", "number", 0, "Constraints", min=0, max=1),
          field("radius", "Neighbourhood (steps)", "number", 1, "Neighbourhood", min=1, max=5)]
OUTPUTS = [
    {"key": "heatmap", "source": "charts", "render": "table", "label": "Map", "primary": True},
    {"key": "top_sets", "source": "tables", "render": "table", "label": "Top sets"},
    {"key": "importance", "source": "tables", "render": "table", "label": "What matters"},
    {"key": "pareto", "source": "tables", "render": "table", "label": "Trade-offs"},
    {"key": "cells", "source": "tables", "render": "table", "label": "All cells"},
    {"key": "spread", "source": "charts", "render": "lineChart", "label": "Spread"},
    {"key": "stability", "source": "tables", "render": "table", "label": "Stability"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    spec, settings, sid, version = parse(payload)
    out = optimise.run_optimise(spec, settings, str(payload.get("method") or "grid"), str(payload.get("objective") or "sharpe"), int(payload.get("max_cells") or 200),
                                progress, getattr(progress, "cancelled", lambda: False), custom=str(payload.get("custom") or ""), link=str(payload.get("link") or ""),
                                min_trades=int(payload.get("min_trades") or 0), max_dd=float(payload.get("max_dd") or 0) or None, radius=int(payload.get("radius") or 1),
                                budget_s=float(payload.get("budget_s") or 0))
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    trials = out.pop("_trials")
    out = backtest._clean(out)
    out["_trials"] = trials
    return out
