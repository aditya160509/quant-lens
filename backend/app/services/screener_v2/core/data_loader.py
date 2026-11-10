"""Screener V2 local data access.

Runtime feature calls are read-only. Fetchers under ``fetchers/`` are
append-only operator helpers for datasets that are not present locally.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import pyarrow.parquet as pq

from .performance import (
    _path_version,
    cached_close_matrix,
    cached_fundamental_history,
    cached_returns_matrix,
    cached_volume_matrix,
    frame_to_pandas,
    pivot_last,
    symbol_key,
)

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
MARKET_CACHE_DIR = BACKEND_DATA / "screener_v2" / "market_cache"



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
    scan = pl.scan_parquet(str(path))
    return (scan.select(columns) if columns else scan).collect().to_pandas()


OHLCV_COLUMNS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
NORMALIZED_TICKER = pl.col("Ticker").str.strip_chars().str.to_uppercase().str.replace_all(r"[.\-]", "_")
_CLOSE = pl.col("Close")
BAD_CLOSE = _CLOSE.is_not_null() & _CLOSE.is_not_nan() & ((_CLOSE <= 0) | _CLOSE.is_infinite())


def _standardize_frame(frame: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Sort by ticker and date, resolve aliases and blank unusable closes; expects typed Ticker, Date and Close."""
    if frame["Date"].null_count() or frame["Ticker"].null_count():
        raise ValueError("Market data contains missing/invalid dates or tickers")
    frame = frame.with_columns(NORMALIZED_TICKER).sort(["Ticker", "Date"], maintain_order=True)
    if frame["Ticker"].eq("").any():
        raise ValueError("Market data requires nonempty tickers")
    duplicated = frame.select(pl.struct("Ticker", "Date").is_duplicated().alias("dup"))["dup"]
    alias_count = 0
    if duplicated.any():
        # pandas treats NaN as equal to NaN, which is the rule identical aliases must follow.
        aliases = frame.filter(duplicated).to_pandas().drop_duplicates()
        if aliases.duplicated(["Ticker", "Date"]).any():
            raise ValueError("Conflicting observed quotes after ticker normalization")
        before = frame.height
        frame = frame.unique(["Ticker", "Date"], keep="first", maintain_order=True)
        alias_count = before - frame.height
    unsupported = frame.filter(BAD_CLOSE)
    if unsupported.height:
        frame = frame.with_columns(pl.when(BAD_CLOSE).then(None).otherwise(pl.col(c)).alias(c) for c in OHLCV_COLUMNS[2:] if c in frame.columns)
    return frame, {
        "identical_alias_rows_removed": alias_count,
        "unsupported_nonpositive_or_nonfinite_close_rows": unsupported.height,
        "unsupported_quote_symbols": sorted(unsupported["Ticker"].unique().to_list()),
        "policy": "Identical aliases deduplicated; conflicting aliases rejected. Nonpositive/nonfinite closes are unavailable for percentage-return analytics; no replacement prices.",
    }


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    out = df.rename(columns={c: str(c).strip().title() for c in df.columns})
    del df
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if not {"Ticker", "Date", "Close"}.issubset(out.columns):
        raise ValueError("Market data requires Ticker, Date and source Close columns")
    for col in OHLCV_COLUMNS[2:]:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float) if col in out.columns else np.nan
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    tickers = out["Ticker"].astype(object).where(out["Ticker"].isna(), out["Ticker"].astype(str))
    frame, integrity = _standardize_frame(pl.from_pandas(out[OHLCV_COLUMNS].assign(Ticker=tickers)))
    result = frame_to_pandas(frame)
    result.attrs["source_integrity"] = integrity
    return result


def _market_derived(name: str, version: int, compute):
    """A JSON result of a whole-file pass, kept on disk per market-file version so normal runs skip the pass."""
    path = MARKET_CACHE_DIR / f"{name}_{version}.json"
    if path.exists():
        return json.loads(path.read_text())
    value = compute()
    if version == _path_version(MARKET_UNIVERSE):  # never persist results for other sources
        MARKET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(value))
        os.replace(temporary, path)
        for stale in MARKET_CACHE_DIR.glob(f"{name}_*.json"):
            if stale != path:
                stale.unlink(missing_ok=True)
    return value


