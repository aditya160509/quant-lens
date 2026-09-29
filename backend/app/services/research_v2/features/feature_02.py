"""R02 Robustness Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import response, robustness_outputs

FEATURE_ID = "02"
FEATURE_NAME = "Robustness Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 500},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "mode", "type": "select", "default": "sequential", "options": ["sequential", "specification_curve"]},
    {"key": "max_specifications", "type": "number", "default": 9},
    {"key": "lookback_days", "type": "number", "default": 2520},
]

OUTPUTS = [
    "robustness_matrix",
    "specification_curve",
    "curve_level_joint_p_value",
    "researcher_degrees_of_freedom",
    "decision_attribution_panel",
    "robustness_summary_line",
    "weakest_specification",
    "strongest_specification",
    "coefficient_stability",
    "economic_magnitude_range",
    "latex_export",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = robustness_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
