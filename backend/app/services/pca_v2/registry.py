"""Registry for PCA V2 feature modules.

Feature imports are deferred until discovery or execution. The mounted API and
Python callers share the same declarations and validation.
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


def validate_payload(feature_id, payload):
    import json
    import math
    from .features.inputs import inputs_for
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object")
    payload = dict(payload)
    for field in inputs_for(normalize_feature_id(feature_id)):
        key = field["key"]
        if key not in payload or payload[key] is None or payload[key] == "":
            continue
        value = payload[key]
        if field["type"] == "number":
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            number = float(value)
            if not math.isfinite(number) or (field.get("min") is not None and number < field["min"]) or (field.get("max") is not None and number > field["max"]):
                raise ValueError(f"{key} outside supported range")
            payload[key] = number
        elif field["type"] == "json" and isinstance(value, str):
            try:
                payload[key] = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{key} must contain valid JSON") from exc
        elif field["type"] == "select" and value not in field["options"]:
            raise ValueError(f"Unsupported {key}: {value}")
        elif field["type"] == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{key} must be boolean")
    return payload


def run_feature(feature_id: str | int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_pca_v2_feature(feature_id)
    payload = validate_payload(feature.id, payload or {})
    from .core.uploads import resolve_payload
    result = get_runner(feature.id)(resolve_payload(payload))
    module = importlib.import_module(f"app.services.pca_v2.features.{feature.module}")
    missing = []
    for output in module.OUTPUTS:
        source = result.get(output["source"], {})
        if output["key"] not in source:
            raise RuntimeError(f"Missing declared output: {output['key']}")
        if source[output["key"]] is None or source[output["key"]] == [] or source[output["key"]] == {}:
            missing.append({"key":output["key"], "source":output["source"], "reason":"Not produced: option not enabled or insufficient eligible observations; see study metadata."})
    result.setdefault("meta", {})["missing_outputs"] = missing
    return result


def feature_manifest():
    features = []
    for feature in PCA_V2_FEATURES.values():
        module = importlib.import_module(f"app.services.pca_v2.features.{feature.module}")
        features.append({"id": feature.id, "title": feature.title, "status": feature.status,
                         "inputs": module.INPUTS, "outputs": module.OUTPUTS})
    return features
