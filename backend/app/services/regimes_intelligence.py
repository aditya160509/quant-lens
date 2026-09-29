"""
Regimes Crown Engine - Market Structural Stability Analysis
============================================================
7 institutional primitives for structural stability monitoring:
1. Structural Integrity Index
2. Probability Mass Flow Engine (HMM)
3. Reflexive Pressure & Denial Index
4. Liquidity & Leverage Fragility Surface
5. Feedback Loop Closure Monitor
6. Nonlinearity Proximity & Break Threshold
7. Collapse State Governor

All computations from unified state vector. No synthetic data ever.
Uses robust_data_fetcher for centralized, rate-limited data access.
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

logger = logging.getLogger(__name__)

# HMM for regime detection
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn("hmmlearn not available - regime detection will use fallback")

# Use robust data fetcher instead of yfinance directly
from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
    Ticker as RDFTicker
)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

ANNUAL_FACTOR = 252
DEFAULT_NODES = ['TLT', 'LQD', 'UUP']
DEFAULT_BENCHMARK = 'SPY'
DEFAULT_WINDOW_YEARS = 2
CACHE_DIR = os.path.join(os.path.dirname(__file__), '.regime_cache')
CACHE_TTL_MARKET_HOURS = 6 * 3600  # 6 hours
CACHE_TTL_CLOSED = 24 * 3600  # 24 hours

# Math constants
EWMA_LAMBDA = 0.94
RV_WINDOWS = [20, 60]
VOV_WINDOW = 20
ILLIQ_WINDOW = 20
CORR_WINDOW = 60
CALIBRATION_DAYS = 252
HMM_STATES = 4
HMM_TRAIN_DAYS = 756  # 3 years
LOOP_WINDOW = 60
LOOP_LAG_MAX = 5
BREAK_SIM_HORIZON = 20
BREAK_SIM_PATHS = 500
BREAK_SIM_BLOCK_SIZE = 5
SHOCK_GRID = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]

# Governor weights (sum to 1)
GOVERNOR_WEIGHTS = {
    'integrity': 0.18,
    'mass_vel': 0.12,
    'entropy': 0.10,
    'reflex_denial': 0.15,
    'fragility': 0.15,
    'amplification': 0.10,
    'nonlinearity': 0.20
}

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def sanitize_float(val, default=0.0):
    """Sanitize float value for JSON serialization."""
    if val is None:
        return default
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def sanitize_dict(d, default=0.0):
    """Recursively sanitize a dictionary for JSON serialization."""
    if isinstance(d, dict):
        return {k: sanitize_dict(v, default) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(item, default) for item in d]
    elif isinstance(d, (float, np.float64, np.float32)):
        return sanitize_float(d, default)
    elif isinstance(d, (np.int64, np.int32)):
        return int(d)
    else:
        return d

# -----------------------------------------------------------------------------
# DATA LAYER - Fetching, Caching, Alignment (using robust_data_fetcher)
# -----------------------------------------------------------------------------

def _get_cache_key(symbol: str, start: str, end: str, vendor: str = 'yahoo') -> str:
    """Generate cache key for data request."""
    key_str = f"{symbol}_{start}_{end}_{vendor}_daily"
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cache_path(cache_key: str) -> str:
    """Get file path for cached data."""
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def _is_cache_valid(cache_path: str) -> bool:
    """Check if cached data is still valid based on TTL."""
    if not os.path.exists(cache_path):
        return False
    
    mtime = os.path.getmtime(cache_path)
    age = datetime.now().timestamp() - mtime
    
    # Use longer TTL if market is closed (weekend or after hours)
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    hour = now.hour
    is_market_hours = 9 <= hour < 16 and not is_weekend
    
    ttl = CACHE_TTL_MARKET_HOURS if is_market_hours else CACHE_TTL_CLOSED
    return age < ttl


def _fetch_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV data using DataEngine (Parquet) with RDF fallback."""
    from app.services.data_engine import engine
    try:
        # 1. Try Parquet-Native Engine FIRST
        # Calculate lookback from start/end
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        days = (datetime.now() - start_dt).days + 30
        
        df = engine.get_full_ohlcv(symbol, lookback_days=days)
        
        # 2. Fallback to RobustDataFetcher
        if df.empty:
            logger.info(f"[Regime] Parquet miss for {symbol}, falling back to RDF")
            df = rdf_get_price(symbol, period="5y")
            
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Filter by date range
        df.index = pd.to_datetime(df.index)
        if hasattr(df.index, 'tz_localize'):
            df.index = df.index.tz_localize(None)
            
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        # Mapping for Regime compatibility
        df = df.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low',
            'Close': 'close', 'Volume': 'volume'
        })
        
        cols = ['open', 'high', 'low', 'close', 'volume']
        available = [c for c in cols if c in df.columns]
        return df[available]
    except Exception as e:
        warnings.warn(f"Fetch failed for {symbol}: {e}")
        return pd.DataFrame()


