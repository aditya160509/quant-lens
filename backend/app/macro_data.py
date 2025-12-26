from fredapi import Fred
import pandas as pd
import os
import logging
from ratelimit import limits, sleep_and_retry
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env from project root (quant /)
# Path: /quant /backend/app/macro_data.py -> /quant /.env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)


# Debug: log loaded keys
fred_key = os.environ.get('FRED_API_KEY')
if fred_key:
    logger.info(f"FRED API key loaded: {fred_key[:8]}...")
else:
    logger.warning("FRED_API_KEY not found in environment")

# Initialize Fred with API key from environment
try:
    if fred_key:
        fred = Fred(api_key=fred_key)
        logger.info("FRED client initialized successfully")
    else:
        logger.error("FRED API key not found or invalid: " + str(os.environ.get('FRED_API_KEY', 'NOT SET')))
        fred = None
except Exception as e:
    logger.error(f"Failed to initialize Fred API: {e}")
    fred = None


SERIES_MAPPING = {
    'CPI': 'CPIAUCSL',
    'UNRATE': 'UNRATE',
    'FEDFUNDS': 'FEDFUNDS',
    'GDP': 'GDP',
    'DGS10': 'DGS10',
    'DGS2': 'DGS2',
    'T10Y2Y': 'T10Y2Y'
}

@sleep_and_retry
@limits(calls=120, period=60)
def fetch_series(series_id: str, observation_start: str = None) -> pd.Series:
    """
    Fetches a specific series from FRED.
    """
    if not fred:
        logger.error("Fred API not initialized")
        return pd.Series()
        
    try:
        data = fred.get_series(series_id, observation_start=observation_start)
        return data
    except Exception as e:
        logger.error(f"Error fetching series {series_id}: {e}")
        return pd.Series()

def get_macro_summary() -> dict:
    """
    Fetches latest values for key macro indicators.
    """
    summary = {}
    for name, series_id in SERIES_MAPPING.items():
        try:
            series = fetch_series(series_id)
            if not series.empty:
                summary[name] = {
                    'value': series.iloc[-1],
                    'date': series.index[-1].strftime('%Y-%m-%d'),
                    'change_1y': (series.iloc[-1] - series.iloc[-13]) if len(series) > 12 and name == 'CPI' else None # Example logic
                }
        except Exception:
            continue
    return summary

def get_yield_curve() -> pd.DataFrame:
    """
    Fetches 10Y and 2Y yields and computes spread.
    """
    d10 = fetch_series(SERIES_MAPPING['DGS10'])
    d2 = fetch_series(SERIES_MAPPING['DGS2'])
    
    df = pd.DataFrame({'10Y': d10, '2Y': d2})
    df.dropna(inplace=True)
    df['Spread'] = df['10Y'] - df['2Y']
    return df
