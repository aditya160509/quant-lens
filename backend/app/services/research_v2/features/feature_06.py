"""F06 Specification Builder and Publication Output."""

from __future__ import annotations

from typing import Any

from .inputs import SIGNAL, UNIVERSE, field, output

FEATURE_ID = "06"
FEATURE_NAME = "Specification Builder and Publication Output"
DESCRIPTION = "Builds a 2-8 column journal table, each column with its own estimator, controls, fixed effects, standard errors, weighting and period. Exports booktabs LaTeX, a 6.5-inch PDF and CSV."

INPUTS = UNIVERSE + SIGNAL + [
    field("number_of_columns", "Columns (default layout)", "select", 4, "Table", [2, 3, 4, 5, 6, 7, 8]),
    field("alternative_signal", "Alternative signal (column 8)", "select", "low_vol", "Table", ["low_vol", "reversal", "momentum", "value", "size", "beta"]),
    field("table_columns", "Custom columns (JSON)", "json", "", "Table", help_='List of objects: label, signal, dependent_variable, controls, estimator (fama_macbeth|panel_ols), se, fixed_effects, weighting, start, end.'),
    field("auto_populate", "Auto-populate", "select", "manual", "Table", ["manual", "spec_curve"], "spec_curve picks columns at the 10/25/50/75/90th percentiles of the Feature 2 curve."),
    field("table_title", "Table title", "text", "Cross-sectional return predictability", "Presentation"),
    field("variable_labels", "Variable labels (JSON)", "json", "", "Presentation", help_='e.g. {"signal": "Value signal"}'),
    field("significance_stars", "Stars", "select", "standard", "Presentation", ["standard", "five_one", "custom"]),
    field("custom_star_thresholds", "Custom thresholds", "text", "0.01,0.05,0.10", "Presentation"),
    field("statistics_rows", "Statistics rows", "multiselect", ["r2", "within_r2", "observations", "months", "fixed_effects", "estimator", "se", "tag"], "Presentation", ["r2", "within_r2", "observations", "months", "period", "fixed_effects", "estimator", "se", "tag"]),
    field("table_notes", "Table notes", "text", "", "Presentation"),
]

OUTPUTS = [
    output("publication_table", "Publication table", "tables", "publicationTable", primary=True),
    output("coefficient_forest_plot", "Coefficient forest plot", "charts", "forestPlot"),
    output("confirmatory_exploratory_tags", "Confirmatory / exploratory", "tables", "dataTable"),
    output("column_specifications", "Column specifications", "tables", "dataTable"),
    output("latex_export", "LaTeX (booktabs)", "tables", "latex"),
    output("pdf_export", "PDF", "tables", "pdf"),
    output("csv_export", "CSV", "tables", "csv"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from ..core.common import response
    from ..core.specification import run_specification

    out = run_specification(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
