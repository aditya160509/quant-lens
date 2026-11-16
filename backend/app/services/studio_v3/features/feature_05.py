"""st05 Live."""

from __future__ import annotations

from typing import Any

from ..core import backtest, live
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st05"
FEATURE_NAME = "Live"
INPUTS = [*[f for f in shared_inputs() if f["key"] not in ("holdout", "start", "end")],
          field("real_trades", "Real trades (CSV: date,symbol,side,price)", "text", "", "Reconcile"),
          field("send", "Send the digest now", "boolean", False, "Alerts")]
OUTPUTS = [
    {"key": "signals", "source": "tables", "render": "table", "label": "Signals", "primary": True},
    {"key": "near", "source": "tables", "render": "table", "label": "Near triggers"},
    {"key": "forward", "source": "charts", "render": "lineChart", "label": "Forward"},
    {"key": "fills", "source": "tables", "render": "table", "label": "Fills"},
    {"key": "reconcile", "source": "tables", "render": "table", "label": "Reconcile"},
    {"key": "deliveries", "source": "tables", "render": "table", "label": "Alerts"},
    {"key": "segments", "source": "tables", "render": "table", "label": "Paper segments"},
]


def parse_trades(text: str) -> list[dict]:
    rows = []
    for line in (text or "").strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 2 or parts[0].lower() == "date":
            continue
        rows.append({"date": parts[0], "symbol": parts[1].upper(), "side": parts[2].lower() if len(parts) > 2 else "buy", "price": float(parts[3]) if len(parts) > 3 and parts[3] else None})
    return rows


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    spec, settings, sid, version = parse(payload)
    out = live.run_live(spec, settings, sid, version, parse_trades(str(payload.get("real_trades") or "")), bool(payload.get("send")), progress)
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    return backtest._clean(out)
