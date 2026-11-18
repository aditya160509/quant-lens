"""Home page rules: what needs attention, in what order, and the live strip (H-2, H-14, H-18)."""

from __future__ import annotations

import datetime as dt
import difflib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

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


# --- prefs, saved filters, pins (H-9, H-15, H-24) ----------------------------

PREFS = {"layout": "cards", "sort": "updated", "columns": [], "density": "comfortable", "group_by": "", "card_fields": [], "pinned": []}
LAYOUTS, DENSITIES, GROUPS = {"cards", "table"}, {"comfortable", "compact"}, {"", "status", "tag", "folder"}


def prefs_get() -> dict:
    return {**PREFS, **store.kv_get("home:prefs", {})}


def prefs_put(p: dict) -> dict:
    bad = [f"{k} must be one of {sorted(v)}" for k, v in (("layout", LAYOUTS), ("density", DENSITIES), ("group_by", GROUPS)) if p.get(k, PREFS[k]) not in v]
    bad += [f"{k} must be a list of text" for k in ("columns", "card_fields", "pinned") if not all(isinstance(x, str) for x in p.get(k, []))]
    if bad or set(p) - set(PREFS):
        raise ValueError("; ".join(bad) or f"unknown fields: {sorted(set(p) - set(PREFS))}")
    out = {**PREFS, **p, "pinned": list(dict.fromkeys(p.get("pinned", [])))}
    store.kv_set("home:prefs", out)
    return out


def pin(sid: str, on: bool) -> None:
    p = prefs_get()
    prefs_put({**p, "pinned": [x for x in p["pinned"] if x != sid] + ([sid] if on else [])})


def filters_get() -> list[dict]:
    return store.kv_get("home:filters", [])


def filters_put(items: list[dict]) -> list[dict]:
    names = [f["name"].strip() for f in items]
    if not all(names) or len(set(names)) != len(names) or len(names) > 50:
        raise ValueError("Filter names must be unique, not empty, and at most 50")
    out = [{"name": n, "q": f.get("q", ""), "status": f.get("status", ""), "tag": f.get("tag", ""), "folder": f.get("folder", "")} for n, f in zip(names, items, strict=True)]
    store.kv_set("home:filters", out)
    return out


def pinned_first(cards: list[dict], pinned: list[str]) -> list[dict]:
    for c in cards:
        c["pinned"] = c["id"] in pinned
    return sorted(cards, key=lambda c: not c["pinned"])  # stable: the rest keep their order


# --- compare (H-17) ------------------------------------------------------------


def _spec_text(spec: dict) -> list[str]:
    code = spec.get("code", "")
    return [*json.dumps({k: v for k, v in spec.items() if k != "code"}, indent=1, sort_keys=True).splitlines(), "code:", *code.splitlines()]


def compare(ids: list[str], results_dir: Path) -> dict:
    """Latest backtest of 2 to 6 strategies on one date axis. Raises ValueError with the reason when it cannot."""
    ids = list(dict.fromkeys(ids))
    if not 2 <= len(ids) <= 6:
        raise ValueError(f"Compare needs 2 to 6 strategies, got {len(ids)}")
    cols, rows, specs = {}, [], {}
    for sid in ids:
        s = store.get(sid)
        run = s["last_run"]
        f = results_dir / f"{run['job_id']}.json" if run else None
        if not f or not f.exists():
            raise ValueError(f"{s['name']} has no backtest to compare; run it first")
        res = json.loads(f.read_text())
        curve = res["charts"]["equity_curve"]
        cols[sid] = pd.Series([r["strategy"] for r in curve], index=pd.to_datetime([r["date"] for r in curve]))
        m = res["meta"]["metrics"]
        rows.append({"id": sid, "name": s["name"], "total_return": res["meta"]["total_return"], **{k: m.get(k) for k in ("cagr", "sharpe", "max_drawdown", "trades")}})
        specs[sid] = s
    eq = pd.DataFrame(cols).sort_index().ffill().dropna()
    if len(eq) < 2:
        raise ValueError("These runs share no dates")
    eq = eq / eq.iloc[0]
    corr = eq.pct_change().dropna().corr().round(4)
    base = _spec_text(specs[ids[0]]["spec"])
    return {"ids": ids, "dates": [str(d.date()) for d in eq.index], "equity": {k: [round(float(x), 6) for x in eq[k]] for k in ids}, "metrics": rows,
            "correlation": {"ids": ids, "matrix": [[None if pd.isna(x) else float(x) for x in corr.loc[a, ids]] for a in ids]},
            "diffs": [{"id": k, "name": specs[k]["name"], "diff": "\n".join(difflib.unified_diff(base, _spec_text(specs[k]["spec"]), specs[ids[0]]["name"], specs[k]["name"], lineterm=""))} for k in ids[1:]]}
