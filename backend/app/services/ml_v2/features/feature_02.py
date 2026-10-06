"""Feature 02: Alpha, cross-sectional return ranking with controls and exact attributions."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract
from app.services.ml_v2.core.data_loader import UNIVERSE_PRESET_IDS


FEATURE_ID = "02"
FEATURE_TITLE = "Alpha: Gradient-Boosted and Ridge Ranking with Controls and Attribution"

DEFAULTS: dict[str, Any] = {
    "embargo_period": 5,
    "model_family": "ensemble",
    "feature_set": "ohlcv_factor_library",
    "prediction_target": "next_period_return",
    "prediction_horizon": 21,
    "tuning_mode": "platform_defaults",
    "cost_bps": 10,
    "lookback_days": 1008,
    "max_symbols": 120,
}

ALIASES = {"model": "model_family", "target": "prediction_target", "horizon": "prediction_horizon", "symbols_csv": "symbols"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet"},
    {"key": "universe", "type": "select", "options": UNIVERSE_PRESET_IDS, "default": "default"},
    {"key": "model_family", "type": "select", "options": ["ensemble", "lightgbm", "ridge", "xgboost", "catboost"], "default": "ensemble"},
    {"key": "feature_set", "type": "select", "options": ['ohlcv_factor_library'], "default": "ohlcv_factor_library"},
    {"key": "feature_families", "type": "multi_select", "options": ["momentum", "value", "quality", "volatility", "liquidity"],
     "default": ["momentum", "value", "quality", "volatility", "liquidity"]},
    {"key": "formulas", "type": "object", "required": False},
    {"key": "upload_id", "type": "text", "required": False},
    {"key": "prediction_target", "type": "select", "options": ['next_period_return'], "default": "next_period_return"},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63, 126, 252], "default": 21},
    {"key": "tuning_mode", "type": "select", "options": ["platform_defaults", "manual", "optuna_research"], "default": "platform_defaults"},
    {"key": "sample_weighting", "type": "select", "options": ["equal", "time_decay"], "default": "equal"},
    {"key": "sector_filter", "type": "text_list", "required": False},
    {"key": "minimum_formation_notional", "type": "float", "min": 0, "default": 0},
    {"key": "hyperparameters", "type": "object", "required": False},
    {"key": "optuna_trials", "type": "integer", "range": [1, 50], "default": 10},
    {"key": "exact_shap_cap", "type": "integer", "range": [1, 256], "default": 64},
]


_OUT = {"charts": ["prediction_rank_table", "shap_feature_importance", "shap_beeswarm", "shap_waterfall_top_signal",
                   "model_ic_leaderboard", "rolling_monthly_ic_series", "decile_spreads", "net_of_cost_curve"],
        "tables": ["current_predictions", "controls", "ensemble", "decile_summary", "what_changed", "ticker_contributions",
                   "feature_families", "model_performance", "heldout_predictions", "tuning_trials", "training_audit"]}
OUTPUT_CONTRACT = [{"key": key, "location": location, "renderer": "table", "status": "live"} for location, keys in _OUT.items() for key in keys]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["Default horizon is 21 sessions; LightGBM and Ridge on date-rank-scaled features, with OLS-3 and an IC-weighted composite as controls beside the model.",
    "Ensemble weights are chosen on a purged validation window before the holdout; attributions are exact TreeSHAP (pred_contrib) and linear contributions, blended with the same weights.",
    "Decile spreads are reported equal-weight and value-weight (dollar-volume proxy); long-short results are net of costs with turnover and capacity.",
    "Predictions get an artifact id in meta that Meta-label, Allocation and Validate can consume."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT, FEATURE_ID)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES)


def run(payload=None):
    from app.services.ml_v2.core.alpha import run_gbt_alpha
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_gbt_alpha(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
