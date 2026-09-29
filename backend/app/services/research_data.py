"""
Research Data Service
Shared data loading functions for all research modules.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Literal
import logging

from app.services.research_cache import research_cache
from app import data_loader, factor_data, macro_data

logger = logging.getLogger(__name__)

# ===== Factor Mappings =====
# Maps user-facing factor names to (source, column) tuples
FACTOR_MAP = {
    "MKT": ("ff3", "Mkt-RF"),
    "SMB": ("ff3", "SMB"),
    "HML": ("ff3", "HML"),
    "VALUE": ("ff3", "HML"),  # Alias for HML
    "MOMENTUM": ("momentum", "Mom"),
    "MOM": ("momentum", "Mom"),  # Alias
    "RF": ("ff3", "RF"),
    # Computed factors (no direct source)
    "QUALITY": None,
    "VOL": None,
    "VOLATILITY": None,
}

# ===== Macro Mappings =====
# Maps user-facing macro names to FRED series IDs
MACRO_MAP = {
    "RATES": "DGS10",           # 10-Year Treasury Yield
    "USD": "DTWEXBGS",          # Trade Weighted USD Index
    "OIL": "DCOILWTICO",        # WTI Crude Oil Price
    "INFLATION": "CPIAUCSL",    # Consumer Price Index
    "VIX": "VIXCLS",            # VIX Index
    "YC_SLOPE": "T10Y2Y",       # Yield Curve Slope (10Y-2Y)
    "CREDIT": "BAMLH0A0HYM2",   # High Yield Credit Spread
    "FEDFUNDS": "FEDFUNDS",     # Federal Funds Rate
    "UNRATE": "UNRATE",         # Unemployment Rate
    # Computed series
    "BREADTH": None,            # Computed from universe
}

# Sign for regime detection (positive = risk off)
MACRO_SIGN = {
    "VIX": 1,
    "CREDIT": 1,
    "RATES": 1,
    "YC_SLOPE": -1,   # Higher slope = risk on
    "BREADTH": -1,    # Higher breadth = risk on
    "USD": 1,
    "OIL": 0,         # Neutral / complex
    "INFLATION": 1,
}


def get_universe() -> List[str]:
    """
    Get the full dynamic universe of tickers.
    
    Returns:
        List of ticker symbols from US and India universes.
    """
    us = data_loader.get_universe("us")
    india = data_loader.get_universe("india")
    
    # Add common ETFs and indices
    etfs = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "USO", "XLF", "XLK", "XLE", "XLV"]
    
    # Combine and deduplicate
    all_tickers = list(set(us + india + etfs))
    all_tickers.sort()
    
    return all_tickers


def get_prices_daily(ticker: str, lookback_days: int) -> pd.DataFrame:
    """
    Get daily OHLCV data for a ticker.
    
    Args:
        ticker: Stock symbol
        lookback_days: Number of days to fetch
        
    Returns:
        DataFrame with columns: date (index), open, high, low, close, volume
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 30)  # Buffer for weekends/holidays
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Check cache
    cached, hit = research_cache.get_prices(ticker, "1d", start_str, end_str)
    if hit and cached is not None:
        return cached
    
    try:
        df = data_loader.get_price_history(
            [ticker],
            start=start_str,
            end=end_str,
            interval="1d"
        )
        
        if df.empty:
            logger.warning(f"No data for ticker {ticker}")
            return pd.DataFrame()
        
        # Handle MultiIndex columns from yfinance
        if isinstance(df.columns, pd.MultiIndex):
            # Extract columns for this ticker
            result = pd.DataFrame(index=df.index)
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if (col, ticker) in df.columns:
                    result[col.lower()] = df[(col, ticker)]
                elif col in df.columns.get_level_values(0):
                    result[col.lower()] = df.xs(col, axis=1, level=0).iloc[:, 0]
        else:
            result = df.copy()
            result.columns = [c.lower() for c in result.columns]
        
        # Ensure we have required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in result.columns:
                result[col] = np.nan
        
        result = result[required].dropna(subset=['close'])
        
        # Cache the result
        research_cache.set_prices(ticker, "1d", start_str, end_str, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
        return pd.DataFrame()


def get_prices_multi(tickers: List[str], lookback_days: int) -> Dict[str, pd.DataFrame]:
    """
    Get daily prices for multiple tickers.
    
    Args:
        tickers: List of ticker symbols
        lookback_days: Number of days to fetch
        
    Returns:
        Dict mapping ticker to DataFrame
    """
    result = {}
    for ticker in tickers:
        df = get_prices_daily(ticker, lookback_days)
        if not df.empty:
            result[ticker] = df
    return result


from app.services.parquet_cache import pq_cache

def get_research_series(symbol: str, lookback_days: int) -> pd.DataFrame:
    """
    Unified series fetcher for Research Engine.
    Detects symbol type and routes to appropriate source.
    """
    upper_sym = symbol.upper()
    
    # 1. Check if it's a known Factor
    if upper_sym in FACTOR_MAP:
        df = get_factor_returns([upper_sym], lookback_days)
        if not df.empty:
            # Stats functions usually expect 'close' column
            df = df.rename(columns={upper_sym: 'close'})
            return df
            
    # 2. Check if it's a known Macro indicator
    if upper_sym in MACRO_MAP:
        df = get_macro_series([upper_sym], lookback_days)
        if not df.empty:
            df = df.rename(columns={upper_sym: 'close'})
            return df

    # 3. Default to Price Data (Equity/Index)
    return get_prices_daily(symbol, lookback_days)

def get_factor_returns(factors: List[str], lookback_days: int) -> pd.DataFrame:
    """
    Get factor return series with Parquet caching.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 30)
    
    result = pd.DataFrame()
    
    for factor in factors:
        factor_upper = factor.upper()
        
        # Try Parquet Cache First
        cache_key = f"factor_{factor_upper}"
        cached = pq_cache.get(cache_key, max_age_hours=24)
        if cached is not None:
            mask = cached.index >= start_date
            result[factor_upper] = cached.loc[mask].iloc[:, 0]
            continue
            
        if factor_upper not in FACTOR_MAP:
            continue
        
        mapping = FACTOR_MAP[factor_upper]
        if mapping is None: continue
        
        source, column = mapping
        
        try:
            df = factor_data.load_factors(source)
            if df.empty: continue
            
            col_match = next((c for c in df.columns if c.strip().replace(" ", "") == column.replace(" ", "")), None)
            if col_match is None: continue
            
            # Save to Parquet for next time
            pq_cache.set(cache_key, df[[col_match]])
            
            mask = df.index >= start_date
            result[factor_upper] = df.loc[mask, col_match]
            
        except Exception as e:
            logger.error(f"Error loading factor {factor}: {e}")
    
    if not result.empty:
        result = result.dropna(how='all')
        result.index = pd.to_datetime(result.index.date)
    
    return result

def get_macro_series(series_names: List[str], lookback_days: int) -> pd.DataFrame:
    """
    Get macro indicator series with Parquet caching.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 60)
    
    result = pd.DataFrame()
    
    for name in series_names:
        name_upper = name.upper()
        
        # Try Parquet Cache First
        cache_key = f"macro_{name_upper}"
        cached = pq_cache.get(cache_key, max_age_hours=12)
        if cached is not None:
            mask = cached.index >= start_date
            result[name_upper] = cached.loc[mask].iloc[:, 0]
            continue
            
        if name_upper not in MACRO_MAP: continue
        fred_id = MACRO_MAP[name_upper]
        if fred_id is None: continue
        
        try:
            series = macro_data.fetch_series(fred_id, observation_start=start_date.strftime("%Y-%m-%d"))
            if series.empty: continue
            
            df = pd.DataFrame({name_upper: pd.to_numeric(series, errors='coerce')})
            # Save to Parquet
            pq_cache.set(cache_key, df)
            
            result[name_upper] = df[name_upper]
            
        except Exception as e:
            logger.error(f"Error loading macro series {name}: {e}")
    
    if not result.empty:
        # Resample to daily with forward fill
        result = result.resample('D').ffill()
        result = result.dropna(how='all')
    
    return result

