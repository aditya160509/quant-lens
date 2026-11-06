from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import uvicorn
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from pydantic import BaseModel
import concurrent.futures
from pathlib import Path

# Load environment variables from project root .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default search

from app import data_loader, metrics, factors
from app.api import options, markets, security, orderbook
from app.api import prices
from app.api import nse_india  # NSE India Stock Market API (FREE)
from app.api import factors_v2  # Factors V2 - 14-feature institutional factor intelligence
from app.api import research_v2  # Research V2 - empirical finance test battery
from app.api import screener_v2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quant360 API",
    description="Backend for Quant360 Terminal",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS - Use specific origins in production
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# In production, set CORS_ALLOW_ALL=false
import os
if os.environ.get("CORS_ALLOW_ALL", "true").lower() == "true":
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False if "*" in ALLOWED_ORIGINS else True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "Retry-After",
        "X-Request-ID",
    ],
)

# Security Middleware (OWASP Top 10 Compliant)
# Rate limiting, input validation, security headers, audit logging
try:
    from app.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)
    logger.info("Security middleware enabled: Rate limiting, security headers, audit logging")
except ImportError as e:
    logger.warning(f"Security middleware not loaded: {e}")

# Aggregate Studio V2 request telemetry without retaining payloads or secrets.
from app.studio_v2.shared.observability import StudioObservabilityMiddleware
# Compress the large JSON results of the ML and Research labs (often 0.5-2 MB, ~8x smaller gzipped).
# Scoped by path so streaming endpoints elsewhere are never buffered.
from starlette.middleware.gzip import GZipMiddleware

class _LabGZip(GZipMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith(("/api/ml/v2", "/api/labs/research")):
            await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)

app.add_middleware(_LabGZip, minimum_size=1024)
app.add_middleware(StudioObservabilityMiddleware)

app.include_router(options.router, prefix="/api/options", tags=["options"])
app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(security.router, prefix="/api/security", tags=["security"])
app.include_router(orderbook.router, prefix="/api/orderbook", tags=["orderbook"])

# Price/Quote Routers
app.include_router(prices.router, tags=["prices"])

# Factors V2 - Institutional Factor Intelligence
# Mounted under /api/labs/factors/v2 so legacy /api/labs/factors remains untouched.
app.include_router(factors_v2.router, prefix="/api", tags=["factors-v2"])
app.include_router(research_v2.router, prefix="/api", tags=["research-v2"])
from app.api import research_v2_reports; app.include_router(research_v2_reports.router, prefix="/api", tags=["research-v2-reports"])
from app.api import research_v2_signals; app.include_router(research_v2_signals.router, prefix="/api", tags=["research-v2-signals"])
from app.api import research_v2_projects; app.include_router(research_v2_projects.router, prefix="/api", tags=["research-v2-projects"])

# NSE India Router (FREE - No API key needed)
app.include_router(nse_india.router, prefix="/api", tags=["nse-india"])

app.include_router(screener_v2.router, prefix="/api", tags=["screener-v2"])

# PCA V2 quantitative feature suite
from app.api import pca_v2
app.include_router(pca_v2.router, prefix="/api", tags=["pca-v2"])

# Trade Execution API - CATEGORY G, I, J
from app.api import trades_api
app.include_router(trades_api.router, prefix="/api", tags=["trades"])

# WebSocket API for live price streaming
from app.api import websocket_api
app.include_router(websocket_api.router, tags=["websocket"])

# ML V2
from app.api.ml_v2 import router as ml_v2_router
app.include_router(ml_v2_router, prefix="/api", tags=["ml-v2"])

# Volatility V2 quantitative engines
from app.api import volatility_v2
app.include_router(volatility_v2.router, prefix="/api")

# Portfolio V2 institutional portfolio engines
from app.api import portfolio_v2
app.include_router(portfolio_v2.router, prefix="/api")

# CLI Kernel Router
from app.api import cli as cli_api
app.include_router(cli_api.router, prefix="/api", tags=["cli"])

# Sovereign Algo Studio - Institutional Model Engineering
from app.routers import studio as studio_router
app.include_router(studio_router.router, prefix="/api", tags=["sovereign-algo-studio"])

# Studio V2 is retired. Only the data-studio and health endpoints stay mounted
# because the canonical Studio data inspector (useDataStudio) still calls them.
from fastapi import APIRouter
from app.studio_v2.router import router as studio_v2_router
studio_v2_retained = APIRouter()
studio_v2_retained.routes.extend(
    route for route in studio_v2_router.routes
    if route.path.startswith(("/api/v2/data-studio/", "/api/v2/health/"))
)
app.include_router(studio_v2_retained)

# Sovereign Workspace - Command-and-Control Hub (Parquet-First)
from app.api import sovereign
app.include_router(sovereign.router, prefix="/api/sovereign", tags=["sovereign-workspace"])

# ML v2 - Extended Intelligence System# Removed redundant v2 router as it's merged into labs.py

# Import rate limiter for stats
try:
    from app.services.rate_limiter import get_cache_stats, clear_all_caches
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False

# Import API tracker for monitoring yfinance usage
try:
    from app.services.api_tracker import get_tracker_stats, reset_tracker, track_api_call
    API_TRACKER_AVAILABLE = True
    logger.info("API tracker enabled: Monitoring yfinance and external API usage")
except ImportError as e:
    API_TRACKER_AVAILABLE = False
    logger.warning(f"API tracker not loaded: {e}")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Quant360 Backend is running"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/cache/stats")
def cache_stats():
    """Get cache and rate limiter statistics"""
    if RATE_LIMITER_AVAILABLE:
        return {
            "status": "ok",
            **get_cache_stats(),
            "message": "Cache is active - preventing 429 errors"
        }
    return {"status": "disabled", "message": "Rate limiter not available"}

@app.post("/api/cache/clear")
def clear_cache():
    """Clear all caches"""
    if RATE_LIMITER_AVAILABLE:
        clear_all_caches()
        return {"status": "ok", "message": "All caches cleared"}
    return {"status": "disabled", "message": "Rate limiter not available"}

# =============================================================================
# API USAGE TRACKER - Monitor yfinance and external API calls per module
# =============================================================================

@app.get("/api/tracker/stats")
def api_tracker_stats():
    """
    Get API usage statistics to identify which modules are making heavy yfinance calls.
    
    Returns:
        - modules_ranked: List of modules sorted by call count
        - top_tickers: Most frequently fetched tickers
        - total_calls: Total API calls in tracking window
        - total_yf_calls: Total yfinance calls
    """
    if API_TRACKER_AVAILABLE:
        stats = get_tracker_stats()
        return {
            "status": "ok",
            **stats,
            "message": "API usage tracker active - monitor yfinance load here"
        }
    return {"status": "disabled", "message": "API tracker not available"}

@app.post("/api/tracker/reset")
def api_tracker_reset():
    """Reset API usage tracking data."""
    if API_TRACKER_AVAILABLE:
        reset_tracker()
        return {"status": "ok", "message": "API tracker reset - all stats cleared"}
    return {"status": "disabled", "message": "API tracker not available"}

@app.get("/api/universe")
def get_universe_endpoint():
    """Get the full dynamic universe of tickers."""
    us = data_loader.get_universe("us")
    india = data_loader.get_universe("india")
    etfs = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "USO", "XLF", "XLK", "XLE", "XLV"]
    all_tickers = list(set(us + india + etfs))
    all_tickers.sort()
    return all_tickers

# =============================================================================
# SIMPLE LIQUIDITY ENDPOINT - For Security Page
# =============================================================================

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
