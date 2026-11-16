"""st05 Live: today's signals, a frozen paper record against its backtest band, reconcile with real trades, alerts and the daily digest.

Live reads every bar held (no hold-out cut): it is forward use, not research. A frozen version never changes; a new version starts a new segment (L-6).
"""

from __future__ import annotations

import hashlib
import logging
import time

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import data, limits, store
from .backtest import Refusal, prepare, simulate, trades_table
from .spec import Settings, Strategy

logger = logging.getLogger(__name__)
STALE_DAYS = 10


def freeze(sid: str, version: int, as_of: str | None, actor: str) -> dict:
    """Store spec version, data version, seed and the start date. A backdated start is labelled as such, never as a real record."""
    today = time.strftime("%Y-%m-%d")
    seg = {"version": version, "from": as_of or today, "backdated": bool(as_of and as_of < today), "data_version": data.data_version(), "at": time.time(), "actor": actor}
    segs = [s for s in store.kv_get(f"paper:{sid}", []) if s["version"] != version]
    store.kv_set(f"paper:{sid}", [*segs, seg])
    store.log(actor, "freeze_paper", sid, seg)
    return seg


def segments(sid: str | None) -> list[dict]:
    return store.kv_get(f"paper:{sid}", []) if sid else []


def channels(sid: str | None) -> list[dict]:
    return store.kv_get(f"channels:{sid}", []) if sid else []


def set_channels(sid: str, urls: list[str], quiet: str = "") -> list[dict]:
    out = [{"url": u.strip(), "quiet": quiet} for u in urls if u.strip()]
    store.kv_set(f"channels:{sid}", out)
    return out


def deliver(sid: str, title: str, body: str) -> list[dict]:
    """Send through Apprise (email, push, Telegram, webhook). Each attempt is recorded with its error; nothing raises (L-7)."""
    import apprise

    log = store.kv_get(f"deliveries:{sid}", [])
    out = []
    for ch in channels(sid):
        sender = apprise.Apprise()
        ok, err = False, None
        try:
            if not sender.add(ch["url"]):
                err = "URL not recognised by Apprise"
            else:
                ok = bool(sender.notify(title=title, body=body))
                err = None if ok else "delivery refused by the channel"
        except Exception as exc:  # a broken channel must never break the run
            logger.exception("Studio delivery failed")
            err = f"{type(exc).__name__}: {exc}"
        out.append({"channel": ch["url"].split("://")[0], "ok": ok, "error": err, "at": time.time()})
    store.kv_set(f"deliveries:{sid}", [*out, *log][:200])
    return out


def digest(name: str, as_of: str, today: list[dict], forward: dict | None) -> str:
    entries = [r for r in today if r["action"] in ("buy", "short")]
    exits = [r for r in today if r["action"] in ("sell", "cover")]
    lines = [f"{name}, signals as of {as_of}", f"Entries ({len(entries)}): " + (", ".join(f"{r['action']} {r['symbol']}" for r in entries) or "none"),
             f"Exits ({len(exits)}): " + (", ".join(r["symbol"] for r in exits) or "none")]
    if forward and forward.get("status") == "ok":
        lines.append(f"Paper since {forward['from']}: {forward['return'] * 100:+.1f}% (expected {forward['expected'] * 100:+.1f}% ± {forward['band'] * 100:.1f}%)" + (" · DRIFT" if forward["drift"] else ""))
    return "\n".join(lines)


