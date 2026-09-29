"""Feature 02: Gradient-Boosted Tree Alpha Engine with attribution."""

from __future__ import annotations

from typing import Any

from app.services.ml_v2.core.analytics import merge_feature_contract, normalize_payload, run_gbt_alpha


FEATURE_ID = "02"
FEATURE_TITLE = "Gradient-Boosted Tree Alpha Engine with Full Attribution"

DEFAULTS: dict[str, Any] = {
    "model_family": "all",
    "feature_set": "ohlcv_factor_library",
    "prediction_target": "next_period_return",
    "prediction_horizon": 5,
    "tuning_mode": "platform_defaults",
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"model": "model_family", "target": "prediction_target", "horizon": "prediction_horizon", "symbols_csv": "symbols"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet"},
    {"key": "model_family", "type": "select", "options": ["all", "xgboost", "lightgbm", "catboost", "random_forest", "extra_trees", "ridge"], "default": "all"},
    {"key": "feature_set", "type": "select", "options": ["ohlcv_factor_library", "pca_loadings", "manual_expression"], "default": "ohlcv_factor_library"},
    {"key": "prediction_target", "type": "select", "options": ["next_period_return", "return_sign", "return_quintile", "triple_barrier"], "default": "next_period_return"},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63, 126, 252], "default": 5},
    {"key": "tuning_mode", "type": "select", "options": ["platform_defaults", "manual", "optuna_research"], "default": "platform_defaults"},
]

OUTPUT_CONTRACT = [
    {"key": "prediction_rank_table", "location": "charts", "renderer": "rank_table", "status": "live"},
    {"key": "shap_feature_importance", "location": "charts", "renderer": "bar", "status": "live_importance_proxy"},
    {"key": "shap_long_side_importance", "location": "charts", "renderer": "bar", "status": "live_importance_proxy"},
    {"key": "shap_short_side_importance", "location": "charts", "renderer": "bar", "status": "live_importance_proxy"},
    {"key": "exact_shap_sample_importance", "location": "charts", "renderer": "bar", "status": "live_capped"},
    {"key": "model_ic_leaderboard", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "rolling_monthly_ic_series", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "ic_weighted_ensemble_weights", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "ic_decay_profile", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "shap_beeswarm_proxy", "location": "charts", "renderer": "beeswarm", "status": "disabled_no_fabricated_values"},
    {"key": "shap_waterfall_top_signal", "location": "charts", "renderer": "waterfall", "status": "disabled_no_fabricated_values"},
    {"key": "ice_partial_dependence", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "hyperparameter_landscape", "location": "charts", "renderer": "heatmap", "status": "live_fast_grid"},
    {"key": "signal_to_portfolio_stats", "location": "charts", "renderer": "metric_table", "status": "live"},
    {"key": "prediction_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "top_bottom_signal_spread", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "current_predictions", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "model_performance", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "feature_importance", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "rolling_monthly_ic", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "hyperparameter_landscape", "location": "tables", "renderer": "table", "status": "live_fast_grid"},
    {"key": "signal_to_portfolio_stats", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "training_audit", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["Optuna Bayesian hyperparameter search", "exact TreeSHAP for every current prediction when universe > realtime cap"]
IMPLEMENTATION_NOTES = [
    "Fits installed tree/linear model families on OHLCV-derived cross-sectional features.",
    "XGBoost, LightGBM, and CatBoost are used when installed; unavailable optional libraries are skipped with metadata.",
    "Feature attribution falls back to exact model importances/coefficient magnitude when full SHAP is not requested.",
    "Attribution is also split into long-side and short-side importance proxies using the current ranked prediction book.",
    "Realtime exact TreeSHAP is capped to a small latest-book sample and emitted separately as exact_shap_sample_importance.",
]


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["optuna_trials", "exact_shap", "catboost"])


def run(payload=None):
    normalized = normalize_feature_payload(payload)
    result = run_gbt_alpha(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
