"""Feature registry for Screener V2."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from functools import lru_cache
from typing import Any, Callable


@dataclass(frozen=True)
class ScreenerFeature:
    id: str
    name: str
    module: str
    inputs: list[dict[str, Any]]
    outputs: list[str]


def _load(module: str):
    return import_module(f"{__package__}.features.{module}")

_MODULES = [f"feature_{i:02d}" for i in range(1, 9)]


@lru_cache(maxsize=1)
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


def get_feature(feature_id: int | str) -> ScreenerFeature:
    key = str(feature_id).replace("feature-", "").replace("feature_", "").zfill(2)
    registry = _build_registry()
    if key not in registry:
        raise KeyError(f"Unknown Screener V2 feature {feature_id}")
    return registry[key]


def feature_manifest() -> list[dict[str, Any]]:
    return [
        {"id": f.id, "name": f.name, "inputs": f.inputs, "outputs": f.outputs}
        for f in _build_registry().values()
    ]


def run_feature(feature_id: int | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_feature(feature_id)
    module = _load(feature.module)
    runner: Callable[[dict[str, Any] | None], dict[str, Any]] = getattr(module, "run")
    from .core.data_loader import as_of_context
    with as_of_context((payload or {}).get("as_of_date")):
        return runner(payload or {})
