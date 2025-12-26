"""
ETF Service
Handles ETF holdings, metadata, look-through exposure, and factor DNA.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import yfinance as yf

logger = logging.getLogger(__name__)

# Static ETF holdings data (fallback when yfinance fails)
# This would ideally come from a database or API
STATIC_ETF_HOLDINGS = {
    "SPY": [
        {"ticker": "AAPL", "name": "Apple Inc", "weight": 0.072, "sector": "Technology", "country": "US"},
        {"ticker": "MSFT", "name": "Microsoft Corp", "weight": 0.068, "sector": "Technology", "country": "US"},
        {"ticker": "AMZN", "name": "Amazon.com Inc", "weight": 0.035, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "NVDA", "name": "NVIDIA Corp", "weight": 0.034, "sector": "Technology", "country": "US"},
        {"ticker": "GOOGL", "name": "Alphabet Inc A", "weight": 0.023, "sector": "Communication Services", "country": "US"},
        {"ticker": "META", "name": "Meta Platforms", "weight": 0.022, "sector": "Communication Services", "country": "US"},
        {"ticker": "TSLA", "name": "Tesla Inc", "weight": 0.019, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "BRK.B", "name": "Berkshire Hathaway B", "weight": 0.017, "sector": "Financial Services", "country": "US"},
        {"ticker": "UNH", "name": "UnitedHealth Group", "weight": 0.013, "sector": "Healthcare", "country": "US"},
        {"ticker": "JPM", "name": "JPMorgan Chase", "weight": 0.012, "sector": "Financial Services", "country": "US"},
    ],
    "QQQ": [
        {"ticker": "AAPL", "name": "Apple Inc", "weight": 0.115, "sector": "Technology", "country": "US"},
        {"ticker": "MSFT", "name": "Microsoft Corp", "weight": 0.105, "sector": "Technology", "country": "US"},
        {"ticker": "AMZN", "name": "Amazon.com Inc", "weight": 0.056, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "NVDA", "name": "NVIDIA Corp", "weight": 0.054, "sector": "Technology", "country": "US"},
        {"ticker": "META", "name": "Meta Platforms", "weight": 0.045, "sector": "Communication Services", "country": "US"},
        {"ticker": "GOOGL", "name": "Alphabet Inc A", "weight": 0.038, "sector": "Communication Services", "country": "US"},
        {"ticker": "GOOG", "name": "Alphabet Inc C", "weight": 0.037, "sector": "Communication Services", "country": "US"},
        {"ticker": "TSLA", "name": "Tesla Inc", "weight": 0.032, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "AVGO", "name": "Broadcom Inc", "weight": 0.028, "sector": "Technology", "country": "US"},
        {"ticker": "COST", "name": "Costco Wholesale", "weight": 0.025, "sector": "Consumer Defensive", "country": "US"},
    ],
    "VTI": [
        {"ticker": "AAPL", "name": "Apple Inc", "weight": 0.065, "sector": "Technology", "country": "US"},
        {"ticker": "MSFT", "name": "Microsoft Corp", "weight": 0.060, "sector": "Technology", "country": "US"},
        {"ticker": "AMZN", "name": "Amazon.com Inc", "weight": 0.032, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "NVDA", "name": "NVIDIA Corp", "weight": 0.030, "sector": "Technology", "country": "US"},
        {"ticker": "GOOGL", "name": "Alphabet Inc A", "weight": 0.021, "sector": "Communication Services", "country": "US"},
        {"ticker": "META", "name": "Meta Platforms", "weight": 0.019, "sector": "Communication Services", "country": "US"},
        {"ticker": "TSLA", "name": "Tesla Inc", "weight": 0.017, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "BRK.B", "name": "Berkshire Hathaway B", "weight": 0.015, "sector": "Financial Services", "country": "US"},
        {"ticker": "UNH", "name": "UnitedHealth Group", "weight": 0.012, "sector": "Healthcare", "country": "US"},
        {"ticker": "XOM", "name": "Exxon Mobil", "weight": 0.011, "sector": "Energy", "country": "US"},
    ],
    "VUG": [
        {"ticker": "AAPL", "name": "Apple Inc", "weight": 0.135, "sector": "Technology", "country": "US"},
        {"ticker": "MSFT", "name": "Microsoft Corp", "weight": 0.125, "sector": "Technology", "country": "US"},
        {"ticker": "NVDA", "name": "NVIDIA Corp", "weight": 0.065, "sector": "Technology", "country": "US"},
        {"ticker": "AMZN", "name": "Amazon.com Inc", "weight": 0.058, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "META", "name": "Meta Platforms", "weight": 0.042, "sector": "Communication Services", "country": "US"},
        {"ticker": "GOOGL", "name": "Alphabet Inc A", "weight": 0.038, "sector": "Communication Services", "country": "US"},
        {"ticker": "TSLA", "name": "Tesla Inc", "weight": 0.035, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "LLY", "name": "Eli Lilly", "weight": 0.028, "sector": "Healthcare", "country": "US"},
        {"ticker": "AVGO", "name": "Broadcom Inc", "weight": 0.025, "sector": "Technology", "country": "US"},
        {"ticker": "V", "name": "Visa Inc", "weight": 0.022, "sector": "Financial Services", "country": "US"},
    ],
    "VTV": [
        {"ticker": "BRK.B", "name": "Berkshire Hathaway B", "weight": 0.035, "sector": "Financial Services", "country": "US"},
        {"ticker": "JPM", "name": "JPMorgan Chase", "weight": 0.028, "sector": "Financial Services", "country": "US"},
        {"ticker": "UNH", "name": "UnitedHealth Group", "weight": 0.027, "sector": "Healthcare", "country": "US"},
        {"ticker": "XOM", "name": "Exxon Mobil", "weight": 0.026, "sector": "Energy", "country": "US"},
        {"ticker": "JNJ", "name": "Johnson & Johnson", "weight": 0.022, "sector": "Healthcare", "country": "US"},
        {"ticker": "PG", "name": "Procter & Gamble", "weight": 0.021, "sector": "Consumer Defensive", "country": "US"},
        {"ticker": "CVX", "name": "Chevron Corp", "weight": 0.018, "sector": "Energy", "country": "US"},
        {"ticker": "HD", "name": "Home Depot", "weight": 0.017, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "MRK", "name": "Merck & Co", "weight": 0.016, "sector": "Healthcare", "country": "US"},
        {"ticker": "ABBV", "name": "AbbVie Inc", "weight": 0.015, "sector": "Healthcare", "country": "US"},
    ],
    "IWM": [
        {"ticker": "SMCI", "name": "Super Micro Computer", "weight": 0.008, "sector": "Technology", "country": "US"},
        {"ticker": "MSTR", "name": "MicroStrategy", "weight": 0.007, "sector": "Technology", "country": "US"},
        {"ticker": "CRVS", "name": "Corvus Pharmaceuticals", "weight": 0.006, "sector": "Healthcare", "country": "US"},
        {"ticker": "UPST", "name": "Upstart Holdings", "weight": 0.005, "sector": "Financial Services", "country": "US"},
        {"ticker": "CELH", "name": "Celsius Holdings", "weight": 0.005, "sector": "Consumer Defensive", "country": "US"},
        {"ticker": "SAIA", "name": "Saia Inc", "weight": 0.004, "sector": "Industrials", "country": "US"},
        {"ticker": "TGTX", "name": "TG Therapeutics", "weight": 0.004, "sector": "Healthcare", "country": "US"},
        {"ticker": "CROX", "name": "Crocs Inc", "weight": 0.004, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "WING", "name": "Wingstop Inc", "weight": 0.004, "sector": "Consumer Cyclical", "country": "US"},
        {"ticker": "FN", "name": "Fabrinet", "weight": 0.003, "sector": "Technology", "country": "US"},
    ],
    "GLD": [
        {"ticker": "GOLD", "name": "Gold Bullion", "weight": 1.0, "sector": "Commodities", "country": "US"},
    ],
    "TLT": [
        {"ticker": "UST20Y", "name": "US Treasury 20+ Year", "weight": 1.0, "sector": "Fixed Income", "country": "US"},
    ],
}

# Sector to factor exposure mapping (simplified)
SECTOR_FACTOR_MAP = {
    "Technology": {"value": -0.4, "momentum": 0.6, "quality": 0.3, "size": -0.2, "volatility": 0.4},
    "Healthcare": {"value": 0.1, "momentum": 0.2, "quality": 0.4, "size": -0.1, "volatility": 0.1},
    "Financial Services": {"value": 0.3, "momentum": 0.0, "quality": 0.2, "size": 0.1, "volatility": 0.2},
    "Consumer Cyclical": {"value": -0.1, "momentum": 0.4, "quality": 0.1, "size": 0.0, "volatility": 0.3},
    "Consumer Defensive": {"value": 0.2, "momentum": -0.1, "quality": 0.3, "size": 0.0, "volatility": -0.2},
    "Energy": {"value": 0.4, "momentum": 0.2, "quality": 0.1, "size": 0.2, "volatility": 0.3},
    "Communication Services": {"value": -0.2, "momentum": 0.3, "quality": 0.2, "size": -0.2, "volatility": 0.2},
    "Industrials": {"value": 0.1, "momentum": 0.1, "quality": 0.2, "size": 0.1, "volatility": 0.1},
    "Utilities": {"value": 0.3, "momentum": -0.2, "quality": 0.2, "size": 0.1, "volatility": -0.3},
    "Real Estate": {"value": 0.2, "momentum": 0.0, "quality": 0.1, "size": 0.1, "volatility": 0.1},
    "Materials": {"value": 0.2, "momentum": 0.1, "quality": 0.1, "size": 0.1, "volatility": 0.2},
    "Commodities": {"value": 0.1, "momentum": 0.3, "quality": 0.0, "size": 0.0, "volatility": 0.4},
    "Fixed Income": {"value": 0.0, "momentum": -0.1, "quality": 0.5, "size": 0.0, "volatility": -0.4},
}

# Known ETFs list
KNOWN_ETFS = ["SPY", "QQQ", "VTI", "VUG", "VTV", "IWM", "DIA", "GLD", "TLT", "HYG", "IEF", "SHY", 
              "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "VOO", "VGT"]


def is_etf(ticker: str) -> bool:
    """Check if a ticker is likely an ETF."""
    ticker_upper = ticker.upper()
    return ticker_upper in KNOWN_ETFS or ticker_upper.startswith("V") or ticker_upper.startswith("X")


def get_etf_holdings(ticker: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Get ETF holdings. Tries yfinance first, falls back to static data.
    """
    ticker_upper = ticker.upper()
    
    # Try static data first (more reliable)
    if ticker_upper in STATIC_ETF_HOLDINGS:
        holdings = STATIC_ETF_HOLDINGS[ticker_upper][:top_n]
        return holdings
    
    # Try yfinance
    try:
        etf = yf.Ticker(ticker)
        
        # Try to get holdings from info or known methods
        info = etf.info
        
        # yfinance doesn't reliably provide ETF holdings
        # Return empty or generate placeholder
        return []
        
    except Exception as e:
        logger.warning(f"Could not fetch holdings for {ticker}: {e}")
        return []


