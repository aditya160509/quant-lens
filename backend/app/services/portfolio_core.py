"""
Portfolio Core - Mathematical Foundation
All quantitative primitives for the portfolio system
"""
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from typing import Tuple, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# RETURNS CALCULATIONS
# =============================================================================

def log_returns(prices: pd.Series) -> pd.Series:
    """Compute log returns from price series."""
    return np.log(prices / prices.shift(1)).dropna()


def simple_returns(prices: pd.Series) -> pd.Series:
    """Compute simple returns from price series."""
    return prices.pct_change().dropna()


def excess_returns(returns: pd.Series, rf: float = 0.0) -> pd.Series:
    """Compute excess returns over risk-free rate (daily rf assumed)."""
    return returns - rf / 252


# =============================================================================
# VOLATILITY ESTIMATORS
# =============================================================================

def realized_volatility(returns: pd.Series, window: int = 20, annualize: bool = True) -> float:
    """Compute realized volatility over a rolling window."""
    vol = returns.tail(window).std()
    if annualize:
        vol *= np.sqrt(252)
    return float(vol) if not np.isnan(vol) else 0.0


def ewma_volatility(returns: pd.Series, lambda_: float = 0.94, annualize: bool = True) -> pd.Series:
    """
    Compute EWMA volatility (RiskMetrics methodology).
    σ²_t = λ * σ²_{t-1} + (1-λ) * r²_t
    """
    var = returns.ewm(alpha=1-lambda_, adjust=False).var()
    vol = np.sqrt(var)
    if annualize:
        vol *= np.sqrt(252)
    return vol


def downside_volatility(returns: pd.Series, threshold: float = 0.0, annualize: bool = True) -> float:
    """Compute downside volatility (semi-deviation)."""
    downside = returns[returns < threshold]
    if len(downside) < 2:
        return 0.0
    vol = downside.std()
    if annualize:
        vol *= np.sqrt(252)
    return float(vol)


# =============================================================================
# COVARIANCE ESTIMATION
# =============================================================================

def sample_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    """Compute sample covariance matrix."""
    return returns.cov() * 252  # Annualized


def sample_correlation(returns: pd.DataFrame) -> pd.DataFrame:
    """Compute sample correlation matrix."""
    return returns.corr()


