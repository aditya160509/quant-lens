"""
Liquidity Intelligence Engine API
=================================

REST API for the Liquidity Intelligence Engine.

Endpoints:
- GET /api/liquidity/state-manifold - 3D liquidity state coordinates
- GET /api/liquidity/cliff-vacuum - Cliff detection & vacuum probabilities
- GET /api/liquidity/contagion - Transmission network & patient zero
- GET /api/liquidity/capacity - Absorption thresholds & size limits
- GET /api/liquidity/regimes - Regime classification & transitions
- GET /api/liquidity/feedback - Vol-liquidity feedback loops
- GET /api/liquidity/fingerprint - Crisis signature matching
- GET /api/liquidity/diagnostics - Data quality & health
- GET /api/liquidity/summary - High-level dashboard data
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import pandas as pd
import numpy as np
from scipy import stats
from fastapi.concurrency import run_in_threadpool

from app.services.market_state_v2 import get_market_state
from app.services.liquidity_engine import (
    LiquidityIntelligenceEngine,
    compute_amihud,
    compute_returns,
    compute_dollar_volume,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/liquidity", tags=["Liquidity Intelligence"])


# =============================================================================
# REQUEST MODELS
# =============================================================================

class LiquidityRequest(BaseModel):
    """Base request for liquidity analysis."""
    universe_key: str = "INDIA"
    window: int = 60
    lookback_days: int = 252
    force_rebuild: bool = False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _get_engine_data(
    universe_key: str,
    window: int,
    lookback_days: int,
    force_rebuild: bool = False,
) -> Dict[str, Any]:
    """
    Build market state and run liquidity engine.
    """
    # Get market state
    market_state = await get_market_state(
        universe_key=universe_key,
        lookback_days=lookback_days,
        force_rebuild=force_rebuild,
    )
    
    if not market_state.is_built:
        raise HTTPException(
            status_code=500,
            detail=f"Market state build failed: {market_state._build_error}"
        )
    
    # AUDIT FIX: Synchronous Math Deadlocking
    # Offload the heavy loop and matrix math to a threadpool
    def _heavy_compute(tickers, prices, volumes, ohlc, sector_map):
        engine = LiquidityIntelligenceEngine(window=window)
        amihud_dict = {}
        for ticker in tickers:
            try:
                close = prices[ticker].dropna()
                volume = volumes[ticker].dropna() if ticker in volumes.columns else pd.Series()
                if len(close) < 30 or len(volume) < 30: continue
                
                if ohlc is not None and ticker in ohlc.open.columns:
                    open_prices = ohlc.open[ticker].reindex(close.index).fillna(close)
                    high = ohlc.high[ticker].reindex(close.index).fillna(close)
                    low = ohlc.low[ticker].reindex(close.index).fillna(close)
                else:
                    returns = close.pct_change().abs()
                    daily_range = returns.rolling(20).mean().fillna(0.01)
                    open_prices = close.shift(1).fillna(close.iloc[0])
                    high = close * (1 + daily_range)
                    low = close * (1 - daily_range)
                
                ticker_sector = sector_map.get(ticker, "Other")
                engine.process_ticker(ticker, close, volume, open_prices, high, low, ticker_sector)
                
                returns = compute_returns(close)
                dollar_volume = compute_dollar_volume(close, volume)
                amihud = compute_amihud(returns, dollar_volume).replace([np.inf, -np.inf], np.nan).dropna()
                if len(amihud) > 20: amihud_dict[ticker] = amihud
            except Exception as e:
                logger.warning(f"Failed to process {ticker}: {e}")
                continue
        
        if len(amihud_dict) > 5:
            try:
                engine.compute_contagion_network(amihud_dict)
            except Exception as e:
                logger.warning(f"Contagion computation failed: {e}")
        return engine

    # Run heavy compute in a separate thread to avoid blocking the event loop
    engine = await run_in_threadpool(_heavy_compute, tickers, prices, volumes, ohlc, sector_map)
    
    return {
        "engine": engine,
        "market_state": market_state,
        "tickers": list(engine._liquidity_metrics.keys()),
    }


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/state-manifold")
async def get_state_manifold(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 1: Liquidity State Manifold
    
    Returns 3D coordinates for each ticker in liquidity space.
    - X: Stability dimension
    - Y: Depth dimension  
    - Z: Responsiveness dimension
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        manifold_data = engine.get_manifold_data()
        
        # Add liquidity metrics to response
        ticker_states = [
            m.to_dict() for m in engine._liquidity_metrics.values()
        ]
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "manifold_coordinates": manifold_data["coordinates"],
            "phase_distribution": manifold_data.get("phase_distribution", {}),
            "sector_stats": manifold_data.get("sector_stats", {}),
            "drift_paths": manifold_data.get("drift_paths", {}),
            "ticker_states": ticker_states,
            "summary": engine.get_summary()["summary"],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"State manifold failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cliff-vacuum")
async def get_cliff_vacuum(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 2: Cliff & Vacuum Detection
    
    Returns cliff proximity and vacuum probability for each ticker.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        cliff_data = [
            m.to_dict() for m in engine._cliff_metrics.values()
        ]
        
        # Sort by cliff distance (closest to cliff first)
        cliff_data.sort(key=lambda x: x["cliff_distance"], reverse=True)
        
        # Identify high-risk names
        vacuum_candidates = [
            c for c in cliff_data if c["vacuum_probability"] > 0.3
        ]
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "cliff_metrics": cliff_data,
            "vacuum_candidates": vacuum_candidates,
            "summary": {
                "avg_cliff_distance": np.mean([c["cliff_distance"] for c in cliff_data]),
                "avg_vacuum_probability": np.mean([c["vacuum_probability"] for c in cliff_data]),
                "high_risk_count": len(vacuum_candidates),
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cliff-vacuum failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/contagion")
async def get_contagion(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 3: Contagion & Transmission Network
    
    Returns transmission graph with patient zero probabilities.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        contagion_data = [
            m.to_dict() for m in engine._contagion_metrics.values()
        ]
        
        # Build network
        nodes = []
        for m in engine._contagion_metrics.values():
            nodes.append({
                "id": m.ticker,
                "r_number": m.r_number,
                "patient_zero_prob": m.patient_zero_prob,
                "firebreak_score": m.firebreak_score,
                "in_degree": m.in_degree,
                "out_degree": m.out_degree,
            })
        
        edges = []
        if engine._strength_matrix is not None:
            for i in engine._strength_matrix.index:
                for j in engine._strength_matrix.columns:
                    strength = engine._strength_matrix.loc[i, j]
                    if i != j and strength != 0:
                        edges.append({
                            "source": i,
                            "target": j,
                            "strength": round(float(strength), 4),
                            "lag": int(engine._lag_matrix.loc[i, j]) if engine._lag_matrix is not None else 0,
                        })
        
        # Identify super-spreaders and patient zeros
        super_spreaders = [c for c in contagion_data if c["r_number"] > 3]
        patient_zeros = sorted(contagion_data, key=lambda x: x["patient_zero_prob"], reverse=True)[:5]
        firebreaks = sorted(contagion_data, key=lambda x: x["firebreak_score"], reverse=True)[:5]
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "network": {
                "nodes": nodes,
                "edges": edges[:200],  # Limit edges
            },
            "super_spreaders": super_spreaders,
            "patient_zeros": patient_zeros,
            "firebreaks": firebreaks,
            "summary": {
                "avg_r_number": np.mean([c["r_number"] for c in contagion_data]) if contagion_data else 0,
                "total_edges": len(edges),
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contagion failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/capacity")
async def get_capacity(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 4: Absorption & Capacity
    
    Returns liquidity capacity thresholds for each ticker.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        capacity_data = [
            m.to_dict() for m in engine._capacity_metrics.values()
        ]
        
        # Add percentile rankings
        safe_sizes = [c["safe_size_dollars"] for c in capacity_data if c["safe_size_dollars"] > 0]
        if safe_sizes:
            for c in capacity_data:
                if c["safe_size_dollars"] > 0:
                    c["capacity_percentile"] = round(
                        stats.percentileofscore(safe_sizes, c["safe_size_dollars"]), 1
                    )
        
        # Sort by capacity
        capacity_data.sort(key=lambda x: x.get("capacity_percentile", 50), reverse=True)
        
        # Identify low capacity names
        low_capacity = [c for c in capacity_data if c.get("capacity_percentile", 50) < 25]
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "capacity_metrics": capacity_data,
            "low_capacity_names": low_capacity,
            "summary": {
                "median_safe_size": np.median(safe_sizes) if safe_sizes else 0,
                "avg_impact_slope": np.mean([c["impact_slope"] for c in capacity_data]),
                "low_capacity_count": len(low_capacity),
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Capacity failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/regimes")
async def get_regimes(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 5: Regime Transition Engine
    
    Returns current regime and transition probabilities.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        regime_data = [
            m.to_dict() for m in engine._regime_states.values()
        ]
        
        # Regime distribution
        regimes = [r["current_regime"] for r in regime_data]
        regime_dist = {r: regimes.count(r) / len(regimes) for r in set(regimes)}
        
        # High transition risk
        high_risk = [r for r in regime_data if r["transition_risk"] > 0.5]
        high_risk.sort(key=lambda x: x["transition_risk"], reverse=True)
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "regime_states": regime_data,
            "regime_distribution": regime_dist,
            "high_transition_risk": high_risk[:10],
            "summary": {
                "avg_transition_risk": np.mean([r["transition_risk"] for r in regime_data]),
                "modal_regime": max(regime_dist, key=regime_dist.get) if regime_dist else "normal",
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regimes failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/feedback")
async def get_feedback(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    System 6: Volatility-Liquidity Feedback
    
    Returns feedback loop metrics and stability status.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        feedback_data = [
            m.to_dict() for m in engine._feedback_metrics.values()
        ]
        
        # Sort by loop gain
        feedback_data.sort(key=lambda x: x["loop_gain"], reverse=True)
        
        # Identify unstable names
        unstable = [f for f in feedback_data if f["stability_status"] == "unstable"]
        amplifying = [f for f in feedback_data if f["stability_status"] == "amplifying"]
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "feedback_metrics": feedback_data,
            "unstable_names": unstable,
            "amplifying_names": amplifying[:10],
            "summary": {
                "avg_loop_gain": np.mean([f["loop_gain"] for f in feedback_data]),
                "unstable_count": len(unstable),
                "amplifying_count": len(amplifying),
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/fingerprint")
async def get_fingerprint(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
    top_k: int = Query(5),
):
    """
    System 7: Crisis Fingerprint Vault
    
    Compares current conditions to historical crises.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        crisis_data = engine.get_crisis_comparison()
        
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "current_fingerprint": crisis_data["current_fingerprint"],
            "fingerprint_labels": ["Instability", "Depth", "Fragility", "Contagion", "Feedback"],
            "similar_crises": crisis_data["similar_crises"][:top_k],
            "summary": {
                "closest_match": crisis_data["similar_crises"][0]["name"] if crisis_data["similar_crises"] else "None",
                "similarity_score": crisis_data["similar_crises"][0]["similarity"] if crisis_data["similar_crises"] else 0,
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fingerprint failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/diagnostics")
async def get_diagnostics(
    universe_key: str = Query("INDIA"),
):
    """
    Data quality and diagnostic information.
    """
    try:
        from app.services.market_state_v2 import get_cache_status
        
        cache_status = get_cache_status()
        
        return {
            "success": True,
            "universe_key": universe_key,
            "cache_status": cache_status,
            "available_universes": ["INDIA", "US", "ETF", "MACRO"],
            "available_windows": [5, 20, 60, 252],
        }
        
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary")
async def get_summary(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """
    High-level dashboard summary of all systems.
    """
    try:
        data = await _get_engine_data(universe_key, window, lookback_days)
        engine = data["engine"]
        
        summary = engine.get_summary()
        crisis_data = engine.get_crisis_comparison()
        
        # Build comprehensive summary
        return {
            "success": True,
            "universe_key": universe_key,
            "window": window,
            "as_of": summary["as_of"],
            "universe_size": summary["universe_size"],
            "liquidity_summary": summary["summary"],
            "sector_breakdown": summary.get("sector_breakdown", {}),
            "crisis_match": {
                "closest": crisis_data["similar_crises"][0] if crisis_data["similar_crises"] else None,
            },
            "alerts": [],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "liquidity_intelligence"}


# Note: scipy.stats already imported at top of file
