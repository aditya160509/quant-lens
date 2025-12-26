"""
Cluster E Service Module
Shared math utilities for all Cluster E research endpoints.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# ===== Core Math Utilities =====

def zscore(x: Union[pd.Series, np.ndarray], ddof: int = 1) -> Union[pd.Series, np.ndarray]:
    """
    Compute z-score: (x - mean) / std.
    Returns 0 if std is 0 to avoid division by zero.
    """
    mean = np.nanmean(x)
    std = np.nanstd(x, ddof=ddof)
    if std == 0 or np.isnan(std):
        return np.zeros_like(x)
    return (x - mean) / std


def zscore_single(value: float, series: Union[pd.Series, np.ndarray]) -> float:
    """
    Compute z-score for a single value against a series.
    """
    mean = np.nanmean(series)
    std = np.nanstd(series, ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return (value - mean) / std


def percentile_rank(x: Union[pd.Series, np.ndarray]) -> Union[pd.Series, np.ndarray]:
    """
    Compute percentile rank: rank(x) / (n - 1).
    Returns values in range [0, 1].
    """
    n = len(x)
    if n <= 1:
        return np.zeros_like(x)
    ranks = pd.Series(x).rank(method='average').values
    return (ranks - 1) / (n - 1)


def percentile_rank_single(value: float, series: Union[pd.Series, np.ndarray]) -> float:
    """
    Compute percentile rank for a single value against a series.
    """
    series = np.array(series)
    n = len(series)
    if n == 0:
        return 0.5
    count_below = np.sum(series < value)
    count_equal = np.sum(series == value)
    return (count_below + 0.5 * count_equal) / n


def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """
    Compute rolling mean with specified window.
    """
    return series.rolling(window=window, min_periods=1).mean()


def rolling_std(series: pd.Series, window: int, ddof: int = 1) -> pd.Series:
    """
    Compute rolling standard deviation with specified window.
    """
    return series.rolling(window=window, min_periods=2).std(ddof=ddof)


def daily_return(close: pd.Series) -> pd.Series:
    """
    Compute daily simple returns: close[t] / close[t-1] - 1.
    """
    return close.pct_change()


def log_return(close: pd.Series) -> pd.Series:
    """
    Compute log returns: ln(close[t] / close[t-1]).
    """
    return np.log(close / close.shift(1))


def realized_vol(returns: pd.Series, window: int = 21, annualize: bool = True) -> pd.Series:
    """
    Compute realized volatility as rolling std of returns.
    Annualized by default (multiply by sqrt(252)).
    """
    vol = rolling_std(returns, window)
    if annualize:
        vol = vol * np.sqrt(252)
    return vol


def realized_vol_scalar(returns: pd.Series, annualize: bool = True) -> float:
    """
    Compute realized volatility as std of returns series.
    """
    vol = np.nanstd(returns, ddof=1)
    if annualize:
        vol = vol * np.sqrt(252)
    return float(vol)


# ===== Indicator Utilities =====

def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD indicator.
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ===== Pattern Detection =====

def detect_golden_cross(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """
    Detect golden cross: fast SMA crosses above slow SMA.
    Returns boolean Series.
    """
    sma_fast = sma(close, fast)
    sma_slow = sma(close, slow)
    
    cross = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
    return cross


def detect_death_cross(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """
    Detect death cross: fast SMA crosses below slow SMA.
    """
    sma_fast = sma(close, fast)
    sma_slow = sma(close, slow)
    
    cross = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))
    return cross


def detect_rsi_oversold(close: pd.Series, window: int = 14, threshold: float = 30) -> pd.Series:
    """
    Detect RSI oversold condition.
    """
    rsi_val = rsi(close, window)
    return rsi_val < threshold


def detect_rsi_overbought(close: pd.Series, window: int = 14, threshold: float = 70) -> pd.Series:
    """
    Detect RSI overbought condition.
    """
    rsi_val = rsi(close, window)
    return rsi_val > threshold


def detect_volume_spike(volume: pd.Series, window: int = 20, threshold: float = 2.0) -> pd.Series:
    """
    Detect volume spike: z-score of volume > threshold.
    """
    vol_mean = rolling_mean(volume, window)
    vol_std = rolling_std(volume, window)
    vol_z = (volume - vol_mean) / vol_std.replace(0, np.nan)
    return vol_z.fillna(0) >= threshold


def detect_breakout(high: pd.Series, close: pd.Series, window: int = 55) -> pd.Series:
    """
    Detect breakout above resistance (highest high of last N bars).
    """
    resistance = high.shift(1).rolling(window=window).max()
    return close > resistance


# ===== Correlation & Covariance =====

def rolling_correlation(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    """
    Compute rolling correlation between two series.
    """
    return x.rolling(window=window).corr(y)


def correlation_matrix(returns_df: pd.DataFrame, window: Optional[int] = None) -> pd.DataFrame:
    """
    Compute correlation matrix for a DataFrame of returns.
    If window is None, uses full history.
    """
    if window is not None:
        returns_df = returns_df.tail(window)
    return returns_df.corr()


# ===== Sharpe Ratio =====

def sharpe_ratio(returns: pd.Series, rf: float = 0.0, annualize: bool = True) -> float:
    """
    Compute Sharpe ratio for a returns series.
    """
    excess = returns - rf / 252  # Daily risk-free rate
    mean_ret = np.nanmean(excess)
    std_ret = np.nanstd(excess, ddof=1)
    
    if std_ret == 0 or np.isnan(std_ret):
        return 0.0
    
    sharpe = mean_ret / std_ret
    if annualize:
        sharpe = sharpe * np.sqrt(252)
    return float(sharpe)


def rolling_sharpe(returns: pd.Series, window: int, rf: float = 0.0) -> pd.Series:
    """
    Compute rolling Sharpe ratio.
    """
    excess = returns - rf / 252
    roll_mean = rolling_mean(excess, window)
    roll_std = rolling_std(excess, window)
    
    sharpe = (roll_mean / roll_std.replace(0, np.nan)) * np.sqrt(252)
    return sharpe.fillna(0)


# ===== Stress Mapping =====

def stress_from_zscore(z: float, invert: bool = False) -> float:
    """
    Map z-score to stress scale [0, 1] using linear clipping.
    Formula: stress = clip((z + 3) / 6, 0, 1)
    If invert=True, stress = 1 - stress (for metrics where low = stress)
    """
    stress = np.clip((z + 3) / 6, 0, 1)
    if invert:
        stress = 1 - stress
    return float(stress)


def risk_label(score: float) -> str:
    """
    Convert risk score (0-100) to label.
    """
    if score < 20:
        return "calm"
    elif score < 40:
        return "neutral"
    elif score < 60:
        return "cautious"
    elif score < 80:
        return "stressed"
    else:
        return "extreme"


# ===== Sentiment Scoring =====

def candle_sentiment(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    prev_close: float,
    vol_z: float
) -> float:
    """
    Compute per-candle sentiment score.
    
    Formula:
    body_pct = (close - open) / max(high - low, epsilon)
    return_1d = close / prev_close - 1
    score = 0.5 * tanh(5 * body_pct) + 0.3 * tanh(3 * return_1d) + 0.2 * tanh(0.5 * vol_z)
    """
    epsilon = 0.0001
    range_val = max(high - low, epsilon)
    body_pct = (close - open_price) / range_val
    return_1d = (close / prev_close - 1) if prev_close > 0 else 0
    
    score = (
        0.5 * np.tanh(5 * body_pct) +
        0.3 * np.tanh(3 * return_1d) +
        0.2 * np.tanh(0.5 * vol_z)
    )
    return float(np.clip(score, -1, 1))


def sentiment_label(score: float) -> str:
    """
    Convert sentiment score (-1 to 1) to label.
    """
    if score >= 0.35:
        return "bullish"
    elif score >= 0.10:
        return "mild_bullish"
    elif score >= -0.10:
        return "neutral"
    elif score >= -0.35:
        return "mild_bearish"
    else:
        return "bearish"


# ===== Episode Presets =====

REPLAY_PRESETS = {
    "covid": {"start": "2020-02-15", "end": "2020-05-30", "title": "COVID-19 Crash"},
    "gfc": {"start": "2008-08-01", "end": "2009-06-30", "title": "Global Financial Crisis"},
    "dotcom": {"start": "2000-03-01", "end": "2002-10-31", "title": "Dot-com Bubble Burst"},
    "inflation2022": {"start": "2022-01-01", "end": "2022-12-31", "title": "2022 Inflation Shock"},
    "brexit": {"start": "2016-06-01", "end": "2016-08-31", "title": "Brexit Vote"},
    "flash_crash": {"start": "2010-05-01", "end": "2010-06-30", "title": "Flash Crash"},
}


def get_replay_dates(preset: str) -> Dict[str, str]:
    """
    Get start/end dates for a replay preset.
    """
    return REPLAY_PRESETS.get(preset.lower(), {})
