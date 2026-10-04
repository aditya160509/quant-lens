"""F02 Robustness Engine: sequential or full specification curve with a curve-level permutation test."""

from __future__ import annotations

from typing import Any

from ..core.common import response
from ..core.robustness import DIMENSIONS, run_robustness
from .merge import merged_inputs, merged_outputs, run_merged
from .inputs import BASE, field, output

FEATURE_ID = "02"
FEATURE_NAME = "Robustness Engine"
DESCRIPTION = "Re-runs the base test across time windows, subsamples, crisis exclusions, universes, signal transforms, controls, standard errors and weighting, then tests the whole curve."

INPUTS = BASE + [
    field("mode", "Mode", "select", "sequential", "Robustness", ["sequential", "specification_curve"], "Sequential changes one dimension at a time; the curve runs every combination (sampled above the cap)."),
    field("dimensions", "Dimensions", "multiselect", DIMENSIONS, "Robustness", DIMENSIONS),
    field("max_specifications", "Max specifications", "number", 60, "Robustness", min=5, max=5000),
    field("weighting_philosophy", "Curve weighting", "select", "unweighted", "Robustness", ["unweighted", "sample_size", "inverse_variance", "aic", "bic"]),
    field("permutation_replications", "Curve permutations", "select", 200, "Robustness", [0, 100, 200, 500]),
    field("custom_split_date", "Custom split date", "date", None, "Robustness"),
    field("custom_exclusion_start", "Custom exclusion start", "date", None, "Robustness"),
    field("custom_exclusion_end", "Custom exclusion end", "date", None, "Robustness"),
]

OUTPUTS = [
    output("robustness_summary_line", "Robustness summary", "tables", "summaryLine", primary=True),
    output("specification_curve", "Specification curve", "charts", "specificationCurve"),
    output("decision_panel", "Decision panel", "charts", "decisionLedger"),
    output("curve_level_joint_p_value", "Curve-level permutation test", "tables", "testCard"),
    output("permutation_null", "Permutation null (median |t|)", "charts", "nullDistribution"),
    output("researcher_degrees_of_freedom", "Researcher degrees of freedom", "tables", "keyValue"),
    output("decision_attribution_panel", "Decision attribution", "tables", "barList"),
    output("robustness_matrix", "Robustness matrix", "tables", "robustnessMatrix"),
    output("weakest_specification", "Weakest specification", "tables", "explanation"),
    output("strongest_specification", "Strongest specification", "tables", "explanation"),
    output("coefficient_stability_stats", "Coefficient stability", "tables", "boxSummary"),
    output("economic_magnitude_range", "Economic magnitude range", "tables", "keyValue"),
    output("skipped_specifications", "Skipped specifications", "tables", "dataTable"),
    output("latex_export", "LaTeX", "tables", "latex"),
]
INPUTS = merged_inputs(INPUTS, "04", "Regimes")
OUTPUTS = merged_outputs(OUTPUTS, "04", "regimes", "Regimes")


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_robustness(payload or {})
    result = response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
    return run_merged(result, "04", payload or {}, "regimes", "Regimes")
