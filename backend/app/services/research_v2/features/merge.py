"""Section merges: one feature also returns another feature's outputs under a prefixed section.

Canonical + Diagnostics ("Model checks"), Robustness + Regimes, Decay + Factor zoo and
Causal designs + Synthetic control. The old feature ids keep working on their own.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _module(feature_id: str):
    return import_module(f"{__package__}.feature_{feature_id}")


def merged_inputs(inputs: list[dict[str, Any]], feature_id: str, section: str) -> list[dict[str, Any]]:
    """``inputs`` plus the other feature's inputs whose keys are new, grouped under ``section``."""

    have = {i["key"] for i in inputs}
    extra = [{**i, "group": section} for i in _module(feature_id).INPUTS if i["key"] not in have]
    return inputs + extra


def merged_outputs(outputs: list[dict[str, Any]], feature_id: str, prefix: str, section: str, conditional: bool = False) -> list[dict[str, Any]]:
    extra = [{**o, "key": f"{prefix}__{o['key']}", "primary": False, "section": section, **({"conditional": True} if conditional else {})} for o in _module(feature_id).OUTPUTS]
    return outputs + extra


def merge_result(result: dict[str, Any], other: dict[str, Any], prefix: str, section: str) -> dict[str, Any]:
    for k, v in other["tables"].items():
        result["tables"][f"{prefix}__{k}"] = v
    for k, v in other["charts"].items():
        result["charts"][f"{prefix}__{k}"] = v
    result["meta"].setdefault("sections", {})[section] = [f"{prefix}__{k}" for k in [*other["tables"], *other["charts"]]]
    return result


def run_merged(result: dict[str, Any], feature_id: str, payload: dict[str, Any], prefix: str, section: str) -> dict[str, Any]:
    """Run ``feature_id`` on the same payload (the cached panel is reused) and merge its outputs; a failure is recorded, not raised."""

    if payload.get("include_merged") is False:
        return result
    try:
        other = _module(feature_id).run(payload)
    except Exception as exc:
        result["tables"][f"{prefix}__status"] = [{"section": section, "status": "not run", "reason": str(exc)}]
        return result
    return merge_result(result, other, prefix, section)
