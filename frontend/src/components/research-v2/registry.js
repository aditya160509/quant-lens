const section = (id, source, chartType = "table", rank = "supporting") => ({
  id,
  title: id.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
  source,
  dataKey: id,
  chartType,
  rank,
});

const inferChartType = (key) => {
  const customTypes = {
    fama_macbeth_regression: "regressionTable",
    panel_ols: "regressionTable",
    portfolio_sort: "portfolioLadder",
    double_sort_matrix: "heatmap",
    grs_test: "testCard",
    monotonicity_test: "testCard",
    factor_spanning: "regressionTable",
    weak_identification_card: "testCard",
    gmm_vs_shanken_comparison: "comparisonTable",
    bootstrap_vs_ttest_disagreement: "testCard",
    coefficient_stability: "coefficientPath",
    specification_curve: "specificationCurve",
    robustness_matrix: "heatmap",
    curve_level_joint_p_value: "testCard",
    researcher_degrees_of_freedom: "decisionLedger",
    decision_attribution_panel: "decisionLedger",
    permutation_null_histogram: "nullDistribution",
    oos_coefficient_comparison: "coefficientCompare",
    combined_significance: "testCard",
    falsification_verdict: "verdict",
    regime_timeline: "regimeRibbon",
    regime_return_chart: "regimeBars",
    markov_state_probability: "regimeRibbon",
    threshold_search: "thresholdCurve",
    residual_distribution: "distribution",
    qq_plot: "qqPlot",
    residual_autocorrelation_correlogram: "correlogram",
    heteroskedasticity_plot: "scatterDiagnostic",
    andrews_structural_break: "breakScan",
    coefficient_forest_plot: "forestPlot",
    publication_table: "publicationTable",
    journal_table_bundle: "publicationTable",
    specification_grid: "decisionLedger",
    event_study_path: "eventStudy",
    treatment_timeline: "treatmentTimeline",
    difference_in_differences: "regressionTable",
    parallel_trends_pretest: "testCard",
    callaway_santanna_att: "eventStudy",
    sun_abraham_event_study: "eventStudy",
    regression_discontinuity: "rddPlot",
    rdd_bandwidth_sensitivity: "rddPlot",
    rdd_mccrary_density_test: "testCard",
    vitality_gauge: "vitalityGauge",
    decay_curve: "decayCurve",
    long_short_sharpe_decay: "decayCurve",
    treated_vs_synthetic_path: "syntheticPath",
    augmented_synthetic_path: "syntheticPath",
    gap_plot: "gapPlot",
    rmspe_ratio_ranking: "placeboRanking",
    donor_weight_table: "donorWeights",
    leave_one_out_sensitivity: "sensitivityTable",
    conformal_confidence_band: "syntheticPath",
    zoo_positioning_chart: "zooMap",
    factor_correlation_map: "heatmap",
    harvey_liu_zhu_card: "testCard",
  };
  if (customTypes[key]) return customTypes[key];
  if (/heatmap|matrix|double_sort/.test(key)) return "heatmap";
  if (/waterfall/.test(key)) return "waterfall";
  if (/timeline|series|curve|path|chart|plot|histogram|correlogram|probability|coefficient|gap/.test(key)) return "line";
  if (/gauge|card|summary|flag|validity/.test(key)) return "metrics";
  return "table";
};

const outputs = (chartKeys, tableKeys, primary) => [
  ...chartKeys.map((key, index) => section(key, "charts", inferChartType(key), index === 0 || key === primary ? "primary" : "supporting")),
  ...tableKeys.map((key) => section(key, "tables", inferChartType(key), key === primary ? "primary" : "supporting")),
];

