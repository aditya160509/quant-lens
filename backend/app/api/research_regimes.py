"""
Research Regimes API
D4: Regime detection from macro and market indicators.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging

from app.models.research_schemas import (
    RegimesRequest,
    RegimeModelType,
    make_error_response,
)
from app.services.research_cache import research_cache
from app.services import research_data, research_math

logger = logging.getLogger(__name__)

router = APIRouter()

# Regime labels
REGIME_LABELS = {
    0: "Risk On",
    1: "Neutral",
    2: "Risk Off"
}


def compute_zscore_regimes(
    inputs_df: pd.DataFrame,
    weights: Dict[str, float],
    smooth_days: int,
    thresholds: Dict[str, float]
) -> Dict[str, Any]:
    """
    Compute regimes using weighted z-score composite.
    
    Args:
        inputs_df: DataFrame of input series (already standardized)
        weights: Weight per input
        smooth_days: Smoothing window
        thresholds: risk_on and risk_off thresholds
        
    Returns:
        Dict with timeline, current, and contributors
    """
    # Apply signs (higher positive = risk off)
    signed_df = inputs_df.copy()
    for col in signed_df.columns:
        sign = research_data.get_macro_sign(col)
        signed_df[col] = signed_df[col] * sign
    
    # Normalize weights
    total_weight = sum(weights.get(col, 1.0) for col in signed_df.columns)
    norm_weights = {col: weights.get(col, 1.0) / total_weight for col in signed_df.columns}
    
    # Compute weighted score
    score = pd.Series(0.0, index=signed_df.index)
    for col in signed_df.columns:
        score += signed_df[col] * norm_weights[col]
    
    # Smooth
    score_smooth = score.rolling(window=smooth_days, min_periods=1).mean()
    
    # Assign regimes
    risk_on_thresh = thresholds.get('risk_on', -0.5)
    risk_off_thresh = thresholds.get('risk_off', 0.5)
    
    regimes = pd.Series("Neutral", index=score_smooth.index)
    regimes[score_smooth < risk_on_thresh] = "Risk On"
    regimes[score_smooth > risk_off_thresh] = "Risk Off"
    
    # Compute confidence as distance from nearest threshold
    confidence = pd.Series(0.5, index=score_smooth.index)
    for i, (idx, s) in enumerate(score_smooth.items()):
        if s < risk_on_thresh:
            confidence.iloc[i] = min(1.0, abs(s - risk_on_thresh) / 1.0 + 0.5)
        elif s > risk_off_thresh:
            confidence.iloc[i] = min(1.0, abs(s - risk_off_thresh) / 1.0 + 0.5)
        else:
            # Neutral - lower confidence
            confidence.iloc[i] = 0.5 - 0.3 * abs(s)
    
    # Contributors (latest values)
    contributors = {}
    if len(signed_df) > 0:
        last_row = signed_df.iloc[-1]
        for col in signed_df.columns:
            contributors[col] = round(float(last_row[col] * norm_weights[col]), 4)
    
    # Build timeline
    timeline = []
    for i, idx in enumerate(score_smooth.index):
        timeline.append({
            "date": idx.strftime('%Y-%m-%d'),
            "regime": regimes.iloc[i],
            "score": round(float(score_smooth.iloc[i]), 4),
            "confidence": round(float(confidence.iloc[i]), 4)
        })
    
    # Current
    current = None
    if len(timeline) > 0:
        last = timeline[-1]
        current = {
            "date": last["date"],
            "regime": last["regime"],
            "score": last["score"],
            "confidence": last["confidence"]
        }
    
    return {
        "timeline": timeline,
        "current": current,
        "contributors": contributors
    }


def compute_kmeans_regimes(
    inputs_df: pd.DataFrame,
    n_clusters: int = 3
) -> Dict[str, Any]:
    """
    Compute regimes using K-means clustering.
    """
    from sklearn.cluster import KMeans
    
    # Apply signs
    signed_df = inputs_df.copy()
    for col in signed_df.columns:
        sign = research_data.get_macro_sign(col)
        signed_df[col] = signed_df[col] * sign
    
    # Prepare feature matrix
    X = signed_df.dropna().values
    valid_index = signed_df.dropna().index
    
    if len(X) < n_clusters * 10:
        return {"error": "Insufficient data for clustering"}
    
    # Fit K-means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    
    # Compute composite score per cluster to order them
    composite_scores = signed_df.mean(axis=1)
    cluster_scores = {}
    for c in range(n_clusters):
        mask = labels == c
        cluster_scores[c] = composite_scores.loc[valid_index[mask]].mean()
    
    # Order clusters: lowest score = Risk On, highest = Risk Off
    sorted_clusters = sorted(cluster_scores.keys(), key=lambda x: cluster_scores[x])
    label_map = {
        sorted_clusters[0]: "Risk On",
        sorted_clusters[-1]: "Risk Off"
    }
    for c in sorted_clusters[1:-1]:
        label_map[c] = "Neutral"
    
    # Build timeline
    timeline = []
    composite_smooth = composite_scores.rolling(window=5, min_periods=1).mean()
    
    for i, idx in enumerate(valid_index):
        regime = label_map.get(labels[i], "Neutral")
        score = float(composite_smooth.loc[idx])
        timeline.append({
            "date": idx.strftime('%Y-%m-%d'),
            "regime": regime,
            "score": round(score, 4),
            "confidence": 0.6  # K-means doesn't give probabilities
        })
    
    # Contributors
    contributors = {}
    if len(signed_df) > 0:
        last_row = signed_df.iloc[-1]
        for col in signed_df.columns:
            contributors[col] = round(float(last_row[col] / len(signed_df.columns)), 4)
    
    current = timeline[-1] if timeline else None
    
    return {
        "timeline": timeline,
        "current": current,
        "contributors": contributors
    }


def compute_hmm_regimes(
    inputs_df: pd.DataFrame,
    n_states: int = 3
) -> Dict[str, Any]:
    """
    Compute regimes using Gaussian HMM.
    """
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        return {"error": "hmmlearn not installed"}
    
    # Apply signs
    signed_df = inputs_df.copy()
    for col in signed_df.columns:
        sign = research_data.get_macro_sign(col)
        signed_df[col] = signed_df[col] * sign
    
    # Prepare feature matrix
    clean_df = signed_df.dropna()
    X = clean_df.values
    valid_index = clean_df.index
    
    if len(X) < n_states * 20:
        return {"error": "Insufficient data for HMM"}
    
    # Fit HMM
    try:
        model = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            n_iter=100,
            random_state=42
        )
        model.fit(X)
        
        hidden_states = model.predict(X)
        probs = model.predict_proba(X)
    except Exception as e:
        logger.error(f"HMM fit failed: {e}")
        return {"error": f"HMM fit failed: {str(e)}"}
    
    # Order states by mean composite score
    composite_scores = clean_df.mean(axis=1)
    state_scores = {}
    for s in range(n_states):
        mask = hidden_states == s
        state_scores[s] = composite_scores.loc[valid_index[mask]].mean()
    
    sorted_states = sorted(state_scores.keys(), key=lambda x: state_scores[x])
    label_map = {
        sorted_states[0]: "Risk On",
        sorted_states[-1]: "Risk Off"
    }
    for s in sorted_states[1:-1]:
        label_map[s] = "Neutral"
    
    # Build timeline
    timeline = []
    composite_smooth = composite_scores.rolling(window=5, min_periods=1).mean()
    
    for i, idx in enumerate(valid_index):
        state = hidden_states[i]
        regime = label_map.get(state, "Neutral")
        score = float(composite_smooth.loc[idx])
        conf = float(probs[i, state])
        timeline.append({
            "date": idx.strftime('%Y-%m-%d'),
            "regime": regime,
            "score": round(score, 4),
            "confidence": round(conf, 4)
        })
    
    # Contributors
    contributors = {}
    if len(signed_df) > 0:
        last_row = signed_df.iloc[-1]
        for col in signed_df.columns:
            contributors[col] = round(float(last_row[col] / len(signed_df.columns)), 4)
    
    current = timeline[-1] if timeline else None
    
    return {
        "timeline": timeline,
        "current": current,
        "contributors": contributors
    }


@router.post("/regimes")
async def regimes(request: RegimesRequest):
    """
    Detect market regimes from macro and market indicators.
    
    Supports zscore, kmeans, and hmm model types.
    """
    try:
        # Check compute cache
        payload = request.model_dump()
        cached, cache_hit = research_cache.get_compute(payload)
        if cache_hit and cached is not None:
            cached['meta']['cache_hit'] = True
            return JSONResponse(content=cached)
        
        # Load input series
        available_macro = research_data.get_available_macro()
        invalid_inputs = [i for i in request.inputs if i.upper() not in available_macro]
        
        # Allow VIX as special case (may be loaded differently)
        if invalid_inputs:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "INVALID_INPUT",
                    f"Unknown input series: {invalid_inputs}",
                    {"available": available_macro}
                )
            )
        
        # Load macro series
        inputs_df = research_data.get_macro_series(request.inputs, request.lookback)
        
        if inputs_df.empty:
            return JSONResponse(
                status_code=500,
                content=make_error_response(
                    "DATA_ERROR",
                    "Failed to load input series. Ensure FRED_API_KEY is set.",
                    {}
                )
            )
        
        # Standardize all inputs
        for col in inputs_df.columns:
            inputs_df[col] = research_math.standardize(inputs_df[col])
        
        # Compute regimes based on model type
        model_type = request.model.type
        
        if model_type == RegimeModelType.ZSCORE:
            weights = request.model.weights or {col: 1.0 for col in inputs_df.columns}
            results = compute_zscore_regimes(
                inputs_df,
                weights,
                request.model.smooth_days,
                {
                    "risk_on": request.model.thresholds.risk_on,
                    "risk_off": request.model.thresholds.risk_off
                }
            )
        elif model_type == RegimeModelType.KMEANS:
            results = compute_kmeans_regimes(inputs_df, request.model.n_clusters)
        elif model_type == RegimeModelType.HMM:
            results = compute_hmm_regimes(inputs_df, request.model.n_states)
        else:
            # Rule-based fallback to zscore
            weights = request.model.weights or {col: 1.0 for col in inputs_df.columns}
            results = compute_zscore_regimes(
                inputs_df,
                weights,
                request.model.smooth_days,
                {
                    "risk_on": request.model.thresholds.risk_on,
                    "risk_off": request.model.thresholds.risk_off
                }
            )
        
        if "error" in results:
            return JSONResponse(
                status_code=500,
                content=make_error_response(
                    "COMPUTE_ERROR",
                    results["error"],
                    {}
                )
            )
        
        # Downsample timeline if too long
        if len(results.get("timeline", [])) > 500:
            step = len(results["timeline"]) // 500
            results["timeline"] = results["timeline"][::step]
        
        # Build response
        response = {
            "meta": {
                "inputs": list(inputs_df.columns),
                "model_type": model_type.value,
                "lookback_days": request.lookback,
                "data_points": len(inputs_df),
                **research_cache.make_cache_meta(False)
            },
            "current": results.get("current"),
            "timeline": results.get("timeline", []),
            "contributors": results.get("contributors", {})
        }
        
        # Cache result
        research_cache.set_compute(payload, response)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in regimes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )
