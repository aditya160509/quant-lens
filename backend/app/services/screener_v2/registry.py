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
    return [{"id": feature.id, "name": feature.name, "inputs": feature.inputs, "outputs": feature.outputs}
            for feature in _build_registry().values()]


def run_feature(feature_id: int | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_feature(feature_id)
    module = _load(feature.module)
    runner: Callable[[dict[str, Any] | None], dict[str, Any]] = getattr(module, "run")
    from .core.data_loader import as_of_context, load_market_ohlcv
    from .features.inputs import normalize_payload
    payload = normalize_payload(feature.inputs, payload or {})
    cutoff = payload.get("as_of_date") or str(load_market_ohlcv().Date.max().date())
    payload = {**payload, "as_of_date": cutoff}
    with as_of_context(cutoff):
        result = runner(payload or {})
        if (payload or {}).get("screen_id"):
            from .core.state import save_run
            save_run(str(payload["screen_id"]), str(result.get("meta", {}).get("as_of_date") or payload.get("as_of_date") or "latest"), result)
        return result
