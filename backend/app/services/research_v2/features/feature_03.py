"""R03 Placebo and Falsification Suite."""

from __future__ import annotations

from typing import Any

from ..core.analytics import placebo_outputs, response

FEATURE_ID = "03"
FEATURE_NAME = "Placebo and Falsification Suite"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 400},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "permutation_replications", "type": "number", "default": 500},
    {"key": "time_displacement_months", "type": "select", "default": 12, "options": [6, 12, 24]},
    {"key": "oos_split", "type": "select", "default": 0.7, "options": [0.5, 0.6, 0.7]},
]

OUTPUTS = [
    "permutation_placebo",
    "permutation_null_histogram",
    "time_displacement_placebo",
    "wrong_direction_placebo",
    "adjacent_asset_class_placebo",
    "mclean_pontiff_oos",
    "oos_coefficient_comparison",
    "combined_significance",
    "power_analysis",
    "falsification_verdict",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = placebo_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
