"""
Portfolio Risk System - VaR Engine
Complete implementation per portfolio_risk.md specification

Features:
1. Parametric VaR
2. Cornish-Fisher VaR (Primary)
3. Expected Tail Loss (CVaR/ETL)
4. Component VaR
5. Incremental VaR
6. Stressed VaR
7. Correlation Stress Test
8. VaR Backtesting
9. Kupiec Test
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.stats import norm, chi2
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def safe_float(value, default=0.0) -> float:
    """Convert to float safely."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_covariance_matrix(returns: pd.DataFrame, method: str = "exponential", lambda_decay: float = 0.94) -> np.ndarray:
    """
    Calculate covariance matrix using different methods.
    
    Methods:
    - 'simple': Simple rolling covariance
    - 'exponential': EWMA covariance (RiskMetrics style)
    - 'shrinkage': Ledoit-Wolf Shrinkage (optimal for N > T or high noise)
    """
    if method == "exponential":
        # Exponential weighted covariance
        ewm_cov = returns.ewm(halflife=30).cov()
        # Get the last date's covariance matrix
        last_date = returns.index[-1]
        cov_matrix = ewm_cov.loc[last_date].values
        # Reshape to square matrix
        n_assets = len(returns.columns)
        cov_matrix = cov_matrix.reshape(n_assets, n_assets)
        
    elif method == "shrinkage":
        # Ledoit-Wolf optimal shrinkage
        try:
            from sklearn.covariance import ledoit_wolf
            # ledoit_wolf expects (n_samples, n_features)
            shrunk_cov, _ = ledoit_wolf(returns.dropna().values)
            cov_matrix = shrunk_cov
        except Exception as e:
            logger.debug(f"Shrinkage failed: {e}. Falling back to simple.")
            cov_matrix = returns.cov().values
    else:
        cov_matrix = returns.cov().values
    
    return cov_matrix


def get_z_quantile(confidence: float) -> float:
    """Get normal distribution z-score for given confidence level."""
    return norm.ppf(confidence)


# =============================================================================
# 1. PARAMETRIC VAR
# =============================================================================

def calculate_parametric_var(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    confidence: float = 0.99,
    holding_period: int = 1,
    lookback: int = 250
) -> Dict:
    """
    Calculate Parametric (Variance-Covariance) VaR.
    
    VaR = z_α × σ_p × √(holding_period) × Portfolio_Value
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns
        confidence: Confidence level (0.95 or 0.99)
        holding_period: Days to hold
        lookback: Days for calculation
    
    Returns:
        Dict with VaR, volatility, and other metrics
    """
    # Use last N days of returns
    returns_subset = returns.iloc[-lookback:]
    
    # Calculate covariance matrix (annualized daily returns)
    cov_matrix = calculate_covariance_matrix(returns_subset, method="exponential")
    
    # Portfolio variance: σ²_p = w^T Σ w
    portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
    portfolio_volatility = np.sqrt(portfolio_variance)
    
    # Annualized volatility
    annualized_volatility = portfolio_volatility * np.sqrt(252)
    
    # VaR calculation
    z_score = get_z_quantile(confidence)
    
    # Scale for holding period (square root of time)
    scaling = np.sqrt(holding_period)
    
    var_dollar = z_score * portfolio_volatility * scaling * portfolio_value
    var_percent = (var_dollar / portfolio_value) * 100
    
    # Calculate VaR at multiple confidence levels
    var_by_confidence = {}
    for conf in [0.90, 0.95, 0.99]:
        z = get_z_quantile(conf)
        var_by_confidence[f"{int(conf*100)}%"] = {
            "1d": safe_float(z * portfolio_volatility * portfolio_value),
            "10d": safe_float(z * portfolio_volatility * np.sqrt(10) * portfolio_value)
        }
    
    # Marginal VaR for each asset (for Component VaR prep)
    marginal_var = {}
    cov_weight_product = np.dot(cov_matrix, weights)
    for i, col in enumerate(returns.columns):
        mvar = cov_weight_product[i] / portfolio_volatility * z_score * portfolio_value
        marginal_var[col] = safe_float(mvar)
    
    return {
        "var_dollar": safe_float(var_dollar),
        "var_percent": safe_float(var_percent),
        "portfolio_volatility": safe_float(annualized_volatility * 100),  # as percentage
        "confidence": confidence,
        "holding_period": holding_period,
        "lookback": lookback,
        "z_score": safe_float(z_score),
        "var_by_confidence": var_by_confidence,
        "marginal_var": marginal_var,
        "var_per_million": safe_float(var_dollar / portfolio_value * 1_000_000),
        "method": "parametric"
    }


# =============================================================================
# 2. CORNISH-FISHER VAR (PRIMARY)
# =============================================================================

