"""R08 Signal Decay and Arbitrage Clock."""

from __future__ import annotations

from typing import Any

from ..core.analytics import decay_outputs, response

FEATURE_ID = "08"
FEATURE_NAME = "Signal Decay and Arbitrage Clock"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 400},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "discovery_date", "type": "date", "default": None},
    {"key": "publication_date", "type": "date", "default": None},
    {"key": "rolling_window", "type": "number", "default": 12},
]

OUTPUTS = ["vitality_gauge", "mclean_pontiff_comparison", "decay_curve", "half_life_output", "decay_model_comparison", "andrews_break_chart", "long_short_sharpe_decay", "arbitrage_vs_datamining", "international_replication", "anomaly_lifecycle_summary"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = decay_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
