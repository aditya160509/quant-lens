"""
Earnings API - Upcoming earnings calendar and historical earnings data.
"""

from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Universe of tracked tickers
TRACKED_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC", "WMT",
    "PG", "JNJ", "XOM", "CVX", "UNH", "HD", "MA", "V", "DIS", "NFLX"
]

# Sector mapping
SECTOR_MAP = {
    "AAPL": ("Technology", "Consumer Electronics"),
    "MSFT": ("Technology", "Software"),
    "GOOGL": ("Technology", "Internet Services"),
    "AMZN": ("Consumer Discretionary", "E-Commerce"),
    "NVDA": ("Technology", "Semiconductors"),
    "TSLA": ("Consumer Discretionary", "Auto Manufacturers"),
    "META": ("Technology", "Internet Services"),
    "JPM": ("Financials", "Banks"),
    "BAC": ("Financials", "Banks"),
    "WMT": ("Consumer Staples", "Retail"),
    "PG": ("Consumer Staples", "Household Products"),
    "JNJ": ("Healthcare", "Pharmaceuticals"),
    "XOM": ("Energy", "Oil & Gas"),
    "CVX": ("Energy", "Oil & Gas"),
    "UNH": ("Healthcare", "Health Insurance"),
    "HD": ("Consumer Discretionary", "Home Improvement"),
    "MA": ("Financials", "Credit Services"),
    "V": ("Financials", "Credit Services"),
    "DIS": ("Communication Services", "Entertainment"),
    "NFLX": ("Communication Services", "Streaming"),
}


@router.get("/upcoming")
def get_upcoming_earnings(days_ahead: int = Query(30, ge=1, le=90)):
    """
    Get upcoming earnings events for tracked tickers.
    """
    today = datetime.now()
    cutoff_date = today + timedelta(days=days_ahead)
    events = []
    
    for ticker in TRACKED_TICKERS:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            
            # Try to get earnings date from calendar
            earnings_date = None
            try:
                calendar = stock.calendar
                if calendar is not None:
                    if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                        dates = calendar.get('Earnings Date', [])
                        if dates and len(dates) > 0:
                            earnings_date = dates[0]
                    elif hasattr(calendar, 'empty') and not calendar.empty:
                        # DataFrame format
                        if 'Earnings Date' in calendar.index:
                            earnings_date = calendar.loc['Earnings Date'].iloc[0]
            except Exception as e:
                logger.debug(f"Could not get calendar for {ticker}: {e}")
            
            # If no date found, skip (don't synthesize data as per user request)
            if earnings_date is None:
                continue
            
            # Convert to datetime if needed
            if isinstance(earnings_date, str):
                earnings_date = datetime.strptime(earnings_date, "%Y-%m-%d")
            elif hasattr(earnings_date, 'to_pydatetime'):
                earnings_date = earnings_date.to_pydatetime()
            
            # Skip if not within range
            if earnings_date < today or earnings_date > cutoff_date:
                continue
            
            # Get expected EPS and revenue
            expected_eps = info.get('forwardEps') or info.get('trailingEps') or None
            expected_revenue = info.get('revenueEstimate') or info.get('totalRevenue') or None
            
            # Sector info
            sector_info = SECTOR_MAP.get(ticker, ("Other", "Other"))
            
            # Volatility proxy (would need price data, using placeholder)
            volatility_pre = 25.0  # Placeholder
            
            # Confidence based on analyst coverage
            num_analysts = info.get('numberOfAnalystOpinions', 0)
            confidence = min(0.95, 0.5 + (num_analysts * 0.05)) if num_analysts else 0.5
            
            # Significance flag based on implied move
            significance = "HIGH" if volatility_pre > 30 else "MEDIUM" if volatility_pre > 15 else "LOW"
            
            events.append({
                "symbol": ticker,
                "name": info.get('shortName', ticker),
                "earnings_date": earnings_date.strftime("%Y-%m-%d"),
                "expected_eps": round(float(expected_eps), 2) if expected_eps else None,
                "expected_revenue": float(expected_revenue) if expected_revenue else None,
                "sector": sector_info[0],
                "industry": sector_info[1],
                "confidence": round(confidence, 2),
                "volatility_pre_event": round(volatility_pre, 1),
                "significance_flag": significance
            })
            
        except Exception as e:
            logger.error(f"Error fetching upcoming earnings for {ticker}: {e}")
            continue
    
    # Sort by date
    events.sort(key=lambda x: x["earnings_date"])
    
    return {
        "as_of": datetime.now().isoformat(),
        "days_ahead": days_ahead,
        "events": events
    }