def calculate_cornish_fisher_var(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    confidence: float = 0.99,
    holding_period: int = 1,
    lookback: int = 250
) -> Dict:
    """
    Calculate Cornish-Fisher adjusted VaR (accounts for skewness and kurtosis).
    
    This is the PRIMARY risk metric per spec.
    
    z_CF = z + (z² - 1)×S/6 + (z³ - 3z)×K_excess/24 - (2z³ - 5z)×S²/36
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns
        confidence: Confidence level
        holding_period: Days to hold
        lookback: Days for calculation
    
    Returns:
        Dict with CF-VaR, tail metrics, and diagnostics
    """
    # Calculate parametric VaR first
    param_var = calculate_parametric_var(
        portfolio_value, weights, returns, confidence, holding_period, lookback
    )
    
    # Calculate portfolio returns
    returns_subset = returns.iloc[-lookback:]
    portfolio_returns = (returns_subset * weights).sum(axis=1)
    
    # Calculate moments
    mean_return = portfolio_returns.mean()
    std_return = portfolio_returns.std()
    
    # Skewness: S = E[(X - μ)³] / σ³
    skewness = float(stats.skew(portfolio_returns.dropna()))
    
    # Kurtosis: K = E[(X - μ)⁴] / σ⁴ (excess kurtosis, so normal = 0)
    kurtosis = float(stats.kurtosis(portfolio_returns.dropna()))
    
    # Cornish-Fisher expansion
    z = get_z_quantile(confidence)
    
    # z_CF = z + (z² - 1)×S/6 + (z³ - 3z)×K_excess/24 - (2z³ - 5z)×S²/36
    z_cf = z + \
        (z**2 - 1) * skewness / 6 + \
        (z**3 - 3*z) * kurtosis / 24 - \
        (2*z**3 - 5*z) * (skewness**2) / 36
    
    # CF-adjusted VaR
    scaling = np.sqrt(holding_period)
    cf_var_dollar = z_cf * std_return * scaling * portfolio_value
    cf_var_percent = (cf_var_dollar / portfolio_value) * 100
    
    # Tail inflation factor
    param_var_value = param_var["var_dollar"]
    tail_inflation = cf_var_dollar / param_var_value if param_var_value != 0 else 1.0
    
    # Delta vs parametric
    delta_dollar = cf_var_dollar - param_var_value
    delta_percent = (delta_dollar / param_var_value * 100) if param_var_value != 0 else 0
    
    # Tail regime classification
    if tail_inflation > 1.15 or kurtosis > 5:
        tail_regime = "FAT_TAILS"
        fat_tail_warning = True
    elif tail_inflation < 0.9:
        tail_regime = "THIN_TAILS"
        fat_tail_warning = False
    else:
        tail_regime = "NORMAL_TAILS"
        fat_tail_warning = False
    
    # Asymmetry check
    if skewness < -0.3:
        asymmetry = "NEGATIVE_SKEW"
        asymmetry_warning = True
    elif skewness > 0.3:
        asymmetry = "POSITIVE_SKEW"
        asymmetry_warning = False
    else:
        asymmetry = "SYMMETRIC"
        asymmetry_warning = False
    
    # Jarque-Bera test for normality
    n = len(portfolio_returns.dropna())
    jb_stat = n / 6 * (skewness**2 + kurtosis**2 / 4)
    jb_pvalue = 1 - chi2.cdf(jb_stat, 2)
    is_normal = jb_pvalue > 0.05
    
    return {
        "cf_var_dollar": safe_float(cf_var_dollar),
        "cf_var_percent": safe_float(cf_var_percent),
        "parametric_var_dollar": safe_float(param_var_value),
        "tail_inflation": safe_float(tail_inflation),
        "delta_dollar": safe_float(delta_dollar),
        "delta_percent": safe_float(delta_percent),
        "skewness": safe_float(skewness),
        "kurtosis": safe_float(kurtosis),
        "z_cf": safe_float(z_cf),
        "z_normal": safe_float(z),
        "tail_regime": tail_regime,
        "asymmetry": asymmetry,
        "fat_tail_warning": fat_tail_warning,
        "asymmetry_warning": asymmetry_warning,
        "jarque_bera": safe_float(jb_stat),
        "is_normal": is_normal,
        "confidence": confidence,
        "holding_period": holding_period,
        "method": "cornish_fisher",
        "recommendation": "Use CF-VaR as primary risk metric" if fat_tail_warning else "Parametric VaR sufficient"
    }


# =============================================================================
# 3. EXPECTED TAIL LOSS (CVaR / ETL)
# =============================================================================

