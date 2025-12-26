"""
Global Rate Limiter and Cache for API Calls
Prevents 429 (Too Many Requests) errors from yfinance and other APIs
"""

import asyncio
import time
from functools import wraps
from typing import Any, Dict, Optional, Callable
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.
    Allows bursts but enforces average rate over time.
    """
    def __init__(self, rate: float = 1.0, capacity: float = 5.0):
        """
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens (burst capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary.
        Returns: Wait time in seconds
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
            self.last_update = time.time()
            return wait_time
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting. Returns True if successful."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SmartCache:
    """
    Smart cache with:
    - TTL (time to live)
    - Stale-while-revalidate pattern
    - Max size with LRU eviction
    """
    def __init__(self, default_ttl: int = 300, stale_ttl: int = 600, max_size: int = 1000):
        """
        Args:
            default_ttl: Fresh data TTL in seconds (5 min default)
            stale_ttl: Stale but usable data TTL (10 min default)
            max_size: Maximum cache entries
        """
        self.default_ttl = default_ttl
        self.stale_ttl = stale_ttl
        self.max_size = max_size
        self._cache: Dict[str, Dict] = {}
        self._access_times: Dict[str, float] = {}
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from function arguments"""
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> tuple[Optional[Any], bool]:
        """
        Get cached value.
        Returns: (value, is_fresh) - value is None if not found or expired
        """
        if key not in self._cache:
            return None, False
        
        entry = self._cache[key]
        now = time.time()
        age = now - entry['timestamp']
        
        # Update access time for LRU
        self._access_times[key] = now
        
        if age < entry['ttl']:
            return entry['value'], True  # Fresh
        elif age < self.stale_ttl:
            return entry['value'], False  # Stale but usable
        else:
            # Expired
            del self._cache[key]
            del self._access_times[key]
            return None, False
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Store value in cache"""
        # Evict if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_lru()
        
        self._cache[key] = {
            'value': value,
            'timestamp': time.time(),
            'ttl': ttl or self.default_ttl
        }
        self._access_times[key] = time.time()
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._access_times:
            return
        oldest_key = min(self._access_times, key=self._access_times.get)
        del self._cache[oldest_key]
        del self._access_times[oldest_key]
    
    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        self._access_times.clear()
    
    def stats(self) -> dict:
        """Get cache statistics"""
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'default_ttl': self.default_ttl
        }


class BackoffHandler:
    """
    Handles exponential backoff for failed requests.
    Tracks error counts per endpoint and applies backoff.
    """
    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0, decay_time: float = 300.0):
        """
        Args:
            base_delay: Initial delay in seconds
            max_delay: Maximum delay (5 min)
            decay_time: Time to reset error count (5 min)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.decay_time = decay_time
        self._errors: Dict[str, Dict] = {}
    
    def record_error(self, key: str):
        """Record an error for an endpoint"""
        now = time.time()
        if key not in self._errors:
            self._errors[key] = {'count': 0, 'first_error': now}
        
        # Reset if enough time has passed
        if now - self._errors[key]['first_error'] > self.decay_time:
            self._errors[key] = {'count': 0, 'first_error': now}
        
        self._errors[key]['count'] += 1
        self._errors[key]['last_error'] = now
    
    def record_success(self, key: str):
        """Record a success, reducing error count"""
        if key in self._errors:
            self._errors[key]['count'] = max(0, self._errors[key]['count'] - 1)
            if self._errors[key]['count'] == 0:
                del self._errors[key]
    
    def get_delay(self, key: str) -> float:
        """Get current delay for an endpoint based on error history"""
        if key not in self._errors:
            return 0.0
        
        error_count = self._errors[key]['count']
        delay = min(self.base_delay * (2 ** error_count), self.max_delay)
        return delay
    
    def should_skip(self, key: str) -> bool:
        """Check if we should skip this request due to backoff"""
        if key not in self._errors:
            return False
        
        last_error = self._errors[key].get('last_error', 0)
        delay = self.get_delay(key)
        return time.time() - last_error < delay


# ===================== GLOBAL INSTANCES =====================

# Rate limiter: 0.5 requests/second (very conservative to avoid 429)
yfinance_limiter = TokenBucketRateLimiter(rate=0.5, capacity=3)

# Cache: 5 minute fresh, 10 minute stale-while-revalidate
global_cache = SmartCache(default_ttl=300, stale_ttl=600, max_size=2000)

# Backoff handler for failed endpoints
backoff_handler = BackoffHandler(base_delay=2.0, max_delay=300.0)


# ===================== DECORATOR =====================

def cached_with_rate_limit(ttl: int = 300, rate_limit: bool = True):
    """
    Decorator that adds caching and rate limiting to any async function.
    Uses stale-while-revalidate pattern.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            func_name = func.__name__
            cache_key = f"{func_name}:{global_cache._make_key(*args, **kwargs)}"
            
            # Check backoff
            if backoff_handler.should_skip(cache_key):
                # Return stale data if available
                value, _ = global_cache.get(cache_key)
                if value is not None:
                    logger.debug(f"[Cache] Returning stale data due to backoff: {func_name}")
                    return value
                logger.warning(f"[Backoff] Skipping {func_name} - too many recent errors")
                return None
            
            # Check cache for fresh data
            cached_value, is_fresh = global_cache.get(cache_key)
            if is_fresh:
                logger.debug(f"[Cache] Fresh hit: {func_name}")
                return cached_value
            
            # Rate limit
            if rate_limit:
                wait_time = await yfinance_limiter.acquire()
                if wait_time > 0:
                    logger.debug(f"[RateLimit] Waited {wait_time:.2f}s for {func_name}")
            
            # Call the function
            try:
                result = await func(*args, **kwargs)
                
                # Cache successful result
                if result is not None:
                    global_cache.set(cache_key, result, ttl)
                    backoff_handler.record_success(cache_key)
                
                return result
            
            except Exception as e:
                logger.error(f"[Error] {func_name}: {e}")
                backoff_handler.record_error(cache_key)
                
                # Return stale data if available
                if cached_value is not None:
                    logger.info(f"[Cache] Returning stale data after error: {func_name}")
                    return cached_value
                
                raise
        
        return wrapper
    return decorator


def sync_cached_with_rate_limit(ttl: int = 300):
    """
    Decorator for sync functions with caching (no rate limiting for sync).
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            cache_key = f"{func_name}:{global_cache._make_key(*args, **kwargs)}"
            
            # Check cache
            cached_value, is_fresh = global_cache.get(cache_key)
            if is_fresh:
                return cached_value
            
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    global_cache.set(cache_key, result, ttl)
                return result
            except Exception as e:
                if cached_value is not None:
                    return cached_value
                raise
        
        return wrapper
    return decorator


# ===================== HELPER FUNCTIONS =====================

def get_cache_stats() -> dict:
    """Get statistics about the cache and rate limiter"""
    return {
        'cache': global_cache.stats(),
        'rate_limiter': {
            'tokens': yfinance_limiter.tokens,
            'rate': yfinance_limiter.rate,
            'capacity': yfinance_limiter.capacity
        },
        'backoff': {
            'tracked_endpoints': len(backoff_handler._errors)
        }
    }


def clear_all_caches():
    """Clear all cached data"""
    global_cache.clear()
    backoff_handler._errors.clear()
    logger.info("[Cache] All caches cleared")
