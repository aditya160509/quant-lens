"""Feature 07: Bayesian online learning and dynamic model averaging."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "07"
FEATURE_TITLE = "Bayesian Online Learning and Dynamic Model Averaging Engine"

DEFAULTS: dict[str, Any] = {
    "model_library": ["momentum", "reversal", "low_vol", "ridge", "extra_trees"],
    "ensemble_method": "dma",
    "forgetting_factor": 0.97,
    "obs_learning_rate": 0.01,
    "prediction_horizon": 5,
    "scoring_rule": "squared_error",
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"lambda": "forgetting_factor", "method": "ensemble_method", "horizon": "prediction_horizon"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "model_library", "type": "multi_select", "options": ["momentum", "reversal", "low_vol", "ridge", "extra_trees"], "default": DEFAULTS["model_library"]},
    {"key": "ensemble_method", "type": "select", "options": ["dma", "obs", "static_bma", "equal_weight", "all"], "default": "dma"},
    {"key": "forgetting_factor", "type": "float", "range": [0.90, 1.00], "default": 0.97},
    {"key": "obs_learning_rate", "type": "float", "range": [0.001, 0.1], "default": 0.01},
    {"key": "scoring_rule", "type": "select", "options": ["squared_error"], "default": "squared_error"},
]

OUTPUT_CONTRACT = [
    {"key": key, "location": location, "renderer": "table", "status": "live"}
    for location, keys in {
        "charts": ["live_model_weight_dashboard", "model_weight_evolution", "dma_vs_obs_vs_static_bma",
                   "obs_weight_evolution", "obs_regret_curve", "model_performance_tracker", "prediction_calibration_curve"],
        "tables": ["current_model_weights", "score_log", "obs_regret_log", "model_performance_tracker", "training_audit"],
    }.items() for key in keys
]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["Weights update by complete formation-date batches only after their forward labels mature.",
    "All members are calibrated on a purged chronological training split; static weights are equal priors.",
    "Squared-error scoring is used; model dispersion is not a predictive confidence interval."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["obs_full", "distributional_models", "lstm"])


def run(payload=None):
    from app.services.ml_v2.core.dma import run_dma_engine
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_dma_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
