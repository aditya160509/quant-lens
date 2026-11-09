"""Performance helpers for Screener V2.

This module centralizes the hot-path caches used by the feature layer.  The
feature functions stay deterministic and read-only; the caches only memoize
pure transformations of local parquet-backed datasets for the current Python
process.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl


def symbol_key(symbols: Iterable[str]) -> tuple[str, ...]:
    """Return an order-independent, hashable, de-duplicated symbol key."""
    seen: set[str] = set()
    for symbol in symbols or []:
        text = str(symbol).strip().upper().replace(".", "_").replace("-", "_")
        if text:
            seen.add(text)
    return tuple(sorted(seen))


def _lookback_key(lookback_days: int | None, floor: int = 1) -> int:
    try:
        value = int(lookback_days or floor)
    except (TypeError, ValueError):
        value = floor
    return max(floor, value)


def _path_version(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _market_source_path() -> Path | None:
    from . import data_loader

    if data_loader.MARKET_UNIVERSE.exists():
        return data_loader.MARKET_UNIVERSE
    return None


def _market_version() -> int:
    return _path_version(_market_source_path())


def _fundamentals_version() -> int:
    from . import data_loader

    return _path_version(data_loader.MASTER_FUNDAMENTALS)


def frame_to_pandas(frame: pl.DataFrame) -> pd.DataFrame:
    """Polars to pandas, sharing one Python string per ticker run instead of one per row."""
    out = frame.drop("Ticker").to_pandas()
    runs = frame["Ticker"].cast(pl.String).rle().struct.unnest()
    names = np.empty(runs.height, dtype=object)
    names[:] = runs["value"].to_list()
    out.insert(frame.columns.index("Ticker"), "Ticker", pd.array(names.repeat(runs["len"].to_numpy()), dtype=object))
    return out


def pivot_last(raw: pd.DataFrame, field: str) -> pd.DataFrame:
    """Date-by-ticker matrix; the loader guarantees one row per ticker and date."""
    if raw.empty:
        return raw.pivot_table(index="Date", columns="Ticker", values=field, aggfunc="last").sort_index()
    return raw.pivot(index="Date", columns="Ticker", values=field).dropna(how="all").dropna(axis=1, how="all").sort_index()


_OHLCV = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]


def _subset_frame(symbols: tuple[str, ...], lookback_days: int | None, columns: tuple[str, ...] | None, as_of) -> pl.DataFrame:
    from . import data_loader

    query = data_loader.load_market_frame().lazy().filter(pl.col("Ticker").cast(pl.String).is_in(list(symbols)))
    if as_of is not None:
        query = query.filter(pl.col("Date") <= pd.Timestamp(as_of))
    if lookback_days:
        latest = query.select(pl.col("Date").max()).collect().item()
        if latest is not None:
            query = query.filter(pl.col("Date") >= pd.Timestamp(latest) - pd.Timedelta(days=int(lookback_days) * 2))
    return query.select(list(columns) if columns else _OHLCV).collect()


def _ohlcv_subset(symbols: tuple[str, ...], lookback_days: int | None = None, version: int | None = None, columns: tuple[str, ...] | None = None, as_of=None) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=_OHLCV)
    out = _subset_frame(symbols, lookback_days, columns, as_of)
    return frame_to_pandas(out) if out.height else pd.DataFrame(columns=_OHLCV)


def _matrix(symbols: tuple[str, ...], lookback: int, field: str) -> pd.DataFrame:
    """Date-by-ticker matrix built in Polars, so no long pandas frame exists."""
    raw = _subset_frame(symbols, max(lookback + 260, lookback), ("Ticker", "Date", field), None)
    if not raw.height:
        return pd.DataFrame()
    wide = raw.with_columns(pl.col("Ticker").cast(pl.String)).pivot(on="Ticker", index="Date", values=field).sort("Date").tail(lookback)
    out = wide.drop("Date").to_pandas()
    out.index = pd.DatetimeIndex(wide["Date"].to_numpy(), name="Date")
    out.columns = pd.Index(out.columns.tolist(), dtype=object, name="Ticker")
    return out.reindex(columns=sorted(out.columns)).dropna(axis=1, how="all")


@lru_cache(maxsize=6)
def _cached_close_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, version: int = 0) -> pd.DataFrame:
    return _matrix(symbols, _lookback_key(lookback_days), "Close")


def cached_close_matrix(symbols: tuple[str, ...], lookback_days: int = 756) -> pd.DataFrame:
    return _cached_close_matrix_versioned(symbols, _lookback_key(lookback_days), _market_version())


@lru_cache(maxsize=6)
def _cached_volume_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, version: int = 0) -> pd.DataFrame:
    return _matrix(symbols, _lookback_key(lookback_days), "Volume")


def cached_volume_matrix(symbols: tuple[str, ...], lookback_days: int = 756) -> pd.DataFrame:
    return _cached_volume_matrix_versioned(symbols, _lookback_key(lookback_days), _market_version())


@lru_cache(maxsize=6)
def _cached_returns_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, min_coverage_bps: int = 5500, version: int = 0) -> pd.DataFrame:
    lookback = _lookback_key(lookback_days)
    min_coverage = max(0.0, min(1.0, float(min_coverage_bps) / 10000.0))
    prices = _cached_close_matrix_versioned(symbols, lookback, version)
    if prices.empty:
        return pd.DataFrame()
    prices = prices.dropna(axis=1, thresh=max(20, int(len(prices) * min_coverage)))
    rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    rets = rets.dropna(how="all")
    return rets.dropna(axis=1, thresh=max(20, int(len(rets) * min_coverage)))


def cached_returns_matrix(symbols: tuple[str, ...], lookback_days: int = 756, min_coverage_bps: int = 5500) -> pd.DataFrame:
    return _cached_returns_matrix_versioned(symbols, _lookback_key(lookback_days), int(min_coverage_bps), _market_version())


@lru_cache(maxsize=1)
def _fundamentals_frame(version: int) -> pd.DataFrame:
    from . import data_loader

    return data_loader.load_fundamentals()


@lru_cache(maxsize=1)
def _fundamentals_positions(version: int) -> dict[str, np.ndarray]:
    return _fundamentals_frame(version).groupby("ticker", sort=False).indices


@lru_cache(maxsize=512)
def _cached_fundamental_history_versioned(symbol: str, version: int = 0) -> pd.DataFrame:
    normalized = str(symbol).strip().upper().replace(".", "_").replace("-", "_")
    df = _fundamentals_frame(version)
    if df.empty:
        return pd.DataFrame()
    out = df.iloc[_fundamentals_positions(version).get(normalized, np.empty(0, dtype=np.intp))]
    if "reportDate" in out.columns:
        out = out.sort_values("reportDate")
    return out


def cached_fundamental_history(symbol: str) -> pd.DataFrame:
    normalized = str(symbol).strip().upper().replace(".", "_").replace("-", "_")
    return _cached_fundamental_history_versioned(normalized, _fundamentals_version())


def clear_performance_caches() -> None:
    _cached_close_matrix_versioned.cache_clear()
    _cached_volume_matrix_versioned.cache_clear()
    _cached_returns_matrix_versioned.cache_clear()
    _fundamentals_frame.cache_clear()
    _fundamentals_positions.cache_clear()
    _cached_fundamental_history_versioned.cache_clear()


def performance_cache_info() -> dict[str, object]:
    return {
        "close_matrix": _cached_close_matrix_versioned.cache_info()._asdict(),
        "volume_matrix": _cached_volume_matrix_versioned.cache_info()._asdict(),
        "returns_matrix": _cached_returns_matrix_versioned.cache_info()._asdict(),
        "fundamentals_frame": _fundamentals_frame.cache_info()._asdict(),
        "fundamental_history": _cached_fundamental_history_versioned.cache_info()._asdict(),
    }