def band(daily: np.ndarray, days: int, seed: int, n: int = 2000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bootstrap of development-period daily returns: 5th, 50th, 95th percentile of cumulative return after each day."""
    rng = np.random.default_rng(seed)
    d = daily[np.isfinite(daily)]
    paths = np.cumprod(1 + rng.choice(d, size=(n, max(days, 1))), axis=1) - 1
    return tuple(np.percentile(paths, q, axis=0) for q in (5, 50, 95))  # type: ignore[return-value]


def reconcile(model: list[dict], real: list[dict], tolerance_days: int = 2) -> dict:
    """Match real trades to the strategy's by symbol and entry date within `tolerance_days` sessions' worth of calendar days (L-5)."""
    used, matched, diffs = set(), [], []
    for r in real:
        rd = pd.Timestamp(r["date"])
        best = None
        for i, m in enumerate(model):
            if i in used or m["symbol"] != r["symbol"].upper():
                continue
            gap = abs((pd.Timestamp(m["entry_date"]) - rd).days)
            if gap <= tolerance_days and (best is None or gap < best[1]):
                best = (i, gap)
        if best:
            used.add(best[0])
            m = model[best[0]]
            matched.append({"symbol": m["symbol"], "model_date": m["entry_date"], "real_date": r["date"], "model_price": m["entry"], "real_price": r.get("price")})
            if r.get("price"):
                diffs.append((float(r["price"]) / m["entry"] - 1) * (1 if m["side"] == "long" else -1))
    skipped = [m for i, m in enumerate(model) if i not in used]
    extra = [r for r in real if not any(x["real_date"] == r["date"] and x["symbol"] == r["symbol"].upper() for x in matched)]
    return {"matched": len(matched), "model": len(model), "real": len(real), "same_share": len(matched) / len(model) if model else None,
            "avg_fill_bps": float(np.mean(diffs) * 1e4) if diffs else None, "skipped": len(skipped), "extra": len(extra), "rows": matched,
            "skipped_rows": skipped[:50], "extra_rows": extra[:50]}


def run_live(spec: Strategy, settings: Settings, sid: str | None, version: int | None, real_trades: list[dict] | None = None, send: bool = False, progress=None) -> dict:
    stage = progress or (lambda *_: None)
    if not C.compile_spec(spec)["ok"]:
        raise Refusal("The strategy does not compile.", ["fix the rule in Build"])
    fresh = limits.freshness()
    stage("load", 10)
    prep = prepare(settings, include_holdout=True)
    p, dates = prep.panel, prep.panel.dates
    sig = C.signals(spec, prep.sig_bars, dates)
    stage("signals", 40)
    t = len(dates) - 1
    as_of = str(dates[t].date())
    held = np.isfinite(p.close[t])
    price = p.close[t]
    per = settings.capital / max(spec.sizing.max_positions or 1, 1)
    today = []
    for j in np.flatnonzero(held & (sig.entries[t] != 0)):
        side = "buy" if sig.entries[t, j] > 0 else "short"
        today.append({"symbol": p.symbols[j], "action": side, "close": float(price[j]), "shares": int(per // price[j]) if price[j] > 0 else 0,
                      "score": float(sig.score[t, j]) if sig.score is not None and np.isfinite(sig.score[t, j]) else None})
    for j in np.flatnonzero(held & (sig.exits[t] != 0)):
        today.append({"symbol": p.symbols[j], "action": "sell" if sig.exits[t, j] & 1 else "cover", "close": float(price[j]), "shares": None, "score": None})
    recent = sig.entries[max(0, t - 5):t]
    near = [{"symbol": p.symbols[j], "last_fired": str(dates[max(0, t - 5) + int(np.flatnonzero(recent[:, j])[-1])].date())}
            for j in np.flatnonzero((recent != 0).any(axis=0) & held) if sig.entries[t, j] == 0][:200]
    orders = "\n".join(f"{r['action'].upper()} {r['shares']} {r['symbol']} at next open" if r["shares"] else f"{r['action'].upper()} {r['symbol']} at next open" for r in today)

    stage("paper", 60)
    r = simulate(spec, prep, settings, sig=sig, magnifier=False)
    seg = next((s for s in reversed(segments(sid)) if s["version"] == version), None)
    forward, curve, fills = None, [], []
    if seg:
        lo = int(dates.searchsorted(pd.Timestamp(seg["from"])))
        dev_eq = simulate(spec, prepare(settings), settings, magnifier=False).equity
        dev_daily = np.diff(dev_eq) / dev_eq[:-1]
        if lo >= len(dates) - 1:
            forward = {"status": "waiting", "from": seg["from"], "backdated": seg["backdated"], "reason": f"no bar after {seg['from']} yet; data ends {as_of}"}
        else:
            eq = r.equity[lo:] / r.equity[lo]
            p5, p50, p95 = band(dev_daily, len(eq) - 1, settings.seed)
            curve = [{"date": str(dates[lo + i].date()), "paper": float(eq[i]), "p5": float(1 + (p5[i - 1] if i else 0)), "p50": float(1 + (p50[i - 1] if i else 0)),
                      "p95": float(1 + (p95[i - 1] if i else 0))} for i in range(len(eq))]
            out_of = [c["date"] for c in curve[1:] if not c["p5"] <= c["paper"] <= c["p95"]]
            fills = [x for x in trades_table(r, p) if x["entry_date"] >= seg["from"]]
            live_daily = np.diff(eq) / eq[:-1]
            sr_bt = M.sharpe(dev_daily) or 0.0
            forward = {"status": "ok", "from": seg["from"], "backdated": seg["backdated"], "days": len(eq) - 1, "return": float(eq[-1] - 1), "expected": float(p50[-1]),
                       "band": float((p95[-1] - p5[-1]) / 2), "drift": bool(out_of), "drift_from": out_of[0] if out_of else None,
                       "live_sharpe": M.sharpe(live_daily) if len(live_daily) > 2 else None, "backtest_sharpe": sr_bt,
                       "drawdown_odds": _drawdown_odds(dev_daily, float(M.max_drawdown(eq)), len(eq), settings.seed)}
    rec = reconcile([x for x in trades_table(r, p)], real_trades) if real_trades else None

    deliveries = []
    if send and sid:
        deliveries = deliver(sid, f"{spec.name}: {as_of}", digest(spec.name, as_of, today, forward))
    stale = fresh["tone"] == "red"
    head = f"{sum(x['action'] in ('buy', 'short') for x in today)} entries, {sum(x['action'] in ('sell', 'cover') for x in today)} exits as of {as_of}" + (f" (data {fresh['age_days']} days old)" if stale else "")
    return {
        "feature_id": "st05", "status": "ok",
        "summary_cards": [{"label": "Entries", "value": sum(x["action"] in ("buy", "short") for x in today)}, {"label": "Exits", "value": sum(x["action"] in ("sell", "cover") for x in today)},
                          {"label": "Near triggers", "value": len(near)}, {"label": "Paper return", "value": forward.get("return") if forward and forward["status"] == "ok" else None, "unit": "%"}],
        "charts": {"forward": curve},
        "tables": {"signals": today, "near": near, "fills": fills, "reconcile": (rec or {}).get("rows", []), "deliveries": store.kv_get(f"deliveries:{sid}", [])[:30] if sid else [],
                   "segments": segments(sid)},
        "meta": {"headline": head, "as_of": as_of, "stale": stale, "stale_days": fresh["age_days"], "orders": orders, "forward": forward, "reconcile": {k: v for k, v in (rec or {}).items() if not k.endswith("rows")},
                 "channels": [c["url"].split("://")[0] for c in channels(sid)], "sent": deliveries, "total_return": forward["return"] if forward and forward["status"] == "ok" else 0.0,
                 "metrics": {"sharpe": None, "trades": len(fills)}, "freshness": fresh, "verdict_chip": "not validated",
                 "run_hash": hashlib.sha256(f"st05:{spec.hash()}:{settings.hash()}:{as_of}".encode()).hexdigest()[:16],
                 "result_hash": hashlib.sha256(repr(today).encode()).hexdigest()[:16], "period": [str(dates[0].date()), as_of]},
    }


def _drawdown_odds(daily: np.ndarray, depth: float, days: int, seed: int) -> dict:
    """How often a drawdown this deep shows up in `days` sessions if the backtest's returns are right, and if its mean is half as large."""
    rng = np.random.default_rng(seed)
    d = daily[np.isfinite(daily)]
    out = {}
    for label, shift in (("at_backtest", 0.0), ("at_half", d.mean() / 2)):
        paths = np.cumprod(1 + rng.choice(d - shift, size=(1000, max(days, 2))), axis=1)
        dd = (paths / np.maximum.accumulate(paths, axis=1) - 1).min(axis=1)
        out[label] = float((dd <= depth).mean())
    return out

