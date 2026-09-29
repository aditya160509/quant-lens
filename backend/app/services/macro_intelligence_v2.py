import pandas as pd
import numpy as np
import polars as pl
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from scipy import stats
from sklearn.decomposition import PCA

from app.services.data_engine import engine
from app.macro_data import fetch_series, SERIES_MAPPING

logger = logging.getLogger(__name__)

def compute_macro_surveillance() -> Dict:
    """
    1. SURVEILLANCE: Global Cross-Asset Intelligence.
    """
    # Cross-Asset Momentum Ribbon (Gold, Equity, Bonds)
    assets = {
        "Equity": "SPY",
        "Gold": "GLD",
        "Bonds": "TLT",
        "Oil": "CL=F"
    }
    
    returns_df = engine.get_returns_matrix(tickers=list(assets.values()), lookback_days=252)
    if returns_df.empty:
        return {"error": "Insufficient data"}
    
    # Cumulative returns for momentum ribbon
    cum_ret = (1 + returns_df).cumprod()
    
    # Current leader
    current_leader = cum_ret.iloc[-1].idxmax()
    leader_name = [k for k, v in assets.items() if v == current_leader][0]
    
    # Global Volmesh (VIX, IndiaVIX proxy)
    vix_df = engine.get_full_ohlcv("^VIX", 120)
    
    return {
        "momentum_ribbon": {
            "history": cum_ret.reset_index().to_dict(orient="records"),
            "current_leader": leader_name,
            "assets": assets
        },
        "vol_mesh": {
            "vix": vix_df['Close'].tolist(),
            "dates": vix_df.index.tolist()
        },
        "briefing": [
            {"title": f"Dominant Asset: {leader_name}", "delta": "Positive Momentum"},
            {"title": "Global Volatility", "delta": "Contained" if vix_df['Close'].iloc[-1] < 20 else "Elevated"}
        ]
    }

def compute_macro_regimes() -> Dict:
    """
    2. REGIMES: Environmental Landscapes.
    4-State Model: Bull/Bear x Low/High Vol
    """
    spy = engine.get_full_ohlcv("SPY", 504) # 2 years
    if spy.empty: return {"error": "No data"}
    
    returns = np.log(spy['Close'] / spy['Close'].shift(1)).dropna()
    vols = returns.rolling(20).std() * np.sqrt(252)
    
    # Simple thresholds for 4-state regime (HMM proxy)
    mu_med = returns.median()
    vol_med = vols.median()
    
    curr_ret = returns.iloc[-20:].mean()
    curr_vol = vols.iloc[-1]
    
    regime = ""
    if curr_ret > mu_med:
        regime = "Bull " + ("Low Vol" if curr_vol < vol_med else "High Vol")
    else:
        regime = "Bear " + ("Low Vol" if curr_vol < vol_med else "High Vol")
        
    return {
        "current_regime": regime,
        "state_profile": {
            "label": regime,
            "avg_return": float(curr_ret * 252),
            "volatility": float(curr_vol),
            "sharpe": float((curr_ret * 252) / curr_vol) if curr_vol != 0 else 0
        },
        "transition_matrix": [
            [0.8, 0.1, 0.05, 0.05],
            [0.1, 0.7, 0.1, 0.1],
            [0.05, 0.1, 0.8, 0.05],
            [0.05, 0.1, 0.05, 0.8]
        ] # Placeholder for real HMM output
    }

def compute_macro_fragility() -> Dict:
    """
    3. FRAGILITY: Systemic Network.
    Absorption Ratio (PCA)
    """
    # Use top 50 tickers by volatility/liquidity as proxy for systemic risk
    tickers = engine.get_tickers_for_universe("sp500")[:50]
    if not tickers: tickers = engine._df["Ticker"].unique().head(50).to_list()
    
    returns = engine.get_returns_matrix(tickers=tickers, lookback_days=120)
    if returns.empty or returns.shape[0] < 10: 
        return {
            "absorption_ratio": 0.45, 
            "status": "Resilient",
            "var_99": -2.5
        }
    
    # PCA Absorption Ratio
    try:
        pca = PCA(n_components=min(5, returns.shape[1]))
        pca.fit(returns.fillna(0))
        absorption = np.sum(pca.explained_variance_ratio_[:2]) # Top 2 components
        
        return {
            "absorption_ratio": float(absorption),
            "status": "Fragile" if absorption > 0.6 else "Resilient",
            "var_99": float(returns.sum(axis=1).quantile(0.01))
        }
    except Exception as e:
        logger.error(f"Fragility Error: {e}")
        return {"absorption_ratio": 0.5, "status": "Resilient", "var_99": -2.0}

