"""
Shared Indicator Engine Module

Provides unified indicator computation for Markets and Security pages.
Supports: RSI, MACD, STOCH, ROC, CCI, ADX, MFI
Enforces max 2 active indicators per request.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from app.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_stoch,
    calculate_roc,
    calculate_cci,
    calculate_adx,
    calculate_mfi
)
import logging

logger = logging.getLogger(__name__)

MAX_INDICATORS = 2

SUPPORTED_INDICATORS = ["RSI", "MACD", "STOCH", "ROC", "CCI", "ADX", "MFI"]


def compute_indicators_for_bars(
    bars: List[Dict],
    indicator_names: List[str]
) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    Compute requested indicators from OHLCV bars.
    
    Args:
        bars: List of OHLCV bar dicts with keys: timestamp, open, high, low, close, volume
        indicator_names: List of indicator names to compute (e.g., ["RSI", "MACD"])
    
    Returns:
        Tuple of (indicators dict, errors list)
        - indicators: Dict keyed by indicator name, each value is list of timestamped data points
        - errors: List of error/warning messages
    """
    errors = []
    indicators = {}
    
    if not bars or len(bars) < 2:
        return indicators, ["Insufficient data for indicator calculation"]
    
    # Validate and limit indicators
    valid_indicators = [i.upper() for i in indicator_names if i.upper() in SUPPORTED_INDICATORS]
    
    if len(valid_indicators) > MAX_INDICATORS:
        errors.append(f"Maximum {MAX_INDICATORS} indicators allowed. Using first {MAX_INDICATORS}.")
        valid_indicators = valid_indicators[:MAX_INDICATORS]
    
    if not valid_indicators:
        return indicators, errors
    
    # Convert bars to pandas DataFrame
    df = pd.DataFrame(bars)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()
    
    # Rename columns to match indicator function expectations
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })
    
    # Check minimum data requirements
    min_periods_required = {
        "RSI": 14,
        "MACD": 35,  # 26 + 9 for signal line
        "STOCH": 17,  # 14 + 3
        "ROC": 10,
        "CCI": 20,
        "ADX": 28,  # 14 * 2 for smoothing
        "MFI": 14
    }
    
    for ind_name in valid_indicators:
        try:
            if len(df) < min_periods_required.get(ind_name, 14):
                errors.append(f"Insufficient data for {ind_name} (need {min_periods_required.get(ind_name, 14)} bars)")
                continue
            
            ind_data = _compute_single_indicator(df, ind_name)
            if ind_data:
                indicators[ind_name] = ind_data
                
        except Exception as e:
            logger.error(f"Error computing {ind_name}: {e}")
            errors.append(f"Failed to compute {ind_name}: {str(e)}")
    
    return indicators, errors


def _compute_single_indicator(df: pd.DataFrame, name: str) -> List[Dict]:
    """
    Compute a single indicator and return timestamped data points.
    """
    timestamps = df.index.strftime('%Y-%m-%dT%H:%M:%SZ').tolist()
    
    if name == "RSI":
        values = calculate_rsi(df['Close'], window=14)
        return _format_single_series(timestamps, values)
    
    elif name == "MACD":
        macd, signal, hist = calculate_macd(df['Close'], fast=12, slow=26, signal=9)
        return _format_macd_series(timestamps, macd, signal, hist)
    
    elif name == "STOCH":
        k, d = calculate_stoch(df['High'], df['Low'], df['Close'], k_window=14, d_window=3, slow_k=3)
        return _format_stoch_series(timestamps, k, d)
    
    elif name == "ROC":
        values = calculate_roc(df['Close'], window=10)
        return _format_single_series(timestamps, values)
    
    elif name == "CCI":
        values = calculate_cci(df['High'], df['Low'], df['Close'], window=20)
        return _format_single_series(timestamps, values)
    
    elif name == "ADX":
        values = calculate_adx(df['High'], df['Low'], df['Close'], window=14)
        return _format_single_series(timestamps, values)
    
    elif name == "MFI":
        values = calculate_mfi(df['High'], df['Low'], df['Close'], df['Volume'], window=14)
        return _format_single_series(timestamps, values)
    
    return []


def _format_single_series(timestamps: List[str], values: pd.Series) -> List[Dict]:
    """Format a single-value indicator series."""
    result = []
    for ts, val in zip(timestamps, values):
        if pd.notna(val) and not np.isinf(val):
            result.append({
                "timestamp": ts,
                "value": round(float(val), 4)
            })
    return result


def _format_macd_series(
    timestamps: List[str], 
    macd: pd.Series, 
    signal: pd.Series, 
    hist: pd.Series
) -> List[Dict]:
    """Format MACD indicator with macd, signal, and histogram."""
    result = []
    for i, ts in enumerate(timestamps):
        m = macd.iloc[i] if i < len(macd) else None
        s = signal.iloc[i] if i < len(signal) else None
        h = hist.iloc[i] if i < len(hist) else None
        
        if pd.notna(m) and pd.notna(s) and pd.notna(h):
            if not (np.isinf(m) or np.isinf(s) or np.isinf(h)):
                result.append({
                    "timestamp": ts,
                    "macd": round(float(m), 4),
                    "signal": round(float(s), 4),
                    "histogram": round(float(h), 4)
                })
    return result


def _format_stoch_series(
    timestamps: List[str],
    k: pd.Series,
    d: pd.Series
) -> List[Dict]:
    """Format Stochastic indicator with %K and %D."""
    result = []
    for i, ts in enumerate(timestamps):
        k_val = k.iloc[i] if i < len(k) else None
        d_val = d.iloc[i] if i < len(d) else None
        
        if pd.notna(k_val) and pd.notna(d_val):
            if not (np.isinf(k_val) or np.isinf(d_val)):
                result.append({
                    "timestamp": ts,
                    "k": round(float(k_val), 4),
                    "d": round(float(d_val), 4)
                })
    return result


def get_indicator_reference_levels(name: str) -> List[float]:
    """
    Return reference levels for an indicator (for horizontal guides).
    """
    refs = {
        "RSI": [30, 70],
        "STOCH": [20, 80],
        "CCI": [-100, 0, 100],
        "ADX": [20, 40],
        "MFI": [20, 80],
        "ROC": [0],
        "MACD": [0]
    }
    return refs.get(name.upper(), [])
