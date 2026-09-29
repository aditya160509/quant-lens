"""R01 Canonical Test Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import canonical_outputs, response

FEATURE_ID = "01"
FEATURE_NAME = "Canonical Test Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 500},
    {"key": "lookback_days", "type": "number", "default": 2520},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal", "size"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "controls", "type": "select", "default": "none", "options": ["none", "size", "value", "momentum", "reversal", "beta", "ivol", "asset_growth", "profitability", "leverage", "full"]},
    {"key": "fixed_effects", "type": "select", "default": "none", "options": ["none", "time", "asset", "two_way"]},
    {"key": "weighting", "type": "select", "default": "equal", "options": ["equal", "value", "rank"]},
    {"key": "rebalancing_frequency", "type": "select", "default": "monthly", "options": ["daily", "weekly", "monthly", "quarterly"]},
    {"key": "second_signal", "type": "select", "default": "low_vol", "options": ["low_vol", "momentum", "value", "quality", "reversal", "size"]},
    {"key": "benchmark_tickers", "type": "ticker_list", "default": "ff5_mom"},
    {"key": "se_type", "type": "select", "default": "newey_west", "options": ["newey_west", "driscoll_kraay", "double_cluster", "time_cluster", "asset_cluster"]},
    {"key": "nw_lag", "type": "number", "default": 4},
    {"key": "forward_months", "type": "select", "default": 1, "options": [1, 3, 6, 12]},
    {"key": "sort_portfolios", "type": "select", "default": 5, "options": [3, 5, 10]},
    {"key": "rolling_window", "type": "number", "default": 36},
    {"key": "bootstrap_replications", "type": "number", "default": 500},
]

OUTPUTS = [
    "fama_macbeth_regression",
    "panel_ols",
    "portfolio_sort",
    "double_sort_matrix",
    "grs_test",
    "monotonicity_test",
    "rolling_coefficient",
    "calendar_time_portfolio",
    "portfolio_return_series",
    "factor_spanning",
    "fm_validity_flag",
    "weak_identification_card",
    "gmm_vs_shanken_comparison",
    "bootstrap_vs_ttest_disagreement",
    "latex_export",
    "csv_export",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = canonical_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
