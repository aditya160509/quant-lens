"""Feature 03: Multi-horizon volatility forecasting engine."""

from __future__ import annotations

from typing import Any

from app.services.ml_v2.core.analytics import merge_feature_contract, normalize_payload, run_vol_forecasting


FEATURE_ID = "03"
FEATURE_TITLE = "Multi-Horizon Volatility Forecasting Engine"

DEFAULTS: dict[str, Any] = {
    "asset": "SPY",
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
    {"key": "model_suite", "type": "select", "options": ["har_ml", "har_ridge", "har_gbm", "arch_family", "ginn_research"], "default": "har_ml"},
    {"key": "garch_fit_cap", "type": "integer", "options": [500, 1000, 1500], "default": 1000},
    {"key": "macro_features", "type": "multi_select", "options": ["vix", "vix9d", "vix3m", "yc_slope_10y_2y"], "default": ["vix", "yc_slope_10y_2y"]},
]

OUTPUT_CONTRACT = [
    {"key": "vol_forecast_panel", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "forecast_error_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "vol_term_structure", "location": "charts", "renderer": "curve", "status": "live"},
    {"key": "realized_vs_predicted", "location": "charts", "renderer": "scatter_or_line", "status": "live"},
    {"key": "model_confidence_intervals", "location": "charts", "renderer": "band", "status": "live"},
    {"key": "vix_yield_macro_overlay", "location": "charts", "renderer": "macro_overlay", "status": "live_if_macro_present"},
    {"key": "jump_component_decomposition", "location": "charts", "renderer": "stacked_area", "status": "live"},
    {"key": "realized_vol_estimator_comparison", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "garch_model_selection", "location": "charts", "renderer": "table", "status": "live_if_arch_installed"},
    {"key": "garch_leverage_news_impact_curve", "location": "charts", "renderer": "line", "status": "live_if_arch_installed"},
    {"key": "vol_spillover_network", "location": "charts", "renderer": "network", "status": "live"},
    {"key": "ensemble_vol_forecast_weights", "location": "charts", "renderer": "bar", "status": "live_if_arch_installed"},
    {"key": "rolling_qlike_ensemble_weights", "location": "charts", "renderer": "stacked_area", "status": "live"},
    {"key": "vol_regime_classification", "location": "charts", "renderer": "stacked_area", "status": "live"},
    {"key": "batch_universe_vol_heatmap", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "forecast_tournament", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "forecast_rows", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "vol_regime_diagnostics", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "vol_spillover_edges", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "rolling_qlike_ensemble_weights", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["GINN neural architecture training", "Diebold-Mariano full tournament across large model grid", "GPU sequence-vol ensemble"]
IMPLEMENTATION_NOTES = [
    "Uses HAR-Ridge/HAR-GBM plus capped ARCH-family MLE model selection when arch is installed.",
    "Adds close-to-close, Garman-Klass, Yang-Zhang, and bipower jump decomposition where OHLCV fields are present.",
    "Macro overlay is pulled from category7 macro parquet when available.",
]


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["ginn", "gpu_training"])


def run(payload=None):
    normalized = normalize_feature_payload(payload)
    result = run_vol_forecasting(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
