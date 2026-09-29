"""Simple env-flag map for risky Studio paths — P15 hardening.

Flags gate renderer / worker / GPU-adjacent paths without new
infrastructure. All flags default to the safe (legacy) path and are read
from the environment so operators can toggle without a deploy. Frontend
mirrors this map in ``studioFeatureFlags.js``.
"""

from __future__ import annotations

import os

_FLAGS = {
    # Canonical canvas renderer stays default; WebGL remains opt-in.
    "STUDIO_RENDERER_WEBGL": "0",
    # Keep bounded ThreadPoolExecutor; an external worker pool stays off.
    "STUDIO_WORKER_EXTERNAL": "0",
    # No GPU execution path exists; flag reserves the kill-switch.
    "STUDIO_GPU_ENABLED": "0",
    # Opt-in parquet fast-scan path for large return panels.
    "STUDIO_PARQUET_FAST_SCAN": "0",
}


def is_enabled(name: str) -> bool:
    default = _FLAGS.get(name, "0")
    raw = os.environ.get(name, default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def snapshot() -> dict[str, bool]:
    return {name: is_enabled(name) for name in _FLAGS}
