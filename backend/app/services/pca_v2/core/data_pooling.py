"""Append-only PCA V2 data pooling utilities.

These functions are operator tools. Feature runtime code does not call them.
They only append/deduplicate and never blindly overwrite parquet files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import json

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

from .data_loader import (
    BACKEND_DATA,
    CATEGORY7_MACRO,
    COMMODITY_FUTURES_SYMBOLS,
    CRYPTO_SYMBOLS,
    EQUITY_PROXY_SYMBOLS,
    FX_SYMBOLS,
    MARKET_UNIVERSE,
    RATES_FUTURES_SYMBOLS,
    RESEARCH_HOURLY,
    load_cross_asset_ohlcv,
    load_hourly_ohlcv,
    normalize_symbol,
)


PRICE_DIR = BACKEND_DATA / "prices"
HOURLY_UNIVERSE = BACKEND_DATA / "market_universe_hourly.parquet"
BACKEND_INTRADAY_DIR = BACKEND_DATA / "intraday_hourly_v5"
ROOT_INTRADAY_DIR = BACKEND_DATA.parents[1] / "data" / "intraday_hourly_v5"
PORTFOLIO_STATE = BACKEND_DATA / "portfolio_state.json"
CANONICAL_DIR = BACKEND_DATA / "canonical"


PCA_V2_TARGET_CROSS_ASSET_SYMBOLS: dict[str, list[str]] = {
    "fx_major": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X"],
    "fx_em": ["USDINR=X", "USDMXN=X", "USDBRL=X", "USDZAR=X", "USDKRW=X", "USDCNY=X", "USDTRY=X", "USDCNH=X", "USDHKD=X", "USDTWD=X"],
    "futures_energy": ["CL=F", "BZ=F", "NG=F", "RB=F", "HO=F"],
    "futures_metals": ["GC=F", "SI=F", "HG=F", "PL=F", "PA=F"],
    "futures_agriculture": ["ZC=F", "ZW=F", "ZS=F", "KC=F", "SB=F", "CC=F", "CT=F"],
    "futures_rates": ["ZB=F", "ZN=F", "ZF=F", "ZT=F"],
    "crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "AVAX-USD", "MATIC-USD", "LINK-USD", "LTC-USD", "BCH-USD", "DOGE-USD"],
}


def _append_dedup_parquet(path: Path, rows: pd.DataFrame, keys: list[str]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows.empty:
        return {"path": str(path), "added_rows": 0, "total_rows": None}
    if path.exists():
        existing = pd.read_parquet(path)
        before = len(existing)
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        before = 0
        combined = rows.copy()
    combined = combined.drop_duplicates(keys, keep="last").sort_values(keys)
    combined.to_parquet(path, index=False)
    return {"path": str(path), "added_rows": int(max(0, len(combined) - before)), "total_rows": int(len(combined))}


def fetch_yahoo_ohlcv(symbols: Iterable[str], period: str = "10y") -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed")
    frames = []
    for symbol in sorted({str(s).strip() for s in symbols if str(s).strip()}):
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        frame = df.reset_index()
        frame["Ticker"] = normalize_symbol(symbol)
        keep = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]
        frames.append(frame[keep])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])


def append_ohlcv_to_master(symbols: Iterable[str], period: str = "10y") -> dict:
    rows = fetch_yahoo_ohlcv(symbols, period=period)
    rows["Date"] = pd.to_datetime(rows["Date"], errors="coerce")
    rows = rows.dropna(subset=["Ticker", "Date", "Close"])
    return _append_dedup_parquet(MARKET_UNIVERSE, rows, ["Ticker", "Date"])


def _price_file_candidates(symbol: str) -> list[Path]:
    raw = str(symbol).strip()
    variants = {
        raw,
        raw.upper(),
        raw.replace("-", "_"),
        raw.replace("_", "-"),
        raw.upper().replace("-", "_"),
        raw.upper().replace("_", "-"),
    }
    return [PRICE_DIR / f"{variant}{ext}" for variant in variants for ext in (".parquet", ".csv")]


def local_price_file_for_symbol(symbol: str) -> Path | None:
    for path in _price_file_candidates(symbol):
        if path.exists():
            return path
    return None


def _read_local_price_file(symbol: str) -> pd.DataFrame:
    path = local_price_file_for_symbol(symbol)
    if path is None:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "Date" not in df.columns and "Datetime" not in df.columns:
        index_name = str(df.index.name or "").strip().title()
        if index_name in {"Date", "Datetime"}:
            df = df.reset_index()
    rename = {c: str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    date_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = pd.NA
    out = df[[date_col, "Open", "High", "Low", "Close", "Volume"]].rename(columns={date_col: "Date"}).copy()
    out["Ticker"] = normalize_symbol(symbol)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=True).dt.tz_convert(None)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Ticker", "Date", "Close"])


def append_existing_price_files_to_master(symbols: Iterable[str], dry_run: bool = True) -> dict:
    """Normalize local backend/data/prices files and append them to the master parquet.

    The default is a dry run because this is an operator action. Set
    dry_run=False to mutate market_universe.parquet.
    """

    requested = sorted({str(s).strip() for s in symbols if str(s).strip()})
    frames = []
    missing = []
    for symbol in requested:
        if local_price_file_for_symbol(symbol) is None:
            missing.append(symbol)
            continue
        frame = _read_local_price_file(symbol)
        if frame.empty:
            missing.append(symbol)
        else:
            frames.append(frame)
    rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"])
    result = {
        "dry_run": bool(dry_run),
        "requested_symbols": len(requested),
        "available_local_files": len(frames),
        "missing_symbols": missing,
        "candidate_rows": int(len(rows)),
        "path": str(MARKET_UNIVERSE),
    }
    if dry_run:
        return result
    result.update(_append_dedup_parquet(MARKET_UNIVERSE, rows, ["Ticker", "Date"]))
    return result


def append_cross_asset_prices_to_master(
    symbols: Iterable[str] | None = None,
    period: str = "10y",
    dry_run: bool = True,
    prefer_local: bool = True,
) -> dict:
    """Append cross-asset symbols, using local files first and yfinance only when enabled.

    No fetching happens unless dry_run=False and prefer_local cannot satisfy a
    symbol. This keeps the audit path safe while still documenting the exact
    append workflow for later.
    """

    if symbols is None:
        symbols = [s for group in PCA_V2_TARGET_CROSS_ASSET_SYMBOLS.values() for s in group]
    requested = sorted({str(s).strip() for s in symbols if str(s).strip()})
    local = append_existing_price_files_to_master(requested, dry_run=True) if prefer_local else {"missing_symbols": requested}
    missing_after_local = local.get("missing_symbols", requested)
    result = {"dry_run": bool(dry_run), "prefer_local": bool(prefer_local), "local_report": local, "fetch_symbols": missing_after_local}
    if dry_run:
        return result
    rows = []
    if prefer_local:
        local_mutation = append_existing_price_files_to_master([s for s in requested if s not in missing_after_local], dry_run=False)
        result["local_append"] = local_mutation
    if missing_after_local:
        fetched = fetch_yahoo_ohlcv(missing_after_local, period=period)
        rows.append(fetched)
    if rows:
        fetched_rows = pd.concat(rows, ignore_index=True)
        fetched_rows["Date"] = pd.to_datetime(fetched_rows["Date"], errors="coerce")
        fetched_rows = fetched_rows.dropna(subset=["Ticker", "Date", "Close"])
        result["fetch_append"] = _append_dedup_parquet(MARKET_UNIVERSE, fetched_rows, ["Ticker", "Date"])
    return result


def fetch_fred_series(series_ids: Iterable[str], start: str = "1990-01-01") -> pd.DataFrame:
    frames = []
    for sid in sorted({str(s).strip().upper() for s in series_ids if str(s).strip()}):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        from io import StringIO

        df = pd.read_csv(StringIO(resp.text))
        if "observation_date" not in df.columns or sid not in df.columns:
            continue
        df = df.rename(columns={"observation_date": "date", sid: sid.lower()})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df[sid.lower()] = pd.to_numeric(df[sid.lower()].replace(".", pd.NA), errors="coerce")
        frames.append(df[["date", sid.lower()]])
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    return out.sort_values("date")


def append_macro_to_category7(series_ids: Iterable[str] = ("VIXCLS", "DGS2", "DGS10", "BAMLC0A0CM", "BAMLH0A0HYM2")) -> dict:
    rows = fetch_fred_series(series_ids)
    return _append_dedup_parquet(CATEGORY7_MACRO, rows, ["date"])


def missing_data_report(required_symbols: Iterable[str] = ()) -> dict:
    market = pd.read_parquet(MARKET_UNIVERSE, columns=["Ticker", "Date"]) if MARKET_UNIVERSE.exists() else pd.DataFrame()
    macro = pd.read_parquet(CATEGORY7_MACRO) if CATEGORY7_MACRO.exists() else pd.DataFrame()
    existing = set(market.get("Ticker", pd.Series(dtype=str)).astype(str).str.upper())
    requested = {normalize_symbol(s) for s in required_symbols if str(s).strip()}
    macro_cols = {str(c).lower() for c in macro.columns}
    return {
        "has_market_universe": bool(MARKET_UNIVERSE.exists()),
        "has_category7_macro": bool(CATEGORY7_MACRO.exists()),
        "missing_symbols": sorted(requested - existing),
        "missing_macro_series": sorted({"vixcls", "dgs2", "dgs10", "bamlc0a0cm", "bamlh0a0hym2"} - macro_cols),
        "note": "Cross-asset futures/crypto/FX can be appended here later; local equity OHLCV and macro are present now.",
    }


def cross_asset_missing_report() -> dict:
    market = pd.read_parquet(MARKET_UNIVERSE, columns=["Ticker", "Date"]) if MARKET_UNIVERSE.exists() else pd.DataFrame()
    existing_master = set(market.get("Ticker", pd.Series(dtype=str)).astype(str).str.upper())
    categories = {}
    for category, symbols in PCA_V2_TARGET_CROSS_ASSET_SYMBOLS.items():
        rows = []
        for symbol in symbols:
            normalized = normalize_symbol(symbol)
            local_file = local_price_file_for_symbol(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "normalized": normalized,
                    "in_master": normalized in existing_master or symbol.upper() in existing_master,
                    "local_price_file": str(local_file) if local_file else None,
                    "has_local_price_file": local_file is not None,
                }
            )
        categories[category] = rows
    missing_master = [r["symbol"] for rows in categories.values() for r in rows if not r["in_master"]]
    missing_local_file = [r["symbol"] for rows in categories.values() for r in rows if not r["has_local_price_file"]]
    return {
        "market_universe": str(MARKET_UNIVERSE),
        "price_dir": str(PRICE_DIR),
        "target_symbol_count": sum(len(v) for v in PCA_V2_TARGET_CROSS_ASSET_SYMBOLS.values()),
        "missing_from_master_count": len(missing_master),
        "missing_from_master": missing_master,
        "missing_local_file_count": len(missing_local_file),
        "missing_local_file": missing_local_file,
        "categories": categories,
    }


def repository_data_inventory() -> dict:
    market_rows = market_tickers = None
    if MARKET_UNIVERSE.exists():
        market = pd.read_parquet(MARKET_UNIVERSE, columns=["Ticker"])
        market_rows = int(len(market))
        market_tickers = int(market["Ticker"].nunique())
    hourly_rows = hourly_tickers = None
    if HOURLY_UNIVERSE.exists():
        hourly = pd.read_parquet(HOURLY_UNIVERSE, columns=["Ticker"])
        hourly_rows = int(len(hourly))
        hourly_tickers = int(hourly["Ticker"].nunique())
    return {
        "market_universe_exists": MARKET_UNIVERSE.exists(),
        "market_universe_rows": market_rows,
        "market_universe_tickers": market_tickers,
        "price_file_count": len(list(PRICE_DIR.glob("*"))) if PRICE_DIR.exists() else 0,
        "hourly_universe_exists": HOURLY_UNIVERSE.exists(),
        "hourly_universe_rows": hourly_rows,
        "hourly_universe_tickers": hourly_tickers,
        "backend_intraday_csv_count": len(list(BACKEND_INTRADAY_DIR.glob("*.csv"))) if BACKEND_INTRADAY_DIR.exists() else 0,
        "root_intraday_csv_count": len(list(ROOT_INTRADAY_DIR.glob("*.csv"))) if ROOT_INTRADAY_DIR.exists() else 0,
        "portfolio_state_exists": PORTFOLIO_STATE.exists(),
    }


def materialize_canonical_cross_asset_panels(overwrite: bool = False) -> dict:
    """Create canonical PCA-ready parquet panels from existing local data.

    This uses only existing repo files. It does not fetch. Existing files are
    left intact unless overwrite=True.
    """

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    specs = {
        "equity_daily": EQUITY_PROXY_SYMBOLS,
        "fx_daily": FX_SYMBOLS,
        "futures_daily": COMMODITY_FUTURES_SYMBOLS + RATES_FUTURES_SYMBOLS,
        "crypto_daily": CRYPTO_SYMBOLS,
    }
    out = {}
    for name, symbols in specs.items():
        path = CANONICAL_DIR / f"{name}.parquet"
        if path.exists() and not overwrite:
            df = pd.read_parquet(path, columns=["Ticker"])
            out[name] = {"path": str(path), "status": "exists", "rows": int(len(df)), "tickers": int(df["Ticker"].nunique())}
            continue
        df = load_cross_asset_ohlcv(symbols)
        if name == "fx_daily" and not df.empty:
            df["Volume"] = pd.NA
        df["Asset_Class"] = name.replace("_daily", "")
        df["Source"] = "market_universe_or_backend_prices"
        df.to_parquet(path, index=False)
        out[name] = {"path": str(path), "status": "written", "rows": int(len(df)), "tickers": int(df["Ticker"].nunique()) if not df.empty else 0}
    hourly_path = CANONICAL_DIR / "cross_asset_hourly.parquet"
    if hourly_path.exists() and not overwrite:
        dfh = pd.read_parquet(hourly_path, columns=["Ticker"])
        out["cross_asset_hourly"] = {"path": str(hourly_path), "status": "exists", "rows": int(len(dfh)), "tickers": int(dfh["Ticker"].nunique())}
    else:
        hourly = load_hourly_ohlcv()
        if not hourly.empty:
            hourly = hourly.copy()
            hourly["Source"] = str(RESEARCH_HOURLY if RESEARCH_HOURLY.exists() else HOURLY_UNIVERSE)
        hourly.to_parquet(hourly_path, index=False)
        out["cross_asset_hourly"] = {"path": str(hourly_path), "status": "written", "rows": int(len(hourly)), "tickers": int(hourly["Ticker"].nunique()) if not hourly.empty else 0}
    metadata_rows = []
    for panel, info in out.items():
        metadata_rows.append({"panel": panel, **info})
    pd.DataFrame(metadata_rows).to_parquet(CANONICAL_DIR / "asset_metadata.parquet", index=False)
    return out


def materialize_portfolio_holdings_history(overwrite: bool = False) -> dict:
    """Convert server-side portfolio JSON into durable parquet snapshots/trades."""

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    holdings_path = CANONICAL_DIR / "portfolio_holdings_history.parquet"
    trades_path = CANONICAL_DIR / "portfolio_trade_history.parquet"
    if not PORTFOLIO_STATE.exists():
        return {"status": "missing_portfolio_state", "path": str(PORTFOLIO_STATE)}
    if holdings_path.exists() and trades_path.exists() and not overwrite:
        return {"status": "exists", "holdings_path": str(holdings_path), "trades_path": str(trades_path)}
    state = json.loads(PORTFOLIO_STATE.read_text())
    asof = pd.Timestamp.utcnow().tz_localize(None)
    holdings = []
    for ticker, row in (state.get("holdings") or {}).items():
        holdings.append(
            {
                "asof": asof,
                "ticker": normalize_symbol(ticker),
                "quantity": float(row.get("quantity", 0.0)),
                "avg_cost": float(row.get("avg_cost", 0.0)),
                "base_currency": state.get("base_currency", "USD"),
            }
        )
    trades = []
    for idx, row in enumerate(state.get("history") or []):
        item = {"row_id": idx, **row}
        if "symbol" in item:
            item["ticker"] = normalize_symbol(item["symbol"])
        elif "ticker" in item:
            item["ticker"] = normalize_symbol(item["ticker"])
        trades.append(item)
    pd.DataFrame(holdings).to_parquet(holdings_path, index=False)
    pd.DataFrame(trades).to_parquet(trades_path, index=False)
    return {"status": "written", "holdings_rows": len(holdings), "trade_rows": len(trades), "holdings_path": str(holdings_path), "trades_path": str(trades_path)}


def verify_futures_roll_methodology() -> dict:
    """Audit available futures files and write an explicit roll-method report.

    The repo has Yahoo-style continuous/proxy futures symbols (`=F`). Those are
    usable for returns, but the raw files do not contain contract identifiers or
    roll dates, so an independent institutional roll adjustment cannot be
    verified from local columns alone.
    """

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    symbols = COMMODITY_FUTURES_SYMBOLS + RATES_FUTURES_SYMBOLS
    rows = []
    for symbol in symbols:
        path = local_price_file_for_symbol(symbol)
        rows.append(
            {
                "symbol": symbol,
                "local_file": str(path) if path else None,
                "has_file": path is not None,
                "roll_method": "yahoo_continuous_proxy",
                "contract_ids_present": False,
                "roll_dates_present": False,
                "independent_roll_adjustment_verified": False,
                "usable_for_returns": path is not None,
            }
        )
    report = pd.DataFrame(rows)
    report.to_parquet(CANONICAL_DIR / "futures_roll_audit.parquet", index=False)
    return {
        "status": "written",
        "path": str(CANONICAL_DIR / "futures_roll_audit.parquet"),
        "symbols": len(rows),
        "available": int(report["has_file"].sum()),
        "verified_roll_adjusted": False,
        "note": "No contract-id/roll-date columns exist; current futures are Yahoo-style continuous/proxy series.",
    }
