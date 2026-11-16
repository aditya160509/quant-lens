"""st03 Validate."""

from __future__ import annotations

from typing import Any

from ..core import backtest, validate
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st03"
FEATURE_NAME = "Validate"
INPUTS = [*shared_inputs(),
          field("profile", "Profile", "select", "quick", "Validation", options=list(validate.PROFILES)),
          field("show_holdout", "Open the hold-out (logged)", "boolean", False, "Validation")]
OUTPUTS = [
    {"key": "tiles", "source": "tables", "render": "table", "label": "Tests", "primary": True},
    {"key": "verdict", "source": "tables", "render": "table", "label": "Scorecard"},
    {"key": "walk_forward", "source": "charts", "render": "lineChart", "label": "Stitched out-of-sample"},
    {"key": "windows", "source": "tables", "render": "table", "label": "Windows"},
    {"key": "vs_random", "source": "charts", "render": "table", "label": "Vs random"},
    {"key": "execution", "source": "tables", "render": "table", "label": "Execution"},
    {"key": "parameters", "source": "tables", "render": "table", "label": "Nearby settings"},
    {"key": "noise", "source": "tables", "render": "table", "label": "Noise"},
    {"key": "mcpt", "source": "tables", "render": "table", "label": "Permutation"},
    {"key": "lottery", "source": "charts", "render": "table", "label": "Luck lottery"},
    {"key": "luck", "source": "tables", "render": "table", "label": "Luck"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    spec, settings, sid, version = parse(payload)
    out = validate.run_validate(spec, settings, sid, version, str(payload.get("profile") or "quick"), payload.get("weights"), bool(payload.get("show_holdout")),
                                str(payload.get("_actor") or "human"), progress)
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    return backtest._clean(out)
