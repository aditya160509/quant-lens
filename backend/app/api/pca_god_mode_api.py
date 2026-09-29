"""
PCA God Mode Omega - API Endpoints
==================================

RESTful API for PCA God Mode analysis.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import pandas as pd
import numpy as np

from app.services.pca_god_mode import (
    PCAConfig,
    PCAGodModeEngine,
    run_pca_god_mode,
    get_available_universes,
    UNIVERSE_PRESETS
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pca/godmode", tags=["PCA God Mode"])

def clean_for_json(obj):
    """Clean data for JSON serialization (handles NaN, Infinity, NumPy types)."""
    if obj is None: return None
    if isinstance(obj, dict): return {str(k): clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, pd.Series, np.ndarray)):
        items = obj.tolist() if hasattr(obj, "tolist") else list(obj)
        return [clean_for_json(x) for x in items]
    if isinstance(obj, pd.DataFrame): return obj.to_dict(orient="records")
    if isinstance(obj, (float, np.floating)):
        return 0.0 if np.isnan(obj) or np.isinf(obj) else float(obj)
    if isinstance(obj, (int, np.integer)): return int(obj)
    return str(obj) if hasattr(obj, "isoformat") else obj

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class PCAGodModeRequest(BaseModel):
    universe_key: str = Field(default="US_SP500_TOP50", description="Universe preset key")
    custom_tickers: Optional[List[str]] = Field(default=None, description="Custom ticker list")
    lookback_days: int = Field(default=252, ge=60, le=2520, description="Lookback in days")
    min_history_days: int = Field(default=100, ge=30, description="Minimum history required (lowered for intl markets)")
    max_missing_pct: float = Field(default=0.10, ge=0, le=0.3, description="Max missing data tolerance")
    return_type: str = Field(default="log", pattern="^(simple|log)$")
    normalization: str = Field(default="zscore", pattern="^(none|zscore|minmax)$")
    matrix_type: str = Field(default="correlation", pattern="^(correlation|covariance)$")
    rolling_enabled: bool = Field(default=False, description="Enable rolling PCA (slower but shows stability)")
    rolling_window: int = Field(default=126, ge=60, description="Rolling window size")
    rolling_step: int = Field(default=42, ge=5, description="Rolling step size")


class ShockRequest(BaseModel):
    universe_key: str = Field(default="US_SP500_TOP50")
    lookback_days: int = Field(default=252)
    shock_config: Dict[int, float] = Field(
        default={1: 2.0},
        description="Shock config: {pc_index: magnitude}"
    )


# =============================================================================
# CACHE FOR COMPUTED ENGINES
# =============================================================================

_engine_cache: Dict[str, PCAGodModeEngine] = {}
MAX_CACHE_SIZE = 5


def _get_cache_key(config: PCAConfig) -> str:
    """Generate cache key from config"""
    tickers_str = ",".join(sorted(config.custom_tickers or []))
    return f"{config.universe_key}_{config.lookback_days}_{config.matrix_type}_{hash(tickers_str)}"


def _get_or_compute_engine(config: PCAConfig, force: bool = False) -> PCAGodModeEngine:
    """Get cached engine or compute new one"""
    cache_key = _get_cache_key(config)
    
    if not force and cache_key in _engine_cache:
        logger.info(f"[PCA GodMode API] Cache hit: {cache_key[:20]}")
        return _engine_cache[cache_key]
    
    # Compute new engine
    engine = PCAGodModeEngine(config)
    if not engine.compute():
        raise HTTPException(status_code=500, detail="PCA computation failed")
    
    # Cache management
    if len(_engine_cache) >= MAX_CACHE_SIZE:
        oldest_key = next(iter(_engine_cache))
        del _engine_cache[oldest_key]
    
    _engine_cache[cache_key] = engine
    logger.info(f"[PCA GodMode API] Computed and cached: {cache_key[:20]}")
    return engine


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/universes")
async def list_universes():
    """Get list of available universe presets"""
    return {
        "universes": get_available_universes(),
        "regions": ["india", "us", "europe", "japan", "global", "custom"]
    }


@router.get("/universe/{universe_key}")
async def get_universe_detail(universe_key: str):
    """Get details of a specific universe"""
    preset = UNIVERSE_PRESETS.get(universe_key)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Universe not found: {universe_key}")
    
    return {
        "key": universe_key,
        "name": preset["name"],
        "region": preset["region"].value,
        "tickers": preset["tickers"],
        "sector_map": preset.get("sector_map", {})
    }


@router.post("/run")
async def run_full_analysis(request: PCAGodModeRequest):
    """
    Run complete PCA God Mode analysis.
    
    Returns data for all 6 tabs.
    """
    try:
        config = PCAConfig(
            universe_key=request.universe_key,
            custom_tickers=request.custom_tickers,
            lookback_days=request.lookback_days,
            min_history_days=request.min_history_days,
            max_missing_pct=request.max_missing_pct,
            return_type=request.return_type,
            normalization=request.normalization,
            matrix_type=request.matrix_type,
            rolling_enabled=request.rolling_enabled,
            rolling_window=request.rolling_window,
            rolling_step=request.rolling_step
        )
        
        engine = _get_or_compute_engine(config)
        
        # Get all data
        from dataclasses import asdict
        
        return clean_for_json({
            "success": True,
            "metadata": engine.get_governance_metadata(),
            "structure": asdict(engine.get_structure_metrics()),
            "factors": [asdict(f) for f in engine.get_factor_meanings()],
            "factor_returns": engine.get_factor_returns(),
            "stability": [asdict(s) for s in engine.get_stability_metrics()],
            "loading_drift": engine.get_loading_drift_heatmap(),
            "pc_dominance": engine.get_pc_dominance_history(),
            "projections": engine.get_asset_projections(),
            "diversifiers": [asdict(d) for d in engine.get_diversifier_scores()],
            "redundant_pairs": engine.get_redundant_pairs(),
            "breaks": [asdict(b) for b in engine.detect_structural_breaks()]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[PCA GodMode API] Run failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/structure")
async def get_structure_overview(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252)
):
    """
    TAB 1: Structure Overview
    
    Returns explained variance, ENB, concentration metrics.
    """
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        from dataclasses import asdict
        return {
            "tab": "structure_overview",
            "data": asdict(engine.get_structure_metrics()),
            "quality": asdict(engine._quality) if engine._quality else None
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Structure failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/factors")
async def get_factors_meaning(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252),
    num_pcs: int = Query(default=10, ge=1, le=20)
):
    """
    TAB 2: Factors & Meaning
    
    Returns factor interpretations and loadings.
    """
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        from dataclasses import asdict
        return {
            "tab": "factors_meaning",
            "factors": [asdict(f) for f in engine.get_factor_meanings(num_pcs)]
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Factors failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/factors/{pc_index}/loadings")
async def get_pc_loadings(
    pc_index: int,
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252)
):
    """Get full loadings table for a specific PC"""
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        return {
            "pc_index": pc_index,
            "loadings": engine.get_loadings_table(pc_index)
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Loadings failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stability")
async def get_stability_analysis(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252),
    num_pcs: int = Query(default=5, ge=1, le=10)
):
    """
    TAB 3: Factor Behavior & Stability
    
    Returns factor returns, volatility, and stability metrics.
    """
    try:
        config = PCAConfig(
            universe_key=universe_key,
            lookback_days=lookback_days,
            rolling_enabled=True
        )
        engine = _get_or_compute_engine(config)
        
        from dataclasses import asdict
        return {
            "tab": "stability",
            "factor_returns": engine.get_factor_returns(num_pcs),
            "stability_metrics": [asdict(s) for s in engine.get_stability_metrics(num_pcs)],
            "loading_drift": engine.get_loading_drift_heatmap(num_pcs),
            "pc_dominance": engine.get_pc_dominance_history()
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Stability failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/loading-drift")
async def get_loading_drift(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=504),  # 2 years for good drift analysis
    num_pcs: int = Query(default=5, ge=1, le=10)
):
    """
    Get loading drift heatmap data showing how loadings change over time.
    """
    try:
        config = PCAConfig(
            universe_key=universe_key,
            lookback_days=lookback_days,
            rolling_enabled=True,
            rolling_window=252,
            rolling_step=21
        )
        engine = _get_or_compute_engine(config)
        
        return {
            "tab": "loading_drift",
            "data": engine.get_loading_drift_heatmap(num_pcs)
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Loading drift failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/redundancy")
async def get_redundancy_analysis(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252),
    k_components: int = Query(default=5, ge=2, le=10),
    similarity_threshold: float = Query(default=0.85, ge=0.5, le=0.99)
):
    """
    TAB 4: Structure Map & Redundancy
    
    Returns asset projections, diversifier scores, and redundant pairs.
    """
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        from dataclasses import asdict
        return {
            "tab": "redundancy",
            "projections": engine.get_asset_projections(),
            "diversifiers": [asdict(d) for d in engine.get_diversifier_scores(k_components)],
            "redundant_pairs": engine.get_redundant_pairs(similarity_threshold)
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Redundancy failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shock")
async def simulate_shock(request: ShockRequest):
    """
    TAB 5: Systemic Risk & Shocks
    
    Simulate shock to principal components.
    """
    try:
        config = PCAConfig(
            universe_key=request.universe_key,
            lookback_days=request.lookback_days
        )
        engine = _get_or_compute_engine(config)
        
        result = engine.simulate_shock(request.shock_config)
        return {
            "tab": "shocks",
            "simulation": result
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Shock failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/breaks")
async def get_structural_breaks(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=504)  # 2 years for break detection
):
    """
    TAB 5: Structural Break Detection
    
    Returns detected structural breaks from rolling analysis.
    """
    try:
        config = PCAConfig(
            universe_key=universe_key,
            lookback_days=lookback_days,
            rolling_enabled=True,
            rolling_window=252,
            rolling_step=21
        )
        engine = _get_or_compute_engine(config)
        
        from dataclasses import asdict
        return {
            "tab": "breaks",
            "breaks": [asdict(b) for b in engine.detect_structural_breaks()]
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Breaks failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/governance")
async def get_governance_metadata(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252)
):
    """
    TAB 6: Governance & Export metadata
    
    Returns configuration hash, quality metrics, and audit trail.
    """
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        return {
            "tab": "governance",
            "metadata": engine.get_governance_metadata()
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Governance failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/export")
async def export_pca_data(
    universe_key: str = Query(default="US_SP500_TOP50"),
    lookback_days: int = Query(default=252),
    formats: List[str] = Query(default=["eigenvalues", "loadings"])
):
    """
    TAB 6: Export PCA data
    
    Available formats: eigenvalues, loadings, factor_returns, stability, diversifiers
    """
    try:
        config = PCAConfig(universe_key=universe_key, lookback_days=lookback_days)
        engine = _get_or_compute_engine(config)
        
        return {
            "tab": "export",
            "data": engine.export_data(formats),
            "metadata": engine.get_governance_metadata()
        }
        
    except Exception as e:
        logger.exception("[PCA GodMode API] Export failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cache-status")
async def get_cache_status():
    """Get current API cache status"""
    return {
        "cached_engines": len(_engine_cache),
        "max_cache_size": MAX_CACHE_SIZE,
        "cached_keys": list(_engine_cache.keys())[:10]  # Only show first 10
    }


@router.delete("/cache")
async def clear_cache():
    """Clear the engine cache"""
    global _engine_cache
    count = len(_engine_cache)
    _engine_cache = {}
    return {"cleared": count, "status": "ok"}
