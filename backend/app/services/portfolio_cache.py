"""
Portfolio God Mode - In-Memory Cache Layer
Provides caching with TTL, inputHash tracking, and staleness monitoring
"""
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
from functools import wraps


class PortfolioCache:
    """
    In-memory cache for portfolio computations.
    
    Key format: {scope}:{identifiers_hash}
    Tracks:
    - inputHash for audit
    - stalenessSec for quality
    - hit/miss for debugging
    """
    
    def __init__(self, default_ttl_sec: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl_sec
        self._stats = {"hits": 0, "misses": 0}
    
    def _compute_hash(self, *args, **kwargs) -> str:
        """Compute stable hash for inputs."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _make_key(self, scope: str, identifiers: Dict[str, Any]) -> str:
        """Build cache key from scope and identifiers."""
        ident_hash = self._compute_hash(**identifiers)
        return f"{scope}:{ident_hash}"
    
    def get(self, scope: str, identifiers: Dict[str, Any]) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        Get cached value if valid.
        
        Returns:
            (value, meta) where meta contains:
            - cacheHit: bool
            - stalenessSec: int
            - inputHash: str
        """
        key = self._make_key(scope, identifiers)
        input_hash = self._compute_hash(**identifiers)
        
        if key not in self._cache:
            self._stats["misses"] += 1
            return None, {
                "cacheHit": False,
                "stalenessSec": 0,
                "inputHash": input_hash
            }
        
        entry = self._cache[key]
        now = time.time()
        age_sec = int(now - entry["timestamp"])
        
        # Check TTL
        if age_sec > entry["ttl"]:
            del self._cache[key]
            self._stats["misses"] += 1
            return None, {
                "cacheHit": False,
                "stalenessSec": 0,
                "inputHash": input_hash
            }
        
        self._stats["hits"] += 1
        return entry["value"], {
            "cacheHit": True,
            "stalenessSec": age_sec,
            "inputHash": entry["inputHash"]
        }
    
    def set(self, scope: str, identifiers: Dict[str, Any], value: Any, ttl_sec: Optional[int] = None):
        """Store value in cache."""
        key = self._make_key(scope, identifiers)
        input_hash = self._compute_hash(**identifiers)
        
        self._cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl_sec or self._default_ttl,
            "inputHash": input_hash
        }
    
    def invalidate(self, scope: str, identifiers: Optional[Dict[str, Any]] = None):
        """Invalidate cached entries."""
        if identifiers:
            key = self._make_key(scope, identifiers)
            self._cache.pop(key, None)
        else:
            # Invalidate all entries for scope
            keys_to_remove = [k for k in self._cache if k.startswith(f"{scope}:")]
            for k in keys_to_remove:
                del self._cache[k]
    
    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            **self._stats,
            "entries": len(self._cache),
            "hitRate": self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"])
        }


# Global cache instance
_portfolio_cache = PortfolioCache(default_ttl_sec=300)


def get_cache() -> PortfolioCache:
    """Get the global portfolio cache."""
    return _portfolio_cache


def cached(scope: str, ttl_sec: Optional[int] = None):
    """
    Decorator for caching function results.
    
    Usage:
        @cached("risk_metrics")
        def compute_risk(window: str, benchmark: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            identifiers = {"args": args, "kwargs": kwargs}
            
            value, meta = cache.get(scope, identifiers)
            if value is not None:
                # Attach cache meta to result if it has quality field
                if hasattr(value, "quality") and hasattr(value.quality, "stalenessSec"):
                    value.quality.stalenessSec = meta["stalenessSec"]
                return value
            
            # Compute fresh
            result = func(*args, **kwargs)
            cache.set(scope, identifiers, result, ttl_sec)
            return result
        
        return wrapper
    return decorator


def cached_async(scope: str, ttl_sec: Optional[int] = None):
    """Async version of cached decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            identifiers = {"args": args, "kwargs": kwargs}
            
            value, meta = cache.get(scope, identifiers)
            if value is not None:
                if hasattr(value, "quality") and hasattr(value.quality, "stalenessSec"):
                    value.quality.stalenessSec = meta["stalenessSec"]
                return value
            
            result = await func(*args, **kwargs)
            cache.set(scope, identifiers, result, ttl_sec)
            return result
        
        return wrapper
    return decorator


# Utility for computing quality from data
def compute_quality(
    data: Any,
    expected_fields: list = None,
    last_update: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Compute quality metrics for data.
    
    Returns dict with:
    - stalenessSec
    - missingPct  
    - revisionFlag
    - warnings
    """
    warnings = []
    missing_count = 0
    total_count = 0
    
    if expected_fields:
        for field in expected_fields:
            total_count += 1
            if not hasattr(data, field) or getattr(data, field) is None:
                missing_count += 1
                warnings.append(f"Missing field: {field}")
    
    missing_pct = missing_count / max(1, total_count)
    
    staleness_sec = 0
    if last_update:
        staleness_sec = int((datetime.utcnow() - last_update).total_seconds())
        if staleness_sec > 3600:
            warnings.append(f"Data is {staleness_sec // 60} minutes old")
    
    return {
        "stalenessSec": staleness_sec,
        "missingPct": missing_pct,
        "revisionFlag": False,
        "warnings": warnings
    }
