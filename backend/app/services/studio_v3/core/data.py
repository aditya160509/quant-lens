"""Studio's one price source: the Screener loader's parquet rows as (bars x symbols) arrays. Chart, backtest and live all read this."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import polars as pl

from app.services.screener_v2.core import performance

FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class Panel:
    dates: pd.DatetimeIndex
    symbols: tuple[str, ...]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def bars(self) -> dict[str, np.ndarray]:
        return {f: getattr(self, f) for f in FIELDS}

    def window(self, lo: int, hi: int) -> Panel:
        return Panel(self.dates[lo:hi], self.symbols, *(getattr(self, f)[lo:hi] for f in FIELDS))


def data_version() -> str:
    return format(performance._market_version(), "x")[-8:]


@lru_cache(maxsize=4)
def _panel(symbols: tuple[str, ...], start: str | None, end: str | None, version: int) -> Panel:
    raw = performance._subset_frame(symbols, None, ("Ticker", "Date", "Open", "High", "Low", "Close", "Volume"), None)
    if start:
        raw = raw.filter(pl.col("Date") >= pd.Timestamp(start))
    if end:
        raw = raw.filter(pl.col("Date") <= pd.Timestamp(end))
    if not raw.height:
        return Panel(pd.DatetimeIndex([]), (), *(np.empty((0, 0)) for _ in FIELDS))
    # rows are sorted by Ticker then Date: fill each field's matrix by position
    runs = raw["Ticker"].cast(pl.String).rle().struct.unnest()
    stamps = raw["Date"].to_numpy()
    dates = np.unique(stamps)
    rows, cols = np.searchsorted(dates, stamps), np.repeat(np.arange(runs.height), runs["len"].to_numpy())
    out = []
    for field in ("Open", "High", "Low", "Close", "Volume"):
        m = np.full((len(dates), runs.height), np.nan)
        m[rows, cols] = raw[field].cast(pl.Float64).to_numpy()
        out.append(m)
    bad = ~(np.isfinite(out[3]) & (out[3] > 0))  # a bar without a usable close is no bar
    for m in out:
        m[bad] = np.nan
    return Panel(pd.DatetimeIndex(dates), tuple(runs["value"].to_list()), *out)


def panel(symbols, start: str | None = None, end: str | None = None) -> Panel:
    return _panel(performance.symbol_key(symbols), start, end, performance._market_version())


