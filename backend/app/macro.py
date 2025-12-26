from fredapi import Fred
import pandas as pd
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env from project root (quant /)
# Path: /quant /backend/app/macro.py -> /quant /.env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)


# Initialize Fred
fred_key = os.environ.get("FRED_API_KEY")
try:
    if fred_key:
        fred = Fred(api_key=fred_key)
        logger.info(f"FRED client initialized with key: {fred_key[:8]}...")
    else:
        logger.warning("FRED_API_KEY not found in environment")
        fred = None
except Exception as e:
    logger.warning(f"FRED API key not found or invalid: {e}")
    fred = None


# Cache for macro series
_macro_cache = {}

def get_series(series_id):
    """
    Fetch a series from FRED with caching.
    Returns a pandas Series with datetime index.
    """
    if series_id in _macro_cache:
        return _macro_cache[series_id]
        
    if fred is None:
        logger.error("FRED client not initialized")
        return pd.Series()
        
    try:
        series = fred.get_series(series_id)
        # Convert to datetime index if not already
        series.index = pd.to_datetime(series.index)
        
        _macro_cache[series_id] = series
        return series
    except Exception as e:
        logger.error(f"Error fetching {series_id} from FRED: {e}")
        return pd.Series()

def get_macro_summary():
    """
    Helper to get common macro indicators with history for sparklines.
    """
    import numpy as np
    
    def get_data(series_id, transform=None):
        s = get_series(series_id)
        if s.empty:
            return {"value": 0.0, "history": []}
        
        val = s.iloc[-1]
        if transform == "yoy":
            val = (s.iloc[-1] / s.iloc[-13] - 1) if len(s) >= 13 else 0
        elif transform == "qoq":
            val = (s.iloc[-1] / s.iloc[-2] - 1) if len(s) >= 2 else 0
            
        # Get last 20 points for sparkline
        history = s.iloc[-24:].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
        
        return {
            "value": float(val) if not np.isnan(val) and not np.isinf(val) else 0.0,
            "history": history
        }

    # Inflation (CPIAUCSL)
    inflation = get_data("CPIAUCSL", transform="yoy")
    
    # Unemployment (UNRATE)
    unemployment = get_data("UNRATE")
    
    # Fed Funds (FEDFUNDS)
    fed_funds = get_data("FEDFUNDS")
    
    # GDP
    gdp = get_data("GDP", transform="qoq")
    
    # Yields
    y10 = get_data("DGS10")
    y2 = get_data("DGS2")
    
    spread_val = y10["value"] - y2["value"]
    # Calculate spread history
    s10 = get_series("DGS10")
    s2 = get_series("DGS2")
    spread_hist = []
    if not s10.empty and not s2.empty:
        common = s10.index.intersection(s2.index)
        diff = s10.loc[common] - s2.loc[common]
        spread_hist = diff.iloc[-24:].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()

    return {
        "inflation": inflation,
        "unemployment": unemployment,
        "fed_funds": fed_funds,
        "gdp": gdp,
        "yield_10y": y10,
        "yield_2y": y2,
        "yield_spread": {"value": spread_val, "history": spread_hist}
    }

def get_macro_impact(ticker):
    """
    Calculate sensitivity of a ticker to macro variables.
    Returns a list of impacts (e.g. "1% rise in Inflation -> -0.5% return").
    """
    # Mock implementation for now as we don't have full historical macro aligned with price in DB
    # In a real app, we would run a regression: R_ticker = alpha + beta1 * d_CPI + beta2 * d_Rate + ...
    
    impacts = []
    
    # Simple heuristics based on sector/asset class
    # We can infer from ticker
    
    if ticker in ["TLT", "IEF", "BND"]:
        impacts.append({"factor": "Interest Rates", "change": "+1%", "impact": "-8.0%", "desc": "High duration assets suffer when rates rise."})
        impacts.append({"factor": "Inflation", "change": "+1%", "impact": "-5.0%", "desc": "Fixed income real returns fall with inflation."})
    elif ticker in ["SPY", "QQQ", "NVDA", "AAPL"]:
        impacts.append({"factor": "Interest Rates", "change": "+1%", "impact": "-3.0%", "desc": "Growth stocks valuations compress with higher discount rates."})
        impacts.append({"factor": "GDP Growth", "change": "+1%", "impact": "+2.5%", "desc": "Equities benefit from economic expansion."})
    elif ticker in ["GLD", "SLV"]:
        impacts.append({"factor": "Real Rates", "change": "+1%", "impact": "-10.0%", "desc": "Gold is non-yielding and falls when real rates rise."})
        impacts.append({"factor": "Inflation", "change": "+1%", "impact": "+5.0%", "desc": "Gold acts as an inflation hedge."})
    else:
        impacts.append({"factor": "Market Risk", "change": "+10% VIX", "impact": "-2.0%", "desc": "General market stress typically lowers returns."})
        
    return impacts
