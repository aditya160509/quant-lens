"""F03 Placebo and Falsification Suite."""

from __future__ import annotations

from typing import Any

from .inputs import BASE, field, output

FEATURE_ID = "03"
FEATURE_NAME = "Placebo and Falsification Suite"
DESCRIPTION = "Permutation, time-displacement, wrong-direction, McLean-Pontiff out-of-sample and adjacent-asset-class placebos, combined significance, power, and a protected holdout window."

INPUTS = BASE + [
    field("permutation_replications", "Permutation replications", "select", 1000, "Placebos", [500, 1000, 2000]),
    field("time_displacement_months", "Time displacement (months)", "select", 12, "Placebos", [6, 12, 24], "Raised automatically so the future signal cannot overlap the outcome window."),
    field("oos_split", "In-sample share", "select", 0.7, "Placebos", [0.5, 0.6, 0.7]),
    field("sort_portfolios", "Sort portfolios", "select", 5, "Placebos", [3, 5, 10]),
    field("protected_oos_months", "Protected OOS months", "number", 0, "Holdout", min=0, max=60, help_="Reserve the most recent N months: every feature excludes them until you evaluate."),
    field("evaluate_protected", "Evaluate protected window", "boolean", False, "Holdout", help_="Each evaluation is logged; only the first is genuinely out of sample."),
]

OUTPUTS = [
    output("falsification_verdict", "Falsification verdict", "tables", "verdict", primary=True),
    output("placebo_scorecard", "Placebo scorecard", "tables", "scorecard"),
    output("permutation_null_histogram", "Permutation null", "charts", "nullDistribution"),
    output("permutation_placebo", "Permutation placebo", "tables", "keyValue"),
    output("time_displacement_placebo", "Time displacement", "tables", "dataTable"),
    output("wrong_direction_placebo", "Wrong direction", "tables", "dataTable"),
    output("mclean_pontiff_oos", "McLean-Pontiff out-of-sample", "tables", "keyValue"),
    output("oos_coefficient_comparison", "In- vs out-of-sample", "charts", "barCompare"),
    output("adjacent_asset_class_placebo", "Adjacent asset classes", "tables", "dataTable"),
    output("combined_significance", "Combined placebo significance", "tables", "keyValue"),
    output("power_analysis", "Power disclosure", "tables", "keyValue"),
    output("protected_oos", "Protected holdout", "tables", "keyValue"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from ..core.common import response
    from ..core.placebo import run_placebo

    out = run_placebo(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
