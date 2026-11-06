"""
Price API
GET/POST endpoints for candle data with caching.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

import numpy as np
import pandas as pd

from ..services.universe import (
    validate_symbols,
    check_limits,
    is_valid_symbol,
    normalize_symbol,
)
from ..services.research_cache import research_cache
from .. import data_loader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["prices"])

def get_prices_daily(ticker: str, lookback_days: int) -> pd.DataFrame:
    """
    Get daily OHLCV data for a ticker.
    
    Args:
        ticker: Stock symbol
        lookback_days: Number of days to fetch
        
    Returns:
        DataFrame with columns: date (index), open, high, low, close, volume
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 30)  # Buffer for weekends/holidays
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Check cache
    cached, hit = research_cache.get_prices(ticker, "1d", start_str, end_str)
    if hit and cached is not None:
        return cached
    
    try:
        df = data_loader.get_price_history(
            [ticker],
            start=start_str,
            end=end_str,
            interval="1d"
        )
        
        if df.empty:
            logger.warning(f"No data for ticker {ticker}")
            return pd.DataFrame()
        
        # Handle MultiIndex columns from yfinance
        if isinstance(df.columns, pd.MultiIndex):
            # Extract columns for this ticker
            result = pd.DataFrame(index=df.index)
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if (col, ticker) in df.columns:
                    result[col.lower()] = df[(col, ticker)]
                elif col in df.columns.get_level_values(0):
                    result[col.lower()] = df.xs(col, axis=1, level=0).iloc[:, 0]
        else:
            result = df.copy()
            result.columns = [c.lower() for c in result.columns]
        
        # Ensure we have required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in result.columns:
                result[col] = np.nan
        
        result = result[required].dropna(subset=['close'])
        
        # Cache the result
        research_cache.set_prices(ticker, "1d", start_str, end_str, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
        return pd.DataFrame()


# ===== Request/Response Models =====

class BatchPricesRequest(BaseModel):
    tickers: List[str] = Field(..., min_items=1, max_items=200)
    interval: str = Field(default="1d")
    lookback_days: int = Field(default=365, ge=1, le=3650)


class CandleData(BaseModel):
    t: str  # timestamp ISO
    o: float  # open
    h: float  # high
    l: float  # low
    c: float  # close
    v: float  # volume


class PricesResponse(BaseModel):
    data: Dict[str, List[Dict[str, Any]]]
    meta: Dict[str, Any]


class SinglePriceResponse(BaseModel):
    candles: List[Dict[str, Any]]
    meta: Dict[str, Any]


# ===== Helper Functions =====

def _format_candles(df) -> List[Dict[str, Any]]:
    """Convert DataFrame to candle list format."""
    if df is None or df.empty:
        return []
    
    candles = []
    for idx, row in df.iterrows():
        candle = {
            "t": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
            "o": round(float(row.get("Open", row.get("open", 0))), 4),
            "h": round(float(row.get("High", row.get("high", 0))), 4),
            "l": round(float(row.get("Low", row.get("low", 0))), 4),
            "c": round(float(row.get("Close", row.get("close", 0))), 4),
            "v": int(row.get("Volume", row.get("volume", 0)) or 0),
        }
        candles.append(candle)
    
    return candles


def _get_cache_key(symbol: str, interval: str, period: str) -> tuple:
    """Generate cache key components including period."""
    return symbol, interval, period, datetime.now().strftime("%Y-%m-%d")


def _get_ttl_seconds(interval: str) -> int:
    """Get TTL based on interval."""
    if interval in ["1m", "5m", "15m", "1h"]:
        return 60  # 1 minute for intraday
    return 900  # 15 minutes for daily


# ===== Endpoints =====

@router.get("/{symbol}", response_model=SinglePriceResponse)
async def get_prices(
    symbol: str,
    interval: str = Query(default="1d", pattern="^(1d|1m|2m|5m|15m|30m|60m|1h)$"),
    lookback_days: int = Query(default=365, ge=1, le=3650),
    period: str = Query(default=None, description="Optional: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y"),
):
    """
    Get price candles for a single symbol.
    Supports all intervals: 1m, 2m, 5m, 15m, 30m, 60m/1h, 1d
    Supports Indian stocks (.NS, .BO) via robust_data_fetcher.
    """
    from ..services.robust_data_fetcher import get_price_data, get_intraday_data
    
    # Normalize and validate
    symbol = normalize_symbol(symbol)
    
    if not is_valid_symbol(symbol):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SYMBOL",
                "message": f"Symbol not in universe: {symbol}",
                "invalid_symbol": symbol
            }
        )
    
    # Determine period based on interval and lookback
    if period:
        data_period = period
    else:
        # Map interval to appropriate period (Yahoo API limits)
        # 1m: max 7 days, 2m-60m: max 60 days, 1h: max 730 days
        if interval == "1m":
            data_period = "7d"  # Yahoo limits 1m to 7 days
        elif interval in ["2m", "5m"]:
            data_period = "60d"  # Last 60 days for 2m/5m
        elif interval in ["15m", "30m", "60m", "1h"]:
            data_period = "60d"  # Last 60 days for intraday hourly
        else:
            # Daily - use lookback_days
            if lookback_days <= 30:
                data_period = "1mo"
            elif lookback_days <= 90:
                data_period = "3mo"
            elif lookback_days <= 180:
                data_period = "6mo"
            elif lookback_days <= 365:
                data_period = "1y"
            elif lookback_days <= 730:
                data_period = "2y"
            else:
                data_period = "5y"
    
    # Check cache - use period in key
    cache_key = _get_cache_key(symbol, interval, data_period)
    cached_data, cache_hit = research_cache.get_prices(*cache_key)
    
    if cache_hit and cached_data is not None:
        return SinglePriceResponse(
            candles=cached_data,
            meta={
                "cache_hit": True,
                "computed_at": datetime.now().isoformat() + "Z",
                "symbol": symbol,
                "interval": interval,
                "period": data_period,
                "provider": "robust_data_fetcher"
            }
        )
    
    # Fetch data using robust_data_fetcher (supports Indian stocks)
    try:
        df = get_price_data(symbol, period=data_period, interval=interval)
        
        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "PRICE_FETCH_FAILED",
                    "message": f"No price data available for {symbol}",
                    "symbol": symbol
                }
            )
        
        candles = _format_candles(df)
        
        # Cache result
        research_cache.set_prices(*cache_key, candles)
        
        return SinglePriceResponse(
            candles=candles,
            meta={
                "cache_hit": False,
                "computed_at": datetime.now().isoformat() + "Z",
                "symbol": symbol,
                "interval": interval,
                "period": data_period,
                "data_points": len(candles),
                "provider": "robust_data_fetcher"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price fetch error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PRICE_FETCH_FAILED",
                "message": str(e),
                "symbol": symbol
            }
        )