def calculate_etl(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    confidence: float = 0.99,
    lookback: int = 250
) -> Dict:
    """
    Calculate Expected Tail Loss (Expected Shortfall / CVaR).
    
    ETL = E[Loss | Loss > VaR]
    
    This answers: "If VaR is breached, how bad on average?"
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns
        confidence: Confidence level
        lookback: Days for calculation
    
    Returns:
        Dict with ETL metrics and tail statistics
    """
    # Calculate portfolio returns
    returns_subset = returns.iloc[-lookback:]
    portfolio_returns = (returns_subset * weights).sum(axis=1)
    
    # Sort returns (ascending, so worst first)
    sorted_returns = portfolio_returns.sort_values()
    
    # Number of tail observations
    alpha = 1 - confidence
    n_tail = int(np.ceil(len(sorted_returns) * alpha))
    n_tail = max(n_tail, 1)  # At least 1
    
    # Tail observations
    tail_returns = sorted_returns.iloc[:n_tail]
    
    # Expected Tail Loss (non-parametric)
    etl_return = tail_returns.mean()
    etl_dollar = abs(etl_return) * portfolio_value
    etl_percent = abs(etl_return) * 100
    
    # Compare to VaR
    cf_var = calculate_cornish_fisher_var(portfolio_value, weights, returns, confidence, 1, lookback)
    var_dollar = cf_var["cf_var_dollar"]
    
    etl_var_ratio = etl_dollar / var_dollar if var_dollar != 0 else 1.0
    
    # Tail severity classification
    if etl_var_ratio < 1.05:
        tail_severity = "LOW"
    elif etl_var_ratio < 1.15:
        tail_severity = "MODERATE"
    else:
        tail_severity = "HIGH"
    
    # Worst days
    worst_days = []
    for i in range(min(5, len(tail_returns))):
        idx = tail_returns.index[i]
        loss = abs(tail_returns.iloc[i]) * portfolio_value
        worst_days.append({
            "date": str(idx.date()) if hasattr(idx, 'date') else str(idx)[:10],
            "loss_dollar": safe_float(loss),
            "loss_percent": safe_float(abs(tail_returns.iloc[i]) * 100)
        })
    
    # Tail statistics
    tail_volatility = tail_returns.std() * portfolio_value
    worst_single_day = abs(sorted_returns.iloc[0]) * portfolio_value
    
    # Expected frequency (days per year)
    tail_frequency = 252 * alpha
    
    # ETL at multiple confidence levels
    etl_by_confidence = {}
    for conf in [0.95, 0.99, 0.999]:
        alpha_lvl = 1 - conf
        n_tail_lvl = max(int(np.ceil(len(sorted_returns) * alpha_lvl)), 1)
        tail_lvl = sorted_returns.iloc[:n_tail_lvl]
        etl_lvl = abs(tail_lvl.mean()) * portfolio_value
        etl_by_confidence[f"{conf*100:.1f}%"] = safe_float(etl_lvl)
    
    return {
        "etl_dollar": safe_float(etl_dollar),
        "etl_percent": safe_float(etl_percent),
        "var_dollar": safe_float(var_dollar),
        "etl_var_ratio": safe_float(etl_var_ratio),
        "tail_severity": tail_severity,
        "worst_days": worst_days,
        "worst_single_day_dollar": safe_float(worst_single_day),
        "worst_single_day_percent": safe_float(abs(sorted_returns.iloc[0]) * 100),
        "tail_volatility": safe_float(tail_volatility),
        "tail_frequency_per_year": safe_float(tail_frequency),
        "n_tail_observations": n_tail,
        "etl_by_confidence": etl_by_confidence,
        "confidence": confidence,
        "method": "expected_tail_loss"
    }


# =============================================================================
# 4. COMPONENT VAR (RISK ATTRIBUTION)
# =============================================================================

def calculate_component_var(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    asset_names: List[str],
    confidence: float = 0.99,
    lookback: int = 250
) -> Dict:
    """
    Calculate Component VaR (Euler decomposition of portfolio VaR).
    
    Component VaR_i = w_i × MVaR_i
    Sum of all Component VaRs = Total Portfolio VaR
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns
        asset_names: List of asset names
        confidence: Confidence level
        lookback: Days for calculation
    
    Returns:
        Dict with component VaR for each asset
    """
    returns_subset = returns.iloc[-lookback:]
    
    # Calculate covariance matrix
    cov_matrix = calculate_covariance_matrix(returns_subset)
    
    # Portfolio volatility
    portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
    portfolio_volatility = np.sqrt(portfolio_variance)
    
    # Z-score
    z = get_z_quantile(confidence)
    
    # Portfolio VaR
    total_var = z * portfolio_volatility * portfolio_value
    
    # Marginal VaR and Component VaR per asset
    cov_weight_product = np.dot(cov_matrix, weights)
    
    components = []
    total_component = 0
    
    for i, name in enumerate(asset_names):
        # Marginal VaR: ∂VaR / ∂w_i
        marginal_var = (cov_weight_product[i] / portfolio_volatility) * z * portfolio_value / weights[i] if weights[i] != 0 else 0
        
        # Component VaR: w_i × MVaR_i
        component_var = weights[i] * marginal_var
        total_component += component_var
        
        # Risk contribution percentage
        risk_contribution_pct = (component_var / total_var * 100) if total_var != 0 else 0
        
        # Weight percentage
        weight_pct = weights[i] * 100
        
        # Concentration (risk/weight ratio)
        concentration = risk_contribution_pct / weight_pct if weight_pct != 0 else 0
        
        # Status
        if concentration > 2.0:
            status = "RISK_HOG"
        elif concentration > 1.5:
            status = "HIGH"
        elif concentration > 0.7:
            status = "BALANCED"
        elif component_var < 0:
            status = "DIVERSIFIER"
        else:
            status = "LOW"
        
        components.append({
            "asset": name,
            "weight_pct": safe_float(weight_pct),
            "marginal_var": safe_float(marginal_var),
            "component_var": safe_float(component_var),
            "risk_contribution_pct": safe_float(risk_contribution_pct),
            "concentration": safe_float(concentration),
            "status": status
        })
    
    # Sort by component VaR (descending)
    components.sort(key=lambda x: x["component_var"], reverse=True)
    
    # Risk concentration summary
    top1_risk = components[0]["risk_contribution_pct"] if components else 0
    top3_risk = sum(c["risk_contribution_pct"] for c in components[:3])
    top5_risk = sum(c["risk_contribution_pct"] for c in components[:5])
    
    # Herfindahl-Hirschman Index for risk concentration
    hhi = sum((c["risk_contribution_pct"]/100)**2 for c in components)
    
    # Risk hogs and diversifiers
    risk_hogs = [c for c in components if c["status"] == "RISK_HOG"]
    diversifiers = [c for c in components if c["component_var"] < 0]
    
    return {
        "total_var": safe_float(total_var),
        "components": components,
        "concentration_summary": {
            "top1_risk_pct": safe_float(top1_risk),
            "top3_risk_pct": safe_float(top3_risk),
            "top5_risk_pct": safe_float(top5_risk),
            "hhi": safe_float(hhi),
            "is_concentrated": hhi > 0.15 or top3_risk > 60
        },
        "risk_hogs": risk_hogs,
        "diversifiers": diversifiers,
        "alerts": [
            f"{c['asset']} contributes {c['risk_contribution_pct']:.1f}% risk with {c['weight_pct']:.1f}% weight"
            for c in risk_hogs
        ],
        "confidence": confidence,
        "method": "component_var"
    }


