"""Feature 05: Hierarchical Risk Parity optimizer."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "05"
FEATURE_TITLE = "Constrained HRP, NCO and Minimum-Variance Allocation"

DEFAULTS: dict[str, Any] = {
    "covariance_estimator": "ledoit_wolf",
    "clustering_linkage": "ward",
    "optimization_variant": "standard_hrp",
    "max_symbols": 80,
    "lookback_days": 756,
}

ALIASES = {"estimator": "covariance_estimator", "linkage": "clustering_linkage", "variant": "optimization_variant"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "covariance_estimator", "type": "select", "options": ["sample", "ledoit_wolf", "oas", "ewma", "rmt_cleaned"], "default": "ledoit_wolf"},
    {"key": "clustering_linkage", "type": "select", "options": ["ward", "single", "complete", "average"], "default": "ward"},
    {"key": "optimization_variant", "type": "select", "options": ["standard_hrp", "nco", "min_variance"], "default": "standard_hrp"},
    {"key": "max_weight", "type": "float", "default": 0.25},
    {"key": "min_weight", "type": "float", "default": 0.0},
    {"key": "max_sector_weight", "type": "float", "default": 0.40},
    {"key": "black_litterman_tau", "type": "float", "default": 0.05},
    {"key": "views", "type": "asset_return_map", "required": False},
    {"key": "allocation_window", "type": "integer", "options": [63, 126, 252], "default": 126},
    {"key": "cost_bps", "type": "number", "min": 0, "max": 1000, "default": 5},
    {"key": "risk_aversion", "type": "number", "min": .01, "max": 100, "default": 2.5},
]

OUTPUT_CONTRACT = [{'key': 'hrp_weight_vector', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'cluster_dendrograms', 'location': 'charts', 'renderer': 'dendrogram', 'status': 'live'}, {'key': 'quasi_diagonalized_covariance_heatmap', 'location': 'charts', 'renderer': 'heatmap', 'status': 'live'}, {'key': 'risk_contribution_decomposition', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'walk_forward_allocation', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'black_litterman_posterior_return_vector', 'location': 'charts', 'renderer': 'table', 'status': 'live'}, {'key': 'bl_vs_pure_hrp_weight_comparison', 'location': 'charts', 'renderer': 'grouped_bar', 'status': 'live'}, {'key': 'hrp_weights', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'allocation_training_audit', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'black_litterman', 'location': 'tables', 'renderer': 'table', 'status': 'live'}]

RESEARCH_ONLY = ["PPO rebalancing, HERC and asymptotic tail-dependence estimators are not implemented; no proxy output is produced"]
IMPLEMENTATION_NOTES = ["Actual HRP inverse-variance bisection, constrained nested minimum variance and Black-Litterman views.", "Historical allocations refit monthly on past complete observations, execute next close, and charge actual turnover."]


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
