"""Feature 01: Purged K-Fold and Combinatorial Purged CV.

This file owns the feature contract. The reusable math lives in core.analytics,
but this module defines what the feature accepts, what it emits, which pieces
are research-mode only, and how loose frontend/API payloads are normalized.
"""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.cpcv import run_cpcv_engine


FEATURE_ID = "01"
FEATURE_TITLE = "Purged K-Fold and Combinatorial Purged Cross-Validation Engine"

DEFAULTS: dict[str, Any] = {
    "model_type": "ridge",
    "label_type": "regression_return",
    "prediction_horizon": 5,
    "k_folds": 5,
    "embargo_period": 5,
    "cpcv_n_groups": 6,
    "cpcv_k_test_groups": 2,
    "scoring_metric": "sharpe_ratio",
    "number_of_trials": 20,
    "lookback_days": 756,
    "max_symbols": 80,
    "compute_mode": "realtime",
}

ALIASES = {
    "model": "model_type",
    "horizon": "prediction_horizon",
    "embargo": "embargo_period",
    "n_groups": "cpcv_n_groups",
    "k_test": "cpcv_k_test_groups",
    "trials": "number_of_trials",
    "symbols_csv": "symbols",
}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet", "description": "Any local ticker universe; defaults to the most-covered local symbols."},
    {"key": "model_type", "type": "select", "options": ["ridge", "lasso", "elastic_net", "linear_svm", "mlp", "random_forest", "extra_trees", "xgboost", "lightgbm", "catboost"], "default": DEFAULTS["model_type"]},
    {"key": "label_type", "type": "select", "options": ["regression_return"], "default": DEFAULTS["label_type"]},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63], "default": DEFAULTS["prediction_horizon"]},
    {"key": "k_folds", "type": "integer", "options": [3, 5, 10], "default": DEFAULTS["k_folds"]},
    {"key": "embargo_period", "type": "integer", "options": [0, 1, 5, 10, 21, 63], "default": DEFAULTS["embargo_period"]},
    {"key": "cpcv_n_groups", "type": "integer", "options": [4, 6, 8], "default": DEFAULTS["cpcv_n_groups"]},
    {"key": "cpcv_k_test_groups", "type": "integer", "options": [1, 2], "default": DEFAULTS["cpcv_k_test_groups"]},
    {"key": "number_of_trials", "type": "integer", "default": DEFAULTS["number_of_trials"], "description": "Used for Deflated Sharpe selection-bias correction."},
]

OUTPUT_CONTRACT = [
    {"key": "cpcv_sharpe_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "purged_vs_naive_cv_comparison", "location": "charts", "renderer": "comparison_bar", "status": "live"},
    {"key": "deflated_sharpe_ratio", "location": "charts", "renderer": "metric_panel", "status": "live"},
    {"key": "backtest_paths_chart", "location": "charts", "renderer": "line_bundle", "status": "live"},
    {"key": "embargo_sensitivity", "location": "charts", "renderer": "line_or_table", "status": "live"},
    {"key": "model_performance_vs_embargo", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "probability_of_backtest_overfitting", "location": "charts", "renderer": "metric_panel", "status": "live"},
    {"key": "dsr_pbo_joint_decision", "location": "charts", "renderer": "quadrant", "status": "live"},
    {"key": "per_fold_performance", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "label_fractional_uniqueness_audit", "location": "tables", "renderer": "table", "status": "live_proxy"},
    {"key": "cpcv_path_metrics", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = [
    "scikit-learn compatible user model upload",
    "non-uniform event timestamp CSV ingestion",
    "full triple-barrier uniqueness from externally supplied event end-times",
]

IMPLEMENTATION_NOTES = [
    "Uses local OHLCV-derived feature panel and strict temporal ordering.",
    "Purging removes overlapping label-formation windows and applies post-test embargo.",
    "CPCV path count is capped through cpcv_n_groups <= 8 for realtime stability.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["user_model_upload", "event_times_csv"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_cpcv_engine(normalized)
    return merge_feature_contract(
        result,
        feature_title=FEATURE_TITLE,
        input_contract=INPUT_CONTRACT,
        output_contract=OUTPUT_CONTRACT,
        research_only=RESEARCH_ONLY,
        implementation_notes=IMPLEMENTATION_NOTES,
        payload=normalized,
    )
