import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_option_chain(ticker):
    try:
        tk = yf.Ticker(ticker)
        
        # Get spot price
        hist = tk.history(period="1d")
        if hist.empty:
            return {"error": "No data for ticker"}
        spot = hist["Close"].iloc[-1]
        
        # Get expirations
        exps = tk.options
        if not exps:
            return {"underlying": ticker, "spot": spot, "options": []}
            
        # Fetch first expiration for demo speed, or maybe first 2
        # For a real terminal we might want more, but yfinance is slow
        target_exp = exps[0]
        
        chain = tk.option_chain(target_exp)
        calls = chain.calls
        puts = chain.puts
        
        options = []
        
        # Process Calls
        for _, row in calls.iterrows():
            greeks = calculate_greeks("call", spot, row["strike"], 0.05, (datetime.strptime(target_exp, "%Y-%m-%d") - datetime.now()).days / 365.0, row["impliedVolatility"])
            options.append({
                "type": "call",
                "strike": row["strike"],
                "expiry": target_exp,
                "iv": row["impliedVolatility"],
                "lastPrice": row["lastPrice"],
                **greeks
            })
            
        # Process Puts
        for _, row in puts.iterrows():
            greeks = calculate_greeks("put", spot, row["strike"], 0.05, (datetime.strptime(target_exp, "%Y-%m-%d") - datetime.now()).days / 365.0, row["impliedVolatility"])
            options.append({
                "type": "put",
                "strike": row["strike"],
                "expiry": target_exp,
                "iv": row["impliedVolatility"],
                "lastPrice": row["lastPrice"],
                **greeks
            })
            
        return {
            "underlying": ticker,
            "spot": spot,
            "options": options
        }
        
    except Exception as e:
        logger.error(f"Error fetching options for {ticker}: {e}")
        return {"error": str(e)}

def calculate_greeks(flag, S, K, r, t, sigma):
    # Black Scholes Merton
    # flag: 'call' or 'put'
    # S: Spot price
    # K: Strike price
    # r: Risk-free rate
    # t: Time to expiration (years)
    # sigma: Volatility
    
    if t <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
        
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    
    if flag == 'call':
        delta = norm.cdf(d1)
        rho = K * t * np.exp(-r * t) * norm.cdf(d2)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(t)) - r * K * np.exp(-r * t) * norm.cdf(d2)) / 365.0
    else:
        delta = norm.cdf(d1) - 1
        rho = -K * t * np.exp(-r * t) * norm.cdf(-d2)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(t)) + r * K * np.exp(-r * t) * norm.cdf(-d2)) / 365.0
        
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(t))
    vega = S * norm.pdf(d1) * np.sqrt(t) / 100.0 # Per 1% vol change
    
    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega),
        "rho": float(rho)
    }
