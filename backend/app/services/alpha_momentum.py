"""
Alpha Model: Momentum Intelligence
Cross-sectional momentum scoring with trend phase classification

OPTIMIZATIONS:
- Thread-safe caching with TTL
- Input validation for security
- Memory-efficient data structures
- Graceful error handling
"""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import threading

# Use centralized data fetcher instead of direct yfinance
from app.services.robust_data_fetcher import get_price_data as rdf_get_price, validate_ticker

logger = logging.getLogger(__name__)

# Thread-safe cache with lock
_cache_lock = threading.RLock()
_price_cache: Dict[str, Dict] = {}
_cache_ttl_minutes = 30
_max_cache_entries = 500  # Limit memory usage


def _cleanup_cache():
    """Remove expired entries and enforce size limit"""
    with _cache_lock:
        now = datetime.now()
        expired = [
            k for k, v in _price_cache.items()
            if (now - v["timestamp"]).total_seconds() > _cache_ttl_minutes * 60
        ]
        for k in expired:
            del _price_cache[k]
        
        # LRU eviction if over limit
        if len(_price_cache) > _max_cache_entries:
            sorted_keys = sorted(
                _price_cache.keys(),
                key=lambda k: _price_cache[k]["timestamp"]
            )
            for k in sorted_keys[:len(_price_cache) - _max_cache_entries]:
                del _price_cache[k]


