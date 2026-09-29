"""
Centralized Index & VIX Caching Layer
=====================================
This module provides cached access to commonly used indices and market data.
Reduces yfinance API calls to nearly ZERO by:
1. Aggressive memory caching with smart TTLs
2. Disk persistence via robust_data_fetcher
3. Batch fetching for multiple symbols
4. Pre-computed regime/volatility data

Usage:
    from app.services.index_cache import (
        get_vix_data, get_spy_data, get_index_batch,
        get_market_regime_data, get_change_data
    )
"""

import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

# Memory cache TTL (seconds) - different for different data types
TTL_REALTIME = 120        # 2 minutes for real-time quotes
TTL_HISTORICAL = 3600     # 1 hour for historical data
TTL_REGIME = 1800         # 30 minutes for regime data
TTL_EXTENDED = 14400      # 4 hours for non-market hours

# =============================================================================
# MEMORY CACHE IMPLEMENTATION
# =============================================================================

class IndexCache:
    """Thread-safe cache for index data with smart TTL."""
    
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float, int]] = {}  # key -> (data, timestamp, ttl)
        self._lock = Lock()
        self._stats = {"hits": 0, "misses": 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data if fresh."""
        with self._lock:
            if key in self._cache:
                data, timestamp, ttl = self._cache[key]
                if time.time() - timestamp < ttl:
                    self._stats["hits"] += 1
                    return data
            self._stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = TTL_REALTIME):
        """Set cache value with TTL."""
        with self._lock:
            self._cache[key] = (value, time.time(), ttl)
    
    def get_stale(self, key: str) -> Optional[Any]:
        """Get cached data even if stale (for fallback)."""
        with self._lock:
            if key in self._cache:
                return self._cache[key][0]
            return None
    
    def clear(self):
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate * 100, 1),
                "size": len(self._cache)
            }

# Global cache instance
_index_cache = IndexCache()

# =============================================================================
# SMART TTL CALCULATION
# =============================================================================

def _get_smart_ttl(is_realtime: bool = False) -> int:
    """
    Calculate smart TTL based on market hours.
    During market hours: shorter TTL for fresher data
    After hours/weekend: longer TTL to reduce calls
    """
    try:
        import pytz
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        hour = now.hour
        weekday = now.weekday()
        
        # Weekend - very long TTL
        if weekday >= 5:
            return TTL_EXTENDED
        
        # Market hours (9:30 AM - 4:00 PM ET)
        if (hour == 9 and now.minute >= 30) or (10 <= hour < 16):
            return TTL_REALTIME if is_realtime else TTL_HISTORICAL // 2
        
        # Extended hours
        if 4 <= hour < 20:
            return TTL_HISTORICAL
        
        # Night
        return TTL_EXTENDED
        
    except Exception:
        return TTL_REALTIME if is_realtime else TTL_HISTORICAL

# =============================================================================
# COMMONLY USED INDEX DEFINITIONS
# =============================================================================

# Major indices (always cached aggressively)
MAJOR_INDICES = {
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "DIA": "Dow Jones ETF",
    "IWM": "Russell 2000 ETF",
    "^VIX": "VIX Volatility Index",
    "^GSPC": "S&P 500 Index",
    "^DJI": "Dow Jones Index",
    "^IXIC": "Nasdaq Composite",
}

# Indian indices
INDIA_INDICES = {
    "^NSEI": "Nifty 50",
    "^BSESN": "Sensex",
    "^NSEBANK": "Bank Nifty",
    "^INDIAVIX": "India VIX",
}

# FX pairs
FX_PAIRS = {
    "USDINR=X": "USD/INR",
    "EURUSD=X": "EUR/USD",
    "DX-Y.NYB": "DXY",
}

# Crypto
CRYPTO = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
}

# Macro indicators
MACRO = {
    "^TNX": "US 10Y Yield",
    "GC=F": "Gold Futures",
    "CL=F": "Crude Oil",
    "BZ=F": "Brent Oil",
    "GLD": "Gold ETF",
    "TLT": "20Y Treasury ETF",
}

# All commonly used symbols (for batch warming)
ALL_COMMON_SYMBOLS = list(MAJOR_INDICES.keys()) + list(INDIA_INDICES.keys()) + \
                     list(FX_PAIRS.keys()) + list(CRYPTO.keys()) + list(MACRO.keys())

# =============================================================================
# MAIN PUBLIC API - GET DATA FUNCTIONS
# =============================================================================

def get_vix_data(period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
    """
    Get VIX data with aggressive caching.
    
    This is the SINGLE SOURCE for VIX data in the entire codebase.
    Reduces redundant yfinance calls for VIX to nearly zero.
    """
    cache_key = f"vix_{period}"
    
    if use_cache:
        cached = _index_cache.get(cache_key)
        if cached is not None:
            logger.debug("[IndexCache] VIX cache hit")
            return cached
    
    # Get from robust_data_fetcher (which has its own caching)
    try:
        from app.services.robust_data_fetcher import get_price_data
        df = get_price_data("^VIX", period=period)
        
        if df is not None and not df.empty:
            ttl = _get_smart_ttl(is_realtime=(period == "2d"))
            _index_cache.set(cache_key, df, ttl)
            logger.info(f"[IndexCache] VIX data cached: {len(df)} rows, TTL={ttl}s")
            return df
    except Exception as e:
        logger.warning(f"[IndexCache] VIX fetch error: {e}")
    
    # Return stale data if available
    stale = _index_cache.get_stale(cache_key)
    if stale is not None:
        logger.warning("[IndexCache] Returning stale VIX data")
        return stale
    
    return pd.DataFrame()


def get_spy_data(period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
    """Get SPY data with aggressive caching."""
    return get_index_data("SPY", period=period, use_cache=use_cache)


def get_index_data(symbol: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
    """
    Get data for any index symbol with caching.
    
    Args:
        symbol: Ticker symbol (e.g., "SPY", "^VIX", "^NSEI")
        period: Data period
        use_cache: Whether to use cache
        
    Returns:
        DataFrame with OHLCV data
    """
    cache_key = f"index_{symbol}_{period}"
    
    if use_cache:
        cached = _index_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[IndexCache] {symbol} cache hit")
            return cached
    
    try:
        from app.services.robust_data_fetcher import get_price_data
        df = get_price_data(symbol, period=period)
        
        if df is not None and not df.empty:
            ttl = _get_smart_ttl(is_realtime=(period in ["1d", "2d", "5d"]))
            _index_cache.set(cache_key, df, ttl)
            return df
    except Exception as e:
        logger.warning(f"[IndexCache] {symbol} fetch error: {e}")
    
    # Return stale data if available
    stale = _index_cache.get_stale(cache_key)
    if stale is not None:
        return stale
    
    return pd.DataFrame()


def get_index_batch(
    symbols: List[str], 
    period: str = "5d", 
    use_cache: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Get multiple index data in a batch with caching.
    
    This is optimized for the monitor page which needs multiple tickers.
    Returns a dict of {symbol: DataFrame}.
    """
    cache_key = f"batch_{'_'.join(sorted(symbols)[:10])}_{period}"
    
    if use_cache:
        cached = _index_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[IndexCache] Batch cache hit for {len(symbols)} symbols")
            return cached
    
    try:
        from app.services.robust_data_fetcher import get_batch_data
        result = get_batch_data(symbols, period=period, batch_size=10)
        
        if result:
            ttl = _get_smart_ttl(is_realtime=(period in ["1d", "2d", "5d"]))
            _index_cache.set(cache_key, result, ttl)
            return result
    except Exception as e:
        logger.warning(f"[IndexCache] Batch fetch error: {e}")
    
    # Return stale or empty
    stale = _index_cache.get_stale(cache_key)
    return stale if stale else {}


# =============================================================================
# DERIVED DATA FUNCTIONS (Computed from cached data)
# =============================================================================

def get_vix_level() -> Tuple[float, float, float]:
    """
    Get current VIX level, change, and change percent.
    
    Returns: (last, change, change_pct)
    """
    cache_key = "vix_level"
    cached = _index_cache.get(cache_key)
    if cached is not None:
        return cached
    
    df = get_vix_data(period="5d")
    if df.empty or len(df) < 2:
        return (0.0, 0.0, 0.0)
    
    last = float(df['Close'].iloc[-1])
    prev = float(df['Close'].iloc[-2])
    change = last - prev
    change_pct = (change / prev * 100) if prev != 0 else 0
    
    result = (round(last, 2), round(change, 2), round(change_pct, 2))
    _index_cache.set(cache_key, result, TTL_REALTIME)
    return result


def get_change_data(symbol: str, period: str = "2d") -> Dict[str, float]:
    """
    Get price change data for a symbol.
    
    Returns: {"last": float, "change": float, "changePct": float}
    """
    cache_key = f"change_{symbol}_{period}"
    cached = _index_cache.get(cache_key)
    if cached is not None:
        return cached
    
    df = get_index_data(symbol, period=period)
    
    if df.empty:
        return {"last": 0, "change": 0, "changePct": 0, "error": "no_data"}
    
    if len(df) >= 2:
        last = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = last - prev
        change_pct = (change / prev * 100) if prev != 0 else 0
    elif len(df) == 1:
        last = float(df['Close'].iloc[-1])
        change = 0
        change_pct = 0
    else:
        return {"last": 0, "change": 0, "changePct": 0, "error": "insufficient_data"}
    
    result = {
        "last": round(last, 4 if "=" in symbol else 2),
        "change": round(change, 4 if "=" in symbol else 2),
        "changePct": round(change_pct, 2)
    }
    
    _index_cache.set(cache_key, result, TTL_REALTIME)
    return result


def get_batch_change_data(symbols: List[str], period: str = "5d") -> Dict[str, Dict[str, float]]:
    """
    Get change data for multiple symbols efficiently.
    
    Returns: {symbol: {"last", "change", "changePct"}}
    """
    cache_key = f"batch_change_{'_'.join(sorted(symbols)[:10])}_{period}"
    cached = _index_cache.get(cache_key)
    if cached is not None:
        return cached
    
    batch_data = get_index_batch(symbols, period=period)
    result = {}
    
    for symbol, df in batch_data.items():
        if df is None or df.empty:
            result[symbol] = {"last": 0, "change": 0, "changePct": 0, "error": "no_data"}
            continue
        
        if len(df) >= 2:
            last = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2])
            change = last - prev
            change_pct = (change / prev * 100) if prev != 0 else 0
        elif len(df) == 1:
            last = float(df['Close'].iloc[-1])
            change = 0
            change_pct = 0
        else:
            result[symbol] = {"last": 0, "change": 0, "changePct": 0, "error": "insufficient_data"}
            continue
        
        result[symbol] = {
            "last": round(last, 4 if "=" in symbol else 2),
            "change": round(change, 4 if "=" in symbol else 2),
            "changePct": round(change_pct, 2)
        }
    
    _index_cache.set(cache_key, result, TTL_REALTIME)
    return result


