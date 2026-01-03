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
from app.api import labs, portfolio, cluster_b, options, markets, security, orderbook, earnings, registry, macro
from app.api import portfolio_risk_api  # Portfolio Risk VaR System
from app.api import liquidity_api  # Liquidity Intelligence Engine
from app.api import screener_api  # QUANT360 Screener
from app.api import research_beta, research_macro_shock, research_style_map, research_regimes, research_correlation
from app.api import prices, quotes
from app.api import research_e  # Cluster E
from app.api import research_fg  # Cluster F+G
from app.api import monitor  # Monitor Command Center
from app.api import markets_daily  # Markets Daily Cognition Terminal
from app.api import nse_india  # NSE India Stock Market API (FREE)

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
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
)

# Security Middleware (OWASP Top 10 Compliant)
# Rate limiting, input validation, security headers, audit logging
try:
    from app.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)
    logger.info("Security middleware enabled: Rate limiting, security headers, audit logging")
except ImportError as e:
    logger.warning(f"Security middleware not loaded: {e}")

# Include Routers
# Include Routers
app.include_router(labs.router, prefix="/api/labs", tags=["labs"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(cluster_b.router, prefix="/api", tags=["cluster_b"])
app.include_router(options.router, prefix="/api/options", tags=["options"])
app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(security.router, prefix="/api/security", tags=["security"])
app.include_router(liquidity_api.router, prefix="/api", tags=["liquidity-intelligence"])
app.include_router(orderbook.router, prefix="/api/orderbook", tags=["orderbook"])
app.include_router(earnings.router, prefix="/api/earnings", tags=["earnings"])
app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
app.include_router(macro.router, prefix="/api/macro", tags=["macro"])
app.include_router(portfolio_risk_api.router, prefix="/api/portfolio-risk", tags=["portfolio-risk"])

# Price/Quote Routers
app.include_router(prices.router, tags=["prices"])
app.include_router(quotes.router, tags=["quotes"])

# Research Routers (Cluster D)
app.include_router(research_beta.router, prefix="/api/research", tags=["research"])
app.include_router(research_macro_shock.router, prefix="/api/research", tags=["research"])
app.include_router(research_style_map.router, prefix="/api/research", tags=["research"])
app.include_router(research_regimes.router, prefix="/api/research", tags=["research"])
app.include_router(research_correlation.router, prefix="/api/research", tags=["research"])

# Research Router (Cluster E)
app.include_router(research_e.router, tags=["research-e"])

# Research Router (Cluster F+G)
app.include_router(research_fg.router, prefix="/api", tags=["research-fg"])

# Monitor Command Center Router
app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])

# Markets Daily Cognition Terminal Router
app.include_router(markets_daily.router, prefix="/api/markets_daily", tags=["markets_daily"])

# NSE India Router (FREE - No API key needed)
app.include_router(nse_india.router, prefix="/api", tags=["nse-india"])

# Market Labs - 7-Engine Market Structure Analysis
from app.api import market_labs
app.include_router(market_labs.router, prefix="/api/market-labs", tags=["market-labs"])

# QUANT360 Screener - 8-Tab Market Intelligence
app.include_router(screener_api.router, prefix="/api", tags=["quant360-screener"])


# PCA Eigenphysics - Advanced PCA Analysis Terminal
from app.api import pca_eigenphysics
app.include_router(pca_eigenphysics.router, prefix="/api", tags=["pca-eigenphysics"])

# Trade Execution API - CATEGORY G, I, J
from app.api import trades_api
app.include_router(trades_api.router, prefix="/api", tags=["trades"])

# WebSocket API for live price streaming
from app.api import websocket_api
app.include_router(websocket_api.router, tags=["websocket"])

# ML God Stack - 11 Module ML Intelligence System (Labs → ML + Portfolio)
from app.api import ml_api
app.include_router(ml_api.router, prefix="/api", tags=["ml-god-stack"])

# Portfolio v2 - 29-Feature Institutional Portfolio System
from app.api import portfolio_v2
app.include_router(portfolio_v2.router, prefix="/api", tags=["portfolio-v2"])

# Payments API - Razorpay (INR) + Stripe (USD)
from app.api import payments_api
app.include_router(payments_api.router, prefix="/api", tags=["payments"])

# Accuracy Status API - Check enhancement status
from app.api import accuracy_status
app.include_router(accuracy_status.router, tags=["accuracy"])

# Alpha Models API - Momentum and Mean Reversion Intelligence
from app.api import alpha
app.include_router(alpha.router, prefix="/api/alpha", tags=["alpha-models"])



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

# --- MONITOR Page ---

