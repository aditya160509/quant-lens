import yfinance as yf
import pandas as pd
import numpy as np
import logging
import pytz
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

# In-memory cache: {(tuple(symbols), start, end, interval): DataFrame}
_price_cache = {}

def get_session_info():
    """
    Returns current market session status.
    Ref: US Equities (9:30 - 16:00 ET, Mon-Fri).
    """
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    
    # Check weekend
    is_weekend = now.weekday() >= 5
    
    # Check time
    current_time = now.time()
    market_open_time = time(9, 30)
    market_close_time = time(16, 0)
    
    is_market_hours = market_open_time <= current_time <= market_close_time
    
    # Simple market_open logic
    market_open = not is_weekend and is_market_hours
    
    # Determine session date (today if open, or last business day if closed/weekend)
    # This is a simplification; for a real app we'd want a holiday calendar.
    session_date = now.date()
    if is_weekend:
        # If Saturday (5), go back 1 day to Friday. If Sunday (6), go back 2 days.
        days_back = 1 if now.weekday() == 5 else 2
        session_date = (now - timedelta(days=days_back)).date()
    elif current_time < market_open_time:
        # Before open on a weekday, session is yesterday (or Friday if Mon)
        if now.weekday() == 0:
             session_date = (now - timedelta(days=3)).date()
        else:
             session_date = (now - timedelta(days=1)).date()
            
    return {
        "market_open": market_open,
        "session_date": session_date.strftime("%Y-%m-%d"),
        "session_open": "09:30",
        "session_close": "16:00",
        "timezone": "America/New_York",
        "timestamp": now.isoformat()
    }

def get_price_history(symbols, start, end, interval="1d"):
    """
    Fetch price history for one or more symbols from yfinance.
    Returns a DataFrame with MultiIndex columns if multiple symbols,
    or flattened columns if single symbol.
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    
    # Check cache
    cache_key = (tuple(sorted(symbols)), start, end, interval)
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    try:
        # yfinance download
        df = yf.download(
            symbols, 
            start=start, 
            end=end, 
            interval=interval, 
            auto_adjust=False, 
            progress=False,
            threads=False
        )
        
        if df.empty:
            return pd.DataFrame()

        # Handle YF's column structure for single vs multiple symbols and new vs old versions
        # Flatten simple cases
        if isinstance(df.columns, pd.MultiIndex):
            # If 'Close' is in level 0, we are good.
            # Drop rows where ALL symbols have NaNs for Close
            if 'Close' in df.columns.get_level_values(0):
               valid_indices = df.xs('Close', axis=1, level=0).dropna(how='all').index
               df = df.loc[valid_indices]
            df = df.ffill()
        else:
            df = df.dropna(how='all')
            df = df.ffill()

        _price_cache[cache_key] = df
        return df

    except Exception as e:
        logger.error(f"Error fetching data for {symbols}: {e}")
        return pd.DataFrame()

def get_universe(region="us"):
    """
    Return a list of symbols for the specified region.
    """
    if region == "us":
        return [
            "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM", "BAC", "WFC", "C",
            "XOM", "CVX", "COP", "UNH", "JNJ", "PFE", "ABBV", "PG", "KO", "PEP",
            "HD", "COST", "WMT", "MCD", "DIS", "NFLX", "AMD", "INTC", "IBM", "ORCL",
            "ADBE", "CRM", "QCOM", "AVGO", "V", "MA", "T", "TMUS", "UPS", "BA"
        ]
    elif region == "india":
        return [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "KOTAKBANK.NS", "SBIN.NS", "AXISBANK.NS", "LT.NS", "HINDUNILVR.NS",
            "ITC.NS", "BHARTIARTL.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
            "BAJFINANCE.NS", "BAJAJFINSV.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
            "WIPRO.NS", "TECHM.NS", "ADANIENT.NS", "ADANIPORTS.NS", "POWERGRID.NS",
            "ONGC.NS", "COALINDIA.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "HCLTECH.NS",
            "CIPLA.NS", "JSWSTEEL.NS", "DIVISLAB.NS", "HEROMOTOCO.NS", "DRREDDY.NS"
        ]
    else:
        return []

def fetch_ticker_data(ticker, period="1y", interval="1d"):
    """
    Legacy wrapper for compatibility, but using new logic internally if possible.
    """
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        return df
    except Exception as e:
        logger.error(f"Error fetching ticker {ticker}: {e}")
        return pd.DataFrame()

# Intraday Cache: {ticker: {'timestamp': datetime, 'data': [{'t':..., 'o':...}]}}
_intraday_cache = {}

def get_intraday_bars(ticker, interval="5m", max_age_seconds=60):
    """
    Fetch intraday bars for a single ticker with caching.
    Returns a list of dictionaries associated with the current or last session.
    """
    now = datetime.now()
    
    # Check cache
    if ticker in _intraday_cache:
        entry = _intraday_cache[ticker]
        age = (now - entry['timestamp']).total_seconds()
        if age < max_age_seconds and entry['interval'] == interval:
            return entry['data']
            
    try:
        # Check session to decide period
        session = get_session_info()
        period = "1d" if session['market_open'] else "5d" # Fetch 5d if closed to ensure we get ANY recent session
        
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        
        if df.empty:
            return []
            
        # Format data structure
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df_flat = df.copy()
                df_flat.columns = df_flat.columns.droplevel(1)
            except:
                pass
        else:
            df_flat = df
        
        # Determine the single session to return
        # If we fetched 5d, we only want the LAST date's data
        df_flat['DateOnly'] = df_flat.index.date
        last_date = df_flat['DateOnly'].iloc[-1]
        session_df = df_flat[df_flat['DateOnly'] == last_date].copy()
            
        bars = []
        for ts, row in session_df.iterrows():
            if pd.isna(row['Close']):
                continue
                
            bar = {
                "ts": ts.isoformat(), # "ts" per spec, not "t"
                "open": float(row['Open']) if not pd.isna(row['Open']) else 0,
                "high": float(row['High']) if not pd.isna(row['High']) else 0,
                "low": float(row['Low']) if not pd.isna(row['Low']) else 0,
                "close": float(row['Close']) if not pd.isna(row['Close']) else 0,
                "volume": int(row['Volume']) if not pd.isna(row['Volume']) else 0
            }
            bars.append(bar)
            
        # Update cache
        _intraday_cache[ticker] = {
            'timestamp': now,
            'interval': interval,
            'data': bars
        }
        
        return bars
        
    except Exception as e:
        logger.error(f"Error fetching intraday for {ticker}: {e}")
        return []
