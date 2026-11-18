"""st04 Portfolio."""

from __future__ import annotations

import json
from typing import Any

from ..core import backtest, portfolio
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st04"
FEATURE_NAME = "Portfolio"
INPUTS = [field("strategy_ids", "Strategies", "text", None, "Strategy"), *[f for f in shared_inputs() if f["key"] not in ("strategy_id", "version", "spec")],
          field("method", "Allocation", "select", "equal", "Allocation", options=[*portfolio.METHODS, "fixed"]),
          field("rebalance", "Weights", "select", "in_sample", "Allocation", options=["in_sample", "quarterly", "threshold"]),
          field("corridor", "Rebalance when a weight drifts by (pts)", "number", 5, "Allocation"),
          field("min_trade", "Skip trades smaller than (pts)", "number", 1, "Allocation"),
          field("fixed", "Fixed weights (name=weight, …)", "text", "", "Allocation"),
          field("rotate_top", "Rotate: hold the top N by 3-month return (0 = off)", "number", 0, "Allocation"),
          field("max_weight", "Max weight per member (0 = none)", "number", 0, "Allocation"),
          field("max_correlation", "Drop later member above correlation (0 = off)", "number", 0, "Allocation"),
          field("cash_reserve", "Cash reserve (0-0.9)", "number", 0, "Allocation"),
          field("min_members", "Minimum members (0 = off)", "number", 0, "Allocation"),
          field("max_symbol", "Max exposure per symbol, share of capital (0 = off)", "number", 0, "Constraints"),
          field("max_sector", "Max net exposure per sector (0 = off)", "number", 0, "Constraints"),
          field("max_gross", "Max gross exposure (0 = off)", "number", 0, "Constraints"),
          field("max_net", "Max net exposure (0 = off)", "number", 0, "Constraints"),
          field("leverage_cap", "Leverage cap on gross exposure (0 = off)", "number", 0, "Constraints"),
          field("ban", "Ban list (symbols, comma separated)", "text", "", "Constraints"),
          field("net_execution", "Charge cost on netted trades per symbol", "boolean", False, "Constraints"),
          field("book_ids", "Saved books as members (ids, space separated)", "text", "", "Strategy"),
          field("regime_rule", "Regime rule (on the benchmark)", "text", "", "Allocation"),
          field("regime_on", "Allocation when the rule is true", "select", "", "Allocation", options=["", *portfolio.METHODS]),
          field("regime_off", "Allocation when false", "select", "", "Allocation", options=["", *portfolio.METHODS]),
          field("sleeves", 'Sleeves {id: {enabled, start, vol_target}}', "text", "", "Allocation"),
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
    {"key": "risk_share", "source": "tables", "render": "table", "label": "Risk share"},
    {"key": "crises", "source": "tables", "render": "table", "label": "Crisis stress"},
    {"key": "dropout", "source": "tables", "render": "table", "label": "Drop one member"},
    {"key": "drawdown_overlap", "source": "tables", "render": "table", "label": "Drawdown overlap"},
    {"key": "rolling_correlation", "source": "tables", "render": "lineChart", "label": "Rolling correlation"},
    {"key": "capacity", "source": "tables", "render": "table", "label": "Capacity by sleeve"},
    {"key": "exposure", "source": "tables", "render": "table", "label": "Sector exposure"},
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
    sleeves = payload.get("sleeves") or {}
    if isinstance(sleeves, str):
        try:
            sleeves = json.loads(sleeves) if sleeves.strip() else {}
        except ValueError:
            raise backtest.Refusal("Sleeves must be JSON.", ['{"id": {"enabled": false}}']) from None
    net = payload.get("net_execution", False)
    if isinstance(net, str):
        net = {"true": True, "on": True, "1": True, "false": False, "off": False, "0": False, "": False}.get(net.strip().lower())
    if not isinstance(net, bool):
        raise backtest.Refusal("net_execution must be on or off.", ["true or false"])
    books = payload.get("book_ids") or []
    books = books.replace(",", " ").split() if isinstance(books, str) else books
    opts = {"net_execution": net, "book_ids": books, "corridor": float(payload.get("corridor") or 5) / 100, "min_trade": float(payload.get("min_trade") if payload.get("min_trade") is not None else 1) / 100, "sleeves": sleeves,
            "ban": [x for x in str(payload.get("ban") or "").replace(",", " ").split() if x],
            **{k: float(payload.get(k) or 0) for k in ("max_symbol", "max_sector", "max_gross", "max_net", "leverage_cap")},
            **{k: payload.get(k) for k in ("max_correlation", "cash_reserve", "min_members", "regime_rule", "regime_on", "regime_off")}}
    out = portfolio.run_portfolio(portfolio.members_from(ids), settings, str(payload.get("method") or "equal"), str(payload.get("switch") or ""), payload.get("switch_off") or None, progress,
                                  str(payload.get("rebalance") or "in_sample"), fixed, int(payload.get("rotate_top") or 0),
                                  float(payload.get("max_weight") or 0) or None, opts)
    out["meta"]["strategy"] = {"id": None, "version": None, "name": "Portfolio"}
    return backtest._clean(out)
