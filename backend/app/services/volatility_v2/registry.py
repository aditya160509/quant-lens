"""Registry for Volatility V2 feature modules.

Feature declarations are imported lazily and exposed by the mounted API.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict
from .core.data_loader import request_scope, resolve_symbols
from copy import deepcopy


@dataclass(frozen=True)
class VolatilityFeature:
    id: str
    title: str
    module: str
    status: str = "implemented"


VOLATILITY_V2_FEATURES: Dict[str, VolatilityFeature] = {
    "01": VolatilityFeature(
        "01", "Multi-Estimator Daily Volatility Engine", "feature_01"
    ),
    "02": VolatilityFeature("02", "GARCH Family Suite", "feature_02"),
    "03": VolatilityFeature("03", "HAR Forecasting Suite", "feature_03"),
    "04": VolatilityFeature("04", "Volatility Regime Detection Engine", "feature_04"),
    "05": VolatilityFeature("05", "Volatility Risk Premium Monitor", "feature_05"),
    "06": VolatilityFeature("06", "Cross-Asset Volatility Connectedness", "feature_06"),
    "07": VolatilityFeature(
        "07", "Multivariate Volatility and DCC Engine", "feature_07"
    ),
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
    module = importlib.import_module(
        f"app.services.volatility_v2.features.{feature.module}"
    )
    return module.run


def run_feature(
    feature_id: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    prepared = prepare_payload(feature_id, payload)
    with request_scope(prepared):
        return get_runner(feature_id)(prepared)


def feature_manifest():
    """Import feature declarations only on demand, never at package import."""
    return [contract_for(fid) for fid in VOLATILITY_V2_FEATURES]


def contract_for(feature_id):
    feature = get_volatility_v2_feature(feature_id)
    module = importlib.import_module(
        f"app.services.volatility_v2.features.{feature.module}"
    )
    return deepcopy(
        {
            "feature_id": feature.id,
            "id": feature.id,
            "title": feature.title,
            "status": feature.status,
            "aliases": {
                alias: key
                for alias, key in ALIASES.items()
                if key in {field["key"] for field in module.INPUTS}
            },
            "inputs": module.INPUTS,
            "outputs": module.OUTPUTS,
        }
    )


ALIASES = {
    "window_days": "rolling_window",
    "symbol": "asset",
    "ticker": "asset",
    "symbols": "assets",
    "universe": "assets",
    "end_date": "as_of_date",
    "target_vol": "vol_target",
    "rebalance_frequency": "rebalance_trigger",
    "asset_pair": "factor_pair",
    "volatility_estimator": "estimator",
    "forecast_horizons": "horizons",
    "har_variants": "models",
    "monte_carlo_paths": "mc_paths",
    "covariance_estimator": "forecast_source",
    "gross_exposure_constraint": "gross_exposure_cap",
    "cost_bps": "explicit_bps",
}


def prepare_payload(feature_id, payload=None):
    from .features.inputs import coerce

    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Feature payload must be an object")
    contract = contract_for(feature_id)
    definitions = {field["key"]: field for field in contract["inputs"]}
    payload = dict(payload)
    for alias, key in ALIASES.items():
        if alias in payload:
            if key in payload and payload[key] != payload[alias]:
                raise ValueError(f"Conflicting {alias} and {key}")
            payload[key] = payload.pop(alias)
    unknown = set(payload) - set(definitions)
    if unknown:
        raise ValueError(
            "Unsupported controls for this feature: " + ", ".join(sorted(unknown))
        )
    prepared = {key: coerce(value, definitions[key]) for key, value in payload.items()}
    # Null controls are omitted: the documented conditional defaults remain in the engine.
    prepared = {key: value for key, value in prepared.items() if value is not None}
    if "assets" in prepared:
        prepared["assets"] = resolve_symbols(prepared["assets"])
    if "asset" in prepared:
        primary = resolve_symbols([prepared["asset"]])[0]
        if "assets" in prepared and primary not in prepared["assets"]:
            raise ValueError("Primary asset must belong to assets")
        if "assets" in prepared:
            prepared["assets"] = [primary] + [
                a for a in prepared["assets"] if a != primary
            ]
        prepared["asset"] = primary
    if "as_of_date" in prepared:
        from .core.data_loader import cutoff

        with request_scope(prepared):
            cutoff()
    return prepared