# =============================================================================
# 5. INCREMENTAL VAR (TRADE GATEKEEPER)
# =============================================================================

def calculate_incremental_var(
    current_portfolio_value: float,
    current_weights: np.ndarray,
    returns: pd.DataFrame,
    trade_asset: str,
    trade_value: float,
    asset_names: List[str],
    confidence: float = 0.99,
    lookback: int = 250
) -> Dict:
    """
    Calculate Incremental VaR for a proposed trade.
    
    Incremental_VaR = VaR_new - VaR_current
    
    Args:
        current_portfolio_value: Current NAV
        current_weights: Current weight vector
        returns: DataFrame of asset returns
        trade_asset: Asset being traded
        trade_value: Dollar value of trade (positive=buy, negative=sell)
        asset_names: List of asset names
        confidence: Confidence level
        lookback: Days for calculation
    
    Returns:
        Dict with trade impact analysis
    """
    # Current VaR
    current_cf_var = calculate_cornish_fisher_var(
        current_portfolio_value, current_weights, returns, confidence, 1, lookback
    )
    current_var = current_cf_var["cf_var_dollar"]
    
    # Current ETL
    current_etl = calculate_etl(
        current_portfolio_value, current_weights, returns, confidence, lookback
    )
    current_etl_dollar = current_etl["etl_dollar"]
    
    # New portfolio after trade
    new_portfolio_value = current_portfolio_value + trade_value
    
    # Find trade asset index
    trade_idx = asset_names.index(trade_asset) if trade_asset in asset_names else None
    
    if trade_idx is None:
        return {
            "status": "error",
            "message": f"Asset {trade_asset} not found in portfolio"
        }
    
    # Calculate new weights
    current_values = current_weights * current_portfolio_value
    new_values = current_values.copy()
    new_values[trade_idx] += trade_value
    new_weights = new_values / new_portfolio_value
    
    # New VaR
    new_cf_var = calculate_cornish_fisher_var(
        new_portfolio_value, new_weights, returns, confidence, 1, lookback
    )
    new_var = new_cf_var["cf_var_dollar"]
    
    # New ETL
    new_etl = calculate_etl(
        new_portfolio_value, new_weights, returns, confidence, lookback
    )
    new_etl_dollar = new_etl["etl_dollar"]
    
    # Incremental metrics
    incremental_var = new_var - current_var
    incremental_var_pct = (incremental_var / current_var * 100) if current_var != 0 else 0
    
    incremental_etl = new_etl_dollar - current_etl_dollar
    incremental_etl_pct = (incremental_etl / current_etl_dollar * 100) if current_etl_dollar != 0 else 0
    
    # Diversification benefit
    asset_returns = returns[trade_asset] if trade_asset in returns.columns else returns.iloc[:, trade_idx]
    asset_volatility = asset_returns.iloc[-lookback:].std()
    standalone_risk = asset_volatility * abs(trade_value) * get_z_quantile(confidence)
    
    diversification_benefit = 1 - (incremental_var / standalone_risk) if standalone_risk != 0 else 0
    
    # Classification
    if diversification_benefit > 0.3:
        diversification_status = "STRONG"
    elif diversification_benefit > 0.1:
        diversification_status = "MODERATE"
    elif diversification_benefit > 0:
        diversification_status = "WEAK"
    else:
        diversification_status = "NEGATIVE"
    
    # Trade assessment
    risk_per_dollar = incremental_var / abs(trade_value) if trade_value != 0 else 0
    
    if incremental_var < abs(trade_value) * 0.05 and diversification_benefit > 0:
        assessment = "APPROVE"
        assessment_color = "green"
    elif incremental_var < abs(trade_value) * 0.10:
        assessment = "CAUTION"
        assessment_color = "yellow"
    else:
        assessment = "REJECT"
        assessment_color = "red"
    
    # Recommended size (if caution/reject)
    if assessment != "APPROVE":
        # Find max trade size where incremental VaR < 5% of trade
        max_ratio = 0.05 / risk_per_dollar if risk_per_dollar != 0 else 1.0
        recommended_size = abs(trade_value) * min(max_ratio, 1.0)
    else:
        recommended_size = abs(trade_value)
    
    return {
        "trade_asset": trade_asset,
        "trade_value": trade_value,
        "current_var": safe_float(current_var),
        "new_var": safe_float(new_var),
        "incremental_var": safe_float(incremental_var),
        "incremental_var_pct": safe_float(incremental_var_pct),
        "current_etl": safe_float(current_etl_dollar),
        "new_etl": safe_float(new_etl_dollar),
        "incremental_etl": safe_float(incremental_etl),
        "incremental_etl_pct": safe_float(incremental_etl_pct),
        "diversification_benefit": safe_float(diversification_benefit),
        "diversification_status": diversification_status,
        "risk_per_dollar": safe_float(risk_per_dollar),
        "assessment": assessment,
        "assessment_color": assessment_color,
        "recommended_size": safe_float(recommended_size),
        "new_weight_pct": safe_float(new_weights[trade_idx] * 100),
        "confidence": confidence,
        "method": "incremental_var"
    }


# =============================================================================
# 6. STRESSED VAR (CRISIS SCENARIOS)
# =============================================================================

