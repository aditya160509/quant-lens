"""Feature 03: Multi-horizon volatility forecasting engine."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "03"
FEATURE_TITLE = "Multi-Horizon Volatility Forecasting Engine"

DEFAULTS: dict[str, Any] = {
    "asset": None,
    "forecast_horizons": [1, 5, 21, 63],
    "model_suite": "har_ml",
    "lookback_days": 756,
    "max_symbols": 80,
    "compute_mode": "realtime",
}

ALIASES = {"symbol": "asset", "ticker": "asset", "horizon": "forecast_horizons"}

INPUT_CONTRACT = [
    {"key": "asset", "type": "ticker", "required": False, "source": "master_universe.parquet"},
    {"key": "forecast_horizons", "type": "multi_select", "options": [1, 5, 21, 63], "default": [1, 5, 21, 63]},
    {"key": "model_suite", "type": "select", "options": ["har_ml", "har_ridge", "har_gbm", "har_x", "arch_family"], "default": "har_ml"},
    {"key": "garch_fit_cap", "type": "integer", "options": [500, 1000, 1500], "default": 1000},
]

OUTPUT_CONTRACT = [{"key":key,"location":location,"renderer":"table","status":"live"}
    for location,keys in {"charts":["vol_forecast_panel","forecast_error_distribution","vol_term_structure","realized_vs_predicted",
        "model_confidence_intervals","realized_vol_estimator_comparison","garch_model_selection","garch_leverage_news_impact_curve","ensemble_vol_forecast_weights"],
        "tables":["forecast_tournament","forecast_rows","garch_model_selection"]}.items() for key in keys]
RESEARCH_ONLY = []
IMPLEMENTATION_NOTES = ["Direct per-horizon HAR forecasts use future squared-return targets with date purging.",
    "Absolute residual intervals are calibrated before the final holdout, never using its outcomes.",
    "ARCH-family selection supports one-step forecasts only; no GINN or jump-proxy output is advertised."]


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["ginn", "gpu_training"])


def run(payload=None):
    from app.services.ml_v2.core.volatility import run_vol_forecasting
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_vol_forecasting(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