def _fetch_stooq(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fallback: Fetch from Stooq."""
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&d1={start.replace('-','')}&d2={end.replace('-','')}"
        df = pd.read_csv(url)
        if df.empty or 'Date' not in df.columns:
            return pd.DataFrame()
        
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df = df.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low',
            'Close': 'close', 'Volume': 'volume'
        })
        return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        warnings.warn(f"Stooq fetch failed for {symbol}: {e}")
        return pd.DataFrame()


def get_ohlcv_data(
    symbol: str,
    start: str,
    end: str,
    force_refresh: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fetch OHLCV data with caching and fallback.
    Returns (DataFrame, metadata).
    """
    cache_key = _get_cache_key(symbol, start, end)
    cache_path = _get_cache_path(cache_key)
    
    metadata = {
        'seriesId': f"ohlcv_{symbol}_{start}_{end}",
        'symbol': symbol,
        'vendor': 'yahoo',
        'retrievedAt': datetime.now().isoformat(),
        'stalenessSec': 0,
        'missingPct': 0.0,
        'transformPipeline': 'raw',
        'calendar': 'US_EQUITY'
    }
    
    # Try cache first
    if not force_refresh and _is_cache_valid(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            df = pd.DataFrame(cached['data'])
            df.index = pd.to_datetime(df.index)
            metadata['vendor'] = cached.get('vendor', 'yahoo')
            metadata['retrievedAt'] = cached.get('retrievedAt', metadata['retrievedAt'])
            mtime = os.path.getmtime(cache_path)
            metadata['stalenessSec'] = int(datetime.now().timestamp() - mtime)
            return df, metadata
        except Exception:
            pass
    
    # Fetch fresh data - try Yahoo first
    df = _fetch_yahoo(symbol, start, end)
    metadata['vendor'] = 'yahoo'
    
    # Fallback to Stooq
    if df.empty:
        df = _fetch_stooq(symbol, start, end)
        metadata['vendor'] = 'stooq'
    
    if df.empty:
        metadata['missingPct'] = 100.0
        return pd.DataFrame(), metadata
    
    # Calculate missing percentage
    expected_days = pd.bdate_range(start, end).size
    actual_days = len(df)
    metadata['missingPct'] = round(100 * (1 - actual_days / expected_days), 2) if expected_days > 0 else 0
    
    # Cache the data - convert index to string for JSON serialization
    try:
        # Reset index to string for serialization
        df_for_cache = df.copy()
        df_for_cache.index = df_for_cache.index.strftime('%Y-%m-%d')
        cache_data = {
            'data': df_for_cache.to_dict(),
            'vendor': metadata['vendor'],
            'retrievedAt': metadata['retrievedAt']
        }
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        warnings.warn(f"Cache write failed: {e}")
    
    return df, metadata


def get_aligned_universe(
    benchmark: str,
    nodes: List[str],
    window_years: int,
    force_refresh: bool = False
) -> Tuple[Dict[str, pd.DataFrame], List[Dict], Dict[str, Any]]:
    """
    Fetch and align all series to common trading calendar.
    Returns (bars_by_symbol, evidence_list, quality_dict).
    """
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=window_years * 365 + 50)).strftime('%Y-%m-%d')
    
    all_symbols = [benchmark] + nodes
    bars = {}
    evidence = []
    total_missing = 0
    warnings_list = []
    
    for symbol in all_symbols:
        df, meta = get_ohlcv_data(symbol, start_date, end_date, force_refresh)
        if df.empty:
            warnings_list.append(f"{symbol}: UNAVAILABLE")
            continue
        bars[symbol] = df
        evidence.append(meta)
        total_missing += meta['missingPct']
    
    # Align to common index - USE BENCHMARK CALENDAR (Solution 1: Alignment Fix)
    if bars and benchmark in bars:
        main_index = bars[benchmark].index
        for symbol in bars:
            # Reindex to benchmark calendar and propagate last known value 
            # This prevents deleting days when nodes (like US bonds) haven't traded but benchmark has.
            bars[symbol] = bars[symbol].reindex(main_index).ffill().bfill()
    
    quality = {
        'missingPct': round(total_missing / len(all_symbols), 2) if all_symbols else 100,
        'stalenessSec': max([e.get('stalenessSec', 0) for e in evidence]) if evidence else 0,
        'warnings': warnings_list,
        'alignmentMethod': 'benchmark_reindex_ffill'
    }
    
    return bars, evidence, quality


# -----------------------------------------------------------------------------
# MATH PRIMITIVES - Core Building Blocks
# -----------------------------------------------------------------------------

def compute_log_returns(close: pd.Series) -> pd.Series:
    """r_t = ln(c_t / c_{t-1})"""
    return np.log(close / close.shift(1))


def compute_realized_volatility(returns: pd.Series, window: int = 20) -> pd.Series:
    """RV_w(t) = sqrt(252) * stdev(r_{t-w+1..t})"""
    return np.sqrt(ANNUAL_FACTOR) * returns.rolling(window).std()


def compute_ewma_volatility(returns: pd.Series, lambda_: float = EWMA_LAMBDA) -> pd.Series:
    """EWMA volatility with decay factor lambda."""
    var = returns.iloc[:20].var()
    ewma_var = [var]
    
    for r in returns.iloc[20:]:
        var = lambda_ * ewma_var[-1] + (1 - lambda_) * (r ** 2)
        ewma_var.append(var)
    
    # Pad beginning
    ewma_var = [ewma_var[0]] * 20 + ewma_var
    ewma_vol = np.sqrt(ANNUAL_FACTOR) * np.sqrt(pd.Series(ewma_var[:len(returns)], index=returns.index))
    return ewma_vol


def compute_vol_of_vol(rv_series: pd.Series, window: int = VOV_WINDOW) -> pd.Series:
    """VoV_w(t) = stdev(RV_w series over L days)"""
    return rv_series.rolling(window).std()


def compute_drawdown(close: pd.Series, window: int = 252) -> pd.Series:
    """dd_t = c_t / peak_N - 1"""
    rolling_max = close.rolling(window, min_periods=1).max()
    return close / rolling_max - 1


def compute_illiquidity(returns: pd.Series, dollar_volume: pd.Series, window: int = ILLIQ_WINDOW) -> pd.Series:
    """Amihud illiquidity: ILLIQ_t = |r_t| / dvol_t, smoothed with median."""
    eps = 1e-12
    illiq = np.abs(returns) / np.maximum(dollar_volume, eps)
    return illiq.rolling(window).median()


def compute_correlation(series_a: pd.Series, series_b: pd.Series, window: int = CORR_WINDOW) -> pd.Series:
    """Rolling correlation between two series."""
    return series_a.rolling(window).corr(series_b)


def compute_abs_return_correlation(returns_a: pd.Series, returns_b: pd.Series, window: int = CORR_WINDOW) -> pd.Series:
    """Correlation of absolute returns - stress proxy."""
    return np.abs(returns_a).rolling(window).corr(np.abs(returns_b))


def compute_tail_quantiles(returns: pd.Series, window: int = 252) -> Tuple[pd.Series, pd.Series]:
    """Rolling quantiles for tail analysis."""
    q05 = returns.rolling(window).quantile(0.05)
    q95 = returns.rolling(window).quantile(0.95)
    return q05, q95


def compute_robust_zscore(series: pd.Series, window: int = CALIBRATION_DAYS, min_periods: int = 60) -> pd.Series:
    """z(x_t) = (x_t - median) / MAD. Uses adaptive min_periods for shorter windows."""
    median = series.rolling(window, min_periods=min_periods).median()
    mad = series.rolling(window, min_periods=min_periods).apply(
        lambda x: np.median(np.abs(x - np.median(x))), raw=True
    )
    # Avoid division by zero
    mad = mad.replace(0, np.nan).fillna(1e-10)
    return (series - median) / mad


# -----------------------------------------------------------------------------
# CORE MATH UTILITIES
# -----------------------------------------------------------------------------

def calibrate_weights(features: pd.DataFrame, target: pd.Series, default_weights: Dict[str, float]) -> Dict[str, float]:
    """
    Compute dynamic weights for features using Entropy-Weighted Correlation (EWC).
    Prioritizes features that have high correlation with the target AND provide
    distinct structural information (avoiding redundant signals).
    """
    try:
        # Ensure alignment
        common_idx = features.index.intersection(target.index)
        f = features.loc[common_idx]
        t = target.loc[common_idx]
        
        if len(common_idx) < 30:
            return default_weights
            
        # Core correlations
        corrs = {col: abs(f[col].corr(t)) for col in f.columns}
        
        # Calculate Information Gain (approx using signal variance and entropy)
        from scipy.stats import entropy
        info_weights = {}
        for col in f.columns:
            # Use absolute values and bin into histograms to estimate entropy
            bins = np.histogram(f[col].fillna(0).values, bins=10)[0]
            inf_gain = entropy(bins + 1e-10)
            info_weights[col] = inf_gain * corrs[col]
            
        total = sum(info_weights.values())
        if total < 1e-6:
            return default_weights
            
        # Normalize to sum to 1
        dynamic_weights = {k: v / total for k, v in info_weights.items()}
        return dynamic_weights
        
    except Exception as e:
        logger.warning(f"Weight calibration failed: {e}")
        return default_weights

def compute_pca_weights(df: pd.DataFrame) -> np.ndarray:
    """
    Use first principal component loadings as weights.
    """
    from sklearn.decomposition import PCA
    try:
        pca = PCA(n_components=1)
        pca.fit(df.fillna(0))
        # Ensure positive weights (most financial stress signs are positive)
        loadings = np.abs(pca.components_[0])
        return loadings / np.sum(loadings)
    except:
        return np.ones(df.shape[1]) / df.shape[1]

def sigmoid(x: pd.Series) -> pd.Series:
    """Sigmoid transform: 1 / (1 + exp(-x))"""
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))


def clamp_positive(x: pd.Series) -> pd.Series:
    """max(0, x)"""
    return np.maximum(x, 0)


# -----------------------------------------------------------------------------
# UNIFIED STATE VECTOR
# -----------------------------------------------------------------------------

def compute_state_vector(
    bars: Dict[str, pd.DataFrame],
    benchmark: str,
    nodes: List[str]
) -> pd.DataFrame:
    """
    Compute unified state vector from aligned bars.
    All tabs read from this single state object.
    """
    if benchmark not in bars:
        raise ValueError(f"Benchmark {benchmark} not in data")
    
    bench_df = bars[benchmark]
    close = bench_df['close']
    volume = bench_df['volume']
    dollar_volume = close * volume
    
    # Basic returns
    returns = compute_log_returns(close)
    abs_returns = np.abs(returns)
    
    # Volatility metrics
    rv20 = compute_realized_volatility(returns, 20)
    rv60 = compute_realized_volatility(returns, 60)
    ewma = compute_ewma_volatility(returns)
    vov20 = compute_vol_of_vol(rv20, 20)
    
    # Illiquidity
    illiq20 = compute_illiquidity(returns, dollar_volume, 20)
    
    # Drawdown
    dd252 = compute_drawdown(close, 252)
    dd_mag = np.abs(dd252)
    
    # Tail metrics
    q05, q95 = compute_tail_quantiles(returns, 252)
    tail_asym = np.abs(q05) - np.abs(q95)
    
    # Cross-asset correlation stress
    corr_abs_list = []
    for node in nodes:
        if node in bars:
            node_returns = compute_log_returns(bars[node]['close'])
            corr_abs = compute_abs_return_correlation(returns, node_returns, CORR_WINDOW)
            corr_abs_list.append(corr_abs)
    
    if corr_abs_list:
        corr_abs_avg = pd.concat(corr_abs_list, axis=1).mean(axis=1)
    else:
        corr_abs_avg = pd.Series(0, index=close.index)
    
    # Build state DataFrame
    state = pd.DataFrame({
        'close': close,
        'returns': returns,
        'abs_returns': abs_returns,
        'rv20': rv20,
        'rv60': rv60,
        'ewma': ewma,
        'vov20': vov20,
        'illiq20': illiq20,
        'dd252': dd252,
        'dd_mag252': dd_mag,
        'q05_252': q05,
        'q95_252': q95,
        'tail_asym252': tail_asym,
        'corr_abs_avg60': corr_abs_avg,
    })
    
    # Add z-scores  
    state['z_rv20'] = compute_robust_zscore(rv20)
    state['z_vov20'] = compute_robust_zscore(vov20)
    state['z_illiq20'] = compute_robust_zscore(illiq20)
    state['z_dd_mag'] = compute_robust_zscore(dd_mag)
    state['z_corr_abs'] = compute_robust_zscore(corr_abs_avg)
    state['z_tail_asym'] = compute_robust_zscore(tail_asym)
    
    # Cumulative returns for momentum
    state['cum_return_20'] = returns.rolling(20).sum()
    state['z_momentum'] = compute_robust_zscore(state['cum_return_20'])
    
    # Drop only rows where critical columns are NaN (not all z-scores needed for all tabs)
    critical_cols = ['close', 'returns', 'rv20', 'vov20', 'illiq20', 'corr_abs_avg60']
    state = state.dropna(subset=critical_cols)
    
    # Fill remaining NaNs with forward fill for z-scores
    state = state.ffill().bfill()
    
    return state


# -----------------------------------------------------------------------------
# TAB 1: STRUCTURAL INTEGRITY INDEX
# -----------------------------------------------------------------------------

