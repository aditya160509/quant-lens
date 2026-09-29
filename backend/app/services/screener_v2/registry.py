"""Feature registry for Screener V2."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable


@dataclass(frozen=True)
class ScreenerFeature:
    id: str
    name: str
    module: str
    inputs: list[dict[str, Any]]
    outputs: list[str]


def _load(module: str):
    try:
        return import_module(f"app.services.screener_v2.features.{module}")
    except ModuleNotFoundError:
        return import_module(f"backend.app.services.screener_v2.features.{module}")


_MODULES = [f"feature_{i:02d}" for i in range(1, 9)]


def _build_registry() -> dict[str, ScreenerFeature]:
    registry: dict[str, ScreenerFeature] = {}
    for module_name in _MODULES:
        module = _load(module_name)
        feature = ScreenerFeature(
            id=str(module.FEATURE_ID).zfill(2),
            name=module.FEATURE_NAME,
            module=module_name,
            inputs=getattr(module, "INPUTS", []),
            outputs=getattr(module, "OUTPUTS", []),
        )
        registry[feature.id] = feature
    return registry


FEATURES = _build_registry()


def get_feature(feature_id: int | str) -> ScreenerFeature:
    key = str(feature_id).replace("feature-", "").replace("feature_", "").zfill(2)
    if key not in FEATURES:
        raise KeyError(f"Unknown Screener V2 feature {feature_id}")
    return FEATURES[key]


def feature_manifest() -> list[dict[str, Any]]:
    return [
        {"id": f.id, "name": f.name, "inputs": f.inputs, "outputs": f.outputs}
        for f in FEATURES.values()
    ]


def run_feature(feature_id: int | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_feature(feature_id)
    module = _load(feature.module)
    runner: Callable[[dict[str, Any] | None], dict[str, Any]] = getattr(module, "run")
    return runner(payload or {})
