"""Feature 10: Market Microstructure Signal Observatory."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "10"
FEATURE_TITLE = "Market Microstructure Signal Observatory"

DEFAULTS: dict[str, Any] = {
    "signal_families": ["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "52w_high", "ivol", "volume_surprise"],
    "ic_protocol": "daily_forward_ic",
    "lookback_days": 756,
    "max_symbols": 250,
    "compute_mode": "realtime",
}

ALIASES = {"signals": "signal_families", "protocol": "ic_protocol"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False, "source": "master_universe.parquet"},
    {"key": "signal_families", "type": "multi_select", "options": ["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "52w_high", "ivol", "volume_surprise", "dollar_vol_momentum", "turnover_rate"], "default": DEFAULTS["signal_families"]},
    {"key": "ic_protocol", "type": "select", "options": ["daily_forward_ic"], "default": "daily_forward_ic"},
    {"key": "amihud_window", "type": "integer", "options": [21, 63], "default": 21},
    {"key": "ivol_model", "type": "select", "options": ["market_residual"], "default": "market_residual"},
]

INPUT_CONTRACT.append({"key":"cost_bps","type":"float","range":[0,1000],"default":10})

OUTPUT_CONTRACT = [
    {"key": "microstructure_ic_leaderboard", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "amihud_illiquidity_surface", "location": "charts", "renderer": "surface_or_heatmap", "status": "live"},
    {"key": "roll_spread_cross_section", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "max_factor_distribution", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "52_week_high_proximity_heatmap", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "ivol_cross_sectional_sort", "location": "charts", "renderer": "bar", "status": "live"},
    {"key": "volume_surprise_signal", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "microstructure_signal_correlation_matrix", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "liquidity_regime_monitor", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "signal_backtest", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "corwin_schultz_spread_cross_section", "location": "charts", "renderer": "histogram", "status": "live"},
    {"key": "hl_amihud_vs_standard_amihud", "location": "charts", "renderer": "scatter_or_table", "status": "live"},
    {"key": "amihud_time_surface", "location": "charts", "renderer": "heatmap", "status": "live"},
    {"key": "microstructure_table", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "ic_leaderboard", "location": "tables", "renderer": "table", "status": "live"},
    {"key": "amihud_time_surface", "location": "tables", "renderer": "table", "status": "live"},
]

RESEARCH_ONLY = ["true bid-ask spread from quote data", "order-flow imbalance", "signed volume", "intraday Lee-Ready classification"]
IMPLEMENTATION_NOTES = ['This engine uses daily OHLCV estimators, not observed bid-ask quotes or order flow.', 'Rolling market OLS residual IVOL, price-change Roll spreads and historical signal IC use observed panels.', 'Volume ratios and notional values are explicitly relative/native-currency quantities, not shares turnover or USD.']


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["quote_data", "order_book", "signed_volume", "cpcv_research"])


def run(payload=None):
    from app.services.ml_v2.core.microstructure import run_microstructure
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_microstructure(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
