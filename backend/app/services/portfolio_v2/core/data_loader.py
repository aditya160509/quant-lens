"""Portfolio V2 local data access.

Runtime feature calls are read-only. Fetchers in ``fetchers/`` are append-only
operators for missing datasets and are not invoked by analytics runs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
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
RESEARCH_MARKET_UNIVERSE = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe.parquet"
MARKET_UNIVERSE_HOURLY = BACKEND_DATA / "market_universe_hourly.parquet"
RESEARCH_HOURLY = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe_hourly.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
CANONICAL = BACKEND_DATA / "canonical"
EQUITY_DAILY = CANONICAL / "equity_daily.parquet"
FX_DAILY = CANONICAL / "fx_daily.parquet"
CRYPTO_DAILY = CANONICAL / "crypto_daily.parquet"
FUTURES_DAILY = CANONICAL / "futures_daily.parquet"
HOLDINGS_HISTORY = CANONICAL / "portfolio_holdings_history.parquet"
TRADE_HISTORY = CANONICAL / "portfolio_trade_history.parquet"


@lru_cache(maxsize=8192)
def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


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


def lookback_rows(lookback_days: int | float, frequency: Any = "daily", asset_class: str | None = None) -> int:
    days = max(float(lookback_days or 1), 1.0)
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        bars = 24.0 if str(asset_class or "").lower() == "crypto" else 6.5
        return max(100, int(math.ceil(days * bars)))
    if freq == "weekly":
        return max(12, int(math.ceil(days / 5.0)))
    if freq == "monthly":
        return max(6, int(math.ceil(days / 21.0)))
    return max(30, int(days))


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    if pl is not None and columns:
        try:
            return pl.scan_parquet(str(path)).select(columns).collect().to_pandas()
        except Exception:
            pass
    try:
        return pd.read_parquet(path, columns=columns, engine="pyarrow")
    except Exception:
        return pd.read_parquet(path, engine="pyarrow")


def _standardize_ohlcv(df: pd.DataFrame, asset_class: str = "equity") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"])
    rename = {c: str(c).strip().title() for c in df.columns}
    out = df.rename(columns=rename).copy()
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"])
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
    out[["Open", "High", "Low", "Close", "Volume"]] = out[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    if "Asset_Class" not in out.columns:
        out["Asset_Class"] = asset_class
    out["Asset_Class"] = out["Asset_Class"].fillna(asset_class).astype(str).str.lower()
    return out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"]]


_MERGED_OHLCV_CACHE: pd.DataFrame | None = None


def _merged_ohlcv() -> pd.DataFrame:
    global _MERGED_OHLCV_CACHE
    if _MERGED_OHLCV_CACHE is None:
        daily = load_market_ohlcv()
        canonical = load_canonical_ohlcv()
        if daily.empty and canonical.empty:
            _MERGED_OHLCV_CACHE = pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"])
        elif daily.empty:
            _MERGED_OHLCV_CACHE = canonical
        elif canonical.empty:
            _MERGED_OHLCV_CACHE = daily
        else:
            merged = pd.concat([daily, canonical], ignore_index=True, copy=False)
            # Temporary category dtype speeds up dedup sort on large universes
            merged["Ticker"] = merged["Ticker"].astype("category")
            merged = merged.drop_duplicates(["Ticker", "Date"], keep="last").sort_values(["Ticker", "Date"])
            merged["Ticker"] = merged["Ticker"].astype(str)
            _MERGED_OHLCV_CACHE = merged
    return _MERGED_OHLCV_CACHE


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    source = MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE
    cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    return _standardize_ohlcv(_read_parquet(source, cols), "equity").sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    source = RESEARCH_HOURLY if RESEARCH_HOURLY.exists() else MARKET_UNIVERSE_HOURLY
    return _standardize_ohlcv(_read_parquet(source), "mixed").sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_canonical_ohlcv() -> pd.DataFrame:
    frames = []
    for path, cls in [(EQUITY_DAILY, "equity"), (FX_DAILY, "fx"), (CRYPTO_DAILY, "crypto"), (FUTURES_DAILY, "futures")]:
        frame = _standardize_ohlcv(_read_parquet(path), cls)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(["Ticker", "Date"], keep="last").sort_values(["Ticker", "Date"])


@lru_cache(maxsize=4)
def _available_symbols_full(frequency: str = "daily", include_cross_asset: bool = True) -> tuple[str, ...]:
    freq = normalize_frequency(frequency)
    frames = [load_hourly_ohlcv()] if freq == "hourly" and not load_hourly_ohlcv().empty else [load_market_ohlcv()]
    if include_cross_asset and freq != "hourly":
        frames.append(load_canonical_ohlcv())
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        return ()
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    return tuple(str(s) for s in counts.index)


def available_symbols(limit: int | None = None, frequency: str = "daily", include_cross_asset: bool = True) -> list[str]:
    out = list(_available_symbols_full(normalize_frequency(frequency), include_cross_asset))
    return out[:limit] if limit else out


def parse_symbols(payload: dict | None, default_limit: int = 80, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("universe")
    frequency = normalize_frequency(payload.get("frequency") or payload.get("sampling_frequency") or "daily")
    universe = available_symbols(frequency=frequency, include_cross_asset=True)
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
    df = load_hourly_ohlcv() if freq == "hourly" else _merged_ohlcv()
    mask = df["Ticker"].isin(normalized)
    out = df.loc[mask]
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out.loc[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


def returns_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily", min_coverage: float = 0.65) -> pd.DataFrame:
    freq = normalize_frequency(frequency)
    raw = ohlcv_for_symbols(symbols, lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=freq)
    if raw.empty:
        return pd.DataFrame()
    prices = raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().ffill()
    if freq == "hourly":
        prices = prices.resample("1h").last().ffill()
    elif freq == "weekly":
        prices = prices.resample("W-FRI").last()
    elif freq == "monthly":
        prices = prices.resample("ME").last()
    price_thresh = min(len(prices), max(3 if freq == "monthly" else 20, int(len(prices) * min_coverage)))
    prices = prices.dropna(axis=1, thresh=price_thresh)
    arr = prices.to_numpy(dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_ret = np.empty_like(arr)
        log_ret[0] = np.nan
        np.divide(arr[1:], arr[:-1], out=log_ret[1:])
        np.log(log_ret[1:], out=log_ret[1:])
    np.clip(log_ret, -10.0, 10.0, out=log_ret)
    np.nan_to_num(log_ret, copy=False, nan=np.nan, posinf=0.0, neginf=0.0)
    rets = pd.DataFrame(log_ret, index=prices.index, columns=prices.columns)
    rets = rets.dropna(how="all").tail(lookback_rows(lookback_days, freq))
    ret_thresh = min(len(rets), max(3 if freq == "monthly" else 20, int(len(rets) * min_coverage)))
    return rets.dropna(axis=1, thresh=ret_thresh).fillna(0.0)


def close_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    raw = ohlcv_for_symbols(symbols, lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=frequency)
    if raw.empty:
        return pd.DataFrame()
    return raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().ffill().tail(lookback_rows(lookback_days, frequency))


def dollar_volume_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    raw = ohlcv_for_symbols(symbols, lookback_days=max(int(lookback_days) + 120, int(lookback_days)), frequency=frequency)
    if raw.empty:
        return pd.DataFrame()
    raw["DollarVolume"] = raw["Close"].astype(float) * raw["Volume"].fillna(0.0).astype(float)
    return raw.pivot_table(index="Date", columns="Ticker", values="DollarVolume", aggfunc="last").sort_index().ffill().tail(lookback_rows(lookback_days, frequency))


@lru_cache(maxsize=1)
def load_fundamentals_metadata() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    df = pd.read_parquet(MASTER_FUNDAMENTALS)
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    keep = [c for c in ["ticker", "sector", "industry", "marketCap", "currency", "exchange"] if c in df.columns]
    out = df[keep].dropna(subset=["ticker"]).copy()
    out["ticker"] = out["ticker"].map(normalize_symbol)
    return out.drop_duplicates("ticker", keep="last")


@lru_cache(maxsize=1)
def _fundamentals_maps() -> tuple[dict[str, str], dict[str, float]]:
    meta = load_fundamentals_metadata()
    if meta.empty:
        return {}, {}
    sec: dict[str, str] = {}
    cap: dict[str, float] = {}
    for row in meta.itertuples(index=False):
        data = row._asdict()
        ticker = str(data.get("ticker", ""))
        sec[ticker] = str(data.get("sector", "Unknown") or "Unknown")
        try:
            mc = float(data.get("marketCap", 1.0))
            cap[ticker] = mc if mc > 0 else 1.0
        except Exception:
            cap[ticker] = 1.0
    return sec, cap


def sector_map(symbols: Iterable[str]) -> dict[str, str]:
    sec, _ = _fundamentals_maps()
    normalized = [normalize_symbol(s) for s in symbols]
    return {s: str(sec.get(s, "Unknown")) for s in normalized}


def market_caps(symbols: Iterable[str]) -> dict[str, float]:
    _, cap = _fundamentals_maps()
    normalized = [normalize_symbol(s) for s in symbols]
    return {s: float(cap.get(s, 1.0)) for s in normalized}


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


@lru_cache(maxsize=1)
def _load_holdings_history_cached() -> pd.DataFrame:
    if not HOLDINGS_HISTORY.exists():
        return pd.DataFrame(columns=["asof", "ticker", "quantity", "avg_cost", "base_currency"])
    df = pd.read_parquet(HOLDINGS_HISTORY)
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].map(normalize_symbol)
    if "asof" in df.columns:
        df["asof"] = pd.to_datetime(df["asof"], errors="coerce")
    return df


def load_holdings_history() -> pd.DataFrame:
    """Return an isolated holdings frame while caching parquet I/O."""
    return _load_holdings_history_cached().copy()


def current_holdings_weights(default_symbols: Iterable[str], nav: float = 1_000_000.0) -> pd.Series:
    holdings = load_holdings_history()
    if holdings.empty:
        syms = list(default_symbols)
        return pd.Series(np.repeat(1 / max(len(syms), 1), len(syms)), index=syms, dtype=float)
    latest = holdings.sort_values("asof").groupby("ticker").tail(1)
    prices = close_matrix(latest["ticker"].tolist(), lookback_days=20)
    px = prices.ffill().iloc[-1] if not prices.empty else pd.Series(dtype=float)
    latest_idx = latest.set_index("ticker")
    fallback_px = latest_idx["avg_cost"].astype(float) if "avg_cost" in latest_idx.columns else pd.Series(1.0, index=latest_idx.index)
    resolved_px = px.reindex(latest_idx.index).fillna(fallback_px)
    values = latest_idx["quantity"].astype(float) * resolved_px
    values = values[values > 0]
    if values.empty:
        syms = list(default_symbols)
        return pd.Series(np.repeat(1 / max(len(syms), 1), len(syms)), index=syms, dtype=float)
    return values / max(float(values.sum()), 1e-12)


def data_inventory() -> dict[str, Any]:
    daily = load_market_ohlcv()
    canonical = load_canonical_ohlcv()
    hourly = load_hourly_ohlcv()
    macro = load_macro()
    return {
        "market_universe": str(MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE),
        "daily_rows": int(len(daily)),
        "daily_tickers": int(daily["Ticker"].nunique()) if not daily.empty else 0,
        "canonical_rows": int(len(canonical)),
        "canonical_tickers": int(canonical["Ticker"].nunique()) if not canonical.empty else 0,
        "hourly_rows": int(len(hourly)),
        "hourly_tickers": int(hourly["Ticker"].nunique()) if not hourly.empty else 0,
        "macro_rows": int(len(macro)),
        "macro_columns": [str(c) for c in macro.columns],
        "holdings_history_exists": HOLDINGS_HISTORY.exists(),
        "trade_history_exists": TRADE_HISTORY.exists(),
    }
