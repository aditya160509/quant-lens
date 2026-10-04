"""Feature 04: Meta-labeling and triple-barrier label engine."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.barriers import run_triple_barrier


FEATURE_ID = "04"
FEATURE_TITLE = "Meta-Labeling and Triple-Barrier Label Engine"

DEFAULTS: dict[str, Any] = {
    "profit_taking_barrier": 0.05,
    "stop_loss_barrier": 0.03,
    "max_holding_period": 21,
    "primary_side_model": "momentum_sign",
    "confidence_level": 0.90,
    "barrier_mode": "fixed",
    "barrier_side": "bilateral",
    "position_sizing": "probability",
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"pt": "profit_taking_barrier", "sl": "stop_loss_barrier", "holding_period": "max_holding_period", "horizon": "max_holding_period"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "profit_taking_barrier", "type": "float", "default": 0.05},
    {"key": "stop_loss_barrier", "type": "float", "default": 0.03},
    {"key": "max_holding_period", "type": "integer", "options": [5, 10, 21, 63], "default": 21},
    {"key": "barrier_mode", "type": "select", "options": ["fixed", "vol_scaled"], "default": "fixed"},
    {"key": "barrier_side", "type": "select", "options": ["bilateral", "long_only", "short_only"], "default": "bilateral"},
    {"key": "position_sizing", "type": "select", "options": ["probability", "kelly", "binary"], "default": "probability"},
    {"key": "primary_side_model", "type": "select", "options": ["momentum_sign", "external_model_upload", "feature_02_predictions"], "default": "momentum_sign"},
    {"key": "confidence_level", "type": "select", "options": [0.8, 0.9, 0.95], "default": 0.9},
]

OUTPUT_CONTRACT = [
    {"key": "triple_barrier_label_distribution", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "event_outcome_timeline", "location": "charts", "renderer": "timeline", "status": "live"},
    {"key": "meta_label_probability_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "cqr_interval_width_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "cqr_coverage_audit", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "barrier_hit_path_examples", "location": "charts", "renderer": "path_table", "status": "live"},
    {"key": "label_method_comparison", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "barrier_sensitivity_surface", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "label_audit", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "barrier_parameters", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "barrier_sensitivity", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["external primary model upload", "feature-store event timestamp ingestion"]
IMPLEMENTATION_NOTES = [
    "Labels are generated from forward local returns with explicit PT/SL/max-hold barriers.",
    "CQR bands use LightGBM lower/upper quantile models with chronological conformal calibration and volatility fallback only when the quantile fit is unavailable.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["external_model_upload", "quantile_cqr"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_triple_barrier(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
