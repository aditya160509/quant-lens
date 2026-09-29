"""R11 Cross-Sectional Dependence and Factor Zoo Positioning Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import factor_zoo_outputs, response

FEATURE_ID = "11"
FEATURE_NAME = "Cross-Sectional Dependence and Factor Zoo Positioning Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 500},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "benchmark_library", "type": "select", "default": "ff5_mom", "options": ["ff5_mom", "extended_proxy"]},
    {"key": "significance_threshold", "type": "number", "default": 3.0},
]

OUTPUTS = ["zoo_positioning_chart", "harvey_liu_zhu_card", "correlation_with_existing_factors", "extended_spanning_test", "factor_correlation_map"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = factor_zoo_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