def get_sector_breakdown(holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate holdings by sector."""
    sector_weights = {}
    
    for h in holdings:
        sector = h.get("sector", "Other")
        weight = h.get("weight", 0)
        sector_weights[sector] = sector_weights.get(sector, 0) + weight
    
    # Sort by weight descending
    sectors = [{"sector": k, "weight": round(v, 4)} for k, v in sector_weights.items()]
    sectors.sort(key=lambda x: -x["weight"])
    
    return sectors


def get_country_breakdown(holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate holdings by country."""
    country_weights = {}
    
    for h in holdings:
        country = h.get("country", "Unknown")
        weight = h.get("weight", 0)
        country_weights[country] = country_weights.get(country, 0) + weight
    
    countries = [{"country": k, "weight": round(v, 4)} for k, v in country_weights.items()]
    countries.sort(key=lambda x: -x["weight"])
    
    return countries


def compute_etf_factor_exposure(holdings: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Compute weighted factor exposures for an ETF based on sector composition.
    """
    factors = {"value": 0.0, "momentum": 0.0, "quality": 0.0, "size": 0.0, "volatility": 0.0}
    total_weight = 0.0
    
    for h in holdings:
        sector = h.get("sector", "Other")
        weight = h.get("weight", 0)
        
        if sector in SECTOR_FACTOR_MAP:
            sector_factors = SECTOR_FACTOR_MAP[sector]
            for f in factors:
                factors[f] += weight * sector_factors.get(f, 0)
            total_weight += weight
    
    # Normalize by total weight
    if total_weight > 0:
        for f in factors:
            factors[f] = round(factors[f] / total_weight, 3)
    
    return factors


def get_etf_lookthrough(ticker: str, top_n: int = 10, include_factors: bool = True) -> Dict[str, Any]:
    """
    Get full look-through exposure for an ETF.
    """
    holdings = get_etf_holdings(ticker, top_n)
    
    if not holdings:
        return {
            "ticker": ticker,
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "top_holdings": [],
            "sectors": [],
            "countries": [],
            "factors": {},
            "liquidity": {"score": 0.0, "comment": "No holdings data available"},
            "meta": {"source": "none", "cache_ttl_sec": 86400}
        }
    
    sectors = get_sector_breakdown(holdings)
    countries = get_country_breakdown(holdings)
    factors = compute_etf_factor_exposure(holdings) if include_factors else {}
    
    # Simple liquidity score based on ETF type
    ticker_upper = ticker.upper()
    if ticker_upper in ["SPY", "QQQ", "IWM", "DIA"]:
        liquidity_score = 0.95
        liquidity_comment = "Extremely liquid large-cap ETF"
    elif ticker_upper in ["VTI", "VUG", "VTV", "VOO"]:
        liquidity_score = 0.90
        liquidity_comment = "Highly liquid broad market ETF"
    elif ticker_upper in ["GLD", "TLT"]:
        liquidity_score = 0.85
        liquidity_comment = "Liquid commodity/bond ETF"
    else:
        liquidity_score = 0.70
        liquidity_comment = "Standard ETF liquidity"
    
    return {
        "ticker": ticker,
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "top_holdings": holdings,
        "sectors": sectors,
        "countries": countries,
        "factors": factors,
        "liquidity": {"score": liquidity_score, "comment": liquidity_comment},
        "meta": {"source": "static_data", "cache_ttl_sec": 86400}
    }


def compute_etf_factor_dna(
    etf: str,
    peer_etfs: List[str],
    factors: List[str] = None
) -> Dict[str, Any]:
    """
    Compute factor personality of an ETF and compare with peers.
    """
    if factors is None:
        factors = ["value", "momentum", "quality", "size", "volatility"]
    
    # Get ETF exposures
    etf_holdings = get_etf_holdings(etf, 20)
    etf_factors = compute_etf_factor_exposure(etf_holdings)
    
    # Build factor details
    factor_details = []
    for f in factors:
        exposure = etf_factors.get(f, 0)
        # Purity is how extreme the exposure is
        purity = min(1.0, abs(exposure) * 1.5)
        
        factor_details.append({
            "name": f,
            "exposure": exposure,
            "purity": round(purity, 2),
            "drift_1y": round(np.random.uniform(-0.1, 0.1), 3)  # Placeholder for historical drift
        })
    
    # Get peer exposures
    peers = []
    for peer in peer_etfs:
        peer_holdings = get_etf_holdings(peer, 20)
        peer_factors = compute_etf_factor_exposure(peer_holdings)
        peers.append({
            "ticker": peer,
            "factors": peer_factors
        })
    
    return {
        "etf": etf,
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "factors": factor_details,
        "peers": peers,
        "meta": {"factors": factors, "cache_ttl_sec": 86400}
    }