# Pre-defined crisis periods
CRISIS_PERIODS = {
    "2008_GFC": ("2008-09-01", "2008-11-30"),
    "2020_COVID": ("2020-02-20", "2020-03-31"),
    "2022_INFLATION": ("2022-01-01", "2022-06-30"),
    "2011_EURO_CRISIS": ("2011-07-01", "2011-10-31"),
    "2015_CHINA_DEVAL": ("2015-08-01", "2015-09-30"),
}


def calculate_stressed_var(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    crisis_period: str = "2020_COVID",
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
    confidence: float = 0.99
) -> Dict:
    """
    Calculate Stressed VaR using historical crisis period data.
    
    Uses covariance matrix from crisis period instead of normal conditions.
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns (should include crisis period)
        crisis_period: Pre-defined crisis key
        custom_start: Custom crisis start date
        custom_end: Custom crisis end date
        confidence: Confidence level
    
    Returns:
        Dict with stressed VaR and crisis metrics
    """
    # Get crisis dates
    if custom_start and custom_end:
        start_date = custom_start
        end_date = custom_end
        crisis_label = "CUSTOM"
    else:
        if crisis_period not in CRISIS_PERIODS:
            crisis_period = "2020_COVID"
        start_date, end_date = CRISIS_PERIODS[crisis_period]
        crisis_label = crisis_period
    
    # Normal VaR (using current/recent data)
    normal_cf_var = calculate_cornish_fisher_var(
        portfolio_value, weights, returns, confidence, 1, 250
    )
    normal_var = normal_cf_var["cf_var_dollar"]
    
    # Filter returns to crisis period
    try:
        crisis_returns = returns.loc[start_date:end_date]
    except:
        # If crisis period not in data, simulate with scaling
        crisis_returns = returns.iloc[-60:]  # Use recent data as fallback
        crisis_label = f"{crisis_label}_SIMULATED"
    
    if len(crisis_returns) < 20:
        # Not enough crisis data, scale normal vol
        vol_multiplier = 2.5
        stressed_var = normal_var * vol_multiplier
        crisis_cov = None
        correlation_spike = 0.4
    else:
        # Calculate crisis covariance matrix
        crisis_cov = calculate_covariance_matrix(crisis_returns, method="simple")
        
        # Crisis volatility
        crisis_variance = np.dot(weights.T, np.dot(crisis_cov, weights))
        crisis_volatility = np.sqrt(crisis_variance)
        
        # Normal covariance
        normal_cov = calculate_covariance_matrix(returns.iloc[-250:], method="simple")
        normal_variance = np.dot(weights.T, np.dot(normal_cov, weights))
        normal_volatility = np.sqrt(normal_variance)
        
        # Stressed VaR
        z = get_z_quantile(confidence)
        stressed_var = z * crisis_volatility * portfolio_value
        
        # Volatility ratio
        vol_multiplier = crisis_volatility / normal_volatility if normal_volatility != 0 else 1.0
        
        # Correlation analysis
        normal_corr = np.corrcoef(returns.iloc[-250:].T)
        crisis_corr = np.corrcoef(crisis_returns.T)
        
        avg_normal_corr = (np.sum(normal_corr) - len(weights)) / (len(weights) * (len(weights) - 1))
        avg_crisis_corr = (np.sum(crisis_corr) - len(weights)) / (len(weights) * (len(weights) - 1))
        
        correlation_spike = avg_crisis_corr - avg_normal_corr
    
    # Stress multiple
    stress_multiple = stressed_var / normal_var if normal_var != 0 else 1.0
    
    # Classification
    if stress_multiple < 1.3:
        crisis_readiness = "RESILIENT"
        readiness_color = "green"
    elif stress_multiple < 1.8:
        crisis_readiness = "MODERATE_RISK"
        readiness_color = "yellow"
    else:
        crisis_readiness = "HIGH_RISK"
        readiness_color = "red"
    
    # Max safe leverage
    risk_limit_pct = 0.05  # Assume 5% NAV max loss
    risk_limit_dollar = portfolio_value * risk_limit_pct
    max_safe_leverage = risk_limit_dollar / stressed_var if stressed_var != 0 else 10.0
    
    # Compare all crisis periods
    crisis_comparison = []
    for crisis_name, (cs, ce) in CRISIS_PERIODS.items():
        try:
            cr = returns.loc[cs:ce]
            if len(cr) >= 20:
                c_cov = calculate_covariance_matrix(cr, method="simple")
                c_var = np.sqrt(np.dot(weights.T, np.dot(c_cov, weights)))
                c_stressed = get_z_quantile(confidence) * c_var * portfolio_value
                crisis_comparison.append({
                    "crisis": crisis_name,
                    "stressed_var": safe_float(c_stressed),
                    "stress_multiple": safe_float(c_stressed / normal_var if normal_var != 0 else 1.0)
                })
        except:
            pass
    
    return {
        "normal_var": safe_float(normal_var),
        "stressed_var": safe_float(stressed_var),
        "stress_multiple": safe_float(stress_multiple),
        "crisis_period": crisis_label,
        "volatility_amplification": safe_float(vol_multiplier),
        "correlation_spike": safe_float(correlation_spike),
        "crisis_readiness": crisis_readiness,
        "readiness_color": readiness_color,
        "max_safe_leverage": safe_float(max_safe_leverage),
        "crisis_comparison": crisis_comparison,
        "confidence": confidence,
        "method": "stressed_var"
    }


