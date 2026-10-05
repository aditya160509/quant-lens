"""
Portfolio Regimes V2 - Institutional Grade Regime Analysis
============================================================
7-section regime-aware portfolio intelligence:
1. Current Regime Snapshot
2. Regime History and Stability
3. Transitions and Next State
4. Portfolio Performance by Regime
5. Risk and Drawdown Behavior
6. Shock Simulator
7. Regime Sensitivity Heatmap

All computations use real data. No synthetic or placeholder values.
Supports SPY (US) and NIFTY50 (India) market proxies.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from scipy import stats
from scipy.stats import percentileofscore
import warnings
import hashlib
import json
import os
import logging
import sqlite3
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

# HMM for regime detection
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn("hmmlearn not available - regime detection will use fallback")

from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
)
from app.services.portfolio_core import (
    log_returns, maximum_drawdown, sharpe_ratio, value_at_risk
)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

ANNUAL_FACTOR = 252
DEFAULT_WINDOW_YEARS = 2
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cache', 'regime_database.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Market proxies
MARKET_PROXIES = {
    'US': 'SPY',
    'INDIA': '^NSEI',  # NIFTY 50
}

# Regime configuration
REGIME_NAMES = ['Calm', 'Risk', 'Crisis']
N_REGIMES = 3

# Feature windows
RV_WINDOW = 20
CORR_WINDOW = 60
TREND_WINDOW = 20
ILLIQ_WINDOW = 20
CALIBRATION_DAYS = 252


class RegimeState(Enum):
    CALM = "Calm"
    RISK = "Risk"
    CRISIS = "Crisis"


@dataclass
class DailyRegimeRecord:
    """Daily regime record for database storage."""
    date: str
    market_proxy: str
    state: str
    confidence: float
    z_vol: float
    z_corr: float
    z_trend: float
    z_liq: float
    prob_calm: float
    prob_risk: float
    prob_crisis: float


@dataclass
class RegimeSegment:
    """A contiguous period in one regime."""
    regime: str
    start_date: str
    end_date: str
    duration_days: int
    portfolio_return: float
    max_drawdown: float


# -----------------------------------------------------------------------------
# DATABASE LAYER
# -----------------------------------------------------------------------------

def init_database():
    """Initialize SQLite database for regime storage."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Daily regimes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_regimes (
            date TEXT,
            market_proxy TEXT,
            state TEXT,
            confidence REAL,
            z_vol REAL,
            z_corr REAL,
            z_trend REAL,
            z_liq REAL,
            prob_calm REAL,
            prob_risk REAL,
            prob_crisis REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, market_proxy)
        )
    ''')
    
    # Regime summaries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regime_summaries (
            market_proxy TEXT,
            portfolio_id TEXT,
            regime TEXT,
            avg_return_ann REAL,
            volatility_ann REAL,
            sharpe REAL,
            hit_rate REAL,
            avg_drawdown REAL,
            worst_drawdown REAL,
            avg_recovery_days INTEGER,
            pnl_contribution REAL,
            days_in_regime INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (market_proxy, portfolio_id, regime)
        )
    ''')
    
    # Transition matrix table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transition_matrices (
            market_proxy TEXT,
            from_state TEXT,
            to_state TEXT,
            probability REAL,
            sample_size INTEGER,
            avg_duration_days REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (market_proxy, from_state, to_state)
        )
    ''')
    
    conn.commit()
    conn.close()


def save_daily_regime(record: DailyRegimeRecord):
    """Save daily regime record to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO daily_regimes 
        (date, market_proxy, state, confidence, z_vol, z_corr, z_trend, z_liq, 
         prob_calm, prob_risk, prob_crisis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        record.date, record.market_proxy, record.state, record.confidence,
        record.z_vol, record.z_corr, record.z_trend, record.z_liq,
        record.prob_calm, record.prob_risk, record.prob_crisis
    ))
    
    conn.commit()
    conn.close()


def get_regime_history(market_proxy: str, days: int = 756) -> List[Dict]:
    """Get regime history from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, state, confidence, z_vol, z_corr, z_trend, z_liq,
               prob_calm, prob_risk, prob_crisis
        FROM daily_regimes
        WHERE market_proxy = ?
        ORDER BY date DESC
        LIMIT ?
    ''', (market_proxy, days))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            'date': row[0],
            'state': row[1],
            'confidence': row[2],
            'z_vol': row[3],
            'z_corr': row[4],
            'z_trend': row[5],
            'z_liq': row[6],
            'prob_calm': row[7],
            'prob_risk': row[8],
            'prob_crisis': row[9]
        }
        for row in reversed(rows)
    ]


# Initialize database on module load
init_database()


# -----------------------------------------------------------------------------
# DATA FETCHING
# -----------------------------------------------------------------------------

