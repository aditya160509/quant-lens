"""
Macro Lab - Regime Engine
PCA factor spine + regime classification
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RegimeOutput:
    """Output from regime classification."""
    label: str
    transition_probability: float
    stability_score: float
    top_drivers: List[Dict]
    pca_factors: Dict[str, float]
    confidence: float


def robust_zscore(x: np.ndarray) -> np.ndarray:
    """
    Compute robust z-score using median and MAD.
    
    Pseudocode:
    z = (x - median(x)) / MAD(x)
    """
    median = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - median))
    if mad == 0:
        mad = 1e-6
    return (x - median) / (1.4826 * mad)


def standardize(X: np.ndarray) -> np.ndarray:
    """
    Standardize feature matrix.
    
    Pseudocode:
    Z = (X - mean(X)) / std(X)
    """
    mean = np.nanmean(X, axis=0)
    std = np.nanstd(X, axis=0)
    std[std == 0] = 1e-6
    return (X - mean) / std


def pca_fit(Z: np.ndarray, k: int = 4) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fit PCA on standardized feature matrix.
    
    Pseudocode:
    X = build_feature_matrix(features, window)
    Z = standardize(X)
    W, var = PCA_fit(Z, k)
    F = Z * W
    return F, W, var
    """
    # Handle missing values
    Z_clean = np.nan_to_num(Z, nan=0.0)
    
    # Compute covariance matrix
    cov = np.cov(Z_clean.T)
    
    # Eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    
    # Sort by eigenvalue (descending)
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    # Select top k components
    W = eigenvectors[:, :k]
    var = eigenvalues[:k] / np.sum(eigenvalues)
    
    # Project data
    F = Z_clean @ W
    
    return F, W, var


def sigmoid(x: float) -> float:
    """Sigmoid function."""
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))