def get_cached_prices(ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
    """
    Get price data using centralized robust_data_fetcher.
    Supports US, Indian (.NS, .BO), and international tickers.
    """
    # Input validation via RDF
    try:
        ticker = validate_ticker(ticker.strip().upper())
    except ValueError as e:
        logger.warning(f"Invalid ticker format rejected: {ticker} - {e}")
        return None
    
    cache_key = f"{ticker}_{period}"
    now = datetime.now()
    
    with _cache_lock:
        if cache_key in _price_cache:
            cached = _price_cache[cache_key]
            if (now - cached["timestamp"]).total_seconds() < _cache_ttl_minutes * 60:
                return cached["data"].copy()  # Return copy to prevent mutation
    
    try:
        # Use robust data fetcher (multi-source: NSE Direct -> Yahoo Direct -> yfinance)
        df = rdf_get_price(ticker, period=period, interval="1d")
        if df is None or df.empty:
            return None
        
        with _cache_lock:
            _price_cache[cache_key] = {"data": df, "timestamp": now}
            _cleanup_cache()
        
        return df
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
        return None


def calculate_returns(prices: pd.Series, days: int) -> float:
    """Calculate total return over period"""
    if len(prices) < days:
        return np.nan
    return (prices.iloc[-1] / prices.iloc[-days]) - 1


def calculate_volatility(prices: pd.Series, days: int = 63) -> float:
    """Calculate annualized volatility"""
    if len(prices) < days:
        return np.nan
    returns = prices.pct_change().dropna().tail(days)
    return returns.std() * np.sqrt(252)


def calculate_max_drawdown(prices: pd.Series, days: int = 252) -> float:
    """Calculate maximum drawdown over period"""
    if len(prices) < days:
        prices_window = prices
    else:
        prices_window = prices.tail(days)
    
    peak = prices_window.expanding(min_periods=1).max()
    drawdown = (prices_window / peak) - 1
    return drawdown.min()


def calculate_consistency(prices: pd.Series, weeks: int = 12) -> float:
    """Calculate percentage of positive weeks"""
    if len(prices) < weeks * 5:
        return np.nan
    
    # Resample to weekly
    weekly = prices.resample('W').last().dropna()
    if len(weekly) < weeks + 1:
        return np.nan
    
    weekly_returns = weekly.pct_change().dropna().tail(weeks)
    positive_weeks = (weekly_returns > 0).sum()
    return positive_weeks / len(weekly_returns)


def compute_momentum_score(
    symbols: List[str],
    benchmark: str = "SPY"
) -> Dict:
    """
    Calculate cross-sectional momentum scores for a list of symbols.
    
    Returns z-score normalized metrics and composite score 0-100.
    """
    results = []
    errors = []
    
    # Fetch benchmark data
    benchmark_prices = get_cached_prices(benchmark, "2y")
    if benchmark_prices is None or benchmark_prices.empty:
        return {"status": "error", "message": f"Cannot fetch benchmark {benchmark}"}
    
    benchmark_close = benchmark_prices["Close"]
    benchmark_ret_126 = calculate_returns(benchmark_close, 126)
    
    # Calculate metrics for each symbol
    for symbol in symbols:
        try:
            prices = get_cached_prices(symbol, "2y")
            if prices is None or prices.empty:
                errors.append({"symbol": symbol, "error": "No data available"})
                continue
            
            close = prices["Close"]
            
            if len(close) < 252:
                errors.append({"symbol": symbol, "error": f"Insufficient data: {len(close)} days, need 252"})
                continue
            
            # Multi-period returns
            ret_63 = calculate_returns(close, 63)
            ret_126 = calculate_returns(close, 126)
            ret_252 = calculate_returns(close, 252)
            
            # Volatility
            vol_63 = calculate_volatility(close, 63)
            
            # Volatility-adjusted return
            adj_ret_126 = ret_126 / (vol_63 + 0.0001)
            
            # Max drawdown (more negative = worse)
            mdd_252 = calculate_max_drawdown(close, 252)
            
            # Trend consistency
            consistency = calculate_consistency(close, 12)
            
            # Relative strength
            rs_126 = ret_126 - benchmark_ret_126
            
            # Current price
            current_price = float(close.iloc[-1])
            
            results.append({
                "symbol": symbol,
                "price_current": current_price,
                "ret_63": ret_63,
                "ret_126": ret_126,
                "ret_252": ret_252,
                "vol_63": vol_63,
                "adj_ret_126": adj_ret_126,
                "mdd_252": mdd_252,
                "consistency": consistency,
                "rs_126": rs_126
            })
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            errors.append({"symbol": symbol, "error": str(e)})
    
    if not results:
        return {"status": "error", "errors": errors, "data": []}
    
    # Convert to DataFrame for cross-sectional normalization
    df = pd.DataFrame(results)
    
    # Z-score normalization
    metrics_to_normalize = ["ret_63", "ret_126", "ret_252", "adj_ret_126", "consistency", "rs_126", "mdd_252"]
    
    for metric in metrics_to_normalize:
        if metric in df.columns:
            mean_val = df[metric].mean()
            std_val = df[metric].std()
            z_col = f"z_{metric}"
            df[z_col] = (df[metric] - mean_val) / (std_val + 0.0001)
    
    # Note: mdd_252 z-score is already correct - higher z = less negative = better
    
    # Composite raw score with weights
    df["raw_score"] = (
        0.20 * df["z_ret_63"] +
        0.25 * df["z_ret_126"] +
        0.20 * df["z_ret_252"] +
        0.15 * df["z_adj_ret_126"] +
        0.10 * df["z_consistency"] +
        0.10 * df["z_rs_126"] +
        0.20 * df["z_mdd_252"]  # Higher z = smaller drawdown = better
    )
    
    # Convert to percentile rank (0-100 scale)
    df["rank"] = df["raw_score"].rank(ascending=True)
    n = len(df)
    df["percentile"] = ((df["rank"] - 1) / (n - 1)) * 100 if n > 1 else 50
    df["score_0_100"] = df["percentile"]
    
    # Trend phase classification
    def classify_phase(row):
        accel = row["ret_63"] - row["ret_126"]
        score = row["score_0_100"]
        consistency = row["consistency"]
        
        if score > 70 and accel > 0 and consistency > 0.6:
            return "Established"
        elif score > 50 and accel > 0:
            return "Early"
        elif score > 70 and accel < 0:
            return "Late"
        elif score < 50 and row["ret_63"] < 0:
            return "Exhausted"
        else:
            return "Neutral"
    
    df["trend_phase"] = df.apply(classify_phase, axis=1)
    df["acceleration"] = df["ret_63"] - df["ret_126"]
    
    # Stability score (inverse of vol/mdd percentile)
    df["vol_percentile"] = df["vol_63"].rank(pct=True)
    df["mdd_percentile"] = df["mdd_252"].abs().rank(pct=True)
    df["stability_raw"] = 100 - (df["vol_percentile"] * 50 + df["mdd_percentile"] * 50)
    df["stability_score"] = df["stability_raw"].clip(0, 100)
    
    # Build response
    response_data = []
    for _, row in df.iterrows():
        response_data.append({
            "symbol": row["symbol"],
            "price_current": round(row["price_current"], 2),
            "returns": {
                "ret_63": round(row["ret_63"], 4),
                "ret_126": round(row["ret_126"], 4),
                "ret_252": round(row["ret_252"], 4)
            },
            "risk_metrics": {
                "vol_63": round(row["vol_63"], 4),
                "adj_ret_126": round(row["adj_ret_126"], 4),
                "mdd_252": round(row["mdd_252"], 4),
                "consistency": round(row["consistency"], 4) if pd.notna(row["consistency"]) else 0.5
            },
            "relative": {
                "rs_126": round(row["rs_126"], 4)
            },
            "scores": {
                "raw_score": round(row["raw_score"], 4),
                "score_0_100": round(row["score_0_100"], 2),
                "rank": int(row["rank"]),
                "percentile": round(row["percentile"], 2),
                "stability_score": round(row["stability_score"], 2)
            },
            "classification": {
                "trend_phase": row["trend_phase"],
                "acceleration": round(row["acceleration"], 4)
            },
            "debug_metrics": {
                "z_ret_63": round(row["z_ret_63"], 4),
                "z_ret_126": round(row["z_ret_126"], 4),
                "z_ret_252": round(row["z_ret_252"], 4),
                "z_adj_ret_126": round(row["z_adj_ret_126"], 4),
                "z_consistency": round(row["z_consistency"], 4),
                "z_rs_126": round(row["z_rs_126"], 4),
                "z_mdd_252": round(row["z_mdd_252"], 4)
            }
        })
    
    # Sort by score descending
    response_data.sort(key=lambda x: x["scores"]["score_0_100"], reverse=True)
    
    return {
        "status": "success" if not errors else "partial_success",
        "timestamp": datetime.now().isoformat() + "Z",
        "benchmark": benchmark,
        "data": response_data,
        "errors": errors if errors else None
    }
