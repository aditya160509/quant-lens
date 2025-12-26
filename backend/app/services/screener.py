"""
Screener Service - Core logic for Labs Screener

Liquidity Thresholds (Average Daily Dollar Volume):
- HIGH: > $50M
- MEDIUM: $10M - $50M
- LOW: $2M - $10M
- ILLIQUID: < $2M

Volatility Buckets (20-day annualized):
- LOW: < 15%
- MEDIUM: 15% - 35%
- HIGH: > 35%
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from app import data_loader

logger = logging.getLogger(__name__)

# Default universe of tickers
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC", "WMT",
    "PG", "JNJ", "XOM", "CVX", "UNH", "HD", "MA", "V", "DIS", "NFLX",
    "ADBE", "CRM", "PYPL", "INTC", "AMD", "QCOM", "COST", "PEP", "KO", "MCD",
    "NKE", "SBUX", "TGT", "LOW", "GS", "MS", "C", "AXP", "BLK", "SCHW"
]

# Sector mapping
SECTOR_MAP = {
    "AAPL": ("Technology", "Consumer Electronics"),
    "MSFT": ("Technology", "Software"),
    "GOOGL": ("Technology", "Internet Services"),
    "AMZN": ("Consumer Discretionary", "E-Commerce"),
    "NVDA": ("Technology", "Semiconductors"),
    "TSLA": ("Consumer Discretionary", "Auto Manufacturers"),
    "META": ("Technology", "Internet Services"),
    "JPM": ("Financials", "Banks"),
    "BAC": ("Financials", "Banks"),
    "WMT": ("Consumer Staples", "Retail"),
    "PG": ("Consumer Staples", "Household Products"),
    "JNJ": ("Healthcare", "Pharmaceuticals"),
    "XOM": ("Energy", "Oil & Gas"),
    "CVX": ("Energy", "Oil & Gas"),
    "UNH": ("Healthcare", "Health Insurance"),
    "HD": ("Consumer Discretionary", "Home Improvement"),
    "MA": ("Financials", "Credit Services"),
    "V": ("Financials", "Credit Services"),
    "DIS": ("Communication Services", "Entertainment"),
    "NFLX": ("Communication Services", "Streaming"),
    "ADBE": ("Technology", "Software"),
    "CRM": ("Technology", "Software"),
    "PYPL": ("Financials", "Fintech"),
    "INTC": ("Technology", "Semiconductors"),
    "AMD": ("Technology", "Semiconductors"),
    "QCOM": ("Technology", "Semiconductors"),
    "COST": ("Consumer Staples", "Warehouse Clubs"),
    "PEP": ("Consumer Staples", "Beverages"),
    "KO": ("Consumer Staples", "Beverages"),
    "MCD": ("Consumer Discretionary", "Restaurants"),
    "NKE": ("Consumer Discretionary", "Apparel"),
    "SBUX": ("Consumer Discretionary", "Restaurants"),
    "TGT": ("Consumer Discretionary", "Retail"),
    "LOW": ("Consumer Discretionary", "Home Improvement"),
    "GS": ("Financials", "Investment Banking"),
    "MS": ("Financials", "Investment Banking"),
    "C": ("Financials", "Banks"),
    "AXP": ("Financials", "Credit Services"),
    "BLK": ("Financials", "Asset Management"),
    "SCHW": ("Financials", "Brokerage"),
}

def classify_liquidity(avg_dollar_volume: float) -> str:
    """Classify liquidity based on average daily dollar volume."""
    if avg_dollar_volume is None or np.isnan(avg_dollar_volume):
        return "UNKNOWN"
    if avg_dollar_volume > 50_000_000:
        return "HIGH"
    elif avg_dollar_volume > 10_000_000:
        return "MEDIUM"
    elif avg_dollar_volume > 2_000_000:
        return "LOW"
    else:
        return "ILLIQUID"

def classify_volatility(vol_20d: float) -> str:
    """Classify volatility bucket based on 20-day annualized vol."""
    if vol_20d is None or np.isnan(vol_20d):
        return "UNKNOWN"
    if vol_20d < 0.15:
        return "LOW"
    elif vol_20d < 0.35:
        return "MEDIUM"
    else:
        return "HIGH"

def compute_rsi(prices: pd.Series, period: int = 14) -> float:
    """Compute RSI for latest bar."""
    if len(prices) < period + 1:
        return 50.0  # neutral
    
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

def safe_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely convert value to float, handling NaN/Inf."""
    if val is None:
        return default
    try:
        f_val = float(val)
        if np.isnan(f_val) or np.isinf(f_val):
            return default
        return f_val
    except (ValueError, TypeError):
        return default

