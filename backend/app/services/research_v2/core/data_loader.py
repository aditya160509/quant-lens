"""Research V2 local data access.

Runtime feature calls are read-only. Fetchers under ``fetchers/`` append data
that is absent locally. The master universe parquet is the primary daily OHLCV
source, matching the rest of the V2 modules.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
import re

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
            return pl.scan_parquet(str(path)).select(columns).collect().to_pandas()
        except Exception:
            pass
    try:
        return pd.read_parquet(path, columns=columns, engine="pyarrow")
    except Exception:
        return pd.read_parquet(path, engine="pyarrow")


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    out = df.rename(columns={c: str(c).strip().title() for c in df.columns}).copy()
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    out["Ticker"] = out["Ticker"].map(normalize_symbol)
    clean = out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]].sort_values(["Ticker", "Date"])
    clean["Ticker"] = clean["Ticker"].astype("category")
    return clean


@lru_cache(maxsize=1)
def load_market_ohlcv() -> pd.DataFrame:
    source = MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE
    cols = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    return _standardize_ohlcv(_read_parquet(source, cols))


@lru_cache(maxsize=1)
def available_symbols() -> tuple[str, ...]:
    df = load_market_ohlcv()
    if df.empty:
        return ()
    counts = df.groupby("Ticker", observed=True)["Close"].count().sort_values(ascending=False)
    return tuple(str(x) for x in counts.index)


def parse_symbols(payload: dict | None, default_limit: int = 500, max_symbols: int = 5000) -> list[str]:
    payload = payload or {}
    raw = payload.get("tickers") or payload.get("symbols") or payload.get("universe") or payload.get("asset_universe")
    universe = list(available_symbols())
    existing = set(universe)
    label = str(raw or "").strip().lower()
    if raw is None or label in {"", "default", "broad", "broad_market"}:
        requested = universe[:default_limit]
    elif label in {"all", "full", "master", "master_universe", "whole"}:
        requested = universe
    elif isinstance(raw, str):
        requested = [normalize_symbol(x) for x in re.split(r"[,;\s]+", raw) if x.strip()]
    elif isinstance(raw, Iterable):
        requested = [normalize_symbol(x) for x in raw if str(x).strip()]
    else:
        requested = [normalize_symbol(raw)]
    out = [s for s in requested if s in existing]
    if not out:
        out = universe[:default_limit]
    cap = int(payload.get("max_symbols") or payload.get("max_tickers") or max_symbols)
    return out[: max(1, min(cap, max_symbols))]


def ohlcv_for_symbols(symbols: Iterable[str], lookback_days: int | None = None) -> pd.DataFrame:
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
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


def _safe_user_path(path_value: Any) -> Path | None:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve()
    except Exception:
        return None
    upload_roots = [BACKEND_DATA / "uploads", BACKEND_DATA / "research_uploads"]
    for root in upload_roots:
        root.mkdir(parents=True, exist_ok=True)
    allowed_roots = [ROOT.resolve(), *[p.resolve() for p in upload_roots], Path("/tmp").resolve()]
    if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
        return None
    return resolved if resolved.exists() else None


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
    out = df.rename(columns={ticker_col: "ticker", date_col: "treatment_date"}).copy()
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


@lru_cache(maxsize=1)
def load_fundamentals() -> pd.DataFrame:
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


@lru_cache(maxsize=1)
def latest_fundamentals() -> pd.DataFrame:
    df = load_fundamentals()
    if df.empty:
        return pd.DataFrame(columns=["ticker"]).set_index("ticker")
    if "reportDate" in df.columns:
        df = df.sort_values(["ticker", "reportDate"])
    return df.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)


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
    out = df.set_index("date").resample("ME").sum(min_count=1).reset_index()
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
        except Exception:
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
    market = load_market_ohlcv()
    macro = load_macro()
    macro_cols = {str(c).lower() for c in macro.columns}
    return {
        "market_universe": str(MARKET_UNIVERSE if MARKET_UNIVERSE.exists() else RESEARCH_MARKET_UNIVERSE),
        "market_rows": int(len(market)),
        "market_symbols": int(market["Ticker"].nunique()) if not market.empty else 0,
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
            "BAMLH0A0HYM2": "bamlh0a0hym2" in macro_cols or bool(any("hy" in c and "spread" in c for c in macro_cols)),
        },
    }
