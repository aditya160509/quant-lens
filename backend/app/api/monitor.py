"""
Monitor API Router - Bloomberg-style Command Center Endpoints
Provides real-time market monitoring data with audit trails and quality scores.
Now with aggressive caching to prevent 429 (Too Many Requests) errors.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, time
from pydantic import BaseModel
import pytz
import numpy as np
import pandas as pd
import logging
import hashlib
import concurrent.futures
import time as time_module

import yfinance as yf
from app import data_loader
from app.services import universe

# Import rate limiting and caching
try:
    from app.services.rate_limiter import global_cache, yfinance_limiter, backoff_handler
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    global_cache = None

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Caching Helper
# ============================================================================

def get_cached_yf_data(symbols: List[str], period: str = "2d") -> pd.DataFrame:
    """
    Get yfinance data with caching and rate limiting.
    Returns cached data if rate limited or on error.
    """
    cache_key = f"yf_download:{','.join(sorted(symbols[:10]))}:{period}"
    
    # Check cache first (5 minute TTL)
    if CACHE_AVAILABLE and global_cache:
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh and cached is not None:
            logger.debug(f"[Cache] Hit for {len(symbols)} symbols")
            return cached
        
        # Check backoff
        if backoff_handler.should_skip("yfinance"):
            if cached is not None:
                logger.info("[Cache] Returning stale data due to backoff")
                return cached
            logger.warning("[Backoff] Skipping yfinance request")
            return pd.DataFrame()
        
        # Rate limit
        if not yfinance_limiter.try_acquire():
            if cached is not None:
                logger.info("[RateLimit] Returning stale data")
                return cached
            return pd.DataFrame()
    
    try:
        tickers_str = " ".join(symbols[:50])  # Limit batch
        data = yf.download(tickers_str, period=period, progress=False, threads=True)
        
        # Cache successful result
        if CACHE_AVAILABLE and global_cache and not data.empty:
            global_cache.set(cache_key, data, ttl=300)  # 5 min cache
            backoff_handler.record_success("yfinance")
        
        return data
    except Exception as e:
        logger.error(f"[YF] Download error: {e}")
        if CACHE_AVAILABLE:
            backoff_handler.record_error("yfinance")
        
        # Return stale cache if available
        if CACHE_AVAILABLE and global_cache:
            cached, _ = global_cache.get(cache_key)
            if cached is not None:
                return cached
        
        return pd.DataFrame()


def get_cached_ticker(symbol: str, period: str = "2d") -> Optional[pd.DataFrame]:
    """Get single ticker data with caching."""
    cache_key = f"yf_ticker:{symbol}:{period}"
    
    if CACHE_AVAILABLE and global_cache:
        cached, is_fresh = global_cache.get(cache_key)
        if is_fresh and cached is not None:
            return cached
        
        if backoff_handler.should_skip("yfinance"):
            return cached if cached is not None else None
        
        if not yfinance_limiter.try_acquire():
            return cached if cached is not None else None
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if CACHE_AVAILABLE and global_cache and not hist.empty:
            global_cache.set(cache_key, hist, ttl=300)
            backoff_handler.record_success("yfinance")
        
        return hist
    except Exception as e:
        logger.error(f"[YF] Ticker error {symbol}: {e}")
        if CACHE_AVAILABLE:
            backoff_handler.record_error("yfinance")
        
        if CACHE_AVAILABLE and global_cache:
            cached, _ = global_cache.get(cache_key)
            return cached
        return None

# ============================================================================
# Response Models
# ============================================================================

class AuditBlock(BaseModel):
    cacheHit: bool = False
    stalenessSec: int = 0
    warnings: List[str] = []
    sources: List[str] = []
    inputHash: Optional[str] = None

class QualityBlock(BaseModel):
    missingPct: float = 0.0
    confidenceLabel: str = "high"  # high, medium, low

# ============================================================================
# Utility Functions
# ============================================================================

def get_audit_hash(data: Any) -> str:
    """Generate a hash for audit trail."""
    return hashlib.md5(str(data).encode()).hexdigest()[:12]

def compute_staleness(updated_at: datetime) -> int:
    """Compute seconds since last update."""
    return int((datetime.now(pytz.UTC) - updated_at).total_seconds())

def safe_float(val) -> float:
    """Safely convert to float, handling NaN/Inf."""
    if val is None or pd.isna(val) or np.isinf(val):
        return 0.0
    return float(val)

# ============================================================================
# Ticker Pills Endpoint
# ============================================================================

@router.get("/tickers")
def get_monitor_tickers():
    """
    GET /api/monitor/tickers
    Returns curated list of ticker pills with price, change, changePct.
    OPTIMIZED: Uses single batched yf.download() instead of individual requests.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Curated list: US majors, India proxy, VIX, FX, Crypto
        ticker_config = [
            {"symbol": "SPY", "name": "S&P 500 ETF", "market": "US", "currency": "USD"},
            {"symbol": "QQQ", "name": "Nasdaq 100 ETF", "market": "US", "currency": "USD"},
            {"symbol": "DIA", "name": "Dow Jones ETF", "market": "US", "currency": "USD"},
            {"symbol": "IWM", "name": "Russell 2000 ETF", "market": "US", "currency": "USD"},
            {"symbol": "^VIX", "name": "VIX", "market": "US", "currency": "USD"},
            {"symbol": "^NSEI", "name": "Nifty 50", "market": "IN", "currency": "INR"},
            {"symbol": "^BSESN", "name": "Sensex", "market": "IN", "currency": "INR"},
            {"symbol": "GLD", "name": "Gold ETF", "market": "US", "currency": "USD"},
            {"symbol": "TLT", "name": "20Y Treasury ETF", "market": "US", "currency": "USD"},
        ]
        
        symbols = [t["symbol"] for t in ticker_config]
        
        try:
            # ===== OPTIMIZATION: Single batched download =====
            # Instead of 9 separate ticker requests, use ONE yf.download() call
            data = get_cached_yf_data(symbols, period="2d")
            
            items = []
            missing_count = 0
            
            if data.empty:
                # All failed - likely rate limited
                warnings.append("All data fetch failed - possibly rate limited")
                return {
                    "asOf": now.isoformat(),
                    "items": [],
                    "audit": {"cacheHit": False, "stalenessSec": 0, "warnings": warnings},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            # Handle multi-index columns from yf.download
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data[['Close']] if 'Close' in data.columns else pd.DataFrame()
            
            for cfg in ticker_config:
                sym = cfg["symbol"]
                # Try to find the column (yfinance sometimes strips ^)
                col_sym = sym.replace("^", "") if sym not in closes.columns else sym
                
                if col_sym in closes.columns:
                    series = closes[col_sym].dropna()
                    
                    if len(series) >= 2:
                        last = safe_float(series.iloc[-1])
                        prev = safe_float(series.iloc[-2])
                        change = last - prev
                        changePct = (change / prev * 100) if prev != 0 else 0
                        
                        items.append({
                            "symbol": sym,
                            "name": cfg["name"],
                            "last": round(last, 2),
                            "change": round(change, 2),
                            "changePct": round(changePct, 2),
                            "currency": cfg["currency"],
                            "market": cfg["market"],
                            "updatedAt": now.isoformat()
                        })
                    elif len(series) == 1:
                        last = safe_float(series.iloc[-1])
                        items.append({
                            "symbol": sym,
                            "name": cfg["name"],
                            "last": round(last, 2),
                            "change": 0,
                            "changePct": 0,
                            "currency": cfg["currency"],
                            "market": cfg["market"],
                            "updatedAt": now.isoformat()
                        })
                        warnings.append(f"{sym}: only 1 day of data")
                    else:
                        missing_count += 1
                        warnings.append(f"{sym}: no data in series")
                else:
                    missing_count += 1
                    warnings.append(f"{sym}: not found in batch response")
            
            missing_pct = (missing_count / len(ticker_config)) * 100 if ticker_config else 0
            confidence = "high" if missing_pct < 10 else "medium" if missing_pct < 30 else "low"
            
            return {
                "asOf": now.isoformat(),
                "items": items,
                "audit": {
                    "cacheHit": False,
                    "stalenessSec": 0,
                    "warnings": warnings,
                    "optimization": "batched_download"  # Flag for debugging
                },
                "quality": {
                    "missingPct": round(missing_pct, 1),
                    "confidenceLabel": confidence
                }
            }
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return {
                "asOf": now.isoformat(),
                "items": [],
                "audit": {"cacheHit": False, "stalenessSec": 0, "warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Breadth / Temperature Bar Endpoint
# ============================================================================

@router.get("/breadth")
def get_monitor_breadth(market: str = Query("IN", description="Market: IN or US")):
    """
    GET /api/monitor/breadth
    Returns advances, declines, unchanged counts for temperature bar.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Get universe based on market
        if market == "IN":
            univ_name = "india_nse"
            symbols = universe.get_universe_list("india_nse")[:100]  # Top 100 for speed
        else:
            univ_name = "us_equities"
            symbols = universe.get_universe_list("us_equities")[:100]
        
        if not symbols:
            return {
                "asOf": now.isoformat(),
                "universe": {"name": univ_name, "count": 0},
                "advances": 0, "declines": 0, "unchanged": 0,
                "advPct": 0, "decPct": 0, "uncPct": 0,
                "audit": {"inputs": [], "stalenessSec": 0, "warnings": ["No symbols in universe"]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch current prices
            tickers_str = " ".join(symbols[:50])  # Limit batch size
            data = yf.download(tickers_str, period="2d", progress=False, threads=True)
            
            if data.empty:
                warnings.append("No price data returned")
                return {
                    "asOf": now.isoformat(),
                    "universe": {"name": univ_name, "count": len(symbols)},
                    "advances": 0, "declines": 0, "unchanged": 0,
                    "advPct": 0, "decPct": 0, "uncPct": 0,
                    "audit": {"inputs": symbols[:10], "stalenessSec": 0, "warnings": warnings},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            # Handle single vs multi-column
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data[['Close']] if 'Close' in data.columns else data
            
            # Compute daily change
            eps = 0.0005  # Threshold for unchanged
            advances = 0
            declines = 0
            unchanged = 0
            missing = 0
            
            for col in closes.columns:
                series = closes[col].dropna()
                if len(series) >= 2:
                    pct_change = (series.iloc[-1] - series.iloc[-2]) / series.iloc[-2]
                    if pct_change > eps:
                        advances += 1
                    elif pct_change < -eps:
                        declines += 1
                    else:
                        unchanged += 1
                else:
                    missing += 1
            
            total = advances + declines + unchanged
            if total == 0:
                total = 1  # Avoid division by zero
            
            missing_pct = (missing / len(symbols)) * 100
            confidence = "high" if missing_pct < 20 else "medium" if missing_pct < 50 else "low"
            
            return {
                "asOf": now.isoformat(),
                "universe": {"name": univ_name, "count": len(symbols)},
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "advPct": round(advances / total * 100, 1),
                "decPct": round(declines / total * 100, 1),
                "uncPct": round(unchanged / total * 100, 1),
                "audit": {
                    "inputs": symbols[:5],
                    "stalenessSec": 0,
                    "warnings": warnings
                },
                "quality": {
                    "missingPct": round(missing_pct, 1),
                    "confidenceLabel": confidence
                }
            }
        except Exception as e:
            logger.error(f"Error computing breadth: {e}")
            warnings.append(str(e))
            return {
                "asOf": now.isoformat(),
                "universe": {"name": univ_name, "count": len(symbols)},
                "advances": 0, "declines": 0, "unchanged": 0,
                "advPct": 0, "decPct": 0, "uncPct": 0,
                "audit": {"inputs": symbols[:5], "stalenessSec": 0, "warnings": warnings},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Leaders & Laggards Endpoint
# ============================================================================

@router.get("/leaders")
def get_monitor_leaders(
    market: str = Query("IN", description="Market: IN or US"),
    k: int = Query(10, description="Number of top movers")
):
    """
    GET /api/monitor/leaders
    Returns top gainers and losers for the given market.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Get universe
        if market == "IN":
            univ_name = "india_nse"
            symbols = universe.get_universe_list("india_nse")[:100]
        else:
            univ_name = "us_equities"
            symbols = universe.get_universe_list("us_equities")[:100]
        
        if not symbols:
            return {
                "asOf": now.isoformat(),
                "gainers": [], "losers": [],
                "audit": {"universe": univ_name, "warnings": ["No symbols"]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch 2-day history
            tickers_str = " ".join(symbols[:50])
            data = yf.download(tickers_str, period="2d", progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "gainers": [], "losers": [],
                    "audit": {"universe": univ_name, "warnings": ["No data"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data
            
            # Compute changes
            changes = []
            missing = 0
            for col in closes.columns:
                series = closes[col].dropna()
                if len(series) >= 2:
                    last = series.iloc[-1]
                    prev = series.iloc[-2]
                    pct = ((last - prev) / prev) * 100 if prev != 0 else 0
                    changes.append({"symbol": col, "changePct": round(pct, 2), "last": round(last, 2)})
                else:
                    missing += 1
            
            # Sort
            changes.sort(key=lambda x: x["changePct"], reverse=True)
            gainers = changes[:k]
            losers = changes[-k:][::-1] if len(changes) >= k else changes[::-1]
            
            missing_pct = (missing / len(symbols)) * 100
            confidence = "high" if missing_pct < 20 else "medium" if missing_pct < 50 else "low"
            
            return {
                "asOf": now.isoformat(),
                "gainers": gainers,
                "losers": losers,
                "audit": {"universe": univ_name, "warnings": warnings},
                "quality": {"missingPct": round(missing_pct, 1), "confidenceLabel": confidence}
            }
        except Exception as e:
            logger.error(f"Error fetching leaders: {e}")
            return {
                "asOf": now.isoformat(),
                "gainers": [], "losers": [],
                "audit": {"universe": univ_name, "warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Flows Snapshot Endpoint
# ============================================================================

@router.get("/flows")
def get_monitor_flows():
    """
    GET /api/monitor/flows
    Returns FII/DII flows, SPY/QQQ proxy flows, VIX change.
    Note: FII/DII are unavailable without official data source - returns proxy.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        missing_inputs = []
        
        result = {
            "asOf": now.isoformat(),
            "india": {"fiiNet": None, "diiNet": None, "unit": "INR Cr"},
            "us": {"spyFlow": None, "qqqFlow": None, "unit": "USD M", "isProxy": True},
            "vix": {"last": None, "change": None, "changePct": None},
            "audit": {"sources": [], "warnings": []},
            "quality": {"missingPct": 0, "confidenceLabel": "low"}
        }
        
        # FII/DII - Not available via free API, mark as unavailable
        warnings.append("FII/DII: No free data source available")
        missing_inputs.append("FII/DII official daily data")
        
        try:
            # SPY/QQQ flow proxy: volume * price * sign(change)
            for sym, key in [("SPY", "spyFlow"), ("QQQ", "qqqFlow")]:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period="2d")
                if len(hist) >= 2:
                    last_close = hist['Close'].iloc[-1]
                    prev_close = hist['Close'].iloc[-2]
                    volume = hist['Volume'].iloc[-1]
                    change = last_close - prev_close
                    sign = 1 if change >= 0 else -1
                    flow_proxy = (volume * last_close * sign) / 1e6  # In millions
                    result["us"][key] = round(flow_proxy, 1)
                    result["audit"]["sources"].append(f"yfinance:{sym}")
                else:
                    missing_inputs.append(f"{sym} history")
            
            # VIX
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="2d")
            if len(vix_hist) >= 2:
                vix_last = vix_hist['Close'].iloc[-1]
                vix_prev = vix_hist['Close'].iloc[-2]
                vix_change = vix_last - vix_prev
                vix_pct = (vix_change / vix_prev) * 100 if vix_prev != 0 else 0
                result["vix"] = {
                    "last": round(vix_last, 2),
                    "change": round(vix_change, 2),
                    "changePct": round(vix_pct, 2)
                }
                result["audit"]["sources"].append("yfinance:^VIX")
            else:
                missing_inputs.append("VIX history")
                
        except Exception as e:
            warnings.append(f"Error fetching US data: {str(e)[:50]}")
        
        # Calculate quality
        total_fields = 5  # fiiNet, diiNet, spyFlow, qqqFlow, vix
        missing = len(missing_inputs)
        missing_pct = (missing / total_fields) * 100
        result["quality"]["missingPct"] = round(missing_pct, 1)
        result["quality"]["confidenceLabel"] = "low" if missing_pct > 30 else "medium"
        result["audit"]["warnings"] = warnings + [f"Missing: {m}" for m in missing_inputs]
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FX & Crypto Endpoint
# ============================================================================

@router.get("/fxcrypto")
def get_monitor_fxcrypto():
    """
    GET /api/monitor/fxcrypto
    Returns FX pairs (USDINR, EURUSD) and crypto (BTC, ETH).
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        pairs = [
            {"symbol": "USDINR=X", "display": "USDINR", "unit": "INR"},
            {"symbol": "EURUSD=X", "display": "EURUSD", "unit": "USD"},
            {"symbol": "DX-Y.NYB", "display": "DXY", "unit": "USD"},
            {"symbol": "BTC-USD", "display": "BTC", "unit": "USD"},
            {"symbol": "ETH-USD", "display": "ETH", "unit": "USD"},
        ]
        
        items = []
        missing = 0
        
        for pair in pairs:
            try:
                ticker = yf.Ticker(pair["symbol"])
                hist = ticker.history(period="2d")
                
                if len(hist) >= 2:
                    last = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change = last - prev
                    changePct = (change / prev) * 100 if prev != 0 else 0
                    
                    items.append({
                        "symbol": pair["display"],
                        "last": round(last, 4 if "USD" in pair["display"] else 2),
                        "change": round(change, 4 if "USD" in pair["display"] else 2),
                        "changePct": round(changePct, 2),
                        "unit": pair["unit"]
                    })
                elif len(hist) == 1:
                    items.append({
                        "symbol": pair["display"],
                        "last": round(hist['Close'].iloc[-1], 4),
                        "change": 0,
                        "changePct": 0,
                        "unit": pair["unit"]
                    })
                    warnings.append(f"{pair['display']}: only 1 day data")
                else:
                    missing += 1
                    warnings.append(f"{pair['display']}: no data")
            except Exception as e:
                missing += 1
                warnings.append(f"{pair['display']}: {str(e)[:30]}")
        
        missing_pct = (missing / len(pairs)) * 100
        confidence = "high" if missing_pct < 20 else "medium" if missing_pct < 50 else "low"
        
        return {
            "asOf": now.isoformat(),
            "items": items,
            "audit": {"warnings": warnings},
            "quality": {"missingPct": round(missing_pct, 1), "confidenceLabel": confidence}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Regime Tags Endpoint
# ============================================================================

@router.get("/regime")
def get_monitor_regime(
    market: str = Query("IN", description="Market: IN or US"),
    index: str = Query("^NSEI", description="Index symbol"),
    window: str = Query("2y", description="Lookback window")
):
    """
    GET /api/monitor/regime
    Returns volatility, trend, and liquidity regime tags with drivers.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Default response
        result = {
            "asOf": now.isoformat(),
            "volatility": {"score": 50, "label": "normal"},
            "trend": {"score": 50, "label": "chop"},
            "liquidity": {"score": 50, "label": "normal"},
            "drivers": [],
            "evidence": [],
            "audit": {"inputHash": "", "stalenessSec": 0, "warnings": []},
            "quality": {"missingPct": 0, "confidenceLabel": "medium"}
        }
        
        try:
            # Fetch 2 years of data
            ticker = yf.Ticker(index)
            hist = ticker.history(period="2y")
            
            if len(hist) < 60:
                warnings.append(f"Insufficient history: {len(hist)} days")
                result["quality"]["confidenceLabel"] = "low"
                result["audit"]["warnings"] = warnings
                return result
            
            closes = hist['Close']
            volumes = hist['Volume']
            
            # === Volatility Regime ===
            window_vol = 20
            returns = np.log(closes / closes.shift(1)).dropna()
            rolling_vol = returns.rolling(window=window_vol).std() * np.sqrt(252)
            current_vol = rolling_vol.iloc[-1]
            vol_pctile = (rolling_vol < current_vol).mean() * 100
            
            if vol_pctile < 33:
                vol_label = "low"
            elif vol_pctile < 66:
                vol_label = "normal"
            else:
                vol_label = "high"
            
            result["volatility"] = {"score": int(vol_pctile), "label": vol_label}
            result["drivers"].append({
                "name": "annualized_vol",
                "value": round(current_vol * 100, 1),
                "unit": "%",
                "explanation": f"20-day rolling volatility at {vol_pctile:.0f}th percentile of 2y history"
            })
            
            # === Trend Regime ===
            window_trend = 60
            if len(closes) >= window_trend:
                y = np.log(closes.iloc[-window_trend:].values)
                x = np.arange(window_trend)
                slope, _ = np.polyfit(x, y, 1)
                returns_std = returns.iloc[-window_trend:].std()
                slope_norm = slope / returns_std if returns_std > 0 else 0
                
                # Historical slope distribution
                slopes = []
                for i in range(window_trend, len(closes)):
                    y_hist = np.log(closes.iloc[i-window_trend:i].values)
                    s, _ = np.polyfit(np.arange(window_trend), y_hist, 1)
                    slopes.append(s)
                trend_pctile = (np.array(slopes) < slope).mean() * 100
                
                t = 0.15
                if slope_norm > t:
                    trend_label = "uptrend"
                elif slope_norm < -t:
                    trend_label = "downtrend"
                else:
                    trend_label = "chop"
                
                result["trend"] = {"score": int(trend_pctile), "label": trend_label}
                result["drivers"].append({
                    "name": "slope_normalized",
                    "value": round(slope_norm, 3),
                    "unit": "ratio",
                    "explanation": f"60-day log slope normalized by volatility"
                })
            
            # === Liquidity Regime ===
            window_liq = 60
            if len(volumes) >= window_liq:
                recent_vol = volumes.iloc[-5:].mean()
                rolling_avg = volumes.rolling(window=5).mean()
                liq_pctile = (rolling_avg < recent_vol).mean() * 100
                
                if liq_pctile < 33:
                    liq_label = "thin"
                elif liq_pctile < 66:
                    liq_label = "normal"
                else:
                    liq_label = "high"
                
                result["liquidity"] = {"score": int(liq_pctile), "label": liq_label}
                result["drivers"].append({
                    "name": "volume_5d_avg",
                    "value": int(recent_vol),
                    "unit": "shares",
                    "explanation": f"5-day avg volume at {liq_pctile:.0f}th percentile"
                })
            
            # Evidence
            result["evidence"] = [
                {"seriesId": index, "source": "yfinance", "transformChain": ["log_returns", "rolling_std", "percentile_rank"]}
            ]
            result["audit"]["inputHash"] = get_audit_hash(f"{index}_{window}")
            result["audit"]["warnings"] = warnings
            result["quality"]["confidenceLabel"] = "high" if len(warnings) == 0 else "medium"
            
        except Exception as e:
            logger.error(f"Error computing regime: {e}")
            warnings.append(str(e))
            result["audit"]["warnings"] = warnings
            result["quality"]["confidenceLabel"] = "low"
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Options Snapshot Endpoint
# ============================================================================

@router.get("/options")
def get_monitor_options(
    nifty: bool = Query(True, description="Nifty options if true, else SPY"),
    window: str = Query("1y", description="IV percentile lookback")
):
    """
    GET /api/monitor/options
    Returns PCR, max pain, IV percentile for Nifty or SPY.
    Note: NSE options not available via yfinance - falls back to SPY.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        result = {
            "asOf": now.isoformat(),
            "pcr": {"value": None, "unit": "ratio"},
            "maxPain": {"value": None, "unit": "price"},
            "ivPctile": {"value": None, "unit": "percentile"},
            "audit": {"sources": [], "warnings": []},
            "quality": {"missingPct": 100, "confidenceLabel": "low"}
        }
        
        # NSE options not available via yfinance
        if nifty:
            warnings.append("Nifty options: No free data source (NSE not in yfinance)")
            warnings.append("Falling back to unavailable state")
            result["audit"]["warnings"] = warnings
            return result
        
        # Try SPY options
        try:
            spy = yf.Ticker("SPY")
            expirations = spy.options
            
            if not expirations:
                warnings.append("SPY: No option expirations available")
                result["audit"]["warnings"] = warnings
                return result
            
            # Get nearest expiration
            nearest_exp = expirations[0]
            chain = spy.option_chain(nearest_exp)
            calls = chain.calls
            puts = chain.puts
            
            # PCR: Put OI / Call OI
            total_call_oi = calls['openInterest'].sum()
            total_put_oi = puts['openInterest'].sum()
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            result["pcr"] = {"value": round(pcr, 3), "unit": "ratio"}
            
            # Max Pain calculation
            strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
            spot = spy.history(period="1d")['Close'].iloc[-1]
            
            min_pain = float('inf')
            max_pain_strike = spot
            
            for s in strikes:
                pain = 0
                # Call pain
                for _, row in calls.iterrows():
                    if s > row['strike']:
                        pain += (s - row['strike']) * row['openInterest']
                # Put pain
                for _, row in puts.iterrows():
                    if s < row['strike']:
                        pain += (row['strike'] - s) * row['openInterest']
                
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = s
            
            result["maxPain"] = {"value": round(max_pain_strike, 2), "unit": "price"}
            
            # IV percentile - use VIX as proxy
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="1y")
            if len(vix_hist) > 20:
                current_vix = vix_hist['Close'].iloc[-1]
                iv_pctile = (vix_hist['Close'] < current_vix).mean() * 100
                result["ivPctile"] = {"value": int(iv_pctile), "unit": "percentile"}
            
            result["audit"]["sources"] = ["yfinance:SPY", "yfinance:^VIX"]
            result["quality"]["missingPct"] = 0
            result["quality"]["confidenceLabel"] = "medium"
            
        except Exception as e:
            warnings.append(f"Options error: {str(e)[:50]}")
        
        result["audit"]["warnings"] = warnings
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Schedule Endpoint
# ============================================================================

@router.get("/schedule")
def get_monitor_schedule(
    market: str = Query("IN", description="Market: IN or US"),
    date: str = Query(None, description="Date YYYYMMDD, defaults to today")
):
    """
    GET /api/monitor/schedule
    Returns earnings, macro events, and speaker schedules.
    Note: Limited free sources - returns stub with warnings.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        result = {
            "asOf": now.isoformat(),
            "earnings": [],
            "macro": [],
            "speakers": [],
            "audit": {"warnings": []},
            "quality": {"missingPct": 0, "confidenceLabel": "medium"}
        }
        
        # Try to get earnings from yfinance calendar
        try:
            # Get watchlist tickers
            if market == "IN":
                tickers = universe.get_universe_list("india_nse")[:20]
            else:
                tickers = universe.get_universe_list("us_equities")[:20]
            
            today = datetime.now().date()
            for sym in tickers[:5]:  # Limit for speed
                try:
                    t = yf.Ticker(sym)
                    cal = t.calendar
                    if cal is not None and not cal.empty:
                        # Check if earnings are today
                        if 'Earnings Date' in cal.index:
                            earn_date = cal.loc['Earnings Date']
                            if isinstance(earn_date, pd.Series):
                                earn_date = earn_date.iloc[0]
                            if hasattr(earn_date, 'date') and earn_date.date() == today:
                                result["earnings"].append({
                                    "symbol": sym,
                                    "when": "today",
                                    "estimate": None
                                })
                except:
                    pass
        except Exception as e:
            warnings.append(f"Earnings fetch error: {str(e)[:30]}")
        
        # Macro events and speakers - no free real-time source
        warnings.append("Macro events: No free API available")
        warnings.append("Fed/RBI speakers: No free API available")
        
        if not result["earnings"]:
            result["earnings"].append({
                "symbol": "N/A",
                "when": "No earnings today in tracked universe",
                "estimate": None
            })
        
        result["audit"]["warnings"] = warnings
        result["quality"]["missingPct"] = 60  # Missing macro & speakers
        result["quality"]["confidenceLabel"] = "low"
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# News Endpoint
# ============================================================================

@router.get("/news")
def get_monitor_news(
    region: str = Query("IN", description="Region: IN or US"),
    k: int = Query(20, description="Number of items to return")
):
    """
    GET /api/monitor/news
    Returns aggregated news from yfinance for major tickers.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        result = {
            "asOf": now.isoformat(),
            "items": [],
            "clusters": [],
            "audit": {"sources": [], "warnings": []},
            "quality": {"missingPct": 0, "confidenceLabel": "medium"}
        }
        
        # Use yfinance news for major tickers
        if region == "IN":
            news_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
        else:
            news_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ"]
        
        all_news = []
        sources_used = []
        
        for ticker_sym in news_tickers[:5]:  # Limit for speed
            try:
                ticker = yf.Ticker(ticker_sym)
                news = ticker.news
                
                if news:
                    sources_used.append(f"yfinance:{ticker_sym}")
                    for item in news[:5]:  # Limit per ticker
                        # New yfinance format: data is nested in 'content' key
                        content = item.get("content", item)
                        
                        # Extract title
                        title = content.get("title", item.get("title", ""))
                        
                        # Extract publisher
                        provider = content.get("provider", {})
                        publisher = provider.get("displayName", item.get("publisher", "News"))
                        
                        # Extract URL
                        canonical = content.get("canonicalUrl", {})
                        url = canonical.get("url", item.get("link", ""))
                        
                        # Extract publish date
                        pub_date = content.get("pubDate", "")
                        if pub_date:
                            try:
                                from dateutil import parser as date_parser
                                published_at = date_parser.parse(pub_date).isoformat()
                            except:
                                published_at = now.isoformat()
                        else:
                            pub_time = item.get("providerPublishTime")
                            if pub_time:
                                published_at = datetime.fromtimestamp(pub_time, tz=pytz.UTC).isoformat()
                            else:
                                published_at = now.isoformat()
                        
                        if title:  # Only add if we have a title
                            all_news.append({
                                "title": title,
                                "source": publisher,
                                "publishedAt": published_at,
                                "url": url,
                                "topic": "market",
                                "symbols": [ticker_sym],
                                "sentiment": None
                            })
            except Exception as e:
                warnings.append(f"{ticker_sym}: {str(e)[:30]}")
        
        # Sort by published time descending and limit
        all_news.sort(key=lambda x: x["publishedAt"], reverse=True)
        result["items"] = all_news[:k]
        
        if not result["items"]:
            result["items"] = [{
                "title": "No recent news available",
                "source": "system",
                "publishedAt": now.isoformat(),
                "url": "",
                "topic": "notice",
                "symbols": [],
                "sentiment": None
            }]
            result["quality"]["confidenceLabel"] = "low"
        
        result["audit"]["sources"] = sources_used
        result["audit"]["warnings"] = warnings
        result["quality"]["missingPct"] = 0 if len(all_news) > 0 else 100
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# World Clock Endpoint
# ============================================================================

@router.get("/clock")
def get_monitor_clock():
    """
    GET /api/monitor/clock
    Returns market session status for India, US, and Europe.
    """
    try:
        now = datetime.now(pytz.UTC)
        
        # Timezone definitions
        tz_india = pytz.timezone("Asia/Kolkata")
        tz_us = pytz.timezone("America/New_York")
        tz_europe = pytz.timezone("Europe/London")
        
        # Market hours (local time)
        # India: 9:15 - 15:30
        # US: 9:30 - 16:00
        # Europe (LSE): 8:00 - 16:30
        
        sessions = []
        
        def get_session_status(tz, market_open, market_close, region, pre_hours=0.5, post_hours=0.5):
            local_now = now.astimezone(tz)
            local_time = local_now.time()
            weekday = local_now.weekday()
            
            # Weekend check
            if weekday >= 5:
                # Find next Monday
                days_until_monday = 7 - weekday
                next_open = (local_now + timedelta(days=days_until_monday)).replace(
                    hour=market_open.hour, minute=market_open.minute, second=0, microsecond=0
                )
                return {
                    "region": region,
                    "status": "closed",
                    "nextOpen": next_open.isoformat(),
                    "nextClose": None,
                    "countdownSec": int((next_open - local_now).total_seconds())
                }
            
            # Pre-market
            pre_open = (datetime.combine(local_now.date(), market_open) - timedelta(hours=pre_hours)).time()
            
            if pre_open <= local_time < market_open:
                open_dt = datetime.combine(local_now.date(), market_open)
                open_dt = tz.localize(open_dt)
                return {
                    "region": region,
                    "status": "pre",
                    "nextOpen": open_dt.isoformat(),
                    "nextClose": None,
                    "countdownSec": int((open_dt - local_now).total_seconds())
                }
            
            # Open
            if market_open <= local_time <= market_close:
                close_dt = datetime.combine(local_now.date(), market_close)
                close_dt = tz.localize(close_dt)
                return {
                    "region": region,
                    "status": "open",
                    "nextOpen": None,
                    "nextClose": close_dt.isoformat(),
                    "countdownSec": int((close_dt - local_now).total_seconds())
                }
            
            # After-hours
            post_close = (datetime.combine(local_now.date(), market_close) + timedelta(hours=post_hours)).time()
            if market_close < local_time <= post_close:
                # Next open is tomorrow (or Monday if Friday)
                if weekday == 4:
                    next_open = local_now + timedelta(days=3)
                else:
                    next_open = local_now + timedelta(days=1)
                next_open = next_open.replace(hour=market_open.hour, minute=market_open.minute, second=0, microsecond=0)
                return {
                    "region": region,
                    "status": "after",
                    "nextOpen": next_open.isoformat(),
                    "nextClose": None,
                    "countdownSec": int((next_open - local_now).total_seconds())
                }
            
            # Closed (before pre-market or after post-market)
            if local_time < pre_open:
                open_dt = datetime.combine(local_now.date(), market_open)
                open_dt = tz.localize(open_dt)
            else:
                if weekday == 4:
                    next_open = local_now + timedelta(days=3)
                else:
                    next_open = local_now + timedelta(days=1)
                open_dt = next_open.replace(hour=market_open.hour, minute=market_open.minute, second=0, microsecond=0)
            
            return {
                "region": region,
                "status": "closed",
                "nextOpen": open_dt.isoformat() if hasattr(open_dt, 'isoformat') else str(open_dt),
                "nextClose": None,
                "countdownSec": int((open_dt - local_now).total_seconds()) if hasattr(open_dt, '__sub__') else 0
            }
        
        # India
        sessions.append(get_session_status(
            tz_india, time(9, 15), time(15, 30), "India"
        ))
        
        # US
        sessions.append(get_session_status(
            tz_us, time(9, 30), time(16, 0), "US"
        ))
        
        # Europe (LSE)
        sessions.append(get_session_status(
            tz_europe, time(8, 0), time(16, 30), "Europe"
        ))
        
        return {
            "asOf": now.isoformat(),
            "sessions": sessions,
            "audit": {"warnings": []},
            "quality": {"missingPct": 0, "confidenceLabel": "high"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Equity Ticker Strip Endpoint (Animated)
# ============================================================================

@router.get("/equity_tickers")
def get_equity_tickers():
    """
    GET /api/monitor/equity_tickers
    Returns NIFTY, SENSEX, BANKNIFTY, FINNIFTY, SPY, QQQ, DIA, IWM
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        ticker_config = [
            {"symbol": "^NSEI", "display": "NIFTY"},
            {"symbol": "^BSESN", "display": "SENSEX"},
            {"symbol": "^NSEBANK", "display": "BANKNIFTY"},
            {"symbol": "NIFTYFIN.NS", "display": "FINNIFTY"},
            {"symbol": "SPY", "display": "SPY"},
            {"symbol": "QQQ", "display": "QQQ"},
            {"symbol": "DIA", "display": "DIA"},
            {"symbol": "IWM", "display": "IWM"},
        ]
        
        items = []
        missing = 0
        
        for cfg in ticker_config:
            try:
                ticker = yf.Ticker(cfg["symbol"])
                hist = ticker.history(period="2d")
                
                if len(hist) >= 2:
                    last = safe_float(hist['Close'].iloc[-1])
                    prev = safe_float(hist['Close'].iloc[-2])
                    changePct = ((last - prev) / prev * 100) if prev != 0 else 0
                    items.append({
                        "symbol": cfg["display"],
                        "last": round(last, 2),
                        "changePct": round(changePct, 2)
                    })
                elif len(hist) == 1:
                    items.append({
                        "symbol": cfg["display"],
                        "last": round(safe_float(hist['Close'].iloc[-1]), 2),
                        "changePct": 0
                    })
                else:
                    missing += 1
            except Exception as e:
                missing += 1
                warnings.append(f"{cfg['display']}: {str(e)[:30]}")
        
        return {
            "asOf": now.isoformat(),
            "items": items,
            "audit": {"warnings": warnings},
            "quality": {"missingPct": round(missing / len(ticker_config) * 100, 1), "confidenceLabel": "high" if missing < 2 else "medium"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Macro Pressure Strip Endpoint (Animated)
# ============================================================================

@router.get("/macro_tickers")
def get_macro_tickers():
    """
    GET /api/monitor/macro_tickers
    Returns DXY, US10Y, VIX, GOLD, BRENT, USDINR
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        ticker_config = [
            {"symbol": "DX-Y.NYB", "display": "DXY"},
            {"symbol": "^TNX", "display": "US10Y"},
            {"symbol": "^VIX", "display": "VIX"},
            {"symbol": "GC=F", "display": "GOLD"},
            {"symbol": "BZ=F", "display": "BRENT"},
            {"symbol": "USDINR=X", "display": "USDINR"},
        ]
        
        items = []
        missing = 0
        
        for cfg in ticker_config:
            try:
                ticker = yf.Ticker(cfg["symbol"])
                hist = ticker.history(period="2d")
                
                if len(hist) >= 2:
                    last = safe_float(hist['Close'].iloc[-1])
                    prev = safe_float(hist['Close'].iloc[-2])
                    changePct = ((last - prev) / prev * 100) if prev != 0 else 0
                    items.append({
                        "symbol": cfg["display"],
                        "last": round(last, 2 if cfg["display"] not in ["USDINR"] else 4),
                        "changePct": round(changePct, 2)
                    })
                elif len(hist) == 1:
                    items.append({
                        "symbol": cfg["display"],
                        "last": round(safe_float(hist['Close'].iloc[-1]), 2),
                        "changePct": 0
                    })
                else:
                    missing += 1
            except Exception as e:
                missing += 1
                warnings.append(f"{cfg['display']}: {str(e)[:30]}")
        
        return {
            "asOf": now.isoformat(),
            "items": items,
            "audit": {"warnings": warnings},
            "quality": {"missingPct": round(missing / len(ticker_config) * 100, 1), "confidenceLabel": "high" if missing < 2 else "medium"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NIFTY 50 Heatmap Endpoint
# ============================================================================

@router.get("/nifty50_heatmap")
def get_nifty50_heatmap():
    """
    GET /api/monitor/nifty50_heatmap
    Returns NIFTY 50 stocks with weight, last price, change percent, volume
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # NIFTY 50 top constituents with approximate weights
        nifty50_stocks = [
            {"symbol": "RELIANCE.NS", "weight": 10.5},
            {"symbol": "HDFCBANK.NS", "weight": 8.2},
            {"symbol": "ICICIBANK.NS", "weight": 7.1},
            {"symbol": "INFY.NS", "weight": 6.8},
            {"symbol": "TCS.NS", "weight": 4.5},
            {"symbol": "BHARTIARTL.NS", "weight": 4.2},
            {"symbol": "ITC.NS", "weight": 3.9},
            {"symbol": "SBIN.NS", "weight": 3.5},
            {"symbol": "KOTAKBANK.NS", "weight": 3.2},
            {"symbol": "LT.NS", "weight": 3.0},
            {"symbol": "AXISBANK.NS", "weight": 2.8},
            {"symbol": "HINDUNILVR.NS", "weight": 2.6},
            {"symbol": "BAJFINANCE.NS", "weight": 2.5},
            {"symbol": "MARUTI.NS", "weight": 2.3},
            {"symbol": "HCLTECH.NS", "weight": 2.2},
            {"symbol": "SUNPHARMA.NS", "weight": 2.1},
            {"symbol": "TITAN.NS", "weight": 2.0},
            {"symbol": "TATAMOTORS.NS", "weight": 1.9},
            {"symbol": "NTPC.NS", "weight": 1.8},
            {"symbol": "ONGC.NS", "weight": 1.7},
            {"symbol": "POWERGRID.NS", "weight": 1.6},
            {"symbol": "M&M.NS", "weight": 1.5},
            {"symbol": "ULTRACEMCO.NS", "weight": 1.4},
            {"symbol": "TATASTEEL.NS", "weight": 1.3},
            {"symbol": "ADANIENT.NS", "weight": 1.3},
            {"symbol": "TECHM.NS", "weight": 1.2},
            {"symbol": "WIPRO.NS", "weight": 1.1},
            {"symbol": "JSWSTEEL.NS", "weight": 1.1},
            {"symbol": "COALINDIA.NS", "weight": 1.0},
            {"symbol": "BAJAJFINSV.NS", "weight": 1.0},
            {"symbol": "DRREDDY.NS", "weight": 0.9},
            {"symbol": "CIPLA.NS", "weight": 0.9},
            {"symbol": "GRASIM.NS", "weight": 0.9},
            {"symbol": "HINDALCO.NS", "weight": 0.8},
            {"symbol": "EICHERMOT.NS", "weight": 0.8},
            {"symbol": "APOLLOHOSP.NS", "weight": 0.8},
            {"symbol": "DIVISLAB.NS", "weight": 0.7},
            {"symbol": "BPCL.NS", "weight": 0.7},
            {"symbol": "TATACONSUM.NS", "weight": 0.7},
            {"symbol": "BRITANNIA.NS", "weight": 0.6},
            {"symbol": "NESTLEIND.NS", "weight": 0.6},
            {"symbol": "HEROMOTOCO.NS", "weight": 0.5},
            {"symbol": "SHRIRAMFIN.NS", "weight": 0.5},
            {"symbol": "SBILIFE.NS", "weight": 0.5},
            {"symbol": "HDFCLIFE.NS", "weight": 0.5},
            {"symbol": "INDUSINDBK.NS", "weight": 0.4},
            {"symbol": "BAJAJ-AUTO.NS", "weight": 0.4},
            {"symbol": "TRENT.NS", "weight": 0.4},
            {"symbol": "VEDL.NS", "weight": 0.3},
            {"symbol": "ADANIPORTS.NS", "weight": 0.3},
        ]
        
        symbols = [s["symbol"] for s in nifty50_stocks]
        weight_map = {s["symbol"]: s["weight"] for s in nifty50_stocks}
        
        try:
            # Fetch data in batch
            data = yf.download(" ".join(symbols[:30]), period="2d", progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "stocks": [],
                    "audit": {"warnings": ["No data returned"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
                volumes = data['Volume']
            else:
                closes = data[['Close']] if 'Close' in data.columns else data
                volumes = data[['Volume']] if 'Volume' in data.columns else pd.DataFrame()
            
            stocks = []
            for col in closes.columns:
                series = closes[col].dropna()
                if len(series) >= 2:
                    last = series.iloc[-1]
                    prev = series.iloc[-2]
                    changePct = ((last - prev) / prev) * 100 if prev != 0 else 0
                    vol = volumes[col].iloc[-1] if col in volumes.columns else 0
                    
                    symbol_key = col if col in weight_map else f"{col}.NS"
                    stocks.append({
                        "symbol": col,
                        "last": round(last, 2),
                        "changePct": round(changePct, 2),
                        "volume": int(vol) if not pd.isna(vol) else 0,
                        "weight": weight_map.get(symbol_key, 0.5)
                    })
            
            return {
                "asOf": now.isoformat(),
                "stocks": stocks,
                "audit": {"warnings": warnings},
                "quality": {"missingPct": round((len(nifty50_stocks) - len(stocks)) / len(nifty50_stocks) * 100, 1), "confidenceLabel": "high" if len(stocks) > 20 else "medium"}
            }
        except Exception as e:
            logger.error(f"Error fetching heatmap: {e}")
            return {
                "asOf": now.isoformat(),
                "stocks": [],
                "audit": {"warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Breadth Charts Data Endpoints
# ============================================================================

@router.get("/adl")
def get_advance_decline_line(days: int = Query(90, description="Number of days")):
    """
    GET /api/monitor/adl
    Returns Advance/Decline Line data
    ADL = cumulative sum of (advances - declines)
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Use India NSE universe
        symbols = universe.get_universe_list("india_nse")[:100]
        
        if not symbols:
            return {
                "asOf": now.isoformat(),
                "dates": [],
                "adl": [],
                "audit": {"warnings": ["No symbols in universe"]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch historical data
            period = f"{days}d" if days <= 60 else f"{days // 30}mo"
            data = yf.download(" ".join(symbols[:50]), period=period, progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "dates": [],
                    "adl": [],
                    "audit": {"warnings": ["No data"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data
            
            # Calculate daily returns
            returns = closes.pct_change()
            
            # Count advances and declines per day
            eps = 0.0005
            advances = (returns > eps).sum(axis=1)
            declines = (returns < -eps).sum(axis=1)
            net = advances - declines
            adl = net.cumsum()
            
            # Clean data
            adl = adl.dropna()
            
            return {
                "asOf": now.isoformat(),
                "dates": adl.index.strftime('%Y-%m-%d').tolist(),
                "adl": adl.tolist(),
                "audit": {"universe": "india_nse", "count": len(symbols), "warnings": warnings},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            logger.error(f"Error computing ADL: {e}")
            return {
                "asOf": now.isoformat(),
                "dates": [],
                "adl": [],
                "audit": {"warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volatility_regime")
def get_volatility_regime(days: int = Query(90, description="Number of days")):
    """
    GET /api/monitor/volatility_regime
    Returns rolling 20-day annualized volatility for NIFTY and BANKNIFTY
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        try:
            # Fetch NIFTY and BANKNIFTY data
            period = f"{days + 30}d" if days <= 60 else f"{(days + 30) // 30}mo"
            
            nifty = yf.Ticker("^NSEI")
            banknifty = yf.Ticker("^NSEBANK")
            
            nifty_hist = nifty.history(period=period)
            banknifty_hist = banknifty.history(period=period)
            
            if len(nifty_hist) < 30:
                return {
                    "asOf": now.isoformat(),
                    "dates": [],
                    "niftyVol": [],
                    "bankniftyVol": [],
                    "audit": {"warnings": ["Insufficient data"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            # Calculate rolling volatility
            window = 20
            
            nifty_returns = np.log(nifty_hist['Close'] / nifty_hist['Close'].shift(1))
            nifty_vol = nifty_returns.rolling(window=window).std() * np.sqrt(252) * 100
            
            banknifty_returns = np.log(banknifty_hist['Close'] / banknifty_hist['Close'].shift(1))
            banknifty_vol = banknifty_returns.rolling(window=window).std() * np.sqrt(252) * 100
            
            # Align and clean
            nifty_vol = nifty_vol.dropna().tail(days)
            banknifty_vol = banknifty_vol.dropna().tail(days)
            
            return {
                "asOf": now.isoformat(),
                "dates": nifty_vol.index.strftime('%Y-%m-%d').tolist(),
                "niftyVol": [round(v, 1) for v in nifty_vol.tolist()],
                "bankniftyVol": [round(v, 1) for v in banknifty_vol.tolist()[:len(nifty_vol)]],
                "audit": {"window": window, "warnings": warnings},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            logger.error(f"Error computing volatility regime: {e}")
            return {
                "asOf": now.isoformat(),
                "dates": [],
                "niftyVol": [],
                "bankniftyVol": [],
                "audit": {"warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ad_thrust")
def get_ad_ratio_thrust(days: int = Query(90, description="Number of days")):
    """
    GET /api/monitor/ad_thrust
    Returns Advance/Decline Ratio Thrust (EMA10 of advance ratio)
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Use India NSE universe
        symbols = universe.get_universe_list("india_nse")[:100]
        
        if not symbols:
            return {
                "asOf": now.isoformat(),
                "dates": [],
                "thrust": [],
                "audit": {"warnings": ["No symbols"]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch historical data
            period = f"{days + 15}d" if days <= 60 else f"{(days + 15) // 30}mo"
            data = yf.download(" ".join(symbols[:50]), period=period, progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "dates": [],
                    "thrust": [],
                    "audit": {"warnings": ["No data"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data
            
            # Calculate daily returns
            returns = closes.pct_change()
            
            # Count advances per day
            eps = 0.0005
            advances = (returns > eps).sum(axis=1)
            total = returns.notna().sum(axis=1)
            total = total.replace(0, 1)  # Avoid division by zero
            
            # Advance ratio
            ratio = advances / total
            
            # EMA(10) of ratio
            thrust = ratio.ewm(span=10).mean()
            thrust = thrust.dropna().tail(days)
            
            return {
                "asOf": now.isoformat(),
                "dates": thrust.index.strftime('%Y-%m-%d').tolist(),
                "thrust": [round(v, 3) for v in thrust.tolist()],
                "audit": {"universe": "india_nse", "ema_window": 10, "warnings": warnings},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            logger.error(f"Error computing A/D thrust: {e}")
            return {
                "asOf": now.isoformat(),
                "dates": [],
                "thrust": [],
                "audit": {"warnings": [str(e)]},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

