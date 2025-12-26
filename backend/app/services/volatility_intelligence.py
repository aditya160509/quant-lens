"""
Volatility Intelligence System - Individual Feature Services
Each feature has its own endpoint to avoid timeout and provide granular control
"""

import pandas as pd
import numpy as np
from scipy import stats
import logging
from typing import Dict, List, Optional, Any
import yfinance as yf
from datetime import datetime, timedelta

from app.services import research_math, research_data
import os

logger = logging.getLogger(__name__)

# Cache for price data
_price_cache: Dict[str, Dict] = {}
_cache_ttl_minutes = 30


def get_cached_prices(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Get price data with caching"""
    cache_key = f"{ticker}_{period}"
    now = datetime.now()
    
    if cache_key in _price_cache:
        cached = _price_cache[cache_key]
        if (now - cached['timestamp']).total_seconds() < _cache_ttl_minutes * 60:
            return cached['data'].copy()
    
    try:
        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            return pd.DataFrame()
        
        # Flatten multi-index columns if present (yfinance 0.2.x returns multi-index)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        _price_cache[cache_key] = {
            'data': df,
            'timestamp': now
        }
        return df.copy()
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()


# =============================================================================
# CORE VOLATILITY PRIMITIVES
# =============================================================================

def log_returns(prices: pd.Series) -> pd.Series:
    """Calculate log returns"""
    return np.log(prices / prices.shift(1)).dropna()


def realized_vol(returns: pd.Series, window: int = 20) -> pd.Series:
    """Close-to-close realized volatility (annualized)"""
    return returns.rolling(window=window).std() * np.sqrt(252)


def ewma_vol(returns: pd.Series, lambda_: float = 0.94) -> pd.Series:
    """EWMA volatility (RiskMetrics approach)"""
    alpha = 1 - lambda_
    return returns.ewm(alpha=alpha, adjust=False).std() * np.sqrt(252)


def parkinson_vol(high: pd.Series, low: pd.Series, window: int = 20) -> pd.Series:
    """Parkinson range-based volatility estimator"""
    hl_ratio = np.log(high / low)
    factor = 1.0 / (4.0 * np.log(2))
    return np.sqrt(factor * (hl_ratio ** 2).rolling(window).mean()) * np.sqrt(252)


def robust_zscore(series: pd.Series) -> pd.Series:
    """Robust z-score using median and MAD"""
    med = series.median()
    mad = np.median(np.abs(series - med))
    if mad == 0:
        mad = series.std()
    
    if mad == 0:
        return pd.Series(0, index=series.index)
        
    return (series - med) / (1.4826 * mad)


# =============================================================================
# FEATURE 1: REALIZED VOLATILITY SUITE
# =============================================================================

def compute_rv_suite(ticker: str, window_years: int = 2) -> Dict:
    """Feature 1: Realized Volatility Suite"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}. Need at least 60 days.'}
    
    try:
        close = df['Close']
        returns = log_returns(close)
        
        rv_20 = realized_vol(returns, 20)
        rv_60 = realized_vol(returns, 60)
        ewma = ewma_vol(returns)
        
        if 'High' in df.columns and 'Low' in df.columns:
            park = parkinson_vol(df['High'], df['Low'])
        else:
            # --- SOLUTION 4: OHLC FALLBACK (STEP-DOWN ESTIMATOR) ---
            # If OHLC is missing, fallback to EWMA as a more dynamic proxy than simple RV
            park = ewma_vol(returns)
        
        # Vol-of-vol (60-day window for statistical stability)
        vvol = rv_20.rolling(60).std()
        
        # Ensure we have valid data
        valid_idx = rv_20.dropna().index
        
        return {
            'ticker': ticker,
            'dates': valid_idx.strftime('%Y-%m-%d').tolist(),
            'rv_20': [float(x) for x in rv_20.reindex(valid_idx).values],
            'rv_60': [float(x) if not pd.isna(x) else 0 for x in rv_60.reindex(valid_idx).values],
            'ewma': [float(x) for x in ewma.reindex(valid_idx).values],
            'parkinson': [float(x) if not pd.isna(x) else 0 for x in park.reindex(valid_idx).values] if park is not None else None,
            'vol_of_vol': [float(x) if not pd.isna(x) else 0 for x in vvol.reindex(valid_idx).values],
            'current': {
                'rv_20': float(rv_20.iloc[-1]) if len(rv_20) > 0 else 0,
                'rv_60': float(rv_60.iloc[-1]) if len(rv_60) > 0 else 0,
                'ewma': float(ewma.iloc[-1]) if len(ewma) > 0 else 0,
            },
            'meta': {
                'data_points': len(valid_idx),
                'start': valid_idx[0].strftime('%Y-%m-%d'),
                'end': valid_idx[-1].strftime('%Y-%m-%d'),
            }
        }
    except Exception as e:
        logger.error(f"RV Suite error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 2: VOLATILITY HEATMAP
# =============================================================================

def compute_vol_heatmap(ticker: str, window_years: int = 2) -> Dict:
    """Feature 2: Volatility Heatmap across multiple windows"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 120:
        return {'error': f'Insufficient data for {ticker}. Need at least 120 days.'}
    
    try:
        returns = log_returns(df['Close'])
        windows = [5, 10, 20, 40, 60, 120]
        
        # Find common valid index after largest window
        valid_idx = realized_vol(returns, 120).dropna().index
        
        heatmap = {}
        for w in windows:
            rv = realized_vol(returns, w)
            heatmap[f'rv_{w}'] = [float(x) if not pd.isna(x) else 0 for x in rv.reindex(valid_idx).values]
        
        return {
            'ticker': ticker,
            'dates': valid_idx.strftime('%Y-%m-%d').tolist(),
            'windows': windows,
            'heatmap': heatmap,
            'color_scale': {
                'min': 0,
                'max': 0.80,
                'thresholds': [0.10, 0.20, 0.30, 0.50, 0.80]
            },
            'meta': {
                'data_points': len(valid_idx),
            }
        }
    except Exception as e:
        logger.error(f"Heatmap error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 3: IV-RV SPREAD
# =============================================================================

def compute_iv_rv_spread(ticker: str, window_years: int = 2) -> Dict:
    """
    Feature 3: Implied Volatility - Realized Volatility Spread
    
    Approach:
    1. For SPY/SPX: Use VIX as direct IV proxy (most accurate)
    2. For QQQ: Use VXN (NASDAQ volatility)
    3. For IWM: Use RVX (Russell volatility)
    4. For ALL OTHER stocks: Use Beta-Adjusted VIX (VIX × Beta)
       - This is a professional-grade approximation used by traders
    """
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        # Calculate RV
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        rv_30 = realized_vol(returns, 30).dropna()
        
        # Determine IV source
        iv_source = None
        iv_series = None
        beta_used = None
        
        # VIX-based tickers (use VIX directly)
        # Format: ticker -> (vix_ticker, multiplier)
        vix_mapped = {
            # US S&P 500
            'SPY': ('^VIX', 1.0),
            'SPX': ('^VIX', 1.0),
            '^GSPC': ('^VIX', 1.0),
            'IVV': ('^VIX', 1.0),
            'VOO': ('^VIX', 1.0),
            
            # US NASDAQ
            'QQQ': ('^VXN', 1.0),
            '^NDX': ('^VXN', 1.0),
            '^IXIC': ('^VXN', 1.0),
            'TQQQ': ('^VXN', 3.0),  # 3x leveraged
            'SQQQ': ('^VXN', 3.0),  # 3x inverse
            
            # US Russell 2000
            'IWM': ('^RVX', 1.0),
            '^RUT': ('^RVX', 1.0),
            
            # India - NIFTY VIX
            '^NSEI': ('^INDIAVIX', 1.0),  # NIFTY 50
            '^BSESN': ('^INDIAVIX', 1.0),  # SENSEX (use India VIX as proxy)
            'NIFTYBEES.NS': ('^INDIAVIX', 1.0),
            'BANKBEES.NS': ('^INDIAVIX', 1.2),  # Bank NIFTY is typically 1.2x
            
            # Dow Jones
            '^DJI': ('^VIX', 0.8),  # Dow is typically less volatile than S&P
            'DIA': ('^VIX', 0.8),
        }
        
        ticker_upper = ticker.upper()
        vix_info = vix_mapped.get(ticker_upper)
        
        # Check if it's an Indian stock (.NS or .BO suffix)
        is_indian_stock = ticker_upper.endswith('.NS') or ticker_upper.endswith('.BO')
        
        if vix_info:
            vix_ticker, multiplier = vix_info
            # Fetch VIX data
            vix_df = get_cached_prices(vix_ticker, f'{window_years}y')
            if not vix_df.empty and len(vix_df) > 60:
                iv_source = vix_ticker
                # VIX is in percentage points, convert to decimal and apply multiplier
                iv_series = (vix_df['Close'] / 100.0) * multiplier
                if multiplier != 1.0:
                    iv_source = f'{vix_ticker} (×{multiplier})'
        
        # For Indian stocks not in map, use India VIX with beta adjustment vs NIFTY
        elif is_indian_stock and iv_series is None:
            # Fetch India VIX and NIFTY 50 for beta calculation
            india_vix_df = get_cached_prices('^INDIAVIX', f'{window_years}y')
            nifty_df = get_cached_prices('^NSEI', f'{window_years}y')
            
            if not india_vix_df.empty and not nifty_df.empty and len(india_vix_df) > 60:
                # Calculate beta vs NIFTY 50
                nifty_returns = log_returns(nifty_df['Close'])
                stock_returns_aligned = returns
                
                # Align dates
                common_idx = nifty_returns.index.intersection(stock_returns_aligned.index)
                if len(common_idx) > 60:
                    nifty_ret = nifty_returns.reindex(common_idx).dropna()
                    stock_ret = stock_returns_aligned.reindex(common_idx).dropna()
                    
                    # Re-align
                    final_idx = nifty_ret.index.intersection(stock_ret.index)
                    nifty_ret = nifty_ret.reindex(final_idx)
                    stock_ret = stock_ret.reindex(final_idx)
                    
                    if len(final_idx) > 60:
                        # Calculate beta vs NIFTY
                        cov = stock_ret.rolling(60).cov(nifty_ret)
                        var_nifty = nifty_ret.rolling(60).var()
                        rolling_beta = cov / var_nifty
                        
                        current_beta = rolling_beta.dropna().iloc[-1] if len(rolling_beta.dropna()) > 0 else 1.0
                        current_beta = np.clip(current_beta, 0.3, 3.0)
                        beta_used = float(current_beta)
                        
                        # Apply beta to India VIX
                        india_vix_decimal = india_vix_df['Close'] / 100.0
                        iv_series = india_vix_decimal * current_beta
                        iv_source = f'^INDIAVIX × β={current_beta:.2f}'
        
        # For ALL OTHER TICKERS (US, Europe, etc.): Use Beta-Adjusted VIX vs SPY
        if iv_series is None:
            # Fetch VIX and SPY for beta calculation
            vix_df = get_cached_prices('^VIX', f'{window_years}y')
            spy_df = get_cached_prices('SPY', f'{window_years}y')
            
            if not vix_df.empty and not spy_df.empty and len(vix_df) > 60:
                # Calculate beta vs SPY
                spy_returns = log_returns(spy_df['Close'])
                stock_returns = returns
                
                # Align dates
                common_idx = spy_returns.index.intersection(stock_returns.index)
                if len(common_idx) > 60:
                    spy_ret_aligned = spy_returns.reindex(common_idx).dropna()
                    stock_ret_aligned = stock_returns.reindex(common_idx).dropna()
                    
                    # Re-align after dropna
                    final_idx = spy_ret_aligned.index.intersection(stock_ret_aligned.index)
                    spy_ret_aligned = spy_ret_aligned.reindex(final_idx)
                    stock_ret_aligned = stock_ret_aligned.reindex(final_idx)
                    
                    if len(final_idx) > 60:
                        # Calculate rolling beta (60-day)
                        cov = stock_ret_aligned.rolling(60).cov(spy_ret_aligned)
                        var_spy = spy_ret_aligned.rolling(60).var()
                        rolling_beta = cov / var_spy
                        
                        # Current beta (last valid value)
                        current_beta = rolling_beta.dropna().iloc[-1] if len(rolling_beta.dropna()) > 0 else 1.0
                        current_beta = np.clip(current_beta, 0.3, 3.0)  # Reasonable bounds
                        beta_used = float(current_beta)
                        
                        # Apply beta adjustment to VIX
                        vix_decimal = vix_df['Close'] / 100.0
                        
                        # Use rolling beta for historical IV, constant beta for simplicity
                        iv_series = vix_decimal * current_beta
                        iv_source = f'^VIX × β={current_beta:.2f}'
        
        # Fallback: Try to get current ATM IV from options chain
        current_atm_iv = None
        if iv_series is None or len(iv_series) == 0:
            try:
                tk = yf.Ticker(ticker)
                expirations = tk.options
                if expirations and len(expirations) > 0:
                    # Get nearest expiration
                    exp = expirations[0]
                    chain = tk.option_chain(exp)
                    spot = df['Close'].iloc[-1]
                    
                    # Find ATM calls
                    calls = chain.calls
                    if not calls.empty and 'strike' in calls.columns and 'impliedVolatility' in calls.columns:
                        calls['distance'] = abs(calls['strike'] - spot)
                        atm_calls = calls.nsmallest(3, 'distance')
                        valid_iv = atm_calls['impliedVolatility'].dropna()
                        if len(valid_iv) > 0:
                            current_atm_iv = float(valid_iv.mean())
                            iv_source = 'options_chain'
            except Exception as e:
                logger.debug(f"Could not fetch options for {ticker}: {e}")
        
        # If we have VIX-based IV, align with RV dates
        if iv_series is not None and len(iv_series) > 0:
            # Align dates
            common_idx = rv_20.index.intersection(iv_series.index)
            if len(common_idx) < 20:
                # Not enough overlap, try forward fill
                iv_series = iv_series.reindex(rv_20.index, method='ffill')
                common_idx = rv_20.index
            
            iv_aligned = iv_series.reindex(common_idx)
            rv_aligned = rv_20.reindex(common_idx)
            
            # IV-RV Spread calculation
            spread = iv_aligned - rv_aligned  # Positive = IV > RV (expensive options)
            spread_pct = (spread / rv_aligned) * 100  # Spread as percentage of RV
            
            # Z-score of spread
            spread_zscore = robust_zscore(spread.dropna())
            
            # Volatility Risk Premium (VRP) - historical average spread
            vrp = spread.rolling(60).mean()
            
            current_iv = float(iv_aligned.iloc[-1]) if len(iv_aligned) > 0 and not pd.isna(iv_aligned.iloc[-1]) else None
            current_rv = float(rv_aligned.iloc[-1]) if len(rv_aligned) > 0 else None
            current_spread = float(spread.iloc[-1]) if len(spread) > 0 and not pd.isna(spread.iloc[-1]) else None
            current_zscore = float(spread_zscore.iloc[-1]) if len(spread_zscore) > 0 and not pd.isna(spread_zscore.iloc[-1]) else 0
            
            # Signal interpretation
            if current_spread is not None:
                if current_spread > 0.05:  # IV > RV by 5%+
                    signal = 'IV Premium (Options Expensive)'
                    signal_color = 'warning'
                elif current_spread < -0.03:  # RV > IV by 3%+
                    signal = 'IV Discount (Options Cheap)'
                    signal_color = 'success'
                else:
                    signal = 'Fair Value'
                    signal_color = 'neutral'
            else:
                signal = 'Unknown'
                signal_color = 'neutral'
            
            return {
                'ticker': ticker,
                'dates': common_idx.strftime('%Y-%m-%d').tolist(),
                'iv': [float(x) if not pd.isna(x) else None for x in iv_aligned.values],
                'rv': [float(x) if not pd.isna(x) else None for x in rv_aligned.values],
                'spread': [float(x) if not pd.isna(x) else None for x in spread.values],
                'spread_pct': [float(x) if not pd.isna(x) else None for x in spread_pct.values],
                'zscore': [float(x) if not pd.isna(x) else 0 for x in spread_zscore.reindex(common_idx).fillna(0).values],
                'vrp': [float(x) if not pd.isna(x) else None for x in vrp.values],
                'current': {
                    'iv': current_iv,
                    'rv': current_rv,
                    'spread': current_spread,
                    'spread_pct': float((current_spread / current_rv) * 100) if current_spread and current_rv else None,
                    'zscore': current_zscore,
                    'signal': signal,
                    'signal_color': signal_color,
                },
                'stats': {
                    'mean_spread': float(spread.mean()) if len(spread) > 0 else 0,
                    'std_spread': float(spread.std()) if len(spread) > 0 else 0,
                    'mean_vrp': float(vrp.iloc[-1]) if len(vrp) > 0 and not pd.isna(vrp.iloc[-1]) else 0,
                    'pct_iv_premium': float((spread > 0).sum() / len(spread) * 100) if len(spread) > 0 else 50,
                },
                'iv_source': iv_source,
                'meta': {
                    'data_points': len(common_idx),
                    'start': common_idx[0].strftime('%Y-%m-%d') if len(common_idx) > 0 else None,
                    'end': common_idx[-1].strftime('%Y-%m-%d') if len(common_idx) > 0 else None,
                }
            }
        
        # Fallback: Point-in-time IV from options
        elif current_atm_iv is not None:
            current_rv = float(rv_20.iloc[-1]) if len(rv_20) > 0 else None
            current_spread = current_atm_iv - current_rv if current_rv else None
            
            signal = 'Unknown'
            signal_color = 'neutral'
            if current_spread is not None:
                if current_spread > 0.05:
                    signal = 'IV Premium (Options Expensive)'
                    signal_color = 'warning'
                elif current_spread < -0.03:
                    signal = 'IV Discount (Options Cheap)'
                    signal_color = 'success'
                else:
                    signal = 'Fair Value'
                    signal_color = 'neutral'
            
            return {
                'ticker': ticker,
                'point_in_time': True,
                'current': {
                    'iv': current_atm_iv,
                    'rv': current_rv,
                    'spread': current_spread,
                    'spread_pct': float((current_spread / current_rv) * 100) if current_spread and current_rv else None,
                    'signal': signal,
                    'signal_color': signal_color,
                },
                'iv_source': iv_source,
                'warning': 'Historical IV data not available. Showing current ATM IV from options chain only.',
                'meta': {
                    'data_points': 1,
                }
            }
        
        else:
            # No IV data available
            return {
                'unavailable': True,
                'reason': f'No options data or VIX proxy available for {ticker}. IV-RV spread requires options chain access or a VIX-mapped ticker (SPY, QQQ, IWM).',
                'ticker': ticker,
            }
            
    except Exception as e:
        logger.error(f"IV-RV Spread error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 4: CLUSTER DETECTOR
# =============================================================================

def compute_cluster_detector(ticker: str, window_years: int = 2) -> Dict:
    """Feature 4: Volatility Cluster Detector"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        
        # Threshold using robust statistics
        med = rv_20.median()
        mad = np.median(np.abs(rv_20 - med))
        threshold = med + 2 * 1.4826 * mad
        
        # Identify clusters
        above = rv_20 > threshold
        clusters = []
        current_cluster = None
        
        dates_list = rv_20.index.tolist()
        for i, (date, is_above) in enumerate(zip(dates_list, above)):
            if is_above:
                if current_cluster is None:
                    current_cluster = {'start': date, 'start_idx': i}
            else:
                if current_cluster is not None:
                    current_cluster['end'] = dates_list[i - 1]
                    current_cluster['duration'] = i - current_cluster['start_idx']
                    if current_cluster['duration'] >= 3:
                        clusters.append(current_cluster)
                    current_cluster = None
        
        if current_cluster is not None:
            current_cluster['end'] = dates_list[-1]
            current_cluster['duration'] = len(dates_list) - current_cluster['start_idx']
            current_cluster['ongoing'] = True
            if current_cluster['duration'] >= 3:
                clusters.append(current_cluster)
        
        durations = [c['duration'] for c in clusters if not c.get('ongoing')]
        
        return {
            'ticker': ticker,
            'dates': rv_20.index.strftime('%Y-%m-%d').tolist(),
            'rv_20': [float(x) for x in rv_20.values],
            'threshold': float(threshold),
            'clusters': [
                {
                    'start': c['start'].strftime('%Y-%m-%d'),
                    'end': c['end'].strftime('%Y-%m-%d'),
                    'duration': c['duration'],
                    'ongoing': c.get('ongoing', False)
                } for c in clusters
            ],
            'stats': {
                'count': len(clusters),
                'avg_duration': float(np.mean(durations)) if durations else 0,
                'max_duration': max(durations) if durations else 0,
                'current_in_cluster': clusters[-1].get('ongoing', False) if clusters else False
            },
            'meta': {
                'data_points': len(rv_20),
            }
        }
    except Exception as e:
        logger.error(f"Cluster detector error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 5: VOLATILITY Z-SCORE
# =============================================================================

def compute_zscore(ticker: str, window_years: int = 2) -> Dict:
    """Feature 5: Volatility Z-Score"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        
        z = robust_zscore(rv_20)
        percentile = rv_20.rank(pct=True)
        
        return {
            'ticker': ticker,
            'dates': rv_20.index.strftime('%Y-%m-%d').tolist(),
            'rv_20': [float(x) for x in rv_20.values],
            'zscore': [float(x) for x in z.values],
            'percentile': [float(x) for x in percentile.values],
            'current': {
                'zscore': float(z.iloc[-1]),
                'percentile': float(percentile.iloc[-1]),
                'rv_20': float(rv_20.iloc[-1])
            },
            'meta': {
                'data_points': len(rv_20),
            }
        }
    except Exception as e:
        logger.error(f"Z-score error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 6: VOLATILITY REGIME CLASSIFIER
# =============================================================================

def compute_regime_classifier(ticker: str, window_years: int = 2) -> Dict:
    """Feature 6: Volatility Regime Classifier"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        
        # Percentile-based classification
        pct = rv_20.rank(pct=True)
        
        def classify(p):
            if p < 0.15:
                return 0  # Low
            elif p < 0.60:
                return 1  # Normal
            elif p < 0.85:
                return 2  # Elevated
            else:
                return 3  # Crisis
        
        regime = pct.apply(classify)
        
        # Smoothed (5d trailing mode)
        regime_smooth = regime.rolling(5).apply(lambda x: stats.mode(x, keepdims=False)[0])
        
        # Probabilities
        probs = pd.DataFrame(index=rv_20.index)
        for i, r in enumerate(['low', 'normal', 'elevated', 'crisis']):
            probs[r] = (regime == i).rolling(20).mean()
        
        current_regime = int(regime_smooth.iloc[-1]) if len(regime_smooth) > 0 else 1
        
        return {
            'ticker': ticker,
            'dates': rv_20.index.strftime('%Y-%m-%d').tolist(),
            'regime': [int(x) if not pd.isna(x) else 1 for x in regime_smooth.values],
            'probabilities': {
                'low': [float(x) if not pd.isna(x) else 0 for x in probs['low'].values],
                'normal': [float(x) if not pd.isna(x) else 1 for x in probs['normal'].values],
                'elevated': [float(x) if not pd.isna(x) else 0 for x in probs['elevated'].values],
                'crisis': [float(x) if not pd.isna(x) else 0 for x in probs['crisis'].values],
            },
            'current': {
                'regime': current_regime,
                'regime_label': ['Low', 'Normal', 'Elevated', 'Crisis'][current_regime],
                'confidence': float(max(probs.iloc[-1])) if len(probs) > 0 else 0.5
            },
            'meta': {
                'data_points': len(rv_20),
            }
        }
    except Exception as e:
        logger.error(f"Regime classifier error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 7: MACRO-LINKED MODEL
# =============================================================================

def compute_macro_model(ticker: str, window_years: int = 2) -> Dict:
    """Feature 7: Macro-Linked Vol Model"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 100:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        ewma = ewma_vol(returns).reindex(rv_20.index)
        vvol = rv_20.rolling(20).std()
        
        # Drawdown
        price = df['Close'].reindex(rv_20.index)
        peak = price.expanding().max()
        drawdown = (price - peak) / peak
        
        # Fetch real macro data
        macro_names = ["VIX", "RATES", "CREDIT", "USD", "YC_SLOPE"]
        macro_df = research_data.get_macro_series(macro_names, window_years * 252)
        
        if macro_df.empty:
            return {'error': 'Failed to load macro factors for model'}
            
        # Align macro data with rv_20
        # Calculate daily changes for macro (returns or diffs)
        macro_changes = macro_df.pct_change().fillna(0)
        # Replace Inf/-Inf with 0 to prevent sklearn errors
        macro_changes = macro_changes.replace([np.inf, -np.inf], 0)
        
        # Build feature matrix using real macro signals
        X_df = pd.DataFrame(index=rv_20.index)
        for col in macro_changes.columns:
            X_df[col] = macro_changes[col].reindex(rv_20.index).ffill().fillna(0)
            
        # Add lagged vol as a control (use ffill, not bfill to avoid forward-looking bias)
        X_df['vol_lag'] = rv_20.shift(1).ffill()
        X_df['drawdown'] = drawdown.shift(1).abs().ffill().fillna(0)
        
        X = X_df.dropna()
        # Also clean Inf from X just in case
        X = X.replace([np.inf, -np.inf], 0)
        y = rv_20.reindex(X.index)
        
        if len(X) < 60:
            return {'error': 'Insufficient data for model'}
        
        from sklearn.linear_model import Ridge
        model = Ridge(alpha=0.1)
        model.fit(X, y)
        
        pred = model.predict(X)
        residuals = y.values - pred
        
        return {
            'ticker': ticker,
            'dates': X.index.strftime('%Y-%m-%d').tolist(),
            'observed': [float(x) for x in y.values],
            'predicted': [float(x) for x in pred],
            'residuals': [float(x) for x in residuals],
            'coefficients': dict(zip(X.columns, [float(x) for x in model.coef_])),
            'r_squared': float(model.score(X, y)),
            'rmse': float(np.sqrt(np.mean(residuals ** 2))),
            'meta': {
                'data_points': len(X),
            }
        }
    except Exception as e:
        logger.error(f"Macro model error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 8: FORECAST CONE
# =============================================================================

def compute_forecast_cone(ticker: str, horizon: int = 20) -> Dict:
    """Feature 8: Volatility Forecast Cone"""
    df = get_cached_prices(ticker, '2y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 100:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20)
        current_vol = float(rv_20.iloc[-1])
        
        # --- SOLUTION 2: VOL-CLUSTERING FIX (CIRCULAR BLOCK BOOTSTRAP) ---
        # Instead of i.i.d. sampling, we sample chunks of days to preserve volatility clusters
        n_paths = 500
        block_size = 5
        n_blocks = int(np.ceil(horizon / block_size))
        
        # Use last 60 days for bootstrap pool
        recent_returns = returns.tail(60).values
        
        # Bootstrap paths
        paths = np.zeros((n_paths, horizon))
        for i in range(n_paths):
            path = []
            for _ in range(n_blocks):
                # Pick a random 5-day window from recent history
                start_idx = np.random.randint(0, len(recent_returns) - block_size)
                path.extend(recent_returns[start_idx : start_idx + block_size])
            paths[i] = np.array(path[:horizon])
        
        # Compute EXPANDING vol for each path (gives horizon points instead of just 1)
        # This shows cumulative volatility building up over the forecast period
        path_vols = np.zeros((n_paths, horizon))
        for i in range(n_paths):
            for j in range(horizon):
                # Use at least 5 days for std, otherwise just use what we have
                window_size = max(5, j + 1)
                start_idx = max(0, j + 1 - window_size)
                path_vols[i, j] = np.std(paths[i, start_idx:j+1]) * np.sqrt(252)
        
        # Quantiles at each horizon step
        bands = {}
        for q in [10, 25, 50, 75, 90]:
            bands[f'q_{q}'] = [float(x) for x in np.percentile(path_vols, q, axis=0)]
        
        forecast_dates = [(datetime.now() + timedelta(days=i+1)).strftime('%Y-%m-%d') 
                          for i in range(horizon)]
        
        return {
            'ticker': ticker,
            'horizon_days': horizon,
            'current_vol': current_vol,
            'bands': bands,
            'forecast_dates': forecast_dates,
            'meta': {
                'n_simulations': n_paths,
            }
        }
    except Exception as e:
        logger.error(f"Forecast cone error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 9: GRAVITY WELL
# =============================================================================

def compute_gravity_well(ticker: str, window_years: int = 2) -> Dict:
    """Feature 9: Volatility Gravity Well (2D)"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20).dropna()
        
        price = df['Close'].reindex(rv_20.index)
        
        # Trapping probability
        trap_prob = pd.Series(0.5, index=rv_20.index)
        for i in range(len(rv_20) - 20):
            band = 2 * rv_20.iloc[i] * price.iloc[i] / np.sqrt(252)
            future_prices = price.iloc[i:i+20]
            within_band = np.abs(future_prices - price.iloc[i]) <= band
            trap_prob.iloc[i] = float(within_band.sum()) / 20
        
        # Gravity intensity
        max_rv = rv_20.max()
        gravity = 100 * trap_prob * (rv_20 / max_rv)
        
        return {
            'ticker': ticker,
            'dates': rv_20.index.strftime('%Y-%m-%d').tolist(),
            'gravity_intensity': [float(x) for x in gravity.values],
            'trapping_probability': [float(x) for x in trap_prob.values],
            'rv_20': [float(x) for x in rv_20.values],
            'meta': {
                'data_points': len(rv_20),
            }
        }
    except Exception as e:
        logger.error(f"Gravity well error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 10: FRACTURE MAP
# =============================================================================

def compute_fracture_map(ticker: str, window_years: int = 2) -> Dict:
    """Feature 10: Temporal Volatility Fracture Map"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 120:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        
        # Multi-scale signals
        rv_5 = realized_vol(returns, 5)
        rv_20 = realized_vol(returns, 20)
        rv_60 = realized_vol(returns, 60)
        
        # Valid index after longest window
        valid_idx = rv_60.dropna().index
        
        short_signal = robust_zscore(rv_5.diff()).reindex(valid_idx).fillna(0)
        mid_signal = robust_zscore(rv_20.diff()).reindex(valid_idx).fillna(0)
        long_signal = robust_zscore(rv_60.diff()).reindex(valid_idx).fillna(0)
        
        # Fracture score
        fracture = 1 / (1 + np.exp(-(short_signal + mid_signal - long_signal)))
        alignment = fracture.rolling(5).mean() * 100
        
        return {
            'ticker': ticker,
            'dates': valid_idx.strftime('%Y-%m-%d').tolist(),
            'short_signal': [float(x) for x in short_signal.values],
            'mid_signal': [float(x) for x in mid_signal.values],
            'long_signal': [float(x) for x in long_signal.values],
            'fracture': [float(x) for x in fracture.fillna(0.5).values],
            'alignment': [float(x) for x in alignment.fillna(50).values],
            'meta': {
                'data_points': len(valid_idx),
            }
        }
    except Exception as e:
        logger.error(f"Fracture map error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 11: ENERGY RESERVOIR
# =============================================================================

def compute_energy_reservoir(ticker: str, window_years: int = 2) -> Dict:
    """Feature 11: Volatility Energy Reservoir"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 120:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        rv_20 = realized_vol(returns, 20)
        rv_5 = realized_vol(returns, 5)
        
        # Valid index
        valid_idx = rv_20.dropna().index[-len(rv_20.dropna()):]
        rv_20 = rv_20.reindex(valid_idx)
        rv_5 = rv_5.reindex(valid_idx)
        
        # Compression
        rv_max_120 = rv_20.rolling(120).max()
        compression = 1 - (rv_20 / rv_max_120)
        compression = compression.fillna(0)
        
        # Range tightness (proxy)
        atr = returns.abs().rolling(14).mean().reindex(valid_idx) * np.sqrt(252)
        atr_max_120 = atr.rolling(120).max()
        range_tight = 1 - (atr / atr_max_120)
        range_tight = range_tight.fillna(0)
        
        # Inflow/Outflow
        inflow = np.maximum(0, compression + range_tight - 1)
        outflow = rv_5.rank(pct=True).fillna(0.5)
        
        # Reservoir level
        reservoir = np.zeros(len(valid_idx))
        for i in range(1, len(reservoir)):
            prev = reservoir[i-1]
            new_val = prev + inflow.iloc[i] - outflow.iloc[i]
            reservoir[i] = np.clip(new_val, 0, 1)
        
        reservoir_pct = reservoir * 100
        fill_rate = np.gradient(reservoir, 5)
        
        return {
            'ticker': ticker,
            'dates': valid_idx.strftime('%Y-%m-%d').tolist(),
            'reservoir': [float(x) for x in reservoir_pct],
            'compression': [float(x) for x in compression.values],
            'range_tightness': [float(x) for x in range_tight.values],
            'fill_rate': [float(x) for x in fill_rate],
            'current_level': float(reservoir_pct[-1]),
            'meta': {
                'data_points': len(valid_idx),
            }
        }
    except Exception as e:
        logger.error(f"Energy reservoir error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 12: SYMMETRY BREAK
# =============================================================================

def compute_symmetry_break(ticker: str, window_years: int = 2) -> Dict:
    """Feature 12: Volatility Symmetry Break Index"""
    df = get_cached_prices(ticker, f'{window_years}y')
    
    if df.empty:
        return {'error': f'No data available for {ticker}'}
    
    if len(df) < 60:
        return {'error': f'Insufficient data for {ticker}'}
    
    try:
        returns = log_returns(df['Close'])
        
        # Semi-volatilities - use rolling apply to handle sparse data properly
        def downside_vol(x):
            neg_returns = x[x < 0]
            if len(neg_returns) >= 5:
                return np.std(neg_returns) * np.sqrt(252)
            return np.nan
        
        def upside_vol(x):
            pos_returns = x[x > 0]
            if len(pos_returns) >= 5:
                return np.std(pos_returns) * np.sqrt(252)
            return np.nan
        
        rv_down = returns.rolling(40).apply(downside_vol, raw=True)
        rv_up = returns.rolling(40).apply(upside_vol, raw=True)
        
        # Valid index - require both to have values
        valid_mask = rv_down.notna() & rv_up.notna()
        valid_idx = rv_down[valid_mask].index
        
        if len(valid_idx) < 20:
            # Fallback: use simple realized vol split
            rv_20 = realized_vol(returns, 20).dropna()
            
            # Approximate semi-vol from skewness
            skew = returns.rolling(40).skew().reindex(rv_20.index).fillna(0)
            
            # Negative skew = more downside risk
            sym = -skew / 3  # Scale to roughly -1 to 1
            sym = sym.clip(-1, 1)
            
            valid_idx = rv_20.index
            rv_down = rv_20 * (1 + sym * 0.2)  # Approximate
            rv_up = rv_20 * (1 - sym * 0.2)
        else:
            rv_down = rv_down.reindex(valid_idx)
            rv_up = rv_up.reindex(valid_idx)
            
            # Symmetry index: -1 = upside dominant, +1 = downside dominant
            sym = (rv_down - rv_up) / (rv_down + rv_up + 1e-10)
            sym = sym.fillna(0)
        
        # Breakpoints
        delta_sym = sym.diff()
        mad_delta = np.median(np.abs(delta_sym.dropna() - delta_sym.median()))
        if mad_delta == 0:
            mad_delta = delta_sym.std() + 1e-10
        breakpoints = np.abs(delta_sym) > 2 * 1.4826 * mad_delta
        
        current_sym = float(sym.iloc[-1]) if len(sym) > 0 else 0
        
        return {
            'ticker': ticker,
            'dates': valid_idx.strftime('%Y-%m-%d').tolist(),
            'symmetry_index': [float(x) for x in sym.values],
            'rv_down': [float(x) for x in rv_down.values],
            'rv_up': [float(x) for x in rv_up.values],
            'breakpoints': [bool(x) for x in breakpoints.fillna(False).values],
            'current': {
                'symmetry': current_sym,
                'interpretation': 'Downside dominant' if current_sym > 0.1 else 
                                 'Upside dominant' if current_sym < -0.1 else 'Balanced'
            },
            'meta': {
                'data_points': len(valid_idx),
            }
        }
    except Exception as e:
        logger.error(f"Symmetry break error for {ticker}: {e}")
        return {'error': str(e)}


# =============================================================================
# FEATURE 13: TRANSMISSION ENGINE
# =============================================================================

def compute_transmission_engine(tickers: List[str] = None) -> Dict:
    """Feature 13: Volatility Transmission Engine"""
    if tickers is None:
        tickers = ['SPY', 'TLT', 'UUP', 'LQD']
    
    try:
        # Load all data
        vol_data = {}
        for t in tickers:
            df = get_cached_prices(t, '2y')
            if not df.empty and len(df) > 60:
                returns = log_returns(df['Close'])
                vol_data[t] = realized_vol(returns, 20)
        
        if len(vol_data) < 2:
            return {'error': 'Insufficient data for network'}
        
        # Common index
        common_idx = None
        for v in vol_data.values():
            if common_idx is None:
                common_idx = v.dropna().index
            else:
                common_idx = common_idx.intersection(v.dropna().index)
        
        for t in vol_data:
            vol_data[t] = vol_data[t].reindex(common_idx)
        
        # Lead-lag correlations
        edges = []
        max_lag = 10
        confidence_threshold = 0.5
        
        for t1 in vol_data:
            for t2 in vol_data:
                if t1 == t2:
                    continue
                
                v1 = vol_data[t1].values
                v2 = vol_data[t2].values
                
                best_corr = 0
                best_lag = 0
                for lag in range(1, max_lag + 1):
                    if lag < len(v1):
                        corr = np.corrcoef(v1[:-lag], v2[lag:])[0, 1]
                        if not np.isnan(corr) and abs(corr) > abs(best_corr):
                            best_corr = corr
                            best_lag = lag
                
                if best_lag > 0 and abs(best_corr) > confidence_threshold:
                    edges.append({
                        'source': t1,
                        'target': t2,
                        'lag_days': best_lag,
                        'correlation': round(best_corr, 3),
                        'confidence': round(abs(best_corr), 2)
                    })
        
        # Sort by confidence and limit to top 3
        edges.sort(key=lambda x: x['confidence'], reverse=True)
        edges = edges[:3]
        
        return {
            'nodes': list(vol_data.keys()),
            'edges': edges,
            'warning': 'Lead-lag tendencies only. Not causal claims.',
            'meta': {
                'data_points': len(common_idx) if common_idx is not None else 0,
            }
        }
    except Exception as e:
        logger.error(f"Transmission engine error: {e}")
        return {'error': str(e)}
