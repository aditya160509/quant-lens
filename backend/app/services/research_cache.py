"""
Research Cache Service
Two-level caching for price data and computed outputs.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ResearchCache:
    """
    Two-level cache implementation:
    - Level A (Price Cache): Interval-aware TTL, keyed by (ticker, interval, start, end)
    - Level B (Compute Cache): TTL 5 minutes, keyed by request payload hash
    
    TTL Rules (per Quant360 Master Rulebook):
    - daily (1d): 15 minutes (900s)
    - hourly (1h): 5 minutes (300s)
    - intraday (1m, 5m, 15m): 60 seconds
    - quote: 5 seconds
    """
    
    def __init__(self):
        self._price_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._compute_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._quote_cache: Dict[str, Tuple[Any, datetime]] = {}
        
        # Interval-aware TTLs
        self.TTL_DAILY = 900      # 15 minutes
        self.TTL_HOURLY = 300     # 5 minutes
        self.TTL_INTRADAY = 60    # 60 seconds
        self.TTL_QUOTE = 5        # 5 seconds
        self.COMPUTE_TTL = 300    # 5 minutes
    
    def _get_price_ttl(self, interval: str) -> int:
        """Get TTL based on interval type."""
        interval = interval.lower()
        if interval in ('1d', 'daily', 'd'):
            return self.TTL_DAILY
        elif interval in ('1h', 'hourly', 'h'):
            return self.TTL_HOURLY
        elif interval in ('1m', '5m', '15m', '30m'):
            return self.TTL_INTRADAY
        else:
            return self.TTL_DAILY  # Default to daily TTL
    
    def _is_expired(self, timestamp: datetime, ttl_seconds: int) -> bool:
        """Check if a cache entry is expired."""
        return datetime.now() - timestamp > timedelta(seconds=ttl_seconds)
    
    def _make_key(self, *args) -> str:
        """Create a cache key from arguments."""
        return "|".join(str(a) for a in args)
    
    def _hash_payload(self, payload: dict) -> str:
        """Create a hash from a request payload."""
        # Sort keys for consistent hashing
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()[:16]
    
    # ===== Level A: Price Cache (Interval-Aware) =====
    
    def get_prices(self, ticker: str, interval: str, start: str, end: str) -> Tuple[Optional[Any], bool]:
        """
        Get cached price data with interval-aware TTL.
        
        Returns:
            Tuple of (data, cache_hit). data is None if not found or expired.
        """
        key = self._make_key(ticker, interval, start, end)
        ttl = self._get_price_ttl(interval)
        
        if key in self._price_cache:
            data, timestamp = self._price_cache[key]
            if not self._is_expired(timestamp, ttl):
                return data, True
            else:
                # Clean up expired entry
                del self._price_cache[key]
        
        return None, False
    
    def set_prices(self, ticker: str, interval: str, start: str, end: str, data: Any) -> None:
        """Store price data in cache."""
        key = self._make_key(ticker, interval, start, end)
        self._price_cache[key] = (data, datetime.now())
    
    # ===== Quote Cache (5 second TTL) =====
    
    def get_quote(self, ticker: str) -> Tuple[Optional[Any], bool]:
        """Get cached quote data (5 second TTL)."""
        if ticker in self._quote_cache:
            data, timestamp = self._quote_cache[ticker]
            if not self._is_expired(timestamp, self.TTL_QUOTE):
                return data, True
            else:
                del self._quote_cache[ticker]
        return None, False
    
    def set_quote(self, ticker: str, data: Any) -> None:
        """Store quote data in cache."""
        self._quote_cache[ticker] = (data, datetime.now())
    
    # ===== Level B: Compute Cache =====
    
    def get_compute(self, payload: dict) -> Tuple[Optional[Any], bool]:
        """
        Get cached computation result.
        
        Returns:
            Tuple of (data, cache_hit). data is None if not found or expired.
        """
        key = self._hash_payload(payload)
        
        if key in self._compute_cache:
            data, timestamp = self._compute_cache[key]
            if not self._is_expired(timestamp, self.COMPUTE_TTL):
                return data, True
            else:
                # Clean up expired entry
                del self._compute_cache[key]
        
        return None, False
    
    def set_compute(self, payload: dict, data: Any) -> None:
        """Store computation result in cache."""
        key = self._hash_payload(payload)
        self._compute_cache[key] = (data, datetime.now())
    
    # ===== Utility =====
    
    def make_cache_meta(self, cache_hit: bool) -> dict:
        """
        Create cache metadata for response.
        
        Returns:
            Dict with cache_hit and computed_at fields.
        """
        return {
            "cache_hit": cache_hit,
            "computed_at": datetime.now().isoformat() + "Z"
        }
    
    def clear_all(self) -> None:
        """Clear all caches."""
        self._price_cache.clear()
        self._compute_cache.clear()
        logger.info("Research cache cleared")
    
    def clear_expired(self) -> int:
        """
        Clear expired entries from all caches.
        
        Returns:
            Number of entries cleared.
        """
        cleared = 0
        now = datetime.now()
        
        # Clean price cache
        expired_keys = [
            k for k, (_, ts) in self._price_cache.items()
            if self._is_expired(ts, self.PRICE_TTL)
        ]
        for k in expired_keys:
            del self._price_cache[k]
            cleared += 1
        
        # Clean compute cache
        expired_keys = [
            k for k, (_, ts) in self._compute_cache.items()
            if self._is_expired(ts, self.COMPUTE_TTL)
        ]
        for k in expired_keys:
            del self._compute_cache[k]
            cleared += 1
        
        if cleared > 0:
            logger.debug(f"Cleared {cleared} expired cache entries")
        
        return cleared
    
    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "price_cache_size": len(self._price_cache),
            "compute_cache_size": len(self._compute_cache),
            "price_ttl_seconds": self.PRICE_TTL,
            "compute_ttl_seconds": self.COMPUTE_TTL
        }


# Global cache instance
research_cache = ResearchCache()