export const RESEARCH_V2_FEATURES = [
  {
    id: "01", slug: "feature-01", title: "Canonical Test Engine", shortTitle: "Canonical", 
    description: "Cross-sectional factor validation with Fama-MacBeth, panel OLS, portfolio sorts, spanning, inference, and stability diagnostics.",
    defaults: { universe: "master", max_symbols: 500, lookback_days: 2520, signal: "momentum", signal_csv_path: "", controls: "none", fixed_effects: "none", weighting: "equal", rebalancing_frequency: "monthly", second_signal: "low_vol", benchmark_tickers: "ff5_mom", se_type: "newey_west", nw_lag: 4, forward_months: 1, sort_portfolios: 5, rolling_window: 36, bootstrap_replications: 500 },
    fields: [
      f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 500, "Universe"), f("lookback_days", "Lookback Days", "number", 2520, "Window"),
      f("signal", "Primary Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal", "size"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("controls", "Controls", "select", "none", "Specification", ["none", "size", "value", "momentum", "reversal", "beta", "ivol", "asset_growth", "profitability", "leverage", "full"]),
      f("fixed_effects", "Fixed Effects", "select", "none", "Specification", ["none", "time", "asset", "two_way"]), f("weighting", "Portfolio Weighting", "select", "equal", "Portfolio", ["equal", "value", "rank"]), f("rebalancing_frequency", "Rebalance Frequency", "select", "monthly", "Portfolio", ["daily", "weekly", "monthly", "quarterly"]),
      f("second_signal", "Second Sort Signal", "select", "low_vol", "Portfolio", ["low_vol", "momentum", "value", "quality", "reversal", "size"]), f("benchmark_tickers", "Benchmark Library", "ticker_list", "ff5_mom", "Benchmark"), f("se_type", "Standard Errors", "select", "newey_west", "Inference", ["newey_west", "driscoll_kraay", "double_cluster", "time_cluster", "asset_cluster"]),
      f("nw_lag", "Newey-West Lag", "number", 4, "Inference"), f("forward_months", "Forward Months", "select", 1, "Inference", [1, 3, 6, 12]), f("sort_portfolios", "Sort Buckets", "select", 5, "Portfolio", [3, 5, 10]), f("rolling_window", "Rolling Window", "number", 36, "Window"), f("bootstrap_replications", "Bootstrap Replications", "number", 500, "Inference"),
    ],
    sections: outputs(["calendar_time_portfolio", "double_sort_matrix", "portfolio_return_series", "rolling_coefficient"], ["fama_macbeth_regression", "panel_ols", "portfolio_sort", "grs_test", "monotonicity_test", "factor_spanning", "fm_validity_flag", "weak_identification_card", "gmm_vs_shanken_comparison", "bootstrap_vs_ttest_disagreement", "latex_export", "csv_export"], "fama_macbeth_regression"),
  },
  {
    id: "02", slug: "feature-02", title: "Robustness Engine", shortTitle: "Robustness", description: "Specification search, researcher degrees of freedom, joint inference, and coefficient stability under alternative research decisions.",
    defaults: { universe: "master", max_symbols: 500, signal: "momentum", signal_csv_path: "", mode: "sequential", max_specifications: 9, lookback_days: 2520 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 500, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("mode", "Search Mode", "select", "sequential", "Specification", ["sequential", "specification_curve"]), f("max_specifications", "Max Specifications", "number", 9, "Specification"), f("lookback_days", "Lookback Days", "number", 2520, "Window")],
    sections: outputs(["coefficient_stability", "specification_curve"], ["robustness_matrix", "curve_level_joint_p_value", "researcher_degrees_of_freedom", "decision_attribution_panel", "robustness_summary_line", "weakest_specification", "strongest_specification", "economic_magnitude_range", "latex_export"], "specification_curve"),
  },
  {
    id: "03", slug: "feature-03", title: "Placebo and Falsification Suite", shortTitle: "Falsification", description: "Permutation, displaced-time, wrong-direction, adjacent-asset, and out-of-sample challenges to the original result.",
    defaults: { universe: "master", max_symbols: 400, signal: "momentum", signal_csv_path: "", permutation_replications: 500, time_displacement_months: 12, oos_split: 0.7 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 400, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("permutation_replications", "Permutation Replications", "number", 500, "Tests"), f("time_displacement_months", "Time Displacement", "select", 12, "Tests", [6, 12, 24]), f("oos_split", "OOS Split", "select", 0.7, "Tests", [0.5, 0.6, 0.7])],
    sections: outputs(["permutation_null_histogram", "oos_coefficient_comparison"], ["permutation_placebo", "time_displacement_placebo", "wrong_direction_placebo", "adjacent_asset_class_placebo", "mclean_pontiff_oos", "combined_significance", "power_analysis", "falsification_verdict"], "permutation_null_histogram"),
  },
  {
    id: "04", slug: "feature-04", title: "Regime Conditional Analyzer", shortTitle: "Regimes", description: "Conditional factor economics, threshold search, Markov state probability, and stability across macro regimes.",
    defaults: { universe: "master", max_symbols: 400, signal: "momentum", signal_csv_path: "", regime_source: "realized_vol", lookback_days: 2520 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 400, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("regime_source", "Regime Source", "select", "realized_vol", "Regime", ["realized_vol", "vix", "recession", "credit_spread"]), f("lookback_days", "Lookback Days", "number", 2520, "Window")],
    sections: outputs(["regime_timeline", "regime_return_chart", "threshold_search", "markov_state_probability"], ["conditional_return_table", "interaction_regression", "subsample_stability", "macro_state_summary", "chow_test", "quantile_regression", "markov_switching_model", "economic_magnitude_by_regime"], "regime_timeline"),
  },
  {
    id: "05", slug: "feature-05", title: "Diagnostic Center", shortTitle: "Diagnostics", description: "Residual diagnostics, model adequacy tests, serial dependence, influence, missingness, and structural break checks.",
    defaults: { universe: "master", max_symbols: 400, signal: "momentum", signal_csv_path: "", lookback_days: 2520 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 400, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("lookback_days", "Lookback Days", "number", 2520, "Window")],
    sections: outputs(["residual_distribution", "qq_plot", "residual_autocorrelation_correlogram", "heteroskedasticity_plot", "andrews_structural_break"], ["normality_tests", "serial_correlation_tests", "heteroskedasticity_tests", "influence_diagnostics", "missing_data_audit", "vif_table", "reset_test", "structural_break_tests"], "residual_distribution"),
  },
  {
    id: "06", slug: "feature-06", title: "Specification Builder and Publication Output", shortTitle: "Publication", description: "Publication-ready regression tables, forest plots, specification grids, appendices, and journal-specific presentation.",
    defaults: { universe: "master", max_symbols: 400, signal: "momentum", signal_csv_path: "", controls: "size,value", weighting: "equal", max_specifications: 12, table_columns: "", journal_style: "finance" },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 400, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("controls", "Controls", "select", "size,value", "Specification", ["none", "size", "value", "size,value", "size,value,momentum", "full"]), f("weighting", "Weighting", "select", "equal", "Specification", ["equal", "value", "rank"]), f("max_specifications", "Max Specifications", "number", 12, "Specification"), f("table_columns", "Custom Table Columns", "json", "", "Output"), f("journal_style", "Journal Style", "select", "finance", "Output", ["finance", "aer", "jfe", "rfs"])],
    sections: outputs(["coefficient_forest_plot", "spec_curve_auto_table", "table_manifest"], ["publication_table_manifest", "publication_table", "journal_table_bundle", "specification_grid", "auto_built_spec_curve_table", "confirmatory_exploratory_tags", "appendix_latex", "pdf_report"], "publication_table"),
  },
  {
    id: "07", slug: "feature-07", title: "Causal Identification Engine", shortTitle: "Causal", description: "Event studies, DiD, IV, RDD, matching, treatment timing, pre-trends, and causal robustness diagnostics.",
    defaults: { universe: "master", treated_unit: "AAPL", treatment_date: "", event_csv_path: "", instrument_csv_path: "", identification_design: "event_study", lookback_days: 2520 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("treated_unit", "Treated Unit", "ticker", "AAPL", "Treatment"), f("treatment_date", "Treatment Date", "date", "", "Treatment"), f("event_csv_path", "Event File", "file_path", "", "Treatment"), f("instrument_csv_path", "Instrument File", "file_path", "", "Treatment"), f("identification_design", "Identification Design", "select", "event_study", "Design", ["event_study", "did", "iv", "rdd", "matching"]), f("lookback_days", "Lookback Days", "number", 2520, "Window")],
    sections: outputs(["event_study_path", "treatment_timeline"], ["difference_in_differences", "parallel_trends_pretest", "placebo_treatment", "goodman_bacon_decomposition", "callaway_santanna_att", "sun_abraham_event_study", "event_study_car", "event_study_tests", "calendar_time_portfolio_alpha", "pre_event_drift", "post_event_reversal", "matching_balance", "instrumental_variables", "regression_discontinuity", "rdd_bandwidth_sensitivity", "rdd_placebo_cutoffs", "rdd_mccrary_density_test", "rdd_ik_bandwidth", "rdd_covariate_continuity", "rdd_donut_hole"], "event_study_path"),
  },
  {
    id: "08", slug: "feature-08", title: "Signal Decay and Arbitrage Clock", shortTitle: "Decay", description: "Signal vitality, half-life, publication decay, break detection, lifecycle classification, and arbitrage versus data-mining evidence.",
    defaults: { universe: "master", max_symbols: 400, signal: "momentum", signal_csv_path: "", discovery_date: "", publication_date: "", rolling_window: 12 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 400, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("discovery_date", "Discovery Date", "date", "", "Timeline"), f("publication_date", "Publication Date", "date", "", "Timeline"), f("rolling_window", "Rolling Window", "number", 12, "Window")],
    sections: outputs(["decay_curve", "andrews_break_chart", "long_short_sharpe_decay"], ["vitality_gauge", "mclean_pontiff_comparison", "half_life_output", "decay_model_comparison", "arbitrage_vs_datamining", "international_replication", "anomaly_lifecycle_summary"], "vitality_gauge"),
  },
  {
    id: "09", slug: "feature-09", title: "Synthetic Control Engine", shortTitle: "Synthetic", description: "Classical and augmented synthetic control with donor diagnostics, placebo paths, conformal bands, and robust sensitivity output.",
    defaults: { universe: "master", treated_unit: "AAPL", treatment_date: "", event_csv_path: "", donor_limit: 80, lookback_days: 2520, scm_variant: "classic" },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("treated_unit", "Treated Unit", "ticker", "AAPL", "Treatment"), f("treatment_date", "Treatment Date", "date", "", "Treatment"), f("event_csv_path", "Event File", "file_path", "", "Treatment"), f("donor_limit", "Donor Limit", "number", 80, "Donor Pool"), f("lookback_days", "Lookback Days", "number", 2520, "Window"), f("scm_variant", "SCM Variant", "select", "classic", "Specification", ["classic", "augmented_proxy"])],
    sections: outputs(["treated_vs_synthetic_path", "gap_plot", "rmspe_ratio_ranking", "augmented_synthetic_path"], ["donor_weight_table", "pre_treatment_fit", "leave_one_out_sensitivity", "in_time_placebo", "augmented_scm", "generalized_scm", "robust_matrix_completion_scm", "staggered_adoption_scm", "conformal_confidence_band", "latex_export"], "treated_vs_synthetic_path"),
  },
  {
    id: "11", slug: "feature-11", title: "Factor Zoo Positioning Engine", shortTitle: "Factor Zoo", description: "Cross-sectional dependence, multiple-testing threshold, benchmark overlap, spanning, and factor-zoo positioning.",
    defaults: { universe: "master", max_symbols: 500, signal: "momentum", signal_csv_path: "", benchmark_library: "ff5_mom", significance_threshold: 3.0 },
    fields: [f("universe", "Universe", "ticker_list", "master", "Universe"), f("max_symbols", "Universe Size", "number", 500, "Universe"), f("signal", "Signal", "select", "momentum", "Signal", ["momentum", "value", "quality", "low_vol", "reversal"]), f("signal_csv_path", "Custom Signal File", "file_path", "", "Signal"), f("benchmark_library", "Benchmark Library", "select", "ff5_mom", "Benchmark", ["ff5_mom", "extended_proxy"]), f("significance_threshold", "Significance Threshold", "number", 3.0, "Inference")],
    sections: outputs(["zoo_positioning_chart", "factor_correlation_map"], ["harvey_liu_zhu_card", "correlation_with_existing_factors", "extended_spanning_test"], "zoo_positioning_chart"),
  },
];

function f(key, label, type, defaultValue, group, options) {
  return { key, label, type, default: defaultValue, group, options };
}

export function getResearchV2Feature(featureId) {
  const id = String(featureId).replace("feature-", "").replace("feature_", "").padStart(2, "0");
  const feature = RESEARCH_V2_FEATURES.find((item) => item.id === id);
  if (!feature) throw new Error(`Unknown Research V2 feature: ${featureId}`);
  return feature;
}
