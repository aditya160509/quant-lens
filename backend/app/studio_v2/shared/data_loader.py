from __future__ import annotations

"""
Single data engine for ALL services.

Reads from canonical parquet first, with validated CSV fallbacks for legacy
Fama-French files:
- backend/data/market_universe.parquet (4,158 tickers OHLCV)
- factors/data/processed/category7_macro_regime.parquet (21 macro series)
- backend/data/factors_us/ff5_daily.parquet (FF5 factor returns)
- backend/data/factors_us/momentum_daily.parquet (momentum factor)
- backend/data/fundamentals/master_fundamentals.parquet (market cap, float)

Exports: get_returns, get_ohlcv, get_all_tickers, get_macro,
         get_factor_returns, get_market_cap, get_float
"""

from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq


_ROOT = Path(__file__).resolve().parents[4]
UNIVERSE_PATH = _ROOT / "backend/data/market_universe.parquet"
CATEGORY7_PATH = _ROOT / "factors/data/processed/category7_macro_regime.parquet"
FF5_PATH = _ROOT / "backend/data/factors_us/ff5_daily.parquet"
MOM_PATH = _ROOT / "backend/data/factors_us/momentum_daily.parquet"
FUNDAMENTALS_PATH = _ROOT / "backend/data/fundamentals/master_fundamentals.parquet"
CANONICAL_PATH = _ROOT / "backend/data/canonical"
FF3_PATH = _ROOT / "backend/data/factors_us/ff3_daily.parquet"

_EMPTY_OHLCV_COLUMNS = [
    "date", "open", "high", "low", "close", "volume", "adjusted_close", "dollar_volume"
]

_UNIVERSE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]
_FUNDAMENTAL_COLS = frozenset({"floatshares", "sharesfloat", "ordinary shares number", "ordinarysharesnumber", "share issued", "shareissued"})
_CANONICAL_ASSET_ALIASES = {
    "crypto": "crypto",
    "equity": "equity",
    "etf": "equity",
    "future": "futures",
    "futures": "futures",
    "commodity": "futures",
    "fx": "fx",
}
_SCAN_LOCK = Lock()
_SCAN_METRICS: dict[str, dict[str, int]] = {}


def _frame_bytes(frame: pd.DataFrame) -> int:
    return int(frame.memory_usage(index=True, deep=False).sum()) if not frame.empty else 0


def _record_scan(
    dataset: str,
    *,
    rows: int,
    bytes_scanned: int,
    predicate_pushdown: bool,
) -> None:
    """Record aggregate scan cost without retaining symbols or date filters."""
    with _SCAN_LOCK:
        row = _SCAN_METRICS.setdefault(
            str(dataset),
            {
                "queries": 0,
                "rows_scanned": 0,
                "bytes_scanned": 0,
                "predicate_pushdown_queries": 0,
                "fallback_queries": 0,
            },
        )
        row["queries"] += 1
        row["rows_scanned"] += max(0, int(rows))
        row["bytes_scanned"] += max(0, int(bytes_scanned))
        row[
            "predicate_pushdown_queries" if predicate_pushdown else "fallback_queries"
        ] += 1


def clear_data_access_metrics() -> None:
    with _SCAN_LOCK:
        _SCAN_METRICS.clear()


def _as_timestamp(value: object) -> Optional[pd.Timestamp]:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(parsed) else pd.Timestamp(parsed).tz_convert(None)


def _normalize_dates(values: pd.Series) -> pd.Series:
    """Normalize naive or timezone-aware values to UTC-naive timestamps."""
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_convert(None)