def load_market_frame() -> pl.LazyFrame:
    """A lazy scan of the raw market file; callers filter it, then standardize what they collect."""
    if not MARKET_UNIVERSE.exists():
        raise FileNotFoundError(f"Required market dataset is missing: {MARKET_UNIVERSE}")
    return pl.scan_parquet(str(MARKET_UNIVERSE)).select(OHLCV_COLUMNS)


def _flagged_market_tickers() -> list[str]:
    # One row group at a time with dictionary tickers: only integer keys outlive each group.
    source = pq.ParquetFile(MARKET_UNIVERSE, read_dictionary=["Ticker"])
    codes: dict[str, int] = {}
    keys = np.empty(source.metadata.num_rows, dtype="int64")
    flagged: set[str] = set()
    position = 0
    for group in range(source.num_row_groups):
        for batch in source.read_row_group(group, columns=["Ticker", "Date", "Close"], use_threads=False).to_batches():
            tickers, dates, close = batch.columns
            if tickers.null_count or dates.null_count:
                raise ValueError("Market data contains missing/invalid dates or tickers")
            names = [normalize_symbol(name) for name in tickers.dictionary.to_pylist()]
            mapped = np.array([codes.setdefault(name, len(codes)) for name in names], dtype="int64")
            rows = mapped[tickers.indices.to_numpy(zero_copy_only=False)]
            days = dates.cast("timestamp[s]", safe=False).to_numpy(zero_copy_only=False).astype("int64") // 86_400
            keys[position:position + len(rows)] = rows * 100_000 + days + 50_000
            position += len(rows)
            values = close.to_numpy(zero_copy_only=False)
            flagged.update(names[i] for i in np.unique(tickers.indices.to_numpy(zero_copy_only=False)[(values <= 0) | np.isinf(values)]))
    # Sorting integers costs a fraction of hashing 10M structs; a collision only flags a ticker for the exact check below.
    keys.sort()
    repeated = {int(code) for code in np.unique(keys[1:][keys[1:] == keys[:-1]] // 100_000)}
    del keys
    flagged.update(name for name, code in codes.items() if code in repeated or name == "")
    return sorted(flagged)


@lru_cache(maxsize=1)
def _market_anomalies_versioned(version: int) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Standardized rows of tickers with aliases or unusable closes, so the clean majority never needs a full load."""
    if not MARKET_UNIVERSE.exists():
        raise FileNotFoundError(f"Required market dataset is missing: {MARKET_UNIVERSE}")
    flagged = _market_derived("flagged_tickers", version, _flagged_market_tickers)
    scan = pl.scan_parquet(str(MARKET_UNIVERSE)).select(OHLCV_COLUMNS)
    return _standardize_frame(scan.filter(NORMALIZED_TICKER.is_in(flagged)).collect())


def market_source_integrity() -> dict[str, Any]:
    return _market_anomalies_versioned(_path_version(MARKET_UNIVERSE))[1]


def latest_market_date():
    return pd.Timestamp(load_market_frame().lazy().select(pl.col("Date").max()).collect().item())


def load_market_ohlcv() -> pd.DataFrame:
    frame, integrity = _standardize_frame(load_market_frame().lazy().collect())
    result = frame_to_pandas(frame)
    result.attrs["source_integrity"] = integrity
    return result


@lru_cache(maxsize=1)
def load_hourly_ohlcv() -> pd.DataFrame:
    return _standardize_ohlcv(_read_parquet(MARKET_UNIVERSE_HOURLY))


@lru_cache(maxsize=1)
def _available_symbols_versioned(version: int, fundamentals_version: int) -> tuple[str, ...]:
    fundamentals = load_fundamentals()
    if "ticker" not in fundamentals:
        raise FileNotFoundError("Equity universe requires a local fundamentals ticker inventory")
    equities = set(fundamentals.ticker)
    anomalies = _market_anomalies_versioned(_path_version(MARKET_UNIVERSE))[0]
    usable = (pl.col("Close").is_not_null() & pl.col("Close").is_not_nan()).sum().alias("n")
    counts = _market_derived("close_counts", version, lambda: dict(load_market_frame().lazy().group_by("Ticker").agg(usable).collect().iter_rows()))
    # Normalize after counting: a few thousand strings instead of ten million.
    by_name = pl.DataFrame({"Ticker": list(counts), "n": list(counts.values())}, schema={"Ticker": pl.String, "n": pl.Int64}).with_columns(NORMALIZED_TICKER)
    clean = by_name.filter(~pl.col("Ticker").is_in(anomalies["Ticker"].unique().to_list())).group_by("Ticker").agg(pl.col("n").sum())
    observed = pl.concat([clean, anomalies.group_by("Ticker").agg(usable).cast({"n": pl.Int64})])
    pairs = sorted((t, int(n)) for t, n in observed.iter_rows() if t in equities)
    counts = pd.Series(dict(pairs), dtype="int64").sort_values(ascending=False)
    return tuple(str(x) for x in counts[counts > 0].index)


def available_symbols() -> tuple[str, ...]:
    return _available_symbols_versioned(_path_version(MARKET_UNIVERSE), _path_version(MASTER_FUNDAMENTALS))


class UnknownSymbolsError(ValueError):
    """Explicit symbols must all belong to the local price universe."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Unknown or unsupported tickers (not in the local equity universe): {', '.join(missing)}")


_ALL_SYMBOLS: ContextVar[tuple[str, ...]] = ContextVar("screener_all_symbols", default=())


@lru_cache(maxsize=8)
def _liquidity_rank(version: int, as_of) -> dict[str, int]:
    from .currency import instrument_specs, usd_rates
    frame = load_market_frame()
    if as_of is not None:
        frame = frame.filter(pl.col("Date") <= pd.Timestamp(as_of))
    last = frame.select(pl.col("Date").max()).collect().item()
    if last is None:
        return {}
    # Per-ticker window: one stray late-dated ticker must not empty everyone else's window.
    rows = (frame.with_columns(NORMALIZED_TICKER.alias("_t"))
            .filter(pl.col("Date") >= pl.col("Date").max().over("_t") - pl.duration(days=45))
            .group_by("_t").agg((pl.col("Close") * pl.col("Volume")).median().alias("_dv")).collect())
    traded = dict(zip(rows["_t"].to_list(), rows["_dv"].to_list(), strict=True))
    known = [t for t in traded if t in set(_ALL_SYMBOLS.get())]
    specs = instrument_specs(known)
    currencies = sorted({specs[t].get("quote_currency") for t in known if specs[t].get("quote_currency")})
    # Ranking only: the latest FX within two weeks, so a holiday does not push a whole market last.
    dates = pd.date_range(pd.Timestamp(last) - pd.Timedelta(days=14), pd.Timestamp(last))
    rates = usd_rates(currencies, dates)
    latest = {c: rates[c].dropna().iloc[-1] for c in currencies if c in rates and rates[c].notna().any()}
    usd = {t: float(traded[t] or 0) * latest.get(specs[t].get("quote_currency"), 0.0) for t in known}
    return {t: i for i, t in enumerate(sorted(usd, key=lambda t: (-usd[t], t)))}


def _by_liquidity(universe: list[str]) -> list[str]:
    token = _ALL_SYMBOLS.set(tuple(universe))
    try:
        rank = _liquidity_rank(_path_version(MARKET_UNIVERSE), AS_OF.get())
    finally:
        _ALL_SYMBOLS.reset(token)
    return sorted(universe, key=lambda s: (rank.get(s, len(rank)), s))


def parse_symbols(payload: dict | None, default_limit: int = 500, max_symbols: int = 1000) -> list[str]:
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
        requested = _by_liquidity(universe)
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
    return _ohlcv_subset(tuple(sorted(normalized)), lookback_days=lookback_days, as_of=AS_OF.get())


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
        return frame.reindex(pd.DatetimeIndex(dates)).dropna(axis=1, how="all")
    # Per ticker, never the union calendar: another symbol's extra dates must not shorten this window.
    return frame.where(frame.notna().iloc[::-1].cumsum().iloc[::-1] <= int(lookback_days)).dropna(how="all")


def close_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols, int(lookback_days))
        return _session_matrix(pivot_last(raw, "Close"), lookback_days)
    return _session_matrix(cached_close_matrix(symbol_key(symbols), int(lookback_days)).copy(deep=False), lookback_days)


