"""Screener V2 local data access.

Runtime feature calls are read-only. Fetchers under ``fetchers/`` are
append-only operator helpers for datasets that are not present locally.
"""

from __future__ import annotations

from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterable
import math
import re
import zipfile
from io import BytesIO

import numpy as np
import pandas as pd

from .performance import cached_close_matrix, cached_fundamental_history, cached_returns_matrix, cached_volume_matrix, symbol_key

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
RESEARCH_MARKET_UNIVERSE = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe.parquet"
MARKET_UNIVERSE_HOURLY = BACKEND_DATA / "market_universe_hourly.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
FF5_DAILY = BACKEND_DATA / "factors_us" / "ff5_daily.csv"
MOM_DAILY = BACKEND_DATA / "factors_us" / "momentum_daily.csv"



AS_OF = ContextVar("screener_as_of", default=None)


@contextmanager
def as_of_context(value):
    date = pd.Timestamp(value) if value else None
    if date is not None and pd.isna(date):
        raise ValueError("Invalid as_of_date")
    token = AS_OF.set(date)
    try:
        yield
    finally:
        AS_OF.reset(token)


def eligible_reports(frame, date=None):
    cutoff = pd.Timestamp(date) if date is not None else AS_OF.get()
    if frame.empty or cutoff is None:
        return frame
    if "reportDate" not in frame:
        raise ValueError("Fundamentals lack reportDate")
    dates = pd.to_datetime(frame.reportDate, errors="coerce")
    return frame[(dates + pd.Timedelta(days=90) <= cutoff) & (dates + pd.Timedelta(days=640) >= cutoff)]


@lru_cache(maxsize=8192)
def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    if pl is not None:
        scan = pl.scan_parquet(str(path))
        return (scan.select(columns) if columns else scan).collect().to_pandas()
    return pd.read_parquet(path, columns=columns, engine="pyarrow")


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    rename = {c: str(c).strip().title() for c in df.columns}
    out = df.rename(columns=rename).copy()
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
    out[["Open", "High", "Low", "Close", "Volume"]] = out[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    return out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]].sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    if not MARKET_UNIVERSE.exists():
        raise FileNotFoundError(f"Required market dataset is missing: {MARKET_UNIVERSE}")
    source = MARKET_UNIVERSE
    cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    return _standardize_ohlcv(_read_parquet(source, cols))


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    return _standardize_ohlcv(_read_parquet(MARKET_UNIVERSE_HOURLY))


@lru_cache(maxsize=1)
def available_symbols() -> tuple[str, ...]:
    df = load_market_ohlcv()
    if df.empty:
        return ()
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    return tuple(str(x) for x in counts.index)


