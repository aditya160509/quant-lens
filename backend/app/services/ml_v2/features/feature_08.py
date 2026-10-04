"""Feature 08: Multi-factor IC-weighted composite signal optimizer."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.composite import run_composite_optimizer


FEATURE_ID = "08"
FEATURE_TITLE = "Multi-Factor IC-Weighted Composite Signal Optimizer"

DEFAULTS: dict[str, Any] = {
    "factor_library": "ohlcv_factor_library",
    "weighting_scheme": "ic_ir",
    "orthogonalization": "gram_schmidt",
    "walk_forward_window": 252,
    "prediction_horizon": 5,
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
    "higher_order_interactions": True,
    "max_interactions": 30,
    "interaction_min_ic": 0.015,
    "forward_selection_max_factors": 8,
}

ALIASES = {"factors": "factor_library", "scheme": "weighting_scheme", "horizon": "prediction_horizon"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "factor_library", "type": "select", "options": ["ohlcv_factor_library", "fama_french", "microstructure", "gbt_predictions", "custom"], "default": "ohlcv_factor_library"},
    {"key": "weighting_scheme", "type": "select", "options": ["ic", "ic_ir", "shrinkage", "dml_ape"], "default": "ic_ir"},
    {"key": "orthogonalization", "type": "select", "options": ["none", "gram_schmidt", "pca_neutralized"], "default": "gram_schmidt"},
    {"key": "walk_forward_window", "type": "integer", "options": [126, 252, 504], "default": 252},
    {"key": "output_signal_construction", "type": "select", "options": ["long_short_decile", "zscore", "signed_rank"], "default": "zscore"},
    {"key": "higher_order_interactions", "type": "boolean", "default": True},
    {"key": "max_interactions", "type": "integer", "options": [10, 30, 60, 100], "default": 30},
    {"key": "interaction_min_ic", "type": "number", "default": 0.015},
    {"key": "forward_selection_max_factors", "type": "integer", "options": [4, 8, 12], "default": 8},
]

OUTPUT_CONTRACT = [
    {"key": "ic_weighted_composite_weights", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "factor_correlation_heatmap", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "orthogonalization_impact", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "walk_forward_weight_stability", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "composite_signal_distribution", "location": "charts", "renderer": "histogram_or_table", "status": "live"},
    {"key": "long_short_backtest", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "factor_turnover_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "higher_order_interaction_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "interaction_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "forward_selection_fama_macbeth", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "elastic_lasso_factor_selection", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "alphaforge_dynamic_weights", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "ic_decay_alerts", "location": "charts", "renderer": "event_log", "status": "live"},
    {"key": "rolling_composite_ic", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "factor_ic_table", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "latest_composite_scores", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "orthogonalization_table", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "elastic_lasso_factor_selection", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "ic_decay_alerts", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["server-side persistence of Feature 11 DML APE weights", "custom factor CSV ingestion", "nested/full-library Fama-MacBeth model-selection research sweep"]
IMPLEMENTATION_NOTES = [
    "Computes IC weights and Gram-Schmidt residualization from local cross-sectional feature panel.",
    "Screens pairwise higher-order factor interactions with fast cross-sectional Spearman IC.",
    "Includes a realtime forward-selection Fama-MacBeth-style screen over the current local factor library.",
    "DML APE mode is available once Feature 11 outputs are persisted/routed.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["custom_factor_csv", "fama_macbeth", "dml_ape"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_composite_optimizer(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
