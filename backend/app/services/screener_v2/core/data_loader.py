"""Screener V2 local data access.

Runtime feature calls are read-only. Fetchers under ``fetchers/`` are
append-only operator helpers for datasets that are not present locally.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .performance import (
    _path_version,
    cached_close_matrix,
    cached_fundamental_history,
    cached_returns_matrix,
    cached_volume_matrix,
    symbol_key,
)

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
FX_DAILY = BACKEND_DATA / "canonical" / "fx_daily.parquet"
FF5_DAILY = BACKEND_DATA / "factors_us" / "ff5_daily.csv"
MOM_DAILY = BACKEND_DATA / "factors_us" / "momentum_daily.csv"



AS_OF = ContextVar("screener_as_of", default=None)


@contextmanager
def as_of_context(value):
    date = pd.Timestamp(value) if value else None
    if date is not None and date.tzinfo is not None:
        raise ValueError("as_of_date must be an unzoned calendar date")
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
    out = df.rename(columns={c: str(c).strip().title() for c in df.columns})
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if not {"Ticker", "Date", "Close"}.issubset(out.columns):
        raise ValueError("Market data requires Ticker, Date and source Close columns")
    prices = ["Open", "High", "Low", "Close", "Volume"]
    for col in prices:
        if col not in out.columns:
            out[col] = np.nan
        elif not pd.api.types.is_float_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    if out["Date"].isna().any() or out["Ticker"].isna().any():
        raise ValueError("Market data contains missing/invalid dates or tickers")
    # Normalise each distinct ticker once, not every row.
    codes, uniques = pd.factorize(out["Ticker"])
    names = [normalize_symbol(x) for x in uniques]
    if "" in names:
        raise ValueError("Market data requires nonempty tickers")
    out["Ticker"] = pd.Index(names, dtype=object).take(codes)
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    distinct = sorted(set(names))  # aliases such as BRK.B and BRK-B share one rank
    position = {name: i for i, name in enumerate(distinct)}
    rank = np.array([position[name] for name in names], dtype=np.int64)
    order = np.lexsort((out["Date"].to_numpy(), rank[codes]))
    code_sorted, date_sorted = rank[codes][order], out["Date"].to_numpy()[order]
    same = np.zeros(len(out), dtype=bool)
    same[1:] = (code_sorted[1:] == code_sorted[:-1]) & (date_sorted[1:] == date_sorted[:-1])
    del code_sorted, date_sorted
    alias_count = int(same.sum())
    if alias_count:
        either = same.copy()
        either[:-1] |= same[1:]
        aliases = out.iloc[order[either]][columns].drop_duplicates()
        if aliases.duplicated(["Ticker", "Date"]).any():
            raise ValueError("Conflicting observed quotes after ticker normalization")
        order = order[~same]
    if len(order) != len(out) or not (order == np.arange(len(out))).all():
        out = out.iloc[order]  # one copy: sorted and de-duplicated together
    unsupported = out["Close"].notna() & ((out["Close"] <= 0) | ~np.isfinite(out["Close"]))
    source_integrity = {
        "identical_alias_rows_removed": alias_count,
        "unsupported_nonpositive_or_nonfinite_close_rows": int(unsupported.sum()),
        "unsupported_quote_symbols": sorted(out.loc[unsupported, "Ticker"].unique().tolist()),
        "policy": "Identical aliases deduplicated; conflicting aliases rejected. Nonpositive/nonfinite closes are unavailable for percentage-return analytics; no replacement prices.",
    }
    out.loc[unsupported, ["Open", "High", "Low", "Close", "Volume"]] = np.nan
    result = out[columns]
    result.attrs["source_integrity"] = source_integrity
    return result



@lru_cache(maxsize=1)
def _load_market_ohlcv_versioned(version: int) -> pd.DataFrame:
    if not MARKET_UNIVERSE.exists():
        raise FileNotFoundError(f"Required market dataset is missing: {MARKET_UNIVERSE}")
    source = MARKET_UNIVERSE
    cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    return _standardize_ohlcv(_read_parquet(source, cols))


def load_market_ohlcv() -> pd.DataFrame:
    if not MARKET_UNIVERSE.exists():
        raise FileNotFoundError(f"Required market dataset is missing: {MARKET_UNIVERSE}")
    return _load_market_ohlcv_versioned(_path_version(MARKET_UNIVERSE))


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    return _standardize_ohlcv(_read_parquet(MARKET_UNIVERSE_HOURLY))


@lru_cache(maxsize=1)
def _available_symbols_versioned(version: int, fundamentals_version: int) -> tuple[str, ...]:
    df = load_market_ohlcv()
    if df.empty:
        return ()
    fundamentals = load_fundamentals()
    if "ticker" not in fundamentals:
        raise FileNotFoundError("Equity universe requires a local fundamentals ticker inventory")
    equities = set(fundamentals.ticker)
    from .performance import _market_ohlcv_by_ticker
    by_ticker = _market_ohlcv_by_ticker(_path_version(MARKET_UNIVERSE))  # per-ticker views; no 10M-row hash join
    counts = pd.Series({t: int(f["Close"].count()) for t, f in sorted(by_ticker.items()) if t in equities}, dtype="int64").sort_values(ascending=False)
    return tuple(str(x) for x in counts[counts > 0].index)


def available_symbols() -> tuple[str, ...]:
    return _available_symbols_versioned(_path_version(MARKET_UNIVERSE), _path_version(MASTER_FUNDAMENTALS))


class UnknownSymbolsError(ValueError):
    """Explicit symbols must all belong to the local price universe."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Unknown or unsupported tickers (not in the local equity universe): {', '.join(missing)}")


