"""
Security & Performance Middleware
OWASP Top 10 Compliant Security Measures + Scalability Optimizations

OWASP Top 10 2021 Coverage:
A01:2021 - Broken Access Control: Rate limiting, IP blocking
A02:2021 - Cryptographic Failures: Secure headers, no sensitive data in logs
A03:2021 - Injection: Input sanitization, query validation
A04:2021 - Insecure Design: Defense in depth, logging
A05:2021 - Security Misconfiguration: Secure defaults, CORS validation
A06:2021 - Vulnerable Components: Keep dependencies updated (external)
A07:2021 - Authentication Failures: Rate limiting on auth endpoints
A08:2021 - Data Integrity Failures: Request validation
A09:2021 - Security Logging: Comprehensive audit logging
A10:2021 - SSRF: URL validation for external requests
"""

import hashlib
import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ============================================================================
# RATE LIMITING (A01, A07 - Access Control, Auth Failures)
# ============================================================================

class RateLimiter:
    """
    Token bucket rate limiter with sliding window.
    Scales to 10,000+ users with O(1) operations.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10,
        cleanup_interval: int = 300  # 5 minutes
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        self.cleanup_interval = cleanup_interval
        
        # In-memory storage (use Redis for multi-instance production)
        self._minute_buckets: dict[str, list[float]] = defaultdict(list)
        self._hour_buckets: dict[str, list[float]] = defaultdict(list)
        self._blocked_ips: dict[str, float] = {}
        self._last_cleanup = time.time()
    
    def _cleanup(self):
        """Remove stale entries to prevent memory bloat"""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return
        
        cutoff_minute = now - 60
        cutoff_hour = now - 3600
        
        # Clean minute buckets
        for key in list(self._minute_buckets.keys()):
            self._minute_buckets[key] = [
                t for t in self._minute_buckets[key] if t > cutoff_minute
            ]
            if not self._minute_buckets[key]:
                del self._minute_buckets[key]
        
        # Clean hour buckets
        for key in list(self._hour_buckets.keys()):
            self._hour_buckets[key] = [
                t for t in self._hour_buckets[key] if t > cutoff_hour
            ]
            if not self._hour_buckets[key]:
                del self._hour_buckets[key]
        
        # Clean expired blocks
        for ip in list(self._blocked_ips.keys()):
            if self._blocked_ips[ip] < now:
                del self._blocked_ips[ip]
        
        self._last_cleanup = now
    
    def get_client_key(self, request: Request) -> str:
        """Extract client identifier (IP or user ID)"""
        # Try to get real IP from proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        # Include user ID if authenticated for per-user limits
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        return f"ip:{ip}"
    
    def is_allowed(self, request: Request) -> tuple[bool, dict | None]:
        """
        Check if request is allowed.
        Returns (allowed, rate_limit_info)
        """
        self._cleanup()
        now = time.time()
        key = self.get_client_key(request)
        # Build's editor calls (lint, types, hover, lenses, outline) fire on every pause in typing; give them their own,
        # larger bucket so editing never locks the rest of the app out. Runs stay in the normal bucket.
        path = request.url.path
        editor = path.startswith("/api/studio-v3/build/") and not path.startswith("/api/studio-v3/build/run")
        scale = 5 if editor else 1
        if editor:
            key += ":editor"
        
        # Check if blocked
        if key in self._blocked_ips:
            if self._blocked_ips[key] > now:
                return False, {
                    "blocked_until": self._blocked_ips[key],
                    "reason": "Too many requests"
                }
            del self._blocked_ips[key]
        
        # Check minute limit
        minute_requests = [t for t in self._minute_buckets[key] if t > now - 60]
        if len(minute_requests) >= self.requests_per_minute * scale:
            # Temp block for escalating violations
            self._blocked_ips[key] = now + 60  # Block for 1 minute
            return False, {
                "limit": self.requests_per_minute,
                "window": "minute",
                "retry_after": 60
            }
        
        # Check hour limit
        hour_requests = [t for t in self._hour_buckets[key] if t > now - 3600]
        if len(hour_requests) >= self.requests_per_hour * scale:
            self._blocked_ips[key] = now + 300  # Block for 5 minutes
            return False, {
                "limit": self.requests_per_hour,
                "window": "hour",
                "retry_after": 300
            }
        
        # Check burst (10 requests in 1 second)
        recent = [t for t in minute_requests if t > now - 1]
        if len(recent) >= self.burst_limit * scale:
            return False, {
                "limit": self.burst_limit,
                "window": "burst",
                "retry_after": 1
            }
        
        # Allow and record
        self._minute_buckets[key].append(now)
        self._hour_buckets[key].append(now)
        
        return True, {
            "remaining_minute": self.requests_per_minute - len(minute_requests) - 1,
            "remaining_hour": self.requests_per_hour - len(hour_requests) - 1
        }

# Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_minute=120,  # 2 req/sec steady
    requests_per_hour=3000,   # 50 req/min average
    burst_limit=20            # Allow short bursts
)


# ============================================================================
# INPUT VALIDATION (A03 - Injection)
# ============================================================================

# Regex patterns for validation - supports US, Indian (.NS, .BO), and international tickers
# Examples: AAPL, RELIANCE.NS, TCS.BO, ^NSEI, 005930.KS
SAFE_TICKER_PATTERN = re.compile(r'^[\^]?[A-Z0-9]{1,20}(\.[A-Z]{1,4})?$')
SAFE_SYMBOL_LIST_PATTERN = re.compile(r'^[A-Z0-9.,\s\^]{1,500}$')
UNSAFE_PATTERNS = [
    re.compile(r'<script', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
    re.compile(r'data:\s*text/html', re.IGNORECASE),
    re.compile(r'\{\{.*\}\}'),  # Template injection
    re.compile(r'\$\{.*\}'),    # Template injection
]


def sanitize_ticker(ticker: str) -> str:
    """
    Sanitize ticker symbol input.
    Prevents injection attacks.
    Supports US (AAPL), Indian (RELIANCE.NS, TCS.BO), and international tickers.
    """
    if not ticker:
        raise ValueError("Ticker cannot be empty")
    
    # Strip whitespace and uppercase
    clean = ticker.strip().upper()
    
    # Validate format - supports international formats
    # Examples: AAPL, RELIANCE.NS, TCS.BO, ^NSEI, 005930.KS, BRK.A
    if not SAFE_TICKER_PATTERN.match(clean):
        # Clean up invalid characters, preserving dots for exchange suffixes
        clean = re.sub(r'[^A-Z0-9.\^]', '', clean)[:25]
    
    if not clean:
        raise ValueError(f"Invalid ticker format: {ticker}")
    
    return clean


def sanitize_symbol_list(symbols: str, max_symbols: int = 100) -> list[str]:
    """
    Sanitize comma-separated symbol list.
    """
    if not symbols:
        return []
    
    # Check for injection attempts
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(symbols):
            raise ValueError("Invalid characters in input")
    
    # Split and sanitize each
    raw_symbols = symbols.split(",")
    
    if len(raw_symbols) > max_symbols:
        raise ValueError(f"Too many symbols: {len(raw_symbols)}, max: {max_symbols}")
    
    result = []
    for sym in raw_symbols:
        try:
            clean = sanitize_ticker(sym)
            if clean:
                result.append(clean)
        except ValueError:
            continue  # Skip invalid ones
    
    return result


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    General string sanitization.
    Prevents XSS and injection.
    """
    if not value:
        return ""
    
    # Truncate
    clean = value[:max_length]
    
    # Check for injection patterns
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(clean):
            raise ValueError("Potentially malicious input detected")
    
    # HTML entity encode special chars
    clean = clean.replace("<", "&lt;").replace(">", "&gt;")
    
    return clean


