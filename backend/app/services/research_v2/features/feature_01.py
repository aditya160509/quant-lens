"""F01 Canonical Test Engine: Fama-MacBeth, panel OLS, sorts, GRS, MR test, spanning, two-pass risk premia."""

from __future__ import annotations

from typing import Any

from .inputs import BASE, field, output
from .merge import merged_inputs, merged_outputs, run_merged

FEATURE_ID = "01"
FEATURE_NAME = "Canonical Test Engine"
DESCRIPTION = "Fama-MacBeth with validity checks, panel OLS with fixed effects, single and double sorts, GRS, the Patton-Timmermann monotonicity test, factor spanning, calendar-time portfolios and a Shanken vs GMM two-pass test."

INPUTS = BASE + [
    field("fixed_effects", "Panel fixed effects", "select", "none", "Inference", ["none", "time", "asset", "two_way"]),
    field("se_type", "Panel standard errors", "select", "clustered_both", "Inference", ["unadjusted", "robust", "clustered_time", "clustered_asset", "clustered_both", "driscoll_kraay"]),
    field("nw_lag", "Newey-West lag (FM)", "text", "auto", "Inference", help_="'auto' uses max(Newey-West plug-in, holding period)."),
    field("bootstrap_replications", "Bootstrap replications", "select", 1000, "Inference", [500, 1000, 2000]),
    field("sort_portfolios", "Sort portfolios", "select", 5, "Sorts", [3, 5, 10]),
    field("second_signal", "Double-sort second signal", "select", "low_vol", "Sorts", ["low_vol", "momentum", "reversal", "size", "value", "beta", "ivol"]),
    field("double_sort_type", "Double-sort type", "select", "independent", "Sorts", ["independent", "sequential"]),
    field("factor_benchmark", "Factor benchmark", "select", "ff5_mom", "Sorts", ["capm", "ff3", "ff5", "ff5_mom"]),
    field("rolling_window", "Rolling window (months)", "select", 36, "Sorts", [12, 24, 36, 60]),
    field("event_window_months", "Calendar-time holding (months)", "select", 6, "Sorts", [3, 6, 12, 24]),
    field("event_quantile", "Calendar-time event threshold", "number", 0.8, "Sorts", min=0.5, max=0.95, help_="Event = signal rank crosses above this percentile."),
]
INPUTS = merged_inputs(INPUTS, "05", "Model checks")

OUTPUTS = [
    output("fama_macbeth_regression", "Fama-MacBeth regression", "tables", "regressionTable", "Time-series means of monthly cross-sectional slopes with Newey-West SEs.", primary=True),
    output("fm_validity_flag", "FM validity", "tables", "testCard"),
    output("rolling_coefficient", "Rolling Fama-MacBeth slope", "charts", "coefficientPath"),
    output("portfolio_sort", "Single portfolio sort", "tables", "portfolioLadder"),
    output("cumulative_long_short", "Long-short growth of $1", "charts", "lineChart"),
    output("double_sort_matrix", "Double-sort mean returns", "tables", "heatmap"),
    output("grs_test", "GRS test", "tables", "testCard"),
    output("monotonicity_test", "Monotonic relation test", "tables", "testCard"),
    output("factor_spanning", "Factor spanning", "tables", "keyValue"),
    output("gmm_vs_shanken_comparison", "Shanken vs GMM risk premia", "tables", "dataTable"),
    output("weak_identification_card", "Weak identification", "tables", "testCard"),
    output("two_pass_model_fit", "Two-pass model fit", "tables", "keyValue"),
    output("panel_ols", "Panel OLS", "tables", "regressionTable"),
    output("hausman_test", "Hausman test", "tables", "testCard"),
    output("calendar_time_portfolio", "Calendar-time portfolio", "tables", "keyValue"),
    output("bootstrap_vs_ttest_disagreement", "Bootstrap vs t-test", "tables", "dataTable"),
    output("portfolio_return_series", "Portfolio returns", "charts", "lineChart"),
    output("latex_export", "LaTeX", "tables", "latex"),
    output("csv_export", "CSV", "tables", "csv"),
]
OUTPUTS = merged_outputs(OUTPUTS, "05", "model_checks", "Model checks")


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from ..core.common import response
    from ..core.canonical import run_canonical

    out = run_canonical(payload or {})
    result = response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
    return run_merged(result, "05", payload or {}, "model_checks", "Model checks")