def parse_symbols(payload: dict | None, default_limit: int = 500, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = next((payload[key] for key in ["tickers", "symbols", "universe"] if key in payload and payload[key] is not None), None)
    if isinstance(raw, dict):
        raise ValueError("Tickers must be a string or list, not an object")  # noqa: TRY004
    if isinstance(raw, (list, tuple)) and not raw:
        raise ValueError("Explicit ticker list is empty")
    if payload.get("universe_id"):
        if raw:
            raise ValueError("Use either universe_id or explicit universe/tickers")
        from .state import get_universe
        raw = get_universe(str(payload["universe_id"]))
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
    if label not in {"", "default", "all", "full", "master", "master_universe", "market_universe", "whole"} and len(requested) > cap:
        raise ValueError(f"Explicit universe exceeds max_symbols={cap}; raise the cap instead of dropping tickers")
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


def default_as_of(payload):
    """Default to the selected observed session calendar, not another asset's newer quote."""
    symbol = normalize_symbol(payload.get('calendar_ticker') or 'SPY')
    quotes = ohlcv_for_symbols([symbol])
    if quotes.empty:
        raise ValueError(f'Calendar instrument {symbol} has no observed dates')
    return str(quotes.Date.max().date())


def _session_matrix(frame, lookback_days):
    from .currency import CONFIG
    calendar = CONFIG.get().get('calendar_ticker')
    if calendar:
        dates = ohlcv_for_symbols([calendar]).Date.drop_duplicates().sort_values().tail(int(lookback_days))
        return frame.reindex(pd.DatetimeIndex(dates))
    return frame.tail(int(lookback_days))


def close_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols)
        return _session_matrix(raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index(), lookback_days)
    return _session_matrix(cached_close_matrix(symbol_key(symbols), int(lookback_days)).copy(), lookback_days)


def volume_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols)
        return _session_matrix(raw.pivot_table(index="Date", columns="Ticker", values="Volume", aggfunc="last").sort_index(), lookback_days)
    return _session_matrix(cached_volume_matrix(symbol_key(symbols), int(lookback_days)).copy(), lookback_days)


