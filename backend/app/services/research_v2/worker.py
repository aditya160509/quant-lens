"""Short-lived worker process entry for feature jobs, so memory returns to the OS when a job ends."""

from __future__ import annotations

from typing import Any, Dict


def run_in_worker(feature_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.research_v2.registry import run_feature

    return run_feature(feature_id, payload)
