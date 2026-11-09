"""Feature registry for Screener V2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class ScreenerFeature:
    id: str
    name: str
    module: str
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]


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


def hash_versions() -> int:
    from .core.data_loader import MARKET_UNIVERSE, MASTER_FUNDAMENTALS
    from .core.performance import _path_version
    return _path_version(MARKET_UNIVERSE) ^ _path_version(MASTER_FUNDAMENTALS)


def run_feature(feature_id: int | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_feature(feature_id)
    module = _load(feature.module)
    runner: Callable[[dict[str, Any] | None], dict[str, Any]] = module.run
    from .core.currency import instrument_context
    from .core.data_loader import as_of_context, default_as_of, latest_market_date
    from .features.inputs import normalize_payload
    payload = normalize_payload(feature.inputs, payload or {})
    import pandas as pd
    latest = latest_market_date()
    if pd.isna(latest):
        raise ValueError("Market dataset has no observed dates")
    cutoff = payload.get("as_of_date") or default_as_of(payload)
    date = pd.Timestamp(cutoff)
    if pd.isna(date) or date.tzinfo is not None or date != date.normalize():
        raise ValueError("as_of_date must be an unzoned calendar date")
    if date > latest.normalize():
        raise ValueError("as_of_date exceeds the latest observed market date")
    payload = {**payload, "as_of_date": cutoff}
    with as_of_context(cutoff), instrument_context(payload):
        result = runner(payload or {})
        if (payload or {}).get("screen_id"):
            from .core.state import save_run
            save_run(str(payload["screen_id"]), str(result.get("meta", {}).get("as_of_date") or payload.get("as_of_date") or "latest"), result)
        meta = result.setdefault("meta", {})
        meta.setdefault("research_caveats", meta.get("limitations", []))
        meta["data_version"] = format(hash_versions(), "x")[-8:]
        return result