def returns_matrix(symbols: Iterable[str], lookback_days: int = 756, min_coverage: float = 0.55) -> pd.DataFrame:
    if AS_OF.get() is not None:
        prices = close_matrix(symbols, lookback_days)
        rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
        return rets.dropna(axis=1, thresh=max(20, int(len(rets) * min_coverage)))
    min_coverage_bps = int(max(0.0, min(1.0, float(min_coverage))) * 10000)
    return cached_returns_matrix(symbol_key(symbols), int(lookback_days), min_coverage_bps).copy()


@lru_cache(maxsize=1)
def _load_fundamentals_versioned(version: int) -> pd.DataFrame:
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


def load_fundamentals() -> pd.DataFrame:
    return _load_fundamentals_versioned(_path_version(MASTER_FUNDAMENTALS))


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
def _load_macro_versioned(version: int) -> pd.DataFrame:
    if CATEGORY7_MACRO.exists():
        df = pd.read_parquet(CATEGORY7_MACRO, engine="pyarrow")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.dropna(subset=["date"]).sort_values("date")
    return pd.DataFrame(columns=["date"])


def load_macro() -> pd.DataFrame:
    frame = _load_macro_versioned(_path_version(CATEGORY7_MACRO))
    cutoff = AS_OF.get()
    return frame.loc[frame.date <= cutoff].copy() if cutoff is not None else frame.copy()


@lru_cache(maxsize=1)
def _load_fx_versioned(version: int) -> pd.DataFrame:
    if not FX_DAILY.exists():
        raise FileNotFoundError(f"Required FX dataset is missing: {FX_DAILY}")
    return _standardize_ohlcv(_read_parquet(FX_DAILY))


def load_fx() -> pd.DataFrame:
    """Observed canonical FX quotes, bounded by the active research date."""
    frame = _load_fx_versioned(_path_version(FX_DAILY))
    cutoff = AS_OF.get()
    return frame.loc[frame.Date <= cutoff].copy() if cutoff is not None else frame.copy()


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
        "hourly_universe": {"exists": MARKET_UNIVERSE_HOURLY.exists(), "rows": len(load_hourly_ohlcv()) if MARKET_UNIVERSE_HOURLY.exists() else 0},
        "master_fundamentals": {"exists": MASTER_FUNDAMENTALS.exists(), "rows": len(load_fundamentals())},
        "macro": {"exists": CATEGORY7_MACRO.exists(), "rows": len(load_macro())},
        "fx_daily": {"exists": FX_DAILY.exists(), "rows": len(load_fx()) if FX_DAILY.exists() else 0},
        "ff5_daily": {"exists": FF5_DAILY.exists(), "rows": len(load_factor_returns())},
        "momentum_daily": {"exists": MOM_DAILY.exists()},
    }


UPLOADS_DIR = BACKEND_DATA / 'screener_v2' / 'uploads'


def store_universe_upload(raw: bytes, filename: str | None = None) -> dict:
    """Validate before writing, using a generated id rather than client paths."""
    import csv
    import json
    from io import StringIO
    from uuid import uuid4

    from .state import save_universe
    if len(raw) > 2_000_000:
        raise ValueError('Universe CSV exceeds 2 MB')
    try:
        reader = csv.reader(StringIO(raw.decode('utf-8-sig')), strict=True)
        symbols = [row[0].strip() for row in reader if row and row[0].strip() and row[0].strip().lower() not in {'ticker', 'tickers', 'symbol', 'symbols'}]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError('Invalid UTF-8 universe CSV') from exc
    if not symbols or len(symbols) > 5000:
        raise ValueError('Universe CSV must contain 1-5000 ticker rows')
    symbols = parse_symbols({'tickers': symbols, 'max_symbols': 5000})
    upload_id = uuid4().hex
    name = Path(filename or 'Uploaded universe').name[:200] or 'Uploaded universe'
    # Only a generated UUID can determine a write path.
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOADS_DIR / f'{upload_id}.json'
    with path.open('x') as handle:
        json.dump({'symbols': symbols, 'name': name}, handle, allow_nan=False)
    universe = save_universe(upload_id, name, symbols)
    return {'upload_id': upload_id, **universe}
