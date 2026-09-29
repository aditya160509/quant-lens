"""
Centralized YFinance Wrapper with Rate Limiting and Caching
Use this instead of importing yfinance directly to avoid 429 errors.
"""

import yfinance as yf
import pandas as pd
from typing import Optional, Dict, Any, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from functools import lru_cache
import time

from app.services.rate_limiter import (
    yfinance_limiter, 
    global_cache, 
    backoff_handler,
    get_cache_stats
)

logger = logging.getLogger(__name__)

# Thread pool for sync yfinance calls
_executor = ThreadPoolExecutor(max_workers=3)


class YFinanceWrapper:
    """
    Rate-limited wrapper for yfinance.
    Implements caching and backoff to prevent 429 errors.
    """
    
    # Cache TTLs for different data types (increased to avoid rate limiting)
    TTL_PRICE_DATA = 300   # 5 minutes for price data
    TTL_INFO = 900         # 15 minutes for stock info
    TTL_HISTORICAL = 1800  # 30 minutes for historical data  
    TTL_OPTIONS = 600      # 10 minutes for options
    TTL_FINANCIALS = 3600  # 1 hour for financials
    
    @staticmethod
    def _make_cache_key(method: str, symbol: str, **kwargs) -> str:
        """Create a cache key"""
        import hashlib
        import json
        key_data = f"{method}:{symbol}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @classmethod
    def _check_rate_limit(cls) -> bool:
        """Check if we should proceed with the request"""
        return yfinance_limiter.try_acquire()
    
    @classmethod
    async def _wait_for_rate_limit(cls):
        """Wait for rate limit token"""
        await yfinance_limiter.acquire()
    
    @classmethod
    def get_ticker_info(cls, symbol: str) -> Optional[Dict]:
        """
        Get ticker info with caching.
        Returns cached data if available, even if stale.
        """
        cache_key = cls._make_cache_key('info', symbol)
        
        # Check backoff
        if backoff_handler.should_skip(cache_key):
            cached, _ = global_cache.get(cache_key)
            if cached:
                logger.debug(f"[YF] Returning cached info for {symbol} (backoff)")
                return cached
            return None
        
        # Check cache
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh:
            return cached
        
        # Rate limit check
        if not cls._check_rate_limit():
            if cached:
                logger.debug(f"[YF] Rate limited, returning stale data for {symbol}")
                return cached
            logger.warning(f"[YF] Rate limited, no cached data for {symbol}")
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if info:
                global_cache.set(cache_key, info, cls.TTL_INFO)
                backoff_handler.record_success(cache_key)
            return info
        except Exception as e:
            logger.error(f"[YF] Error getting info for {symbol}: {e}")
            backoff_handler.record_error(cache_key)
            return cached  # Return stale data
    
    @classmethod
    def get_history(
        cls, 
        symbol: str, 
        period: str = "1y", 
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data with caching.
        """
        cache_key = cls._make_cache_key('history', symbol, period=period, interval=interval)
        
        # Check backoff
        if backoff_handler.should_skip(cache_key):
            cached, _ = global_cache.get(cache_key)
            if cached is not None:
                return cached
            return None
        
        # Check cache
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh:
            return cached
        
        # Rate limit
        if not cls._check_rate_limit():
            if cached is not None:
                return cached
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df is not None and not df.empty:
                global_cache.set(cache_key, df, cls.TTL_HISTORICAL)
                backoff_handler.record_success(cache_key)
            return df
        except Exception as e:
            logger.error(f"[YF] Error getting history for {symbol}: {e}")
            backoff_handler.record_error(cache_key)
            return cached

    @classmethod
    def get_earnings_history(cls, symbol: str) -> Optional[pd.DataFrame]:
        """Get earnings history with caching."""
        cache_key = cls._make_cache_key('earnings_history', symbol)
        
        if backoff_handler.should_skip(cache_key):
            cached, _ = global_cache.get(cache_key)
            return cached
            
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh: return cached
        
        if not cls._check_rate_limit():
            return cached
            
        try:
            ticker = yf.Ticker(symbol)
            eh = ticker.earnings_history
            if eh is not None and not eh.empty:
                global_cache.set(cache_key, eh, cls.TTL_FINANCIALS)
                backoff_handler.record_success(cache_key)
            return eh
        except Exception as e:
            logger.error(f"[YF] Error getting earnings history for {symbol}: {e}")
            backoff_handler.record_error(cache_key)
            return cached

    @classmethod
    def get_recommendations(cls, symbol: str) -> Optional[pd.DataFrame]:
        """Get analyst recommendations with caching."""
        cache_key = cls._make_cache_key('recommendations', symbol)
        
        if backoff_handler.should_skip(cache_key):
            cached, _ = global_cache.get(cache_key)
            return cached
            
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh: return cached
        
        if not cls._check_rate_limit():
            return cached
            
        try:
            ticker = yf.Ticker(symbol)
            recs = ticker.recommendations
            if recs is not None and not recs.empty:
                global_cache.set(cache_key, recs, cls.TTL_INFO)
                backoff_handler.record_success(cache_key)
            return recs
        except Exception as e:
            logger.error(f"[YF] Error getting recommendations for {symbol}: {e}")
            backoff_handler.record_error(cache_key)
            return cached

    @classmethod
    def get_institutional_holders(cls, symbol: str) -> Optional[pd.DataFrame]:
        """Get institutional holders with caching."""
        cache_key = cls._make_cache_key('institutional', symbol)
        
        if backoff_handler.should_skip(cache_key):
            cached, _ = global_cache.get(cache_key)
            return cached
            
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh: return cached
        
        if not cls._check_rate_limit():
            return cached
            
        try:
            ticker = yf.Ticker(symbol)
            inst = ticker.institutional_holders
            if inst is not None and not inst.empty:
                global_cache.set(cache_key, inst, cls.TTL_FINANCIALS)
                backoff_handler.record_success(cache_key)
            return inst
        except Exception as e:
            logger.error(f"[YF] Error getting institutional holders for {symbol}: {e}")
            backoff_handler.record_error(cache_key)
            return cached
    
    @classmethod
    def get_current_price(cls, symbol: str) -> Optional[float]:
        """Get current price (uses info endpoint)"""
        info = cls.get_ticker_info(symbol)
        if info:
            return info.get('currentPrice') or info.get('regularMarketPrice')
        return None
    
    @classmethod
    def get_options_chain(cls, symbol: str, date: str = None) -> Optional[Dict]:
        """Get options chain with caching"""
        cache_key = cls._make_cache_key('options', symbol, date=date)
        
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh:
            return cached
        
        if not cls._check_rate_limit():
            if cached:
                return cached
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            if date:
                chain = ticker.option_chain(date)
            else:
                dates = ticker.options
                if not dates:
                    return None
                chain = ticker.option_chain(dates[0])
            
            result = {
                'calls': chain.calls.to_dict('records') if chain.calls is not None else [],
                'puts': chain.puts.to_dict('records') if chain.puts is not None else [],
                'expiry': date or (dates[0] if dates else None)
            }
            global_cache.set(cache_key, result, cls.TTL_OPTIONS)
            return result
        except Exception as e:
            logger.error(f"[YF] Error getting options for {symbol}: {e}")
            return cached
    
    @classmethod
    async def get_multiple_tickers(cls, symbols: List[str], data_type: str = 'info') -> Dict[str, Any]:
        """
        Get data for multiple tickers with rate limiting.
        Batches requests to avoid overwhelming the API.
        """
        results = {}
        batch_size = 3  # Small batch to avoid rate limits
        delay_between_batches = 2.0  # 2 seconds between batches
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            
            # Process batch
            for symbol in batch:
                await cls._wait_for_rate_limit()
                
                if data_type == 'info':
                    results[symbol] = cls.get_ticker_info(symbol)
                elif data_type == 'price':
                    results[symbol] = cls.get_current_price(symbol)
                elif data_type == 'history':
                    results[symbol] = cls.get_history(symbol)
            
            # Delay between batches
            if i + batch_size < len(symbols):
                await asyncio.sleep(delay_between_batches)
        
        return results


# ===================== ASYNC WRAPPERS =====================

async def async_get_ticker_info(symbol: str) -> Optional[Dict]:
    """Async wrapper for get_ticker_info"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, YFinanceWrapper.get_ticker_info, symbol)


async def async_get_history(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Async wrapper for get_history"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, 
        lambda: YFinanceWrapper.get_history(symbol, period, interval)
    )


async def async_get_options(symbol: str) -> Optional[Dict]:
    """Async wrapper for get_options_chain"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, YFinanceWrapper.get_options_chain, symbol)


# ===================== CONVENIENCE FUNCTIONS =====================

def yf_info(symbol: str) -> Optional[Dict]:
    """Get ticker info (shorthand)"""
    return YFinanceWrapper.get_ticker_info(symbol)


def yf_history(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Get history (shorthand)"""
    return YFinanceWrapper.get_history(symbol, period, interval)


def yf_price(symbol: str) -> Optional[float]:
    """Get current price (shorthand)"""
    return YFinanceWrapper.get_current_price(symbol)


def yf_options(symbol: str) -> Optional[Dict]:
    """Get options chain (shorthand)"""
    return YFinanceWrapper.get_options_chain(symbol)


# ===================== STATS =====================

def get_yf_stats() -> dict:
    """Get yfinance wrapper statistics"""
    return get_cache_stats()


# ===================== BULK DATA DOWNLOAD =====================

async def get_cached_yf_data(
    tickers: List[str],
    period: str = "1y",
    interval: str = "1d"
) -> Optional[pd.DataFrame]:
    """
    Get OHLCV data for multiple tickers using yf.download.
    Implements caching and rate limiting for bulk requests.
    Used by Market Labs for universe-wide data.
    """
    import hashlib
    
    # Create cache key
    tickers_sorted = sorted(tickers)
    key_str = f"bulk:{','.join(tickers_sorted[:10])}...{len(tickers)}:{period}:{interval}"
    cache_key = hashlib.md5(key_str.encode()).hexdigest()
    
    # Check cache first
    cached, is_fresh = global_cache.get(cache_key)
    if is_fresh and cached is not None:
        logger.debug(f"[YF] Returning cached bulk data for {len(tickers)} tickers")
        return cached
    
    # Check backoff
    if backoff_handler.should_skip(cache_key):
        if cached is not None:
            logger.debug(f"[YF] Backoff active, returning stale bulk data")
            return cached
        return None
    
    # Rate limit check
    if not yfinance_limiter.try_acquire():
        if cached is not None:
            logger.debug(f"[YF] Rate limited, returning stale bulk data")
            return cached
        logger.warning(f"[YF] Rate limited, no cached bulk data available")
        return None
    
    try:
        logger.info(f"[YF] Downloading bulk data for {len(tickers)} tickers")
        
        # Use yf.download for efficiency
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            _executor,
            lambda: yf.download(
                tickers,
                period=period,
                interval=interval,
                group_by='column',
                auto_adjust=True,
                threads=True,
                progress=False
            )
        )
        
        if df is not None and not df.empty:
            # Cache for 60 minutes (increased to avoid rate limiting)
            global_cache.set(cache_key, df, 3600)
            backoff_handler.record_success(cache_key)
            logger.info(f"[YF] Downloaded {len(df)} rows for {len(tickers)} tickers")
        
        return df
        
    except Exception as e:
        logger.error(f"[YF] Error downloading bulk data: {e}")
        backoff_handler.record_error(cache_key)
        return cached  # Return stale data if available

