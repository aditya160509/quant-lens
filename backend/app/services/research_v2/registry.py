"""Feature registry for Research V2. Features load on first use."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any

FEATURE_MODULES = [*(f"feature_{i:02d}" for i in range(1, 10)), "feature_11"]  # the spec defines no Feature 10


@dataclass(frozen=True)
class ResearchFeature:
    id: str
    name: str
    description: str
    module: str
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]


def _load(module: str):
    return import_module(f"{__package__}.features.{module}")


@lru_cache(maxsize=1)
def features() -> dict[str, ResearchFeature]:
    out: dict[str, ResearchFeature] = {}
    for name in FEATURE_MODULES:
        m = _load(name)
        out[str(m.FEATURE_ID).zfill(2)] = ResearchFeature(str(m.FEATURE_ID).zfill(2), m.FEATURE_NAME, m.DESCRIPTION, name, m.INPUTS, m.OUTPUTS)
    return out


def normalize_id(feature_id: int | str) -> str:
    return str(feature_id).replace("feature-", "").replace("feature_", "").zfill(2)


def get_feature(feature_id: int | str) -> ResearchFeature:
    key = normalize_id(feature_id)
    if key not in features():
        raise KeyError(f"Unknown Research V2 feature {feature_id}")
    return features()[key]


def feature_manifest() -> list[dict[str, Any]]:
    return [{"id": f.id, "name": f.name, "description": f.description, "inputs": f.inputs, "outputs": f.outputs} for f in features().values()]


def run_feature(feature_id: int | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = get_feature(feature_id)
    return _load(feature.module).run(payload or {})