# =============================================================================
# REGIME DATA (For portfolio_regimes.py and factors_intelligence.py)
# =============================================================================

def get_market_regime_data(period: str = "2y") -> Dict[str, pd.DataFrame]:
    """
    Get market regime data (SPY + VIX) in a single cached call.
    
    This is specifically for regime classification functions.
    """
    cache_key = f"regime_data_{period}"
    cached = _index_cache.get(cache_key)
    if cached is not None:
        logger.debug("[IndexCache] Regime data cache hit")
        return cached
    
    try:
        spy_df = get_index_data("SPY", period=period)
        vix_df = get_vix_data(period=period)
        
        result = {
            "spy": spy_df,
            "vix": vix_df
        }
        
        _index_cache.set(cache_key, result, TTL_REGIME)
        return result
        
    except Exception as e:
        logger.warning(f"[IndexCache] Regime data error: {e}")
        return {"spy": pd.DataFrame(), "vix": pd.DataFrame()}


def get_vix_percentile(window_years: int = 2) -> float:
    """
    Get current VIX percentile vs historical.
    
    Returns: percentile (0-100)
    """
    cache_key = f"vix_percentile_{window_years}"
    cached = _index_cache.get(cache_key)
    if cached is not None:
        return cached
    
    df = get_vix_data(period=f"{window_years}y")
    if df.empty or len(df) < 20:
        return 50.0  # Default to median
    
    current = df['Close'].iloc[-1]
    percentile = float((df['Close'] < current).mean() * 100)
    
    _index_cache.set(cache_key, percentile, TTL_REGIME)
    return round(percentile, 1)


