"""Studio v3 features: one id per job (PAGES §0)."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any

_MODULES = ["feature_01", "feature_02", "feature_03", "feature_04"]


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    return {m.FEATURE_ID: m for m in (import_module(f"{__package__}.features.{name}") for name in _MODULES)}


def get_feature(feature_id: str):
    key = str(feature_id)
    key = key if key.startswith("st") else f"st{key.zfill(2)}"
    if key not in _registry():
        raise KeyError(f"Unknown Studio feature {feature_id}")
    return _registry()[key]


def feature_manifest() -> list[dict[str, Any]]:
    return [{"id": m.FEATURE_ID, "name": m.FEATURE_NAME, "inputs": m.INPUTS, "outputs": m.OUTPUTS} for m in _registry().values()]


def run_feature(feature_id: str, payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    return get_feature(feature_id).run(payload or {}, progress)