def ledoit_wolf_shrinkage(returns: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    """
    Ledoit-Wolf shrinkage estimator for covariance matrix.
    Σ̂ = δ*F + (1-δ)*S
    where F = structured target (constant correlation), S = sample covariance
    
    Returns: (shrunk covariance matrix, shrinkage intensity)
    """
    n, p = returns.shape
    
    if n < 2 or p < 2:
        return returns.cov() * 252, 0.0
    
    # Sample covariance
    S = returns.cov().values
    
    # Sample correlation and average correlation
    corr = returns.corr().values
    avg_corr = (corr.sum() - p) / (p * (p - 1))
    
    # Structured target: constant correlation model
    sample_var = np.diag(S)
    F = avg_corr * np.outer(np.sqrt(sample_var), np.sqrt(sample_var))
    np.fill_diagonal(F, sample_var)
    
    # Compute optimal shrinkage intensity (simplified Ledoit-Wolf)
    # Using asymptotic formula
    X = returns.values
    X_centered = X - X.mean(axis=0)
    
    sum_pi = 0
    for i in range(p):
        for j in range(p):
            y_ij = X_centered[:, i] * X_centered[:, j]
            pi_ij = np.sum((y_ij - S[i, j]) ** 2) / n
            sum_pi += pi_ij
    
    # Avoid numerical issues
    gamma = np.sum((S - F) ** 2)
    kappa = sum_pi / n
    
    if gamma == 0:
        delta = 1.0
    else:
        delta = max(0, min(1, kappa / gamma))
    
    # Shrunk covariance
    shrunk = delta * F + (1 - delta) * S
    
    # Annualize
    shrunk *= 252
    
    return pd.DataFrame(shrunk, index=returns.columns, columns=returns.columns), delta


# =============================================================================
# RISK METRICS
# =============================================================================

def value_at_risk(returns: pd.Series, alpha: float = 0.05, method: str = "historical") -> float:
    """
    Compute Value-at-Risk at given confidence level.
    Returns positive number (loss magnitude).
    """
    if len(returns) < 10:
        return 0.0
    
    if method == "historical":
        var = -np.percentile(returns, alpha * 100)
    elif method == "parametric":
        mu = returns.mean()
        sigma = returns.std()
        var = -(mu + stats.norm.ppf(alpha) * sigma)
    else:
        var = -np.percentile(returns, alpha * 100)
    
    return float(var) if not np.isnan(var) else 0.0


def conditional_var(returns: pd.Series, alpha: float = 0.05) -> float:
    """
    Compute Conditional VaR (Expected Shortfall).
    CVaR = E[Loss | Loss > VaR]
    """
    if len(returns) < 10:
        return 0.0
    
    var_threshold = np.percentile(returns, alpha * 100)
    tail_returns = returns[returns <= var_threshold]
    
    if len(tail_returns) == 0:
        return value_at_risk(returns, alpha)
    
    cvar = -tail_returns.mean()
    return float(cvar) if not np.isnan(cvar) else 0.0


def maximum_drawdown(nav: pd.Series) -> Tuple[float, Optional[int], Optional[int]]:
    """
    Compute maximum drawdown from NAV series.
    Returns: (max_dd, peak_idx, trough_idx)
    """
    if len(nav) < 2:
        return 0.0, None, None
    
    peak = nav.expanding().max()
    drawdown = (nav - peak) / peak
    
    max_dd = drawdown.min()
    trough_idx = drawdown.idxmin() if not pd.isna(max_dd) else None
    
    if trough_idx is not None:
        peak_idx = nav.loc[:trough_idx].idxmax()
    else:
        peak_idx = None
    
    return float(max_dd) if not np.isnan(max_dd) else 0.0, peak_idx, trough_idx


def current_drawdown(nav: pd.Series) -> float:
    """Compute current drawdown from peak."""
    if len(nav) < 2:
        return 0.0
    peak = nav.max()
    current = nav.iloc[-1]
    dd = (current - peak) / peak
    return float(dd) if not np.isnan(dd) else 0.0


# =============================================================================
# RATIOS
# =============================================================================

def sharpe_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    """
    Compute annualized Sharpe ratio.
    Sharpe = (E[R] - Rf) / σ
    """
    if len(returns) < 10:
        return 0.0
    
    excess = returns - rf / 252
    mu_ann = excess.mean() * 252
    vol_ann = excess.std() * np.sqrt(252)
    
    if vol_ann == 0:
        return 0.0
    
    return float(mu_ann / vol_ann)


def sortino_ratio(returns: pd.Series, rf: float = 0.0, target: float = 0.0) -> float:
    """
    Compute Sortino ratio using downside deviation.
    Sortino = (E[R] - Rf) / σ_downside
    """
    if len(returns) < 10:
        return 0.0
    
    excess = returns - rf / 252
    mu_ann = excess.mean() * 252
    down_vol = downside_volatility(returns, target)
    
    if down_vol == 0:
        return 0.0
    
    return float(mu_ann / down_vol)


def calmar_ratio(returns: pd.Series, nav: pd.Series) -> float:
    """
    Compute Calmar ratio.
    Calmar = CAGR / |Max Drawdown|
    """
    if len(returns) < 252:
        cagr = returns.mean() * 252
    else:
        total_return = nav.iloc[-1] / nav.iloc[0] - 1
        years = len(nav) / 252
        cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    
    max_dd, _, _ = maximum_drawdown(nav)
    
    if abs(max_dd) < 0.001:
        return 0.0
    
    return float(cagr / abs(max_dd))


def information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Compute Information Ratio.
    IR = E[R - Rb] / σ(R - Rb)
    """
    if len(returns) < 10 or len(benchmark_returns) < 10:
        return 0.0
    
    # Align returns
    common_idx = returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 10:
        return 0.0
    
    active = returns.loc[common_idx] - benchmark_returns.loc[common_idx]
    mu_ann = active.mean() * 252
    te = active.std() * np.sqrt(252)
    
    if te == 0:
        return 0.0
    
    return float(mu_ann / te)


# =============================================================================
# RISK ATTRIBUTION
# =============================================================================

def portfolio_volatility(weights: np.ndarray, cov: np.ndarray) -> float:
    """Compute portfolio volatility."""
    var = weights @ cov @ weights
    return float(np.sqrt(var))


def risk_contribution(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """
    Compute risk contribution of each asset.
    RC_i = w_i * (Σw)_i / σ_p
    """
    port_var = weights @ cov @ weights
    if port_var <= 0:
        return np.zeros_like(weights)
    
    port_vol = np.sqrt(port_var)
    marginal = cov @ weights
    rc = weights * marginal / port_vol
    
    return rc


def marginal_risk(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """
    Compute marginal risk contribution.
    MR_i = ∂σ_p / ∂w_i
    """
    port_var = weights @ cov @ weights
    if port_var <= 0:
        return np.zeros_like(weights)
    
    port_vol = np.sqrt(port_var)
    marginal = cov @ weights / port_vol
    
    return marginal


def percentage_risk_contribution(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """
    Compute percentage risk contribution.
    %RC_i = RC_i / σ_p
    """
    rc = risk_contribution(weights, cov)
    total = rc.sum()
    if total <= 0:
        return np.zeros_like(weights)
    return rc / total


# =============================================================================
# FACTOR ATTRIBUTION
# =============================================================================

def factor_regression(returns: pd.Series, factors: pd.DataFrame) -> Dict:
    """
    Run factor regression to decompose returns.
    R = α + Σ β_i * F_i + ε
    """
    import statsmodels.api as sm
    
    # Align
    common_idx = returns.index.intersection(factors.index)
    if len(common_idx) < 30:
        return {"alpha": 0, "betas": {}, "r_squared": 0}
    
    y = returns.loc[common_idx]
    X = factors.loc[common_idx]
    X = sm.add_constant(X)
    
    try:
        model = sm.OLS(y, X).fit()
        betas = {col: model.params.get(col, 0) for col in factors.columns}
        return {
            "alpha": float(model.params.get("const", 0)) * 252,  # Annualized
            "betas": betas,
            "r_squared": float(model.rsquared),
            "residual_vol": float(model.resid.std() * np.sqrt(252))
        }
    except Exception as e:
        logger.warning(f"Factor regression failed: {e}")
        return {"alpha": 0, "betas": {}, "r_squared": 0}


# =============================================================================
# CONCENTRATION METRICS
# =============================================================================

def herfindahl_hirschman_index(weights: np.ndarray) -> float:
    """
    Compute Herfindahl-Hirschman Index.
    HHI = Σ w_i²
    """
    return float(np.sum(weights ** 2))


def effective_n(weights: np.ndarray) -> float:
    """
    Compute effective number of assets.
    N_eff = 1 / HHI
    """
    hhi = herfindahl_hirschman_index(weights)
    if hhi <= 0:
        return 0.0
    return 1.0 / hhi


def entropy(weights: np.ndarray) -> float:
    """
    Compute Shannon entropy.
    H = -Σ w_i * ln(w_i)
    """
    weights = weights[weights > 0]
    if len(weights) == 0:
        return 0.0
    return float(-np.sum(weights * np.log(weights)))


def diversification_ratio(weights: np.ndarray, vols: np.ndarray, cov: np.ndarray) -> float:
    """
    Compute diversification ratio.
    DR = (Σ w_i * σ_i) / σ_p
    """
    weighted_vol = np.sum(weights * vols)
    port_vol = portfolio_volatility(weights, cov)
    
    if port_vol <= 0:
        return 1.0
    
    return float(weighted_vol / port_vol)


def correlation_adjusted_hhi(weights: np.ndarray, corr: np.ndarray) -> float:
    """
    Correlation-adjusted HHI.
    HHI_adj = Σ w_i² + ΣΣ w_i * w_j * ρ_ij (i≠j)
    """
    n = len(weights)
    hhi_adj = 0.0
    
    for i in range(n):
        for j in range(n):
            if i == j:
                hhi_adj += weights[i] ** 2
            else:
                hhi_adj += weights[i] * weights[j] * corr[i, j]
    
    return float(hhi_adj)


# =============================================================================
# LIQUIDITY METRICS
# =============================================================================

def exit_days(position_value: float, adv: float, participation_rate: float = 0.1) -> float:
    """
    Estimate days to exit position.
    Exit_Days = Position / (ADV * Participation_Rate)
    """
    if adv <= 0:
        return float('inf')
    return position_value / (adv * participation_rate)


def market_impact_sqrt(order_size: float, adv: float, volatility: float, alpha: float = 0.1) -> float:
    """
    Almgren-Chriss square-root market impact model.
    MI = α * σ * √(Q/V)
    """
    if adv <= 0:
        return 0.0
    
    participation = order_size / adv
    impact = alpha * volatility * np.sqrt(participation)
    return float(impact)


def liquidity_score(exit_d: float) -> float:
    """
    Convert exit days to 0-100 liquidity score.
    Higher score = more liquid.
    """
    if exit_d <= 0.5:
        return 100.0
    elif exit_d <= 1:
        return 90.0
    elif exit_d <= 2:
        return 75.0
    elif exit_d <= 5:
        return 50.0
    elif exit_d <= 10:
        return 25.0
    else:
        return max(0, 10 - exit_d)


# =============================================================================
# OPTIMIZATION
# =============================================================================

def optimize_max_sharpe(mu: np.ndarray, cov: np.ndarray, rf: float = 0.0,
                        constraints: Optional[Dict] = None) -> np.ndarray:
    """
    Find weights that maximize Sharpe ratio.
    """
    n = len(mu)
    
    def neg_sharpe(w):
        port_ret = w @ mu
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol == 0:
            return 0
        return -(port_ret - rf) / port_vol
    
    # Constraints
    cons = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1}  # Weights sum to 1
    ]
    
    # Bounds (long only by default)
    bounds = [(0, 1) for _ in range(n)]
    
    # Initial guess: equal weights
    w0 = np.ones(n) / n
    
    result = minimize(neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=cons)
    
    return result.x if result.success else w0


def optimize_min_vol(cov: np.ndarray, constraints: Optional[Dict] = None) -> np.ndarray:
    """
    Find minimum volatility portfolio.
    """
    n = cov.shape[0]
    
    def port_vol(w):
        return np.sqrt(w @ cov @ w)
    
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0, 1) for _ in range(n)]
    w0 = np.ones(n) / n
    
    result = minimize(port_vol, w0, method="SLSQP", bounds=bounds, constraints=cons)
    
    return result.x if result.success else w0


def optimize_risk_parity(cov: np.ndarray) -> np.ndarray:
    """
    Find risk parity weights (equal risk contribution).
    """
    n = cov.shape[0]
    target_rc = 1.0 / n
    
    def risk_parity_obj(w):
        rc = percentage_risk_contribution(w, cov)
        return np.sum((rc - target_rc) ** 2)
    
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.01, 1) for _ in range(n)]  # Min 1% per asset
    w0 = np.ones(n) / n
    
    result = minimize(risk_parity_obj, w0, method="SLSQP", bounds=bounds, constraints=cons)
    
    return result.x if result.success else w0


# =============================================================================
# REGIME DETECTION HELPERS
# =============================================================================

def z_score(series: pd.Series, lookback: int = 252) -> float:
    """Compute z-score of latest value vs rolling history."""
    if len(series) < lookback:
        lookback = len(series)
    
    if lookback < 10:
        return 0.0
    
    window = series.tail(lookback)
    current = series.iloc[-1]
    mu = window.mean()
    sigma = window.std()
    
    if sigma == 0:
        return 0.0
    
    return float((current - mu) / sigma)


def rolling_correlation(x: pd.Series, y: pd.Series, window: int = 60) -> pd.Series:
    """Compute rolling correlation between two series."""
    return x.rolling(window).corr(y)
