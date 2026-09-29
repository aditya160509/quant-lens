"""ML V2 local data access.

Runtime code is read-only. `data_fetcher.py` contains append-only fetch plans for
missing FRED/yfinance/Ken-French artifacts but is not invoked by feature runs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Any
import math

import numpy as np
import pandas as pd

try:
    import polars as pl
except Exception:  # pragma: no cover
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
MARKET_UNIVERSE_HOURLY = BACKEND_DATA / "market_universe_hourly.parquet"
RESEARCH_HOURLY = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe_hourly.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
FF_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Research_Data_Factors_daily.csv"
FF5_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Research_Data_5_Factors_2x3_daily.csv"
MOM_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Momentum_Factor_daily.csv"


def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


def denormalize_candidates(symbol: str) -> set[str]:
    raw = str(symbol).strip()
    return {raw, raw.upper(), raw.replace("_", "-"), raw.replace("-", "_"), raw.upper().replace("_", "-"), raw.upper().replace("-", "_")}


def normalize_frequency(frequency: Any = "daily") -> str:
    raw = str(frequency or "daily").strip().lower().replace("-", "_")
    if raw in {"h", "1h", "hour", "hourly", "intraday"}:
        return "hourly"
    if raw in {"w", "week", "weekly"}:
        return "weekly"
    if raw in {"m", "month", "monthly"}:
        return "monthly"
    return "daily"


def annualization_factor(frequency: Any = "daily", asset_class: str | None = None) -> float:
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        return 365.0 * 24.0 if str(asset_class or "").lower() == "crypto" else 252.0 * 6.5
    if freq == "weekly":
        return 52.0
    if freq == "monthly":
        return 12.0
    return 252.0


def lookback_rows(lookback_days: int | float, frequency: Any = "daily") -> int:
    days = max(float(lookback_days or 1), 1.0)
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        return max(100, int(math.ceil(days * 6.5)))
    if freq == "weekly":
        return max(12, int(math.ceil(days / 5.0)))
    if freq == "monthly":
        return max(6, int(math.ceil(days / 21.0)))
    return max(30, int(days))


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    if not MARKET_UNIVERSE.exists():
        return pd.DataFrame(columns=columns)
    if pl is not None:
        try:
            df = pl.scan_parquet(str(MARKET_UNIVERSE)).select([c for c in columns if c]).collect().to_pandas()
        except Exception:
            df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    else:
        df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Ticker"] = df["Ticker"].map(normalize_symbol)
    return df.dropna(subset=["Ticker", "Date", "Close"]).sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    path = RESEARCH_HOURLY if RESEARCH_HOURLY.exists() else MARKET_UNIVERSE_HOURLY
    if not path.exists():
        return pd.DataFrame(columns=["Ticker", "Datetime", "Open", "High", "Low", "Close", "Volume"])
    df = pd.read_parquet(path)
    rename = {c: str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    if "Date" in df.columns and "Datetime" not in df.columns:
        df = df.rename(columns={"Date": "Datetime"})
    keep = [c for c in ["Ticker", "Datetime", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    out = df[keep].copy()
    out["Datetime"] = pd.to_datetime(out["Datetime"], errors="coerce")
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Ticker", "Datetime", "Close"]).sort_values(["Ticker", "Datetime"])


@lru_cache(maxsize=1)
def available_symbols(limit: int | None = None, frequency: str = "daily") -> list[str]:
    df = load_hourly_ohlcv() if normalize_frequency(frequency) == "hourly" and not load_hourly_ohlcv().empty else load_market_ohlcv()
    if df.empty:
        return []
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    out = [str(s) for s in counts.index]
    return out[:limit] if limit else out


def parse_symbols(payload: dict | None, default_limit: int = 80, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("universe")
    freq = normalize_frequency(payload.get("frequency") or payload.get("sampling_frequency") or "daily")
    universe = available_symbols(frequency=freq)
    existing = set(universe)
    raw_label = str(raw or "").strip().lower()
    if raw is None or raw_label in {"", "default", "sp500", "s&p 500"}:
        requested = universe[:default_limit]
    elif raw_label in {"all", "full", "master", "master_universe", "market_universe", "whole"}:
        requested = universe
    elif isinstance(raw, str):
        requested = [normalize_symbol(x) for x in raw.replace(";", ",").split(",") if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    filtered = [s for s in requested if s in existing]
    if not filtered:
        filtered = universe[:default_limit]
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or max_symbols)
    return filtered[: max(3, min(cap, max_symbols))]


def ohlcv_for_symbols(symbols: Iterable[str], lookback_days: int | None = None, frequency: str = "daily") -> pd.DataFrame:
    freq = normalize_frequency(frequency)
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    if freq == "hourly":
        df = load_hourly_ohlcv()
        out = df[df["Ticker"].isin(normalized)].copy()
        if lookback_days and not out.empty:
            cutoff = out["Datetime"].max() - pd.Timedelta(days=int(lookback_days) * 2)
            out = out[out["Datetime"] >= cutoff]
        return out.rename(columns={"Datetime": "Date"}).sort_values(["Ticker", "Date"])
    df = load_market_ohlcv()
    out = df[df["Ticker"].isin(normalized)].copy()
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


def returns_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily", min_coverage: float = 0.70) -> pd.DataFrame:
    freq = normalize_frequency(frequency)
    ohlcv = ohlcv_for_symbols(list(symbols), lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=freq)
    if ohlcv.empty:
        return pd.DataFrame()
    prices = ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    prices = prices.ffill().dropna(axis=1, thresh=max(20, int(len(prices) * min_coverage)))
    if freq == "hourly":
        prices = prices.resample("1h").last().ffill()
    elif freq == "weekly":
        prices = prices.resample("W-FRI").last()
    elif freq == "monthly":
        prices = prices.resample("M").last()
    rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    rets = rets.dropna(how="all").tail(lookback_rows(lookback_days, freq))
    return rets.dropna(axis=1, thresh=max(20, int(len(rets) * min_coverage))).fillna(0.0)


def close_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    ohlcv = ohlcv_for_symbols(list(symbols), lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=frequency)
    if ohlcv.empty:
        return pd.DataFrame()
    return ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().ffill().tail(lookback_rows(lookback_days, frequency))


def volume_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    ohlcv = ohlcv_for_symbols(list(symbols), lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=frequency)
    if ohlcv.empty:
        return pd.DataFrame()
    return ohlcv.pivot_table(index="Date", columns="Ticker", values="Volume", aggfunc="last").sort_index().ffill().tail(lookback_rows(lookback_days, frequency))


@lru_cache(maxsize=1)
def load_fundamentals_metadata() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    df = pd.read_parquet(MASTER_FUNDAMENTALS)
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    keep = [c for c in ["ticker", "sector", "industry", "marketCap", "currency", "exchange"] if c in df.columns]
    out = df[keep].copy()
    out["ticker"] = out["ticker"].map(normalize_symbol)
    return out.drop_duplicates("ticker", keep="last")


def sector_map(symbols: Iterable[str]) -> dict[str, str]:
    meta = load_fundamentals_metadata()
    if meta.empty or "sector" not in meta.columns:
        return {str(s): "Unknown" for s in symbols}
    mapping = dict(zip(meta["ticker"], meta["sector"].fillna("Unknown")))
    return {str(s): str(mapping.get(normalize_symbol(s), "Unknown")) for s in symbols}


def market_caps(symbols: Iterable[str]) -> dict[str, float]:
    meta = load_fundamentals_metadata()
    if meta.empty or "marketCap" not in meta.columns:
        return {str(s): 1.0 for s in symbols}
    mapping = dict(zip(meta["ticker"], pd.to_numeric(meta["marketCap"], errors="coerce")))
    out = {}
    for s in symbols:
        v = mapping.get(normalize_symbol(s), np.nan)
        out[str(s)] = float(v) if pd.notna(v) and float(v) > 0 else 1.0
    return out


@lru_cache(maxsize=1)
def load_macro() -> pd.DataFrame:
    if not CATEGORY7_MACRO.exists():
        return pd.DataFrame(columns=["date"])
    df = pd.read_parquet(CATEGORY7_MACRO)
    date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    out = df.rename(columns={date_col: "date"}).dropna(subset=["date"]).sort_values("date")
    for col in out.columns:
        if col != "date":
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _read_fama_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date"])
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            parts = [p.strip() for p in line.split(",")]
            if not parts or not parts[0].isdigit() or len(parts[0]) != 8:
                continue
            rows.append(parts)
    if not rows:
        return pd.DataFrame(columns=["date"])
    header = None
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.strip().lower().startswith(",") or "mkt" in line.lower():
                maybe = [p.strip() for p in line.split(",")]
                if len(maybe) == len(rows[0]):
                    header = ["date", *maybe[1:]]
                    break
    header = header or ["date", *[f"factor_{i}" for i in range(1, len(rows[0]))]]
    df = pd.DataFrame(rows, columns=header[: len(rows[0])])
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    for col in df.columns:
        if col != "date":
            df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
    return df.dropna(subset=["date"]).sort_values("date")


@lru_cache(maxsize=1)
def load_fama_french() -> pd.DataFrame:
    frames = [_read_fama_csv(FF_DAILY), _read_fama_csv(FF5_DAILY), _read_fama_csv(MOM_DAILY)]
    out = pd.DataFrame(columns=["date"])
    for frame in frames:
        if frame.empty:
            continue
        if out.empty or len(out.columns) == 1:
            out = frame
        else:
            cols = [c for c in frame.columns if c == "date" or c not in out.columns]
            out = out.merge(frame[cols], on="date", how="outer")
    return out.sort_values("date") if not out.empty else out


def data_inventory() -> dict[str, Any]:
    daily = load_market_ohlcv()
    hourly = load_hourly_ohlcv()
    macro = load_macro()
    ff = load_fama_french()
    return {
        "market_universe_parquet": str(MARKET_UNIVERSE),
        "market_universe_exists": MARKET_UNIVERSE.exists(),
        "daily_rows": int(len(daily)),
        "daily_tickers": int(daily["Ticker"].nunique()) if not daily.empty else 0,
        "hourly_rows": int(len(hourly)),
        "hourly_tickers": int(hourly["Ticker"].nunique()) if not hourly.empty else 0,
        "hourly_source": str(RESEARCH_HOURLY if RESEARCH_HOURLY.exists() else MARKET_UNIVERSE_HOURLY),
        "macro_rows": int(len(macro)),
        "macro_columns": [str(c) for c in macro.columns[:50]],
        "fama_french_rows": int(len(ff)),
        "fama_french_columns": [str(c) for c in ff.columns[:30]],
        "fundamentals_exists": MASTER_FUNDAMENTALS.exists(),
    }

