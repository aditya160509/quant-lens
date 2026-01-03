"""
Macro Control System API Router (PRODUCTION)
=============================================
World-Class Macro Dashboard with 7 Regime Detection Systems

Endpoints:
- GET /master-posture - Aggregate risk posture
- GET /regime-engine - Market regime (HMM-based)
- GET /stress-detector - Turbulence index
- GET /volatility-regime - Vol classification
- GET /cta-trend - CTA trend signals
- GET /mean-reversion - Reversion timer
- GET /breadth - McClellan indicators
- GET /rate-cycle - Interest rate position
- GET /cache-stats - Cache monitoring
- POST /cache-clear - Clear cache (admin)

Security: Input validation, rate limiting, OWASP compliant
Scalability: Async handlers, caching, response compression
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from typing import Optional
import logging
import time
import asyncio
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

from app.services.macro_control_system import (
    compute_master_posture,
    compute_regime_engine,
    compute_stress_detector,
    compute_volatility_regime,
    compute_cta_trend,
    compute_mean_reversion,
    compute_market_breadth,
    compute_rate_cycle,
    get_cache_stats,
    clear_cache,
    preload_cache
)

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# RATE LIMITING (In-Memory - Use Redis for production at scale)
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter. For 10k users, use Redis."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self._cleanup_interval = 60  # seconds
        self._last_cleanup = time.time()
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for this client."""
        now = time.time()
        
        # Periodic cleanup of old entries
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now
        
        # Remove requests older than 1 minute
        cutoff = now - 60
        self.requests[client_id] = [t for t in self.requests[client_id] if t > cutoff]
        
        # Check rate limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False
        
        # Record this request
        self.requests[client_id].append(now)
        return True
    
    def _cleanup(self):
        """Remove old entries to prevent memory growth."""
        now = time.time()
        cutoff = now - 120  # 2 minutes
        to_delete = []
        for client_id, timestamps in self.requests.items():
            self.requests[client_id] = [t for t in timestamps if t > cutoff]
            if not self.requests[client_id]:
                to_delete.append(client_id)
        for client_id in to_delete:
            del self.requests[client_id]


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)


# =============================================================================
# SECURITY & VALIDATION
# =============================================================================

VALID_MARKETS = {"US", "INDIA"}
MAX_WINDOW = 504
MIN_WINDOW = 60


def validate_market(market: str) -> str:
    """Validate and sanitize market input."""
    if not isinstance(market, str):
        raise HTTPException(status_code=400, detail="Market must be a string")
    
    market = market.upper().strip()
    
    # Prevent injection
    if len(market) > 10:
        raise HTTPException(status_code=400, detail="Invalid market parameter")
    
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"Invalid market. Must be one of: {VALID_MARKETS}")
    
    return market


def validate_window(window: int) -> int:
    """Validate window parameter."""
    if not isinstance(window, int):
        raise HTTPException(status_code=400, detail="Window must be an integer")
    
    if window < MIN_WINDOW or window > MAX_WINDOW:
        raise HTTPException(
            status_code=400, 
            detail=f"Window must be between {MIN_WINDOW} and {MAX_WINDOW}"
        )
    
    return window


def get_client_id(request: Request) -> str:
    """Extract client identifier for rate limiting."""
    # Use forwarded IP if behind proxy
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    """Check and enforce rate limit."""
    client_id = get_client_id(request)
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before trying again.",
            headers={"Retry-After": "60"}
        )


# =============================================================================
# RESPONSE CACHING HEADERS
# =============================================================================

def add_cache_headers(response: Response, max_age: int = 60):
    """Add caching headers for CDN/browser caching."""
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"


# =============================================================================
# ASYNC WRAPPER FOR CPU-BOUND CALCULATIONS
# =============================================================================

async def run_in_thread(func, *args, **kwargs):
    """Run CPU-bound function in thread pool to avoid blocking event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# =============================================================================
# MASTER POSTURE ENDPOINT
# =============================================================================

@router.get("/master-posture")
async def get_master_posture(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Master Trading Posture - Aggregate of all 7 features.
    
    Returns:
    - overall_score: 0-100 weighted score
    - posture: RISK-ON / CAUTION / RISK-OFF
    - trading_clearances: exposure, leverage, new positions
    - warnings: active constraints
    - feature_scores: breakdown by feature
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        # Run in thread to avoid blocking
        result = await run_in_thread(compute_master_posture, market)
        
        add_cache_headers(response, max_age=60)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing master posture: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 1: REGIME ENGINE
# =============================================================================

@router.get("/regime-engine")
async def get_regime_engine(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA"),
    window: int = Query(252, ge=MIN_WINDOW, le=MAX_WINDOW, description="Lookback window in days")
):
    """
    Feature 1: Market Regime Engine (HMM-Based)
    
    4 Hidden States:
    - Bull Low Vol: μ > 0, σ < median
    - Bull High Vol: μ > 0, σ > median
    - Bear Low Vol: μ < 0, σ < median
    - Bear High Vol: μ < 0, σ > median
    
    Returns regime label, confidence, stability, transition risk, and constraints.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        window = validate_window(window)
        
        result = await run_in_thread(compute_regime_engine, market, window)
        
        add_cache_headers(response, max_age=300)  # 5 min cache for individual features
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing regime engine: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 2: STRESS DETECTOR
# =============================================================================

