"""Volatility V2 local data access.

All loaders are read-only. Data acquisition lives in data_pooling.py so runtime
feature calls never mutate parquet files.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from joblib import Memory
except Exception:  # pragma: no cover
    Memory = None

try:
    import polars as pl
except Exception:  # pragma: no cover
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
_MEM = Memory(location="/tmp/vol_v2_cache", verbose=0) if Memory else None


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    if pl is not None:
        try:
            df = pl.scan_parquet(str(MARKET_UNIVERSE)).select(columns).collect().to_pandas()
        except Exception:
            df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    else:
        df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    if not np.issubdtype(df["Date"].dtype, np.datetime64):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Ticker", "Date", "Close"]).sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_category7_macro() -> pd.DataFrame:
    if not CATEGORY7_MACRO.exists():
        return pd.DataFrame()
    df = pd.read_parquet(CATEGORY7_MACRO)
    date_col = "date" if "date" in df.columns else df.columns[0]
    if not np.issubdtype(df[date_col].dtype, np.datetime64):
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df.rename(columns={date_col: "date"}).dropna(subset=["date"]).sort_values("date")


def _ohlcv_for_symbols_impl(symbols: tuple[str, ...], lookback_days: int | None = None) -> pd.DataFrame:
    symbols = [str(s).upper().replace(".", "_").replace("-", "_") for s in symbols if str(s).strip()]
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    data: pd.DataFrame
    if pl is not None and MARKET_UNIVERSE.exists() and symbols:
        try:
            scan = pl.scan_parquet(str(MARKET_UNIVERSE)).select(columns)
            scan = scan.filter(pl.col("Ticker").cast(pl.Utf8).is_in(symbols))
            data = scan.collect().to_pandas()
            if not np.issubdtype(data["Date"].dtype, np.datetime64):
                data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
            data = data.dropna(subset=["Ticker", "Date", "Close"]).sort_values(["Ticker", "Date"])
        except Exception:
            data = load_market_ohlcv()
            data = data[data["Ticker"].astype(str).str.upper().isin(symbols)]
    else:
        data = load_market_ohlcv()
        if symbols:
            data = data[data["Ticker"].astype(str).str.upper().isin(symbols)]
    if lookback_days:
        cutoff = data["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        data = data[data["Date"] >= cutoff]
    return data.copy()


if _MEM is not None:
    _cached_ohlcv_for_symbols = _MEM.cache(_ohlcv_for_symbols_impl)
else:
    _cached_ohlcv_for_symbols = _ohlcv_for_symbols_impl


def ohlcv_for_symbols(symbols: list[str] | tuple[str, ...], lookback_days: int | None = None) -> pd.DataFrame:
    key = tuple(sorted(str(s).upper().replace(".", "_").replace("-", "_") for s in symbols if str(s).strip()))
    return _cached_ohlcv_for_symbols(key, lookback_days)
