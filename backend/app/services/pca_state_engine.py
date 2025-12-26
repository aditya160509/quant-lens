"""
PCA Eigenphysics Core Engine
============================

This module implements the PCA State computation with:
- Ledoit-Wolf shrinkage for covariance estimation
- Eigen decomposition with proper normalization
- Entropy and participation ratio calculations
- Multi-horizon support (20, 60, 120 day windows)

All computations are deterministic and cache-aware.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# PCA STATE SCHEMA
# =============================================================================

@dataclass(frozen=True)
class PCAState:
    """
    Core PCA state object.
    
    This is the fundamental output of eigendecomposition.
    All 12 features derive from this state.
    """
    # Identification
    as_of: str  # ISO timestamp
    window_days: int
    universe_key: str
    
    # Universe info
    tickers: Tuple[str, ...]
    N: int  # Number of tickers
    T: int  # Number of observations
    
    # Eigendecomposition
    eigenvalues: Tuple[float, ...]  # Descending order
    eigenvectors: np.ndarray  # N × K matrix (columns are eigenvectors)
    K: int  # Number of components kept
    
    # Variances
    explained_variance: Tuple[float, ...]
    cumulative_variance: Tuple[float, ...]
    
    # Derived metrics
    entropy: float  # Shannon entropy of eigenvalue distribution
    normalized_entropy: float  # H / log(N)
    participation_ratio: float  # Effective dimension measure
    effective_dimensions: float  # PR interpretation
    eigen_gini: float  # Concentration of variance
    
    # Top PC1 characteristics
    pc1_explained: float  # PC1 variance share
    pc1_velocity: float  # Change in PC1 share (vs prior window)
    pc1_acceleration: float  # Change in velocity
    
    # Quality and provenance
    config_hash: str
    market_state_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "window_days": self.window_days,
            "universe_key": self.universe_key,
            "tickers": list(self.tickers),
            "N": self.N,
            "T": self.T,
            "eigenvalues": list(self.eigenvalues),
            "explained_variance": list(self.explained_variance),
            "cumulative_variance": list(self.cumulative_variance),
            "K": self.K,
            "entropy": round(self.entropy, 6),
            "normalized_entropy": round(self.normalized_entropy, 6),
            "participation_ratio": round(self.participation_ratio, 4),
            "effective_dimensions": round(self.effective_dimensions, 2),
            "eigen_gini": round(self.eigen_gini, 4),
            "pc1_explained": round(self.pc1_explained, 4),
            "pc1_velocity": round(self.pc1_velocity, 6),
            "pc1_acceleration": round(self.pc1_acceleration, 6),
            "config_hash": self.config_hash,
            "market_state_hash": self.market_state_hash,
        }
    
    def get_loadings(self) -> pd.DataFrame:
        """Get eigenvector loadings as DataFrame."""
        return pd.DataFrame(
            self.eigenvectors[:, :self.K],
            index=list(self.tickers),
            columns=[f"PC{i+1}" for i in range(self.K)],
        )


@dataclass(frozen=True)
class PCATimeline:
    """
    Sequence of PCA states over time.
    Used for rotation, instability, and trend analysis.
    """
    states: Tuple[PCAState, ...]
    window_days: int
    universe_key: str
    
    @property
    def timestamps(self) -> List[str]:
        return [s.as_of for s in self.states]
    
    @property
    def pc1_series(self) -> np.ndarray:
        return np.array([s.pc1_explained for s in self.states])
    
    @property
    def entropy_series(self) -> np.ndarray:
        return np.array([s.entropy for s in self.states])
    
    @property
    def pr_series(self) -> np.ndarray:
        return np.array([s.participation_ratio for s in self.states])


# =============================================================================
# MATHEMATICAL FUNCTIONS
# =============================================================================

def compute_entropy(eigenvalues: np.ndarray) -> Tuple[float, float]:
    """
    Compute Shannon entropy of eigenvalue distribution.
    
    H = -Σ p_i * log(p_i)
    
    where p_i = λ_i / Σλ
    
    Returns:
        (entropy, normalized_entropy)
    """
    # Normalize to probability distribution
    eig_sum = np.sum(eigenvalues)
    if eig_sum <= 0:
        return 0.0, 0.0
    
    p = eigenvalues / eig_sum
    p = p[p > 1e-10]  # Filter near-zero values
    
    # Shannon entropy
    H = -np.sum(p * np.log(p))
    
    # Normalize by log(N) - max entropy
    H_max = np.log(len(p)) if len(p) > 1 else 1.0
    H_normalized = H / H_max if H_max > 0 else 0.0
    
    return float(H), float(H_normalized)


def compute_participation_ratio(eigenvalues: np.ndarray) -> float:
    """
    Compute participation ratio (effective number of dimensions).
    
    PR = (Σλ_i)² / Σ(λ_i²)
    
    Interpretation:
    - PR = 1: All variance in one component
    - PR = N: Equal variance across all components
    """
    eig_sum = np.sum(eigenvalues)
    eig_sq_sum = np.sum(eigenvalues ** 2)
    
    if eig_sq_sum <= 0:
        return 1.0
    
    return float((eig_sum ** 2) / eig_sq_sum)


def compute_eigen_gini(eigenvalues: np.ndarray) -> float:
    """
    Compute Gini coefficient of eigenvalue distribution.
    
    Measures concentration of variance.
    - 0: Perfect equality (all eigenvalues equal)
    - 1: Perfect inequality (one eigenvalue dominates)
    """
    n = len(eigenvalues)
    if n <= 1:
        return 0.0
    
    sorted_eig = np.sort(eigenvalues)
    cumsum = np.cumsum(sorted_eig)
    
    # Lorenz curve integration
    gini = (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n
    
    return float(max(0, min(1, gini)))


def eigen_decomposition(
    cov_matrix: np.ndarray,
    K: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Perform eigen decomposition with proper handling.
    
    Returns:
        (eigenvalues, eigenvectors) - sorted descending
    """
    # Symmetric eigenvalue decomposition
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    
    # Sort descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    # Ensure positive eigenvalues (numerical stability)
    eigenvalues = np.maximum(eigenvalues, 0)
    
    # Keep top K
    eigenvalues = eigenvalues[:K]
    eigenvectors = eigenvectors[:, :K]
    
    return eigenvalues, eigenvectors


