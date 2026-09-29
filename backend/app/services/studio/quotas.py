"""Central Studio quota configuration — P15 hardening.

Collects the previously scattered ``STUDIO_MAX_*`` / compute / storage
limits into one map so operators tune a single surface. Existing services
keep their own enforcement call-sites; they now read through
:func:`get_quota` for consistent defaults.

Open (documented, not implemented here): per-tenant quota accounting.
Global counters (``SQLiteStore.count``) bound total objects, but usage is
not yet attributed per owner. See ``docs/evidence/studio/P15/operations.md``.
"""

from __future__ import annotations

import os

DEFAULTS: dict[str, int] = {
    # Object-count quotas (pre-existing, now centralized)
    "STUDIO_MAX_PORTFOLIO_VERSIONS": 200,
    "STUDIO_MAX_PAPER_DEPLOYMENTS": 100,
    "STUDIO_MAX_REPORT_RECIPES": 200,
    "STUDIO_MAX_RESEARCH_NOTES": 500,
    "STUDIO_MAX_CERTIFICATIONS": 500,
    # Rate / concurrency (mirror middleware + job executor bounds)
    "STUDIO_RATE_PER_MINUTE": 120,
    "STUDIO_RATE_PER_HOUR": 3000,
    "STUDIO_MAX_CONCURRENT_JOBS": 2,
    # Compute budgets (mirror algorithm-lab ComputeBudget + execution caps)
    "STUDIO_MAX_CODE_BYTES": 64 * 1024,
    "STUDIO_MAX_RESPONSE_BYTES": 4 * 1024 * 1024,
    "STUDIO_MAX_SIGNALS": 100_000,
    "STUDIO_MAX_SIMULATIONS": 10_000,
    # Storage (mirror upload catalog owner quota default)
    "STUDIO_OWNER_QUOTA_BYTES": 512 * 1024 * 1024,
}


def get_quota(name: str, default: int | None = None) -> int:
    fallback = DEFAULTS.get(name, default if default is not None else 0)
    try:
        return int(os.environ.get(name, fallback))
    except (TypeError, ValueError):
        return int(fallback)


def snapshot() -> dict[str, int]:
    """Return the resolved quota map (values only, no secrets)."""
    return {name: get_quota(name) for name in DEFAULTS}
