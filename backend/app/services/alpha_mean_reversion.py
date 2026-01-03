"""
Alpha Model: Mean Reversion Intelligence
Quantify stretch vs statistical behavior with confidence gating
"""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Use centralized data fetcher instead of direct yfinance
from app.services.robust_data_fetcher import get_price_data as rdf_get_price

logger = logging.getLogger(__name__)

# Cache for price data
_price_cache: Dict[str, Dict] = {}
_cache_ttl_minutes = 30


def get_cached_prices(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """
    Get price data using centralized robust_data_fetcher.
    Supports US, Indian (.NS, .BO), and international tickers.
    """
    cache_key = f"{ticker}_{period}"
    now = datetime.now()
    
    if cache_key in _price_cache:
        cached = _price_cache[cache_key]
        if (now - cached["timestamp"]).total_seconds() < _cache_ttl_minutes * 60:
            return cached["data"]
    
    try:
        # Use robust data fetcher (multi-source: NSE Direct -> Yahoo Direct -> yfinance)
        df = rdf_get_price(ticker, period=period, interval="1d")
        if df is None or df.empty:
            return None
        _price_cache[cache_key] = {"data": df, "timestamp": now}
        return df
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
        return None


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI using Wilder smoothing"""
    if len(prices) < period + 1:
        return 50.0
    
    delta = prices.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    
    # Wilder smoothing
    avg_gain = gains.rolling(window=period, min_periods=period).mean().iloc[-1]
    avg_loss = losses.rolling(window=period, min_periods=period).mean().iloc[-1]
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


def calculate_bollinger_z(prices: pd.Series, period: int = 20) -> float:
    """Calculate Z-score relative to Bollinger Bands"""
    if len(prices) < period:
        return 0.0
    
    sma = prices.rolling(window=period).mean().iloc[-1]
    std = prices.rolling(window=period).std().iloc[-1]
    
    if std == 0:
        return 0.0
    
    current = prices.iloc[-1]
    z = (current - sma) / std
    return float(z)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Calculate Average True Range"""
    if len(close) < period + 1:
        return np.nan
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean().iloc[-1]
    return float(atr)


def calculate_sma(prices: pd.Series, period: int) -> float:
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return prices.mean()
    return float(prices.rolling(window=period).mean().iloc[-1])


def calculate_realized_vol(prices: pd.Series, period: int = 20) -> float:
    """Calculate realized volatility (annualized)"""
    if len(prices) < period:
        return np.nan
    returns = prices.pct_change().dropna().tail(period)
    return returns.std() * np.sqrt(252)


def compute_mean_reversion(
    symbols: List[str],
    sensitivity: str = "conservative"
) -> Dict:
    """
    Calculate mean reversion scores with confidence gating.
    
    sensitivity: "conservative" (longer lookbacks) or "aggressive" (shorter)
    """
    # Sensitivity parameters
    if sensitivity == "aggressive":
        bb_period = 10
        sma_period = 10
        sma_long_period = 30
    else:  # conservative
        bb_period = 20
        sma_period = 20
        sma_long_period = 50
    
    results = []
    errors = []
    
    for symbol in symbols:
        try:
            prices = get_cached_prices(symbol, "1y")
            if prices is None or prices.empty:
                errors.append({"symbol": symbol, "error": "No data available"})
                continue
            
            close = prices["Close"]
            high = prices["High"]
            low = prices["Low"]
            
            if len(close) < 60:
                errors.append({"symbol": symbol, "error": f"Insufficient data: {len(close)} days"})
                continue
            
            # Current price
            current_price = float(close.iloc[-1])
            
            # RSI (14-period)
            rsi = calculate_rsi(close, 14)
            rsi_deviation = (rsi - 50) / 10  # Normalize: -5 to +5
            
            # Bollinger Z-score
            boll_z = calculate_bollinger_z(close, bb_period)
            
            # SMA distances
            sma_short = calculate_sma(close, sma_period)
            sma_long = calculate_sma(close, sma_long_period)
            dist_short = (current_price - sma_short) / current_price
            dist_long = (current_price - sma_long) / current_price
            
            # ATR and ATR-normalized stretch
            atr = calculate_atr(high, low, close, 14)
            stretch_atr = (current_price - sma_short) / (atr + 0.0001)
            
            # Volatility regime
            rv_20 = calculate_realized_vol(close, 20)
            rv_252 = calculate_realized_vol(close, 252) if len(close) >= 252 else rv_20
            vol_regime = rv_20 / (rv_252 + 0.0001)
            
            # Unified stretch score
            stretch = (
                0.45 * boll_z +
                0.25 * rsi_deviation +
                0.15 * stretch_atr +
                0.15 * (dist_long / (atr / current_price + 0.0001))
            )
            
            # Reversion score (inverted)
            reversion_score = -stretch
            
            # Magnitude (0-100)
            magnitude = min(100, abs(reversion_score) * 25)
            
            # Confidence calculation
            confidence = 70  # Base
            
            # Vol regime penalty
            if vol_regime > 1.5:
                confidence -= 20
            elif vol_regime > 1.2:
                confidence -= 10
            
            # Note: earnings proximity and momentum conflict would be added here
            # if we had access to those services
            
            # Clamp confidence
            confidence = max(0, min(100, confidence))
            
            # Quality label
            if confidence < 35:
                quality_label = "Low Odds"
            elif confidence <= 65:
                quality_label = "Tactical"
            elif magnitude > 60:
                quality_label = "High Probability"
            else:
                quality_label = "Moderate"
            
            # Dangerous zone detection
            dangerous = False
            if vol_regime > 1.5 and magnitude > 70:
                dangerous = True
            
            # Direction interpretation
            if reversion_score > 0:
                direction = "oversold"
            elif reversion_score < 0:
                direction = "overbought"
            else:
                direction = "neutral"
            
            results.append({
                "symbol": symbol,
                "price_current": round(current_price, 2),
                "stretch_indicators": {
                    "rsi": round(rsi, 2),
                    "rsi_deviation": round(rsi_deviation, 4),
                    "boll_z": round(boll_z, 4),
                    "dist_short": round(dist_short, 4),
                    "dist_long": round(dist_long, 4),
                    "stretch_atr": round(stretch_atr, 4),
                    "atr_14": round(atr, 4)
                },
                "volatility": {
                    "rv_20": round(rv_20, 4) if pd.notna(rv_20) else None,
                    "rv_252": round(rv_252, 4) if pd.notna(rv_252) else None,
                    "vol_regime": round(vol_regime, 4)
                },
                "scores": {
                    "stretch": round(stretch, 4),
                    "reversion_score": round(reversion_score, 4),
                    "magnitude_0_100": round(magnitude, 2),
                    "confidence_0_100": round(confidence, 2),
                    "quality_label": quality_label,
                    "direction": direction
                },
                "flags": {
                    "dangerous": dangerous,
                    "earnings_proximity": None,  # Would need earnings data
                    "momentum_conflict": None  # Would need momentum data
                },
                "debug": {
                    "base_confidence": 70,
                    "vol_penalty": -(20 if vol_regime > 1.5 else (10 if vol_regime > 1.2 else 0)),
                    "final_confidence": confidence
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            errors.append({"symbol": symbol, "error": str(e)})
    
    # Sort by magnitude descending
    results.sort(key=lambda x: x["scores"]["magnitude_0_100"], reverse=True)
    
    return {
        "status": "success" if not errors else "partial_success",
        "timestamp": datetime.now().isoformat() + "Z",
        "sensitivity": sensitivity,
        "data": results,
        "errors": errors if errors else None
    }
