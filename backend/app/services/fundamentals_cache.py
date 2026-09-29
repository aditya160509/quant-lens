"""
Fundamentals Cache Service
==========================
Provides fast access to pre-downloaded fundamental data (financials, earnings).

This service reads from the JSON files created by bulk_download_fundamentals.py
and returns data instantly (0 API calls required).

Usage:
    from app.services.fundamentals_cache import get_fundamentals, is_cached

    # Check if data is cached
    if is_cached("RELIANCE.NS"):
        data = get_fundamentals("RELIANCE.NS")
        print(data["income"])  # Income statement data
        print(data["balance"])  # Balance sheet data
        print(data["cashflow"])  # Cash flow data

Performance:
    - API call: ~2 seconds per ticker
    - Cache hit: <10 milliseconds
"""

import json
import logging
import polars as pl
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache for the master parquet dataframe to avoid reloading
_MASTER_DF = None

# =============================================================================
# PATHS
# =============================================================================

APP_DIR = Path(__file__).parent.parent
BACKEND_ROOT = APP_DIR.parent
DATA_DIR = BACKEND_ROOT / "data"
FUNDAMENTALS_DIR = DATA_DIR / "fundamentals"


def _get_fundamentals_path(ticker: str) -> Path:
    """Get the JSON file path for a ticker's fundamentals."""
    safe_ticker = ticker.replace("^", "_").replace("=", "_")
    return FUNDAMENTALS_DIR / f"{safe_ticker}.json"

def _get_shard_path(ticker: str) -> Path:
    """Get the Parquet shard path for a ticker."""
    # Handle the .NS / _NS transformation used in shards
    safe_ticker = ticker.replace(".", "_")
    return FUNDAMENTALS_DIR / "shards" / f"{safe_ticker}_fin.parquet"


def is_cached(ticker: str) -> bool:
    """Check if fundamental data is cached for a ticker."""
    return _get_fundamentals_path(ticker).exists()


