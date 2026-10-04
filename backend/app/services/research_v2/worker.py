"""Short-lived worker process entry for feature jobs, so memory returns to the OS when a job ends."""

from __future__ import annotations

from typing import Any, Dict


def run_in_worker(feature_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.research_v2.registry import run_feature

    return run_feature(feature_id, payload)


def run_special(kind: str, payload: Dict[str, Any], args: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Report card, batch screening and validation jobs (reports.py), one short-lived process each."""

    from app.services.research_v2 import reports

    args = args or {}
    if kind == "report_card":
        return reports.run_report_card(payload)
    if kind == "batch":
        return reports.run_batch(payload, list(args.get("signals") or []))
    if kind == "validation":
        return reports.run_validation(payload, str(args.get("method") or "walk_forward"), int(args.get("folds") or 5), int(args.get("embargo_days") or 30))
    raise KeyError(kind)
