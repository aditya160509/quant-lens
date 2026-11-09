"""PCA V2 local data access.

Runtime feature calls are read-only. Fetching/appending missing data lives in
data_pooling.py.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    import polars as pl
except Exception:  # pragma: no cover  # noqa: BLE001
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
PRICE_DIR = BACKEND_DATA / "prices"
MARKET_UNIVERSE_HOURLY = BACKEND_DATA / "market_universe_hourly.parquet"
RESEARCH_HOURLY = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe_hourly.parquet"


FX_SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X",
    "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "EURCHF=X",
    "USDINR=X", "USDMXN=X", "USDBRL=X", "USDZAR=X", "USDKRW=X", "USDCNY=X", "USDHKD=X",
    "USDTWD=X", "USDSGD=X", "USDSEK=X", "USDNOK=X", "USDTHB=X", "USDIDR=X", "USDMYR=X", "USDPHP=X",
]
COMMODITY_FUTURES_SYMBOLS = [
    "CL=F", "BZ=F", "NG=F", "RB=F", "HO=F", "GC=F", "SI=F", "HG=F", "PL=F", "PA=F",
    "ZC=F", "ZW=F", "ZS=F", "KC=F", "SB=F", "CC=F", "CT=F",
]
RATES_FUTURES_SYMBOLS = ["ZB=F", "ZN=F", "ZF=F", "ZT=F"]
CRYPTO_SYMBOLS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "AVAX-USD", "MATIC-USD",
    "LINK-USD", "LTC-USD", "BCH-USD", "DOGE-USD",
]
EQUITY_PROXY_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "USO", "AAPL", "MSFT", "NVDA", "AMZN"]


class UnknownSymbolsError(ValueError):
    """Requested symbols absent from the selected local dataset."""

    def __init__(self, symbols):
        self.symbols = sorted(set(symbols))
        super().__init__("Unknown symbols: " + ", ".join(self.symbols))


def complete_returns(prices, rows):
    """Observed adjacent-price log returns; complete dates, never synthetic zeros."""
    returns = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna(how="all").tail(rows)
    coverage = {str(c): float(returns[c].notna().mean()) for c in returns}
    before = len(returns)
    result = returns.dropna(how="any")
    result.attrs["coverage"] = coverage
    result.attrs["rows_before_complete_case"] = before
    result.attrs["rows_dropped_missing"] = before - len(result)
    result.attrs["missing_data_policy"] = "complete_case_no_price_fill"
    return result


def normalize_symbol(symbol: object) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


def normalize_frequency(frequency: object = "daily") -> str:
    raw = str(frequency or "daily").strip().lower().replace("-", "_")
    if raw in {"h", "1h", "hour", "hourly", "intraday"}:
        return "hourly"
    if raw in {"w", "week", "weekly"}:
        return "weekly"
    if raw in {"m", "month", "monthly"}:
        return "monthly"
    return "daily"


def bars_per_day(frequency: object = "daily", asset_class: str | None = None) -> float:
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        cls = str(asset_class or "").lower()
        return 24.0 if cls == "crypto" else 6.5
    return 1.0


def annualization_factor(frequency: object = "daily", asset_class: str | None = None) -> float:
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        cls = str(asset_class or "").lower()
        return 365.0 * 24.0 if cls == "crypto" else 252.0 * 6.5
    if freq == "weekly":
        return 52.0
    if freq == "monthly":
        return 12.0
    return 252.0


def lookback_rows(lookback_days: float, frequency: object = "daily", asset_class: str | None = None) -> int:
    days = max(float(lookback_days or 0), 1.0)
    freq = normalize_frequency(frequency)
    if freq == "weekly":
        return max(8, int(math.ceil(days / 5.0)))  # noqa: RUF046
    if freq == "monthly":
        return max(6, int(math.ceil(days / 21.0)))  # noqa: RUF046
    return max(30, int(math.ceil(days * bars_per_day(freq, asset_class))))  # noqa: RUF046


def price_file_candidates(symbol: object) -> list[Path]:
    raw = str(symbol).strip()
    variants = {
        raw,
        raw.upper(),
        raw.replace("-", "_"),
        raw.replace("_", "-"),
        raw.upper().replace("-", "_"),
        raw.upper().replace("_", "-"),
    }
    return [PRICE_DIR / f"{variant}{ext}" for variant in variants for ext in (".parquet", ".csv")]


def local_price_file(symbol: object) -> Path | None:
    for path in price_file_candidates(symbol):
        if path.exists():
            return path
    return None


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    if pl is not None:
        try:
            df = pl.scan_parquet(str(MARKET_UNIVERSE)).select(columns).collect().to_pandas()
        except Exception:  # noqa: BLE001
            df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    else:
        df = pd.read_parquet(MARKET_UNIVERSE, columns=columns)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Ticker", "Date", "Close"]).sort_values(["Ticker", "Date"])


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    """Load the largest verified hourly parquet, falling back to backend hourly."""

    path = RESEARCH_HOURLY if RESEARCH_HOURLY.exists() else MARKET_UNIVERSE_HOURLY
    if not path.exists():
        return pd.DataFrame(columns=["Ticker", "Datetime", "Open", "High", "Low", "Close", "Volume"])
    names = pq.read_schema(path).names
    keep = [c for c in ["Market", "Ticker", "Datetime", "Open", "High", "Low", "Close", "Volume"] if c in names]
    out = pd.read_parquet(path, columns=keep)
    out["Datetime"] = pd.to_datetime(out["Datetime"], errors="coerce")
    out["Ticker"] = out["Ticker"].astype(str)
    return out.dropna(subset=["Ticker", "Datetime", "Close"]).sort_values(["Ticker", "Datetime"])


def read_local_price_ohlcv(symbol: object) -> pd.DataFrame:
    path = local_price_file(symbol)
    if path is None:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    if "Date" not in df.columns and "Datetime" not in df.columns:
        index_name = str(df.index.name or "").strip().title()
        if index_name in {"Date", "Datetime"}:
            df = df.reset_index()
    rename = {c: str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    date_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = pd.NA
    out = df[[date_col, "Open", "High", "Low", "Close", "Volume"]].rename(columns={date_col: "Date"}).copy(deep=False)
    out["Ticker"] = normalize_symbol(symbol)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=True).dt.tz_convert(None)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]]


def load_cross_asset_ohlcv(symbols: Iterable[str], lookback_days: int | None = None, master_only: bool = True) -> pd.DataFrame:
    """Read cross-asset symbols from the master parquet.

    The master universe is the daily source of truth. Local price files are an
    explicit fallback only when master_only=False for operator diagnostics.
    """

    requested_raw = [str(s).strip() for s in symbols if str(s).strip()]
    requested_norm = {normalize_symbol(s) for s in requested_raw}
    master = load_market_ohlcv()
    out = master[master["Ticker"].map(normalize_symbol).isin(requested_norm)].copy(deep=False)
    found = set(out["Ticker"].map(normalize_symbol).unique()) if not out.empty else set()
    frames = [out] if not out.empty else []
    if not master_only:
        for symbol in requested_raw:
            if normalize_symbol(symbol) in found:
                continue
            local = read_local_price_ohlcv(symbol)
            if not local.empty:
                frames.append(local)
    if not frames:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(["Ticker", "Date"], keep="last")
    if lookback_days and not combined.empty:
        cutoff = combined["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        combined = combined[combined["Date"] >= cutoff]
    return combined.sort_values(["Ticker", "Date"])


def cross_asset_returns_matrix(symbols: Iterable[str], lookback_days: int = 756, min_coverage: float = 0.65) -> pd.DataFrame:
    ohlcv = load_cross_asset_ohlcv(symbols, lookback_days=max(lookback_days + 120, lookback_days), master_only=True)
    if ohlcv.empty:
        return pd.DataFrame()
    prices = ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    prices = prices.dropna(axis=1, how="all")
    return complete_returns(prices, lookback_rows(lookback_days, "daily"))


@lru_cache(maxsize=1)
def load_fundamentals_metadata() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    cols = None
    try:
        all_cols = pq.read_schema(MASTER_FUNDAMENTALS).names
        cols = [c for c in ["ticker", "sector", "industry", "marketCap", "currency"] if c in all_cols]
    except Exception:  # noqa: BLE001
        cols = None
    df = pd.read_parquet(MASTER_FUNDAMENTALS, columns=cols) if cols else pd.read_parquet(MASTER_FUNDAMENTALS)
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "marketCap", "currency"])
    keep = [c for c in ["ticker", "sector", "industry", "marketCap", "currency"] if c in df.columns]
    out = df[keep].dropna(subset=["ticker"]).copy(deep=False)
    out["ticker"] = out["ticker"].map(normalize_symbol)
    return out.drop_duplicates("ticker", keep="last")


@lru_cache(maxsize=1)
def load_category7_macro() -> pd.DataFrame:
    if not CATEGORY7_MACRO.exists():
        return pd.DataFrame(columns=["date"])
    df = pd.read_parquet(CATEGORY7_MACRO)
    date_col = "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df.rename(columns={date_col: "date"}).dropna(subset=["date"]).sort_values("date")


def available_symbols(limit: int | None = None) -> list[str]:
    df = load_market_ohlcv()
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    symbols = [normalize_symbol(s) for s in counts.index]
    return symbols[:limit] if limit else symbols


def available_hourly_symbols(limit: int | None = None) -> list[str]:
    df = load_hourly_ohlcv()
    if df.empty:
        return []
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    symbols = [normalize_symbol(s) for s in counts.index]
    return symbols[:limit] if limit else symbols


def parse_symbols(payload: dict | None, default_limit: int = 80, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("universe")
    raw_label = str(raw).strip().lower() if raw is not None else ""
    frequency = normalize_frequency(payload.get("sampling_frequency") or payload.get("frequency") or "daily")
    source_symbols = available_hourly_symbols if frequency == "hourly" else available_symbols
    if raw_label in {"all", "full", "master", "master_universe", "market_universe", "whole"}:
        requested = source_symbols()
    elif raw is None or raw_label == "default":
        requested = source_symbols(default_limit)
    elif isinstance(raw, str):
        requested = [normalize_symbol(x) for x in raw.replace(";", ",").split(",") if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    existing = set(source_symbols())
    missing = [s for s in requested if s not in existing]
    if missing:
        raise UnknownSymbolsError(missing)
    filtered = list(dict.fromkeys(requested))
    max_symbols = int(payload.get("max_symbols") or payload.get("max_tickers") or max_symbols)
    limit = max(3,min(max_symbols,5000))
    if raw is not None and raw_label not in {"default","all","full","master","master_universe","market_universe","whole"} and len(filtered)>limit:
        raise ValueError(f"Requested {len(filtered)} symbols exceeds max_symbols={limit}; increase the explicit limit")
    return filtered[:limit]


def ohlcv_for_symbols(symbols: list[str] | tuple[str, ...], lookback_days: int | None = None) -> pd.DataFrame:
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    df = load_market_ohlcv()
    out = df[df["Ticker"].map(normalize_symbol).isin(normalized)].copy(deep=False)
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


def returns_matrix(symbols: list[str], lookback_days: int = 504, frequency: str = "daily", end_date=None, start_date=None) -> pd.DataFrame:
    frequency = normalize_frequency(frequency)
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    if frequency == "hourly":
        ohlcv = load_hourly_ohlcv()
        if ohlcv.empty:
            raise ValueError("frequency='hourly' requested but no hourly parquet is available")
        ohlcv = ohlcv[ohlcv["Ticker"].map(normalize_symbol).isin(normalized)].copy(deep=False)
        if end_date:
            ohlcv = ohlcv[ohlcv["Datetime"] <= pd.Timestamp(end_date)]
        prices = ohlcv.pivot_table(index="Datetime", columns="Ticker", values="Close", aggfunc="last").sort_index()
        prices = prices.resample("1h").last().dropna(how="all")
    else:
        ohlcv = ohlcv_for_symbols(symbols)
        if end_date:
            ohlcv = ohlcv[ohlcv["Date"] <= pd.Timestamp(end_date)]
        prices = ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    prices = prices.dropna(axis=1, how="all")
    if frequency == "weekly":
        prices = prices.resample("W-FRI").last()
    elif frequency == "monthly":
        prices = prices.resample("M").last()
    if start_date:
        prices = prices.loc[pd.Timestamp(start_date):]
    return complete_returns(prices, lookback_rows(lookback_days, frequency))


def dollar_volume_matrix(symbols: list[str], lookback_days: int = 504) -> pd.DataFrame:
    ohlcv = ohlcv_for_symbols(symbols, lookback_days=max(lookback_days + 80, lookback_days))
    ohlcv = ohlcv.copy(deep=False)
    ohlcv["DollarVolume"] = pd.to_numeric(ohlcv["Close"], errors="coerce") * pd.to_numeric(ohlcv["Volume"], errors="coerce")
    dv = ohlcv.pivot_table(index="Date", columns="Ticker", values="DollarVolume", aggfunc="last").sort_index()
    return dv.tail(int(lookback_days))


def sector_map(symbols: list[str]) -> dict[str, str]:
    meta = load_fundamentals_metadata()
    if meta.empty or "sector" not in meta.columns:
        return {s: "Unknown" for s in symbols}
    mapping = dict(zip(meta["ticker"], meta["sector"].fillna("Unknown")))
    return {s: str(mapping.get(normalize_symbol(s), "Unknown")) for s in symbols}


def latest_market_caps(symbols: list[str]) -> dict[str, float]:
    meta = load_fundamentals_metadata()
    if meta.empty or "marketCap" not in meta.columns:
        return {s: 1.0 for s in symbols}
    mapping = dict(zip(meta["ticker"], pd.to_numeric(meta["marketCap"], errors="coerce")))
    return {s: float(mapping.get(normalize_symbol(s), np.nan)) for s in symbols}