# ============================================================================
# SECURITY HEADERS (A05 - Security Misconfiguration)
# ============================================================================

SECURITY_HEADERS = {
    # Prevent clickjacking
    "X-Frame-Options": "DENY",
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    # Enable XSS filter
    "X-XSS-Protection": "1; mode=block",
    # Referrer policy
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Permissions policy (disable unnecessary features)
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    # Content Security Policy (for API responses)
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    # Cache control for sensitive data
    "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
    "Pragma": "no-cache",
}


# ============================================================================
# SECURITY MIDDLEWARE
# ============================================================================

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware.
    Implements OWASP Top 10 protections.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 1. Rate limiting check
        allowed, rate_info = rate_limiter.is_allowed(request)
        if not allowed:
            logger.warning(
                f"Rate limit exceeded: {rate_limiter.get_client_key(request)} - {request.url.path}"
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": rate_info
                }
            )
            response.headers["Retry-After"] = str(rate_info.get("retry_after", 60))
            return response
        
        try:
            response = await call_next(request)
        except Exception as e:  # noqa: BLE001 the last guard: log and return a 500 for any handler failure
            import traceback
            # Log error with traceback for debugging
            logger.error(f"Request error: {request.url.path} - {e!s}\n{traceback.format_exc()}")
            response = JSONResponse(
                status_code=500,
                content={"error": "Internal Server Error"}
            )
        
        # 3. Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # 4. Add rate limit headers
        if rate_info and "remaining_minute" in rate_info:
            response.headers["X-RateLimit-Limit"] = str(rate_limiter.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining_minute"])
        
        # 5. Log request (A09 - Security Logging)
        duration = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {duration:.3f}s"
        )
        
        return response


