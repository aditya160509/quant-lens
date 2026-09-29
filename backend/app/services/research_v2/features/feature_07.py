"""F07 Causal Identification Engine."""

from __future__ import annotations

from typing import Any

from ..core.causal import DESIGNS, OUTCOMES, RUNNING_VARIABLES, run_causal
from ..core.common import response
from .inputs import UNIVERSE, field, output

FEATURE_ID = "07"
FEATURE_NAME = "Causal Identification Engine"
DESCRIPTION = "Difference-in-differences with staggered-timing estimators, abnormal-return event studies, cross-sectional regression discontinuity and instrumental variables, each with its full diagnostic battery."

INPUTS = UNIVERSE + [
    field("identification_design", "Design", "select", "event_study", "Design", [*DESIGNS, "all"]),
    field("event_csv_path", "Event / treatment file", "file", "", "Treatment", help_="CSV with ticker and treatment_date (event_date). Required for staggered DiD and multi-event studies."),
    field("treated_unit", "Treated ticker(s)", "ticker_list", "", "Treatment", help_="Used when no file is uploaded."),
    field("treatment_date", "Treatment / event date", "date", None, "Treatment"),
    field("outcome_variable", "DiD outcome", "select", "return", "DiD", OUTCOMES),
    field("control_group", "DiD controls", "select", "all_untreated", "DiD", ["all_untreated", "matched"], "matched = nearest-neighbour propensity score on pre-period characteristics."),
    field("matches_per_treated", "Matches per treated unit", "number", 5, "DiD", min=1, max=20),
    field("cs_control_group", "Callaway-Sant'Anna controls", "select", "never_treated", "DiD", ["never_treated", "not_yet_treated"]),
    field("pre_period_months", "Pre-period (months)", "select", 12, "DiD", [3, 6, 12, 24, 36]),
    field("post_period_months", "Post-period (months)", "select", 12, "DiD", [3, 6, 12, 24, 36]),
    field("anticipation_months", "Anticipation (months)", "select", 0, "DiD", [0, 1, 2, 3]),
    field("bootstrap_replications", "Placebo replications", "select", 500, "DiD", [100, 500, 1000]),
    field("benchmark_model", "Event-study benchmark", "select", "market", "Event study", ["market", "ff3", "ff5", "dimson"]),
    field("estimation_window", "Estimation window (days)", "select", 250, "Event study", [120, 180, 250]),
    field("event_window", "Event window", "select", "-1,1", "Event study", ["-1,1", "-3,3", "-5,5", "-10,10", "-20,20"]),
    field("abnormal_return_type", "Abnormal return", "select", "car", "Event study", ["car", "bhar"]),
    field("aggregation", "Aggregation", "select", "equal", "Event study", ["equal", "value"]),
    field("contamination_days", "Contamination filter (days)", "select", 0, "Event study", [0, 10, 20, 30]),
    field("running_variable", "RD running variable", "select", "market_cap", "Regression discontinuity", list(RUNNING_VARIABLES)),
    field("cutoff", "RD cutoff", "number", None, "Regression discontinuity", help_="Market cap in USD billions, or a size rank (1 = largest)."),
    field("rd_design", "RD design", "select", "sharp", "Regression discontinuity", ["sharp", "fuzzy"]),
    field("kernel", "Kernel", "select", "triangular", "Regression discontinuity", ["triangular", "uniform", "epanechnikov"]),
    field("polynomial_order", "Polynomial order", "select", 1, "Regression discontinuity", [1, 2, 3]),
    field("bandwidth", "Bandwidth", "text", "auto", "Regression discontinuity", help_="'auto' = CCT MSE-optimal."),
    field("endogenous_variable", "IV endogenous variable", "select", "momentum", "Instrumental variables", ["momentum", "reversal", "low_vol", "beta", "ivol", "size", "value", "profitability", "leverage"]),
    field("additional_endogenous", "Additional endogenous (up to 3)", "multiselect", [], "Instrumental variables", ["reversal", "low_vol", "beta", "ivol", "size", "value"]),
    field("instrument", "Instrument", "select", "lag_3", "Instrumental variables", ["lag_1", "lag_3", "lag_6", "industry_mean", "uploaded"]),
    field("instrument_csv_path", "Instrument file", "file", "", "Instrumental variables", help_="CSV with date, ticker, instrument."),
    field("iv_estimator", "Estimator", "select", "2sls", "Instrumental variables", ["2sls", "liml"]),
    field("iv_controls", "IV controls", "select", "none", "Instrumental variables", ["none", "size", "size,value", "full"]),
    field("cluster", "Cluster by", "select", "date", "Instrumental variables", ["date", "asset"]),
]

OUTPUTS = [
    output("did_estimates", "DiD estimators", "tables", "regressionTable", primary=True),
    output("did_event_study", "DiD event study (TWFE)", "charts", "eventStudy"),
    output("callaway_santanna_event", "Callaway-Sant'Anna event study", "charts", "eventStudy"),
    output("sun_abraham_event", "Sun-Abraham event study", "charts", "eventStudy"),
    output("parallel_trends_pretest", "Parallel trends pre-test", "tables", "testCard"),
    output("goodman_bacon_decomposition", "Goodman-Bacon decomposition", "tables", "dataTable"),
    output("goodman_bacon_scatter", "Goodman-Bacon weights", "charts", "baconScatter"),
    output("callaway_santanna_att", "Group ATT (Callaway-Sant'Anna)", "tables", "dataTable"),
    output("did_placebo_treatment", "Placebo treatment", "tables", "keyValue"),
    output("did_placebo_distribution", "Placebo distribution", "charts", "nullDistribution"),
    output("covariate_balance", "Covariate balance", "tables", "dataTable"),
    output("covariate_balance_matched", "Balance after matching", "tables", "dataTable"),
    output("did_sample", "DiD sample", "tables", "keyValue"),
    output("event_study_verdict", "Event-study verdict", "tables", "verdict"),
    output("car_event_path", "CAR path", "charts", "eventStudy"),
    output("event_study_tests", "Event-window tests", "tables", "dataTable"),
    output("pre_event_drift", "Pre-event drift (-20,-2)", "tables", "dataTable"),
    output("post_event_continuation", "Post-event (+2,+20)", "tables", "dataTable"),
    output("car_distribution", "CAR distribution", "charts", "distribution"),
    output("calendar_time_portfolio_alpha", "Calendar-time alpha", "tables", "keyValue"),
    output("rd_estimate", "RD estimate", "tables", "keyValue"),
    output("rd_plot", "RD plot", "charts", "rdPlot"),
    output("rd_density_test", "Manipulation test", "tables", "testCard"),
    output("rd_density", "Running-variable density", "charts", "density"),
    output("rd_placebo_chart", "Placebo cutoffs", "charts", "placeboCutoffs"),
    output("rd_bandwidth_chart", "Bandwidth sensitivity", "charts", "placeboCutoffs"),
    output("rd_covariate_continuity", "Covariate continuity", "tables", "dataTable"),
    output("rd_donut_hole", "Donut hole", "tables", "dataTable"),
    output("iv_first_stage", "First stage", "tables", "dataTable"),
    output("iv_second_stage", "2SLS vs OLS", "tables", "dataTable"),
    output("anderson_rubin_confidence_set", "Anderson-Rubin set", "tables", "keyValue"),
    output("iv_ar_pvalue_curve", "AR p-value curve", "charts", "lineChart"),
    output("iv_tests", "Endogeneity and over-identification", "tables", "dataTable"),
    output("iv_assessment", "Instrument assessment", "tables", "keyValue"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_causal(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