def get_screener_data(
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    liquidity: Optional[str] = None,
    vol_bucket: Optional[str] = None,
    marketcap_min: Optional[float] = None,
    marketcap_max: Optional[float] = None,
    sort_by: str = "change_pct",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Main screener function.
    Returns filtered, sorted, paginated results.
    """
    results = []
    
    # Fetch data for all tickers in universe
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 1 year for momentum calc
    
    for symbol in DEFAULT_UNIVERSE:
        try:
            df = data_loader.fetch_ticker_data(symbol, period="1y")
            
            if df is None or df.empty or len(df) < 30:
                continue
            
            # Basic price data
            if 'Close' not in df.columns:
                continue
                
            closes = df['Close']
            volumes = df['Volume'] if 'Volume' in df.columns else pd.Series([0] * len(df))
            
            last_price = float(closes.iloc[-1])
            prev_close = float(closes.iloc[-2]) if len(closes) > 1 else last_price
            change_pct = (last_price / prev_close) - 1 if prev_close != 0 else 0
            
            last_volume = int(volumes.iloc[-1]) if len(volumes) > 0 else 0
            
            # Average daily dollar volume (20d)
            avg_volume_20d = volumes.tail(20).mean() if len(volumes) >= 20 else volumes.mean()
            avg_dollar_volume = avg_volume_20d * closes.tail(20).mean()
            
            # Market cap (approximate using shares if available, else None)
            # For now, use a rough estimate based on typical float
            marketcap = None  # Would need shares outstanding data
            
            # Sector/Industry
            sector_info = SECTOR_MAP.get(symbol, ("Other", "Other"))
            sym_sector = sector_info[0]
            sym_industry = sector_info[1]
            
            # Liquidity classification
            liq_class = classify_liquidity(avg_dollar_volume)
            
            # Volatility
            log_rets = np.log(closes / closes.shift(1)).dropna()
            
            # Day-to-day volatility (absolute change)
            d1_vol = abs(change_pct) * 100
            
            # 20-day annualized volatility
            if len(log_rets) >= 20:
                d20_vol = float(log_rets.tail(20).std() * np.sqrt(252))
            else:
                d20_vol = float(log_rets.std() * np.sqrt(252)) if len(log_rets) > 0 else 0
            
            vol_class = classify_volatility(d20_vol)
            
            # Factor scores (z-scores, simplified)
            # Value: Use P/E ratio proxy (lower is better) - simplified as inverse of momentum
            # Momentum: 12-month minus 1-month return
            # Growth: Price appreciation rate
            
            if len(closes) >= 252:
                ret_12m = (closes.iloc[-1] / closes.iloc[-252]) - 1
            else:
                ret_12m = (closes.iloc[-1] / closes.iloc[0]) - 1
                
            if len(closes) >= 21:
                ret_1m = (closes.iloc[-1] / closes.iloc[-21]) - 1
            else:
                ret_1m = 0
                
            momentum_factor = ret_12m - ret_1m
            
            # Simplified z-score conversion (will be normalized across universe later)
            value_factor = -momentum_factor  # Placeholder: value as inverse of momentum
            growth_factor = ret_12m
            
            # Sparkline (last 20 closes)
            sparkline = closes.tail(20).tolist()
            
            # Signals
            rsi = compute_rsi(closes)
            avg_vol_20d = volumes.tail(20).mean()
            volume_spike = bool(last_volume > (avg_vol_20d * 2.0)) if avg_vol_20d > 0 else False
            momentum_high = bool(momentum_factor > 0.1)  # Top momentum if > 10%
            oversold_rsi = bool(rsi < 30)
            earnings_soon = False  # Would need earnings calendar integration
            
            results.append({
                "symbol": symbol,
                "name": symbol,  # Would need name lookup
                "price": safe_float(last_price),
                "change_pct": safe_float(change_pct, 0.0),
                "volume": int(last_volume),
                "marketcap": marketcap,
                "sector": sym_sector,
                "industry": sym_industry,
                "liquidity": liq_class,
                "volatility": {
                    "d1": safe_float(d1_vol),
                    "d20": safe_float(d20_vol * 100)
                },
                "factors": {
                    "value": safe_float(value_factor),
                    "momentum": safe_float(momentum_factor),
                    "growth": safe_float(growth_factor)
                },
                "sparkline": [safe_float(p) for p in sparkline[-10:]],
                "signals": {
                    "momentum_high": momentum_high,
                    "oversold_rsi": oversold_rsi,
                    "volume_spike": volume_spike,
                    "earnings_soon": earnings_soon
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue
    
    # Apply filters
    filtered = results
    
    if sector:
        filtered = [r for r in filtered if r["sector"].lower() == sector.lower()]
    
    if industry:
        filtered = [r for r in filtered if industry.lower() in r["industry"].lower()]
    
    if liquidity:
        filtered = [r for r in filtered if r["liquidity"] == liquidity.upper()]
    
    if vol_bucket:
        filtered = [r for r in filtered if classify_volatility(r["volatility"]["d20"] / 100) == vol_bucket.upper()]
    
    if marketcap_min is not None:
        filtered = [r for r in filtered if r["marketcap"] is not None and r["marketcap"] >= marketcap_min]
    
    if marketcap_max is not None:
        filtered = [r for r in filtered if r["marketcap"] is not None and r["marketcap"] <= marketcap_max]
    
    # Sort
    sort_key_map = {
        "price": lambda x: x["price"] or 0,
        "change_pct": lambda x: x["change_pct"] or 0,
        "volume": lambda x: x["volume"] or 0,
        "marketcap": lambda x: x["marketcap"] or 0,
        "vol_20d": lambda x: x["volatility"]["d20"] or 0,
        "momentum_score": lambda x: x["factors"]["momentum"] or 0,
    }
    
    sort_fn = sort_key_map.get(sort_by, sort_key_map["change_pct"])
    reverse = sort_dir.lower() == "desc"
    
    filtered.sort(key=sort_fn, reverse=reverse)
    
    total = len(filtered)
    
    # Paginate
    paginated = filtered[offset:offset + limit]
    
    return {
        "total": total,
        "results": paginated
    }
