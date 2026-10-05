"""Feature 11: Conditional Factor Association Engine with Double/Debiased ML."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "11"
FEATURE_TITLE = "Conditional Factor Association Engine"

DEFAULTS: dict[str, Any] = {
    "embargo_period": 5,
    "factor_library": "ohlcv_factor_library",
    "dml_folds": 5,
    "nuisance_model": "ridge",
    "rolling_window": 252,
    "significance_threshold": 0.95,
    "spurious_factor_action": "flag_only",
    "lookback_days": 756,
    "max_symbols": 120,
}

ALIASES = {"folds": "dml_folds", "model": "nuisance_model", "confidence": "significance_threshold"}

INPUT_CONTRACT = [{'key': 'symbols', 'type': 'ticker_list', 'required': False}, {'key': 'factor_library', 'type': 'select', 'options': ['ohlcv_factor_library'], 'default': 'ohlcv_factor_library'}, {'key': 'dml_folds', 'type': 'integer', 'options': [3, 5], 'default': 5}, {'key': 'nuisance_model', 'type': 'select', 'options': ['ridge', 'elastic_net', 'random_forest', 'lightgbm'], 'default': 'ridge'}, {'key': 'rolling_window', 'type': 'integer', 'options': [126, 252, 504], 'default': 252}, {'key': 'significance_threshold', 'type': 'select', 'options': [0.9, 0.95, 0.99], 'default': 0.95}, {'key': 'spurious_factor_action', 'type': 'select', 'options': ['flag_only'], 'default': 'flag_only'}]

OUTPUT_CONTRACT = [{'key': 'conditional_ape_leaderboard', 'location': 'charts', 'renderer': 'error_bar_table', 'status': 'live'}, {'key': 'ape_time_series', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'adjustment_vs_univariate_slope', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'robust_inference_table', 'location': 'charts', 'renderer': 'table', 'status': 'live'}, {'key': 'conditional_ape_table', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'unidentified_factors', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'robust_inference_table', 'location': 'tables', 'renderer': 'table', 'status': 'live'}]

RESEARCH_ONLY = ["Optuna tuning for nuisance models", "server-side auto-prune into Feature 8"]
IMPLEMENTATION_NOTES = [
    "Expanding date-based purged cross-fitting estimates conditional associations with HC3 standard errors.",
    "Statistical significance does not establish causal identification; no Causal/Proxy/Spurious rule labels are produced.",
    "Adds HC3 robust univariate inference as a fast diagnostic beside the DML APE statistic.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT, FEATURE_ID)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES)


def run(payload=None):
    from app.services.ml_v2.core.dml import run_causal_dml
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_causal_dml(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