# ============================================================================
# CACHING LAYER (Scalability)
# ============================================================================

class OptimizedCache:
    """
    In-memory cache with TTL and LRU eviction.
    Redis-compatible interface for easy migration.
    
    Optimized for 10,000+ concurrent users.
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 300  # 5 minutes
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: dict[str, dict] = {}
        self._access_order: list[str] = []
    
    def _evict_lru(self):
        """Evict least recently used items when at capacity"""
        while len(self._store) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            self._store.pop(oldest_key, None)
    
    def _clean_expired(self):
        """Remove expired entries"""
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if v["expires_at"] < now
        ]
        for key in expired:
            del self._store[key]
            if key in self._access_order:
                self._access_order.remove(key)
    
    def get(self, key: str) -> Any | None:
        """Get value if exists and not expired"""
        if key not in self._store:
            return None
        
        entry = self._store[key]
        if entry["expires_at"] < time.time():
            del self._store[key]
            return None
        
        # Update access order (LRU)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: int | None = None):
        """Set value with TTL"""
        if ttl is None:
            ttl = self.default_ttl
        
        # Evict if needed
        self._evict_lru()
        
        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }
        self._access_order.append(key)
    
    def delete(self, key: str) -> bool:
        """Delete entry"""
        if key in self._store:
            del self._store[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False
    
    def clear(self):
        """Clear all entries"""
        self._store.clear()
        self._access_order.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self._store)
    
    def stats(self) -> dict:
        """Get cache statistics"""
        now = time.time()
        expired = sum(1 for v in self._store.values() if v["expires_at"] < now)
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "expired_pending": expired
        }


# Global cache instance
app_cache = OptimizedCache(max_size=50000, default_ttl=300)


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(ttl=60, key_prefix="momentum")
        def get_momentum(symbol: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            arg_hash = hashlib.md5(
                f"{args}{kwargs}".encode()
            ).hexdigest()[:16]
            cache_key = f"{key_prefix}:{func.__name__}:{arg_hash}"
            
            # Try cache
            cached_result = app_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            app_cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


# ============================================================================
# URL VALIDATION (A10 - SSRF Prevention)
# ============================================================================

ALLOWED_EXTERNAL_HOSTS = {
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "download.finance.yahoo.com",
    "api.tradingview.com",
}


def validate_external_url(url: str) -> bool:
    """
    Validate external URL to prevent SSRF attacks.
    Only allow whitelisted domains.
    """
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        
        # Must be HTTPS
        if parsed.scheme != "https":
            return False
        
        # Must be in whitelist
        if parsed.netloc not in ALLOWED_EXTERNAL_HOSTS:
            return False
        
        return not any(parsed.netloc.startswith(p) for p in ["127.", "10.", "192.168.", "172."])  # no private IPs
    except Exception:  # noqa: BLE001 any unparsable URL is refused
        return False


# ============================================================================
# AUDIT LOGGING (A09 - Security Logging)
# ============================================================================

class AuditLogger:
    """Structured audit logging for security events"""
    
    def __init__(self):
        self.logger = logging.getLogger("security.audit")
    
    def log_auth_attempt(
        self,
        success: bool,
        user_id: str | None,
        ip: str,
        reason: str | None = None
    ):
        """Log authentication attempt"""
        self.logger.info(
            f"AUTH: success={success} user={user_id} ip={ip} reason={reason}"
        )
    
    def log_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        allowed: bool
    ):
        """Log access control decision"""
        self.logger.info(
            f"ACCESS: user={user_id} resource={resource} action={action} allowed={allowed}"
        )
    
    def log_rate_limit(
        self,
        key: str,
        limit_type: str,
        blocked_until: float | None = None
    ):
        """Log rate limit event"""
        self.logger.warning(
            f"RATELIMIT: key={key} type={limit_type} blocked_until={blocked_until}"
        )
    
    def log_suspicious(
        self,
        ip: str,
        reason: str,
        details: str | None = None
    ):
        """Log suspicious activity"""
        self.logger.warning(
            f"SUSPICIOUS: ip={ip} reason={reason} details={details}"
        )


audit_logger = AuditLogger()
