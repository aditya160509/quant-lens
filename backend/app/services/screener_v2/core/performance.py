"""Performance helpers for Screener V2.

This module centralizes the hot-path caches used by the feature layer.  The
feature functions stay deterministic and read-only; the caches only memoize
pure transformations of local parquet-backed datasets for the current Python
process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


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


def _path_version(path: Path | None) -> float:
    if path is None:
        return 0.0
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


def _market_source_path() -> Path | None:
    from . import data_loader

    if data_loader.MARKET_UNIVERSE.exists():
        return data_loader.MARKET_UNIVERSE
    return None


def _market_version() -> float:
    return _path_version(_market_source_path())


def _fundamentals_version() -> float:
    from . import data_loader

    return _path_version(data_loader.MASTER_FUNDAMENTALS)


@lru_cache(maxsize=1)
def _market_ohlcv_by_ticker(version: float) -> dict[str, pd.DataFrame]:
    """Pre-index the current market parquet by ticker for fast subset assembly."""
    from . import data_loader

    df = data_loader.load_market_ohlcv()
    if df.empty or "Ticker" not in df.columns:
        return {}
    return {str(ticker): group.copy() for ticker, group in df.groupby("Ticker", sort=False)}


def _ohlcv_subset(symbols: tuple[str, ...], lookback_days: int | None = None, version: float | None = None) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    grouped = _market_ohlcv_by_ticker(version if version is not None else _market_version())
    frames = [grouped[symbol] for symbol in symbols if symbol in grouped]
    if not frames:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    out = pd.concat(frames, ignore_index=True)
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


@lru_cache(maxsize=384)
def _cached_close_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, version: float = 0.0) -> pd.DataFrame:
    lookback = _lookback_key(lookback_days)
    raw = _ohlcv_subset(symbols, lookback_days=max(lookback + 260, lookback), version=version)
    if raw.empty:
        return pd.DataFrame()
    return raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().tail(lookback)


def cached_close_matrix(symbols: tuple[str, ...], lookback_days: int = 756) -> pd.DataFrame:
    return _cached_close_matrix_versioned(symbols, _lookback_key(lookback_days), _market_version())


@lru_cache(maxsize=256)
def _cached_volume_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, version: float = 0.0) -> pd.DataFrame:
    lookback = _lookback_key(lookback_days)
    raw = _ohlcv_subset(symbols, lookback_days=max(lookback + 260, lookback), version=version)
    if raw.empty:
        return pd.DataFrame()
    return raw.pivot_table(index="Date", columns="Ticker", values="Volume", aggfunc="last").sort_index().tail(lookback)


def cached_volume_matrix(symbols: tuple[str, ...], lookback_days: int = 756) -> pd.DataFrame:
    return _cached_volume_matrix_versioned(symbols, _lookback_key(lookback_days), _market_version())


@lru_cache(maxsize=256)
def _cached_returns_matrix_versioned(symbols: tuple[str, ...], lookback_days: int = 756, min_coverage_bps: int = 5500, version: float = 0.0) -> pd.DataFrame:
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
def _fundamentals_frame(version: float) -> pd.DataFrame:
    from . import data_loader

    return data_loader.load_fundamentals()


@lru_cache(maxsize=None)
def _cached_fundamental_history_versioned(symbol: str, version: float = 0.0) -> pd.DataFrame:
    normalized = str(symbol).strip().upper().replace(".", "_").replace("-", "_")
    df = _fundamentals_frame(version)
    if df.empty:
        return pd.DataFrame()
    out = df[df["ticker"].eq(normalized)].copy()
    if "reportDate" in out.columns:
        out = out.sort_values("reportDate")
    return out


def cached_fundamental_history(symbol: str) -> pd.DataFrame:
    normalized = str(symbol).strip().upper().replace(".", "_").replace("-", "_")
    return _cached_fundamental_history_versioned(normalized, _fundamentals_version())


def clear_performance_caches() -> None:
    _market_ohlcv_by_ticker.cache_clear()
    _cached_close_matrix_versioned.cache_clear()
    _cached_volume_matrix_versioned.cache_clear()
    _cached_returns_matrix_versioned.cache_clear()
    _fundamentals_frame.cache_clear()
    _cached_fundamental_history_versioned.cache_clear()


def performance_cache_info() -> dict[str, object]:
    return {
        "market_by_ticker": _market_ohlcv_by_ticker.cache_info()._asdict(),
        "close_matrix": _cached_close_matrix_versioned.cache_info()._asdict(),
        "volume_matrix": _cached_volume_matrix_versioned.cache_info()._asdict(),
        "returns_matrix": _cached_returns_matrix_versioned.cache_info()._asdict(),
        "fundamentals_frame": _fundamentals_frame.cache_info()._asdict(),
        "fundamental_history": _cached_fundamental_history_versioned.cache_info()._asdict(),
    }
