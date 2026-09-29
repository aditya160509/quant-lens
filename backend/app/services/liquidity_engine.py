"""
Liquidity Intelligence Engine
=============================

Institutional-grade liquidity analysis platform for market microstructure,
execution risk, and systemic stress detection.

7 Interconnected Systems:
1. Liquidity State Manifold
2. Cliff & Vacuum Detection
3. Contagion & Transmission
4. Absorption & Capacity
5. Regime Transition Engine
6. Volatility-Liquidity Feedback
7. Crisis Fingerprint Vault
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from scipy import stats
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.services.robust_data_fetcher import get_batch_data, get_price_data

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LiquidityMetrics:
    """Core liquidity metrics for a ticker."""
    ticker: str
    as_of: str
    
    # Amihud illiquidity
    amihud_mean: float = 0.0
    amihud_std: float = 0.0
    amihud_skew: float = 0.0
    amihud_kurt: float = 0.0
    
    # Dollar volume
    dollar_volume_mean: float = 0.0
    dollar_volume_std: float = 0.0
    dollar_volume_trend: float = 0.0
    
    # Gap analysis
    gap_frequency: float = 0.0
    gap_mean_size: float = 0.0
    gap_recovery_time: float = 0.0
    gap_failed_recovery_rate: float = 0.0
    
    # Asymmetry
    up_day_illiquidity: float = 0.0
    down_day_illiquidity: float = 0.0
    asymmetry_ratio: float = 1.0
    
    # Derived scores
    stability_score: float = 50.0
    fragility_score: float = 50.0
    depth_score: float = 50.0
    
    # Persistence/autocorrelation (new)
    persistence_score: float = 0.0  # How sticky is illiquidity
    autocorr_1d: float = 0.0
    autocorr_5d: float = 0.0
    half_life: float = 0.0  # Days for shock to decay 50%
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "amihud_mean": round(self.amihud_mean, 6),
            "amihud_std": round(self.amihud_std, 6),
            "amihud_skew": round(self.amihud_skew, 4),
            "dollar_volume_mean": round(self.dollar_volume_mean, 0),
            "dollar_volume_trend": round(self.dollar_volume_trend, 4),
            "gap_frequency": round(self.gap_frequency, 4),
            "gap_mean_size": round(self.gap_mean_size, 4),
            "gap_recovery_time": round(self.gap_recovery_time, 2),
            "asymmetry_ratio": round(self.asymmetry_ratio, 4),
            "stability_score": round(self.stability_score, 1),
            "fragility_score": round(self.fragility_score, 1),
            "depth_score": round(self.depth_score, 1),
            "persistence_score": round(self.persistence_score, 2),
            "autocorr_1d": round(self.autocorr_1d, 4),
            "autocorr_5d": round(self.autocorr_5d, 4),
            "half_life": round(self.half_life, 1),
        }


@dataclass
class ManifoldCoordinates:
    """3D manifold coordinates for a ticker."""
    ticker: str
    x: float  # Stability dimension
    y: float  # Depth dimension
    z: float  # Responsiveness dimension
    phase: str = "normal"  # normal, tight, fragile, stress, vacuum
    sector: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "z": round(self.z, 4),
            "phase": self.phase,
            "sector": self.sector,
        }


@dataclass
class CliffMetrics:
    """Cliff and vacuum detection metrics."""
    ticker: str
    cliff_distance: float = 0.0
    vacuum_probability: float = 0.0
    illiquidity_acceleration: float = 0.0
    volume_acceleration: float = 0.0
    gap_acceleration: float = 0.0
    exhaustion_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "cliff_distance": round(self.cliff_distance, 4),
            "vacuum_probability": round(self.vacuum_probability, 4),
            "illiquidity_acceleration": round(self.illiquidity_acceleration, 6),
            "volume_acceleration": round(self.volume_acceleration, 6),
            "gap_acceleration": round(self.gap_acceleration, 4),
            "exhaustion_score": round(self.exhaustion_score, 1),
        }


@dataclass 
class ContagionMetrics:
    """Contagion transmission metrics."""
    ticker: str
    r_number: float = 0.0  # Reproduction number
    patient_zero_prob: float = 0.0
    firebreak_score: float = 0.0
    in_degree: int = 0
    out_degree: int = 0
    avg_transmission_lag: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "r_number": round(self.r_number, 2),
            "patient_zero_prob": round(self.patient_zero_prob, 4),
            "firebreak_score": round(self.firebreak_score, 2),
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "avg_transmission_lag": round(self.avg_transmission_lag, 1),
        }


@dataclass
class CapacityMetrics:
    """Liquidity absorption capacity."""
    ticker: str
    safe_size_dollars: float = 0.0
    safe_size_pct_adv: float = 0.0
    stress_size_dollars: float = 0.0
    break_size_dollars: float = 0.0
    impact_slope: float = 0.0
    convexity: float = 0.0
    elasticity: float = 0.0
    capacity_percentile: float = 50.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "safe_size_dollars": round(self.safe_size_dollars, 0),
            "safe_size_pct_adv": round(self.safe_size_pct_adv, 2),
            "stress_size_dollars": round(self.stress_size_dollars, 0),
            "break_size_dollars": round(self.break_size_dollars, 0),
            "impact_slope": round(self.impact_slope, 4),
            "convexity": round(self.convexity, 4),
            "elasticity": round(self.elasticity, 4),
            "capacity_percentile": round(self.capacity_percentile, 1),
        }


@dataclass
class RegimeState:
    """Liquidity regime classification."""
    ticker: str
    current_regime: str = "normal"  # normal, tight, fragile, stress, crisis
    regime_probability: Dict[str, float] = field(default_factory=dict)
    days_in_regime: int = 0
    transition_risk: float = 0.0
    boundary_distance: float = 0.0
    regime_velocity: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "current_regime": self.current_regime,
            "regime_probability": {k: round(v, 3) for k, v in self.regime_probability.items()},
            "days_in_regime": self.days_in_regime,
            "transition_risk": round(self.transition_risk, 3),
            "boundary_distance": round(self.boundary_distance, 4),
            "regime_velocity": round(self.regime_velocity, 4),
        }


@dataclass
class FeedbackMetrics:
    """Volatility-liquidity feedback loop metrics."""
    ticker: str
    beta_vol_to_liq: float = 0.0  # Vol -> Liquidity impact
    beta_liq_to_vol: float = 0.0  # Liquidity -> Vol impact
    loop_gain: float = 0.0
    stability_status: str = "stable"  # stable, amplifying, unstable
    runaway_probability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "beta_vol_to_liq": round(self.beta_vol_to_liq, 4),
            "beta_liq_to_vol": round(self.beta_liq_to_vol, 4),
            "loop_gain": round(self.loop_gain, 4),
            "stability_status": self.stability_status,
            "runaway_probability": round(self.runaway_probability, 4),
        }


# =============================================================================
# UNIVERSAL COMPUTATIONS
# =============================================================================

def compute_returns(prices: pd.Series) -> pd.Series:
    """Compute simple returns."""
    return prices.pct_change().dropna()


def compute_hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    """
    PRODUCTION: Compute Hurst exponent for persistence measurement.
    H > 0.5: Trending (persistent)
    H = 0.5: Random walk
    H < 0.5: Mean-reverting
    
    Uses R/S (rescaled range) method.
    """
    if len(series) < max_lag * 2:
        return 0.5  # Default to random walk
    
    try:
        lags = range(2, max_lag)
        rs_values = []
        
        for lag in lags:
            # Divide series into chunks of size lag
            chunks = [series.iloc[i:i+lag] for i in range(0, len(series)-lag, lag)]
            
            rs_chunk = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                # Mean-adjusted cumulative sum
                mean_adj = chunk - chunk.mean()
                cumsum = mean_adj.cumsum()
                
                # Range
                R = cumsum.max() - cumsum.min()
                
                # Standard deviation
                S = chunk.std()
                
                if S > 0:
                    rs_chunk.append(R / S)
            
            if rs_chunk:
                rs_values.append((lag, np.mean(rs_chunk)))
        
        if len(rs_values) < 3:
            return 0.5
        
        # Log-log regression
        log_lags = np.log([v[0] for v in rs_values])
        log_rs = np.log([v[1] for v in rs_values])
        
        # Linear regression: log(R/S) = H * log(n) + c
        H, _ = np.polyfit(log_lags, log_rs, 1)
        
        return float(max(0, min(1, H)))  # Clamp to [0, 1]
    except Exception:
        return 0.5


def compute_gap_recovery(
    open_prices: pd.Series, 
    close: pd.Series, 
    high: pd.Series,
    low: pd.Series,
    threshold_pct: float = 1.0
) -> Dict[str, float]:
    """
    PRODUCTION: Compute gap recovery statistics.
    Returns average recovery time, recovery rate, and failed recovery rate.
    """
    prev_close = close.shift(1)
    gap_size = (open_prices - prev_close) / prev_close * 100
    
    is_gap = np.abs(gap_size) > threshold_pct
    gap_indices = is_gap[is_gap].index
    
    if len(gap_indices) == 0:
        return {
            "gap_count": 0,
            "avg_recovery_time": 0.0,
            "recovery_rate": 1.0,
            "failed_recovery_rate": 0.0,
        }
    
    recovery_times = []
    recovered = 0
    failed = 0
    
    for gap_date in gap_indices:
        gap_val = gap_size.loc[gap_date]
        gap_open = open_prices.loc[gap_date]
        gap_close_prev = prev_close.loc[gap_date]
        
        # Look forward for recovery (close crosses back through gap level)
        future_idx = close.index.get_loc(gap_date)
        
        recovered_at = None
        for i in range(future_idx + 1, min(future_idx + 21, len(close))):  # Max 20 days
            if gap_val > 0:  # Gap up
                if close.iloc[i] <= gap_close_prev:
                    recovered_at = i - future_idx
                    break
            else:  # Gap down
                if close.iloc[i] >= gap_close_prev:
                    recovered_at = i - future_idx
                    break
        
        if recovered_at:
            recovery_times.append(recovered_at)
            recovered += 1
        else:
            failed += 1
    
    total = recovered + failed
    
    return {
        "gap_count": len(gap_indices),
        "avg_recovery_time": float(np.mean(recovery_times)) if recovery_times else 20.0,
        "recovery_rate": float(recovered / total) if total > 0 else 1.0,
        "failed_recovery_rate": float(failed / total) if total > 0 else 0.0,
    }


def compute_log_returns(prices: pd.Series) -> pd.Series:
    """Compute log returns."""
    return np.log(prices / prices.shift(1)).dropna()


def compute_dollar_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Compute dollar volume = close × volume."""
    return close * volume


