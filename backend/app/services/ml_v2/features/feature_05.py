"""Feature 05: Hierarchical Risk Parity optimizer."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.data_loader import UNIVERSE_PRESET_IDS


FEATURE_ID = "05"
FEATURE_TITLE = "Allocation: Ledoit-Wolf Minimum Variance with HRP, Inverse-Variance and 1/N Controls"

DEFAULTS: dict[str, Any] = {
    "covariance_estimator": "ledoit_wolf",
    "clustering_linkage": "ward",
    "optimization_variant": "min_variance",
    "max_symbols": 80,
    "lookback_days": 756,
    "allocation_window": 252,
}

ALIASES = {"estimator": "covariance_estimator", "linkage": "clustering_linkage", "variant": "optimization_variant"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "universe", "type": "select", "options": UNIVERSE_PRESET_IDS, "default": "default"},
    {"key": "holdings", "type": "object", "required": False},
    {"key": "holdings_unit", "type": "select", "options": ["weights", "shares"], "default": "weights"},
    {"key": "portfolio_value", "type": "float", "min": 1, "default": 100000},
    {"key": "alpha_artifact_id", "type": "text", "required": False},
    {"key": "bootstrap_samples", "type": "integer", "range": [0, 200], "default": 40},
    {"key": "covariance_estimator", "type": "select", "options": ["sample", "ledoit_wolf", "oas", "ewma", "rmt_cleaned"], "default": "ledoit_wolf"},
    {"key": "clustering_linkage", "type": "select", "options": ["ward", "single", "complete", "average"], "default": "ward"},
    {"key": "optimization_variant", "type": "select", "options": ["min_variance", "standard_hrp", "nco", "inverse_variance", "equal_weight"], "default": "min_variance"},
    {"key": "max_weight", "type": "float", "default": 0.25},
    {"key": "min_weight", "type": "float", "default": 0.0},
    {"key": "max_sector_weight", "type": "float", "default": 0.40},
    {"key": "black_litterman_tau", "type": "float", "default": 0.05},
    {"key": "views", "type": "asset_return_map", "required": False},
    {"key": "allocation_window", "type": "integer", "options": [63, 126, 252], "default": 252},
    {"key": "cost_bps", "type": "number", "min": 0, "max": 1000, "default": 5},
    {"key": "risk_aversion", "type": "number", "min": .01, "max": 100, "default": 2.5},
]


OUTPUT_CONTRACT = [{'key': 'hrp_weight_vector', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'cluster_dendrograms', 'location': 'charts', 'renderer': 'dendrogram', 'status': 'live'}, {'key': 'quasi_diagonalized_covariance_heatmap', 'location': 'charts', 'renderer': 'heatmap', 'status': 'live'}, {'key': 'risk_contribution_decomposition', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'walk_forward_allocation', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'controls_equity', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'weight_stability', 'location': 'charts', 'renderer': 'table', 'status': 'live'}, {'key': 'black_litterman_posterior_return_vector', 'location': 'charts', 'renderer': 'table', 'status': 'live'}, {'key': 'bl_vs_pure_hrp_weight_comparison', 'location': 'charts', 'renderer': 'grouped_bar', 'status': 'live'}, {'key': 'controls_summary', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'weight_stability', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'rebalance_log', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'trade_list', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'rebalance_summary', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'holding_risk', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'alpha_views', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'hrp_weights', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'allocation_training_audit', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'black_litterman', 'location': 'tables', 'renderer': 'table', 'status': 'live'}]

RESEARCH_ONLY = ["PPO rebalancing, HERC and asymptotic tail-dependence estimators are not implemented; no proxy output is produced"]
IMPLEMENTATION_NOTES = ["Default is Ledoit-Wolf minimum variance; HRP, inverse-variance and 1/N are always walk-forward controls, net of costs, with a no-trade rule that rebalances only when the gain beats the cost.",
    "Actual HRP inverse-variance bisection, constrained nested minimum variance and Black-Litterman views.", "Historical allocations refit monthly on past complete observations, execute next close, and charge actual turnover."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT, FEATURE_ID)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES)


def run(payload=None):
    from app.services.ml_v2.core.allocation import run_hrp_optimizer
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_hrp_optimizer(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
