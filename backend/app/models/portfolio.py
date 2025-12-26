import pandas as pd
import numpy as np
from scipy.optimize import minimize
import logging

logger = logging.getLogger(__name__)

def optimize_portfolio(returns_df: pd.DataFrame, objective: str = "max_sharpe", risk_free_rate: float = 0.04) -> dict:
    """
    Optimizes portfolio weights.
    
    Args:
        returns_df (pd.DataFrame): Asset returns.
        objective (str): "max_sharpe", "min_vol", "risk_parity".
        
    Returns:
        dict: Optimal weights and metrics.
    """
    try:
        mu = returns_df.mean() * 252
        cov = returns_df.cov() * 252
        n_assets = len(mu)
        
        if n_assets < 2:
            return {"weights": {c: 1.0 for c in returns_df.columns}}
            
        # Constraints: sum(w) = 1, 0 <= w <= 1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(n_assets))
        initial_guess = n_assets * [1. / n_assets,]
        
        def portfolio_vol(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            
        def negative_sharpe(weights):
            p_ret = np.dot(weights.T, mu)
            p_vol = portfolio_vol(weights)
            return -(p_ret - risk_free_rate) / p_vol
            
        if objective == "max_sharpe":
            result = minimize(negative_sharpe, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
        elif objective == "min_vol":
            result = minimize(portfolio_vol, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
        elif objective == "risk_parity":
            # Simplified risk parity: equal risk contribution
            # This is harder to solve with minimize, usually requires specific objective
            # Obj: sum((w_i * (Cov * w)_i - target_risk)^2)
            # For now, let's just do 1/vol weighting as a proxy or stick to min_vol
            # Or implement true risk parity
            def risk_budget_objective(weights):
                p_vol = portfolio_vol(weights)
                # Marginal Risk Contribution
                mrc = np.dot(cov, weights) / p_vol
                # Risk Contribution
                rc = weights * mrc
                # Target is equal risk
                target = p_vol / n_assets
                return np.sum((rc - target)**2)
                
            result = minimize(risk_budget_objective, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
        else:
            return {"error": "Unknown objective"}
            
        if not result.success:
            return {"error": "Optimization failed"}
            
        weights = dict(zip(returns_df.columns, result.x))
        
        # Calculate metrics for optimized portfolio
        opt_ret = np.dot(result.x, mu)
        opt_vol = portfolio_vol(result.x)
        opt_sharpe = (opt_ret - risk_free_rate) / opt_vol
        
        return {
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "metrics": {
                "expected_return": round(opt_ret, 4),
                "expected_volatility": round(opt_vol, 4),
                "sharpe_ratio": round(opt_sharpe, 4)
            }
        }
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return {"error": str(e)}