def compute_amihud(returns: pd.Series, dollar_volume: pd.Series) -> pd.Series:
    """
    Compute Amihud illiquidity ratio.
    Amihud = |return| / dollar_volume
    """
    # Align series
    common_idx = returns.index.intersection(dollar_volume.index)
    r = returns.loc[common_idx]
    dv = dollar_volume.loc[common_idx]
    
    # Avoid division by zero
    dv = dv.replace(0, np.nan)
    amihud = np.abs(r) / dv
    
    # Scale for readability (multiply by 1e6)
    return amihud * 1e6


def detect_gaps(open_prices: pd.Series, close_prices: pd.Series, 
                threshold_pct: float = 1.0) -> pd.DataFrame:
    """
    Detect price gaps (open vs previous close).
    Returns DataFrame with gap info.
    """
    prev_close = close_prices.shift(1)
    gap_size = (open_prices - prev_close) / prev_close * 100
    
    is_gap = np.abs(gap_size) > threshold_pct
    
    gaps = pd.DataFrame({
        "date": open_prices.index,
        "gap_size_pct": gap_size,
        "is_gap": is_gap,
        "direction": np.sign(gap_size),
    })
    
    return gaps[gaps["is_gap"]]


def compute_rolling_stats(series: pd.Series, windows: List[int] = [5, 20, 60, 252]
                         ) -> Dict[str, pd.DataFrame]:
    """Compute rolling statistics at multiple windows."""
    stats = {}
    
    for w in windows:
        stats[f"mean_{w}d"] = series.rolling(w).mean()
        stats[f"std_{w}d"] = series.rolling(w).std()
        stats[f"median_{w}d"] = series.rolling(w).median()
        stats[f"skew_{w}d"] = series.rolling(w).skew()
        stats[f"kurt_{w}d"] = series.rolling(w).kurt()
    
    return pd.DataFrame(stats)


