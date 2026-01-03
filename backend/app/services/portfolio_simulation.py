"""
Portfolio Simulation Service - Features 34, 37
Monte Carlo Simulation, VaR & CVaR Calculator
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import List, Dict, Optional, Any
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_returns_data(tickers: List[str], period: str = "2y") -> pd.DataFrame:
    """Fetch historical returns for tickers."""
    try:
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        
        # Handle different yfinance output formats
        if data.empty:
            logger.error("Empty data from yfinance")
            return pd.DataFrame()
        
        # Get Close prices - handle both MultiIndex and single column
        if 'Close' in data.columns:
            # Single ticker or MultiIndex with 'Close' at top level
            close_data = data['Close']
        elif isinstance(data.columns, pd.MultiIndex):
            # MultiIndex format: ('Price', 'Ticker')
            if 'Close' in data.columns.get_level_values(0):
                close_data = data['Close']
            else:
                # Fallback to first price column
                close_data = data.iloc[:, :len(tickers)]
        else:
            close_data = data
        
        # Convert Series to DataFrame if needed
        if isinstance(close_data, pd.Series):
            close_data = close_data.to_frame(tickers[0])
        
        # Calculate returns
        returns = close_data.pct_change().dropna()
        
        # Ensure column names match tickers
        if isinstance(returns.columns, pd.MultiIndex):
            returns.columns = returns.columns.get_level_values(-1)
        
        return returns
    except Exception as e:
        logger.error(f"Error fetching returns: {e}")
        return pd.DataFrame()


def _compute_portfolio_returns(returns: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    """Compute weighted portfolio returns."""
    port_returns = pd.Series(0, index=returns.index)
    for ticker, weight in weights.items():
        if ticker in returns.columns:
            port_returns += returns[ticker] * weight
    return port_returns


# =============================================================================
# FEATURE 34: MONTE CARLO SIMULATION
# =============================================================================

def run_monte_carlo(
    positions: List[Dict],
    n_simulations: int = 10000,
    horizon_years: float = 5,
    time_step: str = "monthly",
    initial_capital: float = 100000,
    contributions: float = 0,
    contribution_frequency: str = "monthly",
    withdrawals: float = 0,
    target_wealth: Optional[float] = None,
    inflation_rate: float = 0.02,
    fat_tails: bool = False,
    volatility_clustering: bool = False
) -> Dict[str, Any]:
    """
    Forward-looking probabilistic analysis of portfolio outcomes.
    
    Args:
        positions: List of position dicts with ticker and weight
        n_simulations: Number of Monte Carlo paths (1000-100000)
        horizon_years: Projection horizon in years
        time_step: 'daily', 'monthly', 'annual'
        initial_capital: Starting portfolio value
        contributions: Regular contribution amount
        contribution_frequency: 'monthly', 'quarterly', 'annual'
        withdrawals: Regular withdrawal amount
        target_wealth: Target wealth for goal analysis
        inflation_rate: Annual inflation for real returns
        fat_tails: Enable fat-tail distribution
        volatility_clustering: Enable volatility persistence
    
    Returns:
        Dict with fan_chart, terminal_distribution, probability_metrics
    """
    try:
        tickers = [p.get("ticker") for p in positions]
        weights = {p.get("ticker"): p.get("weight", 0) for p in positions}
        
        # Fetch historical data
        returns = _get_returns_data(tickers, "3y")
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        # Compute portfolio returns
        port_returns = _compute_portfolio_returns(returns, weights)
        
        # Estimate parameters
        mu = port_returns.mean()
        sigma = port_returns.std()
        
        # Time step conversion
        if time_step == "daily":
            periods_per_year = 252
        elif time_step == "monthly":
            periods_per_year = 12
        else:
            periods_per_year = 1
        
        n_periods = int(horizon_years * periods_per_year)
        dt = 1 / periods_per_year
        
        # Annualized parameters
        mu_annual = mu * 252
        sigma_annual = sigma * np.sqrt(252)
        
        # Period parameters
        mu_period = mu_annual * dt
        sigma_period = sigma_annual * np.sqrt(dt)
        
        # Cash flows
        if contribution_frequency == "monthly":
            contribution_periods = periods_per_year / 12
        elif contribution_frequency == "quarterly":
            contribution_periods = periods_per_year / 4
        else:
            contribution_periods = 1
        
        net_cashflow_per_period = (contributions - withdrawals) * (dt * 12)  # Monthly basis
        
        # Simulate paths
        np.random.seed(42)  # For reproducibility
        
        if fat_tails:
            # Use Student's t-distribution with 5 degrees of freedom
            innovations = stats.t.rvs(df=5, size=(n_simulations, n_periods))
            innovations = innovations / np.sqrt(5/3)  # Normalize variance
        else:
            innovations = np.random.randn(n_simulations, n_periods)
        
        # Initialize paths
        paths = np.zeros((n_simulations, n_periods + 1))
        paths[:, 0] = initial_capital
        
        if volatility_clustering:
            # Simple GARCH-like effect
            vol_factor = np.ones((n_simulations, n_periods))
            for t in range(1, n_periods):
                shock = np.abs(innovations[:, t-1])
                vol_factor[:, t] = 0.9 * vol_factor[:, t-1] + 0.1 * shock
        else:
            vol_factor = np.ones((n_simulations, n_periods))
        
        # Generate paths
        for t in range(n_periods):
            returns_sim = mu_period + sigma_period * vol_factor[:, t] * innovations[:, t]
            paths[:, t+1] = paths[:, t] * (1 + returns_sim) + net_cashflow_per_period
            paths[:, t+1] = np.maximum(paths[:, t+1], 0)  # Floor at zero
        
        # Apply inflation adjustment
        if inflation_rate > 0:
            inflation_factor = (1 + inflation_rate) ** (np.arange(n_periods + 1) / periods_per_year)
            paths_real = paths / inflation_factor
        else:
            paths_real = paths
        
        # Compute statistics
        percentiles = [5, 10, 25, 50, 75, 90, 95]
        percentile_paths = np.percentile(paths_real, percentiles, axis=0)
        
        # Fan chart data (sample periods for visualization)
        sample_points = np.linspace(0, n_periods, min(100, n_periods + 1)).astype(int)
        sample_points = np.unique(sample_points)
        
        fan_chart = []
        for i in sample_points:
            year = i / periods_per_year
            values = paths_real[:, i]
            fan_chart.append({
                "year": float(year),
                "p5": float(np.percentile(values, 5)),
                "p10": float(np.percentile(values, 10)),
                "p25": float(np.percentile(values, 25)),
                "p50": float(np.percentile(values, 50)),
                "p75": float(np.percentile(values, 75)),
                "p90": float(np.percentile(values, 90)),
                "p95": float(np.percentile(values, 95)),
                "mean": float(np.mean(values))
            })
        
        # Terminal wealth distribution
        terminal_values = paths_real[:, -1]
        
        # Histogram bins
        hist, bin_edges = np.histogram(terminal_values, bins=50)
        histogram = [
            {"bin_start": float(bin_edges[i]), "bin_end": float(bin_edges[i+1]), "count": int(hist[i])}
            for i in range(len(hist))
        ]
        
        # Probability metrics
        p_loss = float(np.mean(terminal_values < initial_capital)) * 100
        p_double = float(np.mean(terminal_values >= initial_capital * 2)) * 100
        p_target = float(np.mean(terminal_values >= target_wealth)) * 100 if target_wealth else None
        
        # Worst case scenarios
        worst_5_pct = float(np.percentile(terminal_values, 5))
        expected_shortfall = float(np.mean(terminal_values[terminal_values <= np.percentile(terminal_values, 5)]))
        
        # Best and worst paths
        best_path_idx = np.argmax(terminal_values)
        worst_path_idx = np.argmin(terminal_values)
        
        best_path = [{"year": i/periods_per_year, "value": float(paths_real[best_path_idx, i])} for i in sample_points]
        worst_path = [{"year": i/periods_per_year, "value": float(paths_real[worst_path_idx, i])} for i in sample_points]
        
        return {
            "fan_chart": fan_chart,
            "terminal_distribution": {
                "histogram": histogram,
                "mean": float(np.mean(terminal_values)),
                "median": float(np.median(terminal_values)),
                "std": float(np.std(terminal_values)),
                "min": float(np.min(terminal_values)),
                "max": float(np.max(terminal_values))
            },
            "probability_metrics": {
                "p_capital_loss": p_loss,
                "p_doubling": p_double,
                "p_target": p_target,
                "worst_5_pct": worst_5_pct,
                "expected_shortfall": expected_shortfall
            },
            "best_path": best_path,
            "worst_path": worst_path,
            "parameters": {
                "n_simulations": n_simulations,
                "horizon_years": horizon_years,
                "initial_capital": initial_capital,
                "expected_annual_return": float(mu_annual),
                "annual_volatility": float(sigma_annual)
            }
        }
        
    except Exception as e:
        logger.error(f"Monte Carlo error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 37: VaR & CVaR CALCULATOR
# =============================================================================

def compute_var(
    positions: List[Dict],
    confidence_level: float = 0.95,
    horizon_days: int = 1,
    method: str = "historical",
    portfolio_value: float = 100000,
    stress_scenarios: bool = False
) -> Dict[str, Any]:
    """
    Value at Risk and Conditional VaR (Expected Shortfall) calculation.
    
    Args:
        positions: List of position dicts with ticker and weight
        confidence_level: VaR confidence (0.90, 0.95, 0.99)
        horizon_days: Time horizon (1, 5, 21 days)
        method: 'historical', 'parametric', 'monte_carlo'
        portfolio_value: Current portfolio value
        stress_scenarios: Include stress scenario analysis
    
    Returns:
        Dict with var, cvar, rolling_var, tail_concentration
    """
    try:
        tickers = [p.get("ticker") for p in positions]
        weights = {p.get("ticker"): p.get("weight", 0) for p in positions}
        
        # Fetch historical data
        returns = _get_returns_data(tickers, "3y")
        if returns.empty:
            return {"error": "Failed to fetch price data"}
        
        # Compute portfolio returns
        port_returns = _compute_portfolio_returns(returns, weights)
        
        # Scale to horizon
        if horizon_days > 1:
            # Square root of time scaling
            scaling_factor = np.sqrt(horizon_days)
        else:
            scaling_factor = 1
        
        # === Historical VaR ===
        if method == "historical":
            alpha = 1 - confidence_level
            var_pct = float(np.percentile(port_returns, alpha * 100))
            
            # CVaR: average of returns below VaR
            tail_returns = port_returns[port_returns <= var_pct]
            cvar_pct = float(tail_returns.mean()) if len(tail_returns) > 0 else var_pct
            
        # === Parametric VaR ===
        elif method == "parametric":
            mu = port_returns.mean()
            sigma = port_returns.std()
            
            # Z-score for confidence level
            z = stats.norm.ppf(1 - confidence_level)
            var_pct = float(mu + z * sigma)
            
            # Parametric CVaR
            pdf_z = stats.norm.pdf(z)
            cvar_pct = float(mu - sigma * pdf_z / (1 - confidence_level))
            
        # === Monte Carlo VaR ===
        else:  # monte_carlo
            mu = port_returns.mean()
            sigma = port_returns.std()
            
            # Simulate 10,000 scenarios
            simulated = np.random.normal(mu, sigma, 10000)
            
            alpha = 1 - confidence_level
            var_pct = float(np.percentile(simulated, alpha * 100))
            
            tail_sim = simulated[simulated <= var_pct]
            cvar_pct = float(tail_sim.mean()) if len(tail_sim) > 0 else var_pct
        
        # Apply horizon scaling
        var_pct_scaled = var_pct * scaling_factor
        cvar_pct_scaled = cvar_pct * scaling_factor
        
        # Convert to dollar amounts
        var_dollar = float(abs(var_pct_scaled) * portfolio_value)
        cvar_dollar = float(abs(cvar_pct_scaled) * portfolio_value)
        
        # === Rolling VaR (90-day window) ===
        rolling_window = 90
        rolling_var = []
        rolling_dates = []
        
        for i in range(rolling_window, len(port_returns)):
            window_returns = port_returns.iloc[i-rolling_window:i]
            alpha = 1 - confidence_level
            roll_var = float(np.percentile(window_returns, alpha * 100))
            rolling_var.append(abs(roll_var))
            rolling_dates.append(str(port_returns.index[i].date()) if hasattr(port_returns.index[i], 'date') else str(port_returns.index[i]))
        
        # === Tail Loss Concentration (asset contribution to CVaR) ===
        tail_concentration = {}
        threshold = np.percentile(port_returns, (1 - confidence_level) * 100)
        tail_days = port_returns <= threshold
        
        for ticker in tickers:
            if ticker in returns.columns:
                ticker_returns = returns[ticker]
                # Contribution on tail days
                tail_contrib = (ticker_returns[tail_days] * weights.get(ticker, 0)).sum()
                total_tail = port_returns[tail_days].sum()
                contrib_pct = float(tail_contrib / total_tail * 100) if total_tail != 0 else 0
                tail_concentration[ticker] = contrib_pct
        
        # === VaR Breach Analysis ===
        var_threshold = np.percentile(port_returns, (1 - confidence_level) * 100)
        breaches = port_returns < var_threshold
        breach_count = breaches.sum()
        expected_breaches = len(port_returns) * (1 - confidence_level)
        breach_ratio = float(breach_count / expected_breaches) if expected_breaches > 0 else 1
        
        # === Stress VaR ===
        stress_var = {}
        if stress_scenarios:
            # Correlation stress: assume all correlations go to 0.8
            stress_factor = 1.5  # Increase vol by 50%
            stress_var["volatility_shock"] = float(abs(var_pct_scaled) * stress_factor)
            stress_var["correlation_spike"] = float(abs(var_pct_scaled) * 1.3)
            stress_var["tail_event"] = float(abs(cvar_pct_scaled) * 2)
        
        # Risk thermometer (0-100)
        var_severity = abs(var_pct_scaled)
        if var_severity < 0.02:
            risk_level = "low"
            thermometer = 25
        elif var_severity < 0.05:
            risk_level = "medium"
            thermometer = 50
        elif var_severity < 0.10:
            risk_level = "high"
            thermometer = 75
        else:
            risk_level = "extreme"
            thermometer = 95
        
        return {
            "var": {
                "percentage": float(abs(var_pct_scaled)),
                "dollar": var_dollar,
                "horizon_days": horizon_days,
                "confidence": confidence_level
            },
            "cvar": {
                "percentage": float(abs(cvar_pct_scaled)),
                "dollar": cvar_dollar
            },
            "risk_thermometer": {
                "level": risk_level,
                "value": thermometer
            },
            "rolling_var": {
                "dates": rolling_dates,
                "values": rolling_var
            },
            "tail_concentration": tail_concentration,
            "breach_analysis": {
                "breach_count": int(breach_count),
                "expected_breaches": float(expected_breaches),
                "breach_ratio": breach_ratio,
                "warning": breach_ratio > 1.5
            },
            "stress_var": stress_var,
            "method": method,
            "portfolio_value": portfolio_value
        }
        
    except Exception as e:
        logger.error(f"VaR calculation error: {e}")
        return {"error": str(e)}