def compute_explained_variance(eigenvalues: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute explained and cumulative variance ratios.
    
    Returns:
        (explained_var_ratio, cumulative_var_ratio)
    """
    total = np.sum(eigenvalues)
    if total <= 0:
        return np.zeros_like(eigenvalues), np.zeros_like(eigenvalues)
    
    explained = eigenvalues / total
    cumulative = np.cumsum(explained)
    
    return explained, cumulative


# =============================================================================
# PCA STATE BUILDER
# =============================================================================

class PCAStateBuilder:
    """
    Builds PCAState from MarketState.
    
    Handles:
    - Covariance estimation with shrinkage
    - Eigen decomposition
    - Metric computation
    - State history for velocity/acceleration
    """
    
    DEFAULT_WINDOWS = (20, 60, 120)
    K_MAX = 10  # Maximum components to keep
    
    def __init__(
        self,
        windows: Tuple[int, ...] = DEFAULT_WINDOWS,
        shrinkage: str = "ledoit_wolf",
    ):
        self.windows = windows
        self.shrinkage = shrinkage
        self._state_history: Dict[str, List[PCAState]] = {}
    
    def build_state(
        self,
        returns: pd.DataFrame,
        window: int,
        universe_key: str,
        market_state_hash: str,
        prior_state: Optional[PCAState] = None,
    ) -> PCAState:
        """
        Build a PCAState from returns data.
        
        Args:
            returns: Log returns DataFrame (T × N)
            window: Rolling window size
            universe_key: Universe identifier
            market_state_hash: Hash of source MarketState
            prior_state: Previous state for velocity calculation
        
        Returns:
            PCAState object
        """
        # Get windowed returns
        rets = returns.tail(window).dropna(how='all')
        
        # Drop columns with any NaN (strict quality)
        valid_cols = rets.columns[~rets.isna().any()]
        rets = rets[valid_cols]
        
        if rets.empty or len(rets.columns) < 2:
            raise ValueError(f"Insufficient valid data for PCA: {len(rets.columns)} tickers")
        
        tickers = list(rets.columns)
        N = len(tickers)
        T = len(rets)
        
        # Compute covariance with shrinkage
        if self.shrinkage == "ledoit_wolf":
            from sklearn.covariance import LedoitWolf
            cov_estimator = LedoitWolf()
            cov_estimator.fit(rets.values)
            cov_matrix = cov_estimator.covariance_
        elif self.shrinkage == "oas":
            from sklearn.covariance import OAS
            cov_estimator = OAS()
            cov_estimator.fit(rets.values)
            cov_matrix = cov_estimator.covariance_
        else:
            cov_matrix = rets.cov().values
        
        # Eigen decomposition
        K = min(self.K_MAX, N)
        eigenvalues, eigenvectors = eigen_decomposition(cov_matrix, K)
        
        # Explained variance
        explained, cumulative = compute_explained_variance(eigenvalues)
        
        # Entropy metrics
        # Use all eigenvalues for entropy (not just K)
        all_eigenvalues, _ = eigen_decomposition(cov_matrix, N)
        entropy, normalized_entropy = compute_entropy(all_eigenvalues)
        
        # Participation ratio
        participation_ratio = compute_participation_ratio(all_eigenvalues)
        effective_dims = participation_ratio  # Direct interpretation
        
        # Gini coefficient
        eigen_gini = compute_eigen_gini(all_eigenvalues)
        
        # PC1 dynamics
        pc1_explained = float(explained[0]) if len(explained) > 0 else 0.0
        
        if prior_state is not None:
            pc1_velocity = pc1_explained - prior_state.pc1_explained
            pc1_acceleration = pc1_velocity - prior_state.pc1_velocity
        else:
            pc1_velocity = 0.0
            pc1_acceleration = 0.0
        
        # Config hash
        config_str = f"{universe_key}_{window}_{self.shrinkage}_{N}"
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]
        
        return PCAState(
            as_of=datetime.now().isoformat(),
            window_days=window,
            universe_key=universe_key,
            tickers=tuple(tickers),
            N=N,
            T=T,
            eigenvalues=tuple(eigenvalues.tolist()),
            eigenvectors=eigenvectors,
            K=K,
            explained_variance=tuple(explained.tolist()),
            cumulative_variance=tuple(cumulative.tolist()),
            entropy=entropy,
            normalized_entropy=normalized_entropy,
            participation_ratio=participation_ratio,
            effective_dimensions=effective_dims,
            eigen_gini=eigen_gini,
            pc1_explained=pc1_explained,
            pc1_velocity=pc1_velocity,
            pc1_acceleration=pc1_acceleration,
            config_hash=config_hash,
            market_state_hash=market_state_hash,
        )
    
    def build_timeline(
        self,
        returns: pd.DataFrame,
        window: int,
        universe_key: str,
        market_state_hash: str,
        num_points: int = 60,
        step: int = 1,
    ) -> PCATimeline:
        """
        Build a timeline of PCA states for historical analysis.
        
        Args:
            returns: Full returns DataFrame
            window: PCA window size
            universe_key: Universe identifier
            market_state_hash: Source hash
            num_points: Number of points in timeline
            step: Days between points
        
        Returns:
            PCATimeline with historical states
        """
        states = []
        prior_state = None
        
        # Work backwards from end
        end_idx = len(returns)
        
        for i in range(num_points):
            point_end = end_idx - (i * step)
            point_start = point_end - window
            
            if point_start < 0:
                break
            
            rets_slice = returns.iloc[point_start:point_end]
            
            try:
                state = self.build_state(
                    rets_slice,
                    window=window,
                    universe_key=universe_key,
                    market_state_hash=f"{market_state_hash}_{i}",
                    prior_state=prior_state,
                )
                states.append(state)
                prior_state = state
            except ValueError as e:
                logger.warning(f"Timeline point {i} failed: {e}")
                continue
        
        # Reverse to chronological order
        states = states[::-1]
        
        return PCATimeline(
            states=tuple(states),
            window_days=window,
            universe_key=universe_key,
        )
    
    async def build_from_market_state(
        self,
        market_state,  # MarketStateV2
        windows: Optional[Tuple[int, ...]] = None,
    ) -> Dict[int, PCAState]:
        """
        Build PCA states for multiple windows from a MarketState.
        
        Returns:
            Dict mapping window -> PCAState
        """
        if windows is None:
            windows = self.windows
        
        results = {}
        prior_states = {}
        
        for window in sorted(windows):
            try:
                state = self.build_state(
                    returns=market_state.returns,
                    window=window,
                    universe_key=market_state.universe_key,
                    market_state_hash=market_state.metadata.state_hash,
                    prior_state=prior_states.get(window),
                )
                results[window] = state
                prior_states[window] = state
                
            except Exception as e:
                logger.error(f"PCA build failed for window {window}: {e}")
        
        return results


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_pca_builder = PCAStateBuilder()

async def compute_pca_state(
    market_state,  # MarketStateV2
    window: int = 60,
) -> PCAState:
    """Compute PCA state for a single window."""
    states = await _pca_builder.build_from_market_state(
        market_state,
        windows=(window,),
    )
    return states.get(window)


async def compute_pca_multi_horizon(
    market_state,  # MarketStateV2
    windows: Tuple[int, ...] = (20, 60, 120),
) -> Dict[int, PCAState]:
    """Compute PCA states for multiple windows."""
    return await _pca_builder.build_from_market_state(
        market_state,
        windows=windows,
    )


def compute_pca_timeline(
    returns: pd.DataFrame,
    window: int = 60,
    universe_key: str = "UNKNOWN",
    num_points: int = 60,
) -> PCATimeline:
    """Compute PCA timeline for historical analysis."""
    return _pca_builder.build_timeline(
        returns=returns,
        window=window,
        universe_key=universe_key,
        market_state_hash="timeline",
        num_points=num_points,
    )
