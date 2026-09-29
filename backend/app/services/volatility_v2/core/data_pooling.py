"""Append-only data pooling utilities for Volatility V2.

These helpers are intentionally not called by feature runtime code. They are
operator tools for filling local parquet gaps before the Volatility V2 router is
wired. They append/deduplicate by key and never blindly overwrite existing data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"


def _append_dedup_parquet(path: Path, new_rows: pd.DataFrame, keys: list[str]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if new_rows.empty:
        return {"path": str(path), "added_rows": 0, "total_rows": None}
    if path.exists():
        existing = pd.read_parquet(path)
        existing_count = len(existing)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        existing_count = 0
        combined = new_rows.copy()
    combined = combined.drop_duplicates(keys, keep="last").sort_values(keys)
    combined.to_parquet(path, index=False)
    return {"path": str(path), "added_rows": int(max(0, len(combined) - existing_count)), "total_rows": int(len(combined))}


def fetch_yahoo_ohlcv(symbols: Iterable[str], period: str = "10y") -> pd.DataFrame:
    """Fetch daily OHLCV from Yahoo Finance for missing symbols."""
    if yf is None:
        raise RuntimeError("yfinance is not installed in this environment")
    frames = []
    for symbol in sorted({str(s).strip() for s in symbols if str(s).strip()}):
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.reset_index()
        df["Ticker"] = symbol.upper().replace(".", "_").replace("-", "_")
        df = df.rename(columns={"Date": "Date", "Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"})
        frames.append(df[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])


def append_ohlcv_to_master(symbols: Iterable[str], period: str = "10y", path: Path = MARKET_UNIVERSE) -> dict:
    rows = fetch_yahoo_ohlcv(symbols, period=period)
    rows["Date"] = pd.to_datetime(rows["Date"], errors="coerce")
    rows = rows.dropna(subset=["Ticker", "Date", "Close"])
    return _append_dedup_parquet(path, rows, ["Ticker", "Date"])


def fetch_fred_series(series_ids: Iterable[str], start: str = "1990-01-01") -> pd.DataFrame:
    """Fetch FRED CSV observations without requiring an API key."""
    frames = []
    for sid in sorted({str(s).strip().upper() for s in series_ids if str(s).strip()}):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        from io import StringIO

        df = pd.read_csv(StringIO(resp.text))
        if "observation_date" not in df.columns or sid not in df.columns:
            continue
        df = df.rename(columns={"observation_date": "date", sid: sid.lower()})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df[sid.lower()] = pd.to_numeric(df[sid.lower()].replace(".", pd.NA), errors="coerce")
        frames.append(df[["date", sid.lower()]])
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    return out.sort_values("date")


def append_macro_to_category7(series_ids: Iterable[str] = ("VIXCLS", "DGS2", "DGS10", "BAMLC0A0CM", "BAMLH0A0HYM2"), path: Path = CATEGORY7_MACRO) -> dict:
    """Append FRED volatility/rates/credit fields to category7 macro parquet."""
    rows = fetch_fred_series(series_ids)
    return _append_dedup_parquet(path, rows, ["date"])


def fetch_yahoo_macro_series(symbol_map: dict[str, str] | None = None, period: str = "10y") -> pd.DataFrame:
    """Fetch public Yahoo macro/vol-index closes as wide daily series."""
    if yf is None:
        raise RuntimeError("yfinance is not installed in this environment")
    symbol_map = symbol_map or {
        "^VIX": "vix_yahoo",
        "^VIX3M": "vix3m",
        "^VIX6M": "vix6m",
        "^VIX9D": "vix9d",
        "^VIX1Y": "vix1y",
    }
    frames = []
    for symbol, col in symbol_map.items():
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        close = pd.to_numeric(df.get("Close"), errors="coerce")
        frame = pd.DataFrame({"date": pd.to_datetime(close.index, errors="coerce"), str(col): close.to_numpy(dtype=float)})
        frames.append(frame.dropna(subset=["date"]))
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    return out.sort_values("date")


def append_implied_vol_indices_to_category7(path: Path = CATEGORY7_MACRO, period: str = "10y") -> dict:
    """Append public VIX term-structure proxies into category7 without overwriting."""
    rows = fetch_yahoo_macro_series(period=period)
    return _append_dedup_parquet(path, rows, ["date"])


def missing_data_report(required_symbols: Iterable[str] = ()) -> dict:
    market = pd.read_parquet(MARKET_UNIVERSE, columns=["Ticker", "Date"]) if MARKET_UNIVERSE.exists() else pd.DataFrame()
    macro = pd.read_parquet(CATEGORY7_MACRO) if CATEGORY7_MACRO.exists() else pd.DataFrame()
    existing = set(market.get("Ticker", pd.Series(dtype=str)).astype(str).str.upper())
    requested = {str(s).upper().replace(".", "_").replace("-", "_") for s in required_symbols if str(s).strip()}
    macro_cols = {str(c).lower() for c in macro.columns}
    return {
        "missing_symbols": sorted(requested - existing),
        "has_ohlcv_master": bool(MARKET_UNIVERSE.exists()),
        "has_category7_macro": bool(CATEGORY7_MACRO.exists()),
        "missing_macro_series": sorted({"vixcls", "dgs2", "dgs10", "bamlc0a0cm", "bamlh0a0hym2", "vix3m", "vix6m"} - macro_cols),
    }