@router.post("/batch", response_model=PricesResponse)
async def get_prices_batch(request: BatchPricesRequest):
    """
    Get price candles for multiple symbols.
    """
    tickers = [normalize_symbol(t) for t in request.tickers]
    interval = request.interval
    lookback_days = request.lookback_days
    
    # Validate symbols
    valid, invalid = validate_symbols(tickers, mode="any")
    
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SYMBOL",
                "message": f"Invalid symbols: {', '.join(invalid)}",
                "invalid": invalid
            }
        )
    
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "NO_VALID_SYMBOLS",
                "message": "No valid symbols provided"
            }
        )
    
    # Check limits
    ok, error_msg = check_limits(valid, interval)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "SYMBOL_LIMIT_EXCEEDED",
                "message": error_msg
            }
        )
    
    # Fetch data for each ticker
    data = {}
    cache_hits = 0
    total = len(valid)
    
    for ticker in valid:
        cache_key = _get_cache_key(ticker, interval, lookback_days)
        cached_data, cache_hit = research_cache.get_prices(*cache_key)
        
        if cache_hit and cached_data is not None:
            data[ticker] = cached_data
            cache_hits += 1
        else:
            try:
                df = get_prices_daily(ticker, lookback_days)
                if df is not None and not df.empty:
                    candles = _format_candles(df)
                    data[ticker] = candles
                    research_cache.set_prices(*cache_key, candles)
                else:
                    data[ticker] = []
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                data[ticker] = []
    
    return PricesResponse(
        data=data,
        meta={
            "cache_hit": cache_hits == total,
            "cache_hits": cache_hits,
            "total_symbols": total,
            "computed_at": datetime.now().isoformat() + "Z",
            "interval": interval,
            "lookback_days": lookback_days,
            "provider": "yfinance"
        }
    )
