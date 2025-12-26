"""
Quotes API
Quick quote endpoints for Monitor panels with sparkline data.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..services.universe import (
    validate_symbols,
    is_valid_symbol,
    normalize_symbol,
    get_symbol_info,
)
from ..services.research_cache import research_cache
from ..services.research_data import get_prices_daily

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

# ===== Request/Response Models =====

class BatchQuotesRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1, max_items=50)
    interval: str = Field(default="1d")


class QuoteData(BaseModel):
    symbol: str
    price: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    sparkline: List[float]
    timestamp: str


class SingleQuoteResponse(BaseModel):
    quote: Dict[str, Any]
    meta: Dict[str, Any]


class BatchQuotesResponse(BaseModel):
    quotes: Dict[str, Dict[str, Any]]
    meta: Dict[str, Any]


# ===== Helper Functions =====

QUOTE_CACHE_TTL = 5  # 5 seconds for quotes

def _get_quote_cache_key(symbol: str, interval: str) -> str:
    """Generate cache key for quotes."""
    return f"quote|{symbol}|{interval}"


def _calculate_quote(df, symbol: str) -> Dict[str, Any]:
    """Calculate quote data from price DataFrame."""
    if df is None or df.empty:
        return {
            "symbol": symbol,
            "price": None,
            "change": None,
            "change_pct": None,
            "volume": None,
            "sparkline": [],
            "timestamp": datetime.now().isoformat() + "Z"
        }
    
    # Get latest data
    latest = df.iloc[-1]
    current_price = float(latest.get("Close", latest.get("close", 0)))
    volume = int(latest.get("Volume", latest.get("volume", 0)) or 0)
    
    # Calculate change from previous close
    if len(df) >= 2:
        prev = df.iloc[-2]
        prev_close = float(prev.get("Close", prev.get("close", 0)))
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
    else:
        change = 0
        change_pct = 0
    
    # Generate sparkline (last 20 closes)
    sparkline_data = df.tail(20)
    sparkline = []
    for _, row in sparkline_data.iterrows():
        close = float(row.get("Close", row.get("close", 0)))
        sparkline.append(round(close, 2))
    
    # Get symbol info for display
    info = get_symbol_info(symbol)
    
    return {
        "symbol": symbol,
        "display": info.get("display", symbol) if info else symbol,
        "exchange": info.get("exchange", "US") if info else "US",
        "price": round(current_price, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 2),
        "volume": volume,
        "sparkline": sparkline,
        "timestamp": datetime.now().isoformat() + "Z"
    }


# ===== Endpoints =====

@router.get("/{symbol}", response_model=SingleQuoteResponse)
async def get_quote(
    symbol: str,
    interval: str = Query(default="1d", regex="^(1d|1m|5m|15m|1h)$"),
):
    """
    Get quick quote for a single symbol.
    """
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
    
    # Check quote cache (short TTL)
    cache_key = _get_quote_cache_key(symbol, interval)
    cached, cache_hit = research_cache.get_compute({"_quote_key": cache_key})
    
    if cache_hit and cached is not None:
        return SingleQuoteResponse(
            quote=cached,
            meta={
                "cache_hit": True,
                "computed_at": datetime.now().isoformat() + "Z",
                "symbol": symbol,
                "interval": interval
            }
        )
    
    # Fetch recent prices
    try:
        df = get_prices_daily(symbol, lookback_days=30)
        quote = _calculate_quote(df, symbol)
        
        # Cache with short TTL
        research_cache.set_compute({"_quote_key": cache_key}, quote)
        
        return SingleQuoteResponse(
            quote=quote,
            meta={
                "cache_hit": False,
                "computed_at": datetime.now().isoformat() + "Z",
                "symbol": symbol,
                "interval": interval,
                "provider": "yfinance"
            }
        )
        
    except Exception as e:
        logger.error(f"Quote fetch error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "QUOTE_FETCH_FAILED",
                "message": str(e),
                "symbol": symbol
            }
        )


@router.post("/batch", response_model=BatchQuotesResponse)
async def get_quotes_batch(request: BatchQuotesRequest):
    """
    Get quotes for multiple symbols.
    """
    symbols = [normalize_symbol(s) for s in request.symbols]
    interval = request.interval
    
    # Validate symbols
    valid, invalid = validate_symbols(symbols, mode="any")
    
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "NO_VALID_SYMBOLS",
                "message": "No valid symbols provided",
                "invalid": invalid
            }
        )
    
    quotes = {}
    cache_hits = 0
    
    for symbol in valid:
        cache_key = _get_quote_cache_key(symbol, interval)
        cached, cache_hit = research_cache.get_compute({"_quote_key": cache_key})
        
        if cache_hit and cached is not None:
            quotes[symbol] = cached
            cache_hits += 1
        else:
            try:
                df = get_prices_daily(symbol, lookback_days=30)
                quote = _calculate_quote(df, symbol)
                quotes[symbol] = quote
                research_cache.set_compute({"_quote_key": cache_key}, quote)
            except Exception as e:
                logger.warning(f"Failed to get quote for {symbol}: {e}")
                quotes[symbol] = {
                    "symbol": symbol,
                    "error": str(e),
                    "price": None,
                    "sparkline": []
                }
    
    return BatchQuotesResponse(
        quotes=quotes,
        meta={
            "cache_hit": cache_hits == len(valid),
            "cache_hits": cache_hits,
            "total_symbols": len(valid),
            "computed_at": datetime.now().isoformat() + "Z",
            "interval": interval,
            "invalid_symbols": invalid if invalid else None
        }
    )
