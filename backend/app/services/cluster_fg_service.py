"""
Cluster FG Service
Core math and orchestration for FG1-FG9 features.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

EPSILON = 1e-8


# =============================================================================
# SHARED MATH UTILITIES
# =============================================================================

def compute_returns(close: pd.Series, method: str = "simple") -> pd.Series:
    """
    Compute returns from close prices.
    method: 'simple' for (p_t - p_{t-1})/p_{t-1}, 'log' for ln(p_t/p_{t-1})
    """
    if method == "log":
        return np.log(close / close.shift(1))
    return close.pct_change()


def compute_zscore(series: pd.Series) -> float:
    """
    Compute z-score of the last value vs the series.
    If std is 0, return 0.
    """
    mean_val = series.mean()
    std_val = series.std()
    if std_val < EPSILON:
        return 0.0
    return float((series.iloc[-1] - mean_val) / std_val)


def compute_zscore_series(series: pd.Series, window: int) -> pd.Series:
    """Rolling z-score over window."""
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    return (series - rolling_mean) / (rolling_std + EPSILON)


def percentile_rank(value: float, series: pd.Series) -> float:
    """
    Compute percentile rank of value within series.
    Returns 0 to 1.
    """
    n = len(series)
    if n <= 1:
        return 0.5
    rank = (series < value).sum()
    return float(rank / (n - 1))


def percentile_rank_last(series: pd.Series) -> float:
    """Percentile rank of the last value."""
    return percentile_rank(series.iloc[-1], series)


def rolling_volatility(returns: pd.Series, window: int, annualize: bool = True) -> pd.Series:
    """Rolling volatility (std of returns)."""
    vol = returns.rolling(window).std()
    if annualize:
        return vol * np.sqrt(252)
    return vol


def compute_covariance(x: pd.Series, y: pd.Series) -> float:
    """Compute covariance between two series."""
    common_idx = x.index.intersection(y.index)
    if len(common_idx) < 2:
        return 0.0
    return float(x.loc[common_idx].cov(y.loc[common_idx]))


def compute_correlation(x: pd.Series, y: pd.Series) -> float:
    """Compute correlation between two series."""
    common_idx = x.index.intersection(y.index)
    if len(common_idx) < 2:
        return 0.0
    return float(x.loc[common_idx].corr(y.loc[common_idx]))


def clip_to_range(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clip value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


# =============================================================================
# FG1: CROSS ASSET FLOW HEATMAP
# =============================================================================

def compute_flow_heatmap(
    price_data: Dict[str, pd.DataFrame],
    groups: List[str],
    tickers_by_group: Dict[str, List[str]],
    lookback_days: int = 60,
    volume_window: int = 20,
    vol_window: int = 21,
    weights: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Compute flow heatmap scores per asset group.
    
    Args:
        price_data: Dict of ticker -> DataFrame with Close, Volume columns
        groups: List of group names
        tickers_by_group: Mapping of group -> list of tickers
        lookback_days: Lookback period for calculations
        volume_window: Window for volume z-score
        vol_window: Window for volatility calculation
        weights: Optional dict with 'alpha', 'beta', 'gamma' weights
    
    Returns:
        Dict with groups, details, meta
    """
    if weights is None:
        weights = {"alpha": 0.5, "beta": 0.3, "gamma": 0.2}
    
    alpha = weights.get("alpha", 0.5)
    beta = weights.get("beta", 0.3)
    gamma = weights.get("gamma", 0.2)
    
    details = []
    group_scores = []
    
    for group in groups:
        tickers = tickers_by_group.get(group, [])
        group_ret_scores = []
        group_vol_zs = []
        group_vol_changes = []
        
        for ticker in tickers:
            if ticker not in price_data:
                continue
            
            ticker_data = price_data[ticker]
            
            # Handle both dict and DataFrame formats
            if isinstance(ticker_data, dict):
                close = ticker_data.get("Close")
                volume = ticker_data.get("Volume")
                if close is None or len(close) == 0:
                    continue
                if len(close) < lookback_days:
                    continue
                # Use last lookback_days
                close = close.tail(lookback_days)
                volume = volume.tail(lookback_days) if volume is not None else pd.Series([0] * len(close), index=close.index)
            else:
                # DataFrame format
                if hasattr(ticker_data, 'empty') and ticker_data.empty:
                    continue
                if len(ticker_data) < lookback_days:
                    continue
                df = ticker_data.tail(lookback_days).copy()
                close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
                volume = df["Volume"] if "Volume" in df.columns else pd.Series([0] * len(df))
            
            # Returns
            returns = compute_returns(close, "simple").dropna()
            if len(returns) < 10:
                continue
            
            # Cumulative return over period
            cum_ret = (1 + returns).prod() - 1
            
            # Return score: percentile rank of cum_ret vs rolling cumulative returns
            ret_score = percentile_rank_last(returns.rolling(vol_window).apply(lambda x: (1 + x).prod() - 1, raw=False).dropna())
            
            # Volume z-score
            if volume is not None and volume.sum() > 0:
                vol_z = compute_zscore(volume.tail(volume_window))
            else:
                vol_z = 0.0
            
            # Volatility change
            if len(returns) >= 2 * vol_window:
                rv_recent = returns.tail(vol_window).std()
                rv_past = returns.iloc[-2*vol_window:-vol_window].std()
                if rv_past > EPSILON:
                    vol_change = (rv_recent - rv_past) / rv_past
                else:
                    vol_change = 0.0
            else:
                vol_change = 0.0
            
            details.append({
                "ticker": ticker,
                "group": group,
                "ret_score": round(ret_score, 3),
                "vol_z": round(vol_z, 2),
                "vol_change": round(vol_change, 3),
                "cum_return": round(cum_ret, 4)
            })
            
            group_ret_scores.append(ret_score)
            group_vol_zs.append(vol_z)
            group_vol_changes.append(vol_change)
        
        # Aggregate group score
        if group_ret_scores:
            avg_ret_score = np.mean(group_ret_scores)
            avg_vol_z = np.mean(group_vol_zs)
            avg_vol_change = np.mean(group_vol_changes)
            
            # Flow score formula
            flow_score = (
                alpha * avg_ret_score +
                beta * np.tanh(avg_vol_z) -
                gamma * max(0, -avg_vol_change)  # Negative vol_change is bad
            )
            
            # Normalize to -1 to 1 range
            flow_score = np.tanh(flow_score * 2 - 1)
            
            group_scores.append({
                "group": group,
                "flow_score": round(float(flow_score), 3),
                "avg_ret": round(float(avg_ret_score), 3),
                "avg_vol_z": round(float(avg_vol_z), 2)
            })
        else:
            group_scores.append({
                "group": group,
                "flow_score": 0.0,
                "avg_ret": 0.0,
                "avg_vol_z": 0.0
            })
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "groups": group_scores,
        "details": details,
        "meta": {
            "lookback_days": lookback_days,
            "cache_ttl_sec": 300
        }
    }


