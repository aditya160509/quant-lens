"""Volatility V2 feature modules.

This package-level index mirrors the Factors V2 feature-module shape: every
feature file exposes a ``run(payload)`` function, and this module exports stable
aliases plus a small runner map for direct service-layer use. It does not wire
HTTP routes by itself.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from .feature_01 import run as run_feature_01
from .feature_02 import run as run_feature_02
from .feature_03 import run as run_feature_03
from .feature_04 import run as run_feature_04
from .feature_05 import run as run_feature_05
from .feature_06 import run as run_feature_06
from .feature_07 import run as run_feature_07
from .feature_08 import run as run_feature_08
from .feature_09 import run as run_feature_09


VOLATILITY_V2_RUNNERS: Dict[str, Callable[[dict[str, Any] | None], dict[str, Any]]] = {
    "01": run_feature_01,
    "02": run_feature_02,
    "03": run_feature_03,
    "04": run_feature_04,
    "05": run_feature_05,
    "06": run_feature_06,
    "07": run_feature_07,
    "08": run_feature_08,
    "09": run_feature_09,
}


def get_feature_runner(feature_id: str) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    normalized = str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)
    if normalized not in VOLATILITY_V2_RUNNERS:
        raise KeyError(f"Unknown Volatility V2 feature: {feature_id}")
    return VOLATILITY_V2_RUNNERS[normalized]


def run_feature(feature_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_feature_runner(feature_id)(payload or {})


__all__ = [
    "VOLATILITY_V2_RUNNERS",
    "get_feature_runner",
    "run_feature",
    "run_feature_01",
    "run_feature_02",
    "run_feature_03",
    "run_feature_04",
    "run_feature_05",
    "run_feature_06",
    "run_feature_07",
    "run_feature_08",
    "run_feature_09",
]