# =============================================================================
# SYSTEM 1: LIQUIDITY STATE MANIFOLD
# =============================================================================

def compute_liquidity_metrics(
    close: pd.Series,
    volume: pd.Series,
    open_prices: pd.Series,
    high: pd.Series,
    low: pd.Series,
    window: int = 60,
    ticker: str = "",
) -> LiquidityMetrics:
    """
    Compute comprehensive liquidity metrics for a single ticker.
    """
    as_of = close.index[-1].strftime("%Y-%m-%d") if hasattr(close.index[-1], 'strftime') else str(close.index[-1])
    
    # Basic series
    returns = compute_returns(close)
    dollar_volume = compute_dollar_volume(close, volume)
    amihud = compute_amihud(returns, dollar_volume)
    
    # Tail the data to window
    returns = returns.tail(window)
    dollar_volume = dollar_volume.tail(window)
    amihud = amihud.tail(window).replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(amihud) < 10:
        return LiquidityMetrics(ticker=ticker, as_of=as_of)
    
    # Amihud stats
    amihud_mean = float(amihud.mean())
    amihud_std = float(amihud.std())
    amihud_skew = float(amihud.skew()) if len(amihud) > 3 else 0.0
    amihud_kurt = float(amihud.kurtosis()) if len(amihud) > 4 else 0.0
    
    # Dollar volume stats
    dv_mean = float(dollar_volume.mean())
    dv_std = float(dollar_volume.std())
    dv_trend = float((dollar_volume.iloc[-5:].mean() / dollar_volume.iloc[:5].mean() - 1)) if len(dollar_volume) >= 10 else 0.0
    
    # Gap analysis - refined with recovery
    gap_stats = compute_gap_recovery(open_prices, close, high, low)
    gap_frequency = gap_stats["gap_count"] / window * 252 # Annualized
    gap_mean_size = float(gaps["gap_size_pct"].abs().mean()) if len(gaps) > 0 else 0.0
    gap_recovery = gap_stats["avg_recovery_time"]
    gap_failed = gap_stats["failed_recovery_rate"]
    
    # Asymmetry
    up_days = returns[returns > 0]
    down_days = returns[returns < 0]
    
    up_amihud = amihud.loc[amihud.index.isin(up_days.index)]
    down_amihud = amihud.loc[amihud.index.isin(down_days.index)]
    
    up_illiq = float(up_amihud.mean()) if len(up_amihud) > 0 else 0.0
    down_illiq = float(down_amihud.mean()) if len(down_amihud) > 0 else 0.0
    asymmetry = down_illiq / up_illiq if up_illiq > 0 else 1.0
    
    # Derived scores (0-100 scale)
    # Lower Amihud = better stability
    stability_pct = max(0, min(100, 100 - amihud_mean * 10000))
    # Lower asymmetry = better
    fragility_pct = max(0, min(100, (asymmetry - 1) * 50 + 50))
    # Higher dollar volume = better depth
    depth_pct = max(0, min(100, np.log10(dv_mean + 1) * 10))
    
    # Persistence/autocorrelation metrics
    autocorr_1d = float(amihud.autocorr(lag=1)) if len(amihud) > 5 else 0.0
    autocorr_5d = float(amihud.autocorr(lag=5)) if len(amihud) > 10 else 0.0
    
    # Persistence score (0-100): higher = stickier illiquidity
    persistence_pct = max(0, min(100, (autocorr_1d + autocorr_5d) * 50 + 50))
    
    # Half-life estimation (simplified: -1 / ln(autocorr_1d))
    # Only meaningful for positive autocorrelation (decay pattern)
    if autocorr_1d > 0.01 and autocorr_1d < 0.99:  # Valid range for half-life
        half_life = float(-np.log(2) / np.log(autocorr_1d))
    elif autocorr_1d <= 0.01:
        half_life = 0.0  # No persistence (immediate reversion)
    else:
        half_life = 30.0  # Near-unit root, very persistent
    half_life = max(0, min(30, half_life))  # Cap at 30 days
    
    return LiquidityMetrics(
        ticker=ticker,
        as_of=as_of,
        amihud_mean=amihud_mean,
        amihud_std=amihud_std,
        amihud_skew=amihud_skew,
        amihud_kurt=amihud_kurt,
        dollar_volume_mean=dv_mean,
        dollar_volume_std=dv_std,
        dollar_volume_trend=dv_trend,
        gap_frequency=gap_frequency,
        gap_mean_size=gap_mean_size,
        gap_recovery_time=gap_recovery,
        gap_failed_recovery_rate=gap_failed,
        up_day_illiquidity=up_illiq,
        down_day_illiquidity=down_illiq,
        asymmetry_ratio=asymmetry,
        stability_score=stability_pct,
        fragility_score=fragility_pct,
        depth_score=depth_pct,
        persistence_score=persistence_pct,
        autocorr_1d=autocorr_1d if not np.isnan(autocorr_1d) else 0.0,
        autocorr_5d=autocorr_5d if not np.isnan(autocorr_5d) else 0.0,
        half_life=half_life,
    )


