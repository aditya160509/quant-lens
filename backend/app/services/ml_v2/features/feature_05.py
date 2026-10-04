"""Feature 05: Hierarchical Risk Parity optimizer."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.allocation import run_hrp_optimizer


FEATURE_ID = "05"
FEATURE_TITLE = "Hierarchical Risk Parity Portfolio Optimizer with RL-Enhanced Rebalancing"

DEFAULTS: dict[str, Any] = {
    "covariance_estimator": "ledoit_wolf",
    "clustering_linkage": "ward",
    "optimization_variant": "standard_hrp",
    "max_symbols": 80,
    "lookback_days": 756,
    "rl_rebalancing": False,
    "compute_mode": "realtime",
}

ALIASES = {"estimator": "covariance_estimator", "linkage": "clustering_linkage", "variant": "optimization_variant"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "covariance_estimator", "type": "select", "options": ["sample", "ledoit_wolf", "oas", "ewma", "rmt_cleaned"], "default": "ledoit_wolf"},
    {"key": "clustering_linkage", "type": "select", "options": ["ward", "single", "complete", "average"], "default": "ward"},
    {"key": "optimization_variant", "type": "select", "options": ["standard_hrp", "nco", "herc", "min_variance"], "default": "standard_hrp"},
    {"key": "max_weight", "type": "float", "default": 0.25},
    {"key": "min_weight", "type": "float", "default": 0.0},
    {"key": "max_sector_weight", "type": "float", "default": 0.40},
    {"key": "black_litterman_tau", "type": "float", "default": 0.05},
    {"key": "views", "type": "asset_return_map", "required": False},
    {"key": "rl_rebalancing", "type": "boolean", "default": False},
]

OUTPUT_CONTRACT = [
    {"key": "cluster_dendrograms", "location": "charts", "renderer": "dendrogram", "status": "live"},
    {"key": "hrp_weight_vector", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "hrp_vs_nco_vs_markowitz_equal_weight", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "rl_rebalancing_vs_fixed_schedule", "location": "charts", "renderer": "comparison", "status": "research_proxy"},
    {"key": "quasi_diagonalized_covariance_heatmap", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "risk_contribution_decomposition", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "tail_dependence_matrix", "location": "charts", "renderer": "heatmap", "status": "live_proxy"},
    {"key": "rolling_cluster_stability", "location": "charts", "renderer": "line", "status": "live_proxy"},
    {"key": "black_litterman_posterior_return_vector", "location": "charts", "renderer": "bar", "status": "live_proxy"},
    {"key": "bl_vs_pure_hrp_weight_comparison", "location": "charts", "renderer": "grouped_bar", "status": "live_proxy"},
    {"key": "view_attribution_backtest", "location": "charts", "renderer": "line", "status": "live_proxy"},
    {"key": "covariance_estimator_comparison", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "herc_weight_vector", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "herc_vs_hrp_comparison", "location": "charts", "renderer": "comparison", "status": "live"},
    {"key": "hrp_weights", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "risk_contribution", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "herc_weights", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "herc_clusters", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["PPO rebalancing agent training", "manual Black-Litterman view editor persistence"]
IMPLEMENTATION_NOTES = [
    "Supports Ledoit-Wolf, OAS, EWMA, and RMT-cleaned covariance with standard HRP, HERC, or NCO diagnostics in realtime.",
    "RL/BL panels are emitted as clearly marked research proxies unless research jobs are wired.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["rl_rebalancing", "ppo_training", "nco_full"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_hrp_optimizer(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
