"""Feature 09: ML-enhanced pairs and statistical arbitrage engine."""

from __future__ import annotations

from typing import Any

from app.services.ml_v2.core.analytics import merge_feature_contract, normalize_payload, run_pairs_engine


FEATURE_ID = "09"
FEATURE_TITLE = "ML-Enhanced Pairs and Statistical Arbitrage Engine"

DEFAULTS: dict[str, Any] = {
    "pair_selection": "correlation_ou",
    "min_correlation": 0.45,
    "entry_z": 2.0,
    "exit_z": 0.5,
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"entry": "entry_z", "exit": "exit_z", "corr": "min_correlation"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "pair_selection", "type": "select", "options": ["correlation_ou", "engle_granger", "johansen_research", "sector_neutral"], "default": "correlation_ou"},
    {"key": "min_correlation", "type": "float", "default": 0.45},
    {"key": "entry_z", "type": "float", "default": 2.0},
    {"key": "exit_z", "type": "float", "default": 0.5},
    {"key": "hedge_ratio_method", "type": "select", "options": ["static", "rolling_ols", "kalman"], "default": "kalman"},
]

OUTPUT_CONTRACT = [
    {"key": "pair_candidate_leaderboard", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "spread_zscore_timeseries", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "cointegration_network", "location": "charts", "renderer": "network", "status": "live_proxy"},
    {"key": "kalman_hedge_ratio_path", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "entry_exit_signal_timeline", "location": "charts", "renderer": "timeline", "status": "live"},
    {"key": "pair_backtest_equity", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "rl_threshold_policy", "location": "charts", "renderer": "policy_table", "status": "research_proxy"},
    {"key": "adf_pvalue_distribution", "location": "charts", "renderer": "histogram_or_table", "status": "live"},
    {"key": "pair_precluster_map", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "copula_entry_thresholds", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "pair_network_components", "location": "charts", "renderer": "network_summary", "status": "live"},
    {"key": "ml_pair_classifier_scores", "location": "charts", "renderer": "table", "status": "live_fast_score"},
    {"key": "pair_candidates", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "spread_timeseries", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "kalman_hedge_ratio", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "pair_preclusters", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["Johansen full-rank tests across all candidate baskets", "PPO threshold optimizer"]
IMPLEMENTATION_NOTES = [
    "Realtime candidate screen uses correlation, Engle-Granger ADF p-value, spread z-score, and OU half-life.",
    "Top-pair hedge ratio is fit with a random-walk beta Kalman filter and the residual path drives z-score signals.",
]


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["johansen", "kalman", "ppo_threshold"])


def run(payload=None):
    normalized = normalize_feature_payload(payload)
    result = run_pairs_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