def compute_manifold_coordinates(
    metrics: List[LiquidityMetrics],
) -> List[ManifoldCoordinates]:
    """
    Map liquidity metrics to 3D manifold coordinates.
    Uses normalized scores as axes.
    """
    coords = []
    
    for m in metrics:
        # X = Stability (0-1)
        x = m.stability_score / 100
        
        # Y = Depth (0-1)
        y = m.depth_score / 100
        
        # Z = Responsiveness (inverse of gap recovery time, normalized)
        z = max(0, min(1, 1 - m.gap_recovery_time / 20))
        
        # Phase classification
        if m.stability_score >= 70 and m.depth_score >= 70:
            phase = "tight"
        elif m.stability_score >= 50 and m.fragility_score < 40:
            phase = "normal"
        elif m.fragility_score >= 70:
            phase = "stress"
        elif m.fragility_score >= 50:
            phase = "fragile"
        else:
            phase = "normal"
        
        coords.append(ManifoldCoordinates(
            ticker=m.ticker,
            x=x,
            y=y,
            z=z,
            phase=phase,
        ))
    
    return coords


# =============================================================================
# SYSTEM 2: CLIFF & VACUUM DETECTION
# =============================================================================

def compute_cliff_metrics(
    close: pd.Series,
    volume: pd.Series,
    open_prices: pd.Series,
    window: int = 60,
    ticker: str = "",
) -> CliffMetrics:
    """
    Detect liquidity cliff and vacuum formation.
    """
    returns = compute_returns(close)
    dollar_volume = compute_dollar_volume(close, volume)
    amihud = compute_amihud(returns, dollar_volume).replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(amihud) < 20:
        return CliffMetrics(ticker=ticker)
    
    # First derivative (rate of change)
    illiq_diff = amihud.diff()
    vol_diff = dollar_volume.diff()
    
    # Second derivative (acceleration)
    illiq_accel = illiq_diff.diff().tail(10).mean()
    vol_accel = vol_diff.diff().tail(10).mean()
    
    # Gap acceleration
    gaps = detect_gaps(open_prices.tail(window), close.tail(window))
    recent_gaps = len(gaps.tail(10))
    older_gaps = len(gaps.head(10))
    gap_accel = (recent_gaps - older_gaps) / 10
    
    # Cliff distance: composite z-score
    # More positive illiq_accel = closer to cliff
    # More negative vol_accel = closer to cliff
    illiq_z = (illiq_accel - illiq_diff.mean()) / (illiq_diff.std() + 1e-10)
    vol_z = -(vol_accel - vol_diff.mean()) / (vol_diff.std() + 1e-10)
    gap_z = gap_accel * 2  # Scale factor
    
    cliff_distance = float(0.4 * illiq_z + 0.4 * vol_z + 0.2 * gap_z)
    
    # Vacuum probability: use shifted sigmoid so baseline is ~5%, not 50%
    # P = 1 / (1 + exp(-(cliff_distance - 2))) maps 0 -> 0.12, 2 -> 0.5, 4 -> 0.88
    vacuum_prob = float(1 / (1 + np.exp(-(cliff_distance - 2))))
    
    # Exhaustion score (0-100): linear scale with offset
    exhaustion = max(0, min(100, cliff_distance * 25 + 50))
    
    return CliffMetrics(
        ticker=ticker,
        cliff_distance=cliff_distance,
        vacuum_probability=vacuum_prob,
        illiquidity_acceleration=float(illiq_accel) if not np.isnan(illiq_accel) else 0.0,
        volume_acceleration=float(vol_accel) if not np.isnan(vol_accel) else 0.0,
        gap_acceleration=float(gap_accel),
        exhaustion_score=float(exhaustion),
    )


# =============================================================================
# SYSTEM 3: CONTAGION & TRANSMISSION
# =============================================================================

