import pandas as pd
import numpy as np
from arch import arch_model
import logging

logger = logging.getLogger(__name__)

def calculate_realized_vol(returns: pd.Series, window: int = 21) -> pd.Series:
    """
    Calculates annualized realized volatility (rolling std dev).
    """
    return returns.rolling(window=window).std() * np.sqrt(252)

def calculate_ewma_vol(returns: pd.Series, span: int = 21) -> pd.Series:
    """
    Calculates annualized EWMA volatility.
    """
    return returns.ewm(span=span).std() * np.sqrt(252)

def fit_garch(returns: pd.Series, forecast_horizon: int = 21) -> dict:
    """
    Fits a GARCH(1,1) model and forecasts volatility.
    
    Args:
        returns (pd.Series): Daily returns (percentage or decimal).
                             GARCH models often work better with returns * 100.
        forecast_horizon (int): Days to forecast.
        
    Returns:
        dict: Model summary and forecast.
    """
    try:
        # Scale returns to percentage for numerical stability
        scaled_returns = returns * 100.0
        
        # GARCH(1,1)
        am = arch_model(scaled_returns, vol='Garch', p=1, o=0, q=1, dist='Normal')
        res = am.fit(disp='off')
        
        # Forecast
        forecasts = res.forecast(horizon=forecast_horizon)
        
        # Extract conditional volatility (annualized)
        # res.conditional_volatility is daily % volatility
        cond_vol = res.conditional_volatility * np.sqrt(252) / 100.0
        
        # Extract forecast
        # forecasts.variance is daily variance
        var_forecast = forecasts.variance.iloc[-1]
        vol_forecast = np.sqrt(var_forecast) * np.sqrt(252) / 100.0
        
        return {
            "conditional_volatility": cond_vol, # Series
            "forecast": vol_forecast.tolist(), # List of floats
            "summary": str(res.summary()),
            "params": res.params.to_dict()
        }
    except Exception as e:
        logger.error(f"GARCH fit failed: {e}")
        return {}
