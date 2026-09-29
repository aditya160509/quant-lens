"""Registry for Volatility V2 feature modules.

The implementation mirrors the Factors V2 package shape but remains dormant
until the API/router and frontend are explicitly wired.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class VolatilityFeature:
    id: str
    title: str
    module: str
    status: str = "scaffolded"


VOLATILITY_V2_FEATURES: Dict[str, VolatilityFeature] = {
    "01": VolatilityFeature("01", "Multi-Estimator Daily Volatility Engine", "feature_01"),
    "02": VolatilityFeature("02", "GARCH Family Suite", "feature_02"),
    "03": VolatilityFeature("03", "HAR Forecasting Suite", "feature_03"),
    "04": VolatilityFeature("04", "Volatility Regime Detection Engine", "feature_04"),
    "05": VolatilityFeature("05", "Volatility Risk Premium Monitor", "feature_05"),
    "06": VolatilityFeature("06", "Cross-Asset Volatility Connectedness", "feature_06"),
    "07": VolatilityFeature("07", "Multivariate Volatility and DCC Engine", "feature_07"),
    "08": VolatilityFeature("08", "Volatility Stress Testing Engine", "feature_08"),
    "09": VolatilityFeature("09", "Volatility Budget Monitor", "feature_09"),
}


def get_volatility_v2_feature(feature_id: str) -> VolatilityFeature:
    fid = str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)
    if fid not in VOLATILITY_V2_FEATURES:
        raise KeyError(f"Unknown Volatility V2 feature: {feature_id}")
    return VOLATILITY_V2_FEATURES[fid]


def get_runner(feature_id: str) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    feature = get_volatility_v2_feature(feature_id)
    module = importlib.import_module(f"app.services.volatility_v2.features.{feature.module}")
    return module.run


def run_feature(feature_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_runner(feature_id)(payload or {})
