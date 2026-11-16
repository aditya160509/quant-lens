"""Studio's one price source: the Screener loader's parquet rows as (bars x symbols) arrays. Chart, backtest and live all read this."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import polars as pl

from app.services.screener_v2.core import data_loader, performance

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
    return format(performance._market_version() ^ performance._path_version(data_loader.MARKET_UNIVERSE_HOURLY), "x")[-8:]


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


@lru_cache(maxsize=1)
def _hourly(version: int) -> pl.DataFrame:
    return pl.read_parquet(data_loader.MARKET_UNIVERSE_HOURLY).with_columns(data_loader.NORMALIZED_TICKER.alias("Ticker")).sort("Ticker", "Datetime")


def hourly_symbols() -> tuple[str, ...]:
    return tuple(sorted(_hourly(performance._path_version(data_loader.MARKET_UNIVERSE_HOURLY))["Ticker"].unique().to_list()))


def magnifier(p: Panel) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Hourly highs and lows with, per (day, symbol), the slice of that day's hours. None when no symbol of the panel has hourly bars."""
    h = _hourly(performance._path_version(data_loader.MARKET_UNIVERSE_HOURLY)).filter(pl.col("Ticker").is_in(list(p.symbols)))
    if not h.height or not len(p.dates):
        return None
    col = {s: i for i, s in enumerate(p.symbols)}
    sym = np.array([col[s] for s in h["Ticker"].to_list()])
    day = np.searchsorted(p.dates.values, h["Datetime"].dt.truncate("1d").to_numpy().astype("datetime64[ns]"))
    ok = (day < len(p.dates))
    ok[ok] &= p.dates.values[day[ok]] == h["Datetime"].dt.truncate("1d").to_numpy().astype("datetime64[ns]")[ok]
    idx = np.full((len(p.dates), len(p.symbols), 2), -1, dtype=np.int64)
    pos = np.flatnonzero(ok)
    if not len(pos):
        return None
    key = day[pos] * len(p.symbols) + sym[pos]  # sorted by symbol then time, so each (day, symbol) is one run
    starts = np.flatnonzero(np.concatenate(([True], key[1:] != key[:-1])))
    ends = np.concatenate((starts[1:], [len(pos)]))
    idx[day[pos[starts]], sym[pos[starts]], 0] = starts
    idx[day[pos[starts]], sym[pos[starts]], 1] = ends
    return h["High"].to_numpy()[pos].astype(np.float64), h["Low"].to_numpy()[pos].astype(np.float64), idx
