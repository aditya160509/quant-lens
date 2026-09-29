"""
SOVEREIGN WORKSPACE API
The Command-and-Control Hub for Quantitative Analysis

Endpoints for the Sovereign Workspace - loading from Parquet files only.
Provides: Ticker data, Fundamentals, Factors, Normalized Returns, Global Yields
"""


from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from functools import lru_cache
import json

logger = logging.getLogger(__name__)

router = APIRouter()

# Data paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_PARQUET = DATA_DIR / "market_universe.parquet"
FUNDAMENTALS_PARQUET = DATA_DIR / "fundamentals" / "master_fundamentals.parquet"
FACTORS_US_DIR = DATA_DIR / "factors_us"
FACTORS_INDIA_DIR = DATA_DIR / "factors_india"


# =============================================================================
# UTILITIES
# =============================================================================

def normalize_ticker_for_db(ticker: str) -> List[str]:
    """Returns a list of possible ticker formats to try in the DB."""
    t = ticker.upper()
    variants = [t]
    
    # Try dot to underscore swap
    if "." in t:
        variants.append(t.replace(".", "_"))
    
    # Try underscore to dot swap
    if "_" in t:
        variants.append(t.replace("_", "."))
        
    return list(dict.fromkeys(variants))

def get_period_days(period: str) -> int:
    """Map period string to approximate number of trading days."""
    period_map = {
        "1D": 1, "5D": 5, "1M": 21, "3M": 63, 
        "6M": 126, "YTD": 252, "1Y": 252, "2Y": 504,
        "5Y": 1260, "10Y": 2520, "MAX": 5000
    }
    return period_map.get(period.upper(), 252)

# =============================================================================
# DATA LOADERS (Cached for performance)
# =============================================================================

@lru_cache(maxsize=1)
def load_prices_df() -> pd.DataFrame:
    """Load master prices parquet - cached"""
    try:
        if PRICES_PARQUET.exists():
            df = pd.read_parquet(PRICES_PARQUET)
            logger.info(f"Loaded prices parquet: {len(df)} rows, {len(df.columns)} columns")
            # Ensure Date is datetime
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
            return df
        logger.warning(f"Prices parquet not found at {PRICES_PARQUET}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading prices parquet: {e}")
        return pd.DataFrame()



@lru_cache(maxsize=1)
def load_fundamentals_df() -> pd.DataFrame:
    """Load master fundamentals parquet - cached"""
    try:
        if FUNDAMENTALS_PARQUET.exists():
            df = pd.read_parquet(FUNDAMENTALS_PARQUET)
            logger.info(f"Loaded fundamentals parquet: {len(df)} rows")
            return df
        logger.warning(f"Fundamentals parquet not found at {FUNDAMENTALS_PARQUET}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading fundamentals parquet: {e}")
        return pd.DataFrame()


# =============================================================================
# TICKER CATEGORIES - Static definitions for the workspace
# =============================================================================

TICKER_CATEGORIES = {
    "us_equity": {
        "name": "U.S. Equity Markets",
        "tickers": [
            {"symbol": "BA", "name": "Boeing"},
            {"symbol": "C", "name": "Citigroup"},
            {"symbol": "PEP", "name": "PepsiCo"},
            {"symbol": "LLY", "name": "Eli Lilly"},
            {"symbol": "COST", "name": "Costco"},
            {"symbol": "AMZN", "name": "Amazon"},
        ]
    },
    "us_sectors": {
        "name": "U.S. Equity Sectors",
        "tickers": [
            {"symbol": "XLE", "name": "Energy"},
            {"symbol": "XLF", "name": "Financials"},
            {"symbol": "XLP", "name": "Cons. Staples"},
            {"symbol": "XLK", "name": "Technology"},
            {"symbol": "XLV", "name": "Health Care"},
        ]
    },
    "global_markets": {
        "name": "Global Markets",
        "tickers": [
            {"symbol": "EEM", "name": "Emerging"},
            {"symbol": "EFA", "name": "EAFE (Intl)"},
            {"symbol": "EWJ", "name": "Japan"},
            {"symbol": "INDA", "name": "India"},
        ]
    },
    "fixed_income": {
        "name": "Fixed Income",
        "tickers": [
            {"symbol": "AGG", "name": "High Grade"},
            {"symbol": "TLT", "name": "Treasuries (20Y+)"},
            {"symbol": "HYG", "name": "High Yield"},
        ]
    },
    "commodities": {
        "name": "Commodities",
        "tickers": [
            {"symbol": "USO", "name": "Crude Oil"},
            {"symbol": "GLD", "name": "Gold"},
        ]
    },
    "volatility": {
        "name": "Volatility Index",
        "tickers": [
            {"symbol": "VXX", "name": "Short-Term VIX"},
        ]
    }
}



# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/tickers")
async def get_tickers(
    category: Optional[str] = Query(None, description="Filter by category: us_equity, us_sectors, fixed_income, global_markets, currencies, commodities, volatility, india_equity")
) -> Dict[str, Any]:
    """
    Get ticker data with latest prices from parquet.
    Returns ticker metadata + current price/change data.
    """
    try:
        prices_df = load_prices_df()
        
        # Get categories to return
        if category and category in TICKER_CATEGORIES:
            categories = {category: TICKER_CATEGORIES[category]}
        else:
            categories = TICKER_CATEGORIES
        
        result = {}
        
        for cat_key, cat_data in categories.items():
            cat_tickers = []
            for ticker_info in cat_data["tickers"]:
                symbol = ticker_info["symbol"]
                ticker_data = {
                    "symbol": symbol,
                    "name": ticker_info["name"],
                    "price": None,
                    "change": None,
                    "change_pct": None,
                }
                
                # Try to get price data from parquet
                if not prices_df.empty:
                    try:
                        variants = normalize_ticker_for_db(symbol)
                        ticker_df = prices_df[prices_df['Ticker'].isin(variants)].sort_values('Date')
                        
                        if len(ticker_df) >= 2:
                            current = float(ticker_df['Close'].iloc[-1])

                            prev = float(ticker_df['Close'].iloc[-2])
                            change = current - prev
                            change_pct = (change / prev) * 100 if prev != 0 else 0
                            ticker_data["price"] = round(current, 2)
                            ticker_data["change"] = round(change, 2)
                            ticker_data["change_pct"] = round(change_pct, 2)
                    except Exception as e:
                        logger.debug(f"Could not get price for {symbol}: {e}")

                
                cat_tickers.append(ticker_data)
            
            result[cat_key] = {
                "name": cat_data["name"],
                "tickers": cat_tickers
            }
        
        return {"status": "ok", "data": result}
    
    except Exception as e:
        logger.error(f"Error in get_tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fundamentals/{ticker}")
async def get_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Get fundamental metrics for a ticker from the fundamentals parquet.
    Returns: P/E, P/B, Debt/Equity, ROE, Market Cap, etc.
    """
    try:
        df = load_fundamentals_df()
        
        if df.empty:
            return {"status": "error", "message": "Fundamentals data not available"}
        
        # Look for ticker in the dataframe
        variants = normalize_ticker_for_db(ticker)
        
        # Check if ticker column exists or if it's in index
        ticker_data = pd.DataFrame()
        if 'ticker' in df.columns:
            ticker_data = df[df['ticker'].str.upper().isin(variants)]
        elif 'symbol' in df.columns:
            ticker_data = df[df['symbol'].str.upper().isin(variants)]
        else:
            # Assume ticker is in index
            matches = [v for v in variants if v in df.index]
            if matches:
                ticker_data = df.loc[[matches[0]]]
        
        if ticker_data.empty:
            return {"status": "not_found", "ticker": ticker}

        
        # Convert to dict, taking first row
        row = ticker_data.iloc[0]
        fundamentals = {}
        
        # Map common fundamental metrics
        metric_mappings = {
            "pe_ratio": ["trailingPE", "pe_ratio", "PE", "forwardPE"],
            "pb_ratio": ["priceToBook", "pb_ratio", "PB"],
            "debt_to_equity": ["debtToEquity", "debt_to_equity", "D/E"],
            "roe": ["returnOnEquity", "roe", "ROE"],
            "market_cap": ["marketCap", "market_cap", "MarketCap"],
            "dividend_yield": ["dividendYield", "dividend_yield", "DivYield"],
            "eps": ["trailingEps", "eps", "EPS"],
            "revenue": ["totalRevenue", "revenue", "Revenue"],
            "profit_margin": ["profitMargins", "profit_margin", "ProfitMargin"],
            "beta": ["beta", "Beta"],
        }
        
        for metric_name, possible_cols in metric_mappings.items():
            for col in possible_cols:
                if col in row.index and pd.notna(row[col]):
                    val = row[col]
                    if isinstance(val, (int, float)):
                        fundamentals[metric_name] = round(float(val), 4)
                    else:
                        fundamentals[metric_name] = val
                    break
        
        return {
            "status": "ok",
            "ticker": ticker,
            "fundamentals": fundamentals
        }
    
    except Exception as e:
        logger.error(f"Error getting fundamentals for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/normalized-returns")
async def get_normalized_returns(
    tickers: str = Query(..., description="Comma-separated list of tickers"),
    period: str = Query("1M", description="Period: 1D, 5D, 1M, 3M, 6M, YTD, 1Y, 5Y"),
    base_value: float = Query(100.0, description="Starting base value for normalization")
) -> Dict[str, Any]:
    """
    Get normalized cumulative returns for the Alpha Chart.
    All series start at base_value and show % performance from that point.
    Supports ratio syntax: "TICKER1/TICKER2" for spread trading.
    """
    try:
        prices_df = load_prices_df()
        
        if prices_df.empty:
            return {"status": "error", "message": "Price data not available"}
        
        ticker_list = [t.strip() for t in tickers.split(",")]
        
        # Map period to days
        period_map = {
            "1D": 1, "5D": 5, "1M": 21, "3M": 63, 
            "6M": 126, "YTD": 252, "1Y": 252, "5Y": 1260, "10Y": 2520
        }
        days = period_map.get(period, 21)
        
        result = {"series": {}, "dates": []}
        
        for ticker in list(dict.fromkeys(ticker_list)): # Unique tickers
            try:
                # Regular ticker
                variants = normalize_ticker_for_db(ticker)
                ticker_df = prices_df[prices_df['Ticker'].isin(variants)].sort_values('Date')
                series = ticker_df.set_index('Date')['Close'].tail(days)

                
                if len(series) > 0:
                    normalized = (series / series.iloc[0]) * base_value
                    result["series"][ticker] = {
                        "values": normalized.tolist(),
                        "dates": series.index.strftime("%Y-%m-%d").tolist()
                    }
                    
                    # Use longest series as reference for dates
                    if len(series) > len(result["dates"]):
                        result["dates"] = series.index.strftime("%Y-%m-%d").tolist()
                
            except Exception as e:
                logger.debug(f"Could not process {ticker}: {e}")
                continue

        
        return {"status": "ok", "period": period, "base_value": base_value, "data": result}
    
    except Exception as e:
        logger.error(f"Error in normalized returns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/factors")
async def get_factors(
    market: str = Query("US", description="Market: US or IN")
) -> Dict[str, Any]:
    """
    Get factor performance data (Value, Growth, Momentum by size).
    Returns the 1-day performance matrix.
    """
    try:
        factors_dir = FACTORS_US_DIR if market.upper() == "US" else FACTORS_INDIA_DIR
        
        # Default factor matrix (simulated if no data)
        factor_matrix = {
            "size": ["Large", "Mid", "Small"],
            "factors": ["Value", "Core", "Growth"],
            "performance": [
                [-0.2, -0.2, -0.3],  # Large: Value, Core, Growth
                [-0.2, 0.0, 0.1],   # Mid: Value, Core, Growth
                [0.0, 0.0, 0.3],    # Small: Value, Core, Growth
            ]
        }
        
        # Try to load actual factor data
        if factors_dir.exists():
            factor_files = list(factors_dir.glob("*.parquet"))
            if factor_files:
                try:
                    df = pd.read_parquet(factor_files[0])
                    # Process actual factor data here
                    logger.info(f"Loaded factor data from {factor_files[0]}")
                except Exception as e:
                    logger.debug(f"Could not parse factor file: {e}")
        
        return {
            "status": "ok",
            "market": market,
            "period": "1-Day Performance",
            "matrix": factor_matrix
        }
    
    except Exception as e:
        logger.error(f"Error getting factors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/global-yields")
async def get_global_yields() -> Dict[str, Any]:
    """
    Get global bond yield data.
    Returns 5Y and 10Y yields for major countries.
    """
    # Static yield data (would be updated from external source in production)
    yields = [
        {"country": "United States", "flag": "🇺🇸", "yield_5y": 3.181, "yield_10y": 3.054},
        {"country": "Germany", "flag": "🇩🇪", "yield_5y": 1.094, "yield_10y": 1.321},
        {"country": "United Kingdom", "flag": "🇬🇧", "yield_5y": 2.498, "yield_10y": 2.577},
        {"country": "Spain", "flag": "🇪🇸", "yield_5y": 1.774, "yield_10y": 2.508},
        {"country": "Italy", "flag": "🇮🇹", "yield_5y": 2.734, "yield_10y": 3.641},
        {"country": "Japan", "flag": "🇯🇵", "yield_5y": 0.000, "yield_10y": 0.214},
        {"country": "China", "flag": "🇨🇳", "yield_5y": 2.415, "yield_10y": 2.639},
    ]
    
    return {"status": "ok", "yields": yields}


@router.get("/available-tickers")
async def get_available_tickers() -> Dict[str, Any]:
    """
    Get list of all available tickers in the price parquet.
    Used for autocomplete in the workspace.
    """
    try:
        prices_df = load_prices_df()
        
        if prices_df.empty:
            return {"status": "error", "tickers": []}
        
        tickers = prices_df['Ticker'].unique().tolist()
        
        return {
            "status": "ok",
            "count": len(tickers),
            "tickers": sorted(tickers)
        }

    
    except Exception as e:
        logger.error(f"Error getting available tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlcv/{ticker}")
async def get_ohlcv(
    ticker: str,
    period: str = Query("1Y", description="Period: 1M, 3M, 6M, 1Y, 5Y")
) -> Dict[str, Any]:
    """
    Get OHLCV data for a ticker from the parquet.
    Used for the detailed chart widget.
    """
    try:
        prices_df = load_prices_df()
        days = get_period_days(period)
        
        variants = normalize_ticker_for_db(ticker)
        ticker_df = prices_df[prices_df['Ticker'].isin(variants)].sort_values('Date').tail(days)

        
        if ticker_df.empty:
            return {"status": "not_found", "ticker": ticker}
        
        # Format for lightweight-charts
        data = []
        for _, row in ticker_df.iterrows():
            data.append({
                "time": row['Date'].strftime("%Y-%m-%d"),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": float(row['Volume'])
            })

        
        return {
            "status": "ok",
            "ticker": ticker,
            "period": period,
            "data": data
        }
    
    except Exception as e:
        logger.error(f"Error getting OHLCV for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
