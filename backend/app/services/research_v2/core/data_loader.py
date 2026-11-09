"""Research V2 local data access.

Runtime feature calls are read-only. Fetchers under ``fetchers/`` append data
that is absent locally. The master universe parquet is the primary daily OHLCV
source, matching the rest of the V2 modules.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import polars as pl
except Exception:  # pragma: no cover  # noqa: BLE001
    pl = None


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
RESEARCH_MARKET_UNIVERSE = ROOT / "research_exports" / "final_submission_package" / "SUBMISSION_MAIN" / "data_sources" / "parquet" / "market_universe.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
FF5_DAILY = BACKEND_DATA / "factors_us" / "ff5_daily.csv"
MOM_DAILY = BACKEND_DATA / "factors_us" / "momentum_daily.csv"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
PARQUET_CACHE = BACKEND_DATA / "parquet_cache"


def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    if pl is not None and columns:
        try:
            # Strings as categoricals and floats as float32 before pandas sees them: the full market
            # file otherwise peaks near 3 GB while loading (millions of Python ticker strings).
            lf = pl.scan_parquet(str(path)).select(columns)
            lf = lf.with_columns(pl.col(pl.Utf8).cast(pl.Categorical), pl.col(pl.Float64).cast(pl.Float32))
            return lf.collect().to_pandas()
        except Exception:  # noqa: BLE001, S110
            pass
    try:
        return pd.read_parquet(path, columns=columns, engine="pyarrow")
    except Exception:  # noqa: BLE001
        return pd.read_parquet(path, engine="pyarrow")


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    out = df.rename(columns={c: str(c).strip().title() for c in df.columns})
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
        # float32 halves the resident market file; 7 significant digits is ample for prices and volume.
        out[col] = pd.to_numeric(out[col], errors="coerce", downcast="float").astype("float32")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    tick = out["Ticker"].astype("category")
    out["Ticker"] = tick.cat.rename_categories([normalize_symbol(c) for c in tick.cat.categories]) if tick.cat.categories.map(normalize_symbol).is_unique else tick.map(normalize_symbol)
    clean = out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]].sort_values(["Ticker", "Date"])
    clean["Ticker"] = clean["Ticker"].astype("category")
    return clean


def _market_source() -> Path:
    return MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE


def load_market_ohlcv() -> pd.DataFrame:
    """Whole market file. Not cached and not used on job paths: prefer ``ohlcv_for_symbols``."""

    source = _market_source()
    cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    if pl is not None and source.exists():
        try:
            lf = pl.scan_parquet(str(source)).select(cols).drop_nulls(["Ticker", "Date", "Close"])
            tickers = lf.select(pl.col("Ticker").unique()).collect()["Ticker"].to_list()
            mapping = {t: normalize_symbol(t) for t in tickers}
            out = (
                lf.with_columns(pl.col("Ticker").replace_strict(mapping), pl.col(["Open", "High", "Low", "Close", "Volume"]).cast(pl.Float32))
                .filter(pl.col("Ticker") != "")
                .sort(["Ticker", "Date"])
                .with_columns(pl.col("Ticker").cast(pl.Categorical))
                .collect(engine="streaming")
                .to_pandas()
            )
            out["Ticker"] = out["Ticker"].astype("category")
            return out
        except Exception:  # noqa: BLE001, S110
            pass
    return _standardize_ohlcv(_read_parquet(source, cols))


@lru_cache(maxsize=1)
def _market_summary() -> tuple[tuple[str, ...], int]:
    """Small per-symbol close counts (symbols by coverage, total rows) without loading prices."""

    source = _market_source()
    if pl is not None and source.exists():
        try:
            raw = (
                pl.scan_parquet(str(source)).select(["Ticker", "Close", "Date"]).drop_nulls(["Ticker", "Date", "Close"])
                .group_by("Ticker").agg(pl.len().alias("n")).collect()
            )
            counts: dict[str, int] = {}
            for t, n in zip(raw["Ticker"].to_list(), raw["n"].to_list()):
                k = normalize_symbol(t)
                if k:
                    counts[k] = counts.get(k, 0) + int(n)
            order = sorted(counts, key=lambda k: (-counts[k], k))
            return tuple(order), int(sum(counts.values()))
        except Exception:  # noqa: BLE001, S110
            pass
    df = load_market_ohlcv()
    if df.empty:
        return (), 0
    counts = df.groupby("Ticker", observed=True)["Close"].count().sort_values(ascending=False)
    return tuple(str(x) for x in counts.index), len(df)


def available_symbols() -> tuple[str, ...]:
    return _market_summary()[0]


@lru_cache(maxsize=1)
def _raw_tickers() -> dict[str, tuple[str, ...]]:
    source = _market_source()
    raw = pl.scan_parquet(str(source)).select(pl.col("Ticker").unique()).collect()["Ticker"].to_list()
    out: dict[str, list[str]] = {}
    for t in raw:
        if t is not None:
            out.setdefault(normalize_symbol(t), []).append(t)
    return {k: tuple(v) for k, v in out.items()}


class UnknownSymbolsError(ValueError):
    """Raised when a researcher names tickers that are not in the local data."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Unknown tickers (not in local market data): {', '.join(missing[:25])}")

    def __reduce__(self):  # keeps the message intact when raised in a worker process
        return (type(self), (self.missing,))


