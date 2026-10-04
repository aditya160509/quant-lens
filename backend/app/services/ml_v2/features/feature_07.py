"""Feature 07: Bayesian online learning and dynamic model averaging."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.dma import run_dma_engine


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
    {"key": "model_library", "type": "multi_select", "options": ["xgboost", "lightgbm", "random_forest", "ridge", "elastic_net", "lstm", "gru", "har", "rolling_mean"], "default": DEFAULTS["model_library"]},
    {"key": "ensemble_method", "type": "select", "options": ["dma", "obs", "static_bma", "equal_weight", "all"], "default": "dma"},
    {"key": "forgetting_factor", "type": "float", "range": [0.90, 1.00], "default": 0.97},
    {"key": "obs_learning_rate", "type": "float", "range": [0.001, 0.1], "default": 0.01},
    {"key": "scoring_rule", "type": "select", "options": ["log_score", "brier", "qlike", "squared_error", "rank_ic"], "default": "squared_error"},
]

OUTPUT_CONTRACT = [
    {"key": "live_model_weight_dashboard", "location": "charts", "renderer": "horizontal_bar", "status": "live"},
    {"key": "model_weight_evolution", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "dma_vs_obs_vs_static_bma", "location": "charts", "renderer": "line_or_table", "status": "live"},
    {"key": "obs_weight_evolution", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "obs_regret_curve", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "model_pruning_log", "location": "charts", "renderer": "event_log", "status": "live"},
    {"key": "model_performance_tracker", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "prediction_calibration_curve", "location": "charts", "renderer": "calibration", "status": "live"},
    {"key": "epistemic_vs_aleatoric_uncertainty", "location": "charts", "renderer": "line", "status": "live_proxy"},
    {"key": "distributional_uncertainty_panel", "location": "charts", "renderer": "band_line", "status": "live_proxy"},
    {"key": "forgetting_factor_sensitivity", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "regime_specific_lambda_path", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "current_model_weights", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "score_log", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "obs_regret_log", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "model_performance_tracker", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "regime_specific_lambda_path", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["trained distributional predictive models for full calibrated epistemic/aleatoric split", "LSTM/GRU live ensemble members"]
IMPLEMENTATION_NOTES = [
    "Realtime DMA updates weights sequentially from recent squared-error likelihood.",
    "OBS uses simplex-projected online convex updates on Gaussian negative log-score and emits separate weight/regret curves.",
    "Realtime uncertainty bands use current model-dispersion percentiles and residual error, not heavy bootstrapped distributional models.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["obs_full", "distributional_models", "lstm"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_dma_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
