"""Feature 09: ML-enhanced pairs and statistical arbitrage engine."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "09"
FEATURE_TITLE = "Cointegrated Pairs and Statistical Arbitrage Engine"

DEFAULTS: dict[str, Any] = {
    "pair_selection": "engle_granger",
    "min_correlation": 0.45,
    "entry_z": 2.0,
    "exit_z": 0.5,
    "lookback_days": 756,
    "max_symbols": 120,
}

ALIASES = {"entry": "entry_z", "exit": "exit_z", "corr": "min_correlation"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "pair_selection", "type": "select", "options": ["engle_granger", "sector_neutral"], "default": "engle_granger"},
    {"key": "min_correlation", "type": "float", "default": 0.45},
    {"key": "entry_z", "type": "float", "default": 2.0},
    {"key": "exit_z", "type": "float", "default": 0.5},
    {"key": "hedge_ratio_method", "type": "select", "options": ["static", "rolling_ols", "kalman"], "default": "kalman"},
]

INPUT_CONTRACT.append({"key":"cost_bps","type":"float","range":[0,1000],"default":10})
OUTPUT_CONTRACT = [{"key":key,"location":location,"renderer":"table","status":"live"}
    for location,keys in {"charts":["pair_candidate_leaderboard","spread_zscore_timeseries","cointegration_network",
        "hedge_ratio_path","entry_exit_signal_timeline","pair_backtest_equity"],
        "tables":["pair_candidates","spread_timeseries","hedge_ratio","training_audit"]}.items() for key in keys]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["Engle-Granger selects the pair using initial formation history only; evaluation keeps that pair fixed.",
    "Static, rolling OLS and Kalman hedge ratios use only information available at formation.",
    "No copula, RL or trained pair-classifier output is advertised."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT, FEATURE_ID)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES)


def run(payload=None):
    from app.services.ml_v2.core.pairs import run_pairs_engine
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_pairs_engine(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
