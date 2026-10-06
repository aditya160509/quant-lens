"""ML V2 local data access.

Runtime code is read-only. `data_fetcher.py` contains append-only fetch plans for
missing FRED/yfinance/Ken-French artifacts but is not invoked by feature runs.
"""

from __future__ import annotations

from functools import lru_cache
from contextvars import ContextVar
from pathlib import Path
from typing import Iterable, Any

import numpy as np
import pandas as pd

import polars as pl


AS_OF_DATE = ContextVar("ml_v2_as_of_date", default=None)


def dated(frame, column):
    cutoff = AS_OF_DATE.get()
    return frame.loc[frame[column] <= cutoff].copy() if cutoff is not None else frame


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
MASTER_FUNDAMENTALS = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
FF_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Research_Data_Factors_daily.csv"
FF5_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Research_Data_5_Factors_2x3_daily.csv"
MOM_DAILY = FACTORS_DATA / "raw" / "fama_french" / "F-F_Momentum_Factor_daily.csv"


def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")


def normalize_frequency(frequency: Any = "daily") -> str:
    raw = str(frequency or "daily").strip().lower()
    if raw not in {"daily", "day", "d", "1d"}:
        raise ValueError(f"Unsupported frequency: {frequency}; ML V2 supports daily OHLCV only")
    return "daily"


def annualization_factor(frequency: Any = "daily") -> float:
    normalize_frequency(frequency)
    return 252.0


def lookback_rows(lookback_days: int | float) -> int:
    return max(30, int(max(float(lookback_days or 1), 1.0)))


_PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
_TICKER_LOWER = pl.col("ticker").str.strip_chars().str.to_uppercase().str.replace_all(r"[.\-]", "_")
_TICKER = pl.col("Ticker").str.strip_chars().str.to_uppercase().str.replace_all(r"[.\-]", "_")


@lru_cache(maxsize=8)
def _symbol_counts(cutoff: pd.Timestamp | None) -> tuple[str, ...]:
    """Symbols ordered by number of valid daily closes (cached; one projected scan of three columns)."""
    if not MARKET_UNIVERSE.exists():
        return ()
    lazy = pl.scan_parquet(str(MARKET_UNIVERSE)).select(["Ticker", "Date", "Close"])
    if cutoff is not None:
        lazy = lazy.filter(pl.col("Date").cast(pl.Datetime("us")) <= cutoff.to_pydatetime())
    counts = (lazy.filter(pl.col("Close") > 0).with_columns(_TICKER.alias("Ticker"))
              .group_by("Ticker").agg(pl.col("Date").n_unique().alias("n")).sort(["n", "Ticker"], descending=[True, False]).collect())
    return tuple(counts["Ticker"].to_list())


def load_market_ohlcv(symbols: Iterable[str] | None = None) -> pd.DataFrame:
    """Validated daily OHLCV for `symbols` (all symbols when None); only requested symbols are materialised."""
    columns = ["Ticker", "Date", *_PRICE_COLUMNS]
    if not MARKET_UNIVERSE.exists():
        return pd.DataFrame(columns=columns)
    lazy = pl.scan_parquet(str(MARKET_UNIVERSE)).select(columns).with_columns(_TICKER.alias("Ticker"))
    if symbols is not None:
        lazy = lazy.filter(pl.col("Ticker").is_in(sorted({normalize_symbol(s) for s in symbols})))
    df = lazy.collect().to_pandas()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in _PRICE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.loc[~(df["Close"] > 0), _PRICE_COLUMNS] = np.nan
    keys = ["Ticker", "Date"]
    observations = df.dropna(subset=keys)
    duplicate = observations.duplicated(keys, keep=False)
    if duplicate.any() and observations.loc[duplicate].drop_duplicates().duplicated(keys, keep=False).any():
        raise ValueError("Conflicting price observations after ticker normalization")
    return observations.drop_duplicates(keys).sort_values(keys)


def available_symbols(limit: int | None = None, frequency: str = "daily") -> list[str]:
    normalize_frequency(frequency)
    out = list(_symbol_counts(AS_OF_DATE.get()))
    return out[:limit] if limit else out


DEFAULT_UNIVERSE = (
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "BAC", "WFC", "GS", "XOM", "CVX", "COP", "JNJ", "PFE", "MRK", "UNH",
    "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "DIS", "CSCO", "ORCL", "IBM", "ADBE", "CAT", "BA", "GE", "MMM", "HON", "T", "VZ",
)