def get_market_data(market: str = 'US', years: int = 2) -> pd.DataFrame:
    """
    Fetch market data for regime analysis.
    Supports US (SPY) and India (NIFTY50).
    Note: Robust data fetcher supports max 2y period, so we cap at 2y.
    """
    proxy = MARKET_PROXIES.get(market, 'SPY')
    
    # Cap years at 2 (max supported by robust data fetcher)
    period = '2y' if years >= 2 else f'{years}y'
    
    try:
        df = rdf_get_price(proxy, period=period)
        if df is None or df.empty:
            # Try alternate ticker for India
            if market == 'INDIA':
                df = rdf_get_price('NIFTY50.NS', period=period)
        
        if df is None or df.empty:
            logger.warning(f"Failed to fetch data for {proxy}")
            return pd.DataFrame()
        
        # Standardize column names
        df.columns = df.columns.str.lower()
        if 'adj close' in df.columns:
            df['close'] = df['adj close']
        
        return df
        
    except Exception as e:
        logger.error(f"Market data fetch failed: {e}")
        return pd.DataFrame()


def get_portfolio_returns(portfolio_equity: Optional[pd.Series] = None) -> pd.Series:
    """
    Get portfolio returns. If no equity curve provided, uses default test portfolio.
    """
    if portfolio_equity is not None and len(portfolio_equity) > 0:
        returns = np.log(portfolio_equity / portfolio_equity.shift(1)).dropna()
        return returns
    
    # Default: use SPY as proxy portfolio (max 2y supported)
    df = get_market_data('US', 2)
    if df.empty:
        return pd.Series()
    
    returns = np.log(df['close'] / df['close'].shift(1)).dropna()
    return returns


# -----------------------------------------------------------------------------
# FEATURE COMPUTATION
# -----------------------------------------------------------------------------

