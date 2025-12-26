"""
PCA Eigenphysics Features
=========================

All 12 PCA-derived features for market structure analysis.

Feature Index:
1. Eigenstate Collapse Gauge - Concentration of variance in PC1
2. Eigenvector Rotation Radar - Speed and direction of factor rotation
3. Eigenspace Decoherence Index - Breakdown of stable factor structure
4. Tail Shift Correlation Tracker - Left-tail vs right-tail correlations
5. PCA Reconstruction Failure Monitor - Residual variance tracking
6. Liquidity Illusion Index - Crowding detection
7. Eigen Convexity / Forced Unwind Surface - Exit cost estimation
8. Eigen Shock Transmission Simulator - Impact propagation
9. Eigen Topology Graph - Network structure of factors
10. Eigen Instability Early Warning Engine - Regime transition alerts
11. Market Degrees of Freedom Meter - Effective dimensionality
12. Crisis Signature Library - Pattern matching to historical crises
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app.services.pca_state_engine import (
    PCAState,
    PCATimeline,
    compute_entropy,
    compute_participation_ratio,
    compute_eigen_gini,
)

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE OUTPUT SCHEMA
# =============================================================================

@dataclass
class FeatureOutput:
    """Standard output container for all features."""
    feature_name: str
    as_of: str
    window_days: int
    
    # Core outputs
    values: Dict[str, Any]
    
    # Time series (if applicable)
    timeline: Optional[Dict[str, List[float]]] = None
    
    # Chart specification
    chart_spec: Optional[Dict[str, Any]] = None
    
    # Cursor snapshot (latest values)
    cursor: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "as_of": self.as_of,
            "window_days": self.window_days,
            "values": self.values,
            "timeline": self.timeline,
            "chart_spec": self.chart_spec,
            "cursor": self.cursor,
        }


# =============================================================================
# FEATURE 1: EIGENSTATE COLLAPSE GAUGE
# =============================================================================

def compute_collapse_gauge(
    state: PCAState,
    timeline: Optional[PCATimeline] = None,
) -> FeatureOutput:
    """
    Feature 1: Eigenstate Collapse Gauge
    
    Monitors the dominance of PC1 over time.
    
    Collapse occurs when:
    - PC1 explained variance exceeds historical 90th percentile
    - Entropy drops below historical 10th percentile
    - Participation ratio approaches 1
    
    Outputs:
    - pc1_share: Current PC1 explained variance
    - entropy: Shannon entropy of eigenvalue distribution
    - participation_ratio: Effective dimensions
    - collapse_score: 0-100 score (higher = more collapse)
    - state: "normal" | "elevated" | "collapse"
    """
    pc1_share = state.pc1_explained
    entropy = state.entropy
    pr = state.participation_ratio
    
    # Compute collapse score (0-100)
    # Higher PC1 = higher score
    # Lower entropy = higher score
    # Lower PR = higher score
    
    # Normalize each component to 0-100
    pc1_score = min(100, pc1_share * 200)  # 50% PC1 = 100 score
    entropy_score = max(0, 100 - state.normalized_entropy * 100)  # Inverted
    pr_score = max(0, 100 - (pr / state.N) * 100)  # Inverted, normalized by N
    
    collapse_score = 0.5 * pc1_score + 0.3 * entropy_score + 0.2 * pr_score
    
    # Classify state
    if collapse_score >= 70:
        collapse_state = "collapse"
    elif collapse_score >= 50:
        collapse_state = "elevated"
    else:
        collapse_state = "normal"
    
    # Build timeline if available
    timeline_data = None
    if timeline is not None and len(timeline.states) > 0:
        timeline_data = {
            "dates": timeline.timestamps,
            "pc1_share": [s.pc1_explained for s in timeline.states],
            "entropy": [s.entropy for s in timeline.states],
            "participation_ratio": [s.participation_ratio for s in timeline.states],
        }
    
    return FeatureOutput(
        feature_name="collapse_gauge",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "pc1_share": round(pc1_share, 4),
            "pc1_velocity": round(state.pc1_velocity, 6),
            "pc1_acceleration": round(state.pc1_acceleration, 6),
            "entropy": round(entropy, 4),
            "normalized_entropy": round(state.normalized_entropy, 4),
            "participation_ratio": round(pr, 2),
            "effective_dimensions": round(state.effective_dimensions, 2),
            "eigen_gini": round(state.eigen_gini, 4),
            "collapse_score": round(collapse_score, 1),
            "state": collapse_state,
        },
        timeline=timeline_data,
        chart_spec={
            "type": "multi_line",
            "series": ["pc1_share", "normalized_entropy"],
            "annotations": [
                {"type": "threshold", "value": 0.4, "label": "Collapse Zone", "color": "#ff4444"},
            ],
        },
        cursor={
            "pc1": f"{pc1_share:.1%}",
            "entropy": f"{state.normalized_entropy:.2f}",
            "eff_dim": f"{state.effective_dimensions:.1f}",
            "state": collapse_state,
        },
    )


# =============================================================================
# FEATURE 2: EIGENVECTOR ROTATION RADAR
# =============================================================================

def compute_rotation_radar(
    current_state: PCAState,
    prior_state: Optional[PCAState] = None,
    timeline: Optional[PCATimeline] = None,
) -> FeatureOutput:
    """
    Feature 2: Eigenvector Rotation Radar
    
    Tracks how eigenvectors change over time.
    
    Rotation is measured by:
    - Cosine similarity between consecutive eigenvectors
    - Angular velocity (radians per day)
    - Sign-adjusted correlation
    
    High rotation = factor meanings are changing
    Low rotation = stable factor structure
    """
    if prior_state is None or current_state.eigenvectors is None:
        # No prior state available, return defaults
        return FeatureOutput(
            feature_name="rotation_radar",
            as_of=current_state.as_of,
            window_days=current_state.window_days,
            values={
                "rotation_speed": 0.0,
                "pc1_stability": 1.0,
                "pc2_stability": 1.0,
                "direction": "stable",
            },
            cursor={
                "speed": "0.00 r/d",
                "direction": "stable",
            },
        )
    
    current_vecs = current_state.eigenvectors
    prior_vecs = prior_state.eigenvectors
    
    # Compute cosine similarity for top components
    similarities = []
    K = min(current_state.K, prior_state.K, 4)  # Top 4
    
    for k in range(K):
        v1 = current_vecs[:, k]
        v2 = prior_vecs[:, k]
        
        # Handle sign ambiguity
        cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
        cos_sim = abs(cos_sim)  # Sign-invariant
        
        similarities.append(cos_sim)
    
    # Rotation speed (radians per day)
    # θ = arccos(similarity)
    avg_sim = np.mean(similarities)
    rotation_speed = np.arccos(np.clip(avg_sim, -1, 1))
    
    # Stability scores (0-1, higher = more stable)
    pc1_stability = similarities[0] if len(similarities) > 0 else 1.0
    pc2_stability = similarities[1] if len(similarities) > 1 else 1.0
    
    # Direction classification
    if rotation_speed > 0.2:
        direction = "rapid"
    elif rotation_speed > 0.1:
        direction = "drifting"
    else:
        direction = "stable"
    
    # Timeline data
    timeline_data = None
    if timeline is not None and len(timeline.states) >= 2:
        rotation_series = []
        for i in range(1, len(timeline.states)):
            s1 = timeline.states[i-1]
            s2 = timeline.states[i]
            
            if s1.eigenvectors is not None and s2.eigenvectors is not None:
                v1 = s1.eigenvectors[:, 0]
                v2 = s2.eigenvectors[:, 0]
                sim = abs(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10))
                rotation_series.append(np.arccos(np.clip(sim, -1, 1)))
            else:
                rotation_series.append(0.0)
        
        timeline_data = {
            "dates": timeline.timestamps[1:],
            "rotation_speed": rotation_series,
        }
    
    return FeatureOutput(
        feature_name="rotation_radar",
        as_of=current_state.as_of,
        window_days=current_state.window_days,
        values={
            "rotation_speed": round(float(rotation_speed), 4),
            "pc1_stability": round(float(pc1_stability), 4),
            "pc2_stability": round(float(pc2_stability), 4),
            "pc3_stability": round(float(similarities[2] if len(similarities) > 2 else 1.0), 4),
            "pc4_stability": round(float(similarities[3] if len(similarities) > 3 else 1.0), 4),
            "direction": direction,
        },
        timeline=timeline_data,
        chart_spec={
            "type": "polar",
            "series": ["pc1_stability", "pc2_stability", "pc3_stability", "pc4_stability"],
            "labels": ["PC1", "PC2", "PC3", "PC4"],
        },
        cursor={
            "speed": f"{rotation_speed:.2f} r/d",
            "direction": direction,
        },
    )


# =============================================================================
# FEATURE 3: EIGENSPACE DECOHERENCE INDEX
# =============================================================================

def compute_decoherence_index(
    state: PCAState,
    returns: pd.DataFrame,
    window: int = 60,
) -> FeatureOutput:
    """
    Feature 3: Eigenspace Decoherence Index
    
    Measures breakdown of factor structure.
    
    Computed by comparing:
    - In-sample reconstruction error
    - Out-of-sample reconstruction error
    
    High decoherence = factors are breaking down
    """
    # Split window into train/test
    train_end = window * 3 // 4
    train_rets = returns.iloc[:train_end]
    test_rets = returns.iloc[train_end:]
    
    if len(test_rets) < 10:
        # Insufficient data
        return FeatureOutput(
            feature_name="decoherence_index",
            as_of=state.as_of,
            window_days=state.window_days,
            values={"decoherence": 0.0, "status": "insufficient_data"},
            cursor={"index": "N/A"},
        )
    
    # Get loadings
    loadings = state.eigenvectors[:, :min(4, state.K)]
    
    # Compute reconstruction on test set
    test_matrix = test_rets.values
    
    # Project and reconstruct
    projected = test_matrix @ loadings
    reconstructed = projected @ loadings.T
    
    # Compute reconstruction error
    mse = np.mean((test_matrix - reconstructed) ** 2)
    variance = np.var(test_matrix)
    
    decoherence = mse / (variance + 1e-10)
    
    # Classify
    if decoherence > 0.3:
        status = "high"
    elif decoherence > 0.15:
        status = "moderate"
    else:
        status = "low"
    
    return FeatureOutput(
        feature_name="decoherence_index",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "decoherence": round(float(decoherence), 4),
            "reconstruction_error": round(float(mse), 6),
            "test_variance": round(float(variance), 6),
            "status": status,
        },
        cursor={
            "index": f"{decoherence:.2%}",
            "status": status,
        },
    )


# =============================================================================
# FEATURE 4: TAIL SHIFT CORRELATION TRACKER
# =============================================================================

def compute_tail_shift(
    returns: pd.DataFrame,
    window: int = 60,
    tail_percentile: float = 5.0,
) -> FeatureOutput:
    """
    Feature 4: Tail Shift Correlation Tracker
    
    Compares correlation during:
    - Left tail events (market down days)
    - Right tail events (market up days)
    - Normal conditions
    
    Tail correlation asymmetry signals stress regime.
    """
    rets = returns.tail(window).dropna()
    
    if rets.empty or len(rets.columns) < 2:
        return FeatureOutput(
            feature_name="tail_shift",
            as_of=datetime.now().isoformat(),
            window_days=window,
            values={"error": "insufficient_data"},
            cursor={"status": "N/A"},
        )
    
    # Market return (equal-weighted)
    market_ret = rets.mean(axis=1)
    
    # Identify tail days
    left_threshold = np.percentile(market_ret, tail_percentile)
    right_threshold = np.percentile(market_ret, 100 - tail_percentile)
    
    left_tail_mask = market_ret <= left_threshold
    right_tail_mask = market_ret >= right_threshold
    normal_mask = ~left_tail_mask & ~right_tail_mask
    
    # Compute average pairwise correlation for each regime
    def avg_correlation(df):
        if len(df) < 5:
            return np.nan
        corr = df.corr()
        # Handle NaN/inf in correlation matrix
        corr = corr.replace([np.inf, -np.inf], np.nan)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        vals = corr.where(mask).stack()
        return vals.mean() if len(vals) > 0 else np.nan
    
    left_corr = avg_correlation(rets[left_tail_mask])
    right_corr = avg_correlation(rets[right_tail_mask])
    normal_corr = avg_correlation(rets[normal_mask])
    
    # Tail shift = difference between left and right
    tail_shift = (left_corr - right_corr) if not np.isnan(left_corr) and not np.isnan(right_corr) else 0.0
    
    # Tail uplift = left tail correlation above normal
    tail_uplift = (left_corr - normal_corr) if not np.isnan(left_corr) and not np.isnan(normal_corr) else 0.0
    
    return FeatureOutput(
        feature_name="tail_shift",
        as_of=datetime.now().isoformat(),
        window_days=window,
        values={
            "left_tail_corr": round(float(left_corr), 4) if not np.isnan(left_corr) else None,
            "right_tail_corr": round(float(right_corr), 4) if not np.isnan(right_corr) else None,
            "normal_corr": round(float(normal_corr), 4) if not np.isnan(normal_corr) else None,
            "tail_shift": round(float(tail_shift), 4),
            "tail_uplift": round(float(tail_uplift), 4),
            "left_days": int(left_tail_mask.sum()),
            "right_days": int(right_tail_mask.sum()),
        },
        cursor={
            "shift": f"{tail_shift:+.2f}",
            "uplift": f"{tail_uplift:+.2f}",
        },
    )


# =============================================================================
# FEATURE 5: RECONSTRUCTION FAILURE MONITOR
# =============================================================================

def compute_reconstruction_failure(
    state: PCAState,
    returns: pd.DataFrame,
    K_components: int = 4,
) -> FeatureOutput:
    """
    Feature 5: PCA Reconstruction Failure Monitor
    
    Tracks residual variance not explained by top K components.
    
    High residual = market structure is complex/unstable
    Low residual = simple factor structure
    """
    rets = returns.tail(state.window_days).dropna()
    
    if rets.empty or state.eigenvectors is None:
        return FeatureOutput(
            feature_name="reconstruction_failure",
            as_of=state.as_of,
            window_days=state.window_days,
            values={"error": "insufficient_data"},
            cursor={"status": "N/A"},
        )
    
    K = min(K_components, state.K)
    loadings = state.eigenvectors[:, :K]
    
    # Standardize returns
    rets_std = (rets - rets.mean()) / (rets.std() + 1e-10)
    data = rets_std.values
    
    # Handle NaN/inf in standardized data
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Reconstruct
    projected = data @ loadings
    reconstructed = projected @ loadings.T
    
    # Residuals
    residuals = data - reconstructed
    
    # Metrics
    total_var = np.var(data)
    residual_var = np.var(residuals)
    explained_ratio = 1 - (residual_var / (total_var + 1e-10))
    
    # Per-ticker failure
    ticker_residuals = np.var(residuals, axis=0)
    worst_tickers = np.argsort(ticker_residuals)[-5:][::-1]
    
    return FeatureOutput(
        feature_name="reconstruction_failure",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "total_variance": round(float(total_var), 6),
            "residual_variance": round(float(residual_var), 6),
            "explained_ratio": round(float(explained_ratio), 4),
            "failure_ratio": round(1 - explained_ratio, 4),
            "K_components": K,
            "worst_tickers": [
                {"ticker": state.tickers[i], "residual_var": round(float(ticker_residuals[i]), 6)}
                for i in worst_tickers if i < len(state.tickers)
            ],
        },
        cursor={
            "explained": f"{explained_ratio:.1%}",
            "failure": f"{(1-explained_ratio):.1%}",
        },
    )


# =============================================================================
# FEATURE 6: LIQUIDITY ILLUSION INDEX
# =============================================================================

def compute_liquidity_illusion(
    state: PCAState,
    returns: pd.DataFrame,
    dollar_volume: pd.DataFrame,
) -> FeatureOutput:
    """
    Feature 6: Liquidity Illusion Index (LII)
    
    Detects when correlation structure is driven by crowding.
    
    Crowded positions:
    - High correlation with PC1
    - Low volume relative to exposure
    - Price impact amplification during stress
    
    LII = weighted average of crowding scores
    """
    loadings_df = state.get_loadings()
    pc1_loadings = loadings_df["PC1"].values
    
    # Get median dollar volume per ticker
    median_dv = dollar_volume.tail(20).median()
    
    # Normalize loadings and volume
    pc1_abs = np.abs(pc1_loadings)
    pc1_share = pc1_abs / (np.sum(pc1_abs) + 1e-10)
    
    # Crowding score: high PC1 loading + low relative volume
    dv_array = median_dv.reindex(state.tickers).values
    dv_normalized = dv_array / (np.sum(dv_array) + 1e-10)
    
    # Crowding = exposure / volume imbalance
    crowding_scores = pc1_share / (dv_normalized + 1e-10)
    crowding_scores = crowding_scores / (np.mean(crowding_scores) + 1e-10)  # Normalize
    
    # LII = volume-weighted average of crowding
    lii = np.average(crowding_scores, weights=dv_normalized)
    
    # Identify most crowded positions
    crowded_idx = np.argsort(crowding_scores)[-5:][::-1]
    
    return FeatureOutput(
        feature_name="liquidity_illusion",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "lii": round(float(lii), 4),
            "avg_crowding": round(float(np.mean(crowding_scores)), 4),
            "max_crowding": round(float(np.max(crowding_scores)), 4),
            "crowded_positions": [
                {
                    "ticker": state.tickers[i],
                    "crowding": round(float(crowding_scores[i]), 4),
                    "pc1_loading": round(float(pc1_abs[i]), 4),
                }
                for i in crowded_idx if i < len(state.tickers)
            ],
        },
        cursor={
            "lii": f"{lii:.2f}",
            "status": "high" if lii > 1.5 else "normal",
        },
    )


# =============================================================================
# FEATURE 7: EIGEN CONVEXITY / FORCED UNWIND SURFACE
# =============================================================================

def compute_forced_unwind_surface(
    state: PCAState,
    returns: pd.DataFrame,
    dollar_volume: pd.DataFrame,
    shock_sizes: List[float] = [-2.0, -1.5, -1.0, -0.5],
) -> FeatureOutput:
    """
    Feature 7: Eigen Convexity and Forced Unwind Surface
    
    Estimates exit costs under stress scenarios.
    
    For each shock size:
    - Estimate required liquidation
    - Estimate price impact
    - Compute unwind cost curve
    """
    loadings_df = state.get_loadings()
    pc1_loadings = loadings_df["PC1"].values
    
    # Current volatility
    vol = returns.tail(20).std() * np.sqrt(252)
    
    # Median dollar volume
    median_dv = dollar_volume.tail(20).median()
    
    # Unwind cost estimates for each shock
    unwind_curve = []
    
    for shock in shock_sizes:
        # Shock in volatility terms
        shock_return = shock * vol.mean()
        
        # Estimate selling pressure proportional to PC1 loadings
        selling_pressure = np.abs(pc1_loadings) * np.abs(shock_return)
        
        # Price impact (simplified Kyle lambda model)
        # Impact = sqrt(volume_to_trade / daily_volume)
        dv_array = median_dv.reindex(state.tickers).fillna(1e6).values
        impact = np.sqrt(selling_pressure / (dv_array + 1e10))
        
        # Aggregate cost
        total_cost = np.sum(impact * selling_pressure)
        
        unwind_curve.append({
            "shock_sigma": shock,
            "shock_return": round(float(shock_return), 4),
            "total_cost": round(float(total_cost), 6),
            "cost_bps": round(float(total_cost * 10000), 2),
        })
    
    # Door crowding metric
    door_crowding = np.sum(np.abs(pc1_loadings) ** 2) / (np.sum(np.abs(pc1_loadings)) ** 2 + 1e-10)
    
    return FeatureOutput(
        feature_name="forced_unwind_surface",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "unwind_curve": unwind_curve,
            "door_crowding": round(float(door_crowding), 4),
            "n_tickers": state.N,
        },
        chart_spec={
            "type": "line",
            "x": [u["shock_sigma"] for u in unwind_curve],
            "y": [u["cost_bps"] for u in unwind_curve],
            "xlabel": "Shock (σ)",
            "ylabel": "Cost (bps)",
        },
        cursor={
            "1σ_cost": f"{unwind_curve[-1]['cost_bps']:.1f} bps" if unwind_curve else "N/A",
            "crowding": f"{door_crowding:.2f}",
        },
    )


# =============================================================================
# FEATURE 8: EIGEN SHOCK TRANSMISSION SIMULATOR
# =============================================================================

def compute_shock_transmission(
    state: PCAState,
    shock_config: Dict[int, float],  # {pc_index: shock_magnitude}
) -> FeatureOutput:
    """
    Feature 8: Eigen Shock Transmission Simulator
    
    Simulates impact of shocks to principal components.
    
    Input: {1: 2.0, 2: -1.0} = +2σ to PC1, -1σ to PC2
    Output: Per-ticker expected return impact
    """
    loadings_df = state.get_loadings()
    
    # Build shock vector
    shock_vector = np.zeros(state.K)
    for pc_idx, magnitude in shock_config.items():
        if 1 <= pc_idx <= state.K:
            shock_vector[pc_idx - 1] = magnitude
    
    # Compute ticker impacts: Δr = W @ shock
    loadings_matrix = loadings_df.values[:, :len(shock_vector)]
    impacts = loadings_matrix @ shock_vector
    
    # Convert to return impacts (assuming unit vol)
    impact_df = pd.Series(impacts, index=state.tickers)
    
    # Sort by absolute impact
    sorted_idx = np.argsort(np.abs(impacts))[::-1]
    
    return FeatureOutput(
        feature_name="shock_transmission",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "shock_config": shock_config,
            "total_market_impact": round(float(np.mean(impacts)), 4),
            "dispersion": round(float(np.std(impacts)), 4),
            "ticker_impacts": {
                state.tickers[i]: round(float(impacts[i]), 4)
                for i in sorted_idx[:20]  # Top 20
            },
            "most_positive": [
                {"ticker": state.tickers[i], "impact": round(float(impacts[i]), 4)}
                for i in np.argsort(impacts)[-5:][::-1]
            ],
            "most_negative": [
                {"ticker": state.tickers[i], "impact": round(float(impacts[i]), 4)}
                for i in np.argsort(impacts)[:5]
            ],
        },
        cursor={
            "market": f"{np.mean(impacts):+.2%}",
            "dispersion": f"{np.std(impacts):.2%}",
        },
    )


# =============================================================================
# FEATURE 9: EIGEN TOPOLOGY GRAPH
# =============================================================================

def compute_eigen_topology(
    state: PCAState,
    correlation_threshold: float = 0.5,
) -> FeatureOutput:
    """
    Feature 9: Eigen Topology Graph
    
    Builds network structure from factor loadings.
    
    Nodes = tickers
    Edges = similar loading profiles
    Clusters = detected communities
    
    Complexity: O(N² × K)
    """
    loadings = state.eigenvectors[:, :min(4, state.K)]
    
    # Compute pairwise loading similarity
    N = len(state.tickers)
    similarity_matrix = np.zeros((N, N))
    
    for i in range(N):
        for j in range(i + 1, N):
            # Cosine similarity of loading profiles
            v1, v2 = loadings[i], loadings[j]
            sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
            similarity_matrix[i, j] = sim
            similarity_matrix[j, i] = sim
    
    # Build adjacency from threshold
    adjacency = (np.abs(similarity_matrix) >= correlation_threshold).astype(int)
    np.fill_diagonal(adjacency, 0)
    
    # Compute node degrees
    degrees = adjacency.sum(axis=1)
    
    # Simple clustering (connected components)
    # For production, use spectral clustering or Louvain
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse import csr_matrix
    
    sparse_adj = csr_matrix(adjacency)
    n_components, labels = connected_components(sparse_adj, directed=False)
    
    # Build node list
    nodes = [
        {
            "id": state.tickers[i],
            "degree": int(degrees[i]),
            "cluster": int(labels[i]),
            "pc1_loading": round(float(loadings[i, 0]), 4),
        }
        for i in range(N)
    ]
    
    # Build edge list (for visualization)
    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            if adjacency[i, j]:
                edges.append({
                    "source": state.tickers[i],
                    "target": state.tickers[j],
                    "weight": round(float(similarity_matrix[i, j]), 4),
                })
    
    return FeatureOutput(
        feature_name="eigen_topology",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "n_nodes": N,
            "n_edges": len(edges),
            "n_clusters": n_components,
            "avg_degree": round(float(np.mean(degrees)), 2),
            "max_degree": int(np.max(degrees)),
            "density": round(float(len(edges) / (N * (N - 1) / 2)), 4),
            "nodes": nodes,
            "edges": edges[:100],  # Limit for API response
        },
        chart_spec={
            "type": "force_graph",
        },
        cursor={
            "clusters": str(n_components),
            "density": f"{len(edges) / (N * (N - 1) / 2):.1%}",
        },
    )


# =============================================================================
# FEATURE 10: EIGEN INSTABILITY EARLY WARNING ENGINE
# =============================================================================

# Instability weights from specification
INSTABILITY_WEIGHTS = {
    "pc1_share": 0.12,
    "pc1_velocity": 0.08,
    "entropy_inv": 0.10,
    "rotation": 0.12,
    "decoherence": 0.10,
    "tail_shift": 0.10,
    "recon_error": 0.08,
    "unwind_risk": 0.15,
    "lii": 0.08,
    "door_crowding": 0.07,
}


def compute_instability_engine(
    features: Dict[str, Any],
    state: PCAState,
) -> FeatureOutput:
    """
    Feature 10: Eigen Instability Early Warning Engine
    
    Aggregates all features into a single instability score.
    
    Score = Σ (weight_i × normalized_feature_i)
    
    State classification:
    - 0-25: Stable
    - 25-50: Watching
    - 50-75: Warning
    - 75-100: Critical
    """
    # Helper to safely get feature values
    def get_val(feature_name: str, key: str, default=0):
        feature = features.get(feature_name)
        if feature is None:
            return default
        if hasattr(feature, 'values') and isinstance(feature.values, dict):
            return feature.values.get(key, default)
        if isinstance(feature, dict):
            vals = feature.get('values', {})
            return vals.get(key, default) if isinstance(vals, dict) else default
        return default
    
    components = {}
    
    # PC1 share (0-0.5 maps to 0-100)
    pc1 = state.pc1_explained
    components["pc1_share"] = min(100, pc1 * 200)
    
    # PC1 velocity (positive velocity = bad)
    pc1_vel = abs(state.pc1_velocity) * 1000
    components["pc1_velocity"] = min(100, pc1_vel)
    
    # Entropy inverse (low entropy = bad)
    components["entropy_inv"] = 100 - state.normalized_entropy * 100
    
    # Rotation speed
    rot = get_val("rotation_radar", "rotation_speed", 0)
    components["rotation"] = min(100, rot * 500)
    
    # Decoherence
    dec = get_val("decoherence_index", "decoherence", 0)
    components["decoherence"] = min(100, dec * 200)
    
    # Tail shift
    ts = abs(get_val("tail_shift", "tail_shift", 0))
    components["tail_shift"] = min(100, ts * 100)
    
    # Reconstruction error
    fail = get_val("reconstruction_failure", "failure_ratio", 0)
    components["recon_error"] = min(100, fail * 200)
    
    # Unwind risk
    dc = get_val("forced_unwind_surface", "door_crowding", 0)
    components["unwind_risk"] = min(100, dc * 200)
    components["door_crowding"] = min(100, dc * 200)
    
    # LII
    lii = get_val("liquidity_illusion", "lii", 1)
    components["lii"] = min(100, max(0, (lii - 1) * 50))
    
    # Compute weighted score
    instability_score = 0
    for key, weight in INSTABILITY_WEIGHTS.items():
        instability_score += weight * components.get(key, 0)
    
    # Classify state
    if instability_score >= 75:
        regime_state = "critical"
        color = "#ff4444"
    elif instability_score >= 50:
        regime_state = "warning"
        color = "#ff9944"
    elif instability_score >= 25:
        regime_state = "watching"
        color = "#ffcc44"
    else:
        regime_state = "stable"
        color = "#44ff44"
    
    # Top drivers
    sorted_components = sorted(
        components.items(),
        key=lambda x: x[1] * INSTABILITY_WEIGHTS.get(x[0], 0),
        reverse=True,
    )
    
    return FeatureOutput(
        feature_name="instability_engine",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "instability_score": round(instability_score, 1),
            "state": regime_state,
            "color": color,
            "components": {k: round(v, 1) for k, v in components.items()},
            "top_drivers": [
                {"driver": k, "contribution": round(v * INSTABILITY_WEIGHTS.get(k, 0), 2)}
                for k, v in sorted_components[:5]
            ],
        },
        cursor={
            "score": f"{instability_score:.0f}",
            "state": regime_state,
        },
    )


# =============================================================================
# FEATURE 11: MARKET DEGREES OF FREEDOM METER
# =============================================================================

def compute_degrees_of_freedom(
    state: PCAState,
) -> FeatureOutput:
    """
    Feature 11: Market Degrees of Freedom Meter
    
    How many independent factors drive the market?
    
    Metrics:
    - K90, K95, K99: Components needed for 90/95/99% variance
    - Participation ratio
    - Effective dimensions (PR interpretation)
    """
    cumvar = np.array(state.cumulative_variance)
    
    # K at different thresholds
    def get_k(threshold):
        mask = cumvar >= threshold
        return int(np.argmax(mask) + 1) if mask.any() else state.K
    
    k90 = get_k(0.90)
    k95 = get_k(0.95)
    k99 = get_k(0.99)
    
    # Participation ratio as effective dims
    eff_dims = state.participation_ratio
    
    # Eigenvalue decay rate (slope of log eigenvalues)
    eigenvals = np.array(state.eigenvalues)
    if len(eigenvals) > 2:
        log_eigenvals = np.log(eigenvals + 1e-10)
        x = np.arange(len(log_eigenvals))
        decay_rate = np.polyfit(x, log_eigenvals, 1)[0]
    else:
        decay_rate = 0
    
    return FeatureOutput(
        feature_name="degrees_of_freedom",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "k90": k90,
            "k95": k95,
            "k99": k99,
            "effective_dimensions": round(eff_dims, 2),
            "participation_ratio": round(state.participation_ratio, 4),
            "eigen_gini": round(state.eigen_gini, 4),
            "decay_rate": round(float(decay_rate), 4),
            "N": state.N,  # Max dimensions
            "n_factors": state.N,
            "cumulative_variance": [round(v, 4) for v in state.cumulative_variance],
        },
        chart_spec={
            "type": "bar",
            "x": [f"PC{i+1}" for i in range(len(state.explained_variance))],
            "y": list(state.explained_variance),
            "cumulative": list(state.cumulative_variance),
        },
        cursor={
            "K90": str(k90),
            "K95": str(k95),
            "eff_dim": f"{eff_dims:.1f}",
        },
    )


# =============================================================================
# FEATURE 12: CRISIS SIGNATURE LIBRARY
# =============================================================================

def compute_crisis_signature_match(
    state: PCAState,
    crisis_library: List[Dict[str, Any]],
    distance_threshold: float = 0.3,
) -> FeatureOutput:
    """
    Feature 12: Crisis Signature Library
    
    Compares current state fingerprint to historical crises.
    
    Fingerprint = [PC1, entropy, PR, gini, velocity, ...]
    Distance = Euclidean in normalized space
    """
    # Build current fingerprint
    current_fingerprint = np.array([
        state.pc1_explained,
        state.normalized_entropy,
        state.participation_ratio / state.N,
        state.eigen_gini,
        min(1, abs(state.pc1_velocity) * 100),
    ])
    
    matches = []
    
    for crisis in crisis_library:
        if "fingerprint" not in crisis:
            continue
        
        crisis_fp = np.array(crisis["fingerprint"])
        
        # Ensure same length
        min_len = min(len(current_fingerprint), len(crisis_fp))
        
        # Euclidean distance
        distance = np.linalg.norm(current_fingerprint[:min_len] - crisis_fp[:min_len])
        
        if distance <= distance_threshold:
            matches.append({
                "name": crisis.get("name", "Unknown"),
                "date_start": crisis.get("date_start"),
                "distance": round(float(distance), 4),
                "similarity": round(1 - distance / distance_threshold, 4),
            })
    
    # Sort by distance
    matches = sorted(matches, key=lambda x: x["distance"])[:5]
    
    return FeatureOutput(
        feature_name="crisis_signature",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "current_fingerprint": current_fingerprint.tolist(),
            "matches": matches,
            "closest_match": matches[0] if matches else None,
            "n_matches": len(matches),
        },
        cursor={
            "closest": matches[0]["name"] if matches else "None",
            "similarity": f"{matches[0]['similarity']:.0%}" if matches else "N/A",
        },
    )


# =============================================================================
# GOVERNOR SCORE (Meta-Feature)
# =============================================================================

def compute_governor_score(
    state: PCAState,
    features: Dict[str, Any],
) -> FeatureOutput:
    """
    Governor Score: Single risk score for dashboard badge.
    
    Combines instability engine output with additional context.
    Score: 0-100 (higher = more risk)
    """
    # Helper to safely get feature values
    def get_feature_values(feature):
        if feature is None:
            return {}
        if hasattr(feature, 'values') and isinstance(feature.values, dict):
            return feature.values
        if isinstance(feature, dict):
            return feature.get('values', {})
        return {}
    
    # Get instability score if computed
    instability_feature = features.get("instability_engine")
    inst_values = get_feature_values(instability_feature)
    
    if inst_values:
        instability = inst_values.get("instability_score", 50)
        regime_state = inst_values.get("state", "watching")
        drivers = inst_values.get("top_drivers", [])
    else:
        # Compute simplified score
        instability = 25 + state.pc1_explained * 100 - state.normalized_entropy * 50
        instability = max(0, min(100, instability))
        
        if instability >= 75:
            regime_state = "critical"
        elif instability >= 50:
            regime_state = "warning"
        elif instability >= 25:
            regime_state = "watching"
        else:
            regime_state = "stable"
        
        drivers = []
    
    # Color mapping
    color_map = {
        "stable": "#22c55e",
        "watching": "#eab308",
        "warning": "#f97316",
        "critical": "#ef4444",
    }
    
    return FeatureOutput(
        feature_name="governor_score",
        as_of=state.as_of,
        window_days=state.window_days,
        values={
            "score": round(float(instability), 1),
            "state": regime_state,
            "color": color_map.get(regime_state, "#888888"),
            "top_drivers": drivers[:3] if drivers else [],
            "effective_dimensions": round(state.effective_dimensions, 1),
            "pc1_share": round(state.pc1_explained, 4),
            "entropy": round(state.normalized_entropy, 4),
        },
        cursor={
            "score": f"{instability:.0f}",
            "state": regime_state,
        },
    )
