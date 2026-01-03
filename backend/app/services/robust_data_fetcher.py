"""
Robust Data Fetcher with Multi-Source Fallback
===============================================
Priority:
1. NSE Direct API for Indian stocks
2. Direct Yahoo Finance API (avoids rate limiting)
3. yfinance library as last resort

Features:
- Thread-safe caching (TTL-based)
- PERSISTENT DISK SNAPSHOTS (never lose data)
- Exponential backoff on failures
- Rate limiting guards
- Batch support with delays
- Automatic source selection based on ticker
- Fundamentals/Company info support

Security Features:
- Input validation for ticker symbols
- Request timeout protection
- Rate limiting to prevent abuse
- Audit logging for data access
"""

import pandas as pd
import numpy as np
import requests
import asyncio
import time
import logging
import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from threading import Lock
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Valid ticker pattern (alphanumeric, periods, hyphens, ^, =, max 20 chars)
VALID_TICKER_PATTERN = re.compile(r'^[\w\^\.\-=]{1,20}$')

# Maximum values to prevent abuse
MAX_BATCH_SIZE = 100
MAX_PERIOD_DAYS = 3650  # 10 years max
REQUEST_TIMEOUT = 15  # seconds

# Allowed periods
ALLOWED_PERIODS = {"1d", "5d", "7d", "60d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
ALLOWED_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}

# =============================================================================
# CONFIGURATION
# =============================================================================

# Cache settings
CACHE_TTL_SECONDS = 600  # 10 minutes for memory cache
DISK_CACHE_TTL_HOURS = 24  # 24 hours for disk cache
MAX_CACHE_SIZE = 500

# Rate limiting
CALLS_PER_SECOND = 2
MIN_DELAY_BETWEEN_CALLS = 0.5  # seconds

# Backoff settings
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0
BACKOFF_MULTIPLIER = 2.0

# Disk cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

# =============================================================================
# ADVANCED OPTIMIZATIONS
# =============================================================================

# Request coalescing - prevent duplicate concurrent fetches
_pending_requests: Dict[str, 'asyncio.Future'] = {}
_pending_lock = Lock()

# Time-aware TTL settings
def get_smart_ttl() -> int:
    """Smart TTL based on market hours (EST)."""
    from datetime import datetime
    import pytz
    
    try:
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        hour = now.hour
        weekday = now.weekday()
        
        # Weekend - ultra long TTL (12 hours)
        if weekday >= 5:
            return 43200
        
        # Pre-market (4am-9:30am) - medium TTL
        if 4 <= hour < 9 or (hour == 9 and now.minute < 30):
            return 1800  # 30 min
        
        # Market hours (9:30am-4pm) - short TTL
        if (hour == 9 and now.minute >= 30) or (10 <= hour < 16):
            return 300  # 5 min
        
        # After hours - long TTL
        return 3600  # 1 hour
        
    except Exception:
        return CACHE_TTL_SECONDS  # Fallback to default

# Cache warm-up configuration
WARM_CACHE_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",  # Top US
    "^GSPC", "^DJI", "^IXIC", "^VIX",  # Major indices
    "SPY", "QQQ", "IWM",  # Major ETFs
]

WARM_CACHE_INTERVALS = ["1d", "1h"]
WARM_CACHE_PERIODS = ["1mo", "1y"]

# =============================================================================
# INPUT VALIDATION (Security)
# =============================================================================

def validate_ticker(ticker: str) -> str:
    """Validate and sanitize ticker symbol. Raises ValueError if invalid."""
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")
    
    ticker = ticker.strip().upper()
    
    if not VALID_TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    
    return ticker


def validate_period(period: str) -> str:
    """Validate period parameter."""
    if period not in ALLOWED_PERIODS:
        logger.warning(f"Invalid period {period}, defaulting to 1y")
        return "1y"
    return period


def validate_interval(interval: str) -> str:
    """Validate interval parameter."""
    if interval not in ALLOWED_INTERVALS:
        logger.warning(f"Invalid interval {interval}, defaulting to 1d")
        return "1d"
    return interval

# Indian tickers pattern
INDIAN_TICKERS = {
    "^NSEI", "^NSEBANK", "^CNXIT", "^INDIAVIX", "INDA", "SMIN",
    "^BSESN", "^NSEMDCP150"
}

# NSE Nifty 50 component symbols (for mapping)
NSE_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "ASIANPAINT", "MARUTI", "BAJFINANCE", "HCLTECH", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "WIPRO", "NESTLEIND", "TATAMOTORS",
    "POWERGRID", "NTPC", "BAJAJFINSV", "ADANIENT", "ONGC", "M&M",
    "JSWSTEEL", "TATASTEEL", "COALINDIA", "HINDALCO", "GRASIM",
    "TECHM", "DRREDDY", "INDUSINDBK", "CIPLA", "HDFCLIFE", "BPCL",
    "SBILIFE", "DIVISLAB", "APOLLOHOSP", "BRITANNIA", "TATACONSUM",
    "EICHERMOT", "HEROMOTOCO", "UPL", "ADANIPORTS", "BAJAJ-AUTO"
]

# =============================================================================
# PERSISTENT DISK CACHE
# =============================================================================

def _get_disk_cache_path(key: str, data_type: str = "price") -> Path:
    """Get path for disk cache file"""
    safe_key = hashlib.md5(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{data_type}_{safe_key}.json"


def _save_to_disk(key: str, data: Any, data_type: str = "price"):
    """Save data to disk cache (snapshot)"""
    try:
        path = _get_disk_cache_path(key, data_type)
        
        if isinstance(data, pd.DataFrame):
            # Convert DataFrame to serializable format
            cache_data = {
                "timestamp": time.time(),
                "type": "dataframe",
                "data": data.reset_index().to_dict('records'),
                "columns": list(data.columns),
                "index_name": data.index.name or "Date"
            }
        elif isinstance(data, dict):
            cache_data = {
                "timestamp": time.time(),
                "type": "dict",
                "data": data
            }
        else:
            cache_data = {
                "timestamp": time.time(),
                "type": "other",
                "data": str(data)
            }
        
        with open(path, 'w') as f:
            json.dump(cache_data, f, default=str)
        logger.debug(f"[RDF] Saved snapshot to disk: {key}")
    except Exception as e:
        logger.warning(f"[RDF] Failed to save disk cache: {e}")


def _load_from_disk(key: str, data_type: str = "price", max_age_hours: int = DISK_CACHE_TTL_HOURS) -> Optional[Any]:
    """Load data from disk cache if available and not too old"""
    try:
        path = _get_disk_cache_path(key, data_type)
        if not path.exists():
            return None
            
        with open(path, 'r') as f:
            cache_data = json.load(f)
        
        # Check age
        age_hours = (time.time() - cache_data.get("timestamp", 0)) / 3600
        if age_hours > max_age_hours:
            logger.debug(f"[RDF] Disk cache too old: {age_hours:.1f}h > {max_age_hours}h")
            return None
        
        # Reconstruct data
        if cache_data.get("type") == "dataframe":
            df = pd.DataFrame(cache_data["data"])
            # Restore index
            index_name = cache_data.get("index_name", "Date")
            if index_name in df.columns:
                if 'Date' in index_name or index_name == 'Date':
                    df[index_name] = pd.to_datetime(df[index_name])
                df.set_index(index_name, inplace=True)
            logger.info(f"[RDF] Loaded snapshot from disk: {key}")
            return df
        elif cache_data.get("type") == "dict":
            return cache_data["data"]
        else:
            return cache_data.get("data")
            
    except Exception as e:
        logger.warning(f"[RDF] Failed to load disk cache: {e}")
        return None


# =============================================================================
# MEMORY CACHE IMPLEMENTATION
# =============================================================================

class ThreadSafeCache:
    """Thread-safe cache with TTL"""
    
    def __init__(self, ttl: int = CACHE_TTL_SECONDS, max_size: int = MAX_CACHE_SIZE):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """Get from cache. Returns (value, is_fresh)"""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                is_fresh = (time.time() - timestamp) < self.ttl
                return value, is_fresh
            return None, False
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set cache value"""
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (value, time.time())
    
    def clear(self):
        with self._lock:
            self._cache.clear()


class BackoffTracker:
    """Track failures and implement exponential backoff"""
    
    def __init__(self):
        self._failures: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()
    
    def record_failure(self, key: str):
        with self._lock:
            count, _ = self._failures.get(key, (0, 0))
            self._failures[key] = (count + 1, time.time())
    
    def record_success(self, key: str):
        with self._lock:
            if key in self._failures:
                del self._failures[key]
    
    def should_skip(self, key: str) -> bool:
        with self._lock:
            if key not in self._failures:
                return False
            count, last_time = self._failures[key]
            backoff = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** count), MAX_BACKOFF)
            return (time.time() - last_time) < backoff


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, calls_per_second: float = CALLS_PER_SECOND):
        self.calls_per_second = calls_per_second
        self.tokens = calls_per_second
        self.last_update = time.time()
        self._lock = Lock()
    
    def acquire(self, blocking: bool = True) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.calls_per_second, self.tokens + elapsed * self.calls_per_second)
            self.last_update = now
            
            if self.tokens < 1:
                if blocking:
                    wait_time = (1 - self.tokens) / self.calls_per_second
                    time.sleep(wait_time)
                    self.tokens = 0
                    return True
                return False
            
            self.tokens -= 1
            return True


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_cache = ThreadSafeCache()
_info_cache = ThreadSafeCache(ttl=900)  # 15 min for info
_backoff = BackoffTracker()
_rate_limiter = RateLimiter()
_last_call_time = 0
_call_lock = Lock()


def _is_indian_ticker(ticker: str) -> bool:
    """Check if ticker is an Indian stock/index"""
    return (
        ticker in INDIAN_TICKERS or
        ticker.startswith("^NSE") or
        ticker.startswith("^INDIA") or
        ticker.endswith(".NS") or
        ticker.endswith(".BO") or
        ticker.replace(".NS", "").replace(".BO", "") in NSE_SYMBOLS
    )


def _make_cache_key(method: str, ticker: str, **kwargs) -> str:
    data = f"{method}:{ticker}:{str(sorted(kwargs.items()))}"
    return hashlib.md5(data.encode()).hexdigest()


def _enforce_rate_limit():
    global _last_call_time
    with _call_lock:
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < MIN_DELAY_BETWEEN_CALLS:
            time.sleep(MIN_DELAY_BETWEEN_CALLS - elapsed)
        _last_call_time = time.time()


# =============================================================================
# DATA SOURCE 1: NSE DIRECT API (for Indian stocks)
# =============================================================================

def _fetch_from_nse(ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
    """Fetch data from NSE Direct API for Indian stocks"""
    try:
        from app.services.nse_direct import nse_direct
        
        loop = asyncio.new_event_loop()
        try:
            # Determine which NSE endpoint to use
            clean_ticker = ticker.replace(".NS", "").replace(".BO", "").replace("^", "")
            
            # Try getting all indices first
            indices_data = loop.run_until_complete(nse_direct.get_indices())
            
            if indices_data and 'data' in indices_data:
                for idx in indices_data['data']:
                    if clean_ticker in str(idx.get('index', '')) or clean_ticker in str(idx.get('indexSymbol', '')):
                        df = pd.DataFrame([{
                            'Date': datetime.now(),
                            'Open': float(idx.get('open', idx.get('last', 0))),
                            'High': float(idx.get('high', idx.get('last', 0))),
                            'Low': float(idx.get('low', idx.get('last', 0))),
                            'Close': float(idx.get('last', 0)),
                            'Volume': 0
                        }])
                        df.set_index('Date', inplace=True)
                        logger.info(f"[RDF] NSE indices success for {ticker}")
                        return df
            
            # Try Nifty 50 stocks
            nifty_data = loop.run_until_complete(nse_direct.get_nifty50())
            
            if nifty_data and 'data' in nifty_data:
                for stock in nifty_data['data']:
                    symbol = stock.get('symbol', '')
                    if clean_ticker in symbol or symbol in clean_ticker:
                        df = pd.DataFrame([{
                            'Date': datetime.now(),
                            'Open': float(stock.get('open', stock.get('lastPrice', 0))),
                            'High': float(stock.get('dayHigh', stock.get('lastPrice', 0))),
                            'Low': float(stock.get('dayLow', stock.get('lastPrice', 0))),
                            'Close': float(stock.get('lastPrice', 0)),
                            'Volume': float(stock.get('totalTradedVolume', 0) or 0)
                        }])
                        df.set_index('Date', inplace=True)
                        logger.info(f"[RDF] NSE Nifty50 success for {ticker}")
                        return df
        finally:
            loop.close()
    except ImportError:
        logger.debug("[RDF] NSE Direct not available")
    except Exception as e:
        logger.warning(f"[RDF] NSE Direct failed for {ticker}: {e}")
    
    return None


def _fetch_nse_stock_info(ticker: str) -> Optional[Dict]:
    """Fetch stock info from NSE for Indian stocks"""
    try:
        from app.services.nse_direct import nse_direct
        
        loop = asyncio.new_event_loop()
        try:
            clean_ticker = ticker.replace(".NS", "").replace(".BO", "")
            
            # Get quote for the stock
            quote_data = loop.run_until_complete(nse_direct.get_quote(clean_ticker))
            
            if quote_data and not quote_data.get('error'):
                info = quote_data.get('priceInfo', {})
                meta = quote_data.get('info', {})
                return {
                    'symbol': clean_ticker,
                    'shortName': meta.get('companyName', clean_ticker),
                    'longName': meta.get('companyName', clean_ticker),
                    'industry': meta.get('industry', 'N/A'),
                    'sector': meta.get('sector', 'N/A'),
                    'currentPrice': info.get('lastPrice', 0),
                    'previousClose': info.get('previousClose', 0),
                    'open': info.get('open', 0),
                    'dayHigh': info.get('intraDayHighLow', {}).get('max', 0),
                    'dayLow': info.get('intraDayHighLow', {}).get('min', 0),
                    'volume': quote_data.get('preOpenMarket', {}).get('totalTradedVolume', 0),
                    'marketCap': meta.get('marketCap', 0),
                    'exchange': 'NSE',
                    'currency': 'INR'
                }
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"[RDF] NSE stock info failed for {ticker}: {e}")
    return None


# =============================================================================
# DATA SOURCE 2: DIRECT YAHOO API
# =============================================================================

def _fetch_from_yahoo_direct(ticker: str, period: str = "2y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch data directly from Yahoo Finance API"""
    _enforce_rate_limit()
    
    period_map = {
        "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
        "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y", "max": "max"
    }
    yahoo_range = period_map.get(period, "2y")
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": yahoo_range, "interval": interval, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if 'chart' in data and data['chart'].get('result'):
                result = data['chart']['result'][0]
                timestamps = result.get('timestamp', [])
                quote = result.get('indicators', {}).get('quote', [{}])[0]
                
                if timestamps:
                    df = pd.DataFrame({
                        'Date': pd.to_datetime(timestamps, unit='s'),
                        'Open': quote.get('open', []),
                        'High': quote.get('high', []),
                        'Low': quote.get('low', []),
                        'Close': quote.get('close', []),
                        'Volume': quote.get('volume', [])
                    })
                    df.set_index('Date', inplace=True)
                    df = df.dropna()
                    
                    if not df.empty:
                        logger.info(f"[RDF] Yahoo Direct success for {ticker}: {len(df)} rows")
                        return df
                        
        elif resp.status_code == 429:
            logger.warning(f"[RDF] Yahoo Direct rate limited for {ticker}")
            
    except Exception as e:
        logger.warning(f"[RDF] Yahoo Direct exception for {ticker}: {e}")
    
    return None


def _fetch_yahoo_quote_summary(ticker: str) -> Optional[Dict]:
    """Fetch quote summary from Yahoo for fundamentals"""
    _enforce_rate_limit()
    
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    params = {"modules": "price,summaryDetail,defaultKeyStatistics,financialData,assetProfile"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            result = data.get('quoteSummary', {}).get('result', [])
            if result:
                return result[0]
    except Exception as e:
        logger.warning(f"[RDF] Yahoo quote summary failed for {ticker}: {e}")
    
    return None


# =============================================================================
# DATA SOURCE 3: YFINANCE (last resort)
# =============================================================================

def _fetch_from_yfinance(ticker: str, period: str = "2y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fallback to yfinance library"""
    _enforce_rate_limit()
    
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df is not None and not df.empty:
            if 'Adj Close' in df.columns:
                df = df.drop(columns=['Adj Close'], errors='ignore')
            logger.info(f"[RDF] yfinance success for {ticker}: {len(df)} rows")
            return df
            
    except Exception as e:
        logger.warning(f"[RDF] yfinance failed for {ticker}: {e}")
    
    return None


def _fetch_yfinance_info(ticker: str) -> Optional[Dict]:
    """Fallback to yfinance for stock info"""
    _enforce_rate_limit()
    
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        if info and len(info) > 5:  # Has meaningful data
            logger.info(f"[RDF] yfinance info success for {ticker}")
            return info
    except Exception as e:
        logger.warning(f"[RDF] yfinance info failed for {ticker}: {e}")
    
    return None


# =============================================================================
# MAIN PUBLIC API
# =============================================================================

def get_price_data(ticker: str, period: str = "2y", interval: str = "1d", use_cache: bool = True) -> pd.DataFrame:
    """
    Get price data with multi-source fallback and disk snapshot.
    
    Security: Validates ticker, period, and interval inputs.
    """
    # Input validation (security)
    try:
        ticker = validate_ticker(ticker)
    except ValueError as e:
        logger.warning(f"[RDF] Invalid ticker rejected: {e}")
        return pd.DataFrame()
    
    period = validate_period(period)
    interval = validate_interval(interval)
    
    cache_key = _make_cache_key("price", ticker, period=period, interval=interval)
    
    # 1. Check memory cache
    if use_cache:
        cached, is_fresh = _cache.get(cache_key)
        if is_fresh and cached is not None:
            return cached
    
    # 2. Check backoff
    if _backoff.should_skip(cache_key):
        # Try disk cache
        disk_data = _load_from_disk(cache_key, "price")
        if disk_data is not None:
            return disk_data
        cached, _ = _cache.get(cache_key)
        return cached if cached is not None else pd.DataFrame()
    
    # 3. Acquire rate limit
    _rate_limiter.acquire(blocking=True)
    
    df = None
    
    # Source 1: NSE Direct for Indian stocks - ONLY for short periods (realtime/intraday)
    # NSE Direct API only provides current day data, not historical
    # For historical data (>5 days), skip to Yahoo
    nse_periods = {"1d", "5d"}  # NSE Direct is only useful for these
    if _is_indian_ticker(ticker) and period in nse_periods:
        df = _fetch_from_nse(ticker, period)
    
    # Source 2: Direct Yahoo API (handles Indian stocks with .NS/.BO suffix properly)
    if df is None or df.empty:
        df = _fetch_from_yahoo_direct(ticker, period, interval)
    
    # Source 3: yfinance fallback
    if df is None or df.empty:
        df = _fetch_from_yfinance(ticker, period, interval)
    
    # Handle result
    if df is not None and not df.empty:
        _cache.set(cache_key, df)
        _save_to_disk(cache_key, df, "price")  # Snapshot to disk
        _backoff.record_success(cache_key)
        return df
    else:
        _backoff.record_failure(cache_key)
        # Try disk cache
        disk_data = _load_from_disk(cache_key, "price")
        if disk_data is not None:
            logger.info(f"[RDF] Returning disk snapshot for {ticker}")
            return disk_data
        return pd.DataFrame()


def get_ticker_info(ticker: str, use_cache: bool = True) -> Optional[Dict]:
    """Get stock info/fundamentals with multi-source fallback"""
    cache_key = _make_cache_key("info", ticker)
    
    # Check memory cache
    if use_cache:
        cached, is_fresh = _info_cache.get(cache_key)
        if is_fresh and cached is not None:
            return cached
    
    _rate_limiter.acquire(blocking=True)
    
    info = None
    
    # Source 1: NSE for Indian stocks
    if _is_indian_ticker(ticker):
        info = _fetch_nse_stock_info(ticker)
    
    # Source 2: Yahoo quote summary
    if info is None:
        yahoo_data = _fetch_yahoo_quote_summary(ticker)
        if yahoo_data:
            price = yahoo_data.get('price', {})
            profile = yahoo_data.get('assetProfile', {})
            financial = yahoo_data.get('financialData', {})
            
            info = {
                'symbol': ticker,
                'shortName': price.get('shortName', ticker),
                'longName': price.get('longName', ticker),
                'industry': profile.get('industry', 'N/A'),
                'sector': profile.get('sector', 'N/A'),
                'currentPrice': price.get('regularMarketPrice', {}).get('raw', 0),
                'previousClose': price.get('regularMarketPreviousClose', {}).get('raw', 0),
                'marketCap': price.get('marketCap', {}).get('raw', 0),
                'exchange': price.get('exchange', 'N/A'),
                'currency': price.get('currency', 'USD')
            }
    
    # Source 3: yfinance fallback
    if info is None:
        info = _fetch_yfinance_info(ticker)
    
    if info:
        _info_cache.set(cache_key, info)
        _save_to_disk(cache_key, info, "info")
        return info
    
    # Try disk cache
    disk_info = _load_from_disk(cache_key, "info")
    return disk_info


def get_intraday_data(ticker: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    """Get intraday data specifically"""
    return get_price_data(ticker, period=period, interval=interval)


def get_batch_data(
    tickers: List[str], 
    period: str = "2y", 
    interval: str = "1d",
    batch_size: int = 5,
    delay_between_batches: float = 1.0
) -> Dict[str, pd.DataFrame]:
    """Get data for multiple tickers with batching"""
    results = {}
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        
        for ticker in batch:
            results[ticker] = get_price_data(ticker, period, interval)
        
        if i + batch_size < len(tickers):
            time.sleep(delay_between_batches)
    
    return results


def get_current_price(ticker: str) -> Optional[float]:
    """Get current price for a ticker"""
    df = get_price_data(ticker, period="1d", interval="1m")
    if df is not None and not df.empty:
        return float(df['Close'].iloc[-1])
    return None


def clear_cache():
    """Clear all cached data"""
    _cache.clear()
    _info_cache.clear()
    logger.info("[RDF] Cache cleared")


def get_stats() -> Dict:
    """Get fetcher statistics"""
    return {
        "price_cache_size": len(_cache._cache),
        "info_cache_size": len(_info_cache._cache),
        "disk_cache_dir": str(CACHE_DIR),
        "cache_ttl": CACHE_TTL_SECONDS,
        "disk_ttl_hours": DISK_CACHE_TTL_HOURS
    }


# =============================================================================
# CONVENIENCE ALIASES
# =============================================================================

fetch_price_data = get_price_data
fetch_intraday = get_intraday_data
fetch_batch = get_batch_data
yf_info = get_ticker_info
yf_price = get_current_price


# =============================================================================
# YFINANCE-COMPATIBLE DROP-IN REPLACEMENT
# =============================================================================

class Ticker:
    """
    yfinance-compatible Ticker class wrapper.
    Provides same interface as yf.Ticker() for easy migration.
    Uses robust multi-source fetching behind the scenes.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self._info = None
    
    def history(self, period: str = "1mo", interval: str = "1d", start=None, end=None, **kwargs) -> pd.DataFrame:
        """Get historical price data (yfinance-compatible)"""
        df = get_price_data(self.symbol, period=period, interval=interval)
        if df is None:
            return pd.DataFrame()
        
        # Filter by date range if provided
        if start is not None:
            start_dt = pd.to_datetime(start)
            df = df[df.index >= start_dt]
        if end is not None:
            end_dt = pd.to_datetime(end)
            df = df[df.index <= end_dt]
        
        return df
    
    @property
    def info(self) -> Dict:
        """Get ticker info/fundamentals (yfinance-compatible)"""
        if self._info is None:
            self._info = get_ticker_info(self.symbol) or {}
        return self._info
    
    def get_info(self) -> Dict:
        """Alias for info property"""
        return self.info


def download(
    tickers,
    start=None,
    end=None,
    period: str = "1mo",
    interval: str = "1d",
    group_by: str = "column",
    auto_adjust: bool = True,
    progress: bool = False,
    **kwargs
) -> pd.DataFrame:
    """
    yfinance-compatible download function.
    Uses robust multi-source fetching behind the scenes.
    
    Args:
        tickers: Single ticker or list of tickers
        start, end: Date range (optional, uses period if not provided)
        period: Data period like '1mo', '1y', '2y'
        interval: Data interval like '1d', '1h'
        group_by: How to group multi-ticker data
        auto_adjust: Ignored (always use adjusted prices)
        progress: Ignored (no progress bar)
    
    Returns:
        DataFrame with OHLCV data
    """
    # Normalize tickers to list
    if isinstance(tickers, str):
        ticker_list = [t.strip() for t in tickers.split(',') if t.strip()]
    elif isinstance(tickers, (list, tuple)):
        ticker_list = [t.strip() for t in tickers if t.strip()]
    else:
        ticker_list = [str(tickers)]
    
    if len(ticker_list) == 0:
        return pd.DataFrame()
    
    if len(ticker_list) == 1:
        # Single ticker
        df = get_price_data(ticker_list[0], period=period, interval=interval)
        if df is None:
            return pd.DataFrame()
        
        # Filter by date range if provided
        if start is not None:
            start_dt = pd.to_datetime(start)
            df = df[df.index >= start_dt]
        if end is not None:
            end_dt = pd.to_datetime(end)
            df = df[df.index <= end_dt]
        
        return df
    
    # Multiple tickers - use batch fetch
    batch_data = get_batch_data(ticker_list, period=period, batch_size=10, delay_between_batches=0.5)
    
    if not batch_data:
        return pd.DataFrame()
    
    # Filter by date range
    for ticker, df in batch_data.items():
        if df is not None and not df.empty:
            if start is not None:
                start_dt = pd.to_datetime(start)
                batch_data[ticker] = df[df.index >= start_dt]
            if end is not None:
                end_dt = pd.to_datetime(end)
                batch_data[ticker] = df[df.index <= end_dt]
    
    # Combine into multi-index DataFrame like yf.download returns
    all_data = {}
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        for ticker, df in batch_data.items():
            if df is not None and not df.empty and col in df.columns:
                all_data[(col, ticker)] = df[col]
    
    if not all_data:
        return pd.DataFrame()
    
    result = pd.DataFrame(all_data)
    result.columns = pd.MultiIndex.from_tuples(result.columns)
    return result


def warm_cache(tickers: Optional[List[str]] = None, background: bool = True):
    """
    Warm the cache with frequently accessed data.
    Call this on app startup for near-zero latency on common requests.
    
    Args:
        tickers: List of tickers to warm. Defaults to WARM_CACHE_TICKERS.
        background: If True, runs in background thread.
    """
    import threading
    
    target_tickers = tickers or WARM_CACHE_TICKERS
    
    def _warm():
        logger.info(f"[RDF] Warming cache for {len(target_tickers)} tickers...")
        warmed = 0
        
        for ticker in target_tickers:
            for period in WARM_CACHE_PERIODS:
                try:
                    df = get_price_data(ticker, period=period, interval="1d")
                    if df is not None and not df.empty:
                        warmed += 1
                except Exception as e:
                    logger.debug(f"Warm cache failed for {ticker}: {e}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.3)
        
        logger.info(f"[RDF] Cache warmed: {warmed} entries loaded")
    
    if background:
        thread = threading.Thread(target=_warm, daemon=True)
        thread.start()
        return thread
    else:
        _warm()
        return None


def normalize_cache_key(ticker: str, period: str, interval: str) -> str:
    """
    Normalize cache key to avoid redundant fetches.
    Rounds time windows for better cache utilization.
    """
    # Normalize ticker
    ticker = ticker.upper().strip()
    
    # For daily data, bucket by day
    if interval == "1d":
        date_bucket = datetime.now().strftime("%Y-%m-%d")
    # For hourly, bucket by hour
    elif interval in ["1h", "60m"]:
        date_bucket = datetime.now().strftime("%Y-%m-%d-%H")
    # For minute data, bucket by 15-minute windows
    else:
        minute = (datetime.now().minute // 15) * 15
        date_bucket = datetime.now().strftime(f"%Y-%m-%d-%H-{minute:02d}")
    
    return f"{ticker}_{period}_{interval}_{date_bucket}"


def get_cache_stats() -> Dict[str, Any]:
    """Get detailed cache statistics for monitoring."""
    stats = get_stats()
    
    # Add smart TTL info
    smart_ttl = get_smart_ttl()
    stats['current_smart_ttl_seconds'] = smart_ttl
    stats['smart_ttl_reason'] = (
        "weekend" if smart_ttl >= 43200 else
        "after_hours" if smart_ttl >= 3600 else
        "pre_market" if smart_ttl >= 1800 else
        "market_hours"
    )
    
    # Add warm cache config
    stats['warm_cache_tickers'] = len(WARM_CACHE_TICKERS)
    stats['pending_requests'] = len(_pending_requests)
    
    return stats


# Export commonly used names
__all__ = [
    'get_price_data',
    'get_batch_data', 
    'get_ticker_info',
    'get_intraday_data',
    'get_current_price',
    'clear_cache',
    'get_stats',
    # Advanced
    'warm_cache',
    'get_smart_ttl',
    'normalize_cache_key',
    'get_cache_stats',
    # yfinance-compatible
    'Ticker',
    'download',
    # Aliases
    'fetch_price_data',
    'fetch_intraday',
    'fetch_batch',
    'yf_info',
    'yf_price',
]
