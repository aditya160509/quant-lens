from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from app import data_loader, indicators
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/detail")
def get_security_detail(symbol: str, period: str = "1y", interval: str = "1d"):
    try:
        # Determine if we are in intraday mode
        is_intraday = interval in ["1m", "5m", "15m", "30m", "60m", "90m", "1h"]
        
        # Fetch Price Data
        # For intraday, we fetch more data to ensure stable indicators if needed, 
        # but for the "price" chart we might wants just the session? 
        # The prompt says: "When market_open is true... return intraday bars for the current session."
        # But this is the DETAIL endpoint which powers the main chart. 
        # If the user switches to Intraday tab, they expect the session.
        
        # However, to keep it simple and consistent with markets:
        if is_intraday:
            # We want the current session (or last session if closed)
            # We can use get_intraday_bars logic but we need a DataFrame here for logic reuse (SMA etc)
            # So we rely on data_loader.get_price_history but we need to ensure we filter for the session if strict.
            
            # Actually, let's use data_loader.fetch_ticker_data (which wraps get_price_history effectively)
            fetch_period = "5d" if period in ["1y", "2y", "5y", "max"] else period
            df = data_loader.fetch_ticker_data(symbol, period=fetch_period, interval=interval)
            
            # Filter for last available session like we do in get_intraday_bars?
            # Or just return what we have? The prompt says "honest empty state" if no data.
            # "Intraday tab... should fetch and display intraday bars for that single ticker."
            # "When market_open is false... return intraday bars for the most recent completed session."
            
            if not df.empty:
                # Filter to last date
                last_date = df.index.date[-1]
                df = df[df.index.date == last_date]
                
        else:
            df = data_loader.fetch_ticker_data(symbol, period=period, interval=interval)
            
        if df.empty:
             # Should return empty structure rather than 404 to avoid crashing frontend
             # But prompt says "honest empty state".
             return {
                "ticker": symbol,
                "price": {"dates": [], "close": []},
                "indicators": {},
                "risk_profile": {},
                "market_status": "No Data" 
             }
            
        # Compute Indicators (using the df we have)
        # Note: If df is only 1 session (78 bars), indicators might be unstable at start.
        inds = indicators.compute_indicators(symbol, None, None, df=df)
        
        # SMA for Price Chart (Only meaningful if enough data)
        # For intraday, SMAs might not make sense unless we carry over state. 
        # We'll calculate them anyway.
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        
        # Risk Profile - ALWAYS use Daily Data (1Y)
        risk_metrics = {
             "beta": 0,
             "alpha_annual": 0, 
             "volatility": 0, 
             "max_drawdown": 0, 
             "r_squared": 0, 
             "benchmark": "SPY"
        }
        try:
            daily_df = data_loader.fetch_ticker_data(symbol, period="1y", interval="1d")
            benchmark = "^NSEI" if ".NS" in symbol else "SPY"
            bench_df = data_loader.fetch_ticker_data(benchmark, period="1y", interval="1d")
            
            if not daily_df.empty and not bench_df.empty:
                # Align
                asset_ret = daily_df['Close'].pct_change().dropna()
                bench_ret = bench_df['Close'].pct_change().dropna()
                
                common_dates = asset_ret.index.intersection(bench_ret.index)
                asset_ret = asset_ret.loc[common_dates]
                bench_ret = bench_ret.loc[common_dates]
                
                if len(asset_ret) > 20: 
                    from app import metrics
                    beta, alpha, r2 = metrics.beta_alpha(asset_ret, bench_ret)
                    vol = metrics.rolling_volatility(metrics.log_return(daily_df['Close']), window=252, annualize=True).iloc[-1]
                    dd = metrics.max_drawdown(daily_df['Close']).min()
                    
                    risk_metrics = {
                        "beta": beta if not np.isnan(beta) else 0,
                        "alpha_annual": alpha if not np.isnan(alpha) else 0,
                        "volatility": vol if not np.isnan(vol) else 0,
                        "max_drawdown": dd if not np.isnan(dd) else 0,
                        "r_squared": r2 if not np.isnan(r2) else 0,
                        "benchmark": benchmark
                    }
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")

        # Sanitize helpers
        def sanitize(series):
            if isinstance(series, pd.Series):
                return series.replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
            return []

        return {
            "ticker": symbol,
            "price": {
                "dates": df.index.strftime('%Y-%m-%d %H:%M:%S' if is_intraday else '%Y-%m-%d').tolist(),
                "open": sanitize(df['Open']),
                "high": sanitize(df['High']),
                "low": sanitize(df['Low']),
                "close": sanitize(df['Close']),
                "volume": sanitize(df['Volume']),
                "sma_50": sanitize(df['SMA_50']),
                "sma_200": sanitize(df['SMA_200'])
            },
            "indicators": {
                "rsi": sanitize(inds.get('rsi', pd.Series())),
                "macd": {
                    "macd": sanitize(inds.get('macd', {}).get('macd', pd.Series())),
                    "signal": sanitize(inds.get('macd', {}).get('signal', pd.Series())),
                    "hist": sanitize(inds.get('macd', {}).get('hist', pd.Series()))
                },
                "stoch": {
                    "k": sanitize(inds.get('stoch', {}).get('k', pd.Series())),
                    "d": sanitize(inds.get('stoch', {}).get('d', pd.Series()))
                },
                "roc": sanitize(inds.get('roc', pd.Series())),
                "cci": sanitize(inds.get('cci', pd.Series())),
                "adx": sanitize(inds.get('adx', pd.Series())),
                "mfi": sanitize(inds.get('mfi', pd.Series()))
            },
            "risk_profile": risk_metrics
        }
    except Exception as e:
        logger.error(f"Error in security detail: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{ticker}/indicators")