def compute_macro_credit() -> Dict:
    """
    4. CREDIT: Yield Surface & Spreads.
    """
    d10 = fetch_series(SERIES_MAPPING['DGS10'], observation_start='2020-01-01')
    d2 = fetch_series(SERIES_MAPPING['DGS2'], observation_start='2020-01-01')
    
    if d10.empty or d2.empty:
        return {"error": "FRED data unavailable"}
        
    return {
        "yield_curve": {
            "dates": d10.index.strftime("%Y-%m-%d").tolist(),
            "ten_year": d10.values.tolist(),
            "two_year": d2.values.tolist(),
            "spread": (d10 - d2).values.tolist()
        },
        "real_rates": {
            "current": float(d10.iloc[-1] - 2.5), # Proxy for now
            "target": 0.5
        }
    }

def compute_macro_growth() -> Dict:
    """
    5. GROWTH: Economic Cycle & Inflation.
    """
    try:
        gdp = fetch_series(SERIES_MAPPING['GDP'], observation_start='2018-01-01')
        cpi = fetch_series(SERIES_MAPPING['CPI'], observation_start='2020-01-01')
        unrate = fetch_series(SERIES_MAPPING['UNRATE'], observation_start='2020-01-01')
        
        gdp_growth = gdp.pct_change(4).iloc[-1] * 100 # YoY GDP
        cpi_yoy = cpi.pct_change(12).iloc[-1] * 100 # YoY CPI
        
        return {
            "gdp_growth": float(gdp_growth),
            "inflation": float(cpi_yoy),
            "unemployment": float(unrate.iloc[-1]),
            "cycle_phase": "Expansion" if gdp_growth > 2 else "Stagnation",
            "history": {
                "gdp": gdp.to_dict(),
                "cpi": cpi.to_dict()
            }
        }
    except Exception as e:
        logger.error(f"Growth module error: {e}")
        return {"error": str(e)}

def compute_macro_breadth() -> Dict:
    """
    6. BREADTH: Market Participation.
    """
    # Calculate breadth from the 1400+ universe
    universe_df = engine._df
    if universe_df is None: return {"error": "No universe data"}
    
    # Get last 2 days of data for all tickers
    # Use returns matrix for a subset to gauge overall market participation
    tickers = engine.get_tickers_for_universe("sp500")[:100]
    if not tickers:
        tickers = engine._df["Ticker"].unique().head(100).to_list()
        
    returns = engine.get_returns_matrix(tickers=tickers, lookback_days=1)
    if returns.empty:
        return {"advance_decline_ratio": 1.0, "status": "Stable", "participation_score": 50}
    
    advancing = int((returns.iloc[-1] > 0).sum())
    declining = int((returns.iloc[-1] < 0).sum())
    
    return {
        "advance_decline_ratio": float(advancing / declining) if declining > 0 else float(advancing),
        "high_low_index": 75.0, # Placeholder
        "participation_score": float(advancing / len(tickers)) * 100,
        "status": "Healthy" if advancing > declining else "Narrow"
    }

def compute_macro_flow() -> Dict:
    """
    7. FLOW: Institutional Gravity.
    """
    # Proxy flow using volume surges in key ETFs
    spy_vol = engine.get_full_ohlcv("SPY", 20)
    tlt_vol = engine.get_full_ohlcv("TLT", 20)
    
    spy_surge = spy_vol['Volume'].iloc[-1] / spy_vol['Volume'].mean()
    tlt_surge = tlt_vol['Volume'].iloc[-1] / tlt_vol['Volume'].mean()
    
    return {
        "equity_flow_surge": float(spy_surge),
        "bond_flow_surge": float(tlt_surge),
        "dominant_flow": "Equity" if spy_surge > tlt_surge else "Fixed Income",
        "liquidity_state": "Ample" if spy_surge > 0.8 else "Tight"
    }

def compute_macro_positioning() -> Dict:
    """
    8. POSITIONING: Sentiment & Crowding.
    """
    # Proxy using RSI and Distance from SMA
    spy = engine.get_full_ohlcv("SPY", 200)
    sma200 = spy['Close'].rolling(200).mean().iloc[-1]
    dist = (spy['Close'].iloc[-1] / sma200 - 1) * 100
    
    return {
        "crowding_index": float(dist), # Distance from 200d SMA as crowding proxy
        "sentiment_score": 65, # Placeholder (Fear/Greed)
        "signal": "Overextended" if dist > 15 else "Neutral",
        "cta_trend": "Long" if spy['Close'].iloc[-1] > sma200 else "Short"
    }

def get_macro_command_center_full() -> Dict:
    """
    Aggregated response for all macro modules.
    """
    return {
        "surveillance": compute_macro_surveillance(),
        "regimes": compute_macro_regimes(),
        "fragility": compute_macro_fragility(),
        "credit": compute_macro_credit(),
        "growth": compute_macro_growth(),
        "breadth": compute_macro_breadth(),
        "flow": compute_macro_flow(),
        "positioning": compute_macro_positioning(),
        "asOf": datetime.now().isoformat()
    }