def _normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Return stable, unique ticker/session bars suitable for a wide pivot."""
    if frame.empty:
        return frame
    out = frame.copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out["date"] = _normalize_dates(out["date"])
    out = out.dropna(subset=["ticker", "date"])
    out = out.loc[out["ticker"].ne("")]
    return (
        out.sort_values(["ticker", "date"], kind="mergesort")
        .drop_duplicates(["ticker", "date"], keep="last")
        .reset_index(drop=True)
    )


def _date_filter(df: pd.DataFrame, start: object = None, end: object = None) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df.iloc[0:0].copy()
    start_ts, end_ts = _as_timestamp(start), _as_timestamp(end)
    if start_ts is None and end_ts is None:
        return df
    out = df.copy()
    out["date"] = _normalize_dates(out["date"])
    if start_ts is not None:
        out = out.loc[out["date"] >= start_ts]
    if end_ts is not None:
        out = out.loc[out["date"] <= end_ts]
    return out


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required Studio v2 parquet file not found: {path}")


@lru_cache(maxsize=2)
def _load_universe() -> pd.DataFrame:
    _require_file(UNIVERSE_PATH)
    try:
        frame = pd.read_parquet(UNIVERSE_PATH, columns=_UNIVERSE_COLUMNS)
    except Exception:
        # Some historical parquet snapshots use title-case field names.  A
        # schema-projection failure is safe to retry once without projection;
        # normalized columns are then selected after case normalization.
        frame = pd.read_parquet(UNIVERSE_PATH)
    if frame.empty:
        return pd.DataFrame(columns=_UNIVERSE_COLUMNS)
    rename = {c: c.lower() for c in frame.columns}
    frame = frame.rename(columns=rename)
    required = _UNIVERSE_COLUMNS
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"Market universe is missing required columns: {missing}")
    frame = _normalize_bars(frame)
    frame["ticker"] = pd.Categorical(frame["ticker"])
    return frame


@lru_cache(maxsize=256)
def _load_universe_subset(
    tickers: tuple[str, ...],
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
) -> pd.DataFrame:
    """Predicate-push a bounded market-universe request into PyArrow."""
    _require_file(UNIVERSE_PATH)
    requested = tuple(sorted({str(ticker).upper() for ticker in tickers if ticker}))
    if not requested:
        return pd.DataFrame(columns=_UNIVERSE_COLUMNS)
    filters: list[tuple[str, str, object]] = [("Ticker", "in", list(requested))]
    if start_iso:
        filters.append(("Date", ">=", pd.Timestamp(start_iso)))
    if end_iso:
        filters.append(("Date", "<=", pd.Timestamp(end_iso)))
    try:
        table = pq.read_table(
            UNIVERSE_PATH,
            columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"],
            filters=filters,
            use_threads=True,
        )
        _record_scan(
            "market_universe",
            rows=table.num_rows,
            bytes_scanned=table.nbytes,
            predicate_pushdown=True,
        )
        frame = table.to_pandas()
        frame.columns = _UNIVERSE_COLUMNS
    except Exception:
        # Compatibility fallback for alternate historical parquet schemas.
        frame = _load_universe()
        _record_scan(
            "market_universe",
            rows=len(frame),
            bytes_scanned=_frame_bytes(frame),
            predicate_pushdown=False,
        )
        frame = frame.loc[frame["ticker"].isin(requested), _UNIVERSE_COLUMNS]
        frame = _date_filter(frame, start_iso, end_iso)
    if frame.empty:
        return pd.DataFrame(columns=_UNIVERSE_COLUMNS)
    frame = _normalize_bars(frame)
    frame["ticker"] = frame["ticker"].astype("category")
    return frame


@lru_cache(maxsize=1)
def get_trading_sessions() -> pd.DatetimeIndex:
    """Return unique master-universe sessions without materializing OHLCV."""
    _require_file(UNIVERSE_PATH)
    try:
        values = pc.unique(pq.read_table(UNIVERSE_PATH, columns=["Date"])["Date"])
        return pd.DatetimeIndex(values.to_pandas().dropna()).tz_localize(None).sort_values()
    except Exception:
        return pd.DatetimeIndex(_load_universe()["date"].dropna().unique()).sort_values()


@lru_cache(maxsize=1)
def _load_macro() -> pd.DataFrame:
    _require_file(CATEGORY7_PATH)
    frame = pd.read_parquet(CATEGORY7_PATH)
    _record_scan(
        "category7_macro_regime",
        rows=len(frame),
        bytes_scanned=_frame_bytes(frame),
        predicate_pushdown=False,
    )
    frame = frame.rename(columns={c: c.lower() for c in frame.columns})
    if "date" not in frame.columns:
        raise ValueError("Macro parquet must contain a date column")
    frame["date"] = _normalize_dates(frame["date"])
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


@lru_cache(maxsize=1)
def _load_fundamentals() -> pd.DataFrame:
    _require_file(FUNDAMENTALS_PATH)
    frame = pd.read_parquet(FUNDAMENTALS_PATH)
    _record_scan(
        "master_fundamentals",
        rows=len(frame),
        bytes_scanned=_frame_bytes(frame),
        predicate_pushdown=False,
    )
    frame = frame.rename(columns={c: c.lower() for c in frame.columns})
    ticker_col = next((c for c in ("ticker", "symbol") if c in frame.columns), None)
    date_col = next((c for c in ("reportdate", "date", "asofdate") if c in frame.columns), None)
    if ticker_col is None or date_col is None:
        raise ValueError("Fundamentals parquet must contain ticker and reportDate columns")
    frame = frame.rename(columns={ticker_col: "ticker", date_col: "date"})
    frame["ticker"] = frame["ticker"].astype(str).str.upper().astype("category")
    frame["date"] = _normalize_dates(frame["date"])
    return frame.dropna(subset=["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)


@lru_cache(maxsize=16)
def _load_factor_file(path: Path) -> pd.DataFrame:
    candidates = [path]
    if path.suffix == ".parquet":
        candidates.append(path.with_suffix(".csv"))
    actual = next((candidate for candidate in candidates if candidate.exists()), None)
    if actual is None:
        raise FileNotFoundError(f"Required Studio v2 factor file not found; checked: {candidates}")
    is_parquet = actual.suffix == ".parquet"
    if is_parquet:
        frame = pd.read_parquet(actual)
        _record_scan(
            f"factor:{actual.stem}",
            rows=len(frame),
            bytes_scanned=_frame_bytes(frame),
            predicate_pushdown=False,
        )
    else:
        # Kenneth French CSV downloads contain a variable-length prose
        # preamble. Find the first factor header instead of coupling parsing
        # to a hard-coded row count that differs by dataset.
        with actual.open("r", encoding="utf-8-sig", errors="replace") as handle:
            header_row = next(
                (
                    index
                    for index, line in enumerate(handle)
                    if line.lstrip().startswith(",")
                    and any(token in line.lower() for token in ("mkt-rf", "mom", "smb", "hml"))
                ),
                None,
            )
        if header_row is None:
            raise ValueError(f"Factor CSV has no recognizable header: {actual}")
        frame = pd.read_csv(actual, skiprows=header_row)
    if frame.empty:
        return frame
    frame = frame.rename(columns={c: c.lower() for c in frame.columns})
    date_col = next((c for c in ("date", "datetime", "timestamp", "unnamed: 0") if c in frame.columns), None)
    if date_col is not None:
        frame = frame.rename(columns={date_col: "date"})
        if is_parquet and pd.api.types.is_datetime64_any_dtype(frame["date"]):
            parsed = pd.to_datetime(frame["date"], errors="coerce", utc=True)
        else:
            raw_dates = frame["date"].astype(str).str.strip()
            compact = raw_dates.str.fullmatch(r"\d{8}")
            parsed = pd.to_datetime(raw_dates.where(~compact), errors="coerce", utc=True)
            parsed.loc[compact] = pd.to_datetime(
                raw_dates.loc[compact], format="%Y%m%d", errors="coerce", utc=True
            )
        frame["date"] = parsed.dt.tz_convert(None)
        frame = frame.dropna(subset=["date"]).sort_values("date").set_index("date")
    numeric = (
        frame
        if is_parquet and all(pd.api.types.is_numeric_dtype(dtype) for dtype in frame.dtypes)
        else frame.apply(pd.to_numeric, errors="coerce")
    )
    numeric = numeric.mask(numeric.isin((-99.99, -999.0)))
    numeric = numeric.dropna(axis=1, how="all")
    # Kenneth French CSV library files are always expressed in percent. A
    # magnitude heuristic fails on quiet samples whose largest value is <= 1.
    if not is_parquet and not numeric.empty:
        numeric = numeric / 100.0
    frame = numeric
    return frame


@lru_cache(maxsize=8)
def _load_canonical(asset_class: str) -> pd.DataFrame:
    normalized = _CANONICAL_ASSET_ALIASES.get(str(asset_class).lower().strip())
    if normalized is None:
        supported = ", ".join(sorted(_CANONICAL_ASSET_ALIASES))
        raise ValueError(
            f"Unsupported asset class '{asset_class}'. Supported asset classes: {supported}"
        )
    path = CANONICAL_PATH / f"{normalized}_daily.parquet"
    _require_file(path)
    frame = pd.read_parquet(path)
    _record_scan(
        f"canonical:{normalized}",
        rows=len(frame),
        bytes_scanned=_frame_bytes(frame),
        predicate_pushdown=False,
    )
    frame = frame.rename(columns={column: str(column).lower() for column in frame.columns})
    required = {"ticker", "date", "close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Canonical {normalized} parquet is missing required columns: {missing}")
    return _normalize_bars(frame)


def get_returns(tickers: List[str], start: object = None, end: object = None,
                asset_class: str = "equity") -> pd.DataFrame:
    """Return a date-indexed wide matrix of adjusted-close daily returns."""
    requested = list(dict.fromkeys(str(t).upper().strip() for t in (tickers or []) if str(t).strip()))
    if not requested:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"))
    asset_class = str(asset_class or "equity").lower()
    if asset_class in {"equity", "etf"}:
        start_ts, end_ts = _as_timestamp(start), _as_timestamp(end)
        frame = _load_universe_subset(
            tuple(requested),
            start_ts.isoformat() if start_ts is not None else None,
            end_ts.isoformat() if end_ts is not None else None,
        )[["date", "ticker", "close"]].copy()
    else:
        source = _load_canonical(asset_class)
        frame = source.loc[source["ticker"].isin(requested), ["date", "ticker", "close"]]
        frame = _date_filter(frame, start, end)
    if frame.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"), columns=requested, dtype=float)
    frame = frame.sort_values(["ticker", "date"])
    frame["adjusted_close"] = frame["close"].where(np.isfinite(frame["close"]))
    close_values = pd.to_numeric(frame["adjusted_close"], errors="coerce").to_numpy(dtype=float)
    ticker_codes = frame["ticker"].cat.codes.to_numpy() if isinstance(frame["ticker"].dtype, pd.CategoricalDtype) else frame["ticker"].to_numpy()
    previous = np.full(close_values.shape, np.nan, dtype=float)
    if len(close_values) > 1:
        same_ticker = ticker_codes[1:] == ticker_codes[:-1]
        previous[1:] = np.where(same_ticker, close_values[:-1], np.nan)
    frame["return"] = np.divide(close_values, previous, out=np.full_like(close_values, np.nan), where=np.isfinite(previous) & (previous != 0)) - 1.0
    frame["return"] = frame["return"].replace([np.inf, -np.inf], np.nan)
    result = frame.pivot(index="date", columns="ticker", values="return").sort_index()
    result = result.reindex(columns=requested)
    result = result.dropna(axis=1, how="all")
    result.index.name = "date"
    return result


@lru_cache(maxsize=512)
def _load_ticker(symbol: str) -> pd.DataFrame:
    return _load_universe_subset((symbol,)).copy()


def _normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=_EMPTY_OHLCV_COLUMNS)
    out = frame.copy()
    close_num = pd.to_numeric(out["close"], errors="coerce")
    out["adjusted_close"] = close_num
    out["dollar_volume"] = close_num * pd.to_numeric(out["volume"], errors="coerce")
    return out[_EMPTY_OHLCV_COLUMNS].sort_values("date").reset_index(drop=True)


def get_ohlcv_batch(tickers: Sequence[str], start: object = None, end: object = None) -> Dict[str, pd.DataFrame]:
    """Load all requested tickers from the cached universe in one parquet read."""
    requested = {str(t).upper().strip() for t in (tickers or []) if str(t).strip()}
    if not requested:
        return {}
    start_ts, end_ts = _as_timestamp(start), _as_timestamp(end)
    frame = _load_universe_subset(
        tuple(requested),
        start_ts.isoformat() if start_ts is not None else None,
        end_ts.isoformat() if end_ts is not None else None,
    )
    if frame.empty:
        return {}
    grouped = {str(symbol): _normalize_ohlcv(group) for symbol, group in frame.groupby("ticker", sort=True, observed=True)}
    return {k: v for k, v in grouped.items() if not v.empty}


def get_ohlcv(ticker: str, start: object = None, end: object = None) -> pd.DataFrame:
    """Return normalized OHLCV rows for one ticker.

    The supplied market-universe ``close`` field is the platform's adjusted
    close proxy because the source parquet has no separate adjusted-close
    column.  Consumers should not treat it as a split-adjustment guarantee.
    """
    symbol = str(ticker).upper().strip()
    frame = _date_filter(_load_ticker(symbol), start, end)
    if frame.empty:
        return pd.DataFrame(columns=_EMPTY_OHLCV_COLUMNS)
    return _normalize_ohlcv(frame)


@lru_cache(maxsize=1)
def _all_tickers_tuple() -> tuple[str, ...]:
    _require_file(UNIVERSE_PATH)
    try:
        values = pc.unique(pq.read_table(UNIVERSE_PATH, columns=["Ticker"])["Ticker"])
        return tuple(sorted(str(value).upper() for value in values.to_pylist() if value))
    except Exception:
        return tuple(sorted(_load_universe()["ticker"].dropna().astype(str).str.upper().unique().tolist()))


def get_all_tickers() -> List[str]:
    """Return unique universe symbols in stable sorted order."""
    return list(_all_tickers_tuple())


def get_data_access_metrics() -> dict[str, Any]:
    """Return aggregate Parquet scan and cache telemetry for operators."""
    cache_functions = {
        "universe_full": _load_universe,
        "universe_subset": _load_universe_subset,
        "ticker": _load_ticker,
        "trading_sessions": get_trading_sessions,
        "macro": _load_macro,
        "fundamentals": _load_fundamentals,
        "factor_file": _load_factor_file,
        "canonical_asset": _load_canonical,
        "all_tickers": _all_tickers_tuple,
    }
    caches: dict[str, dict[str, Any]] = {}
    total_hits = 0
    total_misses = 0
    for name, function in cache_functions.items():
        info = function.cache_info()
        total_hits += int(info.hits)
        total_misses += int(info.misses)
        caches[name] = {
            "hits": int(info.hits),
            "misses": int(info.misses),
            "max_size": info.maxsize,
            "current_size": int(info.currsize),
            "hit_rate": (
                float(info.hits / (info.hits + info.misses))
                if info.hits + info.misses
                else 0.0
            ),
        }
    with _SCAN_LOCK:
        scans = {name: dict(values) for name, values in sorted(_SCAN_METRICS.items())}
    total_queries = sum(row["queries"] for row in scans.values())
    pushed_queries = sum(row["predicate_pushdown_queries"] for row in scans.values())
    return {
        "cache": {
            "hits": total_hits,
            "misses": total_misses,
            "hit_rate": (
                float(total_hits / (total_hits + total_misses))
                if total_hits + total_misses
                else 0.0
            ),
            "functions": caches,
        },
        "scans": {
            "queries": total_queries,
            "rows_scanned": sum(row["rows_scanned"] for row in scans.values()),
            "bytes_scanned": sum(row["bytes_scanned"] for row in scans.values()),
            "predicate_pushdown_rate": (
                float(pushed_queries / total_queries) if total_queries else 0.0
            ),
            "datasets": scans,
        },
    }


def get_macro(series_name: str, start: object = None, end: object = None) -> pd.Series:
    """Return a date-indexed macro series, preserving NaNs for missing observations."""
    macro = _date_filter(_load_macro(), start, end)
    name = str(series_name).lower().strip()
    columns = {str(c).lower(): c for c in macro.columns}
    actual = columns.get(name)
    if actual is None:
        return pd.Series(dtype=float, name=series_name)
    return macro.set_index("date")[actual].rename(series_name).sort_index()


@lru_cache(maxsize=3)
def _load_multi_factor_model(key: str) -> pd.DataFrame:
    candidates = {
        "global_3f": sorted((_ROOT / "backend/data/factors_global").glob("Developed_*3*.parquet")),
        "global_5f": sorted((_ROOT / "backend/data/factors_global").glob("Developed_*5*.parquet")),
        "aqr": sorted((_ROOT / "factors/data/processed/aqr_parquet").glob("*.parquet")),
    }[key]
    if not candidates:
        raise FileNotFoundError(f"No factor files found for model '{key}'")
    combined = pd.concat([_load_factor_file(path) for path in candidates], axis=1)
    return combined.loc[:, ~combined.columns.duplicated()].sort_index()


def get_factor_returns(model: str = "ff5") -> pd.DataFrame:
    """Load a supported factor return file without reaching out to external APIs."""
    key = str(model or "ff5").lower().strip()
    if key in {"ff5", "fama_french_5", "fama-french-5"}:
        return _load_factor_file(FF5_PATH)
    if key in {"momentum", "mom"}:
        return _load_factor_file(MOM_PATH)
    if key == "ff3":
        return _load_factor_file(FF3_PATH)
    if key in {"global_3f", "global_5f", "aqr"}:
        return _load_multi_factor_model(key)
    raise ValueError(f"Unsupported factor model '{model}'. Supported models: ff3, ff5, momentum, aqr, global_3f, global_5f")


def get_market_cap(ticker: str, date: object) -> float:
    """Return the latest market cap reported on or before ``date``."""
    frame = _load_fundamentals()
    symbol = str(ticker).upper().strip()
    target = _as_timestamp(date)
    if target is None:
        return float("nan")
    rows = frame.loc[(frame["ticker"] == symbol) & (frame["date"] <= target)]
    if rows.empty or "marketcap" not in rows.columns:
        return float("nan")
    value = pd.to_numeric(rows.iloc[-1]["marketcap"], errors="coerce")
    return float(value) if pd.notna(value) and np.isfinite(value) else float("nan")


def get_float(ticker: str) -> float:
    """Return the most recent reported float-like share count."""
    frame = _load_fundamentals()
    symbol = str(ticker).upper().strip()
    rows = frame.loc[frame["ticker"] == symbol]
    if rows.empty:
        return float("nan")
    for column in _FUNDAMENTAL_COLS:
        if column in rows.columns:
            values = pd.to_numeric(rows[column], errors="coerce").dropna()
            if not values.empty:
                value = values.iloc[-1]
                return float(value) if np.isfinite(value) else float("nan")
    return float("nan")


def get_metadata(tickers: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Return latest fundamentals metadata used by universe and robustness filters."""
    frame = _load_fundamentals()
    requested = {str(t).upper().strip() for t in (tickers or []) if str(t).strip()}
    if requested:
        frame = frame.loc[frame["ticker"].isin(requested)]
    if frame.empty:
        return frame.copy()
    return frame.sort_values("date").groupby("ticker", as_index=False, observed=True).tail(1).reset_index(drop=True)


def get_sector_map(tickers: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """Return ticker-to-sector metadata, excluding missing or non-string labels."""
    frame = get_metadata(tickers)
    column = next((c for c in ("gics_sector", "sector") if c in frame.columns), None)
    if column is None:
        return {}
    return dict(zip(frame["ticker"].astype(str).str.upper(), frame[column].astype(str)))


def get_exchange_map(tickers: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """Return ticker-to-exchange metadata, excluding missing labels."""
    frame = get_metadata(tickers)
    column = next((c for c in ("exchange", "exchange_code", "market") if c in frame.columns), None)
    if column is None:
        return {}
    return dict(zip(frame["ticker"].astype(str).str.upper(), frame[column].astype(str)))
