"""
QUANT360 Screener API
=====================

8 endpoints for the screener tabs.
"""

from fastapi import APIRouter, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["QUANT360 Screener"])


@router.get("/tradeable-universe")
async def get_tradeable_universe(
    universe_key: str = Query("INDIA", description="Universe: INDIA or US"),
    window: int = Query(60, description="Lookback window in days"),
    min_dollar_volume: float = Query(0, description="Minimum dollar volume filter"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    liquidity_quality: Optional[str] = Query(None, description="Filter: Stable only"),
):
    """
    Tab 1: Tradeable Universe
    
    What can I safely trade without execution traps?
    Returns: Safe trade list, Caution names, Avoid list
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_tradeable_universe(
        universe_key=universe_key,
        window=window,
        min_dollar_volume=min_dollar_volume,
        sector=sector,
        liquidity_quality=liquidity_quality,
    )


@router.get("/trend-quality")
async def get_trend_quality(
    universe_key: str = Query("INDIA", description="Universe: INDIA or US"),
    window: int = Query(60, description="Lookback window"),
    trend_direction: Optional[str] = Query(None, description="up, down, or any"),
    min_strength: float = Query(0, description="Minimum trend strength"),
):
    """
    Tab 2: Trend Quality Engine
    
    Is this trend real or about to fail?
    Returns: Durable trends, Late stage, Fake trends
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_trend_quality(
        universe_key=universe_key,
        window=window,
        trend_direction=trend_direction,
        min_strength=min_strength,
    )


@router.get("/volatility")
async def get_volatility_control(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    vol_state: Optional[str] = Query(None, description="Filter by vol regime"),
):
    """
    Tab 3: Volatility & Range Control
    
    Is volatility helping or hurting me?
    Returns: Controlled, Expansion plays, Chaos zone
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_volatility_control(
        universe_key=universe_key,
        window=window,
        vol_state=vol_state,
    )


@router.get("/regime")
async def get_regime_context(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
):
    """
    Tab 4: Regime & Market Context
    
    Is the environment aligned with this trade?
    Returns: Tailwinds, Neutral, Headwinds
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_regime_context(
        universe_key=universe_key,
        window=window,
    )


@router.get("/liquidity")
async def get_liquidity_intelligence(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    fragility_threshold: Optional[float] = Query(None, description="Fragility filter"),
):
    """
    Tab 5: Liquidity Intelligence
    
    Where will liquidity disappear first?
    Returns: Stable, Deteriorating, Cliff candidates
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_liquidity_intelligence(
        universe_key=universe_key,
        window=window,
        fragility_threshold=fragility_threshold,
    )


@router.get("/rotation")
async def get_relative_rotation(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(20, description="RS lookback window"),
):
    """
    Tab 6: Relative Rotation & Leadership
    
    Who is leading, who is being distributed?
    Returns: True leaders, Weak leaders, Distribution
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_relative_rotation(
        universe_key=universe_key,
        window=window,
    )


@router.get("/events")
async def get_event_risk(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
):
    """
    Tab 7: Event & Timing Risk
    
    Should I stay away right now?
    Returns: Safe around events, High event risk
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_event_risk(
        universe_key=universe_key,
        window=window,
    )


@router.get("/stress")
async def get_stress_proximity(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    similarity_threshold: float = Query(0.5, description="Crisis similarity threshold"),
):
    """
    Tab 8: Stress & Crisis Proximity
    
    Does this look like past crashes?
    Returns: Normal, Stress-like, Crisis-like
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_stress_proximity(
        universe_key=universe_key,
        window=window,
        similarity_threshold=similarity_threshold,
    )


@router.get("/summary")
async def get_screener_summary(
    universe_key: str = Query("INDIA", description="Universe"),
):
    """
    Quick summary across all tabs.
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    
    # Get quick data from tradeable universe
    result = await service.get_tradeable_universe(universe_key=universe_key)
    
    return {
        "universe": universe_key,
        "names_scanned": result["meta"]["names_scanned"],
        "names_passed": result["meta"]["names_passed"],
        "safe_count": result["quick_stats"]["total_safe"],
        "caution_count": result["quick_stats"]["total_caution"],
        "avoid_count": result["quick_stats"]["total_avoid"],
        "median_dollar_volume": result["quick_stats"]["median_dollar_volume"],
        "median_atr_pct": result["quick_stats"]["median_atr_pct"],
    }