class UnknownSymbolsError(ValueError):
    """Explicit symbols must all belong to the local price universe."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Unknown tickers (not in local market data): {', '.join(missing)}")


def parse_symbols(payload: dict | None, default_limit: int = 500, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("universe")
    universe = list(available_symbols())
    label = str(raw or "").strip().lower()
    if label in {"sp500", "s&p 500"}:
        raise ValueError("S&P 500 membership data is unavailable; use master or explicit tickers")
    if raw is None or label in {"", "default"}:
        requested = universe[:default_limit]
    elif label in {"all", "full", "master", "master_universe", "market_universe", "whole"}:
        requested = universe
    elif isinstance(raw, str):
        requested = [normalize_symbol(x) for x in re.split(r"[,;\s]+", raw) if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    requested = list(dict.fromkeys(requested))
    universe_set = set(universe)
    missing = [symbol for symbol in requested if symbol not in universe_set]
    if missing:
        raise UnknownSymbolsError(missing)
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or max_symbols)
    if not 1 <= cap <= max_symbols:
        raise ValueError(f"max_symbols must be between 1 and {max_symbols}")
    return requested[:cap]


def ohlcv_for_symbols(symbols: Iterable[str], lookback_days: int | None = None) -> pd.DataFrame:
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    from .performance import _ohlcv_subset
    out = _ohlcv_subset(tuple(sorted(normalized)))
    cutoff_date = AS_OF.get()
    if cutoff_date is not None:
        out = out[out["Date"] <= cutoff_date]
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


def close_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols)
        return raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().tail(int(lookback_days))
    return cached_close_matrix(symbol_key(symbols), int(lookback_days)).copy()


def volume_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols)
        return raw.pivot_table(index="Date", columns="Ticker", values="Volume", aggfunc="last").sort_index().tail(int(lookback_days))
    return cached_volume_matrix(symbol_key(symbols), int(lookback_days)).copy()


def returns_matrix(symbols: Iterable[str], lookback_days: int = 756, min_coverage: float = 0.55) -> pd.DataFrame:
    if AS_OF.get() is not None:
        prices = close_matrix(symbols, lookback_days)
        rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
        return rets.dropna(axis=1, thresh=max(20, int(len(rets) * min_coverage)))
    min_coverage_bps = int(max(0.0, min(1.0, float(min_coverage))) * 10000)
    return cached_returns_matrix(symbol_key(symbols), int(lookback_days), min_coverage_bps).copy()


@lru_cache(maxsize=1)
def load_fundamentals() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker"])
    df = pd.read_parquet(MASTER_FUNDAMENTALS, engine="pyarrow")
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker"])
    out = df.copy()
    out["ticker"] = out["ticker"].map(normalize_symbol)
    if "reportDate" in out.columns:
        out["reportDate"] = pd.to_datetime(out["reportDate"], errors="coerce")
    return out.dropna(subset=["ticker"])


@lru_cache(maxsize=1)
def latest_fundamentals() -> pd.DataFrame:
    df = load_fundamentals()
    if df.empty:
        return pd.DataFrame(columns=["ticker"])
    if "reportDate" in df.columns:
        df = df.sort_values(["ticker", "reportDate"])
    return df.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)


def fundamental_history(symbol: str) -> pd.DataFrame:
    frame = cached_fundamental_history(normalize_symbol(symbol)).copy()
    cutoff = AS_OF.get()
    if cutoff is not None and not frame.empty:
        frame = frame[pd.to_datetime(frame.reportDate) + pd.Timedelta(days=90) <= cutoff]
    return frame


@lru_cache(maxsize=1)
def load_macro() -> pd.DataFrame:
    if CATEGORY7_MACRO.exists():
        df = pd.read_parquet(CATEGORY7_MACRO, engine="pyarrow")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.dropna(subset=["date"]).sort_values("date")
    return pd.DataFrame(columns=["date"])


def _parse_ken_french_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*,?\s*Mkt-RF|^\s*Date\s*,", line):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()
    rows = []
    header = [h.strip().replace("-", "_").lower() or "date" for h in lines[header_idx].split(",")]
    for line in lines[header_idx + 1:]:
        if not re.match(r"^\s*\d{8}\s*,", line):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(header):
            continue
        rows.append(parts[: len(header)])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=header)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    for col in df.columns:
        if col != "date":
            df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
    return df.dropna(subset=["date"]).sort_values("date")


@lru_cache(maxsize=1)
def load_factor_returns() -> pd.DataFrame:
    ff = _parse_ken_french_csv(FF5_DAILY)
    mom = _parse_ken_french_csv(MOM_DAILY)
    if ff.empty and mom.empty:
        return pd.DataFrame(columns=["date"])
    if not mom.empty:
        value_cols = [c for c in mom.columns if c != "date"]
        if value_cols:
            mom = mom.rename(columns={value_cols[0]: "mom"})
    if ff.empty:
        return mom
    if mom.empty:
        return ff
    return ff.merge(mom[["date", "mom"]], on="date", how="left")


def data_inventory() -> dict[str, Any]:
    return {
        "market_universe": {"exists": MARKET_UNIVERSE.exists(), "symbols": len(available_symbols())},
        "hourly_universe": {"exists": MARKET_UNIVERSE_HOURLY.exists(), "rows": int(len(load_hourly_ohlcv())) if MARKET_UNIVERSE_HOURLY.exists() else 0},
        "master_fundamentals": {"exists": MASTER_FUNDAMENTALS.exists(), "rows": int(len(load_fundamentals()))},
        "macro": {"exists": CATEGORY7_MACRO.exists(), "rows": int(len(load_macro()))},
        "ff5_daily": {"exists": FF5_DAILY.exists(), "rows": int(len(load_factor_returns()))},
        "momentum_daily": {"exists": MOM_DAILY.exists()},
    }
