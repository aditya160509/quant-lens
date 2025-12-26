"""
Markets Daily API Router - Post-Close Cognition Screen
Rebuilt per Master Spec with 7 endpoints, cache layer, and full audit trails.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import pytz
import numpy as np
import pandas as pd
import logging
import hashlib
import json
from functools import lru_cache

import yfinance as yf
from app.services import universe

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# SECTOR MAPPING
# Derived from NIFTY sector indices - hard-coded since no mapping file exists
# ============================================================================

SECTOR_MAPPING = {
    "Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "FEDERALBNK.NS", "CANBK.NS"],
    "IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "KPITTECH.NS"],
    "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS", "AUROPHARMA.NS", "TORNTPHARM.NS", "ALKEM.NS", "BIOCON.NS", "GLENMARK.NS"],
    "Auto": ["TATAMOTORS.NS", "MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "BHARATFORG.NS", "ESCORTS.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "TATACONSUM.NS", "VBL.NS", "EMAMILTD.NS"],
    "Metal": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS", "JINDALSTEL.NS", "SAIL.NS", "NMDC.NS", "NATIONALUM.NS", "MOIL.NS"],
    "Realty": ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "LODHA.NS", "BRIGADE.NS", "SOBHA.NS", "MAHLIFE.NS", "SUNTECK.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "PETRONET.NS"],
}

SECTOR_INDEX_MAP = {
    "Bank": "^NSEBANK",
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "Auto": "^CNXAUTO",
    "FMCG": "^CNXFMCG",
    "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY",
}

# ============================================================================
# NEWS RSS SOURCES
# ============================================================================

RSS_SOURCES = [
    {"name": "Moneycontrol", "url": "https://www.moneycontrol.com/rss/latestnews.xml", "defaultCategory": "Market"},
    {"name": "Economic Times Markets", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "defaultCategory": "Market"},
    {"name": "Economic Times Stocks", "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "defaultCategory": "Stocks"},
    {"name": "Livemint", "url": "https://www.livemint.com/rss/markets", "defaultCategory": "Market"},
]

# ============================================================================
# CACHE LAYER - In-memory with TTL
# ============================================================================

_MARKET_CACHE: Dict[str, Dict] = {}

def get_cache_key(prefix: str, params: Dict) -> str:
    """Generate cache key from prefix and params."""
    params_str = json.dumps(params, sort_keys=True)
    return f"{prefix}:{hashlib.md5(params_str.encode()).hexdigest()[:12]}"

def get_from_cache(key: str, ttl_sec: int = 300) -> Optional[Dict]:
    """Get from cache if not stale."""
    if key in _MARKET_CACHE:
        entry = _MARKET_CACHE[key]
        age = (datetime.now(pytz.UTC) - entry["retrievedAt"]).total_seconds()
        if age < ttl_sec:
            return {"payload": entry["payload"], "cacheHit": True, "stalenessSec": age}
    return None

def set_cache(key: str, payload: Any, source: str):
    """Store in cache."""
    _MARKET_CACHE[key] = {
        "key": key,
        "payload": payload,
        "retrievedAt": datetime.now(pytz.UTC),
        "source": source,
    }

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_float(val, default=None) -> Optional[float]:
    """Safely convert to float."""
    if val is None or pd.isna(val) or np.isinf(val):
        return default
    return float(val)

def safe_int(val, default=None) -> Optional[int]:
    """Safely convert to int."""
    if val is None or pd.isna(val):
        return default
    return int(val)

def compute_pct_change(current, previous) -> Optional[float]:
    """Compute percentage change safely."""
    if previous is None or previous == 0 or pd.isna(previous) or pd.isna(current):
        return None
    return ((current - previous) / abs(previous)) * 100

def get_quality_label(missing_pct: float) -> str:
    """Get quality label based on missing percentage."""
    if missing_pct < 10:
        return "high"
    elif missing_pct < 30:
        return "medium"
    return "low"

def fetch_ohlcv(symbols: List[str], period: str = "3mo") -> pd.DataFrame:
    """Fetch OHLCV data for symbols with caching."""
    cache_key = get_cache_key("ohlcv", {"symbols": sorted(symbols)[:10], "period": period})
    cached = get_from_cache(cache_key, ttl_sec=300)
    if cached:
        return cached["payload"]
    
    try:
        data = yf.download(" ".join(symbols), period=period, progress=False, threads=True)
        set_cache(cache_key, data, "yfinance")
        return data
    except Exception as e:
        logger.error(f"OHLCV fetch error: {e}")
        return pd.DataFrame()

# ============================================================================
# ENDPOINT 1: Market Matrix
# GET /api/markets_daily/matrix
# ============================================================================

@router.get("/matrix")
def get_market_matrix():
    """
    Market Matrix with India heavy, US light universe.
    Returns: Last, Day%, 5D%, MTD%, Vol%ile, ATR%
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        sources = ["yfinance"]
        cache_hit = False
        
        # Build universe from repo
        india_stocks = universe.get_universe_list("india_nse")[:50]  # NIFTY 50
        india_indices = ["^NSEI", "^NSEBANK"]
        sector_indices = ["^CNXIT", "^CNXPHARMA", "^CNXAUTO", "^CNXFMCG"]
        us_tickers = ["SPY", "QQQ", "DIA"]
        macro_tickers = ["^VIX", "DX-Y.NYB", "USDINR=X"]
        
        # Combine all
        all_symbols = india_indices + sector_indices + india_stocks[:30] + us_tickers + macro_tickers
        
        items = []
        
        try:
            data = yf.download(" ".join(all_symbols), period="3mo", progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "items": [],
                    "audit": {"sources": sources, "cacheHit": False, "stalenessSec": 0, "warnings": ["No data returned"]},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            # Handle MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
                volumes = data['Volume']
                highs = data['High']
                lows = data['Low']
            else:
                closes = data[['Close']]
                volumes = data.get('Volume', pd.DataFrame())
                highs = data.get('High', pd.DataFrame())
                lows = data.get('Low', pd.DataFrame())
            
            for sym in all_symbols:
                try:
                    if sym not in closes.columns:
                        warnings.append(f"{sym}: not in data")
                        continue
                    
                    c = closes[sym].dropna()
                    if len(c) < 2:
                        warnings.append(f"{sym}: insufficient data")
                        continue
                    
                    last = c.iloc[-1]
                    
                    # Day %
                    day_pct = compute_pct_change(c.iloc[-1], c.iloc[-2])
                    
                    # 5D %
                    d5_pct = compute_pct_change(c.iloc[-1], c.iloc[-6]) if len(c) >= 6 else None
                    
                    # MTD %
                    month_start = now.replace(day=1).date()
                    mtd_data = c[c.index.date >= month_start]
                    mtd_pct = compute_pct_change(c.iloc[-1], mtd_data.iloc[0]) if len(mtd_data) > 0 else None
                    
                    # Volume percentile
                    vol_pctile = None
                    if sym in volumes.columns:
                        v = volumes[sym].dropna()
                        if len(v) >= 20:
                            today_vol = v.iloc[-1]
                            rolling_mean = v.rolling(5).mean().dropna()
                            if len(rolling_mean) > 0 and today_vol > 0:
                                vol_pctile = safe_float((rolling_mean < today_vol).mean() * 100)
                    
                    # ATR %
                    atr_pct = None
                    if sym in highs.columns and sym in lows.columns:
                        h = highs[sym].dropna()
                        l = lows[sym].dropna()
                        if len(h) >= 14 and len(l) >= 14 and len(c) >= 14:
                            tr = pd.concat([
                                h.tail(14) - l.tail(14),
                                abs(h.tail(14) - c.shift(1).tail(14)),
                                abs(l.tail(14) - c.shift(1).tail(14))
                            ], axis=1).max(axis=1)
                            atr = tr.mean()
                            atr_pct = safe_float((atr / last) * 100 if last > 0 else None)
                    
                    # Determine group
                    if sym in india_indices:
                        group = "India Index"
                    elif sym in sector_indices:
                        group = "India Sector"
                    elif sym.endswith(".NS"):
                        group = "India"
                    elif sym in us_tickers:
                        group = "US"
                    else:
                        group = "Macro"
                    
                    # Currency
                    currency = "INR" if group in ["India", "India Index", "India Sector"] else "USD"
                    
                    items.append({
                        "name": sym.replace(".NS", "").replace("^", "").replace("=X", "").replace("-Y.NYB", ""),
                        "symbol": sym,
                        "group": group,
                        "last": safe_float(last),
                        "dayPct": safe_float(day_pct),
                        "d5Pct": safe_float(d5_pct),
                        "mtdPct": safe_float(mtd_pct),
                        "volPctile": safe_int(vol_pctile),
                        "atrPct": safe_float(atr_pct, default=None),
                        "currency": currency,
                        "updatedAt": now.isoformat()
                    })
                except Exception as e:
                    warnings.append(f"{sym}: {str(e)[:30]}")
        
        except Exception as e:
            warnings.append(f"Download error: {str(e)[:50]}")
        
        # Sort: India Index > India Sector > India > US > Macro
        group_order = {"India Index": 0, "India Sector": 1, "India": 2, "US": 3, "Macro": 4}
        items.sort(key=lambda x: (group_order.get(x["group"], 5), -(x["dayPct"] or 0)))
        
        missing_pct = (len(all_symbols) - len(items)) / len(all_symbols) * 100 if all_symbols else 0
        
        return {
            "asOf": now.isoformat(),
            "items": items,
            "audit": {"sources": sources, "cacheHit": cache_hit, "stalenessSec": 0, "warnings": warnings[:10]},
            "quality": {"missingPct": round(missing_pct, 1), "confidenceLabel": get_quality_label(missing_pct)}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT 2: Sector Dispersion
# GET /api/markets_daily/sector_dispersion
# ============================================================================

@router.get("/sector_dispersion")
def get_sector_dispersion():
    """
    Sector dispersion with direction and outlier flags.
    Dispersion = std(dayPct) across sector constituents.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        items = []
        all_dispersions = []
        
        for sector, stocks in SECTOR_MAPPING.items():
            try:
                # Fetch 60 days for historical comparison
                data = yf.download(" ".join(stocks[:8]), period="60d", progress=False, threads=True)
                
                if data.empty:
                    warnings.append(f"{sector}: no data")
                    continue
                
                if isinstance(data.columns, pd.MultiIndex):
                    closes = data['Close']
                else:
                    closes = data
                
                # Compute day returns for each stock
                returns = closes.pct_change().iloc[-1] * 100
                valid_returns = returns.dropna()
                
                if len(valid_returns) < 3:
                    warnings.append(f"{sector}: insufficient stocks")
                    continue
                
                # Today's dispersion
                dispersion = valid_returns.std()
                mean_return = valid_returns.mean()
                
                # Direction: compare to 5-day rolling mean of dispersion
                daily_disps = []
                for i in range(-5, 0):
                    if i >= -len(closes):
                        day_returns = (closes.iloc[i] / closes.iloc[i-1] - 1) * 100
                        daily_disps.append(day_returns.std())
                
                mean_5d_disp = np.mean(daily_disps) if daily_disps else dispersion
                eps = 0.05
                if dispersion > mean_5d_disp + eps:
                    direction = "up"
                elif dispersion < mean_5d_disp - eps:
                    direction = "down"
                else:
                    direction = "flat"
                
                all_dispersions.append(dispersion)
                
                items.append({
                    "sector": sector,
                    "dispersion": safe_float(dispersion),
                    "meanReturn": safe_float(mean_return),
                    "label": None,  # Will set after all computed
                    "direction": direction,
                    "outlier": False  # Will set after
                })
            except Exception as e:
                warnings.append(f"{sector}: {str(e)[:30]}")
        
        # Set labels based on percentiles
        if all_dispersions and items:
            p33 = np.percentile(all_dispersions, 33)
            p66 = np.percentile(all_dispersions, 66)
            p90 = np.percentile(all_dispersions, 90)
            
            for item in items:
                d = item["dispersion"] or 0
                if d < p33:
                    item["label"] = "low"
                elif d < p66:
                    item["label"] = "normal"
                else:
                    item["label"] = "high"
                
                item["outlier"] = bool(d >= p90)
        
        missing_pct = (len(SECTOR_MAPPING) - len(items)) / len(SECTOR_MAPPING) * 100 if SECTOR_MAPPING else 0
        
        return {
            "asOf": now.isoformat(),
            "items": items,
            "audit": {"inputs": list(SECTOR_MAPPING.keys()), "stalenessSec": 0, "warnings": warnings[:10]},
            "quality": {"missingPct": round(missing_pct, 1), "confidenceLabel": get_quality_label(missing_pct)}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BLOOMBERG-STYLE GRAPH 1: Index Structure (NIFTY Close vs 20-day VWAP)
# GET /api/markets_daily/graph_index_structure
# ============================================================================

@router.get("/graph_index_structure")
def get_graph_index_structure():
    """
    NIFTY Close vs 20-day VWAP vs Previous Close.
    Determines if index is trading with structural strength or weakness.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        symbol = "^NSEI"
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")
            
            if len(hist) < 21:
                return {
                    "asOf": now.isoformat(),
                    "symbol": symbol,
                    "series": [],
                    "audit": {"sources": ["yfinance"], "warnings": ["Insufficient data"], "stalenessSec": 0},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            closes = hist['Close']
            volumes = hist['Volume']
            
            # Compute 20-day rolling VWAP: Σ(close × volume) / Σ(volume)
            price_vol = closes * volumes
            vwap20 = price_vol.rolling(20).sum() / volumes.rolling(20).sum()
            
            series = []
            for i in range(20, len(closes)):
                prev_close = closes.iloc[i-1] if i > 0 else closes.iloc[i]
                close_val = closes.iloc[i]
                vwap_val = vwap20.iloc[i]
                
                # Color logic: above VWAP = strength (green), below = weakness (red)
                if close_val > vwap_val:
                    color = "green"
                elif close_val < vwap_val:
                    color = "red"
                else:
                    color = "gray"
                
                series.append({
                    "t": closes.index[i].isoformat(),
                    "close": safe_float(close_val),
                    "vwap20": safe_float(vwap_val),
                    "prevClose": safe_float(prev_close),
                    "color": color
                })
            
            return {
                "asOf": now.isoformat(),
                "symbol": symbol,
                "series": series,
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            warnings.append(str(e)[:50])
            return {
                "asOf": now.isoformat(),
                "symbol": symbol,
                "series": [],
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BLOOMBERG-STYLE GRAPH 2: Market Move Intensity (Participation Violence)
# GET /api/markets_daily/graph_move_intensity
# ============================================================================

@router.get("/graph_move_intensity")
def get_graph_move_intensity():
    """
    Measures how violently stocks moved, independent of direction.
    Intensity = Average(|dayReturn|) across NIFTY 50 stocks.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        stocks = universe.get_universe_list("india_nse")[:50]
        
        if not stocks:
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": 0},
                "series": [],
                "audit": {"sources": ["yfinance"], "warnings": ["No universe data"], "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch 60 days of data
            data = yf.download(" ".join(stocks), period="3mo", progress=False, threads=True)
            
            # Also get NIFTY for index direction
            nifty = yf.Ticker("^NSEI")
            nifty_hist = nifty.history(period="3mo")
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "universe": {"name": "india_nse", "count": len(stocks)},
                    "series": [],
                    "audit": {"sources": ["yfinance"], "warnings": ["No data returned"], "stalenessSec": 0},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
            else:
                closes = data
            
            # Calculate daily returns
            returns = closes.pct_change(fill_method=None)
            abs_returns = returns.abs()
            
            # Average absolute return per day
            daily_intensity = abs_returns.mean(axis=1) * 100  # as percentage
            
            # Compute historical median for color thresholds
            median_intensity = daily_intensity.median()
            
            # NIFTY daily returns for direction
            nifty_returns = nifty_hist['Close'].pct_change(fill_method=None) * 100
            
            series = []
            for i in range(1, len(daily_intensity)):
                date = daily_intensity.index[i]
                intensity = daily_intensity.iloc[i]
                
                if pd.isna(intensity):
                    continue
                
                # Get index return for this date
                idx_return = 0
                date_str = date.strftime('%Y-%m-%d')
                matching = nifty_returns.index.strftime('%Y-%m-%d') == date_str
                if matching.any():
                    idx_return = nifty_returns[matching].iloc[0] if not pd.isna(nifty_returns[matching].iloc[0]) else 0
                
                # Color logic per spec
                if intensity < median_intensity:
                    color = "gray"  # Below median = calm
                elif idx_return > 0:
                    color = "green"  # High + index up = strong green
                else:
                    color = "red"  # High + index down = muted red
                
                series.append({
                    "t": date.isoformat(),
                    "intensity": safe_float(intensity),
                    "indexDayPct": safe_float(idx_return),
                    "medianIntensity": safe_float(median_intensity),
                    "color": color
                })
            
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": len(stocks)},
                "series": series[-60:],  # Last 60 sessions
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            warnings.append(str(e)[:50])
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": len(stocks)},
                "series": [],
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BLOOMBERG-STYLE GRAPH 3: Gap and Follow Through (Overnight Conviction)
# GET /api/markets_daily/graph_gap_followthrough
# ============================================================================

@router.get("/graph_gap_followthrough")
def get_graph_gap_followthrough():
    """
    Detects whether overnight information was respected or faded.
    Classifies each stock per day into: Positive Conviction, Negative Conviction, Fade, Reversal.
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        stocks = universe.get_universe_list("india_nse")[:50]
        
        if not stocks:
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": 0},
                "series": [],
                "audit": {"sources": ["yfinance"], "warnings": ["No universe data"], "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
        
        try:
            # Fetch OHLC data
            data = yf.download(" ".join(stocks), period="3mo", progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "universe": {"name": "india_nse", "count": len(stocks)},
                    "series": [],
                    "audit": {"sources": ["yfinance"], "warnings": ["No data returned"], "stalenessSec": 0},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                opens = data['Open']
                closes = data['Close']
            else:
                opens = data[['Open']]
                closes = data[['Close']]
            
            # Get unique dates
            dates = closes.index[1:]  # Skip first day (no previous close)
            
            series = []
            for i, date in enumerate(dates, start=1):
                positive_conviction = 0
                negative_conviction = 0
                fade = 0
                reversal = 0
                
                for col in closes.columns:
                    try:
                        prev_close = closes[col].iloc[i-1]
                        today_open = opens[col].iloc[i]
                        today_close = closes[col].iloc[i]
                        
                        if pd.isna(prev_close) or pd.isna(today_open) or pd.isna(today_close):
                            continue
                        if prev_close == 0 or today_open == 0:
                            continue
                        
                        # Gap = (Open - PrevClose) / PrevClose
                        gap = (today_open - prev_close) / prev_close
                        # Follow Through = (Close - Open) / Open
                        ft = (today_close - today_open) / today_open
                        
                        # Classification (using small threshold for gap direction)
                        gap_up = gap > 0.001
                        gap_down = gap < -0.001
                        ft_up = ft > 0
                        ft_down = ft < 0
                        
                        if gap_up and ft_up:
                            positive_conviction += 1
                        elif gap_up and ft_down:
                            fade += 1
                        elif gap_down and ft_down:
                            negative_conviction += 1
                        elif gap_down and ft_up:
                            reversal += 1
                        # Flat gap or flat ft goes to fade bucket
                        else:
                            fade += 1
                    except:
                        pass
                
                total = positive_conviction + negative_conviction + fade + reversal
                if total > 0:
                    series.append({
                        "t": date.isoformat(),
                        "positiveConviction": positive_conviction,
                        "negativeConviction": negative_conviction,
                        "fade": fade,
                        "reversal": reversal,
                        "total": total
                    })
            
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": len(stocks)},
                "series": series[-60:],  # Last 60 sessions
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            warnings.append(str(e)[:50])
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": len(stocks)},
                "series": [],
                "audit": {"sources": ["yfinance"], "warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT 5: Stock Move Map
# GET /api/markets_daily/stock_move_map
# ============================================================================

@router.get("/stock_move_map")
def get_stock_move_map(k: int = Query(30, description="Top K stocks")):
    """
    Ranked stock moves with micro bar values.
    rankScore = abs(dayPct) * 0.7 + (volPctile/100) * 0.3
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        stocks = universe.get_universe_list("india_nse")[:50]
        
        try:
            data = yf.download(" ".join(stocks), period="60d", progress=False, threads=True)
            
            if data.empty:
                return {
                    "asOf": now.isoformat(),
                    "universe": {"name": "india_nse", "count": 0},
                    "items": [],
                    "audit": {"warnings": ["No data"], "stalenessSec": 0},
                    "quality": {"missingPct": 100, "confidenceLabel": "low"}
                }
            
            if isinstance(data.columns, pd.MultiIndex):
                closes = data['Close']
                volumes = data['Volume']
            else:
                closes = data
                volumes = pd.DataFrame()
            
            items = []
            
            for col in closes.columns:
                try:
                    c = closes[col].dropna()
                    if len(c) < 2:
                        continue
                    
                    last = c.iloc[-1]
                    day_pct = (c.iloc[-1] / c.iloc[-2] - 1) * 100
                    
                    # Volume percentile
                    vol_pctile = 50
                    if col in volumes.columns:
                        v = volumes[col].dropna()
                        if len(v) >= 20:
                            today_vol = v.iloc[-1]
                            rolling_mean = v.rolling(5).mean().dropna()
                            if len(rolling_mean) > 0 and today_vol > 0:
                                vol_pctile = (rolling_mean < today_vol).mean() * 100
                    
                    # Get sector
                    sector = None
                    for s, syms in SECTOR_MAPPING.items():
                        if col in syms:
                            sector = s
                            break
                    
                    # Rank score
                    rank_score = abs(day_pct) * 0.7 + (vol_pctile / 100) * 0.3
                    
                    items.append({
                        "symbol": col.replace(".NS", ""),
                        "sector": sector,
                        "last": safe_float(last),
                        "dayPct": safe_float(day_pct),
                        "volPctile": safe_int(vol_pctile),
                        "rankScore": rank_score,
                        "barValue": 0  # Will normalize
                    })
                except:
                    pass
            
            # Sort by rank score and take top K
            items.sort(key=lambda x: x["rankScore"], reverse=True)
            items = items[:k]
            
            # Normalize bar values
            if items:
                max_abs = max(abs(x["dayPct"] or 0) for x in items) or 1
                for item in items:
                    item["barValue"] = abs(item["dayPct"] or 0) / max_abs
                    del item["rankScore"]  # Remove internal field
            
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": len(stocks)},
                "items": items,
                "audit": {"warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 0, "confidenceLabel": "high"}
            }
        except Exception as e:
            warnings.append(str(e)[:50])
            return {
                "asOf": now.isoformat(),
                "universe": {"name": "india_nse", "count": 0},
                "items": [],
                "audit": {"warnings": warnings, "stalenessSec": 0},
                "quality": {"missingPct": 100, "confidenceLabel": "low"}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT 6: Sector Relative Strength
# GET /api/markets_daily/sector_relative_strength
# ============================================================================

@router.get("/sector_relative_strength")
def get_sector_relative_strength():
    """
    Sector day returns vs NIFTY benchmark.
    rel = sectorDayPct - niftyDayPct
    """
    try:
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Get NIFTY benchmark
        nifty_day_pct = 0
        try:
            nifty = yf.Ticker("^NSEI")
            nifty_hist = nifty.history(period="2d")
            if len(nifty_hist) >= 2:
                nifty_day_pct = (nifty_hist['Close'].iloc[-1] / nifty_hist['Close'].iloc[-2] - 1) * 100
        except Exception as e:
            warnings.append(f"NIFTY: {str(e)[:30]}")
        
        items = []
        
        for sector, stocks in SECTOR_MAPPING.items():
            try:
                data = yf.download(" ".join(stocks[:8]), period="2d", progress=False, threads=True)
                
                if data.empty:
                    continue
                
                if isinstance(data.columns, pd.MultiIndex):
                    closes = data['Close']
                else:
                    closes = data
                
                # Equal-weighted sector return
                returns = []
                for col in closes.columns:
                    c = closes[col].dropna()
                    if len(c) >= 2:
                        ret = (c.iloc[-1] / c.iloc[-2] - 1) * 100
                        if not pd.isna(ret):
                            returns.append(ret)
                
                if returns:
                    sector_day_pct = np.mean(returns)
                    rel = sector_day_pct - nifty_day_pct
                    items.append({
                        "sector": sector,
                        "dayPct": safe_float(sector_day_pct),
                        "rel": safe_float(rel)
                    })
            except Exception as e:
                warnings.append(f"{sector}: {str(e)[:30]}")
        
        # Sort by rel desc
        items.sort(key=lambda x: x["rel"] or 0, reverse=True)
        
        return {
            "asOf": now.isoformat(),
            "benchmark": {"symbol": "^NSEI", "dayPct": safe_float(nifty_day_pct)},
            "items": items,
            "audit": {"inputs": list(SECTOR_MAPPING.keys()), "warnings": warnings, "stalenessSec": 0},
            "quality": {"missingPct": 0 if items else 100, "confidenceLabel": "high" if len(items) >= 5 else "medium"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT 7: News
# GET /api/markets_daily/news
# ============================================================================

@router.get("/news")
def get_news(category: str = Query("Market", description="Market, Stocks, IPO, Global"), k: int = Query(40, description="Max items")):
    """
    RSS-based news with categorization.
    """
    try:
        import feedparser
        now = datetime.now(pytz.UTC)
        warnings = []
        
        # Keyword routing
        CATEGORY_KEYWORDS = {
            "IPO": ["ipo", "gmp", "allotment", "listing", "subscription", "grey market"],
            "Stocks": ["results", "earnings", "shares", "stock", "jumps", "slips", "hits", "falls", "rises", "surges"],
            "Global": ["us", "wall street", "dow", "nasdaq", "s&p", "fed", "treasury", "cpi"],
        }
        
        def categorize_title(title: str, default_cat: str) -> tuple:
            title_lower = title.lower()
            matched_tags = []
            
            for cat, keywords in CATEGORY_KEYWORDS.items():
                for kw in keywords:
                    if kw in title_lower:
                        matched_tags.append(cat)
                        if cat == category:
                            return cat, list(set(matched_tags))
            
            return default_cat, list(set(matched_tags))
        
        def fingerprint(title: str) -> str:
            import re
            return re.sub(r'[^a-z0-9]', '', title.lower())
        
        all_items = []
        seen_fingerprints = set()
        
        for source in RSS_SOURCES:
            try:
                feed = feedparser.parse(source["url"])
                for entry in feed.entries[:20]:
                    try:
                        title = entry.get("title", "").strip()
                        if not title:
                            continue
                        
                        fp = fingerprint(title)
                        if fp in seen_fingerprints:
                            continue
                        seen_fingerprints.add(fp)
                        
                        # Parse date
                        pub = entry.get("published_parsed") or entry.get("updated_parsed")
                        if pub:
                            pub_dt = datetime(*pub[:6], tzinfo=pytz.UTC)
                        else:
                            pub_dt = now
                        
                        assigned_cat, tags = categorize_title(title, source["defaultCategory"])
                        
                        # Filter by category
                        if assigned_cat != category and category not in tags:
                            continue
                        
                        all_items.append({
                            "publishedAt": pub_dt.isoformat(),
                            "timeLabel": pub_dt.strftime("%H:%M"),
                            "title": title,
                            "source": source["name"],
                            "url": entry.get("link", ""),
                            "tags": tags if tags else [assigned_cat]
                        })
                    except:
                        pass
            except Exception as e:
                warnings.append(f"{source['name']}: {str(e)[:30]}")
        
        # Sort by publishedAt desc
        all_items.sort(key=lambda x: x["publishedAt"], reverse=True)
        all_items = all_items[:k]
        
        return {
            "asOf": now.isoformat(),
            "category": category,
            "items": all_items,
            "audit": {"sources": [s["name"] for s in RSS_SOURCES], "warnings": warnings, "stalenessSec": 0},
            "quality": {"missingPct": 0 if all_items else 100, "confidenceLabel": "high" if len(all_items) > 10 else "medium"}
        }
    except ImportError:
        return {
            "asOf": datetime.now(pytz.UTC).isoformat(),
            "category": category,
            "items": [],
            "audit": {"sources": [], "warnings": ["feedparser not installed"], "stalenessSec": 0},
            "quality": {"missingPct": 100, "confidenceLabel": "low"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
