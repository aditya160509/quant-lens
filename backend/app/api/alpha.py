"""
Alpha Models API
Endpoints for momentum, mean reversion, and intelligent alerts
"""

from fastapi import APIRouter, Query
from typing import List, Optional
from app.services import alpha_momentum, alpha_mean_reversion
from app.services.alerts import preview_alerts_for_symbol

router = APIRouter()


@router.get("/momentum")
def get_momentum(
    symbols: str = Query(..., description="Comma-separated list of tickers"),
    benchmark: str = Query("SPY", description="Benchmark ticker for relative strength")
):
    """
    Get cross-sectional momentum scores for a list of symbols.
    
    Returns z-score normalized metrics and composite score 0-100.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    return alpha_momentum.compute_momentum_score(symbol_list, benchmark)


@router.get("/mean_reversion")
def get_mean_reversion(
    symbols: str = Query(..., description="Comma-separated list of tickers"),
    sensitivity: str = Query("conservative", description="conservative or aggressive")
):
    """
    Get mean reversion scores with confidence gating.
    
    Sensitivity modes:
    - conservative: Longer lookbacks (20/50 MA), stricter confidence
    - aggressive: Shorter lookbacks (10/20 MA), looser confidence
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    return alpha_mean_reversion.compute_mean_reversion(symbol_list, sensitivity)


@router.get("/alerts/preview")
def get_alert_preview(
    symbol: str = Query(..., description="Ticker symbol")
):
    """
    Generate intelligent alert suggestions for a symbol.
    
    Returns a preview of actionable alerts based on:
    - Current price levels
    - Momentum scores
    - Mean reversion signals
    - Earnings proximity
    
    Alerts are sorted by severity (high > medium > low).
    """
    return preview_alerts_for_symbol(symbol.upper())

