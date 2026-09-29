"""Registry for PCA V2 feature modules.

No API routes are wired here. The registry exists so future routers can import a
single stable entry point once the backend is ready to expose PCA V2.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class PCAFeature:
    id: str
    title: str
    module: str
    status: str = "backend_ready"


PCA_V2_FEATURES: Dict[str, PCAFeature] = {
    "01": PCAFeature("01", "RMT Noise-Filtered Covariance Engine", "feature_01"),
    "02": PCAFeature("02", "PCA Factor Extraction and Loading Matrix", "feature_02"),
    "03": PCAFeature("03", "PCA Portfolio Risk Decomposition and Attribution", "feature_03"),
    "04": PCAFeature("04", "PCA Residual OU Statistical Arbitrage Signal Engine", "feature_04"),
    "05": PCAFeature("05", "Rolling Eigenvalue Stability and Regime Transition Monitor", "feature_05"),
    "06": PCAFeature("06", "Constrained PCA Portfolio Optimization with RMT Covariance", "feature_06"),
    "07": PCAFeature("07", "Out-of-Sample Bootstrap Validation and Factor Genuineness Scorecard", "feature_07"),
    "08": PCAFeature("08", "PCA Residual Cross-Correlation and Contagion Monitor", "feature_08"),
    "09": PCAFeature("09", "PCA Stress Scenario Generator and PC-Shock P&L Attribution", "feature_09"),
    "10": PCAFeature("10", "Cross-Asset RMT Covariance Engine with Hedged Block Decomposition", "feature_10"),
    "11": PCAFeature("11", "Latent Liquidity Factor Extraction and LaVaR", "feature_11"),
}


def normalize_feature_id(feature_id: str | int) -> str:
    return str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)


def get_pca_v2_feature(feature_id: str | int) -> PCAFeature:
    fid = normalize_feature_id(feature_id)
    if fid not in PCA_V2_FEATURES:
        raise KeyError(f"Unknown PCA V2 feature: {feature_id}")
    return PCA_V2_FEATURES[fid]


def get_runner(feature_id: str | int) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    feature = get_pca_v2_feature(feature_id)
    module = importlib.import_module(f"app.services.pca_v2.features.{feature.module}")
    return module.run


def run_feature(feature_id: str | int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_runner(feature_id)(payload or {})

