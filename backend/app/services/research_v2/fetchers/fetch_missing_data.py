"""Append-only fetch helpers for Research V2 missing external series.

This file is safe to run manually. It never overwrites existing parquet files:
new observations are concatenated, de-duplicated by date/ticker where possible,
and written back atomically.

Research V2 uses the existing repo data stores as source of truth. FRED-style
macro series append to ``factors/data/processed/category7_macro_regime.parquet``.
Public market proxies append to ``backend/data/market_universe.parquet`` only
when the ticker is absent or the fetched observations extend the date range.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"
MARKET_UNIVERSE = BACKEND_DATA / "market_universe.parquet"
CATEGORY7_MACRO = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
PARQUET_CACHE = BACKEND_DATA / "parquet_cache"

FRED_SERIES = {
    "VIXCLS": "vixcls",
    "DGS3MO": "dgs3mo",
    "DGS2": "dgs2",
    "DGS10": "dgs10",
    "BAMLC0A0CM": "bamlc0a0cm",
    "BAMLH0A0HYM2": "bamlh0a0hym2",
    "FEDFUNDS": "fed_funds",
    "CPIAUCSL": "cpi",
    "USREC": "usrec",
    "DEXUSEU": "dexuseu",
    "DEXJPUS": "dexjpus",
}

PUBLIC_MARKET_PROXIES = [
    "EFA", "EWJ", "EWU", "EEM", "VGK", "FEZ", "DXJ",
    "IEF", "TLT", "LQD", "HYG", "FXE", "FXY",
]


def _append_parquet(path: Path, frame: pd.DataFrame, subset: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_parquet(path, engine="pyarrow")
        frame = pd.concat([old, frame], ignore_index=True)
    for col in ("Date", "Datetime", "date", "datetime"):
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.tz_localize(None)
    if "Ticker" in frame.columns:
        frame["Ticker"] = frame["Ticker"].astype(str).str.upper()
    frame = frame.drop_duplicates(list(subset)).sort_values(list(subset))
    tmp = path.with_suffix(".tmp.parquet")
    frame.to_parquet(tmp, index=False, engine="pyarrow")
    tmp.replace(path)
    return int(len(frame))


def _append_wide_by_date(path: Path, frame: pd.DataFrame) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    if path.exists():
        old = pd.read_parquet(path, engine="pyarrow")
        date_col = "date" if "date" in old.columns else ("Date" if "Date" in old.columns else None)
        if date_col and date_col != "date":
            old = old.rename(columns={date_col: "date"})
        old["date"] = pd.to_datetime(old["date"], errors="coerce")
        combined = old.merge(frame, on="date", how="outer", suffixes=("", "_new"))
        for col in list(combined.columns):
            if not col.endswith("_new"):
                continue
            base = col[:-4]
            if base in combined.columns:
                combined[base] = combined[base].combine_first(combined[col])
                combined = combined.drop(columns=[col])
            else:
                combined = combined.rename(columns={col: base})
    else:
        combined = frame
    combined = combined.sort_values("date").drop_duplicates("date")
    tmp = path.with_suffix(".tmp.parquet")
    combined.to_parquet(tmp, index=False, engine="pyarrow")
    tmp.replace(path)
    csv_path = path.with_suffix(".csv")
    if csv_path.exists():
        combined.to_csv(csv_path, index=False)
    return int(len(combined))


def _standardize_yahoo_ohlcv(hist: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    out = hist.reset_index() if "Date" not in hist.columns and "Datetime" not in hist.columns else hist.copy()
    out = out.rename(columns={c: str(c).strip().title() for c in out.columns})
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    out["Ticker"] = ticker.upper()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = 0.0 if col == "Volume" else pd.NA
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]]


def fetch_fred_series(api_key: str | None = None, series: Iterable[str] | None = None) -> dict[str, int]:
    """Fetch FRED series and append them into category7 macro/regime parquet."""

    try:
        from pandas_datareader import data as pdr
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install pandas_datareader to fetch FRED series") from exc
    selected = list(series or FRED_SERIES)
    results: dict[str, int] = {}
    wide = pd.DataFrame()
    for code in selected:
        col = FRED_SERIES.get(code, code.lower())
        df = pdr.DataReader(code, "fred").reset_index().rename(columns={"DATE": "date", code: col})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        results[code] = int(df[col].notna().sum())
        wide = df if wide.empty else wide.merge(df, on="date", how="outer")
    if not wide.empty:
        results["category7_macro_regime_rows"] = _append_wide_by_date(CATEGORY7_MACRO, wide)
    return results


def fetch_public_market_proxies(tickers: Iterable[str] | None = None, period: str = "max") -> dict[str, int]:
    """Fetch public market proxies and append them into the main market universe."""

    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install yfinance to fetch international proxies") from exc
    results: dict[str, int] = {}
    frames = []
    for ticker in list(tickers or PUBLIC_MARKET_PROXIES):
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if hist.empty:
            results[ticker] = 0
            continue
        frame = _standardize_yahoo_ohlcv(hist, ticker)
        frames.append(frame)
        results[ticker] = int(len(frame))
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        results["market_universe_rows"] = _append_parquet(MARKET_UNIVERSE, combined, ["Date", "Ticker"])
    return results


def inventory_required_missing() -> dict[str, object]:
    """Return the external research data still worth refreshing."""

    macro_cols: set[str] = set()
    if CATEGORY7_MACRO.exists():
        macro_cols = {str(c).lower() for c in pd.read_parquet(CATEGORY7_MACRO, engine="pyarrow").columns}
    market_tickers: set[str] = set()
    if MARKET_UNIVERSE.exists():
        market_tickers = set(pd.read_parquet(MARKET_UNIVERSE, columns=["Ticker"], engine="pyarrow")["Ticker"].astype(str).str.upper().unique())
    return {
        "macro_series_in_category7": {code: col.lower() in macro_cols for code, col in FRED_SERIES.items()},
        "market_proxies_in_market_universe": {ticker: ticker.upper() in market_tickers for ticker in PUBLIC_MARKET_PROXIES},
        "researcher_uploads_required_for_publication": [
            "raw cross-sectional rank CSVs",
            "external instruments for IV",
            "formal event/treatment files",
            "custom factor library uploads",
        ],
    }


if __name__ == "__main__":
    print(inventory_required_missing())
