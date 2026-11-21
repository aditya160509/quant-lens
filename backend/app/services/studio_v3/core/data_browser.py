"""Read-only data audit: per-symbol coverage and quality checks over the raw market file."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
import polars as pl

from app.services.screener_v2.core import data_loader, performance

JUMP, STALE_RUN, GAP_DAYS, BUCKETS, MAX_ISSUES = 0.4, 5, 4, 40, 200


def audit(dates, close, issues: bool = False) -> dict:
    """Checks one symbol's bars (raw, unsorted ok). Gaps are runs of more than GAP_DAYS missing business days."""
    d = pd.DatetimeIndex(dates).values.astype("datetime64[D]")
    order = np.argsort(d, kind="stable")
    d, c = d[order], np.asarray(close, float)[order]
    found: list[dict] = []

    def add(kind, i, detail):
        found.append({"kind": kind, "date": str(d[i]), "detail": detail})

    dup = np.flatnonzero(d[1:] == d[:-1]) + 1
    for i in dup:
        add("duplicate", i, "same date twice")
    bad = np.flatnonzero(~np.isfinite(c) | (c <= 0))
    for i in bad:
        add("bad_price", i, f"close {c[i]:g}")
    ok = np.flatnonzero(np.isfinite(c) & (c > 0))
    od, oc = d[ok], c[ok]
    od, keep = np.unique(od, return_index=True)
    oc = oc[keep]
    missing = gaps = 0
    if len(od) > 1:
        miss = np.busday_count(od[:-1], od[1:]) - 1
        for i in np.flatnonzero(miss > GAP_DAYS):
            gaps += 1
            missing += int(miss[i])
            add("gap", i + 1, f"{miss[i]} business days missing after {od[i]}")
        r = oc[1:] / oc[:-1] - 1
        for i in np.flatnonzero(np.abs(r) > JUMP):
            add("jump", i + 1, f"{r[i]:+.0%} in one day")
        run = 0
        for i, s in enumerate(np.r_[False, oc[1:] == oc[:-1]]):
            run = run + 1 if s else 0
            if run == STALE_RUN:
                add("stale", i, f"close unchanged for {STALE_RUN}+ days")
    count = lambda k: sum(f["kind"] == k for f in found)
    out = {"first": str(od[0]) if len(od) else None, "last": str(od[-1]) if len(od) else None, "bars": len(c),
           "gaps": gaps, "missing": missing, "bad": len(bad), "dups": len(dup), "jumps": count("jump"), "stale": count("stale"),
           "_dates": od}
    if issues:
        out["issues"] = sorted(found, key=lambda f: f["date"])[:MAX_ISSUES]
        out["issues_total"] = len(found)
    return out


def _strip(dates: np.ndarray, lo: np.datetime64, hi: np.datetime64) -> list[float]:
    """Share of business days present in each of BUCKETS equal time slices."""
    edges = np.linspace(lo.astype("int64"), hi.astype("int64") + 1, BUCKETS + 1).astype("int64")
    have = np.histogram(dates.astype("int64"), edges)[0]
    want = np.maximum(np.busday_count(edges[:-1].astype("datetime64[D]"), edges[1:].astype("datetime64[D]")), 1)
    return [round(min(1.0, float(h) / float(w)), 2) for h, w in zip(have, want)]


@lru_cache(maxsize=2)
def _frame(version: int) -> pl.DataFrame:
    f = data_loader.load_market_frame().select(["Ticker", "Date", "Close"]).collect()
    return f.with_columns(Ticker=data_loader.NORMALIZED_TICKER).sort("Ticker", "Date")


@lru_cache(maxsize=2)
def _summary(version: int) -> tuple[list[dict], str | None, str | None]:
    rows = [{"symbol": key[0], **audit(g["Date"].to_numpy(), g["Close"].to_numpy())}
            for key, g in _frame(version).partition_by("Ticker", as_dict=True, maintain_order=True).items()]
    seen = [r for r in rows if len(r["_dates"])]
    lo = min((r["_dates"][0] for r in seen), default=None)
    hi = max((r["_dates"][-1] for r in seen), default=None)
    for r in rows:
        r["strip"] = _strip(r["_dates"], lo, hi) if len(r["_dates"]) else []
        del r["_dates"]
    return rows, (str(lo) if lo is not None else None), (str(hi) if hi is not None else None)


def listing(q: str = "", flagged: bool = False, offset: int = 0, limit: int = 100) -> dict:
    rows, lo, hi = _summary(performance._market_version())
    if q:
        rows = [r for r in rows if q.upper() in r["symbol"]]
    if flagged:
        rows = [r for r in rows if r["gaps"] or r["bad"] or r["dups"] or r["jumps"] or r["stale"]]
    limit = max(1, min(limit, 200))
    return {"symbols": rows[offset:offset + limit], "total": len(rows), "start": lo, "end": hi}


def detail(symbol: str) -> dict | None:
    g = _frame(performance._market_version()).filter(pl.col("Ticker") == symbol.upper())
    if not g.height:
        return None
    a = audit(g["Date"].to_numpy(), g["Close"].to_numpy(), issues=True)
    del a["_dates"]
    return {"symbol": symbol.upper(), **a}