@router.get("/history/{symbol}")
def get_earnings_history(symbol: str, quarters: int = Query(8, ge=1, le=20)):
    """
    Get historical earnings data for a specific symbol.
    """
    try:
        stock = yf.Ticker(symbol.upper())
        info = stock.info or {}
        
        # Get historical earnings
        earnings_df = stock.earnings_history
        
        if earnings_df is None or (hasattr(earnings_df, 'empty') and earnings_df.empty):
            return {
                "symbol": symbol.upper(),
                "name": info.get('shortName', symbol),
                "quarters": []
            }
        
        # Also get historical price data for reaction calculations
        price_df = stock.history(period="2y")
        
        quarters_data = []
        
        # Process each earnings event
        for idx, row in earnings_df.head(quarters).iterrows():
            try:
                earnings_date = idx
                if isinstance(earnings_date, str):
                    earnings_date = pd.to_datetime(earnings_date)
                
                eps_actual = row.get('epsActual') or row.get('Reported EPS')
                eps_estimate = row.get('epsEstimate') or row.get('EPS Estimate')
                
                # Calculate surprise
                eps_surprise_pct = None
                if eps_actual is not None and eps_estimate is not None and eps_estimate != 0:
                    eps_surprise_pct = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100
                
                # Revenue data (may not be in earnings_history)
                revenue_actual = None
                revenue_estimate = None
                revenue_surprise_pct = None
                
                # Calculate price reactions if we have price data
                price_reaction_1d = None
                price_reaction_5d = None
                volatility_before = None
                volatility_after = None
                
                if not price_df.empty:
                    try:
                        # Find closes around earnings date
                        ed = pd.Timestamp(earnings_date)
                        
                        # Get price before (day before)
                        before_mask = price_df.index < ed
                        if before_mask.any():
                            price_before = price_df.loc[before_mask, 'Close'].iloc[-1]
                            
                            # Get price 1 day after
                            after_mask = price_df.index > ed
                            if after_mask.any():
                                after_prices = price_df.loc[after_mask, 'Close']
                                if len(after_prices) >= 1:
                                    price_1d = after_prices.iloc[0]
                                    price_reaction_1d = ((price_1d / price_before) - 1) * 100
                                
                                if len(after_prices) >= 5:
                                    price_5d = after_prices.iloc[4]
                                    price_reaction_5d = ((price_5d / price_before) - 1) * 100
                            
                            # Volatility before (20 days before)
                            before_slice = price_df.loc[before_mask].tail(20)
                            if len(before_slice) >= 10:
                                rets_before = before_slice['Close'].pct_change().dropna()
                                volatility_before = float(rets_before.std() * np.sqrt(252) * 100)
                            
                            # Volatility after (20 days after)
                            after_slice = price_df.loc[after_mask].head(20)
                            if len(after_slice) >= 10:
                                rets_after = after_slice['Close'].pct_change().dropna()
                                volatility_after = float(rets_after.std() * np.sqrt(252) * 100)
                    except Exception as pe:
                        logger.debug(f"Price reaction calc error: {pe}")
                
                # Quarter label
                quarter_label = f"{earnings_date.year} Q{((earnings_date.month - 1) // 3) + 1}"
                
                quarters_data.append({
                    "period": quarter_label,
                    "earnings_date": earnings_date.strftime("%Y-%m-%d"),
                    "eps_actual": round(float(eps_actual), 2) if eps_actual is not None else None,
                    "eps_estimate": round(float(eps_estimate), 2) if eps_estimate is not None else None,
                    "eps_surprise_pct": round(float(eps_surprise_pct), 1) if eps_surprise_pct is not None else None,
                    "revenue_actual": revenue_actual,
                    "revenue_estimate": revenue_estimate,
                    "revenue_surprise_pct": revenue_surprise_pct,
                    "price_reaction_1d_pct": round(float(price_reaction_1d), 2) if price_reaction_1d is not None else None,
                    "price_reaction_5d_pct": round(float(price_reaction_5d), 2) if price_reaction_5d is not None else None,
                    "volatility_before": round(float(volatility_before), 1) if volatility_before is not None else None,
                    "volatility_after": round(float(volatility_after), 1) if volatility_after is not None else None
                })
                
            except Exception as row_err:
                logger.debug(f"Error processing earnings row: {row_err}")
                continue
        
        return {
            "symbol": symbol.upper(),
            "name": info.get('shortName', symbol),
            "quarters": quarters_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching earnings history for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Keep legacy endpoint for backwards compatibility
@router.get("/calendar")
def get_earnings_calendar():
    """Legacy endpoint - redirects to /upcoming"""
    return get_upcoming_earnings(days_ahead=30)


# =============================================================================
# EARNINGS LAB ENDPOINTS (14 PRODUCTION-SAFE MODULES)
# =============================================================================

from app.services.earnings_lab import (
    EarningsSnapshot,
    ExpectationTracker,
    RepricingAnalyzer,
    ForwardExpectationReset,  # renamed from GuidanceEngine
    QualityEngine,
    ToneAnalyzer,
    RevisionTracker,
    ReactionAnalyzer,
    TargetDistribution,
    InstitutionalTracker,
    OwnershipAlerts,  # renamed from ActivistMonitor
    BuybackTracker,
    DividendMonitor,
    PeerComparator,
    earnings_lab_service,
)


# Module 1: Earnings Snapshot ✅
@router.get("/lab/snapshot/{symbol}")
def get_earnings_snapshot(symbol: str, quarters: int = Query(12, ge=1, le=20)):
    """Get complete earnings snapshot with beat/miss analysis."""
    try:
        return EarningsSnapshot.get_snapshot(symbol, quarters)
    except Exception as e:
        logger.error(f"Snapshot error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 2: Expectation Path Tracker ⚠️ (some historical gaps)
@router.get("/lab/expectations/{symbol}")
def get_expectations(symbol: str):
    """Track estimate drift and classify low/high bar."""
    try:
        return ExpectationTracker.get_expectations(symbol)
    except Exception as e:
        logger.error(f"Expectations error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 3: Post-Earnings Repricing ✅
@router.get("/lab/repricing/{symbol}")
def get_repricing(symbol: str):
    """Analyze post-earnings price action and market acceptance."""
    try:
        return RepricingAnalyzer.get_repricing(symbol)
    except Exception as e:
        logger.error(f"Repricing error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 4: Forward Expectation Reset (renamed from Guidance Delta)
@router.get("/lab/forward-reset/{symbol}")
def get_forward_reset(symbol: str):
    """Measure how expectations changed after earnings."""
    try:
        return ForwardExpectationReset.get_reset(symbol)
    except Exception as e:
        logger.error(f"Forward reset error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backwards compatibility
@router.get("/lab/guidance/{symbol}")
def get_guidance_legacy(symbol: str):
    """Legacy endpoint - redirects to forward-reset."""
    return get_forward_reset(symbol)


# Module 5: Earnings Quality ✅
@router.get("/lab/quality/{symbol}")
def get_quality(symbol: str):
    """Assess earnings quality - cash vs accruals."""
    try:
        return QualityEngine.get_quality(symbol)
    except Exception as e:
        logger.error(f"Quality error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 6: Tone Delta ⚠️ (limited without transcripts)
@router.get("/lab/tone/{symbol}")
def get_tone(symbol: str):
    """Basic tone analysis from company description."""
    try:
        return ToneAnalyzer.get_tone(symbol)
    except Exception as e:
        logger.error(f"Tone error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 7: Analyst Revision Velocity ✅
@router.get("/lab/revisions/{symbol}")
def get_revisions(symbol: str):
    """Track analyst revision velocity."""
    try:
        return RevisionTracker.get_revisions(symbol)
    except Exception as e:
        logger.error(f"Revisions error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 8: Post-Earnings Analyst Reaction ✅
@router.get("/lab/reactions/{symbol}")
def get_reactions(symbol: str):
    """Analyze post-earnings analyst reactions."""
    try:
        return ReactionAnalyzer.get_reactions(symbol)
    except Exception as e:
        logger.error(f"Reactions error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 9: Target Price Distribution ✅
@router.get("/lab/targets/{symbol}")
def get_targets(symbol: str):
    """Analyze analyst target price distribution."""
    try:
        return TargetDistribution.get_targets(symbol)
    except Exception as e:
        logger.error(f"Targets error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 10: Institutional Holdings ⚠️ (45-day lag)
@router.get("/lab/institutional/{symbol}")
def get_institutional(symbol: str):
    """Track institutional holdings trends."""
    try:
        return InstitutionalTracker.get_institutional(symbol)
    except Exception as e:
        logger.error(f"Institutional error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 11: Ownership Threshold Alerts (renamed from Activist Alerts)
@router.get("/lab/ownership-alerts/{symbol}")
def get_ownership_alerts(symbol: str):
    """Monitor ownership crossing meaningful levels via SEC EDGAR."""
    try:
        return OwnershipAlerts.get_alerts(symbol)
    except Exception as e:
        logger.error(f"Ownership alerts error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backwards compatibility
@router.get("/lab/activist/{symbol}")
def get_activist_legacy(symbol: str):
    """Legacy endpoint - redirects to ownership-alerts."""
    return get_ownership_alerts(symbol)


# Module 12: Buyback Tracker ✅
@router.get("/lab/buyback/{symbol}")
def get_buyback(symbol: str):
    """Track buyback effectiveness."""
    try:
        return BuybackTracker.get_buyback(symbol)
    except Exception as e:
        logger.error(f"Buyback error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 13: Dividend Monitor ✅
@router.get("/lab/dividend/{symbol}")
def get_dividend(symbol: str):
    """Monitor dividend stability and cut risk."""
    try:
        return DividendMonitor.get_dividend(symbol)
    except Exception as e:
        logger.error(f"Dividend error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Module 14: Peer Comparison ✅
@router.get("/lab/peers/{symbol}")
def get_peers(symbol: str, peers: Optional[str] = Query(None, description="Comma-separated peer symbols")):
    """Compare earnings vs peers."""
    try:
        peer_list = peers.split(",") if peers else None
        return PeerComparator.get_peer_comparison(symbol, peer_list)
    except Exception as e:
        logger.error(f"Peers error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Full Analysis Endpoint
@router.get("/lab/full/{symbol}")
def get_full_analysis(symbol: str):
    """
    Get complete earnings lab analysis - 14 production-safe modules.
    
    Removed modules (no reliable free data):
    - Topic Emphasis
    - Revenue Concentration
    - Geographic Exposure
    - Debt Maturity
    """
    try:
        return earnings_lab_service.get_full_analysis(symbol)
    except Exception as e:
        logger.error(f"Full analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# REMOVED ENDPOINTS (return deprecation notice)
@router.get("/lab/topics/{symbol}")
def get_topics_removed(symbol: str):
    """REMOVED - No reliable free data source."""
    return {
        "status": "removed",
        "reason": "Topic analysis requires paid transcript feeds (Seeking Alpha)",
        "alternative": "Use /lab/tone for basic language analysis"
    }


@router.get("/lab/concentration/{symbol}")
def get_concentration_removed(symbol: str):
    """REMOVED - No reliable free data source."""
    return {
        "status": "removed", 
        "reason": "Customer concentration only exists in 10-K filings",
        "alternative": "Manual 10-K review required"
    }


@router.get("/lab/geographic/{symbol}")
def get_geographic_removed(symbol: str):
    """REMOVED - No reliable free data source."""
    return {
        "status": "removed",
        "reason": "Geographic segment data only exists in annual reports",
        "alternative": "Manual annual report review required"
    }


@router.get("/lab/debt/{symbol}")
def get_debt_removed(symbol: str):
    """REMOVED - No reliable free data source."""
    return {
        "status": "removed",
        "reason": "Debt maturity schedules only exist in 10-K footnotes",
        "alternative": "Manual 10-K review required"
    }