@app.get("/api/monitor")
def get_monitor_data(horizon: str = "3mo"):
    """
    Data for the Monitor page.
    Returns real quantitative data for indices, sectors, breadth, and drawdowns.
    """
    try:
        import datetime
        end_date = datetime.datetime.now()
        days_map = {"3mo": 90, "1y": 365}
        
        # Helper functions for parallel execution
        def fetch_global():
            indices = ["DIA", "IWM", "QQQ", "SPY", "^CNXSC", "^GDAXI", "^KS11", "^NSEI"]
            start_date = end_date - datetime.timedelta(days=days_map.get(horizon, 90))
            df_global = data_loader.get_price_history(indices, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
            
            series_data = {}
            if not df_global.empty:
                if isinstance(df_global.columns, pd.MultiIndex):
                    closes = df_global.xs('Close', axis=1, level=0)
                else:
                    closes = df_global
                
                rets = closes.pct_change().fillna(0)
                cum_rets = (1 + rets).cumprod() * 100
                
                for col in cum_rets.columns:
                    series_data[col] = {
                        "dates": cum_rets.index.strftime('%Y-%m-%d').tolist(),
                        "close": cum_rets[col].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                    }
            return series_data

        def fetch_sectors():
            sectors = ["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE"]
            sector_start = end_date - datetime.timedelta(days=90)
            df_sectors = data_loader.get_price_history(sectors, start=sector_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
            
            sectors_data = {}
            if not df_sectors.empty:
                if isinstance(df_sectors.columns, pd.MultiIndex):
                    closes = df_sectors.xs('Close', axis=1, level=0)
                else:
                    closes = df_sectors
                    
                for col in closes.columns:
                    series = closes[col].dropna()
                    if len(series) > 0:
                        sectors_data[col] = {
                            "dates": series.index.strftime('%Y-%m-%d').tolist(),
                            "close": series.replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                        }
            return sectors_data

        def fetch_breadth():
            breadth_data = {"dates": [], "breadth_percent": [], "vix_scaled": []}
            try:
                # Breadth: % of US Universe > SMA 200
                us_universe = data_loader.get_universe("us")[:20] # Limit to top 20 for speed
                # Need 200 days prior to start to calc SMA200 properly, so fetch ~1 year + 90 days
                breadth_start = end_date - datetime.timedelta(days=365) 
                df_univ = data_loader.get_price_history(us_universe, start=breadth_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
                df_vix = data_loader.get_price_history(["^VIX"], start=breadth_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
                
                if not df_univ.empty and not df_vix.empty:
                    if isinstance(df_univ.columns, pd.MultiIndex):
                        univ_closes = df_univ.xs('Close', axis=1, level=0)
                    else:
                        univ_closes = df_univ
                    
                    # Calculate SMA 200
                    sma200 = univ_closes.rolling(window=200).mean()
                    
                    # Determine % above SMA200
                    above_sma = (univ_closes > sma200).sum(axis=1)
                    total_valid = sma200.notna().sum(axis=1)
                    breadth_pct = (above_sma / total_valid.replace(0, np.nan)).fillna(0) * 100
                    
                    # VIX
                    if isinstance(df_vix.columns, pd.MultiIndex):
                        vix_close = df_vix.xs('Close', axis=1, level=0)["^VIX"]
                    else:
                        vix_close = df_vix["^VIX"] if "^VIX" in df_vix.columns else df_vix.iloc[:, 0]
                    
                    # Align dates (last 90 days or horizon)
                    display_start = end_date - datetime.timedelta(days=days_map.get(horizon, 90))
                    common = breadth_pct.index.intersection(vix_close.index)
                    common = common[common >= display_start]
                    
                    breadth_pct = breadth_pct.loc[common]
                    vix_close = vix_close.loc[common]
                    
                    breadth_data = {
                        "dates": common.strftime('%Y-%m-%d').tolist(),
                        "breadth_percent": breadth_pct.replace([np.inf, -np.inf], np.nan).fillna(0).tolist(),
                        "vix_scaled": vix_close.replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                    }
            except Exception as e:
                logger.error(f"Error in breadth calc: {e}")
            return breadth_data

        def fetch_drawdowns():
            drawdowns_data = {}
            dd_indices = ["QQQ", "SPY", "^NSEI"]
            dd_start = end_date - datetime.timedelta(days=365*2)
            df_dd = data_loader.get_price_history(dd_indices, start=dd_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
            
            if not df_dd.empty:
                if isinstance(df_dd.columns, pd.MultiIndex):
                    closes = df_dd.xs('Close', axis=1, level=0)
                else:
                    closes = df_dd
                    
                for col in closes.columns:
                    dd = metrics.max_drawdown(closes[col])
                    drawdowns_data[col] = {
                        "dates": dd.index.strftime('%Y-%m-%d').tolist(),
                        "drawdown": dd.replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                    }
            return drawdowns_data

        # Execute in parallel
        executor = concurrent.futures.ThreadPoolExecutor()
        try:
            f_global = executor.submit(fetch_global)
            f_sectors = executor.submit(fetch_sectors)
            f_breadth = executor.submit(fetch_breadth)
            f_drawdowns = executor.submit(fetch_drawdowns)
            
            # Helper to get result with timeout
            def get_result_safe(f, name, timeout=10):
                try:
                    return f.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Timeout fetching {name}")
                    return {} if name != "breadth" else {"dates": [], "breadth_percent": [], "vix_scaled": []}
                except Exception as e:
                    logger.error(f"Error fetching {name}: {e}")
                    return {} if name != "breadth" else {"dates": [], "breadth_percent": [], "vix_scaled": []}

            return {
                "indices": ["DIA", "IWM", "QQQ", "SPY", "^CNXSC", "^GDAXI", "^KS11", "^NSEI"],
                "series": get_result_safe(f_global, "global", 10),
                "sectors": get_result_safe(f_sectors, "sectors", 10),
                "breadth": get_result_safe(f_breadth, "breadth", 15), # Give breadth a bit more time
                "drawdowns": get_result_safe(f_drawdowns, "drawdowns", 10)
            }
        finally:
            executor.shutdown(wait=False)

    except Exception as e:
        logger.error(f"Critical error in monitor endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# SIMPLE LIQUIDITY ENDPOINT - For Security Page
# =============================================================================

@app.get("/api/liquidity/{ticker}")
def get_liquidity_metrics(ticker: str):
    """
    Get liquidity metrics for a specific ticker.
    Used by the Security page to display liquidity info in header.
    
    Returns:
        - liquidity_label: HIGH, MEDIUM, LOW, VERY_LOW
        - liquidity_color: Tailwind color class
        - estimated_spread_bps: Estimated bid-ask spread in basis points
        - avg_volume: Average daily volume (20-day)
        - avg_dollar_volume: Average daily dollar volume
        - liquidity_score: Normalized 0-100 score
    """
    import yfinance as yf
    
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        # Calculate metrics
        avg_volume = hist['Volume'].tail(20).mean()
        avg_close = hist['Close'].tail(20).mean()
        avg_dollar_volume = avg_volume * avg_close if avg_close > 0 else 0
        
        # Calculate volatility for spread estimation
        returns = hist['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        
        # Estimate spread (simplified model: higher volatility + lower volume = higher spread)
        # Base spread inversely proportional to dollar volume, adjusted by volatility
        if avg_dollar_volume > 0:
            base_spread_bps = max(1, 100 / np.log10(avg_dollar_volume + 1))
            volatility_adj = 1 + volatility * 2  # Higher vol = wider spread
            estimated_spread_bps = base_spread_bps * volatility_adj
        else:
            estimated_spread_bps = 50  # Default high spread for illiquid
        
        # Liquidity score (0-100)
        # Based on dollar volume thresholds
        if avg_dollar_volume >= 100_000_000:  # $100M+/day
            liquidity_score = 95
            liquidity_label = "ULTRA"
            liquidity_color = "bg-terminal-cyan/20 text-terminal-cyan"
        elif avg_dollar_volume >= 10_000_000:  # $10M+/day
            liquidity_score = 80
            liquidity_label = "HIGH"
            liquidity_color = "bg-terminal-green/20 text-terminal-green"
        elif avg_dollar_volume >= 1_000_000:  # $1M+/day
            liquidity_score = 60
            liquidity_label = "MEDIUM"
            liquidity_color = "bg-terminal-yellow/20 text-terminal-yellow"
        elif avg_dollar_volume >= 100_000:  # $100K+/day
            liquidity_score = 40
            liquidity_label = "LOW"
            liquidity_color = "bg-terminal-orange/20 text-terminal-orange"
        else:
            liquidity_score = 20
            liquidity_label = "VERY_LOW"
            liquidity_color = "bg-terminal-red/20 text-terminal-red"
        
        return {
            "ticker": ticker.upper(),
            "liquidity_label": liquidity_label,
            "liquidity_color": liquidity_color,
            "estimated_spread_bps": round(estimated_spread_bps, 2),
            "avg_volume": round(avg_volume),
            "avg_dollar_volume": round(avg_dollar_volume),
            "liquidity_score": liquidity_score,
            "volatility_annual": round(volatility * 100, 2) if volatility else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching liquidity for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