# =============================================================================
# FG2: LIQUIDITY STRESS RADAR
# =============================================================================

def compute_liquidity_stress(
    price_data: Dict[str, pd.DataFrame],
    tickers: List[str],
    benchmark: str = "SPY",
    lookback_days: int = 120,
    volume_window: int = 20,
    vol_window: int = 21,
    corr_window: int = 21
) -> Dict[str, Any]:
    """
    Compute liquidity stress metrics for given tickers.
    
    Returns overall stress score 0-100 and per-ticker breakdown.
    """
    per_ticker = []
    
    # Helper to get close series from ticker data
    def get_series(ticker_data, key):
        if isinstance(ticker_data, dict):
            return ticker_data.get(key)
        elif hasattr(ticker_data, 'columns') and key in ticker_data.columns:
            return ticker_data[key]
        return None
    
    # Get benchmark returns
    bench_returns = None
    if benchmark in price_data:
        bench_data = price_data[benchmark]
        bench_close = get_series(bench_data, "Close")
        if bench_close is not None and len(bench_close) > 0:
            bench_returns = compute_returns(bench_close, "simple").dropna()
    
    for ticker in tickers:
        if ticker not in price_data:
            continue
        
        ticker_data = price_data[ticker]
        
        # Handle both dict and DataFrame formats
        if isinstance(ticker_data, dict):
            close = ticker_data.get("Close")
            high = ticker_data.get("High")
            low = ticker_data.get("Low")
            volume = ticker_data.get("Volume")
            if close is None or len(close) == 0 or len(close) < lookback_days:
                continue
            # Use last lookback_days
            close = close.tail(lookback_days)
            high = high.tail(lookback_days) if high is not None else close
            low = low.tail(lookback_days) if low is not None else close
            volume = volume.tail(lookback_days) if volume is not None else pd.Series([0] * len(close), index=close.index)
        else:
            # DataFrame format
            if hasattr(ticker_data, 'empty') and ticker_data.empty:
                continue
            if len(ticker_data) < lookback_days:
                continue
            df = ticker_data.tail(lookback_days).copy()
            close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
            high = df["High"] if "High" in df.columns else close
            low = df["Low"] if "Low" in df.columns else close
            volume = df["Volume"] if "Volume" in df.columns else pd.Series([0] * len(df), index=df.index)
        
        returns = compute_returns(close, "simple").dropna()
        
        # 1. Volume stress (z-score)
        vol_z = compute_zscore(volume.tail(volume_window)) if volume is not None and volume.sum() > 0 else 0.0
        
        # 2. Spread proxy (intraday range %)
        intraday_range = (high - low) / (close + EPSILON)
        range_z = compute_zscore(intraday_range)
        
        # 3. Volatility spike
        if len(returns) >= 2 * vol_window:
            vol_recent = returns.tail(vol_window).std()
            vol_past = returns.iloc[-2*vol_window:-vol_window].std()
            if vol_past > EPSILON:
                vol_spike = (vol_recent - vol_past) / vol_past
            else:
                vol_spike = 0.0
        else:
            vol_spike = 0.0
        
        # 4. Correlation compression
        corr_change = 0.0
        if bench_returns is not None and len(returns) >= 2 * corr_window:
            common_idx = returns.index.intersection(bench_returns.index)
            if len(common_idx) >= 2 * corr_window:
                r_ticker = returns.loc[common_idx]
                r_bench = bench_returns.loc[common_idx]
                
                corr_recent = r_ticker.tail(corr_window).corr(r_bench.tail(corr_window))
                corr_past = r_ticker.iloc[-2*corr_window:-corr_window].corr(r_bench.iloc[-2*corr_window:-corr_window])
                
                if not np.isnan(corr_recent) and not np.isnan(corr_past):
                    corr_change = corr_recent - corr_past
        
        # Per-ticker stress score (0 to 1)
        stress = (
            0.3 * clip_to_range(vol_z / 3 + 0.5) +
            0.25 * clip_to_range(range_z / 3 + 0.5) +
            0.25 * clip_to_range(vol_spike + 0.5) +
            0.2 * clip_to_range(corr_change + 0.5)
        )
        
        per_ticker.append({
            "ticker": ticker,
            "stress": round(float(stress), 3),
            "vol_z": round(float(vol_z), 2),
            "range_z": round(float(range_z), 2),
            "vol_spike": round(float(vol_spike), 3),
            "corr_change": round(float(corr_change), 3)
        })
    
    # Aggregate stress score
    if per_ticker:
        avg_stress = np.mean([t["stress"] for t in per_ticker])
        stress_score = avg_stress * 100
    else:
        stress_score = 0.0
    
    # Label
    if stress_score < 20:
        label = "calm"
    elif stress_score < 40:
        label = "neutral"
    elif stress_score < 60:
        label = "elevated"
    elif stress_score < 80:
        label = "stressed"
    else:
        label = "extreme"
    
    # Component averages
    components = {
        "volume": {"avg_z": round(np.mean([t["vol_z"] for t in per_ticker]), 2) if per_ticker else 0, "stress": 0},
        "spread_proxy": {"avg_z": round(np.mean([t["range_z"] for t in per_ticker]), 2) if per_ticker else 0, "stress": 0},
        "vol_spike": {"avg": round(np.mean([t["vol_spike"] for t in per_ticker]), 3) if per_ticker else 0, "stress": 0},
        "corr_compression": {"avg": round(np.mean([t["corr_change"] for t in per_ticker]), 3) if per_ticker else 0, "stress": 0}
    }
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "stress_score": round(float(stress_score), 1),
        "label": label,
        "components": components,
        "per_ticker": per_ticker,
        "meta": {"cache_ttl_sec": 300}
    }


# =============================================================================
# FG3: RECESSION PROBABILITY MONITOR
# =============================================================================

def compute_recession_prob(
    macro_data: Dict[str, pd.Series],
    weights: Dict[str, float] = None,
    lookback_years: int = 20
) -> Dict[str, Any]:
    """
    Compute recession probability from macro factors.
    
    Args:
        macro_data: Dict with keys like 'yield_curve', 'credit_spread', 'macro_index', 'equity_vol'
        weights: Component weights
        lookback_years: Years of history for z-score calculation
    
    Returns:
        Recession probability and component breakdown
    """
    if weights is None:
        weights = {"yield_curve": 0.4, "credit": 0.2, "macro": 0.25, "equity_vol": 0.15}
    
    components = {}
    total_stress = 0.0
    total_weight = 0.0
    
    # Yield curve (negative slope = stress)
    if "yield_curve" in macro_data and len(macro_data["yield_curve"]) > 0:
        yc = macro_data["yield_curve"]
        current_slope = yc.iloc[-1]
        z_slope = compute_zscore(yc)
        
        # Inverted curve is stress
        stress_yield = clip_to_range((-z_slope + 3) / 6)
        
        components["yield_curve"] = {
            "slope": round(float(current_slope), 3),
            "z": round(float(z_slope), 2),
            "stress": round(float(stress_yield), 3),
            "weight": weights["yield_curve"]
        }
        total_stress += weights["yield_curve"] * stress_yield
        total_weight += weights["yield_curve"]
    
    # Credit spread (high spread = stress)
    if "credit_spread" in macro_data and len(macro_data["credit_spread"]) > 0:
        cs = macro_data["credit_spread"]
        current_spread = cs.iloc[-1]
        z_credit = compute_zscore(cs)
        
        stress_credit = clip_to_range((z_credit + 3) / 6)
        
        components["credit"] = {
            "spread": round(float(current_spread), 2),
            "z": round(float(z_credit), 2),
            "stress": round(float(stress_credit), 3),
            "weight": weights["credit"]
        }
        total_stress += weights["credit"] * stress_credit
        total_weight += weights["credit"]
    
    # Macro composite
    if "macro_index" in macro_data and len(macro_data["macro_index"]) > 0:
        mi = macro_data["macro_index"]
        z_macro = compute_zscore(mi)
        
        # Lower macro index = more stress
        stress_macro = clip_to_range((-z_macro + 3) / 6)
        
        components["macro"] = {
            "z": round(float(z_macro), 2),
            "stress": round(float(stress_macro), 3),
            "weight": weights["macro"]
        }
        total_stress += weights["macro"] * stress_macro
        total_weight += weights["macro"]
    
    # Equity volatility (high vol = stress)
    if "equity_vol" in macro_data and len(macro_data["equity_vol"]) > 0:
        ev = macro_data["equity_vol"]
        z_vol = compute_zscore(ev)
        
        stress_vol = clip_to_range((z_vol + 3) / 6)
        
        components["equity_vol"] = {
            "z": round(float(z_vol), 2),
            "stress": round(float(stress_vol), 3),
            "weight": weights["equity_vol"]
        }
        total_stress += weights["equity_vol"] * stress_vol
        total_weight += weights["equity_vol"]
    
    # Compute probability
    if total_weight > 0:
        normalized_stress = total_stress / total_weight
        # Quadratic mapping for more sensitivity at high stress
        recession_prob = clip_to_range(normalized_stress ** 1.5)
    else:
        recession_prob = 0.0
    
    # Label
    if recession_prob < 0.2:
        label = "low"
    elif recession_prob < 0.4:
        label = "moderate"
    elif recession_prob < 0.6:
        label = "elevated"
    elif recession_prob < 0.8:
        label = "high"
    else:
        label = "severe"
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "region": "US",
        "recession_prob": round(float(recession_prob), 3),
        "label": label,
        "components": components,
        "history": [],  # Would be filled with historical calculations
        "meta": {"lookback_years": lookback_years, "cache_ttl_sec": 600}
    }


# =============================================================================
# FG4: DRAWDOWN ANATOMY
# =============================================================================

def compute_drawdown_anatomy(
    close: pd.Series,
    lookback_years: int = 5,
    min_drawdown: float = 0.1,
    max_events: int = 10
) -> Dict[str, Any]:
    """
    Identify and analyze major drawdown episodes.
    
    Returns list of drawdown episodes with depth, length, speed, recovery.
    """
    if close.empty:
        return {"episodes": [], "series": [], "meta": {}}
    
    # Ensure we have a clean series
    close = close.dropna()
    if len(close) < 20:
        return {"episodes": [], "series": [], "meta": {}}
    
    # Running peak
    peak = close.cummax()
    
    # Drawdown series
    dd = (close - peak) / peak
    
    # Find drawdown episodes
    episodes = []
    in_drawdown = False
    episode_start = None
    episode_peak_date = None
    episode_trough_date = None
    episode_trough_value = 0.0
    
    for i, (date, dd_val) in enumerate(dd.items()):
        if not in_drawdown and dd_val < -0.01:  # Start of drawdown
            in_drawdown = True
            # Find the peak date (when we were at peak)
            peak_val = peak.loc[date]
            peak_dates = close[close == peak_val].index
            episode_peak_date = peak_dates[-1] if len(peak_dates) > 0 else date
            episode_start = date
            episode_trough_date = date
            episode_trough_value = dd_val
        
        elif in_drawdown:
            if dd_val < episode_trough_value:
                episode_trough_date = date
                episode_trough_value = dd_val
            
            if dd_val >= -0.005:  # Recovery (close to peak)
                # Episode complete
                if abs(episode_trough_value) >= min_drawdown:
                    length_to_trough = (episode_trough_date - episode_peak_date).days
                    length_recovery = (date - episode_trough_date).days
                    speed = episode_trough_value / max(length_to_trough, 1)
                    
                    # Type classification
                    if length_to_trough < 30 and abs(episode_trough_value) > 0.15:
                        dd_type = "shock"
                    else:
                        dd_type = "bleed"
                    
                    episodes.append({
                        "peak_date": episode_peak_date.strftime("%Y-%m-%d"),
                        "trough_date": episode_trough_date.strftime("%Y-%m-%d"),
                        "recovery_date": date.strftime("%Y-%m-%d"),
                        "depth": round(float(episode_trough_value), 4),
                        "length_peak_to_trough": int(length_to_trough),
                        "length_recovery": int(length_recovery),
                        "speed": round(float(speed), 4),
                        "type": dd_type
                    })
                
                in_drawdown = False
    
    # Handle ongoing drawdown
    if in_drawdown and abs(episode_trough_value) >= min_drawdown:
        length_to_trough = (episode_trough_date - episode_peak_date).days
        speed = episode_trough_value / max(length_to_trough, 1)
        dd_type = "shock" if length_to_trough < 30 and abs(episode_trough_value) > 0.15 else "bleed"
        
        episodes.append({
            "peak_date": episode_peak_date.strftime("%Y-%m-%d"),
            "trough_date": episode_trough_date.strftime("%Y-%m-%d"),
            "recovery_date": None,
            "depth": round(float(episode_trough_value), 4),
            "length_peak_to_trough": int(length_to_trough),
            "length_recovery": None,
            "speed": round(float(speed), 4),
            "type": dd_type
        })
    
    # Sort by depth and keep top max_events
    episodes.sort(key=lambda x: x["depth"])
    episodes = episodes[:max_events]
    
    # Add rank
    for i, ep in enumerate(episodes):
        ep["rank"] = i + 1
    
    # Prepare series data (downsampled)
    series_data = []
    step = max(1, len(close) // 500)
    for date, price in close.iloc[::step].items():
        series_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "price": round(float(price), 2),
            "drawdown": round(float(dd.loc[date]), 4)
        })
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "episodes": episodes,
        "series": series_data,
        "meta": {"lookback_years": lookback_years}
    }


# =============================================================================
# FG8: HEDGE SIMULATOR
# =============================================================================

def compute_hedge_simulation(
    portfolio_returns: pd.Series,
    hedge_returns: Dict[str, pd.Series],
    hedge_weights: Dict[str, float],
    benchmark_returns: pd.Series,
    scenarios: List[str] = None
) -> Dict[str, Any]:
    """
    Simulate impact of hedges on portfolio risk.
    
    Args:
        portfolio_returns: Daily returns of current portfolio
        hedge_returns: Dict of ticker -> daily returns for hedge assets
        hedge_weights: Dict of ticker -> target weight
        benchmark_returns: Benchmark returns for beta calculation
        scenarios: List of scenario names to simulate
    
    Returns:
        Base and hedged portfolio risk metrics
    """
    if scenarios is None:
        scenarios = ["rate_hike", "inflation_spike", "equity_crash"]
    
    # Base portfolio metrics
    base_vol = float(portfolio_returns.std() * np.sqrt(252))
    base_var_95 = float(portfolio_returns.quantile(0.05))
    base_cvar_95 = float(portfolio_returns[portfolio_returns <= portfolio_returns.quantile(0.05)].mean())
    
    # Base beta
    common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) > 20:
        cov_pb = portfolio_returns.loc[common_idx].cov(benchmark_returns.loc[common_idx])
        var_b = benchmark_returns.loc[common_idx].var()
        base_beta = float(cov_pb / var_b) if var_b > EPSILON else 1.0
    else:
        base_beta = 1.0
    
    # Base max drawdown
    cum_ret = (1 + portfolio_returns).cumprod()
    peak = cum_ret.cummax()
    base_max_dd = float(((cum_ret - peak) / peak).min())
    
    # Construct hedged portfolio
    total_hedge_weight = sum(hedge_weights.values())
    portfolio_weight = 1.0 - total_hedge_weight
    
    # Align all return series
    all_dates = portfolio_returns.index
    for ticker, h_ret in hedge_returns.items():
        all_dates = all_dates.intersection(h_ret.index)
    all_dates = all_dates.intersection(benchmark_returns.index)
    
    if len(all_dates) < 20:
        # Not enough data
        return {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "base": {"vol": base_vol, "beta": base_beta, "var_95": base_var_95, "cvar_95": base_cvar_95, "max_drawdown": base_max_dd},
            "hedged": {"vol": base_vol, "beta": base_beta, "var_95": base_var_95, "cvar_95": base_cvar_95, "max_drawdown": base_max_dd},
            "scenarios": [],
            "meta": {"lookback_days": len(portfolio_returns)}
        }
    
    # Compute hedged returns
    hedged_returns = portfolio_weight * portfolio_returns.loc[all_dates]
    for ticker, weight in hedge_weights.items():
        if ticker in hedge_returns:
            hedged_returns += weight * hedge_returns[ticker].loc[all_dates]
    
    # Hedged metrics
    hedged_vol = float(hedged_returns.std() * np.sqrt(252))
    hedged_var_95 = float(hedged_returns.quantile(0.05))
    hedged_cvar_95 = float(hedged_returns[hedged_returns <= hedged_returns.quantile(0.05)].mean())
    
    cov_hb = hedged_returns.cov(benchmark_returns.loc[all_dates])
    var_b = benchmark_returns.loc[all_dates].var()
    hedged_beta = float(cov_hb / var_b) if var_b > EPSILON else 0.0
    
    cum_ret_h = (1 + hedged_returns).cumprod()
    peak_h = cum_ret_h.cummax()
    hedged_max_dd = float(((cum_ret_h - peak_h) / peak_h).min())
    
    # Scenario analysis (simplified)
    scenario_results = []
    scenario_shocks = {
        "rate_hike": {"SPY": -0.05, "TLT": -0.08, "GLD": 0.02},
        "inflation_spike": {"SPY": -0.03, "TLT": -0.05, "GLD": 0.08},
        "equity_crash": {"SPY": -0.20, "TLT": 0.05, "GLD": 0.03}
    }
    
    for scenario in scenarios:
        if scenario in scenario_shocks:
            shocks = scenario_shocks[scenario]
            base_pnl = shocks.get("SPY", -0.05) * base_beta
            
            hedged_pnl = portfolio_weight * shocks.get("SPY", -0.05) * base_beta
            for ticker, weight in hedge_weights.items():
                hedged_pnl += weight * shocks.get(ticker, 0.0)
            
            scenario_results.append({
                "name": scenario,
                "base_pnl": round(float(base_pnl), 4),
                "hedged_pnl": round(float(hedged_pnl), 4)
            })
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "base": {
            "vol": round(base_vol, 4),
            "beta": round(base_beta, 3),
            "var_95": round(base_var_95, 4),
            "cvar_95": round(base_cvar_95, 4),
            "max_drawdown": round(base_max_dd, 4)
        },
        "hedged": {
            "vol": round(hedged_vol, 4),
            "beta": round(hedged_beta, 3),
            "var_95": round(hedged_var_95, 4),
            "cvar_95": round(hedged_cvar_95, 4),
            "max_drawdown": round(hedged_max_dd, 4)
        },
        "scenarios": scenario_results,
        "meta": {"lookback_days": len(all_dates)}
    }