def compute_integrity(
    state: pd.DataFrame,
    a1: float = 1.0,
    a2: float = 0.75,
    b0: float = 0.0,
    b1: float = 1.25,
    b2: float = 0.75
) -> Dict[str, Any]:
    """
    Structural Integrity Index - Market health score.
    
    Components:
    - RV stress
    - VoV stress
    - Correlation stress
    - Illiquidity stress
    - Drawdown stress
    """
    # Stress signal vector
    s1 = state['z_rv20']
    s2 = state['z_vov20']
    s3 = state['z_corr_abs']
    s4 = state['z_illiq20']
    s5 = state['z_dd_mag']
    
    stress_signals = pd.DataFrame({
        'RV20': s1, 'VoV20': s2, 'CorrAbs': s3, 'ILLIQ': s4, 'Drawdown': s5
    })
    
    # Dynamic Calibration: Weight markers by their correlation with benchmark returns variance
    returns = state['returns']
    vol_target = returns.rolling(20).std().ffill().fillna(0)
    
    weights_map = calibrate_weights(
        stress_signals, 
        vol_target, 
        {'RV20': 0.25, 'VoV20': 0.20, 'CorrAbs': 0.20, 'ILLIQ': 0.20, 'Drawdown': 0.15}
    )
    
    # Stress core - weighted mean of positive z-scores
    stress_core = pd.Series(0.0, index=state.index)
    for name, w in weights_map.items():
        stress_core += w * stress_signals[name].apply(lambda x: max(0, x))
        
    # Cross-sectional dispersion for agreement score
    # Lower dispersion between stress signals = higher agreement
    disp_s = stress_signals.std(axis=1)
    mean_s = stress_signals.mean(axis=1)
    agreement = sigmoid(a1 * mean_s - a2 * disp_s)
    
    # Integrity calculation
    # High stress = low integrity. High agreement amplifies the stress signal.
    integrity = 100 * (1 - sigmoid(b1 * stress_core + b2 * (1 - agreement) - 1.0))
    
    # Confidence based on data completeness
    confidence = pd.Series(0.95, index=state.index)  # High confidence with real data
    
    # Build output
    values = []
    contributors = []
    
    for idx in state.index:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        values.append({
            't': t,
            'integrity': round(float(integrity.loc[idx]), 2),
            'stressCore': round(float(stress_core.loc[idx]), 4),
            'agreement': round(float(agreement.loc[idx]), 4),
            'confidence': round(float(confidence.loc[idx]), 4)
        })
        
        # Contributors for this timestamp
        items = []
        weights = {'RV20': 0.25, 'VoV20': 0.20, 'CorrAbs': 0.20, 'ILLIQ': 0.20, 'Drawdown': 0.15}
        for name, weight in weights.items():
            z_val = float(stress_signals[name].loc[idx])
            contribution = weight * clamp_positive(pd.Series([z_val])).iloc[0]
            items.append({
                'name': name,
                'z': round(z_val, 4),
                'weight': weight,
                'contribution': round(contribution, 4)
            })
        contributors.append({'t': t, 'items': sorted(items, key=lambda x: -x['contribution'])})
    
    return {
        'asOf': datetime.now().isoformat(),
        'window': {'lookbackDays': len(state), 'calibrationDays': CALIBRATION_DAYS},
        'values': values[-500:],  # Last 500 days for UI
        'contributors': contributors[-100:],  # Last 100 for detail view
    }


# -----------------------------------------------------------------------------
# TAB 2: PROBABILITY MASS FLOW ENGINE (HMM)
# -----------------------------------------------------------------------------

def compute_mass_flow(
    state: pd.DataFrame,
    n_states: int = HMM_STATES,
    train_days: int = HMM_TRAIN_DAYS
) -> Dict[str, Any]:
    """
    Probability Mass Flow - HMM regime detection.
    
    Features:
    - ln(RV20)
    - delta ln(RV20)
    - corrAbsAvg60
    - z(ILLIQ20)
    """
    # Build feature matrix
    ln_rv20 = np.log(state['rv20'].clip(lower=1e-10))
    delta_ln_rv20 = ln_rv20.diff()
    corr_abs = state['corr_abs_avg60']
    z_illiq = state['z_illiq20']
    
    features = pd.DataFrame({
        'ln_rv20': ln_rv20,
        'delta_ln_rv20': delta_ln_rv20,
        'corr_abs': corr_abs,
        'z_illiq': z_illiq
    }).dropna()
    
    X = features.values
    
    if not HMM_AVAILABLE or len(X) < 100:
        # Fallback: quantile-based regimes
        return _compute_mass_flow_fallback(state, features)
    
    try:
        # Fit HMM with 'full' covariance to capture complex inter-feature relationships
        model = GaussianHMM(
            n_components=n_states,
            covariance_type='full',
            n_iter=100,
            random_state=42,
            tol=1e-3
        )
        model.fit(X[-min(train_days, len(X)):])
        
        # --- SOLUTION 3: HMM IDENTITY FIX (STABLE UI COLORS) ---
        # Sort states by the mean of the first feature (ln_rv20)
        # This ensures State 0 is ALWAYS 'Calm' (low vol) and State 3 is ALWAYS 'Crisis' (high vol)
        state_vols = model.means_[:, 0]
        order = np.argsort(state_vols)
        
        # Remap model parameters
        model.means_ = model.means_[order]
        model.covars_ = model.covars_[order]
        model.startprob_ = model.startprob_[order]
        model.transmat_ = model.transmat_[np.ix_(order, order)]
        
        # Get posteriors and states (now sorted)
        posteriors = model.predict_proba(X)
        states = model.predict(X)
        
    except Exception as e:
        warnings.warn(f"HMM fitting failed: {e}")
        return _compute_mass_flow_fallback(state, features)
    
    # Compute derived metrics
    timeline = []
    ages = []
    current_age = 1
    prev_state = states[0]
    
    # State labels by median RV
    state_rv_medians = {}
    for s in range(n_states):
        mask = states == s
        if mask.sum() > 0:
            state_rv_medians[s] = np.median(features.loc[features.index[mask], 'ln_rv20'])
        else:
            state_rv_medians[s] = 0
    
    # Sort states by RV (calm to crisis)
    sorted_states = sorted(state_rv_medians.keys(), key=lambda x: state_rv_medians[x])
    state_labels = {
        sorted_states[0]: {'name': 'Calm', 'description': 'Low volatility regime'},
        sorted_states[1]: {'name': 'Elevated', 'description': 'Moderately elevated volatility'},
        sorted_states[2]: {'name': 'Stressed', 'description': 'High stress environment'},
        sorted_states[3]: {'name': 'Crisis', 'description': 'Extreme market stress'}
    } if n_states >= 4 else {}
    
    # Build timeline with mass velocity and entropy
    for i, idx in enumerate(features.index):
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        
        probs = posteriors[i].tolist()
        state_id = int(states[i])
        
        # Mass velocity: total variation distance
        if i > 0:
            mass_vel = 0.5 * np.sum(np.abs(posteriors[i] - posteriors[i-1]))
        else:
            mass_vel = 0
        
        # Entropy (normalized)
        entropy = -np.sum(posteriors[i] * np.log(posteriors[i] + 1e-10)) / np.log(n_states)
        
        # Age tracking
        if state_id == prev_state:
            current_age += 1
        else:
            current_age = 1
        prev_state = state_id
        ages.append(current_age)
        
        # Exhaustion percentile
        exhaust_pct = percentileofscore(ages, current_age) if len(ages) > 1 else 50
        
        timeline.append({
            't': t,
            'stateId': state_id,
            'probs': [round(float(p), 4) for p in probs],
            'massVel': round(float(mass_vel), 4),
            'entropy': round(float(entropy), 4),
            'age': current_age,
            'exhaustPct': round(float(exhaust_pct), 2)
        })
    
    # State labels output
    state_labels_out = []
    for s in range(n_states):
        mask = states == s
        if mask.sum() > 0:
            feature_subset = features.iloc[mask]
            state_labels_out.append({
                'stateId': int(s),
                'name': state_labels.get(s, {}).get('name', f'State {s}'),
                'description': state_labels.get(s, {}).get('description', ''),
                'medianRV': round(float(np.exp(feature_subset['ln_rv20'].median())), 4),
                'medianILLIQ': round(float(feature_subset['z_illiq'].median()), 4),
                'medianCorrAbs': round(float(feature_subset['corr_abs'].median()), 4)
            })
    
    return {
        'asOf': datetime.now().isoformat(),
        'model': {
            'method': 'HMM',
            'states': n_states,
            'features': ['ln_rv20', 'delta_ln_rv20', 'corr_abs', 'z_illiq'],
            'trainWindowDays': min(train_days, len(X))
        },
        'timeline': timeline[-500:],
        'stateLabels': state_labels_out
    }


