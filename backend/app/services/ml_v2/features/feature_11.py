"""Feature 11: Causal Factor Discovery Engine with Double/Debiased ML."""

from __future__ import annotations

from typing import Any

from app.services.ml_v2.core.analytics import merge_feature_contract, normalize_payload, run_causal_dml


FEATURE_ID = "11"
FEATURE_TITLE = "Causal Factor Discovery Engine"

DEFAULTS: dict[str, Any] = {
    "factor_library": "ohlcv_factor_library",
    "dml_folds": 5,
    "nuisance_model": "ridge",
    "rolling_window": 252,
    "significance_threshold": 0.95,
    "spurious_factor_action": "flag_only",
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"folds": "dml_folds", "model": "nuisance_model", "confidence": "significance_threshold"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "factor_library", "type": "select", "options": ["ohlcv_factor_library", "fama_french", "microstructure", "gbt_predictions", "custom"], "default": "ohlcv_factor_library"},
    {"key": "dml_folds", "type": "integer", "options": [3, 5], "default": 5},
    {"key": "nuisance_model", "type": "select", "options": ["ridge", "elastic_net", "random_forest", "lightgbm"], "default": "ridge"},
    {"key": "rolling_window", "type": "integer", "options": [126, 252, 504], "default": 252},
    {"key": "significance_threshold", "type": "select", "options": [0.90, 0.95, 0.99], "default": 0.95},
    {"key": "spurious_factor_action", "type": "select", "options": ["flag_only", "auto_prune", "user_decision"], "default": "flag_only"},
]

OUTPUT_CONTRACT = [
    {"key": "causal_ape_leaderboard", "location": "charts", "renderer": "error_bar_table", "status": "live"},
    {"key": "confounding_bias_decomposition", "location": "charts", "renderer": "waterfall", "status": "live"},
    {"key": "ape_time_series", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "spurious_factor_detection_log", "location": "charts", "renderer": "event_log", "status": "live"},
    {"key": "nuisance_model_r2_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "robust_inference_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "causal_factor_network", "location": "charts", "renderer": "network", "status": "live"},
    {"key": "dml_vs_ols_backtest_comparison", "location": "charts", "renderer": "comparison", "status": "live"},
    {"key": "rolling_spurious_fraction", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "causal_ape_table", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "causal_network_edges", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "robust_inference_table", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["Optuna tuning for nuisance models", "server-side auto-prune into Feature 8"]
IMPLEMENTATION_NOTES = [
    "Realtime implementation uses K-fold cross-fitted DML residualization with Ridge, random forest, or LightGBM nuisance models when installed.",
    "Outputs distinguish Causal, Proxy, and Spurious factors using APE t-statistics and IC-vs-APE gap.",
    "Adds HC3 robust univariate inference as a fast diagnostic beside the DML APE statistic.",
]


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["optuna", "auto_prune"])


def run(payload=None):
    normalized = normalize_feature_payload(payload)
    result = run_causal_dml(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