# Named cross-sectional universes. Cross-sectional tests must not mix markets
# and currencies, so every named universe resolves to US common equities.
US_UNIVERSE_LABELS = {"", "default", "broad", "broad_market", "master", "master_universe", "us", "us_equities"}
GLOBAL_UNIVERSE_LABELS = {"all", "full", "whole", "global"}


@lru_cache(maxsize=1)
def us_equity_symbols() -> tuple[str, ...]:
    """US common equities: in the market file, no exchange suffix, with a sector."""

    sectors = static_sectors()
    return tuple(s for s in available_symbols() if "_" not in s and not s.startswith("^") and s in sectors.index)


def parse_symbols(payload: dict | None, default_limit: int = 500, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    from ..universes import has_controls, select_symbols

    explicit = payload.get("tickers") or payload.get("symbols")
    if has_controls(payload) and (explicit or str(payload.get("universe") or "").strip().lower() in US_UNIVERSE_LABELS | GLOBAL_UNIVERSE_LABELS | {""}):
        base = [normalize_symbol(x) for x in (explicit if isinstance(explicit, (list, tuple)) else re.split(r"[,;\s]+", str(explicit)) if explicit else []) if str(x).strip()] or None
        return select_symbols(payload, default_limit, max_symbols, base)
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("universe") or payload.get("asset_universe")
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or default_limit or max_symbols)
    cap = max(1, min(cap, max_symbols))
    label = str(raw or "").strip().lower() if not isinstance(raw, (list, tuple)) else "__list__"
    if raw is None or label in US_UNIVERSE_LABELS:
        return list(us_equity_symbols()[:cap])
    if label in GLOBAL_UNIVERSE_LABELS:
        return list(available_symbols()[:cap])
    if isinstance(raw, str):
        requested = [normalize_symbol(x) for x in re.split(r"[,;\s]+", raw) if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    existing = set(available_symbols())
    missing = [s for s in dict.fromkeys(requested) if s not in existing]
    if missing:
        raise UnknownSymbolsError(missing)
    return list(dict.fromkeys(requested))[:cap]


def ohlcv_for_symbols(symbols: Iterable[str], lookback_days: int | None = None) -> pd.DataFrame:
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    source = _market_source()
    out = None
    if pl is not None and source.exists():
        try:
            tmap = _raw_tickers()
            raw = [r for n in normalized for r in tmap.get(n, ())]
            cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
            lf = pl.scan_parquet(str(source)).select(cols).filter(pl.col("Ticker").is_in(raw)).drop_nulls(["Ticker", "Date", "Close"])
            if lookback_days:
                # Same cutoff as before: the latest date among the requested symbols minus 2x lookback.
                latest = lf.select(pl.col("Date").max()).collect().item()
                if latest is not None:
                    lf = lf.filter(pl.col("Date") >= pl.lit(latest) - pl.duration(days=int(lookback_days) * 2))
            out = lf.with_columns(pl.col(["Open", "High", "Low", "Close", "Volume"]).cast(pl.Float32)).collect().to_pandas()
            out["Ticker"] = out["Ticker"].map(normalize_symbol).astype("category")
        except Exception:  # noqa: BLE001
            out = None
    if out is None:
        df = load_market_ohlcv()
        out = df[df["Ticker"].isin(normalized)]
        if lookback_days and not out.empty:
            cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
            out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker", "Date"])


def close_matrix(symbols: Iterable[str], lookback_days: int = 2520, frequency: str = "daily") -> pd.DataFrame:
    df = ohlcv_for_symbols(symbols, lookback_days)
    if df.empty:
        return pd.DataFrame()
    if frequency == "monthly":
        df = df.groupby(["Ticker", pd.Grouper(key="Date", freq="ME")], observed=True)["Close"].last().reset_index()
    elif frequency == "weekly":
        df = df.groupby(["Ticker", pd.Grouper(key="Date", freq="W-FRI")], observed=True)["Close"].last().reset_index()
    mat = df.groupby(["Date", "Ticker"], observed=True)["Close"].last().unstack().sort_index().ffill()
    return mat.dropna(axis=1, thresh=max(20, int(len(mat) * 0.45))).tail(max(30, int(lookback_days)))


def volume_matrix(symbols: Iterable[str], lookback_days: int = 2520, frequency: str = "daily") -> pd.DataFrame:
    df = ohlcv_for_symbols(symbols, lookback_days)
    if df.empty:
        return pd.DataFrame()
    if frequency == "monthly":
        df = df.groupby(["Ticker", pd.Grouper(key="Date", freq="ME")], observed=True)["Volume"].sum().reset_index()
    elif frequency == "weekly":
        df = df.groupby(["Ticker", pd.Grouper(key="Date", freq="W-FRI")], observed=True)["Volume"].sum().reset_index()
    mat = df.groupby(["Date", "Ticker"], observed=True)["Volume"].last().unstack().sort_index().ffill()
    return mat.tail(max(30, int(lookback_days)))


def returns_matrix(symbols: Iterable[str], lookback_days: int = 2520, frequency: str = "monthly") -> pd.DataFrame:
    prices = close_matrix(symbols, lookback_days=lookback_days, frequency=frequency)
    if prices.empty:
        return pd.DataFrame()
    return np.log(prices).diff().replace([np.inf, -np.inf], np.nan).dropna(how="all")


UPLOAD_DIR = BACKEND_DATA / "research_v2" / "uploads"


def _safe_user_path(path_value: Any) -> Path | None:
    """Resolve an upload id (as returned by the upload endpoint) to a file in UPLOAD_DIR.

    Only files inside UPLOAD_DIR are readable; anything else is rejected so a
    payload cannot point the service at arbitrary files on the server.
    """

    if not path_value:
        return None
    name = Path(str(path_value)).name
    resolved = (UPLOAD_DIR / name).resolve()
    if resolved.parent != UPLOAD_DIR.resolve() or not resolved.exists():
        raise ValueError(f"Upload '{name}' was not found. Upload the file again.")
    return resolved


def load_signal_upload(path_value: Any) -> pd.DataFrame:
    """Load researcher-provided asset/date signal ranks from CSV or parquet.

    Expected columns are flexible but must resolve to date, ticker and signal.
    """

    path = _safe_user_path(path_value)
    if path is None:
        return pd.DataFrame(columns=["date", "ticker", "signal"])
    df = pd.read_parquet(path, engine="pyarrow") if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    lower = {str(c).lower(): c for c in df.columns}
    date_col = lower.get("date") or lower.get("month") or lower.get("period")
    ticker_col = lower.get("ticker") or lower.get("symbol") or lower.get("asset")
    signal_col = lower.get("signal") or lower.get("rank") or lower.get("score") or lower.get("value")
    if not all([date_col, ticker_col, signal_col]):
        return pd.DataFrame(columns=["date", "ticker", "signal"])
    out = df[[date_col, ticker_col, signal_col]].rename(columns={date_col: "date", ticker_col: "ticker", signal_col: "signal"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out["ticker"] = out["ticker"].map(normalize_symbol)
    out["signal"] = pd.to_numeric(out["signal"], errors="coerce")
    return out.dropna(subset=["date", "ticker", "signal"]).sort_values(["date", "ticker"])


def load_event_upload(path_value: Any) -> pd.DataFrame:
    """Load event/treatment definitions from CSV or parquet."""

    path = _safe_user_path(path_value)
    if path is None:
        return pd.DataFrame(columns=["ticker", "treatment_date"])
    df = pd.read_parquet(path, engine="pyarrow") if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    lower = {str(c).lower(): c for c in df.columns}
    ticker_col = lower.get("ticker") or lower.get("symbol") or lower.get("asset")
    date_col = lower.get("treatment_date") or lower.get("event_date") or lower.get("date")
    if not ticker_col or not date_col:
        return pd.DataFrame(columns=["ticker", "treatment_date"])
    out = df.rename(columns={ticker_col: "ticker", date_col: "treatment_date"}).copy(deep=False)
    out["ticker"] = out["ticker"].map(normalize_symbol)
    out["treatment_date"] = pd.to_datetime(out["treatment_date"], errors="coerce").dt.tz_localize(None)
    keep = ["ticker", "treatment_date", *[c for c in out.columns if c not in {"ticker", "treatment_date"}]]
    return out[keep].dropna(subset=["ticker", "treatment_date"]).sort_values(["ticker", "treatment_date"])


def load_instrument_upload(path_value: Any) -> pd.DataFrame:
    """Load external instrument values from CSV or parquet."""

    path = _safe_user_path(path_value)
    if path is None:
        return pd.DataFrame(columns=["date", "ticker", "instrument"])
    df = pd.read_parquet(path, engine="pyarrow") if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    lower = {str(c).lower(): c for c in df.columns}
    date_col = lower.get("date") or lower.get("month") or lower.get("period")
    ticker_col = lower.get("ticker") or lower.get("symbol") or lower.get("asset")
    inst_col = lower.get("instrument") or lower.get("iv") or lower.get("z") or lower.get("value")
    if not date_col or not inst_col:
        return pd.DataFrame(columns=["date", "ticker", "instrument"])
    cols = [date_col, inst_col] + ([ticker_col] if ticker_col else [])
    out = df[cols].rename(columns={date_col: "date", inst_col: "instrument"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    if ticker_col:
        out = out.rename(columns={ticker_col: "ticker"})
        out["ticker"] = out["ticker"].map(normalize_symbol)
    else:
        out["ticker"] = "MARKET"
    out["instrument"] = pd.to_numeric(out["instrument"], errors="coerce")
    return out.dropna(subset=["date", "instrument"]).sort_values(["date", "ticker"])


def load_fundamentals() -> pd.DataFrame:
    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker"])
    df = pd.read_parquet(MASTER_FUNDAMENTALS, engine="pyarrow")
    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker"])
    out = df.copy(deep=False)
    out["ticker"] = out["ticker"].map(normalize_symbol)
    if "reportDate" in out.columns:
        out["reportDate"] = pd.to_datetime(out["reportDate"], errors="coerce")
    return out.dropna(subset=["ticker"])


def _fundamentals_cols(columns: list[str], symbols: Iterable[str] | None = None) -> pd.DataFrame:
    """Selected fundamentals columns (optionally only some tickers), tickers normalized."""

    if not MASTER_FUNDAMENTALS.exists():
        return pd.DataFrame(columns=["ticker"])
    if pl is not None:
        try:
            lf = pl.scan_parquet(str(MASTER_FUNDAMENTALS))
            have = set(lf.collect_schema().names())
            if "ticker" not in have:
                return pd.DataFrame(columns=["ticker"])
            lf = lf.select([c for c in columns if c in have])
            lf = lf.with_columns(pl.col("ticker").cast(pl.Utf8).str.strip_chars().str.to_uppercase().str.replace_all(r"[.\-]", "_"))
            if symbols is not None:
                lf = lf.filter(pl.col("ticker").is_in([normalize_symbol(s) for s in symbols]))
            out = lf.drop_nulls(["ticker"]).collect().to_pandas()
            if "reportDate" in out.columns:
                out["reportDate"] = pd.to_datetime(out["reportDate"], errors="coerce")
            return out
        except Exception:  # noqa: BLE001, S110
            pass
    df = load_fundamentals()
    df = df[[c for c in columns if c in df.columns]]
    return df if symbols is None else df[df["ticker"].isin([normalize_symbol(s) for s in symbols])]


@lru_cache(maxsize=1)
def static_sectors() -> pd.Series:
    """Sector per ticker. Sector membership is treated as time-invariant."""

    df = _fundamentals_cols(["ticker", "sector", "reportDate"])
    if df.empty or "sector" not in df.columns:
        return pd.Series(dtype=object)
    out = df.dropna(subset=["sector"]).sort_values("reportDate").groupby("ticker")["sector"].last()
    return out[out.astype(str).str.len() > 0]


# Balance-sheet items are stocks (any report type is valid at its date);
# income-statement items are flows and are only comparable across annual reports.
STOCK_FIELDS = {"Total Assets", "Stockholders Equity", "Common Stock Equity", "Total Debt", "Ordinary Shares Number", "Share Issued"}
FLOW_FIELDS = {"Net Income", "Net Income Common Stockholders", "Gross Profit", "Operating Income", "Total Revenue"}


def point_in_time_fundamental(field: str, dates: pd.DatetimeIndex, symbols: Iterable[str], lag_days: int = 90, max_age_days: int = 550) -> pd.DataFrame:
    """Fundamental ``field`` as it was knowable at each date.

    A report dated ``reportDate`` becomes usable ``lag_days`` later (filing lag).
    Values older than ``max_age_days`` are treated as missing rather than carried
    forward indefinitely. Dates before the first report are NaN: no backfill.
    """

    symbols = [normalize_symbol(s) for s in symbols]
    sub = _fundamentals_cols(["ticker", "reportDate", "periodType", field], symbols)
    if sub.empty or field not in sub.columns or "reportDate" not in sub.columns:
        return pd.DataFrame(np.nan, index=dates, columns=symbols)
    sub = sub.dropna(subset=["reportDate", field])
    if field in FLOW_FIELDS and "periodType" in sub.columns:
        sub = sub[sub["periodType"] == "annual"]
    if sub.empty:
        return pd.DataFrame(np.nan, index=dates, columns=symbols)
    sub = sub.assign(available=sub["reportDate"] + pd.Timedelta(days=int(lag_days)), value=pd.to_numeric(sub[field], errors="coerce"))
    sub = sub.sort_values(["ticker", "reportDate"]).drop_duplicates(["ticker", "available"], keep="last")
    wide = sub.pivot_table(index="available", columns="ticker", values="value", aggfunc="last").sort_index()
    grid = wide.index.union(dates)
    values = wide.reindex(grid).ffill(limit=None)
    # Age of the carried value: days since the last row where the ticker had a report.
    stamp = pd.DataFrame(np.where(wide.notna(), wide.index.values[:, None], np.datetime64("NaT")), index=wide.index, columns=wide.columns)
    stamp = stamp.reindex(grid).ffill()
    age = (grid.values[:, None] - stamp.to_numpy(dtype="datetime64[ns]")) / np.timedelta64(1, "D")
    values = values.where(age <= max_age_days).reindex(dates)
    return values.reindex(columns=symbols)


def annual_growth(field: str, dates: pd.DatetimeIndex, symbols: Iterable[str], lag_days: int = 90) -> pd.DataFrame:
    """Year-over-year growth of an annual-report field, point in time."""

    symbols = [normalize_symbol(s) for s in symbols]
    df = _fundamentals_cols(["ticker", "reportDate", "periodType", field], symbols)
    if df.empty or field not in df.columns:
        return pd.DataFrame(np.nan, index=dates, columns=symbols)
    sub = df[df.get("periodType") == "annual"][["ticker", "reportDate", field]].dropna()
    if sub.empty:
        return pd.DataFrame(np.nan, index=dates, columns=symbols)
    sub = sub.sort_values(["ticker", "reportDate"]).drop_duplicates(["ticker", "reportDate"], keep="last")
    sub["value"] = pd.to_numeric(sub[field], errors="coerce")
    prev = sub.groupby("ticker")["value"].shift(1)
    sub["growth"] = sub["value"] / prev.where(prev > 0) - 1
    sub["available"] = sub["reportDate"] + pd.Timedelta(days=int(lag_days))
    wide = sub.dropna(subset=["growth"]).pivot_table(index="available", columns="ticker", values="growth", aggfunc="last")
    if wide.empty:
        return pd.DataFrame(np.nan, index=dates, columns=symbols)
    grid = wide.index.union(dates)
    return wide.reindex(grid).ffill(limit=None).reindex(dates).reindex(columns=symbols)


def fundamentals_coverage_start() -> pd.Timestamp | None:
    df = _fundamentals_cols(["ticker", "reportDate"])
    if df.empty or "reportDate" not in df.columns:
        return None
    return pd.Timestamp(df["reportDate"].min()) + pd.Timedelta(days=90)


def ohlcv_matrices(symbols: Iterable[str], lookback_days: int = 2520) -> dict[str, pd.DataFrame]:
    """Daily Open/High/Low/Close/Volume matrices (dates x tickers)."""

    df = ohlcv_for_symbols(symbols, lookback_days)
    if df.empty:
        return {}
    return {col: df.pivot_table(index="Date", columns="Ticker", values=col, aggfunc="last", observed=True).sort_index() for col in ["Open", "High", "Low", "Close", "Volume"]}


def _parse_ken_french_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date"])
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*,?\s*Mkt-RF|^\s*Date\s*,", line):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame(columns=["date"])
    header = [h.strip().replace("-", "_").lower() or "date" for h in lines[header_idx].split(",")]
    rows: list[list[str]] = []
    for line in lines[header_idx + 1:]:
        if not re.match(r"^\s*\d{6,8}\s*,", line):
            continue
        parts = [p.strip() for p in line.split(",")]
        rows.append(parts[: len(header)])
    if not rows:
        return pd.DataFrame(columns=["date"])
    df = pd.DataFrame(rows, columns=header)
    fmt = "%Y%m%d" if df["date"].str.len().max() == 8 else "%Y%m"
    df["date"] = pd.to_datetime(df["date"], format=fmt, errors="coerce")
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
        mom_cols = [c for c in mom.columns if c != "date"]
        mom = mom.rename(columns={mom_cols[0]: "umd"}) if mom_cols else mom
    out = ff.merge(mom, on="date", how="outer") if not ff.empty and not mom.empty else (ff if not ff.empty else mom)
    return out.sort_values("date").drop_duplicates("date")


def monthly_factor_returns() -> pd.DataFrame:
    df = load_factor_returns()
    if df.empty:
        return df
    out = df.set_index("date").resample("ME").apply(lambda x: (1 + x).prod() - 1 if x.notna().any() else np.nan).reset_index()
    return out.rename(columns={"date": "Date"})


@lru_cache(maxsize=1)
def load_macro() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if CATEGORY7_MACRO.exists():
        df = pd.read_parquet(CATEGORY7_MACRO, engine="pyarrow")
        date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else None)
        if date_col:
            df = df.rename(columns={date_col: "Date"})
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            frames.append(df.dropna(subset=["Date"]))
    for path in sorted(PARQUET_CACHE.glob("macro_*.parquet")):
        try:
            df = pd.read_parquet(path, engine="pyarrow")
        except Exception:  # noqa: BLE001, S112
            continue
        date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else None)
        if not date_col:
            continue
        df = df.rename(columns={date_col: "Date"})
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        frames.append(df.dropna(subset=["Date"]))
    if not frames:
        return pd.DataFrame(columns=["Date"])
    normalized = []
    for frame in frames:
        cols = ["Date", *[c for c in frame.columns if c != "Date"]]
        normalized.append(frame[cols].set_index("Date"))
    out = pd.concat(normalized, axis=0, sort=False).groupby(level=0).first().sort_index().reset_index()
    return out.drop_duplicates("Date")


def data_inventory() -> dict[str, Any]:
    n_symbols = len(available_symbols())
    n_rows = _market_summary()[1]
    macro = load_macro()
    macro_cols = {str(c).lower() for c in macro.columns}
    return {
        "market_universe": str(MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE),
        "market_rows": n_rows,
        "market_symbols": n_symbols,
        "fundamentals": MASTER_FUNDAMENTALS.exists(),
        "factor_returns": not load_factor_returns().empty,
        "macro": not macro.empty,
        "fred_present": {
            "VIXCLS": bool(any("vix" in c.lower() for c in macro.columns)),
            "DGS3MO": bool(any(token in c for c in macro_cols for token in ("dgs3mo", "3mo", "tbill", "risk_free"))),
            "DGS2": "dgs2" in macro_cols or "ust_2y" in macro_cols,
            "DGS10": "dgs10" in macro_cols or "ust_10y" in macro_cols,
            "USREC": bool(any(token in c for c in macro_cols for token in ("usrec", "recession", "nber"))),
            "BAMLC0A0CM": "bamlc0a0cm" in macro_cols or bool(any(token in c for c in macro_cols for token in ("ig_credit", "credit_spread"))),
            "BAA10Y": "baa10y" in macro_cols,
            "BAMLH0A0HYM2": "bamlh0a0hym2" in macro_cols or bool(any("hy" in c and "spread" in c for c in macro_cols)),
        },
    }