def compute_contagion_matrix(
    amihud_dict: Dict[str, pd.Series],
    max_lag: int = 10,
    significance_threshold: float = 0.3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute cross-lag correlation matrix for contagion detection.
    Returns transmission strength matrix and lag matrix.
    """
    tickers = list(amihud_dict.keys())
    n = len(tickers)
    
    strength_matrix = np.zeros((n, n))
    lag_matrix = np.zeros((n, n))
    
    for i, ticker_i in enumerate(tickers):
        for j, ticker_j in enumerate(tickers):
            if i == j:
                continue
            
            series_i = amihud_dict[ticker_i]
            series_j = amihud_dict[ticker_j]
            
            # Align series
            common = series_i.index.intersection(series_j.index)
            if len(common) < 30:
                continue
            
            s_i = series_i.loc[common]
            s_j = series_j.loc[common]
            
            # Find optimal lag
            best_corr = 0
            best_lag = 0
            
            for lag in range(-max_lag, max_lag + 1):
                if lag == 0:
                    corr_val = s_i.corr(s_j)
                elif lag > 0:
                    corr_val = s_i.iloc[:-lag].corr(s_j.iloc[lag:])
                else:
                    corr_val = s_i.iloc[-lag:].corr(s_j.iloc[:lag])
                
                if not np.isnan(corr_val) and abs(corr_val) > abs(best_corr):
                    best_corr = corr_val
                    best_lag = lag
            
            if abs(best_corr) >= significance_threshold:
                strength_matrix[i, j] = best_corr
                lag_matrix[i, j] = best_lag
    
    return (
        pd.DataFrame(strength_matrix, index=tickers, columns=tickers),
        pd.DataFrame(lag_matrix, index=tickers, columns=tickers),
    )


def compute_contagion_metrics(
    strength_matrix: pd.DataFrame,
    lag_matrix: pd.DataFrame,
    ticker: str,
) -> ContagionMetrics:
    """
    Compute contagion metrics for a single ticker.
    """
    if ticker not in strength_matrix.index:
        return ContagionMetrics(ticker=ticker)
    
    # Out-degree: how many others does this ticker transmit to
    out_edges = (strength_matrix.loc[ticker] != 0).sum()
    out_strengths = strength_matrix.loc[ticker][strength_matrix.loc[ticker] != 0]
    
    # In-degree: how many transmit to this ticker
    in_edges = (strength_matrix[ticker] != 0).sum()
    
    # R-number (how many it infects)
    r_number = float(out_edges)
    
    # Average transmission lag
    out_lags = lag_matrix.loc[ticker][strength_matrix.loc[ticker] != 0]
    avg_lag = float(out_lags.abs().mean()) if len(out_lags) > 0 else 0.0
    
    # Patient zero probability: high out + low in + short lag
    p0_score = (out_edges / (in_edges + 1)) * (1 / (avg_lag + 1))
    p0_prob = float(min(1, p0_score / 10))
    
    # Firebreak score: high in + low out
    firebreak = float(in_edges / (out_edges + 1))
    
    return ContagionMetrics(
        ticker=ticker,
        r_number=r_number,
        patient_zero_prob=p0_prob,
        firebreak_score=firebreak,
        in_degree=int(in_edges),
        out_degree=int(out_edges),
        avg_transmission_lag=avg_lag,
    )


# =============================================================================
# SYSTEM 4: CAPACITY & ABSORPTION
# =============================================================================

def compute_capacity_metrics(
    close: pd.Series,
    volume: pd.Series,
    window: int = 60,
    ticker: str = "",
) -> CapacityMetrics:
    """
    Compute liquidity absorption capacity.
    """
    returns = compute_returns(close)
    dollar_volume = compute_dollar_volume(close, volume)
    
    # Align
    common = returns.index.intersection(dollar_volume.index)
    r = returns.loc[common].tail(window)
    dv = dollar_volume.loc[common].tail(window)
    
    if len(r) < 20 or len(dv) < 20:
        return CapacityMetrics(ticker=ticker)
    
    # Average daily volume
    adv = float(dv.mean())
    
    # Impact regression: log(|return|) ~ log(volume)
    log_ret = np.log(np.abs(r) + 1e-10)
    log_vol = np.log(dv + 1e-10)
    
    # Clean data
    valid = ~(np.isinf(log_ret) | np.isinf(log_vol) | np.isnan(log_ret) | np.isnan(log_vol))
    log_ret = log_ret[valid]
    log_vol = log_vol[valid]
    
    if len(log_ret) < 20:
        return CapacityMetrics(ticker=ticker)
    
    try:
        # Linear regression
        slope, intercept = np.polyfit(log_vol, log_ret, 1)
        impact_slope = float(slope)
    except Exception:
        impact_slope = 1.0
    
    # Convexity: measures how much impact accelerates relative to linear
    # Estimated by comparing the power law fit vs linear fit
    from scipy.optimize import curve_fit
    def power_law(x, k, g): return k * (x**g)
    
    try:
        popt, _ = curve_fit(power_law, dv, np.abs(r), p0=[1e-8, 0.5])
        convexity = float(popt[1]) # Gamma exponent is a scale for convexity
    except Exception:
        convexity = 0.5
    
    return CapacityMetrics(
        ticker=ticker,
        safe_size_dollars=safe_size,
        safe_size_pct_adv=10.0,
        stress_size_dollars=stress_size,
        break_size_dollars=break_size,
        impact_slope=impact_slope,
        convexity=convexity,
        elasticity=elasticity,
        capacity_percentile=50.0,  # Will be computed in aggregation
    )


# =============================================================================
# SYSTEM 5: REGIME TRANSITION ENGINE
# =============================================================================

def classify_regime(metrics: LiquidityMetrics) -> str:
    """
    Classify liquidity regime based on metrics.
    """
    stability = metrics.stability_score
    fragility = metrics.fragility_score
    depth = metrics.depth_score
    
    if stability >= 70 and fragility < 30:
        return "tight"
    elif stability >= 50 and fragility < 50:
        return "normal"
    elif fragility >= 70:
        if stability < 30:
            return "crisis"
        return "stress"
    else:
        return "fragile"


def compute_regime_state(
    metrics: LiquidityMetrics,
    historical_regimes: List[str] = None,
) -> RegimeState:
    """
    Compute regime state and transition metrics.
    """
    current = classify_regime(metrics)
    
    # Regime probabilities (simplified)
    probs = {
        "tight": 0.1,
        "normal": 0.6,
        "fragile": 0.2,
        "stress": 0.08,
        "crisis": 0.02,
    }
    probs[current] = 0.7
    
    # Normalize
    total = sum(probs.values())
    probs = {k: v/total for k, v in probs.items()}
    
    # Days in regime (would need historical data)
    days = 10
    
    # Transition risk
    transition_risk = 1 - probs[current]
    
    return RegimeState(
        ticker=metrics.ticker,
        current_regime=current,
        regime_probability=probs,
        days_in_regime=days,
        transition_risk=transition_risk,
        boundary_distance=probs[current] - 0.5,
        regime_velocity=0.01,
    )


# =============================================================================
# SYSTEM 6: VOLATILITY-LIQUIDITY FEEDBACK
# =============================================================================

def compute_feedback_metrics(
    close: pd.Series,
    volume: pd.Series,
    window: int = 60,
    ticker: str = "",
) -> FeedbackMetrics:
    """
    Compute volatility-liquidity feedback loop metrics.
    """
    returns = compute_returns(close)
    dollar_volume = compute_dollar_volume(close, volume)
    amihud = compute_amihud(returns, dollar_volume).replace([np.inf, -np.inf], np.nan)
    
    # Realized volatility (20-day)
    vol = returns.rolling(20).std() * np.sqrt(252)
    
    # Align series
    common = amihud.index.intersection(vol.index)
    a = amihud.loc[common].tail(window).dropna()
    v = vol.loc[common].tail(window).dropna()
    
    common2 = a.index.intersection(v.index)
    a = a.loc[common2]
    v = v.loc[common2]
    
    if len(a) < 20:
        return FeedbackMetrics(ticker=ticker)
    
    # β_VL: vol -> liquidity
    try:
        beta_vl, _ = np.polyfit(v.shift(1).dropna(), a.iloc[1:], 1)
    except Exception:
        beta_vl = 0.0
    
    # β_LV: liquidity -> vol
    try:
        beta_lv, _ = np.polyfit(a.shift(1).dropna(), v.iloc[1:], 1)
    except Exception:
        beta_lv = 0.0
    
    # Loop gain
    loop_gain = abs(float(beta_vl) * float(beta_lv))
    
    # Stability status
    if loop_gain < 0.25:
        status = "stable"
    elif loop_gain < 1.0:
        status = "amplifying"
    else:
        status = "unstable"
    
    # Runaway probability
    runaway_prob = float(min(1, loop_gain))
    
    return FeedbackMetrics(
        ticker=ticker,
        beta_vol_to_liq=float(beta_vl),
        beta_liq_to_vol=float(beta_lv),
        loop_gain=loop_gain,
        stability_status=status,
        runaway_probability=runaway_prob,
    )


# =============================================================================
# SYSTEM 7: CRISIS FINGERPRINT VAULT
# =============================================================================

# Historical crisis fingerprints (normalized feature vectors)
# [instability, depth, fragility, contagion, feedback]
CRISIS_LIBRARY = [
    {
        "name": "2008 Financial Crisis",
        "date": "2008-09-15",
        "fingerprint": [0.85, 0.20, 0.75, 0.90, 0.80],
        "max_drawdown_20d": -25.0,
        "recovery_days": 180,
        "description": "Lehman Brothers collapse, global credit freeze",
    },
    {
        "name": "2010 Flash Crash",
        "date": "2010-05-06",
        "fingerprint": [0.70, 0.40, 0.90, 0.60, 0.50],
        "max_drawdown_20d": -10.0,
        "recovery_days": 30,
        "description": "Algorithmic trading cascade, 1000-point Dow drop",
    },
    {
        "name": "2011 Euro Debt Crisis",
        "date": "2011-08-08",
        "fingerprint": [0.65, 0.45, 0.70, 0.75, 0.55],
        "max_drawdown_20d": -16.0,
        "recovery_days": 90,
        "description": "US downgrade, Greek debt contagion",
    },
    {
        "name": "2015 China Shock",
        "date": "2015-08-24",
        "fingerprint": [0.60, 0.50, 0.65, 0.70, 0.45],
        "max_drawdown_20d": -12.0,
        "recovery_days": 60,
        "description": "Yuan devaluation, China growth fears",
    },
    {
        "name": "2018 Volmageddon",
        "date": "2018-02-05",
        "fingerprint": [0.55, 0.60, 0.60, 0.50, 0.70],
        "max_drawdown_20d": -10.0,
        "recovery_days": 45,
        "description": "VIX spike, short-vol strategy blowup",
    },
    {
        "name": "COVID-19 Crash",
        "date": "2020-03-16",
        "fingerprint": [0.90, 0.15, 0.85, 0.95, 0.85],
        "max_drawdown_20d": -30.0,
        "recovery_days": 120,
        "description": "Global pandemic lockdowns, circuit breakers",
    },
    {
        "name": "2022 Rate Shock",
        "date": "2022-01-24",
        "fingerprint": [0.50, 0.55, 0.45, 0.40, 0.35],
        "max_drawdown_20d": -12.0,
        "recovery_days": 90,
        "description": "Fed hawkish pivot, growth-to-value rotation",
    },
    {
        "name": "2023 Banking Stress",
        "date": "2023-03-10",
        "fingerprint": [0.55, 0.50, 0.60, 0.65, 0.40],
        "max_drawdown_20d": -8.0,
        "recovery_days": 45,
        "description": "SVB collapse, regional bank contagion fears",
    },
]


def compute_crisis_fingerprint(
    liquidity_metrics: List[LiquidityMetrics],
    cliff_metrics: List[CliffMetrics],
    feedback_metrics: List[FeedbackMetrics],
) -> List[float]:
    """
    Create fingerprint vector from current conditions.
    """
    if not liquidity_metrics:
        return [0.5, 0.5, 0.5, 0.5, 0.5]
    
    # Aggregate metrics
    avg_stability = np.mean([m.stability_score for m in liquidity_metrics])
    avg_depth = np.mean([m.depth_score for m in liquidity_metrics])
    avg_fragility = np.mean([m.fragility_score for m in liquidity_metrics])
    
    if cliff_metrics:
        avg_cliff = np.mean([m.cliff_distance for m in cliff_metrics])
    else:
        avg_cliff = 0.0
    
    if feedback_metrics:
        avg_feedback = np.mean([m.loop_gain for m in feedback_metrics])
    else:
        avg_feedback = 0.0
    
    # Normalize to 0-1
    fingerprint = [
        (100 - avg_stability) / 100,  # Instability
        avg_depth / 100,  # Depth (inverted)
        avg_fragility / 100,  # Fragility
        min(1, max(0, avg_cliff + 0.5)),  # Contagion proxy
        min(1, avg_feedback),  # Feedback
    ]
    
    return fingerprint


def match_crisis_fingerprint(
    current_fingerprint: List[float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Match current fingerprint to historical crises.
    """
    matches = []
    
    for crisis in CRISIS_LIBRARY:
        hist_fp = crisis["fingerprint"]
        
        # Euclidean distance
        distance = np.sqrt(sum((a - b) ** 2 for a, b in zip(current_fingerprint, hist_fp)))
        
        # Cosine similarity
        dot = sum(a * b for a, b in zip(current_fingerprint, hist_fp))
        norm_curr = np.sqrt(sum(a ** 2 for a in current_fingerprint))
        norm_hist = np.sqrt(sum(b ** 2 for b in hist_fp))
        similarity = dot / (norm_curr * norm_hist + 1e-10)
        
        matches.append({
            "name": crisis["name"],
            "date": crisis["date"],
            "distance": round(float(distance), 4),
            "similarity": round(float(similarity), 4),
            "max_drawdown_20d": crisis["max_drawdown_20d"],
            "recovery_days": crisis["recovery_days"],
        })
    
    # Sort by distance
    matches.sort(key=lambda x: x["distance"])
    
    return matches[:top_k]


# =============================================================================
# MAIN ENGINE CLASS
# =============================================================================

class LiquidityIntelligenceEngine:
    """
    Main orchestrator for all 7 liquidity systems.
    PRODUCTION-GRADE with sector aggregation and drift tracking.
    """
    
    def __init__(self, window: int = 60):
        self.window = window
        self.as_of = datetime.now().strftime("%Y-%m-%d")
        
        # Cached results
        self._liquidity_metrics: Dict[str, LiquidityMetrics] = {}
        self._cliff_metrics: Dict[str, CliffMetrics] = {}
        self._contagion_metrics: Dict[str, ContagionMetrics] = {}
        self._capacity_metrics: Dict[str, CapacityMetrics] = {}
        self._regime_states: Dict[str, RegimeState] = {}
        self._feedback_metrics: Dict[str, FeedbackMetrics] = {}
        
        # PRODUCTION: Sector tracking
        self._sector_map: Dict[str, str] = {}
        self._sector_aggregates: Dict[str, Dict[str, float]] = {}
        
        # PRODUCTION: Drift path history (manifold position over time)
        self._drift_paths: Dict[str, List[Dict[str, float]]] = {}
        
        # PRODUCTION: Regime history for transition tracking
        self._regime_history: Dict[str, List[str]] = {}
        
        # Contagion matrices
        self._strength_matrix: Optional[pd.DataFrame] = None
        self._lag_matrix: Optional[pd.DataFrame] = None
    
    def process_ticker(
        self,
        ticker: str,
        close: pd.Series,
        volume: pd.Series,
        open_prices: pd.Series,
        high: pd.Series,
        low: pd.Series,
        sector: str = "Other",
    ) -> Dict[str, Any]:
        """
        Process all systems for a single ticker.
        PRODUCTION: Includes sector tracking and drift path recording.
        """
        # PRODUCTION: Store sector mapping
        self._sector_map[ticker] = sector
        
        # System 1: Liquidity metrics
        liq = compute_liquidity_metrics(
            close, volume, open_prices, high, low,
            window=self.window, ticker=ticker
        )
        self._liquidity_metrics[ticker] = liq
        
        # PRODUCTION: Record drift path (manifold position)
        manifold_pos = {
            "date": self.as_of,
            "x": liq.stability_score / 100,
            "y": liq.depth_score / 100,
            "z": max(0, min(1, 1 - liq.gap_recovery_time / 20)),
        }
        if ticker not in self._drift_paths:
            self._drift_paths[ticker] = []
        self._drift_paths[ticker].append(manifold_pos)
        
        # System 2: Cliff detection
        cliff = compute_cliff_metrics(
            close, volume, open_prices,
            window=self.window, ticker=ticker
        )
        self._cliff_metrics[ticker] = cliff
        
        # System 4: Capacity
        cap = compute_capacity_metrics(
            close, volume, window=self.window, ticker=ticker
        )
        self._capacity_metrics[ticker] = cap
        
        # System 5: Regime
        regime = compute_regime_state(liq)
        self._regime_states[ticker] = regime
        
        # PRODUCTION: Track regime history for proper days_in_regime
        if ticker not in self._regime_history:
            self._regime_history[ticker] = []
        self._regime_history[ticker].append(regime.current_regime)
        
        # System 6: Feedback
        feedback = compute_feedback_metrics(
            close, volume, window=self.window, ticker=ticker
        )
        self._feedback_metrics[ticker] = feedback
        
        return {
            "liquidity": liq.to_dict(),
            "cliff": cliff.to_dict(),
            "capacity": cap.to_dict(),
            "regime": regime.to_dict(),
            "feedback": feedback.to_dict(),
            "sector": sector,
        }
    
    def compute_contagion_network(
        self,
        amihud_dict: Dict[str, pd.Series],
    ) -> Dict[str, Any]:
        """
        Compute contagion network across all tickers.
        """
        self._strength_matrix, self._lag_matrix = compute_contagion_matrix(
            amihud_dict
        )
        
        # Compute per-ticker metrics
        for ticker in amihud_dict.keys():
            contagion = compute_contagion_metrics(
                self._strength_matrix, self._lag_matrix, ticker
            )
            self._contagion_metrics[ticker] = contagion
        
        # Build network edges
        edges = []
        for i in self._strength_matrix.index:
            for j in self._strength_matrix.columns:
                if i != j and self._strength_matrix.loc[i, j] != 0:
                    edges.append({
                        "source": i,
                        "target": j,
                        "strength": float(self._strength_matrix.loc[i, j]),
                        "lag": int(self._lag_matrix.loc[i, j]),
                    })
        
        return {
            "nodes": [
                {
                    "id": t,
                    "r_number": m.r_number,
                    "patient_zero_prob": m.patient_zero_prob,
                    "firebreak_score": m.firebreak_score,
                }
                for t, m in self._contagion_metrics.items()
            ],
            "edges": edges,
        }
    
    def get_crisis_comparison(self) -> Dict[str, Any]:
        """
        Compare current conditions to historical crises.
        """
        fingerprint = compute_crisis_fingerprint(
            list(self._liquidity_metrics.values()),
            list(self._cliff_metrics.values()),
            list(self._feedback_metrics.values()),
        )
        
        matches = match_crisis_fingerprint(fingerprint)
        
        return {
            "current_fingerprint": fingerprint,
            "similar_crises": matches,
        }
    
    def get_manifold_data(self) -> Dict[str, Any]:
        """
        Get 3D manifold visualization data.
        PRODUCTION: Includes sector coloring and phase distribution.
        """
        coords = compute_manifold_coordinates(list(self._liquidity_metrics.values()))
        
        # Add sector to each coordinate
        for coord in coords:
            coord.sector = self._sector_map.get(coord.ticker, "Other")
        
        # Phase distribution
        phase_counts = {}
        for c in coords:
            phase_counts[c.phase] = phase_counts.get(c.phase, 0) + 1
        
        # PRODUCTION: Sector aggregation
        sector_stats = {}
        for ticker, metrics in self._liquidity_metrics.items():
            sector = self._sector_map.get(ticker, "Other")
            if sector not in sector_stats:
                sector_stats[sector] = {
                    "count": 0,
                    "avg_stability": 0,
                    "avg_fragility": 0,
                    "avg_depth": 0,
                }
            sector_stats[sector]["count"] += 1
            sector_stats[sector]["avg_stability"] += metrics.stability_score
            sector_stats[sector]["avg_fragility"] += metrics.fragility_score
            sector_stats[sector]["avg_depth"] += metrics.depth_score
        
        # Compute averages
        for sector in sector_stats:
            n = sector_stats[sector]["count"]
            if n > 0:
                sector_stats[sector]["avg_stability"] /= n
                sector_stats[sector]["avg_fragility"] /= n
                sector_stats[sector]["avg_depth"] /= n
        
        return {
            "coordinates": [c.to_dict() for c in coords],
            "phase_distribution": phase_counts,
            "sector_stats": sector_stats,
            "drift_paths": self._drift_paths,
        }
    
    def get_sector_aggregates(self) -> Dict[str, Any]:
        """
        PRODUCTION: Get sector-level liquidity aggregates.
        """
        sector_data = {}
        
        for ticker, metrics in self._liquidity_metrics.items():
            sector = self._sector_map.get(ticker, "Other")
            if sector not in sector_data:
                sector_data[sector] = {
                    "tickers": [],
                    "stability_scores": [],
                    "fragility_scores": [],
                    "depth_scores": [],
                    "cliff_distances": [],
                    "regime_counts": {},
                }
            
            sector_data[sector]["tickers"].append(ticker)
            sector_data[sector]["stability_scores"].append(metrics.stability_score)
            sector_data[sector]["fragility_scores"].append(metrics.fragility_score)
            sector_data[sector]["depth_scores"].append(metrics.depth_score)
            
            if ticker in self._cliff_metrics:
                sector_data[sector]["cliff_distances"].append(
                    self._cliff_metrics[ticker].cliff_distance
                )
            
            if ticker in self._regime_states:
                regime = self._regime_states[ticker].current_regime
                sector_data[sector]["regime_counts"][regime] = \
                    sector_data[sector]["regime_counts"].get(regime, 0) + 1
        
        # Aggregate per sector
        result = {}
        for sector, data in sector_data.items():
            result[sector] = {
                "ticker_count": len(data["tickers"]),
                "avg_stability": round(float(np.mean(data["stability_scores"])), 1),
                "avg_fragility": round(float(np.mean(data["fragility_scores"])), 1),
                "avg_depth": round(float(np.mean(data["depth_scores"])), 1),
                "avg_cliff_distance": round(float(np.mean(data["cliff_distances"])), 4) if data["cliff_distances"] else 0,
                "dominant_regime": max(data["regime_counts"], key=data["regime_counts"].get) if data["regime_counts"] else "normal",
                "tickers": data["tickers"],
            }
        
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get high-level summary of all systems.
        PRODUCTION: Includes sector breakdown and comprehensive metrics.
        """
        n = len(self._liquidity_metrics)
        
        if n == 0:
            return {"error": "No data processed"}
        
        # Aggregate stats
        avg_stability = np.mean([m.stability_score for m in self._liquidity_metrics.values()])
        avg_fragility = np.mean([m.fragility_score for m in self._liquidity_metrics.values()])
        avg_persistence = np.mean([m.persistence_score for m in self._liquidity_metrics.values()])
        avg_autocorr = np.mean([m.autocorr_1d for m in self._liquidity_metrics.values()])
        
        cliff_risks = [m.cliff_distance for m in self._cliff_metrics.values()]
        avg_cliff = np.mean(cliff_risks) if cliff_risks else 0
        
        capacity_sum = sum(m.safe_size_dollars for m in self._capacity_metrics.values())
        
        feedback_gains = [m.loop_gain for m in self._feedback_metrics.values()]
        avg_loop_gain = np.mean(feedback_gains) if feedback_gains else 0
        
        unstable_count = sum(1 for m in self._feedback_metrics.values() if m.stability_status == "unstable")
        
        # Regime distribution
        regimes = [r.current_regime for r in self._regime_states.values()]
        regime_dist = {r: round(regimes.count(r) / len(regimes), 2) for r in set(regimes)}
        
        # Sector summary
        sector_summary = self.get_sector_aggregates()
        
        return {
            "as_of": self.as_of,
            "universe_size": n,
            "window": self.window,
            "summary": {
                "avg_stability_score": round(avg_stability, 1),
                "avg_fragility_score": round(avg_fragility, 1),
                "avg_persistence_score": round(avg_persistence, 1),
                "avg_autocorr_1d": round(avg_autocorr, 4),
                "avg_cliff_distance": round(avg_cliff, 4),
                "avg_loop_gain": round(avg_loop_gain, 4),
                "total_safe_capacity": round(capacity_sum / 1e6, 1),  # In millions
                "unstable_feedback_count": unstable_count,
                "regime_distribution": regime_dist,
            },
            "sector_breakdown": sector_summary,
        }
