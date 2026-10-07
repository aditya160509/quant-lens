"""Strict, versioned, request-scoped access to observed local prices and macro data."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend/data"
FACTORS_DATA = ROOT / "factors/data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed/category7_macro_regime.parquet"
_REQUEST = ContextVar("volatility_v2_request", default={})
COLUMNS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]


class UnknownSymbolsError(ValueError):
    """Requested identifiers do not exist in the observed price universe."""


@contextmanager
def request_scope(payload):
    token = _REQUEST.set(payload)
    try:
        yield
    finally:
        _REQUEST.reset(token)


def request_payload():
    return _REQUEST.get()


def file_version(path):
    if not path.is_file():
        raise ValueError(f"Required data file is missing: {path}")
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


def source_version():
    return tuple(
        file_version(p)
        for p in (
            MARKET_UNIVERSE,
            CATEGORY7_MACRO,
            BACKEND_DATA / "canonical/fx_daily.parquet",
        )
        if p.is_file()
    )


def cutoff():
    raw = request_payload().get("as_of_date") or request_payload().get("end_date")
    if raw is None:
        return None
    try:
        date = pd.Timestamp(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("as_of_date must be a valid date") from exc
    if pd.isna(date):
        raise ValueError("as_of_date must be a valid date")
    return date.tz_localize(None) if date.tzinfo is not None else date


@lru_cache(maxsize=2)
def _symbols(version):
    return tuple(
        sorted(
            pd.read_parquet(version[0], columns=["Ticker"])
            .Ticker.dropna()
            .astype(str)
            .unique()
        )
    )


def symbol_directory():
    return _symbols(file_version(MARKET_UNIVERSE))


def resolve_symbols(symbols):
    available = set(symbol_directory())
    resolved, unknown = [], []
    for raw in symbols:
        value = str(raw).strip().upper()
        # Storage aliases are accepted only when the exact requested identifier is absent.
        candidate = (
            value if value in available else value.replace("-", "_").replace(".", "_")
        )
        if candidate not in available:
            unknown.append(value)
        elif candidate not in resolved:
            resolved.append(candidate)
    if unknown:
        raise UnknownSymbolsError(
            "Unknown or unavailable symbols: " + ", ".join(unknown)
        )
    if not resolved:
        raise ValueError("Explicit asset list must not be empty")
    return resolved


@lru_cache(maxsize=8)
def _prices(version, symbols, end):
    filters = [("Ticker", "in", list(symbols))] if symbols else []
    if end is not None:
        filters.append(("Date", "<=", pd.Timestamp(end)))
    data = pd.read_parquet(version[0], columns=COLUMNS, filters=filters or None)
    data["Date"] = pd.to_datetime(data["Date"], errors="raise")
    if data.duplicated(["Ticker", "Date"]).any():
        raise ValueError("Duplicate price observations for ticker/date")
    for col in COLUMNS[2:]:
        data[col] = pd.to_numeric(data[col], errors="raise")
    prices = data[["Open", "High", "Low", "Close"]]
    if data[["Ticker", "Date"]].isna().any().any() or not (prices.gt(0).all().all()):
        raise ValueError(
            "Prices require non-null identifiers, dates, and positive OHLC"
        )
    if (data.High < prices.max(axis=1)).any() or (data.Low > prices.min(axis=1)).any():
        raise ValueError("OHLC range is inconsistent")
    return data.sort_values(["Ticker", "Date"])


def load_market_ohlcv():
    end = cutoff()
    return _prices(
        file_version(MARKET_UNIVERSE), (), end.isoformat() if end is not None else None
    ).copy()


def ohlcv_for_symbols(symbols, lookback_days=None):
    symbols = resolve_symbols(symbols)
    end = cutoff()
    data = _prices(
        file_version(MARKET_UNIVERSE),
        tuple(sorted(symbols)),
        end.isoformat() if end is not None else None,
    ).copy()
    missing = sorted(set(symbols) - set(data.Ticker))
    if missing:
        raise ValueError(
            "No price observations at requested date for: " + ", ".join(missing)
        )
    if lookback_days is not None:
        if int(lookback_days) < 2:
            raise ValueError("lookback_days must be at least 2 trading observations")
        data = data.groupby("Ticker", sort=False).tail(int(lookback_days))
    return data


@lru_cache(maxsize=2)
def _macro(version):
    frame = pd.read_parquet(version[0])
    if "date" not in frame:
        raise ValueError("Macro data requires an explicit date column")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame.date.isna().any() or frame.date.duplicated().any():
        raise ValueError("Macro dates must be unique and non-null")
    return frame.sort_values("date")


def load_category7_macro():
    frame = _macro(file_version(CATEGORY7_MACRO)).copy()
    end = cutoff()
    return frame.loc[frame.date <= end].copy() if end is not None else frame