# =============================================================================
# 7. CORRELATION STRESS TEST
# =============================================================================

def calculate_correlation_stress(
    portfolio_value: float,
    weights: np.ndarray,
    returns: pd.DataFrame,
    target_correlation: float = 0.9,
    confidence: float = 0.99,
    lookback: int = 250
) -> Dict:
    """
    Calculate VaR under stressed correlation scenarios.
    
    Tests what happens when all correlations spike (crisis behavior).
    
    Args:
        portfolio_value: Total portfolio NAV
        weights: Asset weight vector
        returns: DataFrame of asset returns
        target_correlation: Target correlation for stress test
        confidence: Confidence level
        lookback: Days for calculation
    
    Returns:
        Dict with correlation stress analysis
    """
    returns_subset = returns.iloc[-lookback:]
    n_assets = len(weights)
    
    # Current correlation matrix
    current_corr = returns_subset.corr().values
    
    # Current covariance
    current_cov = returns_subset.cov().values
    
    # Asset volatilities (diagonal of std matrix)
    volatilities = np.sqrt(np.diag(current_cov))
    
    # Current VaR
    current_variance = np.dot(weights.T, np.dot(current_cov, weights))
    current_volatility = np.sqrt(current_variance)
    z = get_z_quantile(confidence)
    current_var = z * current_volatility * portfolio_value
    
    # Stressed correlation matrix (uniform high correlation)
    stressed_corr = np.full((n_assets, n_assets), target_correlation)
    np.fill_diagonal(stressed_corr, 1.0)
    
    # Ensure positive semi-definite
    eigenvalues, eigenvectors = np.linalg.eigh(stressed_corr)
    eigenvalues = np.maximum(eigenvalues, 0.01)
    stressed_corr = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    
    # Stressed covariance: Σ = D × P × D
    D = np.diag(volatilities)
    stressed_cov = D @ stressed_corr @ D
    
    # Stressed VaR
    stressed_variance = np.dot(weights.T, np.dot(stressed_cov, weights))
    stressed_volatility = np.sqrt(stressed_variance)
    stressed_var = z * stressed_volatility * portfolio_value
    
    # Risk amplification
    risk_amplification = stressed_var / current_var if current_var != 0 else 1.0
    
    # Average correlations
    avg_current_corr = (np.sum(current_corr) - n_assets) / (n_assets * (n_assets - 1))
    
    # Diversification illusion
    # Theoretical VaR if uncorrelated
    theoretical_uncorrelated = np.sqrt(np.sum((weights * volatilities) ** 2))
    theoretical_var = z * theoretical_uncorrelated * portfolio_value
    
    diversification_illusion = current_var - theoretical_var
    
    # Test multiple correlation levels
    correlation_scenarios = []
    for target in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        sc = np.full((n_assets, n_assets), target)
        np.fill_diagonal(sc, 1.0)
        s_cov = D @ sc @ D
        s_var = z * np.sqrt(np.dot(weights.T, np.dot(s_cov, weights))) * portfolio_value
        correlation_scenarios.append({
            "target_correlation": target,
            "stressed_var": safe_float(s_var),
            "risk_amplification": safe_float(s_var / current_var if current_var != 0 else 1.0),
            "risk_added": safe_float(s_var - current_var)
        })
    
    # Identify correlation clusters (simplified)
    clusters = []
    high_corr_pairs = []
    for i in range(n_assets):
        for j in range(i+1, n_assets):
            if current_corr[i, j] > 0.7:
                high_corr_pairs.append({
                    "asset1": returns.columns[i] if hasattr(returns, 'columns') else f"Asset_{i}",
                    "asset2": returns.columns[j] if hasattr(returns, 'columns') else f"Asset_{j}",
                    "correlation": safe_float(current_corr[i, j])
                })
    
    # False diversification flag
    false_diversification = risk_amplification > 1.3
    
    return {
        "current_var": safe_float(current_var),
        "stressed_var": safe_float(stressed_var),
        "target_correlation": target_correlation,
        "risk_amplification": safe_float(risk_amplification),
        "avg_current_correlation": safe_float(avg_current_corr),
        "diversification_illusion_dollar": safe_float(diversification_illusion),
        "theoretical_uncorrelated_var": safe_float(theoretical_var),
        "false_diversification_detected": false_diversification,
        "correlation_scenarios": correlation_scenarios,
        "high_correlation_pairs": high_corr_pairs[:10],  # Top 10
        "confidence": confidence,
        "method": "correlation_stress"
    }


# =============================================================================
# 8. VAR BACKTESTING
# =============================================================================