# One liquid, long-history US large-cap list per GICS sector. Names missing from the local data are dropped at resolve time.
SECTOR_UNIVERSES: dict[str, tuple[str, ...]] = {
    "sector_technology": ("AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "QCOM", "TXN", "INTC", "IBM", "NOW", "AMAT"),
    "sector_communication": ("GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA"),
    "sector_consumer_discretionary": ("AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG", "TJX", "F", "GM"),
    "sector_consumer_staples": ("PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "MDLZ", "CL", "KMB", "GIS"),
    "sector_energy": ("XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PSX", "MPC", "VLO", "WMB", "KMI"),
    "sector_financials": ("JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "USB", "PNC"),
    "sector_health_care": ("JNJ", "UNH", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY", "AMGN"),
    "sector_industrials": ("CAT", "BA", "GE", "HON", "UPS", "RTX", "DE", "LMT", "UNP", "FDX"),
    "sector_materials": ("LIN", "SHW", "APD", "ECL", "FCX", "NEM", "NUE", "VMC", "PPG", "MOS", "CTVA", "IP"),
    "sector_real_estate": ("PLD", "AMT", "CCI", "PSA", "O", "SPG", "WELL", "DLR", "WY", "VICI", "AVB", "EQR"),
    "sector_utilities": ("NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC", "PEG", "ETR"),
}
UNIVERSE_PRESETS: dict[str, tuple[str, ...]] = {
    "default": DEFAULT_UNIVERSE,
    **SECTOR_UNIVERSES,
    "high_volatility": ("TSLA", "NVDA", "AMD", "MU", "NFLX", "PLTR", "COIN", "MARA", "RIOT", "UBER", "ENPH", "FSLR", "AAL", "DAL", "LUV"),
    "etfs": ("SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "USO", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "VNQ"),
}
# Crypto trades on its own 7-day calendar and is not mixed into any equity preset.
UNIVERSE_PRESET_IDS = list(UNIVERSE_PRESETS) + ["all"]
_WHOLE = {"all", "full", "master", "master_universe", "market_universe", "whole"}


def universe_label(payload: dict | None, symbols: Iterable[str]) -> str:
    """Preset id when one was requested, else a custom label with the symbol count."""
    payload = payload or {}
    label = str(payload.get("universe") or "").strip().lower()
    explicit = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("asset") or payload.get("symbol")
    if not explicit and label in UNIVERSE_PRESETS:
        return label
    if not explicit and label in _WHOLE:
        return "all"
    return f"custom:{len(list(symbols))}"


def parse_symbols(payload: dict | None, default_limit: int = 80, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("asset") or payload.get("symbol") or payload.get("universe")
    universe = available_symbols(frequency=payload.get("frequency") or "daily")
    existing = set(universe)
    raw_label = str(raw or "").strip().lower()
    preset = raw_label in UNIVERSE_PRESETS or raw is None
    if raw is None or raw_label in UNIVERSE_PRESETS:
        # Fixed liquid US large caps on one exchange calendar, so a first run is complete;
        # a coverage-ranked default mixes crypto, FX and foreign listings whose calendars leave gaps.
        requested = [s for s in UNIVERSE_PRESETS[raw_label or "default"] if s in existing][:default_limit] or universe[:default_limit]
    elif raw_label in _WHOLE:
        requested = universe
    elif raw_label in {"", "sp500", "s&p 500"}:
        requested = [s for s in DEFAULT_UNIVERSE if s in existing][:default_limit] or universe[:default_limit]
    elif isinstance(raw, str):
        requested = [normalize_symbol(x) for x in raw.replace(";", ",").split(",") if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    if raw_label in {"sp500", "s&p 500"}:
        raise ValueError("S&P 500 membership is unavailable; supply an explicit ticker list.")
    missing = sorted(set(requested) - existing)
    if missing:
        raise ValueError("Unknown ML V2 symbols: " + ", ".join(missing))
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or max_symbols)
    if not 1 <= cap <= max_symbols:
        raise ValueError(f"max_symbols must be between 1 and {max_symbols}")
    requested = list(dict.fromkeys(requested))
    if not preset and raw_label not in _WHOLE and len(requested) > cap:
        raise ValueError(f"Requested {len(requested)} symbols exceeds max_symbols={cap}")
    if not requested:
        raise ValueError("No market observations available for the requested universe")
    return requested[:cap]


def ohlcv_for_symbols(symbols: Iterable[str], lookback_days: int | None = None, frequency: str = "daily") -> pd.DataFrame:
    normalize_frequency(frequency)
    out = dated(load_market_ohlcv(list(symbols)), "Date")
    if lookback_days and not out.empty:
        out = out[out["Date"] >= out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)]
    return out.sort_values(["Ticker", "Date"])


def _wide(ohlcv: pd.DataFrame, field: str) -> pd.DataFrame:
    return ohlcv.pivot(index="Date", columns="Ticker", values=field).sort_index()


def returns_from_ohlcv(ohlcv: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    prices = _wide(ohlcv, "Close")
    rets = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    return rets.dropna(how="all").tail(lookback_rows(lookback_days))


def _fetch(symbols: Iterable[str], lookback_days: int, frequency: str) -> pd.DataFrame:
    return ohlcv_for_symbols(list(symbols), lookback_days=int(lookback_days) + 120, frequency=frequency)


def returns_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    ohlcv = _fetch(symbols, lookback_days, frequency)
    return pd.DataFrame() if ohlcv.empty else returns_from_ohlcv(ohlcv, lookback_days)


def close_matrix(symbols: Iterable[str], lookback_days: int = 504, frequency: str = "daily") -> pd.DataFrame:
    ohlcv = _fetch(symbols, lookback_days, frequency)
    return pd.DataFrame() if ohlcv.empty else _wide(ohlcv, "Close").tail(lookback_rows(lookback_days))


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
        return {str(s): None for s in symbols}
    mapping = dict(zip(meta["ticker"], pd.to_numeric(meta["marketCap"], errors="coerce")))
    out = {}
    for s in symbols:
        v = mapping.get(normalize_symbol(s), np.nan)
        out[str(s)] = float(v) if pd.notna(v) and float(v) > 0 else None
    return out


# Annual flows are only comparable across annual reports; balance-sheet items are stocks at any report date.
_FLOW_FIELDS = {"Net Income", "Net Income Common Stockholders", "Gross Profit", "Operating Income", "Total Revenue"}


def point_in_time_fundamentals(fields: Iterable[str], symbols: Iterable[str], dates: pd.DatetimeIndex,
                               lag_days: int = 90, max_age_days: int = 550) -> dict[str, pd.DataFrame]:
    """Daily ``dates x symbols`` frames of fundamentals as knowable on each date.

    A report is usable ``lag_days`` after its report date and goes missing again after ``max_age_days``;
    dates before a name's first report stay NaN (no backfill). Fields or tickers absent from the data come back all-NaN.
    """
    fields, symbols = list(fields), [normalize_symbol(s) for s in symbols]
    out = {f: pd.DataFrame(np.nan, index=dates, columns=symbols) for f in fields}
    if not fields or not MASTER_FUNDAMENTALS.exists():
        return out
    lazy = pl.scan_parquet(str(MASTER_FUNDAMENTALS))
    have = set(lazy.collect_schema().names())
    present = [f for f in fields if f in have]
    if not present or not {"ticker", "reportDate"} <= have:
        return out
    columns = ["ticker", "reportDate", *(["periodType"] if "periodType" in have else []), *present]
    frame = lazy.select(columns).with_columns(_TICKER_LOWER.alias("ticker")).filter(pl.col("ticker").is_in(symbols)).collect().to_pandas()
    frame["reportDate"] = pd.to_datetime(frame["reportDate"], errors="coerce")
    cutoff = AS_OF_DATE.get()
    for field in present:
        sub = frame.dropna(subset=["reportDate"]).assign(value=pd.to_numeric(frame[field], errors="coerce")).dropna(subset=["value"])
        if field in _FLOW_FIELDS and "periodType" in sub.columns:
            sub = sub[sub["periodType"] == "annual"]
        sub = sub.assign(available=sub["reportDate"] + pd.Timedelta(days=lag_days))
        if cutoff is not None:
            sub = sub[sub["available"] <= cutoff]
        if sub.empty:
            continue
        sub = sub.sort_values("available").drop_duplicates(["available", "ticker"], keep="last")
        grid = dates.union(pd.DatetimeIndex(sub["available"].unique())).sort_values()
        values = sub.pivot(index="available", columns="ticker", values="value").reindex(grid).ffill()
        stamp = sub.assign(stamp=sub["available"]).pivot(index="available", columns="ticker", values="stamp").reindex(grid).ffill()
        age = (pd.DataFrame({c: grid for c in stamp.columns}, index=grid) - stamp).apply(lambda col: col.dt.days)
        out[field] = values.where(age <= max_age_days).reindex(index=dates, columns=symbols)
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
    macro = load_macro()
    ff = load_fama_french()
    return {
        "market_universe_parquet": str(MARKET_UNIVERSE),
        "market_universe_exists": MARKET_UNIVERSE.exists(),
        "daily_tickers": len(_symbol_counts(None)),
        "macro_rows": int(len(macro)),
        "macro_columns": [str(c) for c in macro.columns[:50]],
        "fama_french_rows": int(len(ff)),
        "fama_french_columns": [str(c) for c in ff.columns[:30]],
        "fundamentals_exists": MASTER_FUNDAMENTALS.exists(),
    }