def align_frames(
    frames: List[pd.DataFrame],
    mode: Literal["intersection", "union"] = "intersection"
) -> List[pd.DataFrame]:
    """
    Align multiple DataFrames on their date indices.
    
    Args:
        frames: List of DataFrames with DatetimeIndex
        mode: 
            - "intersection": Keep only dates present in ALL frames
            - "union": Keep all dates, forward-fill for macro data only
            
    Returns:
        List of aligned DataFrames with common index
    """
    if not frames:
        return []
    
    if len(frames) == 1:
        return frames
    
    # Get all indices
    indices = [f.index for f in frames]
    
    if mode == "intersection":
        # Find common dates
        common_idx = indices[0]
        for idx in indices[1:]:
            common_idx = common_idx.intersection(idx)
        
        # Reindex all frames
        aligned = [f.loc[f.index.intersection(common_idx)] for f in frames]
        
    else:  # union
        # Union of all dates
        union_idx = indices[0]
        for idx in indices[1:]:
            union_idx = union_idx.union(idx)
        union_idx = union_idx.sort_values()
        
        # Reindex with forward fill
        aligned = []
        for f in frames:
            reindexed = f.reindex(union_idx)
            # Only forward fill, don't backfill
            reindexed = reindexed.ffill()
            aligned.append(reindexed)
    
    return aligned


def validate_tickers(tickers: List[str]) -> Dict[str, bool]:
    """
    Validate which tickers are in the universe.
    
    Args:
        tickers: List of ticker symbols to validate
        
    Returns:
        Dict mapping ticker to validity (True if valid)
    """
    universe = set(get_universe())
    return {t: t in universe for t in tickers}


def get_available_factors() -> List[str]:
    """Get list of available factor names."""
    return [k for k, v in FACTOR_MAP.items() if v is not None]


def get_available_macro() -> List[str]:
    """Get list of available macro series names."""
    return [k for k, v in MACRO_MAP.items() if v is not None]


def get_macro_sign(series_name: str) -> int:
    """Get the sign for a macro series (for regime detection)."""
    return MACRO_SIGN.get(series_name.upper(), 0)
