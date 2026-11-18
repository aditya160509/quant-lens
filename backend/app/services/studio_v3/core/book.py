"""Portfolio deployed as one paper book (P-20): members frozen at fixed weights, today's orders netted by symbol, paper P&L attributed per member.

A book never changes once frozen; a new weight set is a new book. Like Live, it reads every bar held (forward use) and refuses nothing for stale data, but says so.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import limits, store
from .backtest import Refusal, prepare, simulate
from .spec import Settings, Strategy


def freeze(members: list[dict], name: str, as_of: str | None, actor: str) -> dict:
    """members: [{strategy_id, version, weight}]; weights are normalised to sum to 1."""
    if len(members) < 2:
        raise Refusal("A book needs two or more strategies.", ["pick strategies in Portfolio"])
    total = sum(max(float(m["weight"]), 0.0) for m in members)
    if total <= 0:
        raise Refusal("Weights sum to zero.", ["run Portfolio first"])
    today = time.strftime("%Y-%m-%d")
    rows = [{"strategy_id": m["strategy_id"], "version": int(m["version"]), "weight": max(float(m["weight"]), 0.0) / total} for m in members]
    bid = hashlib.sha256(repr(rows).encode()).hexdigest()[:12]
    book = {"id": bid, "name": name or "Portfolio book", "members": rows, "from": as_of or today, "backdated": bool(as_of and as_of < today), "at": time.time(), "actor": actor}
    store.kv_set(f"book:{bid}", book)
    store.kv_set("books", sorted({*store.kv_get("books", []), bid}))
    store.log(actor, "freeze_book", None, book)
    return book


def books() -> list[dict]:
    return [b for b in (store.kv_get(f"book:{i}") for i in store.kv_get("books", [])) if b]


def daily_returns(bid: str, prep, settings: Settings, mask=None, seen: tuple = ()) -> tuple[str, np.ndarray]:
    """A frozen book as one member: its weighted daily return series over the whole backtest period (no paper start). A book that contains itself, directly or through another book, is refused."""
    b = store.kv_get(f"book:{bid}")
    if not b:
        raise Refusal(f"No such book: {bid}.", ["deploy one from Portfolio"])
    if bid in seen:
        raise Refusal(f"Book {bid} contains itself.", [" > ".join([*seen, bid])])
    out = np.zeros(len(prep.panel.dates))
    for m in b["members"]:
        if m.get("book_id"):
            r = daily_returns(m["book_id"], prep, settings, mask, (*seen, bid))[1]
        else:
            eq = simulate(Strategy(**store.get(m["strategy_id"], m["version"])["spec"]), prep, settings, mask=mask).equity
            r = np.r_[0.0, np.diff(eq) / eq[:-1]]
        out += m["weight"] * r
    return f"{b['name']} ({bid})", out


def net_orders(per_member: list[tuple[str, float, list[dict]]]) -> tuple[list[dict], float]:
    """Sum signed shares by symbol across members (weight-scaled). Returns the netted orders and the share of gross shares netting removed."""
    gross, net = 0.0, {}
    for _, w, orders in per_member:
        for o in orders:
            sign = 1 if o["action"] in ("buy", "cover") else -1
            q = (o.get("shares") or 0) * w
            gross += abs(q)
            net[o["symbol"]] = net.get(o["symbol"], 0.0) + sign * q
    rows = [{"symbol": s, "action": "buy" if q > 0 else "sell", "shares": round(abs(q))} for s, q in sorted(net.items()) if round(abs(q)) > 0]
    saved = 1 - sum(r["shares"] for r in rows) / gross if gross > 0 else 0.0
    return rows, float(saved)


def run(book_id: str, settings: Settings) -> dict:
    b = store.kv_get(f"book:{book_id}")
    if not b:
        raise Refusal("No such book.", ["deploy from Portfolio"])
    prep = prepare(settings, include_holdout=True)
    p, dates = prep.panel, prep.panel.dates
    t = len(dates) - 1
    lo = int(dates.searchsorted(pd.Timestamp(b["from"])))
    per_member, attribution, combined = [], [], None
    for m in b["members"]:
        s = store.get(m["strategy_id"], m["version"])
        spec = Strategy(**s["spec"])
        if not C.compile_spec(spec)["ok"]:
            raise Refusal(f"{spec.name} v{m['version']} does not compile.", ["fix it in Build"])
        sig = C.signals(spec, prep.sig_bars, dates)
        cap = settings.capital * m["weight"]
        per = cap / max(spec.sizing.max_positions or 1, 1)
        orders = []
        for j in np.flatnonzero(np.isfinite(p.close[t]) & (sig.entries[t] != 0)):
            orders.append({"symbol": p.symbols[j], "action": "buy" if sig.entries[t, j] > 0 else "short", "shares": int(per // p.close[t, j]) if p.close[t, j] > 0 else 0})
        per_member.append((f"{spec.name} v{m['version']}", 1.0, orders))
        eq = simulate(spec, prep, settings).equity
        if lo < t:
            r = eq[lo:] / eq[lo] - 1
            attribution.append({"strategy": f"{spec.name} v{m['version']}", "weight": m["weight"], "return": float(r[-1]), "contribution": float(m["weight"] * r[-1])})
            daily = np.diff(eq[lo:]) / eq[lo:-1]
            combined = m["weight"] * daily if combined is None else combined + m["weight"] * daily
    orders, saved = net_orders(per_member)
    fresh = limits.freshness()
    curve = [] if combined is None else [{"date": str(dates[lo + 1 + i].date()), "paper": float(v)} for i, v in enumerate(np.cumprod(1 + combined))]
    return {"book": b, "as_of": str(dates[t].date()), "stale": fresh["tone"] == "red", "freshness": fresh,
            "orders": orders, "netting_saves": saved, "by_member": [{"strategy": n, "orders": len(o)} for n, _, o in per_member],
            "attribution": attribution, "paper": curve, "paper_return": float(np.prod(1 + combined) - 1) if combined is not None else None,
            "paper_sharpe": M.sharpe(combined) if combined is not None and len(combined) > 2 else None,
            "status": "waiting" if lo >= t else "ok", "reason": f"no bar after {b['from']} yet; data ends {dates[t].date()}" if lo >= t else None}