def _compute_mass_flow_fallback(state: pd.DataFrame, features: pd.DataFrame) -> Dict[str, Any]:
    """Fallback regime detection using quantiles when HMM unavailable."""
    rv20 = state['rv20'].reindex(features.index)
    
    # Simple quantile-based regimes
    q25 = rv20.quantile(0.25)
    q50 = rv20.quantile(0.50)
    q75 = rv20.quantile(0.75)
    
    def assign_regime(rv):
        if rv < q25:
            return 0  # Calm
        elif rv < q50:
            return 1  # Elevated
        elif rv < q75:
            return 2  # Stressed
        else:
            return 3  # Crisis
    
    states = rv20.apply(assign_regime)
    
    timeline = []
    current_age = 1
    prev_state = states.iloc[0] if len(states) > 0 else 0
    ages = []
    
    for idx in features.index:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        state_id = int(states.loc[idx])
        
        # Simple probability approximation
        rv_val = rv20.loc[idx]
        dist_to_q = [
            abs(rv_val - q25),
            abs(rv_val - q50),
            abs(rv_val - q75),
            abs(rv_val - rv20.quantile(0.90))
        ]
        inv_dist = [1/(d+0.01) for d in dist_to_q]
        total = sum(inv_dist)
        probs = [d/total for d in inv_dist]
        
        # Age
        if state_id == prev_state:
            current_age += 1
        else:
            current_age = 1
        prev_state = state_id
        ages.append(current_age)
        
        # Calculate dynamic entropy from probs
        entropy = -np.sum(np.array(probs) * np.log(np.array(probs) + 1e-10)) / np.log(4)
        
        # Calculate mass velocity
        if len(timeline) > 0:
            prev_probs = timeline[-1]['probs']
            mass_vel = 0.5 * np.sum(np.abs(np.array(probs) - np.array(prev_probs)))
        else:
            mass_vel = 0.05

        exhaust_pct = percentileofscore(ages, current_age) if len(ages) > 1 else 50
        
        timeline.append({
            't': t,
            'stateId': state_id,
            'probs': [round(p, 4) for p in probs],
            'massVel': round(float(mass_vel), 4),
            'entropy': round(float(entropy), 4),
            'age': current_age,
            'exhaustPct': round(exhaust_pct, 2)
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'model': {
            'method': 'Quantile-Based (Fallback)',
            'states': 4,
            'features': ['rv20'],
            'trainWindowDays': len(features)
        },
        'timeline': timeline[-500:],
        'stateLabels': [
            {'stateId': 0, 'name': 'Calm', 'description': 'RV < 25th percentile', 'medianRV': round(q25, 4), 'medianILLIQ': 0, 'medianCorrAbs': 0},
            {'stateId': 1, 'name': 'Elevated', 'description': 'RV 25th-50th percentile', 'medianRV': round(q50, 4), 'medianILLIQ': 0, 'medianCorrAbs': 0},
            {'stateId': 2, 'name': 'Stressed', 'description': 'RV 50th-75th percentile', 'medianRV': round(q75, 4), 'medianILLIQ': 0, 'medianCorrAbs': 0},
            {'stateId': 3, 'name': 'Crisis', 'description': 'RV > 75th percentile', 'medianRV': round(rv20.quantile(0.90), 4), 'medianILLIQ': 0, 'medianCorrAbs': 0}
        ]
    }


# -----------------------------------------------------------------------------
# TAB 3: REFLEXIVE PRESSURE & DENIAL INDEX
# -----------------------------------------------------------------------------

def compute_reflex_denial(
    state: pd.DataFrame,
    mass_flow_data: Dict[str, Any],
    c1: float = 0.8,
    c2: float = 0.6,
    d1: float = 1.2,
    d2: float = 0.9,
    e1w: float = 1.0,
    e2w: float = 1.0
) -> Dict[str, Any]:
    """
    Reflexive Pressure & Denial Index.
    
    Detects self-reinforcing behavior and reality distortion.
    """
    # Momentum dominance
    mom = state['z_momentum']
    
    # Vol chasing proxy - correlation between returns and delta RV
    delta_rv = state['rv20'].diff()
    vol_chase_raw = state['returns'].rolling(60).corr(delta_rv)
    vol_chase = compute_robust_zscore(vol_chase_raw.fillna(0))
    
    # Reflexive pressure
    reflex_core = c1 * mom + c2 * vol_chase
    reflex = 100 * sigmoid(reflex_core)
    
    # Extract calm probability from mass flow
    timeline = mass_flow_data.get('timeline', [])
    calm_prob = pd.Series(0.25, index=state.index)  # Default
    
    if timeline:
        # Find calm state (lowest median RV)
        state_labels = mass_flow_data.get('stateLabels', [])
        calm_state_id = 0
        if state_labels:
            calm_state_id = min(state_labels, key=lambda x: x.get('medianRV', 999))['stateId']
        
        for entry in timeline:
            t = entry['t']
            if t in state.index.strftime('%Y-%m-%d').tolist():
                idx = pd.to_datetime(t)
                if idx in calm_prob.index:
                    probs = entry.get('probs', [0.25, 0.25, 0.25, 0.25])
                    if calm_state_id < len(probs):
                        calm_prob.loc[idx] = probs[calm_state_id]
    
    # Stress evidence
    stress_evidence = (
        clamp_positive(state['z_rv20']) +
        clamp_positive(state['z_vov20']) +
        clamp_positive(state['z_corr_abs']) +
        clamp_positive(state['z_illiq20'])
    ) / 4
    
    # Denial
    denial_core = d1 * calm_prob + d2 * stress_evidence
    denial = 100 * sigmoid(denial_core)
    
    # Combined index
    reflex_denial_core = e1w * (reflex / 100) + e2w * (denial / 100)
    reflex_denial = 100 * sigmoid(reflex_denial_core)
    
    # Build output
    values = []
    drivers = []
    
    for idx in state.index:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        
        values.append({
            't': t,
            'reflex': round(float(reflex.loc[idx]), 2),
            'denial': round(float(denial.loc[idx]), 2),
            'reflexDenial': round(float(reflex_denial.loc[idx]), 2),
            'calmProb': round(float(calm_prob.loc[idx]), 4),
            'stressEvidence': round(float(stress_evidence.loc[idx]), 4)
        })
        
        # Driver analysis
        items = [
            {'name': 'Momentum', 'value': round(float(mom.loc[idx]), 4), 'z': round(float(mom.loc[idx]), 4), 'note': 'Trend strength'},
            {'name': 'VolChase', 'value': round(float(vol_chase.loc[idx]), 4), 'z': round(float(vol_chase.loc[idx]), 4), 'note': 'Chasing volatility'},
            {'name': 'CalmProb', 'value': round(float(calm_prob.loc[idx]), 4), 'z': 0, 'note': 'Regime calm probability'},
            {'name': 'StressEvid', 'value': round(float(stress_evidence.loc[idx]), 4), 'z': round(float(stress_evidence.loc[idx]), 4), 'note': 'Aggregate stress'}
        ]
        drivers.append({'t': t, 'items': sorted(items, key=lambda x: -abs(x['value']))})
    
    return {
        'asOf': datetime.now().isoformat(),
        'values': values[-500:],
        'drivers': drivers[-100:]
    }


# -----------------------------------------------------------------------------
# TAB 4: LIQUIDITY & LEVERAGE FRAGILITY SURFACE
# -----------------------------------------------------------------------------

def compute_fragility(
    state: pd.DataFrame,
    f1: float = 1.0,
    f2: float = 1.0,
    f3: float = 0.7,
    w_rate: float = 0.5
) -> Dict[str, Any]:
    """
    Liquidity & Leverage Fragility Surface.
    
    2D state space mapping mechanical failure risk.
    """
    # Liquidity axis
    liquidity_axis = state['z_illiq20']
    
    # Convexity stress proxy
    convex_raw = state['rv20'] * state['vov20']
    convex = compute_robust_zscore(convex_raw)
    
    # Leverage sensitivity (no rates data, so just convexity)
    leverage_axis = convex  # Could add rate shock if available
    
    # Correlation stress
    corr_stress = state['z_corr_abs']
    
    # Fragility score
    fragility_core = f1 * liquidity_axis + f2 * leverage_axis + f3 * corr_stress
    fragility = 100 * sigmoid(fragility_core)
    
    # Build output
    values = []
    state_space = []
    
    for idx in state.index:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        
        liq = float(liquidity_axis.loc[idx])
        lev = float(leverage_axis.loc[idx])
        frag = float(fragility.loc[idx])
        corr_s = float(corr_stress.loc[idx])
        
        values.append({
            't': t,
            'fragility': round(frag, 2),
            'liquidityAxis': round(liq, 4),
            'leverageAxis': round(lev, 4),
            'corrStress': round(corr_s, 4)
        })
        
        # State space points
        state_space.append({
            't': t,
            'x': round(liq, 4),
            'y': round(lev, 4),
            'fragility': round(frag, 2)
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'values': values[-500:],
        'stateSpace': state_space[-500:]
    }


# -----------------------------------------------------------------------------
# TAB 5: FEEDBACK LOOP CLOSURE MONITOR
# -----------------------------------------------------------------------------

def compute_feedback_loops(
    state: pd.DataFrame,
    g1: float = 2.0,
    g2: float = 1.0,
    window: int = LOOP_WINDOW,
    max_lag: int = LOOP_LAG_MAX
) -> Dict[str, Any]:
    """
    Feedback Loop Closure Monitor.
    
    Measures whether dynamics are dampening or amplifying.
    """
    # Loop variables
    A = state['returns']  # Returns
    B = state['rv20'].diff()  # Delta RV
    C = state['illiq20'].diff()  # Delta ILLIQ
    
    def best_lag_corr(source: pd.Series, target: pd.Series, window: int, max_lag: int) -> Tuple[float, int]:
        """Find best lag correlation."""
        best_corr = 0
        best_lag = 1
        
        for lag in range(1, max_lag + 1):
            # Lagged correlation
            corr = source.shift(lag).rolling(window).corr(target)
            mean_corr = corr.iloc[-window:].mean() if len(corr) > window else 0
            
            if abs(mean_corr) > abs(best_corr):
                best_corr = mean_corr
                best_lag = lag
        
        return best_corr, best_lag
    
    # Compute link correlations
    values = []
    links_timeline = []
    
    # Rolling computation
    for i in range(window, len(state)):
        idx = state.index[i]
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        
        # Subset for this window
        start_i = max(0, i - window)
        A_win = A.iloc[start_i:i+1]
        B_win = B.iloc[start_i:i+1]
        C_win = C.iloc[start_i:i+1]
        
        # Compute correlations
        try:
            c_ab = A_win.shift(1).corr(B_win)
            c_bc = B_win.shift(1).corr(C_win)
            c_ca = C_win.shift(1).corr(A_win)
        except:
            c_ab = c_bc = c_ca = 0
        
        c_ab = c_ab if not np.isnan(c_ab) else 0
        c_bc = c_bc if not np.isnan(c_bc) else 0
        c_ca = c_ca if not np.isnan(c_ca) else 0
        
        # Loop strength
        loop_strength = np.mean([abs(c_ab), abs(c_bc), abs(c_ca)])
        
        # Amplification detection
        product = c_ab * c_bc * c_ca
        amplify_flag = 1 if product > 0 and loop_strength > 0.1 else 0
        
        amplification_core = g1 * loop_strength + g2 * amplify_flag
        amplification = 100 * (1 / (1 + np.exp(-amplification_core)))
        
        # Dominant link
        corrs = {'ReturnToVol': abs(c_ab), 'VolToIlliq': abs(c_bc), 'IlliqToReturn': abs(c_ca)}
        dominant_link = max(corrs, key=corrs.get)
        
        values.append({
            't': t,
            'loopStrength': round(float(loop_strength), 4),
            'amplification': round(float(amplification), 2),
            'dominantLink': dominant_link
        })
        
        links_timeline.append({
            't': t,
            'items': [
                {'name': 'Return→Vol', 'corr': round(float(c_ab), 4), 'lagDays': 1},
                {'name': 'Vol→Illiq', 'corr': round(float(c_bc), 4), 'lagDays': 1},
                {'name': 'Illiq→Return', 'corr': round(float(c_ca), 4), 'lagDays': 1}
            ]
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'values': values[-500:],
        'links': links_timeline[-100:]
    }


# -----------------------------------------------------------------------------
# TAB 6: NONLINEARITY PROXIMITY & BREAK THRESHOLD
# -----------------------------------------------------------------------------

def compute_nonlinearity(
    state: pd.DataFrame,
    horizon: int = BREAK_SIM_HORIZON,
    paths: int = BREAK_SIM_PATHS,
    block_size: int = BREAK_SIM_BLOCK_SIZE,
    shock_grid: List[float] = None,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Nonlinearity Proximity & Break Threshold Engine.
    
    Bootstrap simulation to estimate break probability.
    """
    if shock_grid is None:
        shock_grid = SHOCK_GRID
    
    np.random.seed(seed)
    
    returns = state['returns'].dropna()
    rv20 = state['rv20']
    
    # Use last 252 days as return pool
    pool_size = min(252, len(returns) - horizon)
    if pool_size < 50:
        # Not enough data
        return _nonlinearity_fallback(state)
    
    # Compute historical damage distribution for critical threshold
    historical_damages = []
    for i in range(pool_size, len(returns) - horizon):
        path_returns = returns.iloc[i:i+horizon]
        path_dd = (path_returns.cumsum().cummax() - path_returns.cumsum()).max()
        path_rv = returns.iloc[i:i+horizon].std() * np.sqrt(252)
        damage = abs(path_dd) + 0.7 * path_rv
        historical_damages.append(damage)
    
    damage_crit = np.percentile(historical_damages, 95) if historical_damages else 0.05
    
    # Compute break probability for each shock size at current time
    values = []
    curves = []
    
    # Only compute for last 100 trading days to save time
    compute_indices = state.index[-100:]
    
    for idx in compute_indices:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        i = state.index.get_loc(idx)
        
        if i < pool_size:
            continue
        
        pool = returns.iloc[max(0, i-pool_size):i].values
        
        break_probs = []
        for shock in shock_grid:
            damages = []
            
            for _ in range(paths):
                # Block bootstrap
                path = []
                # Safety Guard: Ensure pool is large enough for block size
                effective_block = min(block_size, len(pool))
                while len(path) < horizon:
                    if len(pool) <= effective_block:
                        start = 0
                    else:
                        start = np.random.randint(0, len(pool) - effective_block + 1)
                    path.extend(pool[start:start+effective_block])
                path = np.array(path[:horizon])
                
                # Apply shock on day 1
                path[0] -= shock / 100  # Negative shock
                
                # Compute damage
                cum_ret = np.cumsum(path)
                max_dd = np.max(np.maximum.accumulate(cum_ret) - cum_ret)
                path_rv = np.std(path) * np.sqrt(252)
                damage = max_dd + 0.7 * path_rv
                damages.append(damage)
            
            # Break probability
            break_prob = np.mean(np.array(damages) > damage_crit)
            break_probs.append(break_prob)
        
        # Find break threshold
        break_threshold = shock_grid[-1]  # Default to max
        for j, prob in enumerate(break_probs):
            if prob >= 0.5:
                break_threshold = shock_grid[j]
                break
        
        # Nonlinearity proximity (lower threshold = closer to break)
        if len(values) > 0:
            all_thresholds = [v['breakThreshold'] for v in values]
            all_thresholds.append(break_threshold)
            nonlinearity = 100 * (1 - percentileofscore(all_thresholds, break_threshold) / 100)
        else:
            nonlinearity = 50
        
        values.append({
            't': t,
            'nonlinearity': round(float(nonlinearity), 2),
            'breakThreshold': round(float(break_threshold), 4),
            'units': 'pct_return_shock',
            'damageCrit': round(float(damage_crit), 4)
        })
        
        curves.append({
            't': t,
            'shockSizes': shock_grid,
            'breakProb': [round(float(p), 4) for p in break_probs]
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'simulation': {
            'horizonDays': horizon,
            'paths': paths,
            'blockSize': block_size,
            'poolDays': pool_size,
            'seed': seed
        },
        'values': values,
        'curves': curves[-50:]  # Last 50 for detail view
    }


def _nonlinearity_fallback(state: pd.DataFrame) -> Dict[str, Any]:
    """Fallback when insufficient data for bootstrap."""
    values = []
    for idx in state.index[-100:]:
        t = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        # Use VoV as proxy for nonlinearity
        vov = float(state.loc[idx, 'vov20']) if 'vov20' in state.columns else 0.15
        nonlinearity = min(100, vov * 500)  # Scale VoV to 0-100
        
        values.append({
            't': t,
            'nonlinearity': round(nonlinearity, 2),
            'breakThreshold': 2.0,  # Default
            'units': 'pct_return_shock',
            'damageCrit': 0.05
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'simulation': {'method': 'VoV-proxy (fallback)'},
        'values': values,
        'curves': []
    }


# -----------------------------------------------------------------------------
# TAB 7: COLLAPSE STATE GOVERNOR
# -----------------------------------------------------------------------------

def compute_collapse_state(
    integrity_data: Dict,
    mass_flow_data: Dict,
    reflex_denial_data: Dict,
    fragility_data: Dict,
    feedback_data: Dict,
    nonlinearity_data: Dict,
    alpha: float = 0.8
) -> Dict[str, Any]:
    """
    Collapse State Governor - Three-state synthesis.
    
    Compresses all primitives into Stable/Fragile/Critical.
    """
    # Extract time series from each primitive
    def extract_series(data: Dict, key: str, default: float = 0.5) -> Dict[str, float]:
        result = {}
        for entry in data.get('values', data.get('timeline', [])):
            t = entry.get('t')
            val = entry.get(key, default)
            result[t] = float(val) if val is not None else default
        return result
    
    integrity_s = extract_series(integrity_data, 'integrity', 50)
    
    # Extract mass velocity from mass flow
    mass_vel_s = {}
    entropy_s = {}
    for entry in mass_flow_data.get('timeline', []):
        t = entry.get('t')
        mass_vel_s[t] = entry.get('massVel', 0.1)
        entropy_s[t] = entry.get('entropy', 0.5)
    
    reflex_denial_s = extract_series(reflex_denial_data, 'reflexDenial', 50)
    fragility_s = extract_series(fragility_data, 'fragility', 50)
    amplification_s = extract_series(feedback_data, 'amplification', 50)
    nonlinearity_s = extract_series(nonlinearity_data, 'nonlinearity', 50)
    
    # Get all timestamps
    all_times = sorted(set(integrity_s.keys()) & set(fragility_s.keys()))
    
    if not all_times:
        return {'asOf': datetime.now().isoformat(), 'values': [], 'drivers': []}
    
    # Normalize components to 0-1
    values = []
    drivers = []
    pressure_smooth = 0.5
    
    for t in all_times:
        I = 1 - integrity_s.get(t, 50) / 100  # Inverse of integrity
        M_raw = mass_vel_s.get(t, 0.1)
        M = 1 / (1 + np.exp(-2 * (M_raw - 0.2)))  # Sigmoid normalize
        E = entropy_s.get(t, 0.5)
        R = reflex_denial_s.get(t, 50) / 100
        F = fragility_s.get(t, 50) / 100
        A = amplification_s.get(t, 50) / 100
        N = nonlinearity_s.get(t, 50) / 100
        
        # Collapse pressure
        pressure = (
            GOVERNOR_WEIGHTS['integrity'] * I +
            GOVERNOR_WEIGHTS['mass_vel'] * M +
            GOVERNOR_WEIGHTS['entropy'] * E +
            GOVERNOR_WEIGHTS['reflex_denial'] * R +
            GOVERNOR_WEIGHTS['fragility'] * F +
            GOVERNOR_WEIGHTS['amplification'] * A +
            GOVERNOR_WEIGHTS['nonlinearity'] * N
        )
        
        # Handle NaN
        if np.isnan(pressure):
            pressure = 0.5
        
        # Smoothing
        if np.isnan(pressure_smooth):
            pressure_smooth = pressure
        else:
            pressure_smooth = alpha * pressure_smooth + (1 - alpha) * pressure
        
        # State thresholds
        if pressure_smooth < 0.33:
            state = 'Stable'
        elif pressure_smooth < 0.66:
            state = 'Fragile'
        else:
            state = 'Critical'
        
        # Confidence
        confidence = (1 - 0.05) * (1 - E)  # Adjust based on missing data and entropy
        if np.isnan(confidence):
            confidence = 0.5
        
        values.append({
            't': t,
            'state': state,
            'pressure': round(float(pressure), 4),
            'pressureSmooth': round(float(pressure_smooth), 4),
            'confidence': round(float(confidence), 4)
        })
        
        # Driver contributions
        driver_items = [
            {'name': 'Integrity', 'component': 'integrity', 'contribution': round(GOVERNOR_WEIGHTS['integrity'] * I, 4), 'value': round(I, 4)},
            {'name': 'MassVelocity', 'component': 'mass_vel', 'contribution': round(GOVERNOR_WEIGHTS['mass_vel'] * M, 4), 'value': round(M, 4)},
            {'name': 'Entropy', 'component': 'entropy', 'contribution': round(GOVERNOR_WEIGHTS['entropy'] * E, 4), 'value': round(E, 4)},
            {'name': 'ReflexDenial', 'component': 'reflex_denial', 'contribution': round(GOVERNOR_WEIGHTS['reflex_denial'] * R, 4), 'value': round(R, 4)},
            {'name': 'Fragility', 'component': 'fragility', 'contribution': round(GOVERNOR_WEIGHTS['fragility'] * F, 4), 'value': round(F, 4)},
            {'name': 'Amplification', 'component': 'amplification', 'contribution': round(GOVERNOR_WEIGHTS['amplification'] * A, 4), 'value': round(A, 4)},
            {'name': 'Nonlinearity', 'component': 'nonlinearity', 'contribution': round(GOVERNOR_WEIGHTS['nonlinearity'] * N, 4), 'value': round(N, 4)}
        ]
        drivers.append({
            't': t,
            'items': sorted(driver_items, key=lambda x: -x['contribution'])
        })
    
    return {
        'asOf': datetime.now().isoformat(),
        'values': values,
        'drivers': drivers[-100:]
    }


# -----------------------------------------------------------------------------
# MAIN ENTRY POINTS
# -----------------------------------------------------------------------------

def run_regimes_engine(
    benchmark: str = DEFAULT_BENCHMARK,
    nodes: List[str] = None,
    window_years: int = DEFAULT_WINDOW_YEARS,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Main entry point - computes all 7 crown primitives.
    """
    if nodes is None:
        nodes = DEFAULT_NODES
    
    # Fetch and align data
    bars, evidence, quality = get_aligned_universe(benchmark, nodes, window_years, force_refresh)
    
    if not bars or benchmark not in bars:
        return {
            'error': f'Failed to fetch data for {benchmark}',
            'quality': quality,
            'evidence': evidence
        }
    
    # Compute unified state vector
    try:
        state = compute_state_vector(bars, benchmark, nodes)
    except Exception as e:
        return {'error': f'State vector computation failed: {str(e)}', 'quality': quality, 'evidence': evidence}
    
    # Compute each primitive
    try:
        integrity = compute_integrity(state)
    except Exception as e:
        integrity = {'error': str(e)}
    
    try:
        mass_flow = compute_mass_flow(state)
    except Exception as e:
        mass_flow = {'error': str(e)}
    
    try:
        reflex_denial = compute_reflex_denial(state, mass_flow)
    except Exception as e:
        reflex_denial = {'error': str(e)}
    
    try:
        fragility = compute_fragility(state)
    except Exception as e:
        fragility = {'error': str(e)}
    
    try:
        feedback_loops = compute_feedback_loops(state)
    except Exception as e:
        feedback_loops = {'error': str(e)}
    
    try:
        nonlinearity = compute_nonlinearity(state)
    except Exception as e:
        nonlinearity = {'error': str(e)}
    
    try:
        collapse_state = compute_collapse_state(
            integrity, mass_flow, reflex_denial,
            fragility, feedback_loops, nonlinearity
        )
    except Exception as e:
        collapse_state = {'error': str(e)}
    
    result = {
        'asOf': datetime.now().isoformat(),
        'inputs': {
            'universe': {'benchmark': benchmark, 'nodes': nodes},
            'window': {'years': window_years},
        },
        'outputs': {
            'integrity': integrity,
            'massFlow': mass_flow,
            'reflexDenial': reflex_denial,
            'fragility': fragility,
            'feedbackLoops': feedback_loops,
            'nonlinearity': nonlinearity,
            'collapseState': collapse_state
        },
        'quality': quality,
        'evidence': evidence,
        'provenance': {
            'engineVersion': '1.0.0',
            'computeTimeMs': 0,  # Would be filled in by wrapper
            'calendar': 'US_EQUITY'
        }
    }
    
    # Sanitize all float values for JSON serialization
    return sanitize_dict(result)


def get_regimes_universe() -> Dict[str, Any]:
    """Returns available configuration for the regimes engine."""
    return {
        'defaultBenchmark': DEFAULT_BENCHMARK,
        'defaultNodes': DEFAULT_NODES,
        'availableNodes': ['TLT', 'LQD', 'UUP', 'HYG', 'GLD', 'VIX'],
        'windowOptions': [1, 2, 3, 5],
        'hmmStates': HMM_STATES,
        'calibrationDays': CALIBRATION_DAYS
    }
