"""F05 Diagnostic Center."""

from __future__ import annotations

from typing import Any

from ..core.common import response
from ..core.diagnostics import run_diagnostics
from .inputs import BASE, field, output

FEATURE_ID = "05"
FEATURE_NAME = "Diagnostic Center"
DESCRIPTION = "Every validity test a referee asks for, each with a plain-language reading and a specific fix."

INPUTS = BASE + [
    field("significance_level", "Flag at", "select", 0.05, "Diagnostics", [0.01, 0.05, 0.10]),
    field("break_date", "Chow break date", "date", None, "Diagnostics", help_="Leave empty to rely on the Andrews scan."),
    field("influential_top", "Influential observations", "select", 10, "Diagnostics", [5, 10, 20]),
    field("partial_residual_plots", "Partial residual plots", "boolean", True, "Diagnostics"),
    field("extended_influence", "DFBETA / DFFITS", "boolean", True, "Diagnostics"),
]

OUTPUTS = [
    output("diagnostic_report_card", "Diagnostic report card", "tables", "reportCard", primary=True),
    output("vif_table", "Variance inflation factors", "tables", "dataTable"),
    output("residual_autocorrelation_correlogram", "Correlogram of FM premia", "charts", "correlogram"),
    output("heteroskedasticity_plot", "Squared residuals vs fitted", "charts", "scatter"),
    output("andrews_structural_break", "Andrews sup-F scan", "charts", "breakScan"),
    output("partial_residual_plots", "Partial residual plots", "charts", "partialResiduals"),
    output("influential_observation_table", "Influential months", "tables", "dataTable"),
    output("dfbeta_dffits_table", "DFBETA / DFFITS", "tables", "dataTable"),
    output("qq_plot", "Q-Q plot", "charts", "qqPlot"),
    output("serial_correlation_tests", "Serial correlation tests", "tables", "dataTable"),
    output("heteroskedasticity_tests", "Heteroskedasticity tests", "tables", "dataTable"),
    output("reset_test", "RESET test", "tables", "testCard"),
    output("structural_break_tests", "Structural break tests", "tables", "dataTable"),
    output("normality_tests", "Normality", "tables", "dataTable"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_diagnostics(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
