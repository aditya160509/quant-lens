"""
PCA Eigenphysics API Endpoints
==============================

Unified API for the PCA Eigenphysics system.

Endpoints:
- POST /api/pca/eigenphysics/run - Full PCA analysis with all 12 features
- GET /api/pca/eigenphysics/state - Get cached PCA state
- GET /api/pca/eigenphysics/feature/{name} - Get single feature
- POST /api/pca/eigenphysics/shock - Run shock simulation

All responses include provenance tracking.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import numpy as np

from app.services.market_state_v2 import (
    get_market_state,
    MarketStateV2,
    get_cache_status,
)
from app.services.pca_state_engine import (
    PCAState,
    PCAStateBuilder,
    compute_pca_state,
)
from app.services.pca_features import (
    FeatureOutput,
    compute_collapse_gauge,
    compute_rotation_radar,
    compute_decoherence_index,
    compute_tail_shift,
    compute_reconstruction_failure,
    compute_liquidity_illusion,
    compute_forced_unwind_surface,
    compute_shock_transmission,
    compute_eigen_topology,
    compute_instability_engine,
    compute_degrees_of_freedom,
    compute_crisis_signature_match,
    compute_governor_score,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pca/eigenphysics", tags=["PCA Eigenphysics"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class PCARunRequest(BaseModel):
    """Request for full PCA analysis."""
    universe_key: str = "INDIA"
    lookback_days: int = 252
    windows: List[int] = [60]  # Default to single window for efficiency
    include_all_features: bool = True  # Include all 12 features
    force_rebuild: bool = False


class ShockRequest(BaseModel):
    """Request for shock simulation."""
    universe_key: str = "INDIA"
    window: int = 60
    shocks: Dict[int, float]  # {pc_index: magnitude}


# =============================================================================
# CRISIS LIBRARY
# =============================================================================

CRISIS_LIBRARY = [
    {"name": "Global Financial Crisis", "date_start": "2008-09-15", "date_end": "2009-03-09",
     "region": "global", "fingerprint": [0.45, 0.35, 0.15, 0.75, 0.8]},
    {"name": "COVID-19 Crash", "date_start": "2020-02-19", "date_end": "2020-03-23",
     "region": "global", "fingerprint": [0.52, 0.30, 0.12, 0.78, 0.9]},
    {"name": "2022 Rate Shock", "date_start": "2022-01-03", "date_end": "2022-06-16",
     "region": "global", "fingerprint": [0.38, 0.50, 0.22, 0.62, 0.4]},
    {"name": "Demonetization India", "date_start": "2016-11-08", "date_end": "2016-12-30",
     "region": "india", "fingerprint": [0.40, 0.45, 0.20, 0.65, 0.5]},
    {"name": "NBFC Crisis India", "date_start": "2018-09-21", "date_end": "2019-01-31",
     "region": "india", "fingerprint": [0.42, 0.42, 0.18, 0.68, 0.6]},
]

ALL_FEATURES = [
    "collapse_gauge", "rotation_radar", "decoherence_index", "tail_shift",
    "reconstruction_failure", "liquidity_illusion", "forced_unwind_surface",
    "eigen_topology", "instability_engine", "degrees_of_freedom", 
    "crisis_signature", "governor_score",
]


# =============================================================================
# EFFICIENT FEATURE COMPUTATION
# =============================================================================

def compute_all_features(
    pca_state: PCAState,
    market_state: MarketStateV2,
) -> Dict[str, Any]:
    """
    Compute all 12 PCA features efficiently in a single pass.
    Handles errors gracefully - returns partial results if some features fail.
    """
    features = {}
    
    try:
        # FEATURE 1: Collapse Gauge (always computed first)
        features["collapse_gauge"] = compute_collapse_gauge(pca_state)
    except Exception as e:
        logger.warning(f"collapse_gauge failed: {e}")
        features["collapse_gauge"] = _error_feature("collapse_gauge", str(e))
    
    try:
        # FEATURE 2: Rotation Radar (no prior state available)
        features["rotation_radar"] = compute_rotation_radar(pca_state, prior_state=None)
    except Exception as e:
        logger.warning(f"rotation_radar failed: {e}")
        features["rotation_radar"] = _error_feature("rotation_radar", str(e))
    
    try:
        # FEATURE 3: Decoherence Index
        features["decoherence_index"] = compute_decoherence_index(
            pca_state, market_state.returns, pca_state.window_days
        )
    except Exception as e:
        logger.warning(f"decoherence_index failed: {e}")
        features["decoherence_index"] = _error_feature("decoherence_index", str(e))
    
    try:
        # FEATURE 4: Tail Shift
        features["tail_shift"] = compute_tail_shift(
            market_state.returns, pca_state.window_days
        )
    except Exception as e:
        logger.warning(f"tail_shift failed: {e}")
        features["tail_shift"] = _error_feature("tail_shift", str(e))
    
    try:
        # FEATURE 5: Reconstruction Failure
        features["reconstruction_failure"] = compute_reconstruction_failure(
            pca_state, market_state.returns
        )
    except Exception as e:
        logger.warning(f"reconstruction_failure failed: {e}")
        features["reconstruction_failure"] = _error_feature("reconstruction_failure", str(e))
    
    try:
        # FEATURE 6: Liquidity Illusion Index
        features["liquidity_illusion"] = compute_liquidity_illusion(
            pca_state, market_state.returns, market_state.dollar_volume
        )
    except Exception as e:
        logger.warning(f"liquidity_illusion failed: {e}")
        features["liquidity_illusion"] = _error_feature("liquidity_illusion", str(e))
    
    try:
        # FEATURE 7: Forced Unwind Surface
        features["forced_unwind_surface"] = compute_forced_unwind_surface(
            pca_state, market_state.returns, market_state.dollar_volume
        )
    except Exception as e:
        logger.warning(f"forced_unwind_surface failed: {e}")
        features["forced_unwind_surface"] = _error_feature("forced_unwind_surface", str(e))
    
    try:
        # FEATURE 9: Eigen Topology (skip heavy computation for now - simplified)
        features["eigen_topology"] = _compute_topology_simplified(pca_state)
    except Exception as e:
        logger.warning(f"eigen_topology failed: {e}")
        features["eigen_topology"] = _error_feature("eigen_topology", str(e))
    
    try:
        # FEATURE 11: Degrees of Freedom
        features["degrees_of_freedom"] = compute_degrees_of_freedom(pca_state)
    except Exception as e:
        logger.warning(f"degrees_of_freedom failed: {e}")
        features["degrees_of_freedom"] = _error_feature("degrees_of_freedom", str(e))
    
    try:
        # FEATURE 12: Crisis Signature
        features["crisis_signature"] = compute_crisis_signature_match(
            pca_state, CRISIS_LIBRARY
        )
    except Exception as e:
        logger.warning(f"crisis_signature failed: {e}")
        features["crisis_signature"] = _error_feature("crisis_signature", str(e))
    
    try:
        # FEATURE 10: Instability Engine (depends on other features)
        features["instability_engine"] = compute_instability_engine(features, pca_state)
    except Exception as e:
        logger.warning(f"instability_engine failed: {e}")
        features["instability_engine"] = _error_feature("instability_engine", str(e))
    
    try:
        # Governor Score (meta-feature, depends on instability engine)
        features["governor_score"] = compute_governor_score(pca_state, features)
    except Exception as e:
        logger.warning(f"governor_score failed: {e}")
        features["governor_score"] = _error_feature("governor_score", str(e))
    
    return features


def _compute_topology_simplified(state: PCAState) -> FeatureOutput:
    """Simplified topology computation without heavy O(N²) loops."""
    loadings = state.eigenvectors[:, :min(4, state.K)]
    N = len(state.tickers)
    
    # Compute PC1 loading-based clustering
    pc1_loadings = loadings[:, 0]
    pc1_abs = np.abs(pc1_loadings)
    
    # Simple clustering by PC1 loading sign and magnitude
    positive_mask = pc1_loadings >= 0
    n_positive = np.sum(positive_mask)
    n_negative = N - n_positive
    
    # Estimate network properties
    avg_degree = min(N - 1, 5 + int(N * 0.1))  # Heuristic
    density = 2 * avg_degree / N if N > 1 else 0
    
    # Top connected nodes (highest PC1 loading)
    top_idx = np.argsort(pc1_abs)[-10:][::-1]
    nodes = [
        {"id": state.tickers[i], "degree": avg_degree, "cluster": 0 if pc1_loadings[i] >= 0 else 1,
         "pc1_loading": round(float(pc1_loadings[i]), 4)}
        for i in top_idx
    ]
    
    return FeatureOutput(
        feature_name="eigen_topology",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "n_nodes": N,
            "n_edges": int(N * avg_degree / 2),
            "n_clusters": 2,
            "avg_degree": round(avg_degree, 2),
            "max_degree": avg_degree + 2,
            "density": round(density, 4),
            "nodes": nodes,
            "edges": [],  # Skip edges for efficiency
        },
        cursor={"clusters": "2", "density": f"{density:.1%}"},
    )


def _error_feature(name: str, error: str) -> Dict[str, Any]:
    """Create error response for failed feature."""
    return {
        "feature_name": name,
        "error": error,
        "values": {},
    }


def _feature_to_dict(f) -> Dict[str, Any]:
    """Convert FeatureOutput to dict safely."""
    if hasattr(f, 'to_dict'):
        return f.to_dict()
    elif isinstance(f, dict):
        return f
    return {"error": "unknown_format"}


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/run")
async def run_pca_eigenphysics(req: PCARunRequest):
    """
    Run full PCA Eigenphysics analysis with all 12 features.
    
    Returns PCA states and all features for requested windows.
    Optimized for efficiency - single window by default.
    """
    try:
        # Get market state
        market_state = await get_market_state(
            universe_key=req.universe_key,
            lookback_days=req.lookback_days,
            force_rebuild=req.force_rebuild,
        )
        
        if not market_state.is_built:
            raise HTTPException(status_code=500, detail=f"Market state build failed: {market_state._build_error}")
        
        results = {}
        
        for window in req.windows:
            try:
                # Build PCA state
                pca_builder = PCAStateBuilder()
                states = await pca_builder.build_from_market_state(market_state, windows=(window,))
                
                if window not in states:
                    results[f"window_{window}"] = {"error": f"PCA build failed for window {window}"}
                    continue
                
                pca_state = states[window]
                
                # Compute all features
                if req.include_all_features:
                    features = compute_all_features(pca_state, market_state)
                else:
                    # Minimal features only
                    features = {
                        "collapse_gauge": compute_collapse_gauge(pca_state),
                        "degrees_of_freedom": compute_degrees_of_freedom(pca_state),
                        "governor_score": compute_governor_score(pca_state, {}),
                    }
                
                results[f"window_{window}"] = {
                    "pca_state": pca_state.to_dict(),
                    "features": {k: _feature_to_dict(v) for k, v in features.items()},
                }
                
            except Exception as e:
                logger.error(f"Window {window} failed: {e}")
                results[f"window_{window}"] = {"error": str(e)}
        
        # Extract governor score for top-level display
        primary_window = req.windows[0]
        primary_key = f"window_{primary_window}"
        governor_score = None
        
        if primary_key in results and "features" in results[primary_key]:
            gs = results[primary_key]["features"].get("governor_score")
            if gs and "values" in gs:
                governor_score = {
                    "score": gs["values"].get("score"),
                    "state": gs["values"].get("state"),
                    "color": gs["values"].get("color"),
                }
        
        return {
            "success": True,
            "universe_key": req.universe_key,
            "governor_score": governor_score,
            "results": results,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PCA Eigenphysics run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state")
async def get_pca_state(
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """Get cached or fresh PCA state."""
    try:
        market_state = await get_market_state(universe_key=universe_key, lookback_days=lookback_days)
        
        if not market_state.is_built:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        pca_state = await compute_pca_state(market_state, window=window)
        
        if pca_state is None:
            raise HTTPException(status_code=500, detail="PCA computation failed")
        
        return {
            "success": True,
            "pca_state": pca_state.to_dict(),
            "market_state_summary": market_state.to_summary(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get PCA state failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature/{feature_name}")
async def get_pca_feature(
    feature_name: str,
    universe_key: str = Query("INDIA"),
    window: int = Query(60),
    lookback_days: int = Query(252),
):
    """Get a single PCA feature (lazy loading)."""
    if feature_name not in ALL_FEATURES:
        raise HTTPException(status_code=400, detail=f"Unknown feature: {feature_name}. Available: {ALL_FEATURES}")
    
    try:
        market_state = await get_market_state(universe_key=universe_key, lookback_days=lookback_days)
        
        if not market_state.is_built:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        pca_state = await compute_pca_state(market_state, window=window)
        
        if pca_state is None:
            raise HTTPException(status_code=500, detail="PCA computation failed")
        
        # Compute the requested feature
        features = compute_all_features(pca_state, market_state)
        feature = features.get(feature_name)
        
        if feature is None:
            raise HTTPException(status_code=500, detail=f"Feature {feature_name} failed")
        
        return {
            "success": True,
            "feature": _feature_to_dict(feature),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get feature {feature_name} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shock")
async def simulate_shock(req: ShockRequest):
    """
    Run shock transmission simulation.
    
    Shocks: {pc_index: magnitude} - Example: {1: 2.0, 2: -1.0} = +2σ to PC1, -1σ to PC2
    """
    try:
        market_state = await get_market_state(universe_key=req.universe_key)
        
        if not market_state.is_built:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        pca_state = await compute_pca_state(market_state, window=req.window)
        
        if pca_state is None:
            raise HTTPException(status_code=500, detail="PCA computation failed")
        
        result = compute_shock_transmission(pca_state, req.shocks)
        
        return {
            "success": True,
            "shock_result": result.to_dict(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shock simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
async def get_pca_cache_status():
    """Get cache status for debugging."""
    return {"market_state_cache": get_cache_status()}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "pca_eigenphysics"}
