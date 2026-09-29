"""R09 Synthetic Control Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import response, synthetic_control_outputs

FEATURE_ID = "09"
FEATURE_NAME = "Synthetic Control Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "treated_unit", "type": "ticker", "default": "AAPL"},
    {"key": "treatment_date", "type": "date", "default": None},
    {"key": "event_csv_path", "type": "file_path", "default": ""},
    {"key": "donor_limit", "type": "number", "default": 80},
    {"key": "lookback_days", "type": "number", "default": 2520},
    {"key": "scm_variant", "type": "select", "default": "classic", "options": ["classic", "augmented_proxy"]},
]

OUTPUTS = ["treated_vs_synthetic_path", "gap_plot", "donor_weight_table", "pre_treatment_fit", "rmspe_ratio_ranking", "leave_one_out_sensitivity", "in_time_placebo", "augmented_scm", "augmented_synthetic_path", "generalized_scm", "robust_matrix_completion_scm", "staggered_adoption_scm", "conformal_confidence_band", "latex_export"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = synthetic_control_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
