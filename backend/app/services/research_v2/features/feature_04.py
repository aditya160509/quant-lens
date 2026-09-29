"""F04 Regime Conditional Analyzer."""

from __future__ import annotations

from typing import Any

from ..core.common import response
from ..core.regime import CONDITIONS, run_regime
from .inputs import BASE, field, output

FEATURE_ID = "04"
FEATURE_NAME = "Regime Conditional Analyzer"
DESCRIPTION = "Re-runs the test within market states and formally tests the difference: Chow test, signal x regime interaction, threshold search, quantile and Markov-switching models."

INPUTS = BASE + [
    field("conditioning_variable", "Conditioning variable", "select", "vix_20", "Regime", list(CONDITIONS)),
    field("second_condition", "Second condition (intersection)", "select", "none", "Regime", ["none", *CONDITIONS]),
    field("threshold_selection", "Threshold", "select", "fixed", "Regime", ["fixed", "data_driven"], "Data-driven grid-searches the conditioning variable for the largest Chow F."),
    field("regime_structure", "Regime structure", "select", "two_state", "Regime", ["two_state", "quantile", "markov"]),
    field("min_observations", "Minimum months per regime", "number", 24, "Regime", min=6, max=120),
    field("sort_portfolios", "Sort portfolios", "select", 5, "Regime", [3, 5, 10]),
]

OUTPUTS = [
    output("conditional_coefficient_table", "Regime-conditional premia", "tables", "regressionTable", primary=True),
    output("coefficient_comparison", "Coefficient by regime", "charts", "forestPlot"),
    output("chow_test", "Chow test", "tables", "testCard"),
    output("premium_difference_test", "Premium difference test", "tables", "testCard"),
    output("interaction_regression", "Interaction regression", "tables", "regressionTable"),
    output("regime_conditional_sharpe", "Regime Sharpe ratios", "tables", "dataTable"),
    output("economic_magnitude_by_regime", "Regime amplification", "tables", "keyValue"),
    output("regime_timeline", "Regime timeline", "charts", "regimeRibbon"),
    output("threshold_search", "Threshold search", "charts", "lineChart"),
    output("quantile_regression", "Quantile regression on the condition", "tables", "dataTable"),
    output("markov_switching_model", "Markov-switching model", "tables", "keyValue"),
    output("markov_state_probability", "High-premium state probability", "charts", "lineChart"),
    output("regime_definition", "Regime definition", "tables", "keyValue"),
    output("skipped_regimes", "Skipped regimes", "tables", "dataTable"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_regime(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