def get_security_indicators(ticker: str, period: str = "1y", interval: str = "1d"):
    """
    Fetch indicators for a security.
    Computes indicators on the same data series as the price chart.
    """
    try:
        # Determine if we are in intraday mode
        is_intraday = interval in ["1m", "5m", "15m", "30m", "60m", "90m", "1h"]
        
        # Fetch Price Data (Intraday or Daily)
        if is_intraday:
            # We fetch 5d to ensure we have enough context for indicators
            df_full = data_loader.fetch_ticker_data(ticker, period="5d", interval=interval)
            
            # But for the response, we might want to return only the current session's indicators
            # matching the price chart.
            # However, computing on just the session (78 bars) is okay for RSI(14).
            # Let's compute on full fetched data, then slice if needed?
            # For simplicity, we'll return what we fetch, but filtered to last session to match UI expectations if strict.
            # But indicators API usually returns a series. 
            
            if not df_full.empty:
                last_date = df_full.index.date[-1]
                df = df_full[df_full.index.date == last_date]
            else:
                df = df_full
        else:
            df = data_loader.fetch_ticker_data(ticker, period=period, interval=interval)
            
        if df.empty:
            return {
                "ticker": ticker,
                "timeframe": f"{period}_{interval}",
                "indicators": {}
            }
            
        # Compute Indicators
        inds = indicators.compute_indicators(ticker, None, None, df=df)
        
        # Helper to structure response
        def format_indicator(name, data, refs=[]):
            # Check sufficiency
            # 14 is a common period. If len < 14, insufficient.
            is_insufficient = len(df) < 14
            
            series_data = []
            if not is_insufficient:
                 # Flatten logic
                if isinstance(data, dict):
                    # For MACD/Stoch, we combine them into a list of points or keep specific structure?
                    # The prompt example: "series": [{"ts": ..., "macd": ...}]
                    # We need to pivot the dict of series into list of dicts.
                    
                    # Get index from one of them
                    first_key = list(data.keys())[0]
                    index = data[first_key].index
                    
                    for ts in index:
                        point = {"ts": ts.isoformat()}
                        for k, v in data.items():
                            val = v.get(ts)
                            point[k] = float(val) if not pd.isna(val) else None
                        series_data.append(point)
                        
                elif isinstance(data, pd.Series):
                    for ts, val in data.items():
                        series_data.append({
                            "ts": ts.isoformat(),
                            "value": float(val) if not pd.isna(val) else None
                        })
            
            return {
                "insufficient_data": is_insufficient,
                "reference_levels": refs,
                "series": series_data
            }

        return {
            "ticker": ticker,
            "timeframe": f"intraday_{interval}" if is_intraday else f"daily_{period}",
            "indicators": {
                "RSI": format_indicator("RSI", inds.get('rsi'), [30, 70]),
                "MACD": format_indicator("MACD", inds.get('macd'), [0]),
                "STOCH": format_indicator("STOCH", inds.get('stoch'), [20, 80]),
                "ROC": format_indicator("ROC", inds.get('roc'), [0]),
                "CCI": format_indicator("CCI", inds.get('cci'), [-100, 100]),
                "ADX": format_indicator("ADX", inds.get('adx'), [25]),
                "MFI": format_indicator("MFI", inds.get('mfi'), [20, 80])
            }
        }
    except Exception as e:
        logger.error(f"Error in security indicators: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