class RegimeEngine:
    """
    Global Regime Engine.
    
    Inputs:
    - inflation trend and surprise
    - growth trend and surprise
    - policy stance and shifts
    - liquidity and funding stress
    - volatility and correlation regime
    
    Models:
    - PCA factor spine (required)
    - Logistic classifier for regime probabilities
    """
    
    def __init__(self):
        self.feature_names = [
            "inflation_trend",
            "inflation_surprise",
            "growth_trend",
            "growth_surprise",
            "policy_stance",
            "policy_shift",
            "liquidity_level",
            "funding_stress",
            "volatility",
            "correlation"
        ]
        self.pca_loadings = None
        self.pca_variance = None
        self.last_update = None
    
    def compute_regime(
        self,
        features: Dict[str, float],
        history: Optional[np.ndarray] = None
    ) -> RegimeOutput:
        """
        Compute current regime from feature inputs.
        
        Returns regime label, stability, drivers, and PCA factors.
        """
        # Extract feature vector
        feature_vector = np.array([
            features.get(name, 0.0) for name in self.feature_names
        ])
        
        # If we have history, compute PCA
        if history is not None and len(history) > 10:
            Z = standardize(history)
            factors, self.pca_loadings, self.pca_variance = pca_fit(Z, k=4)
            
            # Project current observation
            current_z = standardize(feature_vector.reshape(1, -1))
            current_factors = (current_z @ self.pca_loadings).flatten()
        else:
            # Use simplified factor computation
            current_factors = self._compute_simplified_factors(features)
        
        # Classify regime
        regime_label, regime_prob = self._classify_regime(current_factors, features)
        
        # Compute stability score
        stability = self._compute_stability(features, current_factors)
        
        # Get top drivers
        drivers = self._get_top_drivers(features)
        
        # Build PCA factors dict
        pca_factors = {
            "growth_factor": float(current_factors[0]) if len(current_factors) > 0 else 0.0,
            "inflation_factor": float(current_factors[1]) if len(current_factors) > 1 else 0.0,
            "risk_factor": float(current_factors[2]) if len(current_factors) > 2 else 0.0,
            "liquidity_factor": float(current_factors[3]) if len(current_factors) > 3 else 0.0
        }
        
        self.last_update = datetime.utcnow()
        
        return RegimeOutput(
            label=regime_label,
            transition_probability=1.0 - regime_prob,
            stability_score=stability,
            top_drivers=drivers,
            pca_factors=pca_factors,
            confidence=regime_prob
        )
    
    def _compute_simplified_factors(self, features: Dict[str, float]) -> np.ndarray:
        """Compute simplified factors when no history available."""
        growth_factor = (
            features.get("growth_trend", 0) * 0.5 +
            features.get("growth_surprise", 0) * 0.3 +
            features.get("liquidity_level", 0) * 0.2
        )
        
        inflation_factor = (
            features.get("inflation_trend", 0) * 0.6 +
            features.get("inflation_surprise", 0) * 0.4
        )
        
        risk_factor = (
            features.get("volatility", 0) * 0.5 +
            features.get("funding_stress", 0) * 0.3 +
            features.get("correlation", 0) * 0.2
        )
        
        liquidity_factor = (
            features.get("liquidity_level", 0) * 0.6 +
            features.get("policy_stance", 0) * 0.4
        )
        
        return np.array([growth_factor, inflation_factor, risk_factor, liquidity_factor])
    
    def _classify_regime(
        self,
        factors: np.ndarray,
        features: Dict[str, float]
    ) -> Tuple[str, float]:
        """
        Classify regime based on factors.
        
        Regimes:
        - risk_on: Growth positive, low vol, loose policy
        - risk_off: Growth negative, high vol, tight policy
        - inflation_up: Inflation rising, growth mixed
        - inflation_down: Inflation falling
        - growth_slowdown: Growth falling, policy shifting
        - neutral: Mixed signals
        """
        growth = factors[0] if len(factors) > 0 else 0
        inflation = factors[1] if len(factors) > 1 else 0
        risk = factors[2] if len(factors) > 2 else 0
        liquidity = factors[3] if len(factors) > 3 else 0
        
        # Compute regime scores
        risk_on_score = growth * 0.4 - risk * 0.3 + liquidity * 0.3
        risk_off_score = -growth * 0.3 + risk * 0.5 - liquidity * 0.2
        inflation_score = inflation * 0.7 + growth * 0.3
        
        # Determine dominant regime
        scores = {
            "risk_on": risk_on_score,
            "risk_off": risk_off_score,
            "inflation_up": inflation_score if inflation > 0 else -10,
            "inflation_down": -inflation_score if inflation < 0 else -10,
            "growth_slowdown": -growth * 0.8 if growth < 0 else -10,
            "neutral": 0
        }
        
        best_regime = max(scores, key=scores.get)
        best_score = scores[best_regime]
        
        # Convert to probability using softmax-like transformation
        total = sum(np.exp(s) for s in scores.values())
        prob = np.exp(best_score) / total if total > 0 else 0.5
        
        return best_regime, min(prob, 0.95)
    
    def _compute_stability(
        self,
        features: Dict[str, float],
        factors: np.ndarray
    ) -> float:
        """
        Compute regime stability score (0-100).
        
        Low volatility, low dispersion = high stability.
        """
        vol = abs(features.get("volatility", 0))
        stress = abs(features.get("funding_stress", 0))
        factor_dispersion = np.std(factors) if len(factors) > 0 else 0
        
        # Inverse relationship: lower instability = higher score
        instability = vol * 0.4 + stress * 0.3 + factor_dispersion * 0.3
        stability = 100 * (1 - sigmoid(instability - 0.5))
        
        return max(0, min(100, stability))
    
    def _get_top_drivers(self, features: Dict[str, float], top_n: int = 3) -> List[Dict]:
        """
        Get top contributing drivers to regime.
        """
        drivers = []
        
        for name, value in features.items():
            if abs(value) > 0.01:
                drivers.append({
                    "name": name.replace("_", " ").title(),
                    "contribution": int(abs(value) * 100),
                    "direction": "up" if value > 0 else "down",
                    "confidence": min(0.95, 0.5 + abs(value) * 0.3)
                })
        
        # Sort by contribution
        drivers.sort(key=lambda x: x["contribution"], reverse=True)
        
        return drivers[:top_n]


# Global instance
_regime_engine = RegimeEngine()


def get_current_regime(features: Dict[str, float]) -> Dict:
    """Get current regime as dictionary."""
    result = _regime_engine.compute_regime(features)
    
    return {
        "label": result.label,
        "transition_probability": result.transition_probability,
        "stability_score": result.stability_score,
        "top_drivers": result.top_drivers,
        "pca_factors": result.pca_factors,
        "confidence": result.confidence
    }


def compute_regime_from_series(series_data: Dict[str, List[float]]) -> Dict:
    """
    Compute regime from raw time series data.
    
    Expects dict with keys like 'inflation', 'growth', 'volatility', etc.
    """
    features = {}
    
    for name, values in series_data.items():
        if values and len(values) > 0:
            current = values[-1]
            
            if len(values) > 20:
                trend = np.mean(values[-5:]) - np.mean(values[-20:-5])
                surprise = current - np.mean(values[-20:])
            else:
                trend = 0
                surprise = 0
            
            features[f"{name}_trend"] = trend
            features[f"{name}_surprise"] = surprise
    
    return get_current_regime(features)
