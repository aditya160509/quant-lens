"""R04 Regime Conditional Analyzer."""

from __future__ import annotations

from typing import Any

from ..core.analytics import regime_outputs, response

FEATURE_ID = "04"
FEATURE_NAME = "Regime Conditional Analyzer"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 400},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "regime_source", "type": "select", "default": "realized_vol", "options": ["realized_vol", "vix", "recession", "credit_spread"]},
    {"key": "lookback_days", "type": "number", "default": 2520},
]

OUTPUTS = [
    "regime_timeline",
    "conditional_return_table",
    "regime_return_chart",
    "interaction_regression",
    "subsample_stability",
    "macro_state_summary",
    "chow_test",
    "threshold_search",
    "quantile_regression",
    "markov_state_probability",
    "markov_switching_model",
    "economic_magnitude_by_regime",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = regime_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