def get_fundamentals(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get fundamental data - PARQUET NATIVE PRIORITY.
    """
    global _MASTER_DF
    
    # 1. TRY PARQUET SHARDS FIRST (The Raw High-Performance Data)
    shard_path = _get_shard_path(ticker)
    master_path = FUNDAMENTALS_DIR / "master_fundamentals.parquet"
    
    ticker_data = None
    
    try:
        if shard_path.exists():
            shard_df = pl.read_parquet(shard_path)
            
            # Build detailed financials from shard
            # Shard columns are flat, but we will smartly categorize them for the frontend
            financials = {"income": {}, "balance": {}, "cashflow": {}}
            
            # Map shard rows (years) to the nested structure frontend expects
            for row in shard_df.to_dicts():
                dt = row.get("reportDate")
                date_key = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                
                # Filter nulls and map fields
                row_clean = {k: v for k, v in row.items() if v is not None}
                
                # 1. ENTIRE ROW Mapping:
                # Instead of guessing, we provide the full row to each category. 
                # The frontend's ratio logic looks for specific keys (e.g., 'Total Assets').
                # By providing the full row, we ensure NO data is left behind.
                financials["income"][date_key] = row_clean
                financials["balance"][date_key] = row_clean
                financials["cashflow"][date_key] = row_clean
            
            # 2. GET METADATA FROM MASTER (Sector, MC, etc.)
            if _MASTER_DF is None and master_path.exists():
                _MASTER_DF = pl.read_parquet(master_path)
            
            meta_row = {}
            if _MASTER_DF is not None:
                meta_df = _MASTER_DF.filter(pl.col("ticker") == ticker)
                if not meta_df.is_empty():
                    meta_row = meta_df.to_dicts()[0]
                    
            ticker_data = {
                "symbol": ticker,
                "source": "parquet_shard",
                "info": {
                    # Metadata & Constants
                    "shortName": meta_row.get("shortName") or meta_row.get("longName") or ticker,
                    "longName": meta_row.get("longName") or meta_row.get("shortName") or ticker,
                    "sector": meta_row.get("sector"),
                    "industry": meta_row.get("industry"),
                    "currency": meta_row.get("currency") or ("INR" if ticker.endswith(".NS") else "USD"),
                    
                    # Key Financial Ratios (The "Screener" Header)
                    "marketCap": meta_row.get("marketCap"),
                    "trailingPE": meta_row.get("trailingPE"),
                    "forwardPE": meta_row.get("forwardPE"),
                    "priceToBook": meta_row.get("priceToBook"),
                    "dividendYield": meta_row.get("dividendYield"),
                    "debtToEquity": meta_row.get("debtToEquity"),
                    "returnOnEquity": meta_row.get("returnOnEquity"),
                    "grossMargins": meta_row.get("grossMargins"),
                    "currentRatio": meta_row.get("currentRatio"),
                    "bookValue": meta_row.get("Total Equity Gross Minority Interest") or meta_row.get("Stockholders Equity"),
                    
                    # Store raw meta row for any other custom ratios
                    "raw_ratios": meta_row
                },
                "income": financials["income"],
                "balance": financials["balance"],
                "cashflow": financials["cashflow"],
                "quarterly_earnings": [] 
            }
            return ticker_data
            
    except Exception as e:
        logger.warning(f"[PARQUET] Failed to load shard for {ticker}: {e}")

    # 3. FALLBACK TO MASTER PARQUET ONLY (If shard missing)
    if ticker_data is None and master_path.exists():
        try:
            if _MASTER_DF is None:
                _MASTER_DF = pl.read_parquet(master_path)
            
            meta_df = _MASTER_DF.filter(pl.col("ticker") == ticker)
            if not meta_df.is_empty():
                 row = meta_df.to_dicts()[0]
                 return {
                    "symbol": ticker,
                    "source": "parquet_master",
                    "info": row,
                    "income": {}, "balance": {}, "cashflow": {},
                    "quarterly_earnings": []
                 }
        except Exception as e:
            logger.warning(f"[PARQUET] Master lookup failed: {e}")

    # 4. TERTIARY FALLBACK: JSON (Old logic)
    json_path = _get_fundamentals_path(ticker)
    if json_path.exists():
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                data["source"] = "json"
                return data
        except Exception as e:
            logger.warning(f"Failed to load JSON fundamentals for {ticker}: {e}")
        
    return None


def get_info(ticker: str) -> Optional[Dict[str, Any]]:
    """Get just the info section from cache."""
    data = get_fundamentals(ticker)
    return data.get("info") if data else None


def get_financials(ticker: str) -> Dict[str, Any]:
    """
    Get financials in the format expected by the Company Analysis frontend.
    
    Returns:
    {
        "income": {"2024-03-31": {...}, ...},
        "balance": {"2024-03-31": {...}, ...},
        "cashflow": {"2024-03-31": {...}, ...}
    }
    """
    data = get_fundamentals(ticker)
    if not data:
        return {}
    
    return {
        "income": data.get("income", {}),
        "balance": data.get("balance", {}),
        "cashflow": data.get("cashflow", {})
    }


def get_quarterly_earnings(ticker: str) -> Dict[str, Any]:
    """
    Get quarterly earnings formatted for frontend.
    
    Returns dict keyed by period date.
    """
    data = get_fundamentals(ticker)
    if not data:
        return {}
    
    quarterly = {}
    for q in data.get("quarterly_earnings", []):
        period = q.get("period")
        if period:
            quarterly[period] = q
    
    return quarterly


def get_cache_age_days(ticker: str) -> Optional[int]:
    """Get how old the cached data is in days."""
    data = get_fundamentals(ticker)
    if not data:
        return None
    
    last_updated = data.get("last_updated")
    if not last_updated:
        return None
    
    try:
        last_dt = datetime.fromisoformat(last_updated)
        return (datetime.now() - last_dt).days
    except:
        return None


def get_cached_tickers() -> list:
    """Get list of all cached tickers."""
    if not FUNDAMENTALS_DIR.exists():
        return []
    
    tickers = []
    for f in FUNDAMENTALS_DIR.glob("*.json"):
        if f.name != "metadata.json":
            # Convert filename back to ticker
            ticker = f.stem.replace("_", "^")  # Rough reverse
            tickers.append(ticker)
    
    return sorted(tickers)


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the fundamentals cache."""
    if not FUNDAMENTALS_DIR.exists():
        return {
            "num_tickers": 0,
            "total_size_mb": 0,
            "cache_dir": str(FUNDAMENTALS_DIR),
            "exists": False
        }
    
    json_files = [f for f in FUNDAMENTALS_DIR.glob("*.json") if f.name != "metadata.json"]
    total_size = sum(f.stat().st_size for f in json_files)
    
    return {
        "num_tickers": len(json_files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cache_dir": str(FUNDAMENTALS_DIR),
        "exists": True
    }
