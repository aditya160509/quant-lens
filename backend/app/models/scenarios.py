import pandas as pd
import numpy as np
import logging
from app import data_loader

logger = logging.getLogger(__name__)

SCENARIOS = {
    "2008_Financial_Crisis": ("2007-10-01", "2009-03-09"),
    "2020_Covid_Crash": ("2020-02-19", "2020-03-23"),
    "2022_Inflation_Shock": ("2022-01-03", "2022-10-14"),
    "2000_Dotcom_Bust": ("2000-03-10", "2002-10-09"),
    "2013_Taper_Tantrum": ("2013-05-22", "2013-06-24")
}

def get_scenario_data(tickers: list[str], scenario_name: str) -> pd.DataFrame:
    """
    Fetches returns for the specified scenario period.
    """
    if scenario_name not in SCENARIOS:
        return pd.DataFrame()
        
    start, end = SCENARIOS[scenario_name]
    
    # We fetch a bit more context if needed, but here we just want the period
    # yfinance fetch expects period or start/end
    # We'll use download with start/end
    try:
        # Use data_loader for caching
        df = data_loader.get_price_history(tickers, start=start, end=end)
        
        if df.empty:
            return pd.DataFrame()
            
        # If MultiIndex, extract Close
        if isinstance(df.columns, pd.MultiIndex):
            # Check if Close exists
            if 'Close' in df.columns.get_level_values(0):
                df = df.xs('Close', axis=1, level=0)
            else:
                # Fallback or maybe it's already flattened?
                # If flattened, columns are tickers
                pass
        
        # Calculate returns
        returns = df.pct_change().dropna()
        return returns
    except Exception as e:
        logger.error(f"Error fetching scenario data: {e}")
        return pd.DataFrame()

def simulate_portfolio_scenario(weights: dict[str, float], scenario_name: str) -> dict:
    """
    Simulates portfolio performance in a historical scenario.
    
    Args:
        weights (dict): Asset weights (e.g., {"SPY": 0.6, "TLT": 0.4}).
        scenario_name (str): Key from SCENARIOS.
        
    Returns:
        dict: Simulation results.
    """
    tickers = list(weights.keys())
    returns_df = get_scenario_data(tickers, scenario_name)
    
    if returns_df.empty:
        return {"error": "No data for scenario"}
        
    # Align weights
    w_vector = np.array([weights.get(t, 0) for t in returns_df.columns])
    
    # Portfolio returns
    port_returns = returns_df.dot(w_vector)
    
    # Cumulative return
    cum_returns = (1 + port_returns).cumprod() - 1
    
    total_return = cum_returns.iloc[-1]
    max_drawdown = (cum_returns - cum_returns.cummax()).min()
    volatility = port_returns.std() * np.sqrt(252)
    
    return {
        "scenario": scenario_name,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "dates": cum_returns.index.strftime('%Y-%m-%d').tolist(),
        "cumulative_returns": cum_returns.tolist()
    }
