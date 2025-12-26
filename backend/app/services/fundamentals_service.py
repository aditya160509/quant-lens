"""
Fundamentals Service Module
yfinance wrapper for corporate fundamentals (E7).
"""

import yfinance as yf
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Fetch fundamentals for a ticker using yfinance.
    
    Returns:
        Dict with valuation, growth, profitability, dividends, balance, ranks, meta
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or info.get('regularMarketPrice') is None:
            return {
                "ticker": ticker,
                "error": "Ticker not found or no data available",
                "meta": {"source": "yfinance", "as_of": datetime.now().isoformat()}
            }
        
        # Valuation metrics
        valuation = {
            "pe": _safe_get(info, 'trailingPE'),
            "pe_forward": _safe_get(info, 'forwardPE'),
            "pb": _safe_get(info, 'priceToBook'),
            "ps": _safe_get(info, 'priceToSalesTrailing12Months'),
            "ev_ebitda": _safe_get(info, 'enterpriseToEbitda'),
            "ev_revenue": _safe_get(info, 'enterpriseToRevenue'),
            "peg": _safe_get(info, 'pegRatio'),
            "market_cap": _safe_get(info, 'marketCap'),
            "enterprise_value": _safe_get(info, 'enterpriseValue'),
        }
        
        # Growth metrics
        growth = {
            "revenue_growth": _safe_get(info, 'revenueGrowth'),
            "earnings_growth": _safe_get(info, 'earningsGrowth'),
            "earnings_quarterly_growth": _safe_get(info, 'earningsQuarterlyGrowth'),
            "revenue_per_share": _safe_get(info, 'revenuePerShare'),
            "eps_trailing": _safe_get(info, 'trailingEps'),
            "eps_forward": _safe_get(info, 'forwardEps'),
        }
        
        # Profitability metrics
        profitability = {
            "roe": _safe_get(info, 'returnOnEquity'),
            "roa": _safe_get(info, 'returnOnAssets'),
            "gross_margin": _safe_get(info, 'grossMargins'),
            "operating_margin": _safe_get(info, 'operatingMargins'),
            "profit_margin": _safe_get(info, 'profitMargins'),
            "ebitda_margin": _safe_get(info, 'ebitdaMargins'),
        }
        
        # Dividend metrics
        dividends = {
            "yield": _safe_get(info, 'dividendYield'),
            "rate": _safe_get(info, 'dividendRate'),
            "payout_ratio": _safe_get(info, 'payoutRatio'),
            "ex_date": _safe_get(info, 'exDividendDate'),
            "five_year_avg_yield": _safe_get(info, 'fiveYearAvgDividendYield'),
        }
        
        # Balance sheet metrics
        balance = {
            "total_cash": _safe_get(info, 'totalCash'),
            "total_debt": _safe_get(info, 'totalDebt'),
            "cash_per_share": _safe_get(info, 'totalCashPerShare'),
            "debt_to_equity": _safe_get(info, 'debtToEquity'),
            "current_ratio": _safe_get(info, 'currentRatio'),
            "quick_ratio": _safe_get(info, 'quickRatio'),
            "book_value": _safe_get(info, 'bookValue'),
        }
        
        # Company info
        company = {
            "name": _safe_get(info, 'longName') or _safe_get(info, 'shortName'),
            "sector": _safe_get(info, 'sector'),
            "industry": _safe_get(info, 'industry'),
            "country": _safe_get(info, 'country'),
            "currency": _safe_get(info, 'currency'),
            "exchange": _safe_get(info, 'exchange'),
            "employees": _safe_get(info, 'fullTimeEmployees'),
        }
        
        # Price info
        price = {
            "current": _safe_get(info, 'regularMarketPrice') or _safe_get(info, 'currentPrice'),
            "previous_close": _safe_get(info, 'regularMarketPreviousClose'),
            "open": _safe_get(info, 'regularMarketOpen'),
            "day_high": _safe_get(info, 'regularMarketDayHigh'),
            "day_low": _safe_get(info, 'regularMarketDayLow'),
            "fifty_two_week_high": _safe_get(info, 'fiftyTwoWeekHigh'),
            "fifty_two_week_low": _safe_get(info, 'fiftyTwoWeekLow'),
            "fifty_day_avg": _safe_get(info, 'fiftyDayAverage'),
            "two_hundred_day_avg": _safe_get(info, 'twoHundredDayAverage'),
            "volume": _safe_get(info, 'regularMarketVolume'),
            "avg_volume": _safe_get(info, 'averageVolume'),
            "avg_volume_10d": _safe_get(info, 'averageDailyVolume10Day'),
        }
        
        # Analyst info
        analyst = {
            "target_high": _safe_get(info, 'targetHighPrice'),
            "target_low": _safe_get(info, 'targetLowPrice'),
            "target_mean": _safe_get(info, 'targetMeanPrice'),
            "target_median": _safe_get(info, 'targetMedianPrice'),
            "recommendation": _safe_get(info, 'recommendationKey'),
            "recommendation_mean": _safe_get(info, 'recommendationMean'),
            "num_analysts": _safe_get(info, 'numberOfAnalystOpinions'),
        }
        
        return {
            "ticker": ticker.upper(),
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "company": company,
            "price": price,
            "valuation": valuation,
            "growth": growth,
            "profitability": profitability,
            "dividends": dividends,
            "balance": balance,
            "analyst": analyst,
            "ranks": None,  # To be computed separately if needed
            "meta": {
                "source": "yfinance",
                "cache_ttl_sec": 86400,
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching fundamentals for {ticker}: {e}")
        return {
            "ticker": ticker,
            "error": str(e),
            "meta": {"source": "yfinance", "as_of": datetime.now().isoformat()}
        }


def get_fundamentals_compact(ticker: str) -> Dict[str, Any]:
    """
    Get compact fundamentals for quick display (Security page card).
    """
    full = get_fundamentals(ticker)
    
    if "error" in full:
        return full
    
    return {
        "ticker": full["ticker"],
        "name": full.get("company", {}).get("name"),
        "pe": full.get("valuation", {}).get("pe"),
        "pb": full.get("valuation", {}).get("pb"),
        "ps": full.get("valuation", {}).get("ps"),
        "ev_ebitda": full.get("valuation", {}).get("ev_ebitda"),
        "roe": full.get("profitability", {}).get("roe"),
        "roa": full.get("profitability", {}).get("roa"),
        "gross_margin": full.get("profitability", {}).get("gross_margin"),
        "operating_margin": full.get("profitability", {}).get("operating_margin"),
        "revenue_growth": full.get("growth", {}).get("revenue_growth"),
        "eps_trailing": full.get("growth", {}).get("eps_trailing"),
        "dividend_yield": full.get("dividends", {}).get("yield"),
        "debt_to_equity": full.get("balance", {}).get("debt_to_equity"),
        "current_ratio": full.get("balance", {}).get("current_ratio"),
        "target_mean": full.get("analyst", {}).get("target_mean"),
        "recommendation": full.get("analyst", {}).get("recommendation"),
        "meta": full.get("meta"),
    }


def _safe_get(d: dict, key: str, default=None) -> Any:
    """
    Safely get a value from dict, returning None if not found or if value is NaN.
    """
    import math
    val = d.get(key, default)
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def format_large_number(n: Optional[float]) -> Optional[str]:
    """
    Format large numbers for display (e.g., 1.5B, 450M).
    """
    if n is None:
        return None
    if abs(n) >= 1e12:
        return f"{n/1e12:.2f}T"
    elif abs(n) >= 1e9:
        return f"{n/1e9:.2f}B"
    elif abs(n) >= 1e6:
        return f"{n/1e6:.2f}M"
    elif abs(n) >= 1e3:
        return f"{n/1e3:.2f}K"
    else:
        return f"{n:.2f}"


def format_percentage(n: Optional[float]) -> Optional[str]:
    """
    Format decimal as percentage string.
    """
    if n is None:
        return None
    return f"{n * 100:.2f}%"
