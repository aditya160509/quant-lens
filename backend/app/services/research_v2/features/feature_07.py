"""R07 Causal Identification Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import causal_outputs, response

FEATURE_ID = "07"
FEATURE_NAME = "Causal Identification Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "treated_unit", "type": "ticker", "default": "AAPL"},
    {"key": "treatment_date", "type": "date", "default": None},
    {"key": "event_csv_path", "type": "file_path", "default": ""},
    {"key": "instrument_csv_path", "type": "file_path", "default": ""},
    {"key": "identification_design", "type": "select", "default": "event_study", "options": ["event_study", "did", "iv", "rdd", "matching"]},
    {"key": "lookback_days", "type": "number", "default": 2520},
]

OUTPUTS = [
    "difference_in_differences",
    "parallel_trends_pretest",
    "placebo_treatment",
    "goodman_bacon_decomposition",
    "callaway_santanna_att",
    "sun_abraham_event_study",
    "event_study_path",
    "event_study_car",
    "event_study_tests",
    "calendar_time_portfolio_alpha",
    "pre_event_drift",
    "post_event_reversal",
    "matching_balance",
    "instrumental_variables",
    "regression_discontinuity",
    "rdd_bandwidth_sensitivity",
    "rdd_placebo_cutoffs",
    "rdd_mccrary_density_test",
    "rdd_ik_bandwidth",
    "rdd_covariate_continuity",
    "rdd_donut_hole",
    "treatment_timeline",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = causal_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
