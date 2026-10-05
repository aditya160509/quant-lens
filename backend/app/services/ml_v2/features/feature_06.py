"""Feature 06: Market regime detection and adaptive strategy routing."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


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
    {"key": "input_features", "type": "multi_select", "options": ["returns", "realized_vol", "rolling_sharpe", "skew", "kurtosis"], "default": ["returns", "realized_vol"]},
    {"key": "hmm_state_count", "type": "integer", "options": [2, 3, 4], "default": 3},
    {"key": "gmm_component_count", "type": "integer", "options": [2, 3, 4], "default": 3},
    {"key": "pc1_window", "type": "integer", "options": [21, 63, 126], "default": 63},
    {"key": "random_graph_threshold", "type": "float", "default": 0.45},
    {"key": "regime_alert_threshold", "type": "float", "default": 0.65},
]

OUTPUT_CONTRACT = [{"key":key,"location":location,"renderer":"table","status":"live"}
    for location,keys in {"charts":["regime_probability_time_series","regime_transition_heatmap","ensemble_vs_hmm_comparison",
        "pc1_variance_monitor","regime_conditional_asset_returns","correlation_network_density","parallel_gmm_regime_probabilities"],
        "tables":["transition_matrix","current_regime_probabilities","training_audit"]}.items() for key in keys]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["HMM, scaler and parallel GMM fit only the initial training dates.",
    "Out-of-sample HMM probabilities use causal forward filtering, not smoothing or Viterbi.",
    "Correlation density is descriptive, not an Erdos-Renyi systemic-risk estimate."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["student_t_hmm", "skewed_t_hmm", "ensemble_hmm_full"])


def run(payload=None):
    from app.services.ml_v2.core.regimes import run_regime_engine
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_regime_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
