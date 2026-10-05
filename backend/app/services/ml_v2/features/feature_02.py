"""Feature 02: Gradient-Boosted Tree Alpha Engine with attribution."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "02"
FEATURE_TITLE = "Gradient-Boosted Tree Alpha Engine with Full Attribution"

DEFAULTS: dict[str, Any] = {
    "model_family": "all",
    "feature_set": "ohlcv_factor_library",
    "prediction_target": "next_period_return",
    "prediction_horizon": 5,
    "tuning_mode": "platform_defaults",
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"model": "model_family", "target": "prediction_target", "horizon": "prediction_horizon", "symbols_csv": "symbols"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet"},
    {"key": "model_family", "type": "select", "options": ["all", "xgboost", "lightgbm", "catboost", "random_forest", "extra_trees", "ridge"], "default": "all"},
    {"key": "feature_set", "type": "select", "options": ['ohlcv_factor_library'], "default": "ohlcv_factor_library"},
    {"key": "prediction_target", "type": "select", "options": ['next_period_return'], "default": "next_period_return"},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63, 126, 252], "default": 5},
    {"key": "tuning_mode", "type": "select", "options": ["platform_defaults", "manual", "optuna_research"], "default": "platform_defaults"},
]

INPUT_CONTRACT.extend([{"key":"sample_weighting","type":"select","options":["equal","time_decay"],"default":"equal"},
    {"key":"sector_filter","type":"text_list","required":False},
    {"key":"minimum_formation_notional","type":"float","min":0,"default":0},{"key":"hyperparameters","type":"object","required":False},
    {"key":"optuna_trials","type":"integer","range":[1,50],"default":10},
    {"key":"exact_shap_cap","type":"integer","range":[1,256],"default":64}])

OUTPUT_CONTRACT = [{"key": key, "location": location, "renderer": "table", "status": "live"}
    for location, keys in {"charts": ["prediction_rank_table", "shap_feature_importance", "shap_beeswarm",
        "shap_waterfall_top_signal", "model_ic_leaderboard", "rolling_monthly_ic_series"],
        "tables": ["current_predictions", "model_performance", "heldout_predictions", "tuning_trials", "training_audit"]}.items() for key in keys]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["Model selection, tuning and ensemble weights use nested purged training validation only.",
    "Attribution uses genuine SHAP values in model output units; no model-importance substitutes.",
    "Current predictions use the latest observed feature dates and refit on matured labels only."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["optuna_trials", "exact_shap", "catboost"])


def run(payload=None):
    from app.services.ml_v2.core.alpha import run_gbt_alpha
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_gbt_alpha(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
