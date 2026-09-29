"""Data access helpers for Factors V2.

The feature modules compute from local datasets only. These helpers keep all
path handling and metadata-row CSV parsing in one place.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional
import warnings

import numpy as np
import pandas as pd

try:
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover
    pq = None

try:  # optional until environment is synced with backend/requirements.txt
    import polars as pl
except Exception:  # pragma: no cover
    pl = None

def _read_parquet_mmap(path: Path, columns: Optional[list[str]] = None) -> pd.DataFrame:
    """Read parquet through Arrow memory mapping when available.

    This is the realtime path for Factors V2: it avoids the pandas parquet
    deserialization path and releases the Arrow buffer immediately after
    conversion to keep request memory stable.
    """
    if pq is not None:
        try:
            table = pq.read_table(path, columns=columns, memory_map=True)
            return table.to_pandas(self_destruct=True)
        except Exception:
            pass
    return pd.read_parquet(path, columns=columns) if columns else pd.read_parquet(path)


def _attach_ticker_ids(df: pd.DataFrame) -> pd.DataFrame:
    if "Ticker" not in df.columns or "ticker_id" in df.columns:
        return df
    out = df.copy()
    codes, uniques = pd.factorize(out["Ticker"], sort=True)
    out["ticker_id"] = codes.astype("int32")
    out.attrs["ticker_map"] = {str(t): int(i) for i, t in enumerate(uniques)}
    return out


ROOT = Path(__file__).resolve().parents[5]
BACKEND_DATA = ROOT / "backend" / "data"
FACTORS_DATA = ROOT / "factors" / "data"


def _safe_date_index(df: pd.DataFrame, column: str = "Date") -> pd.DataFrame:
    out = df.copy()
    if column not in out.columns:
        out = out.rename(columns={out.columns[0]: column})
    out[column] = pd.to_datetime(out[column], format="%Y%m%d", errors="coerce")
    out = out.dropna(subset=[column]).set_index(column).sort_index()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.replace([-99.99, -999.0, -999.99], np.nan)
    return out / 100.0


def read_metadata_csv(path: Path, header_tokens: Iterable[str]) -> pd.DataFrame:
    """Read Ken French/AQR-style CSVs with prose metadata before the header."""
    lines = path.read_text(errors="ignore").splitlines()
    header_row = 0
    tokens = tuple(header_tokens)
    for i, line in enumerate(lines):
        if "," in line and any(token in line for token in tokens):
            header_row = i
            break
    return pd.read_csv(path, skiprows=header_row)


def read_metadata_csv_polars(path: Path, header_tokens: Iterable[str]):
    """Polars reader for metadata-heavy Fama-French/AQR files."""
    if pl is None:
        return read_metadata_csv(path, header_tokens)
    lines = path.read_text(errors="ignore").splitlines()
    header_row = 0
    tokens = tuple(header_tokens)
    for i, line in enumerate(lines):
        if "," in line and any(token in line for token in tokens):
            header_row = i
            break
    return pl.read_csv(path, skip_rows=header_row, infer_schema_length=5000)


@lru_cache(maxsize=1)
def load_market_universe() -> pd.DataFrame:
    path = BACKEND_DATA / "market_universe.parquet"
    columns = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
    if pl is not None:
        try:
            df = pl.scan_parquet(str(path)).select(columns).collect().to_pandas()
        except Exception:
            df = _read_parquet_mmap(path, columns=columns)
    else:
        df = _read_parquet_mmap(path, columns=columns)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return _attach_ticker_ids(df.dropna(subset=["Ticker", "Date", "Close"]).sort_values(["Ticker", "Date"]))


@lru_cache(maxsize=1)
def load_symbol_directory() -> pd.DataFrame:
    """Compact symbol directory for terminal-style autocomplete.

    Built from the local market universe parquet and enriched with sector/industry
    metadata from the fundamentals parquet when available. This stays local and
    avoids browser-side third-party symbol search/CORS.
    """
    market = load_market_universe()
    latest_idx = market.groupby("Ticker", sort=False)["Date"].idxmax()
    latest = market.loc[latest_idx, ["Ticker", "Date", "Close", "Volume"]].copy()
    latest = latest.rename(columns={"Ticker": "symbol", "Date": "last_date", "Close": "last_price", "Volume": "volume"})
    latest["symbol"] = latest["symbol"].astype(str).str.upper()
    latest["asset_type"] = latest["symbol"].str.startswith("_IDX_").map(lambda flag: "index" if flag else "equity")
    latest["display_name"] = latest["symbol"].str.replace("_IDX_", "", regex=False)

    try:
        fundamentals = load_fundamentals()
        cols = [col for col in ["ticker", "sector", "industry"] if col in fundamentals.columns]
        if "ticker" in cols:
            meta = fundamentals[cols].dropna(subset=["ticker"]).copy()
            meta["symbol"] = meta["ticker"].astype(str).str.upper()
            meta = meta.drop(columns=["ticker"]).drop_duplicates("symbol", keep="last")
            latest = latest.merge(meta, on="symbol", how="left")
    except Exception:
        latest["sector"] = None
        latest["industry"] = None

    for col in ["sector", "industry"]:
        if col not in latest.columns:
            latest[col] = None
    latest["search_text"] = (
        latest["symbol"].fillna("")
        + " "
        + latest["display_name"].fillna("")
        + " "
        + latest["sector"].fillna("")
        + " "
        + latest["industry"].fillna("")
    ).str.upper()
    return latest.sort_values(["asset_type", "symbol"]).reset_index(drop=True)


def search_symbol_directory(query: str, limit: int = 25, asset_type: Optional[str] = None) -> list[dict]:
    directory = load_symbol_directory()
    q = str(query or "").strip().upper()
    if not q:
        hits = directory.head(limit)
    else:
        scope = directory
        if asset_type:
            scope = scope[scope["asset_type"].eq(asset_type)]
        starts = scope[scope["symbol"].str.startswith(q, na=False)]
        contains = scope[~scope.index.isin(starts.index) & scope["search_text"].str.contains(q, na=False, regex=False)]
        hits = pd.concat([starts, contains], ignore_index=False).head(max(1, min(int(limit or 25), 75)))
    records = []
    for row in hits.itertuples(index=False):
        records.append(
            {
                "symbol": str(row.symbol),
                "name": str(getattr(row, "display_name", row.symbol) or row.symbol),
                "asset_type": str(getattr(row, "asset_type", "equity") or "equity"),
                "sector": None if pd.isna(getattr(row, "sector", None)) else str(getattr(row, "sector")),
                "industry": None if pd.isna(getattr(row, "industry", None)) else str(getattr(row, "industry")),
                "last_price": None if pd.isna(getattr(row, "last_price", None)) else float(getattr(row, "last_price")),
                "volume": None if pd.isna(getattr(row, "volume", None)) else float(getattr(row, "volume")),
            }
        )
    return records


@lru_cache(maxsize=1)
def load_fundamentals() -> pd.DataFrame:
    path = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
    if pl is not None:
        try:
            df = pl.scan_parquet(str(path)).collect().to_pandas()
        except Exception:
            df = _read_parquet_mmap(path)
    else:
        df = _read_parquet_mmap(path)
    if "reportDate" in df.columns:
        df["reportDate"] = pd.to_datetime(df["reportDate"], errors="coerce")
    return df


@lru_cache(maxsize=1)
def load_category7_macro() -> pd.DataFrame:
    path = FACTORS_DATA / "processed" / "category7_macro_regime.parquet"
    if pl is not None:
        try:
            df = pl.scan_parquet(str(path)).collect().to_pandas()
        except Exception:
            df = _read_parquet_mmap(path)
    else:
        df = _read_parquet_mmap(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date")


@lru_cache(maxsize=8)
def load_ff_file(name: str) -> pd.DataFrame:
    file_map = {
        "ff3": BACKEND_DATA / "factors_us" / "ff3_daily.csv",
        "ff5": BACKEND_DATA / "factors_us" / "ff5_daily.csv",
        "momentum": BACKEND_DATA / "factors_us" / "momentum_daily.csv",
    }
    path = file_map[name]
    tokens = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    return _safe_date_index(read_metadata_csv(path, tokens))


@lru_cache(maxsize=2)
def load_factor_returns(model: str = "ff5_mom") -> pd.DataFrame:
    if model in {"ff3", "capm"}:
        df = load_ff_file("ff3")
    else:
        df = load_ff_file("ff5")
    if model in {"ff5_mom", "carhart", "momentum"}:
        mom = load_ff_file("momentum")
        df = df.join(mom[["Mom"]], how="left")
    if model == "carhart":
        df = df[[c for c in ["Mkt-RF", "SMB", "HML", "Mom", "RF"] if c in df.columns]]
    elif model == "capm":
        df = df[[c for c in ["Mkt-RF", "RF"] if c in df.columns]]
    return df.dropna(how="all")


@lru_cache(maxsize=4)
def load_aqr_factor_returns(region: str = "USA") -> pd.DataFrame:
    """Load AQR processed factor files and return a daily/monthly factor panel.

    The processed AQR tabs keep the original workbook metadata above the real
    DATE header. This loader uses the selected region column where present and
    normalizes AQR percentage returns to decimal returns.
    """
    region = (region or "USA").upper()
    folder = FACTORS_DATA / "processed" / "aqr_csv"
    if not folder.exists():
        return pd.DataFrame()
    pieces: list[pd.DataFrame] = []
    for path in sorted(folder.glob("*.csv")):
        upper_name = path.name.upper()
        if not any(token in upper_name for token in ("BAB", "BETTING", "QMJ", "QUALITY", "DEVIL", "HML", "GLOBAL")):
            continue
        parsed = _parse_aqr_csv(path, region)
        if parsed is not None and not parsed.empty:
            pieces.append(parsed)
    if not pieces:
        return pd.DataFrame()
    out = pd.concat(pieces, axis=1).sort_index()
    out = out.loc[:, ~out.columns.duplicated()]
    return out.dropna(how="all")


_AQR_COLUMN_ALIASES = {
    "BAB Factors": "BAB",
    "Betting Against Beta": "BAB",
    "BAB": "BAB",
    "QMJ Factors": "QMJ",
    "Quality Minus Junk": "QMJ",
    "QMJ": "QMJ",
    "Devil HML": "HML_Devil",
    "HML Devil": "HML_Devil",
    "HML_Devil": "HML_Devil",
    "HML FF": "HML_FF_AQR",
    "UMD": "UMD_AQR",
    "MKT": "MKT_AQR",
    "SMB": "SMB_AQR",
    "Value": "Value_Global",
    "Momentum": "Mom_Global",
    "Carry": "Carry_Global",
    "Defensive": "Defensive_Global",
}


def _parse_aqr_csv(path: Path, region: str) -> Optional[pd.DataFrame]:
    try:
        raw = pd.read_csv(path, header=None, nrows=20, dtype=str)
    except Exception:
        return None
    header_row = None
    for i, row in raw.iterrows():
        first = str(row.iloc[0]).strip().lower()
        if first in {"date", "dates"} or (len(first) in {4, 6, 8} and first[:4].isdigit()):
            header_row = int(i)
            break
    if header_row is None:
        header_row = 0
    try:
        df = pd.read_csv(path, skiprows=header_row)
    except Exception:
        return None
    if df.empty:
        return None
    date_col = next((c for c in df.columns if str(c).strip().lower() in {"date", "dates"}), df.columns[0])
    df = df.rename(columns={date_col: "DATE"})
    try:
        parsed_dates = pd.to_datetime(df["DATE"], format="mixed", errors="coerce")
        if parsed_dates.notna().sum() == 0 and df["DATE"].notna().sum() > 0:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Could not infer format")
                parsed_dates = pd.to_datetime(df["DATE"], errors="coerce")
        df["DATE"] = parsed_dates
    except ValueError:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not infer format")
            df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).set_index("DATE")
    if df.empty:
        return None
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(axis=1, how="all")
    if df.empty:
        return None
    selected_cols = []
    if region in df.columns:
        selected_cols.append(region)
    elif "USA" in df.columns:
        selected_cols.append("USA")
    else:
        selected_cols.extend([c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])])
    if not selected_cols:
        return None
    out = df[selected_cols].copy()
    base_name = path.stem.replace("-", " ").replace("_", " ")
    rename = {}
    for col in out.columns:
        canonical = None
        search = f"{base_name} {col}"
        for alias, target in _AQR_COLUMN_ALIASES.items():
            if alias.lower() in search.lower():
                canonical = target
                break
        rename[col] = canonical or str(col).strip()
    out = out.rename(columns=rename)
    for col in out.columns:
        values = out[col].dropna()
        if len(values) and values.abs().median() > 0.5:
            out[col] = out[col] / 100.0
    return out


def load_price_file(ticker: str) -> pd.DataFrame:
    candidates = [
        BACKEND_DATA / "prices" / f"{ticker}.parquet",
        BACKEND_DATA / "prices" / f"{ticker.replace('.', '_')}.parquet",
        BACKEND_DATA / "prices" / f"{ticker}.csv",
        BACKEND_DATA / "prices" / f"{ticker.replace('.', '_')}.csv",
    ]
    for path in candidates:
        if path.exists():
            if path.suffix == ".parquet":
                df = _read_parquet_mmap(path)
            else:
                df = pd.read_csv(path)
            date_col = "Date" if "Date" in df.columns else df.columns[0]
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            return df.rename(columns={date_col: "Date"}).dropna(subset=["Date"]).sort_values("Date")
    return pd.DataFrame()


def available_aqr_csvs() -> list[Path]:
    folder = FACTORS_DATA / "processed" / "aqr_csv"
    return sorted(folder.glob("*.csv")) if folder.exists() else []


def load_market_universe_lazy():
    """Lazy Arrow/Polars scan for full-universe jobs and cached nightly jobs."""
    path = BACKEND_DATA / "market_universe.parquet"
    if pl is None:
        return load_market_universe()
    return pl.scan_parquet(str(path))


def load_fundamentals_lazy():
    path = BACKEND_DATA / "fundamentals" / "master_fundamentals.parquet"
    if pl is None:
        return load_fundamentals()
    return pl.scan_parquet(str(path))


@lru_cache(maxsize=1)
def load_sector_maps() -> dict:
    """Latest ticker-sector/industry maps for attribution and exposure paths."""
    f = load_fundamentals()
    if f.empty or "ticker" not in f.columns:
        return {"sector": {}, "industry": {}, "tickers": []}
    sort_cols = ["ticker"] + (["reportDate"] if "reportDate" in f.columns else [])
    latest = f.sort_values(sort_cols).drop_duplicates("ticker", keep="last")
    sector_col = "sector" if "sector" in latest.columns else "Sector" if "Sector" in latest.columns else None
    industry_col = "industry" if "industry" in latest.columns else "Industry" if "Industry" in latest.columns else None
    return {
        "sector": latest.set_index("ticker")[sector_col].dropna().astype(str).to_dict() if sector_col else {},
        "industry": latest.set_index("ticker")[industry_col].dropna().astype(str).to_dict() if industry_col else {},
        "tickers": latest["ticker"].astype(str).tolist(),
    }


@lru_cache(maxsize=4)
def load_market_return_matrix(max_tickers: int = 500) -> dict:
    """Cached contiguous price/return panel for repeated backtest/capacity jobs."""
    prices = load_market_universe()
    latest = prices.sort_values("Date").groupby("Ticker", as_index=False).tail(1)
    latest["dollar_volume"] = latest["Close"].abs() * latest["Volume"].fillna(0)
    tickers = latest.sort_values("dollar_volume", ascending=False).head(int(max_tickers))["Ticker"].astype(str).tolist()
    sub = prices[prices["Ticker"].isin(tickers)]
    close = sub.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return {
        "dates": returns.index.to_numpy(),
        "tickers": list(returns.columns),
        "returns": np.ascontiguousarray(returns.fillna(0.0).to_numpy(dtype=np.float32)),
        "close": close,
    }
