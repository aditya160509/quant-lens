"""st03 Validate."""

from __future__ import annotations

from typing import Any

from ..core import backtest, validate
from .inputs import field, parse, shared_inputs

FEATURE_ID = "st03"
FEATURE_NAME = "Validate"
INPUTS = [*shared_inputs(),
          field("profile", "Profile", "select", "quick", "Validation", options=list(validate.PROFILES)),
          field("show_holdout", "Open the hold-out (logged)", "boolean", False, "Validation"),
          field("anchored", "Anchored walk-forward", "boolean", False, "Validation"),
          field("purge", "Purge bars", "number", 5, "Validation"),
          field("reopt", "Re-optimise each window", "boolean", True, "Validation"),
          field("volume_cap", "Volume cap (share of day)", "number", 0.01, "Validation"),
          field("sims", "Simulations", "number", 1000, "Validation", min=1, max=100000),
          field("seed", "Seed", "number", 7, "Validation")]
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
    {"key": "wf_matrix", "source": "tables", "render": "table", "label": "Walk-forward matrix"},
    {"key": "shocks", "source": "tables", "render": "table", "label": "Shocks"},
    {"key": "shifted", "source": "tables", "render": "table", "label": "Shifted starts"},
    {"key": "related", "source": "tables", "render": "table", "label": "Other names"},
    {"key": "cpcv", "source": "tables", "render": "table", "label": "CPCV paths"},
    {"key": "cpcv_paths", "source": "charts", "render": "lineChart", "label": "CPCV equity"},
    {"key": "pbo_pairs", "source": "tables", "render": "table", "label": "Rank in vs out"},
    {"key": "mc_trades", "source": "tables", "render": "table", "label": "Trade Monte Carlo"},
    {"key": "skip_trades", "source": "tables", "render": "table", "label": "Skipped trades and slippage"},
    {"key": "cost_sweep", "source": "tables", "render": "table", "label": "Cost sweep"},
    {"key": "regimes", "source": "tables", "render": "table", "label": "By regime"},
    {"key": "years", "source": "tables", "render": "table", "label": "By year"},
    {"key": "sanity", "source": "tables", "render": "table", "label": "Look-ahead and one-trade"},
    {"key": "unseen", "source": "tables", "render": "table", "label": "Unseen symbols"},
    {"key": "pbo_logits", "source": "charts", "render": "table", "label": "PBO logits"},
]


def run(payload: dict[str, Any] | None = None, progress=None) -> dict[str, Any]:
    payload = payload or {}
    spec, settings, sid, version = parse(payload)
    out = validate.run_validate(spec, settings, sid, version, str(payload.get("profile") or "quick"), payload.get("weights"), bool(payload.get("show_holdout")),
                                str(payload.get("_actor") or "human"), progress,
                                bool(payload.get("anchored")), int(payload.get("purge", 5) or 0), payload.get("reopt", True) is not False, float(payload.get("volume_cap", 0.01) or 0), int(payload.get("sims") or 1000))
    out["meta"]["strategy"] = {"id": sid, "version": version, "name": spec.name}
    return backtest._clean(out)
