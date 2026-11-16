"""Shared run inputs (PAGES §0.1) as manifest fields, and the flat payload -> (Strategy, Settings) mapping."""

from __future__ import annotations

from typing import Any

from ..core import store
from ..core.spec import Costs, Settings, Strategy


def field(key: str, label: str, type: str, default: Any, group: str, **extra) -> dict:
    return {"key": key, "label": label, "type": type, "default": default, "group": group, **extra}


COST_PROFILES = {
    "US retail": {"commission_bps": 1.0, "slippage_bps": 2.0, "borrow_bps": 50.0},
    "Crypto taker": {"commission_bps": 10.0, "slippage_bps": 5.0, "borrow_bps": 0.0},
    "Zero (costs off)": {"commission_bps": 0.0, "slippage_bps": 0.0, "borrow_bps": 0.0},
    "Custom": {},
}


def shared_inputs() -> list[dict]:
    return [
        field("strategy_id", "Strategy", "text", None, "Strategy"),
        field("version", "Version", "number", None, "Strategy", min=1),
        field("spec", "Draft", "json", None, "Strategy"),
        field("symbols", "Symbols", "ticker_list", None, "Universe"),
        field("top_n", "Top names by liquidity", "number", 100, "Universe", min=1, max=5000),
        field("start", "From", "date", None, "Period"),
        field("end", "To", "date", None, "Period"),
        field("holdout", "Hold-out share", "number", 0.2, "Period", min=0, max=0.5),
        field("fill", "Fill", "select", "next_open", "Fill", options=["next_open", "same_close"]),
        field("magnifier", "Bar magnifier", "boolean", True, "Fill"),
        field("cost_profile", "Cost profile", "select", "US retail", "Costs", options=list(COST_PROFILES)),
        field("commission_bps", "Commission", "number", 1.0, "Costs", min=0, max=500, unit="bp"),
        field("slippage_bps", "Slippage", "number", 2.0, "Costs", min=0, max=500, unit="bp"),
        field("borrow_bps", "Borrow", "number", 50.0, "Costs", min=0, max=5000, unit="bp a year"),
        field("volume_cap", "Volume cap", "number", 0.0, "Costs", min=0, max=1),
        field("delist_haircut", "Delisting haircut", "number", 0.0, "Delisting", min=0, max=1),
        field("capital", "Starting capital", "number", 100000, "Capital", min=1),
        field("leverage", "Leverage cap", "number", 1.0, "Capital", min=0.1, max=10),
        field("benchmark", "Benchmark", "ticker", "SPY", "Benchmark"),
    ]


def parse(payload: dict[str, Any]) -> tuple[Strategy, Settings, str | None, int | None]:
    """(spec, settings, strategy id, version). A posted `spec` (the open draft) wins over the saved version."""
    payload = {k: v for k, v in (payload or {}).items() if v is not None and v != ""}
    sid, version = payload.get("strategy_id"), payload.get("version")
    if payload.get("spec"):
        spec = Strategy(**payload["spec"])
    elif sid:
        saved = store.get(str(sid), int(version) if version else None)
        spec, version = Strategy(**saved["spec"]), saved["version"]
    else:
        raise ValueError("Pick a strategy")
    profile = COST_PROFILES.get(str(payload.get("cost_profile") or "Custom"), {})
    cost_keys = ("commission_bps", "slippage_bps", "borrow_bps", "volume_cap", "commission_share", "commission_min", "slippage_range")
    costs = Costs(profile=str(payload.get("cost_profile") or "Custom"), **{**{k: payload[k] for k in cost_keys if k in payload}, **profile})
    symbols = payload.get("symbols") or []
    if isinstance(symbols, str):
        symbols = [s for s in symbols.replace(",", " ").split() if s]
    keys = ("top_n", "start", "end", "holdout", "fill", "magnifier", "delist_haircut", "capital", "leverage", "benchmark", "seed",
            "rule_target", "rule_daily_loss", "rule_max_dd", "rule_min_days")
    return spec, Settings(symbols=list(symbols), costs=costs, **{k: payload[k] for k in keys if k in payload}), sid, int(version) if version else None