def calculate_var_backtest(
    historical_var: pd.Series,
    realized_pnl: pd.Series,
    confidence: float = 0.99
) -> Dict:
    """
    Backtest VaR model by comparing forecasts to realized PnL.
    
    Exception = 1 if Realized_PnL < -VaR_forecast
    
    Args:
        historical_var: Series of VaR forecasts (positive values)
        realized_pnl: Series of realized daily PnL
        confidence: VaR confidence level
    
    Returns:
        Dict with backtest results and breach analysis
    """
    # Align series
    common_idx = historical_var.index.intersection(realized_pnl.index)
    var_aligned = historical_var.loc[common_idx]
    pnl_aligned = realized_pnl.loc[common_idx]
    
    n = len(common_idx)
    if n < 30:
        return {
            "status": "error",
            "message": "Insufficient data for backtesting (need at least 30 days)"
        }
    
    # Identify exceptions (breaches)
    exceptions = pnl_aligned < -var_aligned
    breach_count = exceptions.sum()
    
    # Expected breaches
    alpha = 1 - confidence
    expected_breaches = n * alpha
    
    # Breach rate
    actual_rate = breach_count / n
    expected_rate = alpha
    
    # Accuracy
    accuracy = 1 - abs(actual_rate - expected_rate)
    
    # Model status
    if abs(actual_rate - expected_rate) < 0.005:
        status = "PASSING"
        status_color = "green"
    elif abs(actual_rate - expected_rate) < 0.01:
        status = "WARNING"
        status_color = "yellow"
    else:
        status = "FAILING"
        status_color = "red"
    
    # Reliability score
    reliability_score = max(0, min(100, accuracy * 100))
    
    # Breach log
    breach_dates = exceptions[exceptions].index
    breach_log = []
    for date in breach_dates:
        breach_log.append({
            "date": str(date.date()) if hasattr(date, 'date') else str(date)[:10],
            "realized_pnl": safe_float(pnl_aligned.loc[date]),
            "var_forecast": safe_float(var_aligned.loc[date]),
            "breach_amount": safe_float(abs(pnl_aligned.loc[date]) - var_aligned.loc[date]),
            "severity_pct": safe_float((abs(pnl_aligned.loc[date]) - var_aligned.loc[date]) / var_aligned.loc[date] * 100) if var_aligned.loc[date] != 0 else 0
        })
    
    # Sort by severity
    breach_log.sort(key=lambda x: x.get("severity_pct", 0), reverse=True)
    
    # Average breach severity
    severities = [b["severity_pct"] for b in breach_log]
    avg_severity = np.mean(severities) if severities else 0
    worst_severity = max(severities) if severities else 0
    
    # Rolling accuracy (30, 60, 90 days)
    rolling_accuracy = {}
    for window in [30, 60, 90]:
        if len(exceptions) >= window:
            recent = exceptions.iloc[-window:]
            recent_rate = recent.sum() / window
            rolling_accuracy[f"{window}d"] = {
                "breaches": int(recent.sum()),
                "expected": safe_float(window * alpha),
                "accuracy": safe_float(1 - abs(recent_rate - alpha))
            }
    
    # Trend detection
    if rolling_accuracy:
        acc_30 = rolling_accuracy.get("30d", {}).get("accuracy", 0)
        acc_90 = rolling_accuracy.get("90d", {}).get("accuracy", accuracy)
        if acc_30 > acc_90 + 0.02:
            trend = "IMPROVING"
        elif acc_30 < acc_90 - 0.02:
            trend = "DETERIORATING"
        else:
            trend = "STABLE"
    else:
        trend = "STABLE"
    
    # Generate backtest history for charting
    backtest_history = []
    cumulative_breaches = 0
    for i, (date, is_breach) in enumerate(exceptions.items()):
        if is_breach:
            cumulative_breaches += 1
        if i % 5 == 0 or is_breach:  # Sample every 5 days + all breaches
            backtest_history.append({
                "date": str(date.date()) if hasattr(date, 'date') else str(date)[:10],
                "pnl": safe_float(pnl_aligned.loc[date]),
                "var": safe_float(-var_aligned.loc[date]),
                "breach": bool(is_breach),
                "cumulative_breaches": cumulative_breaches
            })
    
    return {
        "n_observations": n,
        "expected_breaches": safe_float(expected_breaches),
        "actual_breaches": int(breach_count),
        "expected_rate": safe_float(expected_rate * 100),
        "actual_rate": safe_float(actual_rate * 100),
        "accuracy": safe_float(accuracy * 100),
        "reliability_score": safe_float(reliability_score),
        "status": status,
        "status_color": status_color,
        "breach_log": breach_log[:10],  # Top 10 worst
        "avg_severity_pct": safe_float(avg_severity),
        "worst_severity_pct": safe_float(worst_severity),
        "rolling_accuracy": rolling_accuracy,
        "trend": trend,
        "backtest_history": backtest_history,
        "confidence": confidence,
        "method": "var_backtest"
    }


# =============================================================================
# 9. KUPIEC TEST (STATISTICAL VALIDATION)
# =============================================================================

