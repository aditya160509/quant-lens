from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from app import data_loader, metrics
import logging
from pydantic import BaseModel

# Use robust data fetcher instead of yfinance directly
from app.services.robust_data_fetcher import get_price_data as rdf_get_price, get_intraday_data as rdf_get_intraday

router = APIRouter()
logger = logging.getLogger(__name__)
@router.get("/")
def get_markets_data(window: str = "1y"):
    """
    Data for Markets page: Global Indices, Rolling Vol, Rolling Corr.
    """
    # 1. US vs Global vs India
    indices = ["SPY", "QQQ", "DIA", "^NSEI", "^CNXSC", "^N225", "^KS11"]
    
    # Calculate start date based on window
    end_date = datetime.now()
    days_map = {"1m": 30, "6m": 180, "1y": 365, "5y": 365*5}
    start_date = end_date - timedelta(days=days_map.get(window.lower(), 365))
    
    global_perf = []
    try:
        df_global = data_loader.get_price_history(indices, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        
        if not df_global.empty:
            if isinstance(df_global.columns, pd.MultiIndex):
                closes = df_global.xs('Close', axis=1, level=0)
            else:
                # If single symbol or flat
                if 'Close' in df_global.columns:
                     closes = df_global['Close']
                else: 
                     closes = df_global
                
            # Normalize to 100
            rets = closes.pct_change().fillna(0)
            cum_rets = (1 + rets).cumprod() * 100
            
            dates = cum_rets.index.strftime('%Y-%m-%d').tolist()
            # If Series (single symbol), convert to DF for uniform iteration
            if isinstance(cum_rets, pd.Series):
                cum_rets = cum_rets.to_frame()
                
            for col in cum_rets.columns:
                global_perf.append({
                    "symbol": col,
                    "data": cum_rets[col].tolist()
                })
        else:
            dates = []
    except Exception as e:
        logger.error(f"Error in markets global perf: {e}")
        dates = []

    # 2. Rolling Volatility (SPY vs NIFTY)
    vol_data = {"dates": [], "spy_21": [], "spy_63": [], "nifty_21": [], "nifty_63": []}
    try:
        vol_indices = ["SPY", "^NSEI"]
        # Need enough history for 63d window
        vol_start = end_date - timedelta(days=365*2)
        df_vol = data_loader.get_price_history(vol_indices, start=vol_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        
        if not df_vol.empty:
            if isinstance(df_vol.columns, pd.MultiIndex):
                closes = df_vol.xs('Close', axis=1, level=0)
            else:
                closes = df_vol
            
            log_rets = metrics.log_return(closes)
            
            spy_vol21 = metrics.rolling_volatility(log_rets["SPY"], window=21)
            spy_vol63 = metrics.rolling_volatility(log_rets["SPY"], window=63)
            nifty_vol21 = metrics.rolling_volatility(log_rets["^NSEI"], window=21)
            nifty_vol63 = metrics.rolling_volatility(log_rets["^NSEI"], window=63)
            
            # Align
            common = spy_vol63.dropna().index.intersection(nifty_vol63.dropna().index)
            # Let's show last 1y for vol chart
            display_start = end_date - timedelta(days=365)
            common = common[common >= display_start]
            
            vol_data = {
                "dates": common.strftime('%Y-%m-%d').tolist(),
                "spy_21": spy_vol21.loc[common].tolist(),
                "spy_63": spy_vol63.loc[common].tolist(),
                "nifty_21": nifty_vol21.loc[common].tolist(),
                "nifty_63": nifty_vol63.loc[common].tolist()
            }
    except Exception as e:
        logger.error(f"Error in markets vol: {e}")

    # 3. Rolling Correlation (SPY & NIFTY)
    corr_data = {"dates": [], "correlation": []}
    try:
        # Re-use log_rets from above if available, else fetch
        # We need 60d window
        if 'log_rets' in locals():
            spy_rets = log_rets["SPY"]
            nifty_rets = log_rets["^NSEI"]
            
            rolling_corr = metrics.rolling_correlation(spy_rets, nifty_rets, window=60)
            
            common = rolling_corr.dropna().index
            display_start = end_date - timedelta(days=365*2) # Show 2y for corr
            common = common[common >= display_start]
            
            corr_data = {
                "dates": common.strftime('%Y-%m-%d').tolist(),
                "correlation": rolling_corr.loc[common].tolist()
            }
    except Exception as e:
        logger.error(f"Error in markets corr: {e}")

    return {
        "global_performance": {"dates": dates, "series": global_perf},
        "volatility": vol_data,
        "correlation": corr_data
    }

@router.get("/intraday")
def get_markets_intraday(
    ticker: str = Query("SPY"),
    interval: str = Query("5m")
):
    """
    Fetch intraday data for a single ticker for the current trading session.
    Returns bars, all indicators, and session info.
    
    - Always uses the current session (today)
    - Computes all 7 indicators: RSI, MACD, STOCH, ROC, CCI, ADX, MFI
    - Filters to regular trading hours only (9:30-16:00 ET)
    """
    from app import indicators as ind_module
    
    # Timezone and market hours
    NY_TZ = pytz.timezone("America/New_York")
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    
    # Get current time in NY
    now_ny = datetime.now(NY_TZ)
    today = now_ny.date()
    
    # Define session boundaries
    session_start = NY_TZ.localize(datetime.combine(today, MARKET_OPEN))
    
    # Determine if market is currently open
    current_time = now_ny.time()
    is_market_open = (
        now_ny.weekday() < 5 and  # Monday-Friday
        MARKET_OPEN <= current_time <= MARKET_CLOSE
    )
    
    if is_market_open:
        session_end = now_ny
        session_status = "open"
    else:
        session_end = NY_TZ.localize(datetime.combine(today, MARKET_CLOSE))
        session_status = "closed"
    
    try:
        # Fetch intraday data using robust fetcher (handles rate limiting)
        # This ensures we have data even when market is closed
        df = rdf_get_intraday(ticker, interval=interval, period="5d")
        
        if df.empty:
            return {
                "ticker": ticker,
                "interval": interval,
                "session": {
                    "status": session_status,
                    "timezone": "America/New_York",
                    "session_start": session_start.isoformat(),
                    "session_end": session_end.isoformat()
                },
                "bars": [],
                "indicators": {
                    "rsi_14": [], "macd_12_26_9": [], "stoch": [],
                    "roc": [], "cci": [], "adx": [], "mfi": []
                },
                "meta": {"range": "current_session", "source": "yfinance"}
            }
        
        # Ensure timezone-aware
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        
        # Filter to regular trading hours only
        df = df.copy()
        df['time_of_day'] = df.index.time
        df = df[
            (df['time_of_day'] >= MARKET_OPEN) & 
            (df['time_of_day'] <= MARKET_CLOSE)
        ]
        df = df.drop(columns=['time_of_day'])
        
        # Drop rows with null/zero values
        df = df.dropna(subset=['Close'])
        df = df[df['Volume'] > 0]
        
        # Sort by timestamp
        df = df.sort_index()
        
        # If market is closed, filter to the most recent trading day only
        # This gives a full day's worth of candles
        if session_status == "closed" and not df.empty:
            # Get unique dates
            df['date'] = df.index.date
            most_recent_date = df['date'].max()
            df = df[df['date'] == most_recent_date]
            df = df.drop(columns=['date'])
            # Update session info for the actual session shown
            session_start = NY_TZ.localize(datetime.combine(most_recent_date, MARKET_OPEN))
            session_end = NY_TZ.localize(datetime.combine(most_recent_date, MARKET_CLOSE))
        
        if df.empty:
            return {
                "ticker": ticker,
                "interval": interval,
                "session": {
                    "status": session_status,
                    "timezone": "America/New_York",
                    "session_start": session_start.isoformat(),
                    "session_end": session_end.isoformat()
                },
                "bars": [],
                "indicators": {
                    "rsi_14": [], "macd_12_26_9": [], "stoch": [],
                    "roc": [], "cci": [], "adx": [], "mfi": []
                },
                "meta": {"range": "current_session", "source": "yfinance"}
            }
        
        # Compute all indicators using the shared indicator module
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # RSI(14)
        rsi = ind_module.calculate_rsi(close, window=14)
        
        # MACD(12, 26, 9)
        macd_line, signal_line, hist = ind_module.calculate_macd(close, fast=12, slow=26, signal=9)
        
        # Stochastic
        stoch_k, stoch_d = ind_module.calculate_stoch(high, low, close, k_window=14, d_window=3, slow_k=3)
        
        # ROC
        roc = ind_module.calculate_roc(close, window=10)
        
        # CCI
        cci = ind_module.calculate_cci(high, low, close, window=20)
        
        # ADX
        adx = ind_module.calculate_adx(high, low, close, window=14)
        
        # MFI
        mfi = ind_module.calculate_mfi(high, low, close, volume, window=14)
        
        # Helper to format series
        def format_series(series, key="value"):
            result = []
            if series is not None:
                for ts, val in series.items():
                    if pd.notna(val) and not np.isinf(val):
                        result.append({"ts": ts.isoformat(), key: round(float(val), 4)})
            return result
        
        # Format bars
        bars = []
        for ts, row in df.iterrows():
            bars.append({
                "ts": ts.isoformat(),
                "open": round(float(row['Open']), 4) if pd.notna(row['Open']) else 0,
                "high": round(float(row['High']), 4) if pd.notna(row['High']) else 0,
                "low": round(float(row['Low']), 4) if pd.notna(row['Low']) else 0,
                "close": round(float(row['Close']), 4) if pd.notna(row['Close']) else 0,
                "volume": int(row['Volume']) if pd.notna(row['Volume']) else 0
            })
        
        # Format RSI
        rsi_data = format_series(rsi)
        
        # Format MACD
        macd_data = []
        for ts in macd_line.index:
            m = macd_line.get(ts)
            s = signal_line.get(ts)
            h = hist.get(ts)
            if pd.notna(m) and pd.notna(s) and pd.notna(h):
                if not (np.isinf(m) or np.isinf(s) or np.isinf(h)):
                    macd_data.append({
                        "ts": ts.isoformat(),
                        "macd": round(float(m), 4),
                        "signal": round(float(s), 4),
                        "hist": round(float(h), 4)
                    })
        
        # Format Stochastic
        stoch_data = []
        for ts in stoch_k.index:
            k = stoch_k.get(ts)
            d = stoch_d.get(ts)
            if pd.notna(k) and pd.notna(d):
                if not (np.isinf(k) or np.isinf(d)):
                    stoch_data.append({
                        "ts": ts.isoformat(),
                        "k": round(float(k), 4),
                        "d": round(float(d), 4)
                    })
        
        # Format other indicators
        roc_data = format_series(roc)
        cci_data = format_series(cci)
        adx_data = format_series(adx)
        mfi_data = format_series(mfi)
        
        return {
            "ticker": ticker,
            "interval": interval,
            "session": {
                "status": session_status,
                "timezone": "America/New_York",
                "session_start": session_start.isoformat(),
                "session_end": session_end.isoformat()
            },
            "bars": bars,
            "indicators": {
                "rsi_14": rsi_data,
                "macd_12_26_9": macd_data,
                "stoch": stoch_data,
                "roc": roc_data,
                "cci": cci_data,
                "adx": adx_data,
                "mfi": mfi_data
            },
            "meta": {
                "range": "current_session",
                "source": "yfinance"
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching intraday for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "ticker": ticker,
            "interval": interval,
            "session": {
                "status": "closed",
                "timezone": "America/New_York",
                "session_start": session_start.isoformat(),
                "session_end": session_end.isoformat()
            },
            "bars": [],
            "indicators": {
                "rsi_14": [], "macd_12_26_9": [], "stoch": [],
                "roc": [], "cci": [], "adx": [], "mfi": []
            },
            "meta": {"range": "current_session", "source": "yfinance"},
            "error": str(e)
        }

class SectorRotationRequest(BaseModel):
    period: str = "3mo"

@router.post("/sector_rotation")
def get_sector_rotation(req: SectorRotationRequest):
    # Simple sector rotation analysis
    sectors = ["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE"]
    
    # Fetch all sectors
    sector_perf = {}
    for s in sectors:
        sdf = data_loader.fetch_ticker_data(s, period="1y")
        if not sdf.empty:
            # Calculate momentum (e.g., 3 month return)
            ret = (sdf['Close'].iloc[-1] / sdf['Close'].iloc[-63] - 1) if len(sdf) > 63 else 0
            sector_perf[s] = ret
            
    # Sort by performance
    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "sectors": [s[0] for s in sorted_sectors],
        "performance": [s[1] for s in sorted_sectors]
    }