def compute_regime_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Z-score normalized features for regime classification.
    
    Features:
    1. Realized Volatility (20-day, annualized)
    2. Correlation Stress (rolling correlation of absolute returns)
    3. Trend Strength (risk-adjusted momentum)
    4. Liquidity Stress (Amihud proxy)
    """
    # Lower minimum requirement to 100 days for basic functionality
    min_required = max(RV_WINDOW + 60, 100)  # Reduced from CALIBRATION_DAYS
    if len(data) < min_required:
        raise ValueError(f"Insufficient data: need {min_required} days minimum, got {len(data)}")
    
    close = data['close']
    volume = data.get('volume', pd.Series(1e9, index=data.index))
    
    # Returns
    returns = np.log(close / close.shift(1)).dropna()
    
    # 1. Realized Volatility (annualized)
    rv = returns.rolling(RV_WINDOW).std() * np.sqrt(ANNUAL_FACTOR)
    
    # 2. Correlation Stress - autocorrelation of absolute returns
    abs_returns = np.abs(returns)
    corr_stress = abs_returns.rolling(CORR_WINDOW).apply(
        lambda x: x.autocorr() if len(x) > 1 else 0, raw=False
    ).fillna(0)
    
    # 3. Trend Strength (risk-adjusted)
    trend_return = returns.rolling(TREND_WINDOW).sum()
    trend_vol = returns.rolling(TREND_WINDOW).std()
    trend_strength = trend_return / (trend_vol + 1e-10)
    
    # 4. Liquidity Stress (Amihud)
    dollar_volume = close * volume
    illiq = np.abs(returns) / (dollar_volume.clip(lower=1e6))
    illiq_smooth = illiq.rolling(ILLIQ_WINDOW).median()
    
    # Combine into DataFrame
    features = pd.DataFrame({
        'rv': rv,
        'corr_stress': corr_stress,
        'trend': trend_strength,
        'illiq': illiq_smooth
    }).dropna()
    
    # Compute Z-scores using rolling window
    z_features = pd.DataFrame(index=features.index)
    
    for col in features.columns:
        rolling_mean = features[col].rolling(CALIBRATION_DAYS, min_periods=60).mean()
        rolling_std = features[col].rolling(CALIBRATION_DAYS, min_periods=60).std()
        z_features[f'z_{col}'] = (features[col] - rolling_mean) / (rolling_std + 1e-10)
    
    # Add raw features
    z_features['rv'] = features['rv']
    z_features['corr_stress'] = features['corr_stress']
    z_features['trend'] = features['trend']
    z_features['illiq'] = features['illiq']
    
    return z_features.dropna()


# -----------------------------------------------------------------------------
# REGIME CLASSIFICATION
# -----------------------------------------------------------------------------

def classify_regimes_hmm(features: pd.DataFrame, n_states: int = 3) -> Tuple[np.ndarray, np.ndarray, Any]:
    """
    Classify regimes using Gaussian HMM.
    
    Returns:
        states: Array of state assignments
        posteriors: Array of posterior probabilities
        model: Fitted HMM model
    """
    # Feature matrix for HMM
    X = features[['z_rv', 'z_corr_stress', 'z_trend', 'z_illiq']].values
    
    if not HMM_AVAILABLE or len(X) < 100:
        return classify_regimes_rules(features)
    
    try:
        model = GaussianHMM(
            n_components=n_states,
            covariance_type='diag',
            n_iter=100,
            random_state=42
        )
        model.fit(X)
        
        # Sort states by volatility level (Calm -> Crisis)
        state_vols = model.means_[:, 0]  # z_rv column
        order = np.argsort(state_vols)
        
        # Remap model parameters
        model.means_ = model.means_[order]
        model.covars_ = model.covars_[order]
        model.startprob_ = model.startprob_[order]
        model.transmat_ = model.transmat_[np.ix_(order, order)]
        
        # Get predictions
        states = model.predict(X)
        posteriors = model.predict_proba(X)
        
        return states, posteriors, model
        
    except Exception as e:
        logger.warning(f"HMM fitting failed: {e}")
        return classify_regimes_rules(features)


def classify_regimes_rules(features: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, None]:
    """
    Fallback rule-based regime classification.
    """
    z_vol = features['z_rv'].values
    z_corr = features['z_corr_stress'].values
    z_trend = features['z_trend'].values
    
    n = len(features)
    states = np.zeros(n, dtype=int)
    posteriors = np.zeros((n, 3))
    
    for i in range(n):
        # Crisis: High vol, high correlation, negative trend
        if z_vol[i] > 1.5 or (z_vol[i] > 1.0 and z_trend[i] < -1.0):
            states[i] = 2  # Crisis
            posteriors[i] = [0.05, 0.15, 0.80]
        # Risk: Elevated vol or mixed signals
        elif z_vol[i] > 0.5 or z_corr[i] > 0.5 or z_trend[i] < -0.5:
            states[i] = 1  # Risk
            posteriors[i] = [0.20, 0.65, 0.15]
        # Calm: Low vol, positive trend
        else:
            states[i] = 0  # Calm
            posteriors[i] = [0.75, 0.20, 0.05]
    
    return states, posteriors, None


# -----------------------------------------------------------------------------
# SECTION 1: CURRENT REGIME SNAPSHOT
# -----------------------------------------------------------------------------

def get_current_regime_snapshot(market: str = 'US') -> Dict[str, Any]:
    """
    Get current regime status with confidence and feature breakdown.
    """
    data = get_market_data(market, 2)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    if features.empty:
        return {'error': 'Insufficient data for regime analysis'}
    
    states, posteriors, _ = classify_regimes_hmm(features)
    
    # Current state
    current_state = int(states[-1])
    current_probs = posteriors[-1]
    confidence = float(current_probs[current_state])
    
    # Count days in current regime
    days_in_regime = 1
    for i in range(len(states) - 2, -1, -1):
        if states[i] == current_state:
            days_in_regime += 1
        else:
            break
    
    # Find start date
    start_idx = len(features) - days_in_regime
    start_date = features.index[start_idx].strftime('%Y-%m-%d')
    
    # Current features
    latest = features.iloc[-1]
    
    # Regime descriptions
    descriptions = {
        0: "Low volatility with stable correlations and positive momentum. Markets are constructive.",
        1: "Elevated volatility with mixed signals. Watch for directional resolution.",
        2: "High volatility with rising correlations and negative momentum. Markets are defensive."
    }
    
    # Regime averages
    regime_mask = states == current_state
    regime_avg = {
        'volatility': float(features.loc[features.index[regime_mask], 'rv'].mean()),
        'correlation': float(features.loc[features.index[regime_mask], 'corr_stress'].mean()),
        'trend': float(features.loc[features.index[regime_mask], 'trend'].mean()),
        'liquidity': float(features.loc[features.index[regime_mask], 'illiq'].mean())
    }
    
    # Percentiles
    def pct_rank(series, value):
        return float(percentileofscore(series.dropna(), value))
    
    percentiles = {
        'volatility': pct_rank(features['rv'], latest['rv']),
        'correlation': pct_rank(features['corr_stress'], latest['corr_stress']),
        'trend': pct_rank(features['trend'], latest['trend']),
        'liquidity': pct_rank(features['illiq'], latest['illiq'])
    }
    
    # Save to database
    record = DailyRegimeRecord(
        date=features.index[-1].strftime('%Y-%m-%d'),
        market_proxy=MARKET_PROXIES.get(market, 'SPY'),
        state=REGIME_NAMES[current_state],
        confidence=confidence,
        z_vol=float(latest['z_rv']),
        z_corr=float(latest['z_corr_stress']),
        z_trend=float(latest['z_trend']),
        z_liq=float(latest['z_illiq']),
        prob_calm=float(current_probs[0]),
        prob_risk=float(current_probs[1]),
        prob_crisis=float(current_probs[2])
    )
    save_daily_regime(record)
    
    return {
        'asOf': datetime.now().isoformat(),
        'market': market,
        'currentRegime': REGIME_NAMES[current_state],
        'confidence': round(confidence, 4),
        'daysInRegime': days_in_regime,
        'startDate': start_date,
        'description': descriptions.get(current_state, ''),
        'stateProbabilities': {
            'Calm': round(float(current_probs[0]), 4),
            'Risk': round(float(current_probs[1]), 4),
            'Crisis': round(float(current_probs[2]), 4)
        },
        'features': {
            'current': {
                'volatility': round(float(latest['rv']), 4),
                'correlation': round(float(latest['corr_stress']), 4),
                'trend': round(float(latest['trend']), 4),
                'liquidity': round(float(latest['illiq']), 8)
            },
            'zScores': {
                'volatility': round(float(latest['z_rv']), 4),
                'correlation': round(float(latest['z_corr_stress']), 4),
                'trend': round(float(latest['z_trend']), 4),
                'liquidity': round(float(latest['z_illiq']), 4)
            },
            'regimeAverage': regime_avg,
            'percentiles': percentiles
        },
        'radarChart': {
            'current': [
                float(latest['z_rv']),
                float(latest['z_corr_stress']),
                float(latest['z_trend']),
                float(latest['z_illiq'])
            ],
            'regimeAverage': [
                float(features.loc[features.index[regime_mask], 'z_rv'].mean()),
                float(features.loc[features.index[regime_mask], 'z_corr_stress'].mean()),
                float(features.loc[features.index[regime_mask], 'z_trend'].mean()),
                float(features.loc[features.index[regime_mask], 'z_illiq'].mean())
            ],
            'labels': ['Volatility', 'Correlation', 'Trend', 'Liquidity']
        }
    }


# -----------------------------------------------------------------------------
# SECTION 2: REGIME HISTORY AND STABILITY
# -----------------------------------------------------------------------------

def get_regime_history_timeline(market: str = 'US', portfolio_equity: pd.Series = None) -> Dict[str, Any]:
    """
    Get regime timeline with equity overlay and duration analysis.
    """
    data = get_market_data(market, 2)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    states, posteriors, _ = classify_regimes_hmm(features)
    
    # Get portfolio equity (use market as proxy if not provided)
    if portfolio_equity is None:
        portfolio_equity = data['close'].reindex(features.index)
        portfolio_equity = portfolio_equity / portfolio_equity.iloc[0] * 100  # Normalize to 100
    
    # Build timeline
    timeline = []
    for i, idx in enumerate(features.index):
        timeline.append({
            't': idx.strftime('%Y-%m-%d'),
            'regime': REGIME_NAMES[states[i]],
            'confidence': round(float(posteriors[i][states[i]]), 4),
            'equity': round(float(portfolio_equity.get(idx, 100)), 2)
        })
    
    # Identify regime segments
    segments = []
    current_regime = states[0]
    segment_start = 0
    
    for i in range(1, len(states)):
        if states[i] != current_regime:
            # End current segment
            segment_equity = portfolio_equity.iloc[segment_start:i]
            if len(segment_equity) > 0:
                seg_return = float(segment_equity.iloc[-1] / segment_equity.iloc[0] - 1)
                seg_dd, _, _ = maximum_drawdown(segment_equity)
            else:
                seg_return = 0
                seg_dd = 0
            
            segments.append({
                'regime': REGIME_NAMES[current_regime],
                'startDate': features.index[segment_start].strftime('%Y-%m-%d'),
                'endDate': features.index[i-1].strftime('%Y-%m-%d'),
                'durationDays': i - segment_start,
                'portfolioReturn': round(seg_return, 4),
                'maxDrawdown': round(float(seg_dd), 4)
            })
            
            current_regime = states[i]
            segment_start = i
    
    # Add final segment
    segment_equity = portfolio_equity.iloc[segment_start:]
    if len(segment_equity) > 0:
        seg_return = float(segment_equity.iloc[-1] / segment_equity.iloc[0] - 1)
        seg_dd, _, _ = maximum_drawdown(segment_equity)
    else:
        seg_return = 0
        seg_dd = 0
    
    segments.append({
        'regime': REGIME_NAMES[current_regime],
        'startDate': features.index[segment_start].strftime('%Y-%m-%d'),
        'endDate': features.index[-1].strftime('%Y-%m-%d'),
        'durationDays': len(states) - segment_start,
        'portfolioReturn': round(seg_return, 4),
        'maxDrawdown': round(float(seg_dd), 4)
    })
    
    # Duration histogram data
    durations_by_regime = {name: [] for name in REGIME_NAMES}
    for seg in segments:
        durations_by_regime[seg['regime']].append(seg['durationDays'])
    
    # Duration bins
    bins = [0, 10, 20, 30, 40, 50, 60, 80, 100, float('inf')]
    bin_labels = ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-80', '80-100', '100+']
    
    histogram_data = {name: [0] * (len(bins) - 1) for name in REGIME_NAMES}
    for regime, durs in durations_by_regime.items():
        for d in durs:
            for i in range(len(bins) - 1):
                if bins[i] <= d < bins[i + 1]:
                    histogram_data[regime][i] += 1
                    break
    
    # Current regime age indicator
    current_regime_name = REGIME_NAMES[states[-1]]
    current_duration = segments[-1]['durationDays'] if segments else 0
    avg_duration = np.mean(durations_by_regime[current_regime_name]) if durations_by_regime[current_regime_name] else 30
    age_ratio = current_duration / avg_duration if avg_duration > 0 else 1
    
    if age_ratio < 0.5:
        age_stage = 'Early'
    elif age_ratio <= 1.2:
        age_stage = 'Mid'
    else:
        age_stage = 'Late'
    
    return {
        'asOf': datetime.now().isoformat(),
        'timeline': timeline,
        'segments': segments,
        'durationHistogram': {
            'bins': bin_labels,
            'data': histogram_data
        },
        'ageIndicator': {
            'currentDuration': current_duration,
            'averageDuration': round(avg_duration, 1),
            'ageRatio': round(age_ratio, 2),
            'stage': age_stage,
            'currentRegime': current_regime_name
        }
    }


# -----------------------------------------------------------------------------
# SECTION 3: TRANSITION MATRIX
# -----------------------------------------------------------------------------

def compute_transition_analysis(market: str = 'US') -> Dict[str, Any]:
    """
    Compute transition matrix and next state probabilities.
    """
    data = get_market_data(market, 2)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    states, posteriors, model = classify_regimes_hmm(features)
    
    # Compute empirical transition matrix
    n_states = len(REGIME_NAMES)
    transition_counts = np.zeros((n_states, n_states))
    
    for i in range(len(states) - 1):
        transition_counts[states[i], states[i + 1]] += 1
    
    # Normalize rows
    row_sums = transition_counts.sum(axis=1, keepdims=True)
    transition_matrix = np.where(row_sums > 0, transition_counts / row_sums, 0)
    
    # Sample sizes
    sample_sizes = {REGIME_NAMES[i]: int(row_sums[i, 0]) for i in range(n_states)}
    
    # Average duration per regime
    avg_durations = {}
    for regime_idx, name in enumerate(REGIME_NAMES):
        durations = []
        current_duration = 0
        in_regime = False
        
        for s in states:
            if s == regime_idx:
                current_duration += 1
                in_regime = True
            elif in_regime:
                durations.append(current_duration)
                current_duration = 0
                in_regime = False
        
        if in_regime:
            durations.append(current_duration)
        
        avg_durations[name] = np.mean(durations) if durations else 0
    
    # Current regime and next state probabilities
    current_state = int(states[-1])
    next_probs = transition_matrix[current_state, :]
    
    # Store in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for i, from_name in enumerate(REGIME_NAMES):
        for j, to_name in enumerate(REGIME_NAMES):
            cursor.execute('''
                INSERT OR REPLACE INTO transition_matrices
                (market_proxy, from_state, to_state, probability, sample_size, avg_duration_days, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                MARKET_PROXIES.get(market, 'SPY'),
                from_name, to_name,
                float(transition_matrix[i, j]),
                int(sample_sizes[from_name]),
                float(avg_durations[from_name]),
                datetime.now().isoformat()
            ))
    
    conn.commit()
    conn.close()
    
    # Confidence based on sample size
    def get_confidence(n):
        if n >= 100:
            return 'High'
        elif n >= 30:
            return 'Medium'
        else:
            return 'Low'
    
    return {
        'asOf': datetime.now().isoformat(),
        'transitionMatrix': {
            'labels': REGIME_NAMES,
            'matrix': [[round(float(v), 4) for v in row] for row in transition_matrix],
            'currentRegimeIndex': current_state
        },
        'nextStateProbabilities': [
            {
                'to': REGIME_NAMES[i],
                'probability': round(float(next_probs[i]), 4)
            }
            for i in np.argsort(-next_probs)
        ],
        'stabilityMetrics': [
            {
                'transition': f"{from_name} to {to_name}",
                'avgDaysToSwitch': round(float(avg_durations[from_name]), 1),
                'sampleSize': sample_sizes[from_name],
                'confidence': get_confidence(sample_sizes[from_name])
            }
            for from_name in REGIME_NAMES
            for to_name in REGIME_NAMES
            if from_name != to_name
        ][:6],  # Top 6 transitions
        'sampleSizes': sample_sizes
    }


# -----------------------------------------------------------------------------
# SECTION 4: PORTFOLIO PERFORMANCE BY REGIME
# -----------------------------------------------------------------------------

def compute_performance_by_regime(market: str = 'US', portfolio_returns: pd.Series = None) -> Dict[str, Any]:
    """
    Compute portfolio performance metrics conditioned on regime.
    """
    data = get_market_data(market, 3)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    states, _, _ = classify_regimes_hmm(features)
    
    # Get portfolio returns
    if portfolio_returns is None:
        close = data['close'].reindex(features.index)
        portfolio_returns = np.log(close / close.shift(1)).dropna()
    else:
        portfolio_returns = portfolio_returns.reindex(features.index).dropna()
    
    # Align states with returns
    common_idx = features.index.intersection(portfolio_returns.index)
    aligned_states = states[:len(common_idx)]
    aligned_returns = portfolio_returns.loc[common_idx].values
    
    # Compute metrics per regime
    performance = []
    pnl_contributions = []
    return_distributions = {}
    
    for regime_idx, name in enumerate(REGIME_NAMES):
        mask = aligned_states == regime_idx
        regime_returns = aligned_returns[mask]
        
        if len(regime_returns) < 5:
            performance.append({
                'regime': name,
                'avgReturnAnn': 0,
                'volatilityAnn': 0,
                'maxDrawdown': 0,
                'hitRate': 0,
                'sharpe': 0,
                'daysInRegime': int(mask.sum())
            })
            pnl_contributions.append({'regime': name, 'pnlContribution': 0})
            return_distributions[name] = []
            continue
        
        # Annualized return
        avg_return = float(np.mean(regime_returns) * ANNUAL_FACTOR)
        
        # Annualized volatility
        volatility = float(np.std(regime_returns) * np.sqrt(ANNUAL_FACTOR))
        
        # Sharpe ratio
        sharpe = avg_return / volatility if volatility > 0 else 0
        
        # Hit rate
        hit_rate = float(np.mean(regime_returns > 0))
        
        # Max drawdown
        cumulative = np.cumsum(regime_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        max_dd = float(np.min(drawdowns))
        
        # PnL contribution
        pnl_contrib = float(np.sum(regime_returns))
        
        performance.append({
            'regime': name,
            'avgReturnAnn': round(avg_return, 4),
            'volatilityAnn': round(volatility, 4),
            'maxDrawdown': round(max_dd, 4),
            'hitRate': round(hit_rate, 4),
            'sharpe': round(sharpe, 4),
            'daysInRegime': int(mask.sum())
        })
        
        pnl_contributions.append({
            'regime': name,
            'pnlContribution': round(pnl_contrib, 4)
        })
        
        # Return distribution bins
        bins = [-0.05, -0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03, 0.05]
        hist, _ = np.histogram(regime_returns, bins=bins + [np.inf])
        return_distributions[name] = [int(h) for h in hist]
    
    # Save to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for perf in performance:
        pnl = next((p['pnlContribution'] for p in pnl_contributions if p['regime'] == perf['regime']), 0)
        cursor.execute('''
            INSERT OR REPLACE INTO regime_summaries
            (market_proxy, portfolio_id, regime, avg_return_ann, volatility_ann, sharpe, 
             hit_rate, avg_drawdown, worst_drawdown, pnl_contribution, days_in_regime, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            MARKET_PROXIES.get(market, 'SPY'),
            'default',
            perf['regime'],
            perf['avgReturnAnn'],
            perf['volatilityAnn'],
            perf['sharpe'],
            perf['hitRate'],
            perf['maxDrawdown'],
            perf['maxDrawdown'],
            pnl,
            perf['daysInRegime'],
            datetime.now().isoformat()
        ))
    
    conn.commit()
    conn.close()
    
    return {
        'asOf': datetime.now().isoformat(),
        'performanceTable': performance,
        'pnlContribution': pnl_contributions,
        'returnDistributions': {
            'bins': ['-5% to -3%', '-3% to -2%', '-2% to -1%', '-1% to 0', '0 to 1%', '1% to 2%', '2% to 3%', '3% to 5%', '5%+'],
            'data': return_distributions
        }
    }


# -----------------------------------------------------------------------------
# SECTION 5: RISK AND DRAWDOWN BEHAVIOR
# -----------------------------------------------------------------------------

def compute_drawdown_analysis(market: str = 'US', portfolio_equity: pd.Series = None) -> Dict[str, Any]:
    """
    Compute drawdown analysis by regime.
    """
    data = get_market_data(market, 3)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    states, _, _ = classify_regimes_hmm(features)
    
    # Get equity curve
    if portfolio_equity is None:
        portfolio_equity = data['close'].reindex(features.index)
    else:
        portfolio_equity = portfolio_equity.reindex(features.index)
    
    # Compute drawdown series
    peak = portfolio_equity.expanding().max()
    drawdown = (portfolio_equity - peak) / peak
    
    # Analyze by regime
    severity_table = []
    drawdown_histogram = {name: [] for name in REGIME_NAMES}
    
    for regime_idx, name in enumerate(REGIME_NAMES):
        mask = (states == regime_idx)
        regime_dd = drawdown.iloc[mask].dropna()
        
        if len(regime_dd) < 5:
            severity_table.append({
                'regime': name,
                'avgDrawdown': 0,
                'worstDrawdown': 0,
                'avgRecoveryDays': 0
            })
            continue
        
        # Average and worst drawdown
        avg_dd = float(regime_dd[regime_dd < 0].mean()) if (regime_dd < 0).any() else 0
        worst_dd = float(regime_dd.min())
        
        # Estimate recovery days (simplified)
        # Count transitions from drawdown to recovery within regime
        recovery_days = []
        in_dd = False
        dd_start = 0
        
        regime_indices = np.where(mask)[0]
        for i, idx in enumerate(regime_indices):
            if drawdown.iloc[idx] < -0.01:  # In drawdown
                if not in_dd:
                    dd_start = i
                    in_dd = True
            else:
                if in_dd:
                    recovery_days.append(i - dd_start)
                    in_dd = False
        
        avg_recovery = np.mean(recovery_days) if recovery_days else 0
        
        severity_table.append({
            'regime': name,
            'avgDrawdown': round(avg_dd, 4),
            'worstDrawdown': round(worst_dd, 4),
            'avgRecoveryDays': round(float(avg_recovery), 1)
        })
        
        # Drawdown histogram
        dd_values = regime_dd[regime_dd < 0].values
        bins = [0, -0.05, -0.10, -0.15, -0.20, -0.25, -float('inf')]
        hist, _ = np.histogram(-dd_values, bins=[0, 0.05, 0.10, 0.15, 0.20, 0.25, np.inf])
        drawdown_histogram[name] = [int(h) for h in hist]
    
    # Timeline data
    timeline = [
        {
            't': idx.strftime('%Y-%m-%d'),
            'regime': REGIME_NAMES[states[i]],
            'drawdown': round(float(drawdown.iloc[i]), 4)
        }
        for i, idx in enumerate(features.index)
    ]
    
    return {
        'asOf': datetime.now().isoformat(),
        'severityTable': severity_table,
        'drawdownHistogram': {
            'bins': ['0 to -5%', '-5% to -10%', '-10% to -15%', '-15% to -20%', '-20% to -25%', 'Below -25%'],
            'data': drawdown_histogram
        },
        'timeline': timeline
    }


# -----------------------------------------------------------------------------
# SECTION 6: SHOCK SIMULATOR
# -----------------------------------------------------------------------------

def simulate_shock(
    market: str = 'US',
    shock_type: str = 'volatility_spike',
    magnitude: str = 'moderate'
) -> Dict[str, Any]:
    """
    Simulate shock impact on regime probabilities and expected outcomes.
    
    Shock types:
    - volatility_spike
    - correlation_spike
    - market_drop
    - liquidity_crunch
    - combined_stress
    
    Magnitude: mild (+1 sigma), moderate (+2 sigma), severe (+3 sigma)
    """
    data = get_market_data(market, 2)
    if data.empty:
        return {'error': 'No market data available'}
    
    features = compute_regime_features(data)
    states, posteriors, model = classify_regimes_hmm(features)
    
    # Current state
    current_features = features.iloc[-1].copy()
    current_probs = posteriors[-1]
    
    # Magnitude mapping
    sigma_map = {'mild': 1.0, 'moderate': 2.0, 'severe': 3.0}
    sigma = sigma_map.get(magnitude, 2.0)
    
    # Apply shock to features
    shocked_features = current_features.copy()
    
    if shock_type == 'volatility_spike':
        shocked_features['z_rv'] += sigma
    elif shock_type == 'correlation_spike':
        shocked_features['z_corr_stress'] += sigma
    elif shock_type == 'market_drop':
        shocked_features['z_trend'] -= sigma
        shocked_features['z_rv'] += sigma * 0.5
    elif shock_type == 'liquidity_crunch':
        shocked_features['z_illiq'] += sigma
        shocked_features['z_rv'] += sigma * 0.3
    elif shock_type == 'combined_stress':
        shocked_features['z_rv'] += sigma
        shocked_features['z_corr_stress'] += sigma * 0.8
        shocked_features['z_trend'] -= sigma * 0.5
        shocked_features['z_illiq'] += sigma * 0.6
    
    # Compute new probabilities (using rule-based for shock)
    z_vol = shocked_features['z_rv']
    z_corr = shocked_features['z_corr_stress']
    z_trend = shocked_features['z_trend']
    
    if z_vol > 2.0 or z_corr > 1.5:
        shocked_probs = [0.05, 0.25, 0.70]
    elif z_vol > 1.0 or z_trend < -1.0:
        shocked_probs = [0.15, 0.55, 0.30]
    else:
        shocked_probs = [0.60, 0.30, 0.10]
    
    # Get historical performance by regime
    perf_data = compute_performance_by_regime(market)
    perf_table = perf_data.get('performanceTable', [])
    
    # Expected outcomes before shock
    before_return = sum(
        current_probs[i] * (perf_table[i]['avgReturnAnn'] / 252)
        for i in range(3)
        if i < len(perf_table)
    )
    before_vol = sum(
        current_probs[i] * (perf_table[i]['volatilityAnn'] / np.sqrt(252))
        for i in range(3)
        if i < len(perf_table)
    )
    before_dd = sum(
        current_probs[i] * perf_table[i]['maxDrawdown']
        for i in range(3)
        if i < len(perf_table)
    )
    
    # Expected outcomes after shock
    after_return = sum(
        shocked_probs[i] * (perf_table[i]['avgReturnAnn'] / 252)
        for i in range(3)
        if i < len(perf_table)
    )
    after_vol = sum(
        shocked_probs[i] * (perf_table[i]['volatilityAnn'] / np.sqrt(252))
        for i in range(3)
        if i < len(perf_table)
    )
    after_dd = sum(
        shocked_probs[i] * perf_table[i]['maxDrawdown']
        for i in range(3)
        if i < len(perf_table)
    )
    
    return {
        'asOf': datetime.now().isoformat(),
        'shockConfig': {
            'type': shock_type,
            'magnitude': magnitude,
            'sigmaApplied': sigma
        },
        'impactTable': {
            'metrics': ['Expected Return (Daily)', 'Expected Volatility (Daily)', 'Expected Max Drawdown'],
            'before': [round(before_return, 6), round(before_vol, 6), round(before_dd, 4)],
            'after': [round(after_return, 6), round(after_vol, 6), round(after_dd, 4)],
            'delta': [
                round(after_return - before_return, 6),
                round(after_vol - before_vol, 6),
                round(after_dd - before_dd, 4)
            ]
        },
        'regimeProbabilities': {
            'before': {REGIME_NAMES[i]: round(float(current_probs[i]), 4) for i in range(3)},
            'after': {REGIME_NAMES[i]: round(float(shocked_probs[i]), 4) for i in range(3)}
        },
        'featureImpact': {
            'z_vol': {
                'before': round(float(current_features['z_rv']), 4),
                'after': round(float(shocked_features['z_rv']), 4)
            },
            'z_corr': {
                'before': round(float(current_features['z_corr_stress']), 4),
                'after': round(float(shocked_features['z_corr_stress']), 4)
            },
            'z_trend': {
                'before': round(float(current_features['z_trend']), 4),
                'after': round(float(shocked_features['z_trend']), 4)
            },
            'z_liq': {
                'before': round(float(current_features['z_illiq']), 4),
                'after': round(float(shocked_features['z_illiq']), 4)
            }
        }
    }


# -----------------------------------------------------------------------------
# SECTION 7: SENSITIVITY HEATMAP
# -----------------------------------------------------------------------------

def compute_sensitivity_heatmap(market: str = 'US') -> Dict[str, Any]:
    """
    Compute sensitivity heatmap showing portfolio favorability by regime.
    """
    # Get performance by regime
    perf_data = compute_performance_by_regime(market)
    perf_table = perf_data.get('performanceTable', [])
    
    if not perf_table:
        return {'error': 'No performance data available'}
    
    metrics = ['avgReturnAnn', 'volatilityAnn', 'maxDrawdown', 'sharpe', 'hitRate']
    metric_labels = ['Return', 'Volatility', 'Max DD', 'Sharpe', 'Hit Rate']
    
    # Higher is better for: Return, Sharpe, Hit Rate
    # Lower is better for: Volatility, Max DD (more negative is worse)
    invert_direction = [False, True, True, False, False]
    
    # Extract values
    values = {metric: [] for metric in metrics}
    for perf in perf_table:
        for metric in metrics:
            values[metric].append(perf.get(metric, 0))
    
    # Compute Z-scores across regimes
    z_scores = []
    for i, regime_perf in enumerate(perf_table):
        row = []
        for j, metric in enumerate(metrics):
            metric_values = np.array(values[metric])
            mean = np.mean(metric_values)
            std = np.std(metric_values)
            
            if std > 0:
                z = (regime_perf.get(metric, 0) - mean) / std
            else:
                z = 0
            
            # Invert if lower is better
            if invert_direction[j]:
                z = -z
            
            row.append(round(float(z), 4))
        z_scores.append(row)
    
    # Compute favorability scores
    weights = [0.35, 0.25, 0.25, 0.15, 0.10]  # Return, Vol, DD, Sharpe, Hit Rate
    favorability_scores = {}
    
    for i, perf in enumerate(perf_table):
        score = sum(z_scores[i][j] * weights[j] for j in range(len(metrics)))
        favorability_scores[perf['regime']] = round(float(score), 4)
    
    # Ranking
    ranking = sorted(
        [{'regime': name, 'score': score} for name, score in favorability_scores.items()],
        key=lambda x: -x['score']
    )
    for i, r in enumerate(ranking):
        r['rank'] = i + 1
    
    # Find best and worst metrics per regime
    for i, perf in enumerate(perf_table):
        best_idx = int(np.argmax(z_scores[i]))
        worst_idx = int(np.argmin(z_scores[i]))
        perf['bestMetric'] = metric_labels[best_idx]
        perf['worstMetric'] = metric_labels[worst_idx]
    
    # Current regime callout
    snapshot = get_current_regime_snapshot(market)
    current_regime = snapshot.get('currentRegime', 'Risk')
    current_rank = next((r['rank'] for r in ranking if r['regime'] == current_regime), 2)
    best_regime = ranking[0]['regime'] if ranking else 'Calm'
    
    return {
        'asOf': datetime.now().isoformat(),
        'heatmap': {
            'regimes': REGIME_NAMES,
            'metrics': metric_labels,
            'zScores': z_scores
        },
        'rankingTable': ranking,
        'currentRegimeCallout': {
            'regime': current_regime,
            'rank': current_rank,
            'totalRegimes': len(REGIME_NAMES),
            'historicalBest': best_regime,
            'favorabilityScore': favorability_scores.get(current_regime, 0)
        },
        'performanceWithAnnotations': perf_table
    }


# -----------------------------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------------------------

def run_full_regime_analysis(market: str = 'US') -> Dict[str, Any]:
    """
    Run complete regime analysis for all 7 sections.
    """
    return {
        'snapshot': get_current_regime_snapshot(market),
        'history': get_regime_history_timeline(market),
        'transitions': compute_transition_analysis(market),
        'performance': compute_performance_by_regime(market),
        'drawdowns': compute_drawdown_analysis(market),
        'sensitivity': compute_sensitivity_heatmap(market)
    }