def volume_matrix(symbols: Iterable[str], lookback_days: int = 756) -> pd.DataFrame:
    if AS_OF.get() is not None:
        raw = ohlcv_for_symbols(symbols, int(lookback_days))
        return _session_matrix(pivot_last(raw, "Volume"), lookback_days)
    return _session_matrix(cached_volume_matrix(symbol_key(symbols), int(lookback_days)).copy(deep=False), lookback_days)


def returns_matrix(symbols: Iterable[str], lookback_days: int = 756, min_coverage: float = 0.55) -> pd.DataFrame:
    if AS_OF.get() is not None:
        prices = close_matrix(symbols, lookback_days)
        rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
        return rets.dropna(axis=1, thresh=max(20, int(len(rets) * min_coverage)))
    min_coverage_bps = int(max(0.0, min(1.0, float(min_coverage))) * 10000)
    return cached_returns_matrix(symbol_key(symbols), int(lookback_days), min_coverage_bps).copy(deep=False)


# Every fundamentals column a Screener module reads by name; the other 311 stay on disk.
FUNDAMENTAL_COLUMNS = (
    "ticker", "reportDate", "periodType", "sector", "industry", "currency", "marketCap", "trailingPE", "forwardPE",
    "priceToBook", "dividendYield", "debtToEquity", "returnOnEquity", "grossMargins", "currentRatio", "EBITDA", "EBIT",
    "Interest Expense", "Interest Expense Non Operating", "Diluted Average Shares", "Basic Average Shares", "Diluted EPS",
    "Basic EPS", "Net Income", "Pretax Income", "Operating Income", "Gross Profit", "Total Revenue", "Ordinary Shares Number",
    "Total Debt", "Common Stock Equity", "Total Equity Gross Minority Interest", "Minority Interest", "Stockholders Equity",
    "Retained Earnings", "Total Liabilities Net Minority Interest", "Long Term Debt", "Current Liabilities", "Total Assets",
    "Net PPE", "Current Assets", "Cash And Cash Equivalents", "Free Cash Flow", "Repurchase Of Capital Stock",
    "Issuance Of Capital Stock", "Cash Dividends Paid", "Common Stock Dividend Paid", "Dividend Paid Cfo",
    "Operating Cash Flow", "Inventory", "Tax Provision", "Preferred Stock", "Preferred Stock Equity",
)


