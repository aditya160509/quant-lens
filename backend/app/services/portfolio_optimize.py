"""
Portfolio Optimization Service - Features 26-29
Markowitz, Risk Parity, Black-Litterman, Factor Tilt
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple, Any
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_returns_data(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """Fetch historical returns for tickers."""
    try:
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        
        if data.empty:
            logger.error("Empty data from yfinance")
            return pd.DataFrame()
        
        # Get Close prices - handle both MultiIndex and single column
        if 'Close' in data.columns:
            close_data = data['Close']
        elif isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0):
                close_data = data['Close']
            else:
                close_data = data.iloc[:, :len(tickers)]
        else:
            close_data = data
        
        if isinstance(close_data, pd.Series):
            close_data = close_data.to_frame(tickers[0])
        
        returns = close_data.pct_change().dropna()
        
        if isinstance(returns.columns, pd.MultiIndex):
            returns.columns = returns.columns.get_level_values(-1)
        
        return returns
    except Exception as e:
        logger.error(f"Error fetching returns: {e}")
        return pd.DataFrame()


def _compute_covariance_matrix(returns: pd.DataFrame, method: str = "sample") -> np.ndarray:
    """Compute covariance matrix with optional shrinkage."""
    if method == "shrinkage":
        # Ledoit-Wolf shrinkage
        sample_cov = returns.cov().values
        n = len(returns)
        p = returns.shape[1]
        
        # Shrinkage target: diagonal matrix
        mu = np.trace(sample_cov) / p
        delta = np.eye(p) * mu
        
        # Shrinkage intensity (simplified)
        shrinkage = min(1.0, max(0.0, (1.0 / n)))
        
        return shrinkage * delta + (1 - shrinkage) * sample_cov
    elif method == "ewma":
        # Exponentially weighted
        span = min(60, len(returns) // 2)
        ewma_returns = returns.ewm(span=span).mean()
        return ewma_returns.cov().values
    else:
        return returns.cov().values


def _annualize_returns(returns: pd.DataFrame) -> np.ndarray:
    """Annualize daily returns."""
    return returns.mean().values * 252


def _annualize_volatility(returns: pd.DataFrame) -> np.ndarray:
    """Annualize daily volatility."""
    return returns.std().values * np.sqrt(252)


# =============================================================================
# FEATURE 26: MARKOWITZ PORTFOLIO OPTIMIZER
# =============================================================================

def compute_markowitz(
    tickers: List[str],
    mode: str = "max_sharpe",
    target_return: Optional[float] = None,
    target_volatility: Optional[float] = None,
    constraints: Dict = None,
    covariance_method: str = "sample",
    risk_free_rate: float = 0.05
) -> Dict[str, Any]:
    """
    Mean-Variance Portfolio Optimization (Markowitz).
    
    Args:
        tickers: List of asset tickers
        mode: 'max_sharpe', 'min_volatility', 'target_return', 'target_volatility'
        target_return: Target annual return (for target_return mode)
        target_volatility: Target annual volatility (for target_volatility mode)
        constraints: Dict with min_weight, max_weight, long_only
        covariance_method: 'sample', 'shrinkage', or 'ewma'
        risk_free_rate: Annual risk-free rate
    
    Returns:
        Dict with optimal_weights, metrics, efficient_frontier, risk_contribution
    """
    try:
        # Get data
        returns = _get_returns_data(tickers, "2y")
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        n_assets = len(tickers)
        mean_returns = _annualize_returns(returns)
        cov_matrix = _compute_covariance_matrix(returns, covariance_method) * 252
        
        # Default constraints
        if constraints is None:
            constraints = {}
        min_weight = constraints.get("min_weight", 0.0)
        max_weight = constraints.get("max_weight", 1.0)
        long_only = constraints.get("long_only", True)
        
        bounds = [(max(0, min_weight) if long_only else min_weight, max_weight) for _ in range(n_assets)]
        
        # Portfolio metrics functions
        def portfolio_return(weights):
            return np.dot(weights, mean_returns)
        
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        def neg_sharpe(weights):
            ret = portfolio_return(weights)
            vol = portfolio_volatility(weights)
            return -(ret - risk_free_rate) / vol if vol > 0 else 0
        
        # Constraint: weights sum to 1
        eq_constraint = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        # Initial guess: equal weights
        init_weights = np.array([1.0 / n_assets] * n_assets)
        
        # Optimization based on mode
        if mode == "max_sharpe":
            result = minimize(neg_sharpe, init_weights, method='SLSQP',
                            bounds=bounds, constraints=[eq_constraint])
        elif mode == "min_volatility":
            result = minimize(portfolio_volatility, init_weights, method='SLSQP',
                            bounds=bounds, constraints=[eq_constraint])
        elif mode == "target_return" and target_return is not None:
            ret_constraint = {'type': 'eq', 'fun': lambda w: portfolio_return(w) - target_return}
            result = minimize(portfolio_volatility, init_weights, method='SLSQP',
                            bounds=bounds, constraints=[eq_constraint, ret_constraint])
        elif mode == "target_volatility" and target_volatility is not None:
            vol_constraint = {'type': 'eq', 'fun': lambda w: portfolio_volatility(w) - target_volatility}
            result = minimize(lambda w: -portfolio_return(w), init_weights, method='SLSQP',
                            bounds=bounds, constraints=[eq_constraint, vol_constraint])
        else:
            result = minimize(neg_sharpe, init_weights, method='SLSQP',
                            bounds=bounds, constraints=[eq_constraint])
        
        optimal_weights = result.x
        opt_return = portfolio_return(optimal_weights)
        opt_vol = portfolio_volatility(optimal_weights)
        opt_sharpe = (opt_return - risk_free_rate) / opt_vol if opt_vol > 0 else 0
        
        # Compute risk contribution
        marginal_risk = np.dot(cov_matrix, optimal_weights) / opt_vol
        risk_contribution = optimal_weights * marginal_risk
        risk_contribution_pct = risk_contribution / np.sum(risk_contribution) * 100
        
        # Generate efficient frontier
        frontier_points = []
        target_returns = np.linspace(mean_returns.min(), mean_returns.max(), 50)
        
        for tr in target_returns:
            try:
                ret_con = {'type': 'eq', 'fun': lambda w, tr=tr: portfolio_return(w) - tr}
                ef_result = minimize(portfolio_volatility, init_weights, method='SLSQP',
                                   bounds=bounds, constraints=[eq_constraint, ret_con])
                if ef_result.success:
                    ef_vol = portfolio_volatility(ef_result.x)
                    ef_ret = portfolio_return(ef_result.x)
                    frontier_points.append({
                        "volatility": float(ef_vol),
                        "return": float(ef_ret),
                        "sharpe": float((ef_ret - risk_free_rate) / ef_vol) if ef_vol > 0 else 0,
                        "weights": {t: float(w) for t, w in zip(tickers, ef_result.x)}
                    })
            except:
                continue
        
        return {
            "optimal_weights": {t: float(w) for t, w in zip(tickers, optimal_weights)},
            "metrics": {
                "expected_return": float(opt_return),
                "expected_volatility": float(opt_vol),
                "sharpe_ratio": float(opt_sharpe),
                "max_drawdown_estimate": float(-opt_vol * 2.5)  # Rough estimate
            },
            "risk_contribution": {t: float(rc) for t, rc in zip(tickers, risk_contribution_pct)},
            "efficient_frontier": frontier_points,
            "optimization_success": result.success,
            "covariance_method": covariance_method
        }
        
    except Exception as e:
        logger.error(f"Markowitz optimization error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 27: RISK PARITY ALLOCATOR
# =============================================================================

def compute_risk_parity(
    tickers: List[str],
    target_volatility: float = 0.12,
    min_weight: float = 0.02,
    crisis_mode: bool = False,
    stress_factor: float = 1.0,
    volatility_lookback: str = "1y"
) -> Dict[str, Any]:
    """
    Risk Parity Portfolio Allocation.
    
    Equalizes risk contribution across assets rather than capital allocation.
    
    Args:
        tickers: List of asset tickers
        target_volatility: Target annual portfolio volatility
        min_weight: Minimum weight per asset
        crisis_mode: Adjust for correlation spike scenarios
        stress_factor: Stress multiplier (1.0 = normal, 2.0 = extreme)
        volatility_lookback: Lookback period for volatility
    
    Returns:
        Dict with risk_parity_weights, risk_contributions, leverage_factor
    """
    try:
        returns = _get_returns_data(tickers, volatility_lookback)
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        n_assets = len(tickers)
        
        # Compute volatilities
        vols = _annualize_volatility(returns)
        
        # Compute correlation matrix
        corr_matrix = returns.corr().values
        
        # Apply stress factor in crisis mode
        if crisis_mode:
            # Increase correlations
            avg_corr = (corr_matrix.sum() - n_assets) / (n_assets * (n_assets - 1))
            stressed_corr = corr_matrix * (1 - stress_factor * 0.2) + stress_factor * 0.2
            np.fill_diagonal(stressed_corr, 1.0)
            corr_matrix = stressed_corr
        
        # Build covariance from stressed correlations
        vol_diag = np.diag(vols)
        cov_matrix = vol_diag @ corr_matrix @ vol_diag
        
        # Risk parity objective: equal risk contribution
        def risk_budget_objective(weights):
            weights = np.abs(weights)
            weights = weights / np.sum(weights)
            
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_contrib = np.dot(cov_matrix, weights)
            risk_contrib = weights * marginal_contrib / port_vol
            
            # Target: equal risk contribution
            target_contrib = port_vol / n_assets
            return np.sum((risk_contrib - target_contrib) ** 2)
        
        # Optimize
        init_weights = np.array([1.0 / n_assets] * n_assets)
        bounds = [(min_weight, 1.0) for _ in range(n_assets)]
        eq_constraint = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        result = minimize(risk_budget_objective, init_weights, method='SLSQP',
                         bounds=bounds, constraints=[eq_constraint])
        
        rp_weights = result.x
        rp_weights = rp_weights / np.sum(rp_weights)  # Normalize
        
        # Compute actual risk contributions
        port_vol = np.sqrt(np.dot(rp_weights.T, np.dot(cov_matrix, rp_weights)))
        marginal_contrib = np.dot(cov_matrix, rp_weights)
        risk_contrib = rp_weights * marginal_contrib / port_vol
        risk_contrib_pct = risk_contrib / np.sum(risk_contrib) * 100
        
        # Leverage factor for volatility targeting
        leverage_factor = target_volatility / port_vol if port_vol > 0 else 1.0
        
        # Diversification score (0-100)
        # Perfect diversification = equal risk contributions
        contrib_variance = np.var(risk_contrib_pct)
        max_variance = (100 / n_assets) ** 2 * n_assets  # All in one asset
        diversification_score = max(0, 100 * (1 - contrib_variance / max_variance))
        
        return {
            "risk_parity_weights": {t: float(w) for t, w in zip(tickers, rp_weights)},
            "risk_contributions": {t: float(rc) for t, rc in zip(tickers, risk_contrib_pct)},
            "metrics": {
                "portfolio_volatility": float(port_vol),
                "target_volatility": float(target_volatility),
                "leverage_factor": float(leverage_factor),
                "diversification_score": float(diversification_score)
            },
            "asset_volatilities": {t: float(v) for t, v in zip(tickers, vols)},
            "crisis_mode": crisis_mode,
            "stress_factor": stress_factor,
            "optimization_success": result.success
        }
        
    except Exception as e:
        logger.error(f"Risk parity error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 28: BLACK-LITTERMAN MODEL
# =============================================================================

def compute_black_litterman(
    tickers: List[str],
    views: List[Dict],
    market_weights: Optional[Dict[str, float]] = None,
    risk_aversion: float = 2.5,
    tau: float = 0.05,
    risk_free_rate: float = 0.05
) -> Dict[str, Any]:
    """
    Black-Litterman Model for portfolio allocation.
    
    Blends market equilibrium returns with investor views using Bayesian statistics.
    
    Args:
        tickers: List of asset tickers
        views: List of view dicts with keys:
            - type: 'absolute' or 'relative'
            - asset: ticker (for absolute) or [asset1, asset2] (for relative)
            - return: expected return (annual)
            - confidence: 0-1 confidence level
        market_weights: Dict of market cap weights (or equal if None)
        risk_aversion: Risk aversion coefficient (1-5)
        tau: Scaling factor for uncertainty (typically 0.01-0.1)
        risk_free_rate: Annual risk-free rate
    
    Returns:
        Dict with bl_weights, equilibrium_returns, posterior_returns, view_impacts
    """
    try:
        returns = _get_returns_data(tickers, "2y")
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        n_assets = len(tickers)
        cov_matrix = _compute_covariance_matrix(returns, "shrinkage") * 252
        
        # Market weights (default: equal)
        if market_weights is None:
            w_mkt = np.array([1.0 / n_assets] * n_assets)
        else:
            w_mkt = np.array([market_weights.get(t, 1.0/n_assets) for t in tickers])
            w_mkt = w_mkt / np.sum(w_mkt)
        
        # Step 1: Equilibrium returns (reverse optimization)
        # π = λ × Σ × w_market
        equilibrium_returns = risk_aversion * np.dot(cov_matrix, w_mkt)
        
        # Step 2: Build view matrices P and Q
        n_views = len(views)
        if n_views == 0:
            # No views - return market equilibrium
            return {
                "bl_weights": {t: float(w) for t, w in zip(tickers, w_mkt)},
                "equilibrium_returns": {t: float(r) for t, r in zip(tickers, equilibrium_returns)},
                "posterior_returns": {t: float(r) for t, r in zip(tickers, equilibrium_returns)},
                "view_impacts": [],
                "no_views": True
            }
        
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        omega_diag = np.zeros(n_views)
        
        ticker_idx = {t: i for i, t in enumerate(tickers)}
        
        for i, view in enumerate(views):
            Q[i] = view.get("return", 0)
            confidence = view.get("confidence", 0.5)
            
            if view.get("type") == "absolute":
                asset = view.get("asset")
                if asset in ticker_idx:
                    P[i, ticker_idx[asset]] = 1
            elif view.get("type") == "relative":
                assets = view.get("asset", [])
                if len(assets) == 2 and assets[0] in ticker_idx and assets[1] in ticker_idx:
                    P[i, ticker_idx[assets[0]]] = 1
                    P[i, ticker_idx[assets[1]]] = -1
            
            # View uncertainty (inverse of confidence)
            omega_diag[i] = (1 - confidence + 0.01) * np.dot(P[i], np.dot(cov_matrix, P[i]))
        
        Omega = np.diag(omega_diag)
        
        # Step 3: Bayesian blending
        # E[R] = [(τΣ)^-1 + P^T Ω^-1 P]^-1 × [(τΣ)^-1 π + P^T Ω^-1 Q]
        tau_cov_inv = np.linalg.inv(tau * cov_matrix)
        omega_inv = np.linalg.inv(Omega + np.eye(n_views) * 1e-8)
        
        M = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P)
        posterior_returns = M @ (tau_cov_inv @ equilibrium_returns + P.T @ omega_inv @ Q)
        
        # Step 4: Optimize with posterior returns
        def neg_utility(weights):
            ret = np.dot(weights, posterior_returns)
            risk = np.dot(weights.T, np.dot(cov_matrix, weights))
            return -(ret - risk_aversion * risk / 2)
        
        bounds = [(0, 1) for _ in range(n_assets)]
        eq_constraint = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        init_weights = w_mkt.copy()
        result = minimize(neg_utility, init_weights, method='SLSQP',
                         bounds=bounds, constraints=[eq_constraint])
        
        bl_weights = result.x
        
        # Compute view impacts
        view_impacts = []
        for i, view in enumerate(views):
            impact = {
                "view": view,
                "return_adjustment": float(posterior_returns[ticker_idx.get(view.get("asset", tickers[0]), 0)] - 
                                          equilibrium_returns[ticker_idx.get(view.get("asset", tickers[0]), 0)]),
            }
            view_impacts.append(impact)
        
        return {
            "bl_weights": {t: float(w) for t, w in zip(tickers, bl_weights)},
            "equilibrium_returns": {t: float(r) for t, r in zip(tickers, equilibrium_returns)},
            "posterior_returns": {t: float(r) for t, r in zip(tickers, posterior_returns)},
            "view_impacts": view_impacts,
            "market_weights": {t: float(w) for t, w in zip(tickers, w_mkt)},
            "optimization_success": result.success
        }
        
    except Exception as e:
        logger.error(f"Black-Litterman error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 29: FACTOR TILT OPTIMIZER
# =============================================================================

def compute_factor_tilt(
    tickers: List[str],
    target_factors: Dict[str, float],
    factor_strength: float = 50.0,
    neutralize_factors: List[str] = None
) -> Dict[str, Any]:
    """
    Factor Tilt Portfolio Optimization.
    
    Allocates capital to achieve desired exposure to systematic risk factors.
    
    Args:
        tickers: List of asset tickers
        target_factors: Dict with factor targets (-100 to +100):
            - momentum, value, quality, size, low_vol
        factor_strength: Overall tilt intensity (0-100)
        neutralize_factors: List of factors to neutralize
    
    Returns:
        Dict with factor_weights, achieved_exposure, factor_contributions
    """
    try:
        returns = _get_returns_data(tickers, "1y")
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        n_assets = len(tickers)
        
        # Compute factor loadings for each asset
        factor_loadings = np.zeros((n_assets, 5))
        factor_names = ["momentum", "value", "quality", "size", "low_vol"]
        
        for i, ticker in enumerate(tickers):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="1y")
                
                # Momentum: 12-month return
                if len(hist) > 0:
                    momentum = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) if len(hist) > 200 else 0
                else:
                    momentum = 0
                
                # Value: inverse of P/E (higher = more value)
                pe = info.get('trailingPE', 20)
                value = 1 / pe if pe and pe > 0 else 0.05
                
                # Quality: ROE
                roe = info.get('returnOnEquity', 0.1) or 0.1
                quality = roe
                
                # Size: log market cap (inverted - small cap is positive)
                market_cap = info.get('marketCap', 1e10)
                size = -np.log10(max(market_cap, 1e6))  # Smaller = higher score
                
                # Low Vol: inverse of volatility
                if len(returns) > 0 and ticker in returns.columns:
                    vol = returns[ticker].std() * np.sqrt(252)
                    low_vol = 1 / (vol + 0.01)
                else:
                    low_vol = 1
                
                # Z-score normalization will happen later
                factor_loadings[i] = [momentum, value, quality, size, low_vol]
                
            except Exception as e:
                logger.warning(f"Factor computation error for {ticker}: {e}")
                factor_loadings[i] = [0, 0.05, 0.1, 0, 1]
        
        # Standardize factor loadings (z-scores)
        factor_loadings = (factor_loadings - factor_loadings.mean(axis=0)) / (factor_loadings.std(axis=0) + 1e-8)
        
        # Target factor exposure vector
        target_exposure = np.array([
            target_factors.get("momentum", 0) / 100,
            target_factors.get("value", 0) / 100,
            target_factors.get("quality", 0) / 100,
            target_factors.get("size", 0) / 100,
            target_factors.get("low_vol", 0) / 100
        ])
        
        # Apply factor strength scaling
        target_exposure = target_exposure * (factor_strength / 100)
        
        # Neutralize specified factors
        if neutralize_factors:
            for factor in neutralize_factors:
                if factor in factor_names:
                    idx = factor_names.index(factor)
                    target_exposure[idx] = 0
        
        # Optimization: minimize variance while achieving target exposure
        cov_matrix = returns.cov().values * 252
        
        def objective(weights):
            # Portfolio variance
            port_var = np.dot(weights.T, np.dot(cov_matrix, weights))
            
            # Factor exposure deviation
            achieved = factor_loadings.T @ weights
            exposure_penalty = np.sum((achieved - target_exposure) ** 2) * 100
            
            return port_var + exposure_penalty
        
        bounds = [(0, 0.3) for _ in range(n_assets)]  # Max 30% per asset
        eq_constraint = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        init_weights = np.array([1.0 / n_assets] * n_assets)
        result = minimize(objective, init_weights, method='SLSQP',
                         bounds=bounds, constraints=[eq_constraint])
        
        factor_weights = result.x
        
        # Compute achieved factor exposure
        achieved_exposure = factor_loadings.T @ factor_weights
        
        # Factor contribution to portfolio
        factor_contributions = {}
        for i, name in enumerate(factor_names):
            factor_contributions[name] = {
                "target": float(target_exposure[i] * 100),
                "achieved": float(achieved_exposure[i] * 100),
                "deviation": float((achieved_exposure[i] - target_exposure[i]) * 100)
            }
        
        # Asset factor scores
        asset_factors = {}
        for i, ticker in enumerate(tickers):
            asset_factors[ticker] = {name: float(factor_loadings[i, j]) for j, name in enumerate(factor_names)}
        
        return {
            "factor_weights": {t: float(w) for t, w in zip(tickers, factor_weights)},
            "achieved_exposure": {name: float(achieved_exposure[i]) for i, name in enumerate(factor_names)},
            "target_exposure": {name: float(target_exposure[i]) for i, name in enumerate(factor_names)},
            "factor_contributions": factor_contributions,
            "asset_factor_scores": asset_factors,
            "factor_strength": factor_strength,
            "optimization_success": result.success
        }
        
    except Exception as e:
        logger.error(f"Factor tilt error: {e}")
        return {"error": str(e)}