# =============================================================================
# CACHE WARMING (Optional - can be called on startup)
# =============================================================================

def warm_cache(symbols: Optional[List[str]] = None):
    """
    Pre-warm the cache with commonly used data.
    
    Call this on server startup or periodically via background task.
    """
    if symbols is None:
        symbols = ALL_COMMON_SYMBOLS
    
    logger.info(f"[IndexCache] Warming cache with {len(symbols)} symbols...")
    
    try:
        # Warm batch data for 2d (realtime quotes)
        get_index_batch(symbols, period="2d")
        
        # Warm VIX historical for regime calculations
        get_vix_data(period="2y")
        
        # Warm SPY historical
        get_spy_data(period="2y")
        
        logger.info(f"[IndexCache] Cache warmed. Stats: {_index_cache.stats()}")
        
    except Exception as e:
        logger.warning(f"[IndexCache] Cache warm error: {e}")


def clear_cache():
    """Clear all cached data."""
    _index_cache.clear()
    logger.info("[IndexCache] Cache cleared")


def get_cache_stats() -> Dict:
    """Get cache statistics."""
    return _index_cache.stats()


# =============================================================================
# CONVENIENCE: DROP-IN REPLACEMENTS FOR COMMON PATTERNS
# =============================================================================

def fetch_ticker_closing_prices(symbol: str, period: str = "2y") -> pd.Series:
    """
    Convenience function: Returns just the closing prices as a Series.
    
    Drop-in replacement for:
        yf.Ticker(symbol).history(period=period)["Close"]
    """
    df = get_index_data(symbol, period=period)
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    return df["Close"]


def fetch_ticker_history(symbol: str, period: str = "2y") -> pd.DataFrame:
    """
    Convenience function: Returns full OHLCV history.
    
    Drop-in replacement for:
        yf.Ticker(symbol).history(period=period)
    """
    return get_index_data(symbol, period=period)
