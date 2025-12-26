"""
Price API
GET/POST endpoints for candle data with caching.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

from ..services.universe import (
    validate_symbols,
    check_limits,
    is_valid_symbol,
    normalize_symbol,
)
from ..services.research_cache import research_cache
from ..services.research_data import get_prices_daily, get_prices_multi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["prices"])

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


def _get_cache_key(symbol: str, interval: str, lookback_days: int) -> tuple:
    """Generate cache key components."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    return symbol, interval, start, end


def _get_ttl_seconds(interval: str) -> int:
    """Get TTL based on interval."""
    if interval in ["1m", "5m", "15m", "1h"]:
        return 60  # 1 minute for intraday
    return 900  # 15 minutes for daily


# ===== Endpoints =====

@router.get("/{symbol}", response_model=SinglePriceResponse)
async def get_prices(
    symbol: str,
    interval: str = Query(default="1d", regex="^(1d|1m|5m|15m|1h)$"),
    lookback_days: int = Query(default=365, ge=1, le=3650),
):
    """
    Get price candles for a single symbol.
    """
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
    
    # Check cache
    cache_key = _get_cache_key(symbol, interval, lookback_days)
    cached_data, cache_hit = research_cache.get_prices(*cache_key)
    
    if cache_hit and cached_data is not None:
        return SinglePriceResponse(
            candles=cached_data,
            meta={
                "cache_hit": True,
                "computed_at": datetime.now().isoformat() + "Z",
                "symbol": symbol,
                "interval": interval,
                "lookback_days": lookback_days,
                "provider": "yfinance"
            }
        )
    
    # Fetch data
    try:
        # Note: get_prices_daily currently only supports daily
        # For intraday, would need to extend fetch logic
        if interval != "1d":
            # For now, fall back to daily with a note
            df = get_prices_daily(symbol, lookback_days)
            interval_note = "intraday_unsupported_using_daily"
        else:
            df = get_prices_daily(symbol, lookback_days)
            interval_note = None
        
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
        
        meta = {
            "cache_hit": False,
            "computed_at": datetime.now().isoformat() + "Z",
            "symbol": symbol,
            "interval": interval,
            "lookback_days": lookback_days,
            "data_points": len(candles),
            "provider": "yfinance"
        }
        if interval_note:
            meta["note"] = interval_note
        
        return SinglePriceResponse(candles=candles, meta=meta)
        
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
