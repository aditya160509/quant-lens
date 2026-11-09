"""Portfolio V2 local data access.

Runtime feature calls are read-only. Fetchers in ``fetchers/`` are append-only
operators for missing datasets and are not invoked by analytics runs.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
MARKET_UNIVERSE_HOURLY = BACKEND_DATA / "market_universe_hourly.parquet"
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
    if raw in {"d", "1d", "day", "daily"}:
        return "daily"
    raise ValueError("Unknown frequency: " + raw)


def annualization_factor(
    frequency: Any = "daily", asset_class: str | None = None
) -> float:
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        return (
            365.0 * 24.0 if str(asset_class or "").lower() == "crypto" else 252.0 * 6.5
        )
    if freq == "weekly":
        return 52.0
    if freq == "monthly":
        return 12.0
    return 252.0


def lookback_rows(
    lookback_days: float, frequency: Any = "daily", asset_class: str | None = None
) -> int:
    days = max(float(lookback_days or 1), 1.0)
    freq = normalize_frequency(frequency)
    if freq == "hourly":
        bars = 24.0 if str(asset_class or "").lower() == "crypto" else 6.5
        return max(100, int(math.ceil(days * bars)))  # noqa: RUF046
    if freq == "weekly":
        return max(12, int(math.ceil(days / 5.0)))  # noqa: RUF046
    if freq == "monthly":
        return max(6, int(math.ceil(days / 21.0)))  # noqa: RUF046
    return max(30, int(days))


def file_version(path):
    path = Path(path)
    return (
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        if path.exists()
        else (str(path), None, None)
    )


def source_version():
    return tuple(
        file_version(p)
        for p in [
            MARKET_UNIVERSE,
            MARKET_UNIVERSE_HOURLY,
            EQUITY_DAILY,
            FX_DAILY,
            CRYPTO_DAILY,
            FUTURES_DAILY,
            MASTER_FUNDAMENTALS,
            CATEGORY7_MACRO,
            HOLDINGS_HISTORY,
            TRADE_HISTORY,
            BACKEND_DATA / "factors_us/ff5_daily.parquet",
            BACKEND_DATA / "factors_us/momentum_daily.parquet",
        ]
    )


_SCOPE = ContextVar("portfolio_request", default={})  # noqa: B039


@contextmanager
def request_scope(payload):
    token = _SCOPE.set(payload)
    try:
        yield
    finally:
        _SCOPE.reset(token)


def cutoff():
    value = _SCOPE.get().get("as_of_date")
    if value is None:
        return None
    date = pd.Timestamp(value)
    if pd.isna(date) or date.tzinfo is not None:
        raise ValueError("as_of_date must be an unambiguous date without timezone")
    return date.normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)


@lru_cache(maxsize=4)
def _read_versioned(path, version, columns):
    return pd.read_parquet(path, columns=list(columns) if columns else None)


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    return _read_versioned(str(path), file_version(path), tuple(columns or ())).copy(deep=False)


def _standardize_ohlcv(df: pd.DataFrame, asset_class: str = "equity") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Asset_Class",
            ]
        )
    rename = {c: str(c).strip().title() for c in df.columns}
    out = df.rename(columns=rename).copy(deep=False)
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Asset_Class",
            ]
        )
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
    out[["Open", "High", "Low", "Close", "Volume"]] = out[
        ["Open", "High", "Low", "Close", "Volume"]
    ].apply(pd.to_numeric, errors="coerce")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    if "Asset_Class" not in out.columns:
        out["Asset_Class"] = asset_class
    out["Asset_Class"] = out["Asset_Class"].fillna(asset_class).astype(str).str.lower()
    if out[["Ticker", "Date"]].isna().any().any():
        raise ValueError("Missing symbol or date in observed market data")
    return out[
        ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume", "Asset_Class"]
    ]


@lru_cache(maxsize=8)
def _symbol_counts(version, frequency, include_cross_asset):
    if pl is None:
        raise ValueError("polars is required for request-scoped market access")
    primary = MARKET_UNIVERSE_HOURLY if frequency == "hourly" else MARKET_UNIVERSE
    if not primary.exists():
        raise ValueError(f"Required observed market source missing: {primary}")
    paths = (
        [MARKET_UNIVERSE_HOURLY]
        if frequency == "hourly"
        else [
            MARKET_UNIVERSE,
            *(
                [EQUITY_DAILY, FX_DAILY, CRYPTO_DAILY, FUTURES_DAILY]
                if include_cross_asset
                else []
            ),
        ]
    )
    counts = {}
    for path in paths:
        if not path.exists():
            continue
        frame = pl.scan_parquet(path).group_by("Ticker").len().collect()
        for ticker, count in frame.iter_rows():
            counts[normalize_symbol(ticker)] = max(
                counts.get(normalize_symbol(ticker), 0), count
            )
    return tuple(sorted(counts, key=lambda x: (-counts[x], x)))


def _available_symbols_full(frequency="daily", include_cross_asset=True):
    return _symbol_counts(
        source_version(), normalize_frequency(frequency), include_cross_asset
    )


def available_symbols(
    limit: int | None = None, frequency: str = "daily", include_cross_asset: bool = True
) -> list[str]:
    out = list(
        _available_symbols_full(normalize_frequency(frequency), include_cross_asset)
    )
    return out[:limit] if limit else out


class UnknownSymbolsError(ValueError):
    pass


def parse_symbols(
    payload: dict | None, default_limit: int = 80, max_symbols: int = 5000
) -> list[str]:
    payload = payload or {}
    raw = next(
        (
            payload[k]
            for k in ("tickers", "symbols", "assets", "universe")
            if k in payload and payload[k] is not None
        ),
        None,
    )
    frequency = normalize_frequency(payload.get("frequency", "daily"))
    universe = available_symbols(frequency=frequency)
    if raw is None or isinstance(raw, str) and raw.lower().strip() == "default":
        requested = universe[:default_limit]
    elif isinstance(raw, str) and raw.strip().lower() in {
        "sp500",
        "s&p 500",
        "russell1000",
        "russell2000",
        "msci world",
    }:
        raise ValueError(
            "Named index constituent histories are unavailable; provide exact observed symbols"
        )
    elif isinstance(raw, str) and raw.strip().lower() in {
        "all",
        "full",
        "master",
        "master_universe",
        "market_universe",
        "whole",
    }:
        requested = universe
    elif isinstance(raw, str):
        requested = [
            normalize_symbol(x) for x in raw.replace(";", ",").split(",") if x.strip()
        ]
    elif isinstance(raw, (list, tuple)):
        requested = [normalize_symbol(x) for x in raw]
    else:
        raise ValueError("tickers must be a list or comma-separated symbols")
    requested = list(dict.fromkeys(requested))
    missing = sorted(set(requested) - set(universe))
    if missing:
        raise UnknownSymbolsError("Unknown symbols: " + ", ".join(missing))
    cap = int(payload.get("max_symbols", max_symbols))
    if not requested or len(requested) > min(cap, max_symbols):
        raise ValueError(f"Select between 1 and {min(cap, max_symbols)} symbols")
    return requested


@lru_cache(maxsize=8)
def _selected_ohlcv(symbols, frequency, version):
    if pl is None:
        raise ValueError("polars is required for filtered market access")
    primary = MARKET_UNIVERSE_HOURLY if frequency == "hourly" else MARKET_UNIVERSE
    if not primary.exists():
        raise ValueError(f"Required observed market source missing: {primary}")
    paths = (
        [(MARKET_UNIVERSE_HOURLY, "mixed")]
        if frequency == "hourly"
        else [
            (MARKET_UNIVERSE, "equity"),
            (EQUITY_DAILY, "equity"),
            (FX_DAILY, "fx"),
            (CRYPTO_DAILY, "crypto"),
            (FUTURES_DAILY, "futures"),
        ]
    )
    frames = []
    for path, kind in paths:
        if not path.exists():
            continue
        lazy = pl.scan_parquet(path)
        normalized = pl.col("Ticker").str.to_uppercase().str.replace_all(r"[.\-]", "_")
        raw = lazy.filter(normalized.is_in(list(symbols))).collect().to_pandas()
        frame = _standardize_ohlcv(raw, kind)
        if frame.duplicated(["Ticker", "Date"]).any():
            raise ValueError(f"Duplicate symbol/date in {path.name}")
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise ValueError("Requested observed prices are unavailable")
    # Canonical source takes precedence over master when both contain an asset;
    # this precedence is explicit, not a duplicate observation fallback.
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(["Ticker", "Date"], keep="last")
        .sort_values(["Ticker", "Date"])
    )


def ohlcv_for_symbols(symbols, lookback_days=None, frequency="daily"):
    freq = normalize_frequency(frequency)
    normalized = tuple(sorted(normalize_symbol(s) for s in symbols))
    out = _selected_ohlcv(
        normalized, "hourly" if freq == "hourly" else "daily", source_version()
    ).copy(deep=False)
    if cutoff() is not None:
        out = out.loc[out.Date <= cutoff()]
    if lookback_days:
        out = out.groupby("Ticker", group_keys=False).tail(int(lookback_days) + 1)
    return out


def _price_panel(symbols, lookback_days, frequency):
    raw = ohlcv_for_symbols(symbols, lookback_days=None, frequency=frequency)
    if raw.empty:
        raise ValueError("No observed price data for selected symbols and as_of_date")
    if raw.duplicated(["Ticker", "Date"]).any():
        raise ValueError("Duplicate symbol/date observations")
    if not np.isfinite(raw.Close).all() or (raw.Close <= 0).any():
        raise ValueError("Prices must be finite and positive")
    prices = raw.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    freq = normalize_frequency(frequency)
    if freq in {"weekly", "monthly"}:
        rule = "W-FRI" if freq == "weekly" else "ME"
        prices = prices.resample(rule).last()
        end = cutoff() if cutoff() is not None else raw.Date.max()
        prices = prices.loc[prices.index <= end]
    return prices.tail(lookback_rows(lookback_days, frequency) + 1)


def returns_matrix(symbols, lookback_days=504, frequency="daily", min_coverage=0.65):
    prices = _price_panel(symbols, lookback_days, frequency)
    # A missing observation remains missing on both sides of its return interval.
    return prices.pct_change(fill_method=None).iloc[1:]


def close_matrix(symbols, lookback_days=504, frequency="daily"):
    return _price_panel(symbols, lookback_days, frequency).iloc[1:]


def dollar_volume_matrix(symbols, lookback_days=504, frequency="daily"):
    raw = ohlcv_for_symbols(symbols, lookback_days=None, frequency=frequency).copy(deep=False)
    raw["DollarVolume"] = raw.Close * raw.Volume
    return (
        raw.pivot(index="Date", columns="Ticker", values="DollarVolume")
        .sort_index()
        .tail(lookback_rows(lookback_days, frequency))
    )


def load_fundamentals_metadata() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(
            columns=["ticker", "sector", "industry", "marketCap", "currency"]
        )
    names = pq.read_schema(MASTER_FUNDAMENTALS).names
    df = _read_parquet(MASTER_FUNDAMENTALS, [c for c in ["ticker", "sector", "industry", "marketCap", "currency", "exchange"] if c in names])
    if "ticker" not in df.columns:
        return pd.DataFrame(
            columns=["ticker", "sector", "industry", "marketCap", "currency"]
        )
    keep = [
        c
        for c in ["ticker", "sector", "industry", "marketCap", "currency", "exchange"]
        if c in df.columns
    ]
    out = df[keep].dropna(subset=["ticker"]).copy(deep=False)
    out["ticker"] = out["ticker"].map(normalize_symbol)
    return out.drop_duplicates("ticker", keep="last")


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
            mc = float(data.get("marketCap", np.nan))
            cap[ticker] = mc if mc > 0 else np.nan
        except (TypeError, ValueError):
            cap[ticker] = np.nan
    return sec, cap


def sector_map(symbols: Iterable[str]) -> dict[str, str]:
    sec, _ = _fundamentals_maps()
    normalized = [normalize_symbol(s) for s in symbols]
    return {s: str(sec.get(s, "Unknown")) for s in normalized}


def load_macro() -> pd.DataFrame:
    if not CATEGORY7_MACRO.exists():
        return pd.DataFrame(columns=["date"])
    df = _read_parquet(CATEGORY7_MACRO)
    date_col = (
        "date"
        if "date" in df.columns
        else ("Date" if "Date" in df.columns else df.columns[0])
    )
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    out = (
        df.rename(columns={date_col: "date"})
        .dropna(subset=["date"])
        .sort_values("date")
    )
    for col in out.columns:
        if col != "date":
            out[col] = pd.to_numeric(out[col], errors="coerce")
    # The archived slope column is sparse and partly weekend-only. This is the
    # same measured quantity, calculated from simultaneous observed daily yields.
    if {"dgs10", "dgs2"} <= set(out):
        out["yc_slope_10y_2y"] = out.dgs10 - out.dgs2
    if cutoff() is not None:
        out = out.loc[out.date <= cutoff()]
    return out


def load_factor_returns():
    ff = BACKEND_DATA / "factors_us/ff5_daily.parquet"
    mom = BACKEND_DATA / "factors_us/momentum_daily.parquet"
    if not ff.exists():
        raise ValueError("Observed FF5 factor returns unavailable")
    out = _read_parquet(ff).rename(columns={"mkt-rf": "mkt_rf"})
    if mom.exists():
        out = out.merge(
            _read_parquet(mom), on="date", how="left", validate="one_to_one"
        )
    out["date"] = pd.to_datetime(out.date)
    if cutoff() is not None:
        out = out.loc[out.date <= cutoff()]
    if out.date.duplicated().any():
        raise ValueError("Duplicate factor dates")
    return out.sort_values("date")
