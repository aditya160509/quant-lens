"""st01 Backtest."""

from __future__ import annotations

from typing import Any

from ..core import backtest
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st01"
FEATURE_NAME = "Backtest"
INPUTS = [*shared_inputs(),
          field("rule_target", "Profit target", "number", 0.10, "Rule check", min=0.01, max=10),
          field("rule_daily_loss", "Max daily loss", "number", 0.05, "Rule check", min=0.001, max=1),
          field("rule_max_dd", "Max drawdown", "number", 0.10, "Rule check", min=0.01, max=1),
          field("rule_min_days", "Min trading days", "number", 5, "Rule check", min=0)]
OUTPUTS = [
    {"key": "equity_curve", "source": "charts", "render": "lineChart", "label": "Equity and drawdown", "primary": True},
    {"key": "cost_ladder", "source": "charts", "render": "table", "label": "Cost ladder"},
    {"key": "start_dates", "source": "charts", "render": "table", "label": "Start dates"},
    {"key": "exposure", "source": "charts", "render": "lineChart", "label": "Exposure"},
    {"key": "rolling", "source": "charts", "render": "lineChart", "label": "Stability"},
    {"key": "trades", "source": "tables", "render": "table", "label": "Trades"},
    {"key": "carried_by", "source": "tables", "render": "table", "label": "Carried by"},
    {"key": "crises", "source": "tables", "render": "table", "label": "Crisis periods"},
    {"key": "drawdowns", "source": "tables", "render": "table", "label": "Drawdowns"},
    {"key": "per_name", "source": "tables", "render": "table", "label": "Per-name results"},
    {"key": "my_limits", "source": "tables", "render": "table", "label": "My limits"},
    {"key": "limits", "source": "tables", "render": "table", "label": "Limits"},
    {"key": "statistics", "source": "tables", "render": "table", "label": "Statistics"},
    {"key": "conditions", "source": "tables", "render": "table", "label": "Conditions"},
    {"key": "rule_check", "source": "tables", "render": "table", "label": "Rule check"},
    {"key": "holdings", "source": "tables", "render": "table", "label": "Names held"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    spec, settings, sid, version = parse(payload or {})
    out = backtest.run_backtest(spec, settings, progress)
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    return out
