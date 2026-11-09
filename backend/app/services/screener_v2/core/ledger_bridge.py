"""Every distinct backtest configuration run in the Screener is one trial on the Research store's ledger."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from app.services.research_v2.store import get_store

PROJECT = "screener"


def record_trial(feature_id: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
    """Store a finished backtest; the same configuration reruns replace, never add."""
    if feature_id != "05":
        return
    curve = (result.get("charts") or {}).get("equity_curve") or []
    equity = np.array([r["strategy"] for r in curve if r.get("strategy") is not None], dtype=float)
    if len(equity) < 3:
        return
    key = {k: v for k, v in payload.items() if k not in ("screen_id", "as_of_date")}
    trial_id = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]
    store = get_store()
    if not store.get_project(PROJECT):
        store._run("INSERT INTO projects(id,name,description,created_at) VALUES(?,?,?,datetime('now'))", (PROJECT, "Screener backtests", "Every backtest configuration run in the Screener"))
    cards = [c for c in result.get("summary_cards") or [] if c.get("label") == "Sharpe"]
    store.save_job(trial_id, "sc05", key, "completed", 1.0, {"summary_cards": cards, "meta": {"return_series": (equity[1:] / equity[:-1] - 1).tolist()}}, project_id=PROJECT)


def ledger() -> dict[str, Any]:
    store = get_store()
    return store.ledger(PROJECT) if store.get_project(PROJECT) else {"trials": 0, "distinct_signals": 0, "deflated_sharpe_hurdle": None, "entries": []}
