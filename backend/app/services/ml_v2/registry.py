"""Registry for ML V2 feature modules.

No API routes are wired here. Future routers can import this single stable
entry point once ML V2 is ready to expose.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class MLFeature:
    id: str
    title: str
    module: str
    status: str = "backend_ready"


ML_V2_FEATURES: Dict[str, MLFeature] = {
    "01": MLFeature("01", "Purged K-Fold and CPCV Engine", "feature_01"),
    "02": MLFeature("02", "Gradient-Boosted Alpha Engine with Attribution", "feature_02"),
    "03": MLFeature("03", "Multi-Horizon Volatility Forecasting Engine", "feature_03"),
    "04": MLFeature("04", "Meta-Labeling and Triple-Barrier Label Engine", "feature_04"),
    "05": MLFeature("05", "Hierarchical Risk Parity Optimizer", "feature_05"),
    "06": MLFeature("06", "Market Regime Detection and Strategy Routing", "feature_06"),
    "07": MLFeature("07", "Bayesian Online Learning and DMA Engine", "feature_07"),
    "08": MLFeature("08", "IC-Weighted Composite Signal Optimizer", "feature_08"),
    "09": MLFeature("09", "ML-Enhanced Pairs and Stat Arb Engine", "feature_09"),
    "10": MLFeature("10", "Market Microstructure Signal Observatory", "feature_10"),
    "11": MLFeature("11", "Causal Factor Discovery Engine", "feature_11"),
    "12": MLFeature("12", "Deep Sequence Alpha Engine", "feature_12"),
}


def normalize_feature_id(feature_id: str | int) -> str:
    return str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)


def get_ml_v2_feature(feature_id: str | int) -> MLFeature:
    fid = normalize_feature_id(feature_id)
    if fid not in ML_V2_FEATURES:
        raise KeyError(f"Unknown ML V2 feature: {feature_id}")
    return ML_V2_FEATURES[fid]


def get_runner(feature_id: str | int) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    feature = get_ml_v2_feature(feature_id)
    module = importlib.import_module(f"app.services.ml_v2.features.{feature.module}")
    return module.run


def run_feature(feature_id: str | int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .core.data_loader import AS_OF_DATE
    import pandas as pd
    request = dict(payload or {})
    cutoff = request.get("as_of_date")
    cutoff = pd.Timestamp(cutoff) if cutoff is not None else None
    if cutoff is not None:
        if pd.isna(cutoff):
            raise ValueError("as_of_date must be a valid date")
        if cutoff.tzinfo is not None:
            cutoff = cutoff.tz_convert("UTC").tz_localize(None)
    token = AS_OF_DATE.set(cutoff)
    try:
        return get_runner(feature_id)(request)
    finally:
        AS_OF_DATE.reset(token)



def feature_manifest():
    from .features.inputs import inputs, outputs
    manifest = []
    for feature in ML_V2_FEATURES.values():
        module = importlib.import_module(f"app.services.ml_v2.features.{feature.module}")
        manifest.append({"id": feature.id, "title": module.FEATURE_TITLE,
            "status": feature.status, "inputs": inputs(module.INPUT_CONTRACT, module.DEFAULTS),
            "outputs": outputs(module.OUTPUT_CONTRACT), "known_limitations": module.RESEARCH_ONLY})
    return manifest