@router.get("/stress-detector")
async def get_stress_detector(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA"),
    window: int = Query(252, ge=MIN_WINDOW, le=MAX_WINDOW, description="Lookback window in days")
):
    """
    Feature 2: Stress Detector (Turbulence Index)
    
    Uses Mahalanobis Distance:
    Turbulence_t = (r_t - μ)^T × Σ^-1 × (r_t - μ)
    
    States: NORMAL / ELEVATED / EXTREME
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        window = validate_window(window)
        
        result = await run_in_thread(compute_stress_detector, market, window)
        
        add_cache_headers(response, max_age=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing stress detector: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 3: VOLATILITY REGIME
# =============================================================================

@router.get("/volatility-regime")
async def get_volatility_regime(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Feature 3: Volatility Regime Classification
    
    Based on VIX/INDIAVIX percentile:
    - LOW: Percentile < 40
    - MEDIUM: 40 ≤ Percentile < 70
    - HIGH: Percentile ≥ 70
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_volatility_regime, market)
        
        add_cache_headers(response, max_age=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing volatility regime: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 4: CTA TREND SIGNAL
# =============================================================================

@router.get("/cta-trend")
async def get_cta_trend(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Feature 4: CTA Trend Signal
    
    Multi-timeframe breakout detection (20d, 50d, 200d).
    Returns trend direction, agreement score, maturity, and exhaustion risk.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_cta_trend, market)
        
        add_cache_headers(response, max_age=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing CTA trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 5: MEAN REVERSION
# =============================================================================

@router.get("/mean-reversion")
async def get_mean_reversion(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Feature 5: Mean Reversion Timer
    
    Z-score and distance from moving averages.
    Returns extension status, snapback probability, and entry restrictions.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_mean_reversion, market)
        
        add_cache_headers(response, max_age=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing mean reversion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 6: MARKET BREADTH
# =============================================================================

@router.get("/breadth")
async def get_market_breadth(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Feature 6: Market Breadth (McClellan Indicators)
    
    McClellan Oscillator = EMA(19) - EMA(39) of Net Advances
    McClellan Summation = Cumulative sum of Oscillator
    
    Returns breadth health, alignment, and rally quality.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_market_breadth, market)
        
        add_cache_headers(response, max_age=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing market breadth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# FEATURE 7: RATE CYCLE
# =============================================================================

@router.get("/rate-cycle")
async def get_rate_cycle(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Feature 7: Rate Cycle Position
    
    Tracks Fed Funds (US) and RBI Repo (India) rates.
    Returns cycle stage, policy stance, and implications.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_rate_cycle, market)
        
        add_cache_headers(response, max_age=3600)  # Rate data changes less frequently
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing rate cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# ALL FEATURES ENDPOINT
# =============================================================================

@router.get("/all-features")
async def get_all_features(
    request: Request,
    response: Response,
    market: str = Query("US", description="Market: US or INDIA")
):
    """
    Get all 7 features in a single call.
    More efficient than calling each endpoint separately.
    """
    try:
        check_rate_limit(request)
        market = validate_market(market)
        
        result = await run_in_thread(compute_master_posture, market)
        
        add_cache_headers(response, max_age=60)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing all features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# CACHE MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/cache-stats")
async def get_cache_statistics(request: Request):
    """
    Get cache statistics for monitoring.
    Useful for observability and debugging.
    """
    try:
        check_rate_limit(request)
        stats = get_cache_stats()
        return {
            "status": "ok",
            "cache": stats,
            "rate_limiter": {
                "active_clients": len(rate_limiter.requests),
                "requests_per_minute_limit": rate_limiter.requests_per_minute
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache-clear")
async def clear_data_cache(request: Request):
    """
    Clear the price data cache.
    Admin endpoint - should be protected in production.
    """
    try:
        check_rate_limit(request)
        clear_cache()
        return {
            "status": "ok",
            "message": "Cache cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache-preload")
async def preload_data_cache(
    request: Request,
    markets: str = Query("US,INDIA", description="Comma-separated list of markets")
):
    """
    Preload cache with common tickers.
    Call on application startup for faster first responses.
    """
    try:
        check_rate_limit(request)
        market_list = [m.strip().upper() for m in markets.split(",") if m.strip()]
        valid_markets = [m for m in market_list if m in VALID_MARKETS]
        
        if not valid_markets:
            raise HTTPException(status_code=400, detail="No valid markets provided")
        
        # Run preload in background
        await run_in_thread(preload_cache, valid_markets)
        
        return {
            "status": "ok",
            "message": f"Cache preloaded for {valid_markets}",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error preloading cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "service": "macro-control-system",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }
