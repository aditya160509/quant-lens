"""What the data is, said plainly (PLAN §5.3). One source for the limits pill, the freshness pill and Library > Data."""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

import polars as pl

from app.services.screener_v2.core import data_loader

from . import data

ADJUSTMENT = "Mixed price adjustment: older segments raw, newer ones dividend-adjusted (rebuilt in the data refresh)"


@lru_cache(maxsize=2)
def _audit(version: str) -> dict:
    per = (data_loader.load_market_frame().lazy().group_by(data_loader.NORMALIZED_TICKER.alias("t"))
           .agg(pl.col("Date").min().alias("first"), pl.col("Date").max().alias("last"), pl.len().alias("bars")).collect())
    last = per["last"].max()
    ends = per.group_by(pl.col("last").dt.date().alias("d")).len().sort("len", descending=True)
    common_from, common_to = min(ends["d"].head(5).to_list()), max(ends["d"].head(5).to_list())
    stale = per.filter(pl.col("last") < pl.lit(common_from))  # stopped before the bulk of the file did
    by_year = (data_loader.load_market_frame().lazy().group_by(pl.col("Date").dt.year().alias("year")).agg(pl.col("Ticker").n_unique().alias("symbols"), pl.len().alias("bars"))
               .sort("year").collect())
    return {
        "tickers": per.height, "bars": int(per["bars"].sum()), "first_date": str(per["first"].min().date()), "last_date": str(last.date()),
        "most_end": [str(common_from), str(common_to)], "started_2015_or_later": int((per["first"].dt.year() >= 2015).sum()),
        "ended_early": stale.height, "ended_early_share": stale.height / per.height,
        "median_bars": float(per["bars"].median()), "by_year": by_year.to_dicts(),
        "adjustment": ADJUSTMENT, "fundamentals": "Fundamentals from 2021, 90-day filing lag", "data_version": version,
    }


def audit() -> dict:
    return _audit(data.data_version())


def freshness(today: dt.date | None = None) -> dict:
    """Age of the bulk of the data: most tickers end well before the file's last date, so the pill uses where most end."""
    a = audit()
    to = dt.date.fromisoformat(a["most_end"][1])
    age = ((today or dt.date.today()) - to).days
    return {"date": str(to), "age_days": age, "tone": "red" if age > 10 else "amber" if age > 3 else "ok", "label": f"Data to {to} ({age} days old)"}


def run_limits(*, start: str, end: str, requested: int, held: int, delisted: int, fill: str, costs: dict, haircut: float, holdout_from: str | None, top_n: int | None = None) -> list[dict]:
    a, f = audit(), freshness()
    c = costs
    cost = "Costs off" if not (c["commission_bps"] or c["slippage_bps"] or c["commission_share"] or c["slippage_range"]) else (
        f"Costs: commission {c['commission_bps']:g} bp, slippage {c['slippage_bps']:g} bp, borrow {c['borrow_bps']:g} bp a year" + (f", at most {c['volume_cap'] * 100:g}% of a bar's volume" if c["volume_cap"] else ""))
    rows = [
        ("Data range", f"{start} to {end}"),
        ("Coverage", f"{held} of {requested} names have bars in the range"),
        *([("Universe", f"Top {top_n} by today's liquidity: the list is chosen with hindsight, so past winners are over-represented")] if top_n else []),
        ("Delisted", f"{delisted} of {held} names stop trading inside the range; holdings settle at the last close" + (f" less {haircut * 100:g}%" if haircut else "")),
        ("Fill model", ("Signal at the close, fill at the next open" if fill == "next_open" else "Fill at the signal bar's close (optimistic)") + "; a gapped stop fills at the open; stop before target inside one bar"),
        ("Costs", cost),
        ("Hold-out", f"Bars from {holdout_from} are sealed for Validate and not shown" if holdout_from else "No hold-out kept"),
        ("Adjustment", a["adjustment"]),
        ("Dividends", "Dividends on shorts are not charged: the file holds no dividend column yet"),
        ("Fundamentals", a["fundamentals"]),
        ("Freshness", f["label"]),
    ]
    return [{"limit": k, "detail": v} for k, v in rows]
