"""Home page rules: what needs attention, in what order, and the live strip (H-2, H-14, H-18)."""

from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np

from . import store

RANK = {"drift": 1, "data_newer": 2, "validation_expired": 3, "failed_run": 4, "alert": 5, "paper_stale": 6, "draft": 7, "data": 8}
PAPER_STALE_DAYS = 3


def _day(ts: float) -> dt.date:
    return dt.datetime.fromtimestamp(ts).date()


def trading_days_since(ts: float, today: dt.date | None = None) -> int:
    """Weekdays between a timestamp and today (market holidays are not modelled)."""
    return int(np.busday_count(_day(ts), today or dt.date.today()))


def _last_live(sid: str) -> dict | None:
    with store.db() as con:
        r = con.execute("SELECT created, summary FROM runs WHERE strategy_id = ? AND feature = 'st05' ORDER BY created DESC LIMIT 1", (sid,)).fetchone()
    return {"at": r["created"], **json.loads(r["summary"])} if r else None


def attention(cards: list[dict], failed: dict[str, float], fresh: dict, today: dt.date | None = None, now: float | None = None) -> list[dict]:
    """`failed` maps strategy id to the time of its latest failed run. Result is sorted by rank, then by name."""
    now = now or time.time()
    out = []

    def add(kind, c, text, tone="amber"):
        out.append({"kind": kind, "rank": RANK[kind], "tone": tone, "strategy_id": c["id"] if c else None, "text": text,
                    "action": {"label": "Open", "href": f"/studio/{'live' if kind in ('drift', 'paper_stale', 'alert') else 'build'}/{c['id']}"} if c else {"label": "Open data", "href": "/studio/library/data"}})

    if fresh["tone"] != "ok":
        add("data", None, fresh["label"], fresh["tone"])
    for c in cards:
        paper = store.kv_get(f"paper:{c['id']}", [])
        live = _last_live(c["id"]) if paper else None
        if live and live.get("drift"):
            add("drift", c, f"{c['name']}: paper return is outside its backtest band", "red")
        run = c["last_run"]
        if run and fresh["date"] > str(_day(run["at"])):
            add("data_newer", c, f"{c['name']}: data to {fresh['date']} is newer than its last run")
        if c["validation_expired"]:
            add("validation_expired", c, f"{c['name']}: validation is for an older version")
        if failed.get(c["id"], 0) > (run["at"] if run else 0):
            add("failed_run", c, f"{c['name']}: last run failed", "red")
        if any(d["at"] > now - 86400 for d in store.kv_get(f"deliveries:{c['id']}", [])):
            add("alert", c, f"{c['name']}: alert fired")
        if paper:
            since = (live or {}).get("at") or max(s["at"] for s in paper)
            if trading_days_since(since, today) > PAPER_STALE_DAYS:
                add("paper_stale", c, f"{c['name']}: paper not stepped for {trading_days_since(since, today)} trading days")
        if c["has_draft"]:
            add("draft", c, f"{c['name']}: unsaved draft")
    return sorted(out, key=lambda a: (a["rank"], a["text"]))


def live_block(cards: list[dict]) -> dict:
    rows, beats, alerts = [], [], 0
    for c in cards:
        if c["status"] != "Paper":
            continue
        last = _last_live(c["id"])
        rows.append({"id": c["id"], "name": c["name"], "status": c["status"], "paper_return": (last or {}).get("total_return"), "today_pnl": (last or {}).get("paper_day"), "last_step": (last or {}).get("at")})
        beats += [last["at"]] if last else []
        alerts += sum(d["at"] > time.time() - 86400 for d in store.kv_get(f"deliveries:{c['id']}", []))
    return {"strategies": rows, "alerts": alerts, "heartbeat": max(beats) if beats else None}