# =============================================================================
# FG9: HEDGE RATIO CALCULATOR
# =============================================================================

def compute_hedge_ratio(
    portfolio_returns: pd.Series,
    hedge_returns: pd.Series,
    mode: str = "beta_neutral"
) -> Dict[str, Any]:
    """
    Compute optimal hedge ratio.
    
    Args:
        portfolio_returns: Daily returns of portfolio
        hedge_returns: Daily returns of hedge asset
        mode: 'beta_neutral' or 'min_var'
    
    Returns:
        Hedge ratio and statistics
    """
    common_idx = portfolio_returns.index.intersection(hedge_returns.index)
    
    if len(common_idx) < 20:
        return {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "hedge_ticker": "UNKNOWN",
            "ratio": 0.0,
            "mode": mode,
            "stats": {},
            "meta": {"lookback_days": 0}
        }
    
    r_p = portfolio_returns.loc[common_idx]
    r_h = hedge_returns.loc[common_idx]
    
    # Correlation
    corr_ph = float(r_p.corr(r_h))
    
    # Covariance and variance
    cov_ph = float(r_p.cov(r_h))
    var_h = float(r_h.var())
    
    # Beta (hedge ratio for beta neutral)
    if var_h > EPSILON:
        beta_ph = cov_ph / var_h
    else:
        beta_ph = 0.0
    
    # Portfolio volatility
    portfolio_vol = float(r_p.std() * np.sqrt(252))
    
    # Min variance and beta neutral give same result in simple case
    ratio = -beta_ph  # Negative because we're shorting the hedge
    
    # Estimate hedged volatility
    hedged_returns = r_p + ratio * r_h
    hedged_vol = float(hedged_returns.std() * np.sqrt(252))
    
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "hedge_ticker": "HEDGE",  # Will be filled by caller
        "ratio": round(float(ratio), 4),
        "mode": mode,
        "stats": {
            "corr_ph": round(corr_ph, 3),
            "beta_ph": round(float(beta_ph), 3),
            "portfolio_vol": round(portfolio_vol, 4),
            "hedged_vol_estimate": round(hedged_vol, 4)
        },
        "meta": {"lookback_days": len(common_idx)}
    }
