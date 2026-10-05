"""Feature 01: Purged K-Fold and Combinatorial Purged CV.

This file owns the feature contract. The reusable math lives in core.cpcv,
but this module defines what the feature accepts, what it emits, which pieces
are research-mode only, and how loose frontend/API payloads are normalized.
"""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "01"
FEATURE_TITLE = "Combinatorial Purged Cross-Validation Engine"

DEFAULTS: dict[str, Any] = {
    "model_type": "ridge",
    "label_type": "regression_return",
    "prediction_horizon": 5,
    "embargo_period": 5,
    "cpcv_n_groups": 6,
    "cpcv_k_test_groups": 2,
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
    "symbols_csv": "symbols",
}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet", "description": "Any local ticker universe; defaults to the most-covered local symbols."},
    {"key": "model_type", "type": "select", "options": ["ridge", "lasso", "elastic_net", "linear_svm", "mlp", "random_forest", "extra_trees", "xgboost", "lightgbm", "catboost"], "default": DEFAULTS["model_type"]},
    {"key": "label_type", "type": "select", "options": ["regression_return"], "default": DEFAULTS["label_type"]},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63], "default": DEFAULTS["prediction_horizon"]},
    {"key": "embargo_period", "type": "integer", "options": [0, 1, 5, 10, 21, 63], "default": DEFAULTS["embargo_period"]},
    {"key": "cpcv_n_groups", "type": "integer", "options": [4, 6, 8], "default": DEFAULTS["cpcv_n_groups"]},
    {"key": "cpcv_k_test_groups", "type": "integer", "options": [1, 2], "default": DEFAULTS["cpcv_k_test_groups"]},
]

OUTPUT_CONTRACT = [
    {"key": key, "location": location, "renderer": renderer, "status": "live"}
    for key, location, renderer in [
        ("cpcv_sharpe_distribution", "charts", "histogram"),
        ("purged_vs_naive_cv_comparison", "charts", "comparison_bar"),
        ("backtest_paths_chart", "charts", "line_bundle"),
        ("probability_of_backtest_overfitting", "charts", "metric_panel"),
        ("deflated_sharpe_ratio", "charts", "metric_panel"),
        ("embargo_sensitivity", "charts", "table"),
        ("per_fold_performance", "tables", "table"),
        ("cpcv_path_metrics", "tables", "table")]]
INPUT_CONTRACT.extend([
    {"key":"calculate_embargo_sensitivity","type":"boolean","default":False},
    {"key": "strategy_returns", "type": "dated_strategy_matrix", "required": False,
     "description": "Actual complete time-by-strategy return matrix, with dates, for CSCV PBO and DSR"},
    {"key": "pbo_partitions", "type": "integer", "options": [4, 6, 8, 10, 12], "default": 8},
    {"key": "selected_strategy", "type": "integer", "min": 0, "default": 0}])


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
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["user_model_upload", "event_times_csv"])


def run(payload=None):
    from app.services.ml_v2.core.cpcv import run_cpcv_engine
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