@lru_cache(maxsize=1)
def _load_fundamentals_versioned(version: int) -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker"])
    columns = [c for c in FUNDAMENTAL_COLUMNS if c in pq.read_schema(MASTER_FUNDAMENTALS).names]
    return _normalize_fundamentals(pd.read_parquet(MASTER_FUNDAMENTALS, columns=columns, engine="pyarrow"))


def _normalize_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker"])
    out = df
    out["ticker"] = out["ticker"].map(normalize_symbol)
    if "reportDate" in out.columns:
        out["reportDate"] = pd.to_datetime(out["reportDate"], errors="coerce").astype("datetime64[us]")  # merge_asof needs one resolution
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


def fundamental_history(symbol: str, all_columns: bool = False) -> pd.DataFrame:
    if all_columns:  # the statements page lists every reported line, so it alone reads the whole file
        full = _normalize_fundamentals(pd.read_parquet(MASTER_FUNDAMENTALS, engine="pyarrow")) if MASTER_FUNDAMENTALS.exists() else pd.DataFrame(columns=["ticker"])
        frame = full[full.ticker.eq(normalize_symbol(symbol))].sort_values("reportDate")
    else:
        frame = cached_fundamental_history(normalize_symbol(symbol)).copy(deep=False)
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
    return frame.loc[frame.date <= cutoff] if cutoff is not None else frame.copy(deep=False)


@lru_cache(maxsize=1)
def _load_fx_versioned(version: int) -> pd.DataFrame:
    if not FX_DAILY.exists():
        raise FileNotFoundError(f"Required FX dataset is missing: {FX_DAILY}")
    return _standardize_ohlcv(_read_parquet(FX_DAILY))


def load_fx() -> pd.DataFrame:
    """Observed canonical FX quotes, bounded by the active research date."""
    frame = _load_fx_versioned(_path_version(FX_DAILY))
    cutoff = AS_OF.get()
    return frame.loc[frame.Date <= cutoff] if cutoff is not None else frame.copy(deep=False)


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
