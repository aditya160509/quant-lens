"""Feature 06: Market regime detection and adaptive strategy routing."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.performance import normalize_payload
from app.services.ml_v2.core.regimes import run_regime_engine


FEATURE_ID = "06"
FEATURE_TITLE = "Market Regime Detection and Adaptive Strategy Routing Engine"

DEFAULTS: dict[str, Any] = {
    "hmm_state_count": 3,
    "gmm_component_count": 3,
    "pc1_window": 63,
    "random_graph_threshold": 0.45,
    "regime_alert_threshold": 0.65,
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"states": "hmm_state_count", "components": "gmm_component_count", "graph_threshold": "random_graph_threshold"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "input_features", "type": "multi_select", "options": ["returns", "realized_vol", "rolling_sharpe", "skew", "kurtosis", "vix", "yield_curve"], "default": ["returns", "realized_vol", "vix"]},
    {"key": "hmm_state_count", "type": "integer", "options": [2, 3, 4], "default": 3},
    {"key": "gmm_component_count", "type": "integer", "options": [2, 3, 4], "default": 3},
    {"key": "pc1_window", "type": "integer", "options": [21, 63, 126], "default": 63},
    {"key": "random_graph_threshold", "type": "float", "default": 0.45},
    {"key": "regime_alert_threshold", "type": "float", "default": 0.65},
]

OUTPUT_CONTRACT = [
    {"key": "regime_probability_time_series", "location": "charts", "renderer": "stacked_area", "status": "live"},
    {"key": "regime_transition_heatmap", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "ensemble_vs_hmm_comparison", "location": "charts", "renderer": "metric_panel", "status": "live_compatible"},
    {"key": "pc1_structural_break_monitor", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "regime_conditional_factor_performance", "location": "charts", "renderer": "heatmap_or_table", "status": "live"},
    {"key": "strategy_performance_attribution_by_regime", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "regime_conditional_vol_term_structure", "location": "charts", "renderer": "curve", "status": "live"},
    {"key": "random_graph_systemic_risk_indicator", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "parallel_gmm_regime_probabilities", "location": "charts", "renderer": "stacked_area", "status": "live"},
    {"key": "hmm_vs_gmm_state_agreement", "location": "charts", "renderer": "metric_panel", "status": "live"},
    {"key": "regime_factor_forward_ic", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "transition_matrix", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "current_regime_probabilities", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "parallel_gmm_state_diagnostics", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "regime_factor_forward_ic", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["Student-t HMM emissions", "skewed-t HMM emissions", "tree/HMM majority-vote lead-lag validation with labeled external regimes"]
IMPLEMENTATION_NOTES = [
    "Realtime engine fits a Gaussian HMM with Baum-Welch and deterministic state ordering by mean return; Gaussian Mixture is an explicit fallback only if HMM fitting fails.",
    "PC1 structural-break and random-graph systemic-risk indicators are computed directly from local returns.",
]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["student_t_hmm", "skewed_t_hmm", "ensemble_hmm_full"])


def run(payload=None):
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_regime_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
