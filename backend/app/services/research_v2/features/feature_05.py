"""R05 Diagnostic Center."""

from __future__ import annotations

from typing import Any

from ..core.analytics import diagnostics_outputs, response

FEATURE_ID = "05"
FEATURE_NAME = "Diagnostic Center"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 400},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "lookback_days", "type": "number", "default": 2520},
]

OUTPUTS = [
    "normality_tests",
    "serial_correlation_tests",
    "heteroskedasticity_tests",
    "residual_distribution",
    "qq_plot",
    "influence_diagnostics",
    "missing_data_audit",
    "vif_table",
    "reset_test",
    "residual_autocorrelation_correlogram",
    "heteroskedasticity_plot",
    "structural_break_tests",
    "andrews_structural_break",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = diagnostics_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
