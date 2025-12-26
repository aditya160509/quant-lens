import numpy as np
import pandas as pd
import statsmodels.api as sm

def log_return(prices):
    """
    Compute log returns: ln(P_t / P_{t-1})
    """
    return np.log(prices / prices.shift(1))

def simple_return(prices):
    """
    Compute simple returns: P_t / P_{t-1} - 1
    """
    return prices.pct_change()

def cumulative_return_index(returns, start_value=100):
    """
    Compute cumulative return index starting at start_value.
    index_t = index_{t-1} * (1 + R_t)
    """
    return start_value * (1 + returns).cumprod()

def rolling_volatility(log_returns, window=21, annualize=True):
    """
    Compute rolling standard deviation of log returns.
    Annualized by sqrt(252) if requested.
    """
    vol = log_returns.rolling(window=window).std()
    if annualize:
        return vol * np.sqrt(252)
    return vol

def rolling_correlation(series_a, series_b, window=60):
    """
    Compute rolling correlation between two return series.
    """
    return series_a.rolling(window=window).corr(series_b)

def max_drawdown(prices):
    """
    Compute Max Drawdown series.
    DD_t = P_t / Peak_t - 1
    """
    peak = prices.cummax()
    drawdown = (prices / peak) - 1
    return drawdown

def beta_alpha(asset_returns, benchmark_returns):
    """
    Compute Beta and Alpha using OLS regression.
    R_asset = alpha + beta * R_bench + epsilon
    Returns: beta, alpha (annualized), r_squared
    """
    # Align data
    common_index = asset_returns.index.intersection(benchmark_returns.index)
    y = asset_returns.loc[common_index]
    x = benchmark_returns.loc[common_index]
    
    if len(y) < 20: # Not enough data
        return np.nan, np.nan, np.nan

    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()
    
    alpha_daily = model.params['const']
    beta = model.params.iloc[1]
    r_squared = model.rsquared
    
    alpha_annual = alpha_daily * 252
    
    return beta, alpha_annual, r_squared

def portfolio_metrics(portfolio_returns, risk_free_rate=0.0):
    """
    Compute CAGR, Annualized Volatility, Sharpe Ratio, Max Drawdown.
    Assumes daily returns.
    """
    if len(portfolio_returns) < 2:
        return {}
        
    # CAGR
    total_return = (1 + portfolio_returns).prod() - 1
    days = len(portfolio_returns)
    years = days / 252
    if years > 0:
        cagr = (1 + total_return) ** (1 / years) - 1
    else:
        cagr = 0
        
    # Volatility
    vol = portfolio_returns.std() * np.sqrt(252)
    
    # Sharpe
    mean_ret = portfolio_returns.mean()
    if vol > 0:
        sharpe = (mean_ret - risk_free_rate/252) * 252 / vol
    else:
        sharpe = 0
        
    # Max Drawdown
    cum_ret = (1 + portfolio_returns).cumprod()
    peak = cum_ret.cummax()
    dd = (cum_ret / peak) - 1
    max_dd = dd.min()
    
    return {
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd
    }
