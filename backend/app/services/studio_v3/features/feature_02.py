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
          field("max_cells", "Cells", "number", 200, "Search", min=4, max=2000)]
OUTPUTS = [
    {"key": "heatmap", "source": "charts", "render": "table", "label": "Map", "primary": True},
    {"key": "top_sets", "source": "tables", "render": "table", "label": "Top sets"},
    {"key": "importance", "source": "tables", "render": "table", "label": "What matters"},
    {"key": "pareto", "source": "tables", "render": "table", "label": "Trade-offs"},
    {"key": "cells", "source": "tables", "render": "table", "label": "All cells"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    spec, settings, sid, version = parse(payload)
    out = optimise.run_optimise(spec, settings, str(payload.get("method") or "grid"), str(payload.get("objective") or "sharpe"), int(payload.get("max_cells") or 200),
                                progress, getattr(progress, "cancelled", lambda: False))
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    trials = out.pop("_trials")
    out = backtest._clean(out)
    out["_trials"] = trials
    return out