def calculate_kupiec_test(
    breach_count: int,
    n_observations: int,
    confidence: float = 0.99,
    significance: float = 0.05
) -> Dict:
    """
    Run Kupiec's Proportion of Failures (POF) test.
    
    Tests if observed breach rate is statistically consistent with expected rate.
    
    LR = -2 × ln[(1-p_0)^(N-x) × p_0^x] + 2 × ln[(1-p)^(N-x) × p^x]
    Under H0: LR ~ χ²(1)
    
    Args:
        breach_count: Number of VaR breaches observed
        n_observations: Total number of observations
        confidence: VaR confidence level (0.95 or 0.99)
        significance: Test significance level (typically 0.05)
    
    Returns:
        Dict with Kupiec test results
    """
    x = breach_count
    N = n_observations
    
    # Expected breach rate
    p_0 = 1 - confidence
    
    # Observed breach rate
    p = x / N if N > 0 else 0
    
    # Handle edge cases
    if p == 0:
        p = 0.0001  # Avoid log(0)
    if p == 1:
        p = 0.9999
    
    # Likelihood ratio
    # LR = -2 * [ln(L0) - ln(L1)]
    # L0 = (1-p_0)^(N-x) * p_0^x
    # L1 = (1-p)^(N-x) * p^x
    
    try:
        ln_L0 = (N - x) * np.log(1 - p_0) + x * np.log(p_0)
        ln_L1 = (N - x) * np.log(1 - p) + x * np.log(p)
        
        LR = -2 * (ln_L0 - ln_L1)
    except:
        LR = 0
    
    # Critical value from chi-square(1)
    critical_value = chi2.ppf(1 - significance, df=1)
    
    # P-value
    p_value = 1 - chi2.cdf(LR, df=1)
    
    # Test result
    if LR < critical_value:
        result = "PASS"
        result_color = "green"
        can_reject = False
    else:
        result = "FAIL"
        result_color = "red"
        can_reject = True
    
    # Model credibility
    if result == "PASS" and abs(p - p_0) < 0.005:
        credibility = "HIGH"
    elif result == "PASS":
        credibility = "MEDIUM"
    else:
        credibility = "LOW"
    
    # Failure mode (if failed)
    if can_reject:
        if p > p_0:
            failure_mode = "TOO_OPTIMISTIC"
            failure_explanation = "Model underestimates risk (too many breaches)"
        else:
            failure_mode = "TOO_CONSERVATIVE"
            failure_explanation = "Model overestimates risk (too few breaches)"
    else:
        failure_mode = None
        failure_explanation = None
    
    # Interpretation
    interpretation = f"With {breach_count} breaches in {n_observations} days "
    if result == "PASS":
        interpretation += f"(p-value={p_value:.3f}), the model is statistically sound at the {confidence*100:.0f}% confidence level."
    else:
        interpretation += f"(p-value={p_value:.3f}), the model fails validation. {failure_explanation}."
    
    return {
        "test_statistic": safe_float(LR),
        "critical_value": safe_float(critical_value),
        "p_value": safe_float(p_value),
        "significance": significance,
        "result": result,
        "result_color": result_color,
        "can_reject_null": can_reject,
        "credibility": credibility,
        "observed_rate_pct": safe_float(p * 100),
        "expected_rate_pct": safe_float(p_0 * 100),
        "rate_difference_pct": safe_float((p - p_0) * 100),
        "failure_mode": failure_mode,
        "failure_explanation": failure_explanation,
        "interpretation": interpretation,
        "confidence": confidence,
        "method": "kupiec_test"
    }


# =============================================================================
# MASTER RISK SCORE CALCULATOR
# =============================================================================

def calculate_portfolio_risk_score(
    var_percent: float,
    etl_var_ratio: float,
    stress_multiple: float,
    avg_correlation: float,
    backtest_accuracy: float,
    kupiec_pass: bool
) -> Dict:
    """
    Calculate overall portfolio risk health score.
    
    Weights:
    - VaR Health: 30%
    - Tail Risk: 25%
    - Stress Prep: 20%
    - Correlation: 15%
    - Validation: 10%
    
    Args:
        var_percent: VaR as % of NAV
        etl_var_ratio: ETL/VaR ratio
        stress_multiple: Stressed VaR / Normal VaR
        avg_correlation: Average portfolio correlation
        backtest_accuracy: Model accuracy (0-100)
        kupiec_pass: Whether model passes Kupiec test
    
    Returns:
        Dict with overall risk score and component scores
    """
    # Component scores (0-100)
    
    # VaR Health
    if var_percent < 1.5:
        var_score = 100
    elif var_percent < 3.0:
        var_score = 70
    else:
        var_score = 30
    
    # Tail Risk
    if etl_var_ratio < 1.1:
        tail_score = 100
    elif etl_var_ratio < 1.2:
        tail_score = 70
    else:
        tail_score = 40
    
    # Stress Preparedness
    if stress_multiple < 1.3:
        stress_score = 100
    elif stress_multiple < 1.8:
        stress_score = 60
    else:
        stress_score = 20
    
    # Correlation Risk
    if avg_correlation < 0.5:
        corr_score = 100
    elif avg_correlation < 0.7:
        corr_score = 60
    else:
        corr_score = 30
    
    # Model Validation
    if kupiec_pass and backtest_accuracy > 98:
        validation_score = 100
    elif kupiec_pass:
        validation_score = 80
    else:
        validation_score = 20
    
    # Weighted average
    overall_score = (
        var_score * 0.30 +
        tail_score * 0.25 +
        stress_score * 0.20 +
        corr_score * 0.15 +
        validation_score * 0.10
    )
    
    # Posture
    if overall_score > 80:
        posture = "HEALTHY"
        posture_color = "green"
    elif overall_score > 60:
        posture = "MODERATE"
        posture_color = "yellow"
    else:
        posture = "AT_RISK"
        posture_color = "red"
    
    # Warnings
    warnings = []
    if var_score < 50:
        warnings.append("VaR exceeds target threshold")
    if tail_score < 50:
        warnings.append("Fat tail risk detected")
    if stress_score < 50:
        warnings.append("High crisis vulnerability")
    if corr_score < 50:
        warnings.append("High correlation risk")
    if validation_score < 50:
        warnings.append("Model validation issues")
    
    return {
        "overall_score": safe_float(overall_score),
        "posture": posture,
        "posture_color": posture_color,
        "component_scores": {
            "var_health": safe_float(var_score),
            "tail_risk": safe_float(tail_score),
            "stress_preparedness": safe_float(stress_score),
            "correlation_risk": safe_float(corr_score),
            "model_validation": safe_float(validation_score)
        },
        "weights": {
            "var_health": 0.30,
            "tail_risk": 0.25,
            "stress_preparedness": 0.20,
            "correlation_risk": 0.15,
            "model_validation": 0.10
        },
        "warnings": warnings,
        "method": "portfolio_risk_score"
    }
