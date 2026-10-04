import { first, isNum, label, num, out, pval, rowsOf, tstat } from "./format";
import type { FeatureResult, FeatureSpec } from "./types";

export type Tone = "up" | "down" | "warn";
export type Verdict = { headline: string | null; tone: Tone | null };

/** One card. `keys` lets a single card combine several outputs (e.g. three event-study estimators). */
export type Item = { keys: string[]; view?: string; span: number; title?: string; hint?: string; opts?: Record<string, unknown>; flush?: boolean };
export type Section = { id: string; label: string; intro?: string; items: Item[] };
type FeatureLayout = { sections: Section[]; verdict?: (r: FeatureResult) => Verdict };

const card = (keys: string | string[], span: number, extra: Omit<Item, "keys" | "span"> = {}): Item => ({ keys: Array.isArray(keys) ? keys : [keys], span, ...extra });
const tests = (keys: string[], span: number, title: string, hint?: string): Item => ({ keys, span, view: "tests", title, hint, flush: true });
const exportSection = (keys: string[]): Section => ({ id: "export", label: "Export", intro: "Tables ready for a paper, and the raw numbers.", items: keys.map((k) => card(k, 12)) });

/** Verdict tone from a p-value: significant passes, borderline is mixed, otherwise it fails. */
const pTone = (p: unknown): Tone => (!isNum(p) ? "warn" : p < 0.05 ? "up" : p < 0.1 ? "warn" : "down");

const LAYOUTS: Record<string, FeatureLayout> = {
  "01": {
    sections: [
      { id: "pricing", label: "Pricing", intro: "Does the signal earn a premium in cross-sectional regressions?", items: [
        card("fama_macbeth_regression", 7, { view: "regressionTable", flush: true, hint: "Monthly cross-sectional slopes, Newey-West errors" }),
        tests(["fm_validity_flag", "grs_test", "monotonicity_test", "weak_identification_card", "hausman_test"], 5, "Specification tests", "Click a test for its details"),
        card("rolling_coefficient", 12, { hint: "Rolling Fama-MacBeth slope with its 95% band. Drag to zoom, add notes to dates." }),
      ] },
      { id: "portfolios", label: "Portfolios", intro: "Sort stocks by the signal and compare the returns of each bucket.", items: [
        card("portfolio_sort", 6, { view: "portfolioLadder", hint: "Mean monthly return per quintile with 95% intervals" }),
        card("cumulative_long_short", 6, { view: "growth", hint: "Growth of $1 in the long-short portfolio, and its drawdown" }),
        card("portfolio_return_series", 12, { view: "cumulative", hint: "Cumulative return of every quintile. Hover to read all of them at one date." }),
        card("double_sort_matrix", 7, { hint: "Mean return of 5 × 5 portfolios, with the long-short spread of each row" }),
        card("bootstrap_vs_ttest_disagreement", 5, { view: "tstats", flush: true, title: "Bootstrap vs t-test", hint: "Where resampling and the classical test disagree" }),
      ] },
      { id: "asset-pricing", label: "Asset pricing", intro: "Is the premium explained by known factors?", items: [
        card("gmm_vs_shanken_comparison", 7, { flush: true, hint: "Risk premia under Shanken-corrected OLS and GLS-GMM", opts: { columns: ["factor", "lambda_ols", "t_shanken", "lambda_gmm_gls", "t_gmm", "material_disagreement"], hide: ["se_uncorrected", "se_shanken", "se_gmm"] } }),
        card("two_pass_model_fit", 5, { opts: { hero: ["shanken_multiplier", "j_stat", "j_p_value"] } }),
        card("factor_spanning", 6, { view: "spanning", hint: "Alpha and factor loadings of the long-short portfolio" }),
        card("calendar_time_portfolio", 6, { opts: { hero: ["alpha", "alpha_t", "alpha_p"] } }),
        card("panel_ols", 12, { view: "regressionTable", flush: true, hint: "Panel regression with fixed effects" }),
      ] },
      exportSection(["latex_export", "csv_export"]),
    ],
    verdict: (r) => {
      const fm = out(r, "fama_macbeth_regression").find((x) => x.term === "signal");
      return { headline: typeof r.meta.headline === "string" ? r.meta.headline : null, tone: fm ? pTone(fm.p_value) : null };
    },
  },

  "02": {
    sections: [
      { id: "curve", label: "Specification curve", intro: "Every reasonable way to run the test, sorted by the answer it gives.", items: [
        card("specification_curve", 12, { hint: "Each dot is one specification. The grid below shows the choices behind it." }),
        card("specification_curve", 12, { view: "byChoice", title: "By choice", hint: "Estimates per choice value: box, median, MAD and IQR" }),
        card("decision_attribution_panel", 6, { hint: "Share of the variation in estimates explained by each decision" }),
        card("permutation_null", 6, { hint: "Median |t| across specifications when the signal is shuffled", opts: { tail: "right", observedLabel: "Your curve", observed: { key: "curve_level_joint_p_value", field: "observed" } } }),
        tests(["curve_level_joint_p_value"], 6, "Whole-curve test", "Is the curve as a whole stronger than chance?"),
        card(["coefficient_stability_stats", "strongest_specification", "weakest_specification"], 6, { view: "stability", title: "Stability", hint: "How far the estimate moves across specifications" }),
      ] },
      { id: "specifications", label: "Specifications", intro: "The full grid of estimates.", items: [
        card("robustness_matrix", 12, { flush: true, hint: "Every specification with its estimate, interval and tests" }),
        card("skipped_specifications", 12, { flush: true, hint: "Specifications that could not be estimated, and why" }),
      ] },
      { id: "magnitude", label: "Magnitude", items: [
        card("economic_magnitude_range", 6, { opts: { hero: ["min_ls_annual_return", "max_ls_annual_return", "share_within_50pct_of_base"] } }),
        card("researcher_degrees_of_freedom", 6, { opts: { hero: ["reasonable_specifications", "usable_specifications"] } }),
      ] },
      exportSection(["latex_export"]),
    ],
    verdict: (r) => {
      const s = first(r, "robustness_summary_line");
      const j = first(r, "curve_level_joint_p_value");
      if (!s) return { headline: null, tone: null };
      const sig = isNum(s.significant_5pct) ? s.significant_5pct : 0;
      const total = isNum(s.specifications) ? s.specifications : 1;
      const p = j && isNum(j.p_value) ? j.p_value : null;
      const share = sig / total;
      const robust = share >= 0.5 && p !== null && p < 0.05;
      const fragile = share < 0.2 || (p !== null && p >= 0.1);
      const headline = robust
        ? `Robust. ${sig} of ${total} specifications are significant at 5%, and the curve beats the shuffled null (p = ${p?.toFixed(3)}).`
        : fragile
          ? `Not robust. Only ${sig} of ${total} specifications are significant at 5%${p !== null ? `, and the curve does not beat the shuffled null (p = ${p.toFixed(3)})` : ""}.`
          : `Mixed. ${sig} of ${total} specifications are significant at 5%${p !== null ? `; curve permutation p = ${p.toFixed(3)}` : ""}.`;
      return { headline, tone: robust ? "up" : fragile ? "down" : "warn" };
    },
  },

  "03": {
    sections: [
      { id: "scorecard", label: "Scorecard", intro: "A real effect should beat every fake version of itself.", items: [
        card("placebo_scorecard", 5),
        card("permutation_null_histogram", 7, { title: "Permutation null", hint: "t-statistics when the signal is randomly reassigned across stocks", opts: { tail: "two", observedLabel: "Real t", observed: { key: "permutation_real_t", field: "t_stat" }, xLabel: "t-statistic" } }),
      ] },
      { id: "placebos", label: "Placebos", intro: "Shift the signal in time, flip its direction, or apply it where it should not work.", items: [
        card("time_displacement_placebo", 6, { view: "tstats", flush: true, hint: "The real signal against the same signal shifted in time" }),
        card("wrong_direction_placebo", 6, { view: "tstats", flush: true, hint: "Long-short returns of reversed and scrambled portfolios" }),
        card("adjacent_asset_class_placebo", 12, { view: "tstats", flush: true, hint: "The same signal on asset classes where it should not work" }),
      ] },
      { id: "oos", label: "Out of sample", intro: "Does the effect survive after the sample it was found in?", items: [
        card(["mclean_pontiff_oos", "oos_coefficient_comparison"], 6, { view: "barCompare", title: "In sample vs out of sample" }),
        card("power_analysis", 6, { view: "power", hint: "Chance each placebo detects a true effect of this size" }),
        tests(["combined_significance", "permutation_placebo"], 6, "Combined evidence"),
        card("protected_oos", 6, { hint: "A holdout window reserved before looking at results" }),
      ] },
    ],
    verdict: (r) => {
      const v = first(r, "falsification_verdict");
      if (!v) return { headline: null, tone: null };
      const tone: Tone = v.verdict === "green" ? "up" : v.verdict === "red" ? "down" : "warn";
      return { headline: `${String(v.message ?? "")} ${num(v.passed)} of ${num(v.tests)} placebos passed.`, tone };
    },
  },

  "04": {
    sections: [
      { id: "premium", label: "Premium by regime", intro: "Split months by market condition and estimate the premium in each.", items: [
        card("coefficient_comparison", 6, { hint: "Signal premium in each regime with 95% intervals" }),
        card("regime_conditional_sharpe", 6, { view: "bars", hint: "Long-short Sharpe ratio in each regime", opts: { label: "regime", value: "ls_sharpe" } }),
        card("regime_timeline", 12, { title: "Regime timeline", hint: "Probability of the high-premium state, with the observed regime underneath" }),
        card("conditional_coefficient_table", 12, { view: "regressionTable", flush: true }),
      ] },
      { id: "tests", label: "Tests", intro: "Is the difference between regimes statistically real?", items: [
        tests(["chow_test", "premium_difference_test"], 6, "Difference tests"),
        card("interaction_regression", 6, { view: "regressionTable", flush: true, hint: "Pooled regression with a signal × regime interaction" }),
        card("quantile_regression", 6, { view: "quantile", hint: "How the condition shifts each part of the return distribution" }),
        card("economic_magnitude_by_regime", 6, { opts: { hero: ["stress_annual_spread", "calm_annual_spread", "amplification_factor"] } }),
      ] },
      { id: "models", label: "Models", items: [
        card("markov_switching_model", 6, { opts: { hero: ["premium_state_high", "premium_state_low"] } }),
        card("threshold_search", 6, { hint: "Fit across candidate thresholds" }),
        card("regime_definition", 6),
        card("skipped_regimes", 6, { flush: true }),
      ] },
    ],
    verdict: (r) => {
      const chow = first(r, "chow_test");
      const diff = first(r, "premium_difference_test");
      const def = first(r, "regime_definition");
      const p = [chow?.p_value, diff?.p_value].filter(isNum);
      const minP = p.length ? Math.min(...p) : null;
      const cond = String(def?.description ?? "the condition");
      if (minP === null) return { headline: null, tone: null };
      return minP < 0.05
        ? { headline: `The premium depends on the regime. Splitting on ${cond}, the best test rejects equal premia (p = ${minP.toFixed(3)}).`, tone: "up" }
        : { headline: `No regime effect. Splitting on ${cond} does not change the premium significantly (lowest p = ${minP.toFixed(3)}).`, tone: "warn" };
    },
  },

  "05": {
    sections: [
      { id: "report", label: "Report card", intro: "Every assumption behind the regressions, checked.", items: [card("diagnostic_report_card", 12)] },
      { id: "residuals", label: "Residuals", items: [
        card("residual_autocorrelation_correlogram", 6, { hint: "Autocorrelation of residuals by lag with the 95% band" }),
        card("qq_plot", 6, { hint: "Points on the diagonal mean normally distributed residuals" }),
        card("heteroskedasticity_plot", 6, { hint: "Squared residuals should not trend with fitted values", opts: { xy: ["fitted", "squared_residual"] } }),
        card("residual_distribution", 6, { view: "distribution", title: "Residual distribution" }),
      ] },
      { id: "stability", label: "Stability", items: [
        card("andrews_structural_break", 12, { hint: "Chow F at every candidate break date against the sup-F critical value" }),
        card("partial_residual_plots", 12, { hint: "Is each regressor's effect linear?" }),
      ] },
      { id: "influence", label: "Influence", items: [
        card("influential_observation_table", 6, { flush: true, hint: "Months that move the premium most" }),
        card("dfbeta_dffits_table", 6, { flush: true, hint: "Single observations with outsized leverage" }),
        tests(["serial_correlation_tests", "heteroskedasticity_tests", "reset_test", "structural_break_tests"], 7, "Formal tests"),
        card(["normality_tests", "vif_table"], 5, { view: "dataTable", flush: true, title: "Normality and collinearity" }),
      ] },
    ],
    verdict: (r) => {
      const rows = out(r, "diagnostic_report_card");
      if (!rows.length) return { headline: null, tone: null };
      const red = rows.filter((x) => x.flag === "red");
      return {
        headline: red.length ? `${red.length} of ${rows.length} diagnostics flag a problem: ${red.slice(0, 3).map((x) => String(x.test).split(" (")[0]).join(", ")}${red.length > 3 ? " and more" : ""}.` : `Clean. All ${rows.length} diagnostics pass.`,
        tone: red.length === 0 ? "up" : red.length <= 2 ? "warn" : "down",
      };
    },
  },

  "06": {
    sections: [
      { id: "table", label: "Table", intro: "The journal-ready table, column by column.", items: [
        card("publication_table", 8),
        card("coefficient_forest_plot", 4, { hint: "The signal coefficient in each column" }),
        card("column_specifications", 12, { flush: true, hint: "What each column estimates" }),
        card("confirmatory_exploratory_tags", 12, { flush: true, hint: "Locked (pre-registered) columns are confirmatory" }),
      ] },
      exportSection(["latex_export", "csv_export", "pdf_export"]),
    ],
    verdict: (r) => {
      const cols = out(r, "column_specifications").length;
      const conf = out(r, "confirmatory_exploratory_tags").filter((x) => x.tag === "confirmatory").length;
      return { headline: `${cols} column${cols === 1 ? "" : "s"} built, ${conf} confirmatory. Copy the LaTeX from Export.`, tone: null };
    },
  },

  "07": {
    sections: [
      { id: "did", label: "Difference in differences", intro: "Compare treated and untreated units before and after treatment.", items: [
        card("did_estimates", 5, { hint: "Average effect under each estimator" }),
        card(["did_event_study", "callaway_santanna_event", "sun_abraham_event"], 7, { view: "eventStudy", title: "Event study", hint: "Effect by month relative to treatment", opts: { names: ["TWFE", "Callaway-Sant'Anna", "Sun-Abraham"] } }),
        tests(["parallel_trends_pretest", "did_placebo_treatment"], 6, "Identification checks"),
        card("did_placebo_distribution", 6, { hint: "Estimates from randomly assigned fake treatments", opts: { tail: "two", observedLabel: "Real estimate", observed: { key: "did_placebo_treatment", field: "real_estimate" } } }),
        card("goodman_bacon_scatter", 7, { hint: "Each 2×2 comparison inside the TWFE estimate" }),
        card("covariate_balance", 5, { view: "lovePlot", hint: "Standardised mean differences before matching" }),
        card("callaway_santanna_att", 6, { view: "forestPlot", hint: "Average effect for each treatment cohort", opts: { label: "cohort" } }),
        card("did_sample", 6),
        card("goodman_bacon_decomposition", 12, { flush: true }),
        card("covariate_balance_matched", 12, { flush: true }),
      ] },
      { id: "event", label: "Event study", intro: "Abnormal returns around each event date.", items: [
        card("car_event_path", 8, { view: "eventStudy", hint: "Mean cumulative abnormal return with its 95% band" }),
        card("event_study_verdict", 4, { view: "prose" }),
        card("event_study_tests", 6, { view: "tstats", flush: true, hint: "Four test statistics for the announcement window" }),
        card("car_distribution", 6, { hint: "Cumulative abnormal return of each event" }),
        card("pre_event_drift", 6, { view: "tstats", flush: true, hint: "Leakage before the event" }),
        card("post_event_continuation", 6, { view: "tstats", flush: true, hint: "Drift or reversal after the event" }),
        card("calendar_time_portfolio_alpha", 12, { opts: { hero: ["alpha_monthly", "alpha_t", "alpha_p"] } }),
      ] },
      { id: "rd", label: "Regression discontinuity", intro: "Compare units just above and just below a cutoff.", items: [
        card("rd_plot", 8, { hint: "Binned means either side of the cutoff with local fits" }),
        card("rd_estimate", 4, { opts: { hero: ["estimate_bias_corrected", "p_value_robust"], hide: ["running_variable"] } }),
        card("rd_density", 6, { hint: "Is there bunching just above or below the cutoff?" }),
        card("rd_bandwidth_chart", 6, { hint: "Estimate as the bandwidth widens or narrows" }),
        card("rd_placebo_chart", 6, { hint: "Fake cutoffs should show no jump" }),
        card("rd_covariate_continuity", 6, { view: "forestPlot", hint: "Covariates should not jump at the cutoff", opts: { label: "covariate" } }),
        tests(["rd_density_test"], 6, "Manipulation test"),
        card("rd_donut_hole", 6, { flush: true, hint: "Dropping observations closest to the cutoff" }),
      ] },
      { id: "iv", label: "Instrumental variables", intro: "Use an instrument to isolate exogenous variation.", items: [
        card("iv_first_stage", 6, { view: "firstStage" }),
        card("iv_second_stage", 6, { view: "regressionTable", flush: true, hint: "2SLS and OLS estimates" }),
        card("iv_ar_pvalue_curve", 7, { view: "arCurve", hint: "Anderson-Rubin test across hypothesised coefficients" }),
        tests(["iv_tests"], 5, "IV tests"),
        card(["iv_assessment", "anderson_rubin_confidence_set"], 12, { view: "facts", title: "Assessment" }),
      ] },
    ],
    verdict: (r) => {
      const parts: string[] = [];
      const twfe = out(r, "did_estimates").find((x) => x.estimator === "TWFE");
      const pre = first(r, "parallel_trends_pretest");
      const ev = first(r, "event_study_verdict");
      const rd = first(r, "rd_estimate");
      const fs = first(r, "iv_first_stage");
      if (twfe) parts.push(`DiD ${num(twfe.estimate, 4)} (t ${tstat(twfe.t_stat)})${pre && isNum(pre.p_value) ? `, pre-trend p ${pval(pre.p_value)}` : ""}`);
      if (ev) parts.push(`event study: ${String(ev.verdict).replace(/\.$/, "")}`);
      if (rd) parts.push(`RD ${num(rd.estimate_bias_corrected, 4)} (p ${pval(rd.p_value_robust)})`);
      if (fs) parts.push(`IV first-stage F ${num(fs.f_stat, 1)}`);
      const sig = (twfe && isNum(twfe.p_value) && twfe.p_value < 0.05) || (rd && isNum(rd.p_value_robust) && rd.p_value_robust < 0.05);
      return { headline: parts.length ? `${sig ? "Evidence of an effect." : "No significant effect."} ${parts.join("; ")}.` : null, tone: sig ? "up" : "warn" };
    },
  },

  "08": {
    sections: [
      { id: "vitality", label: "Vitality", intro: "How much of the original predictive power is left.", items: [
        card("vitality_gauge", 4),
        card(["anomaly_lifecycle_summary"], 8, { view: "prose", title: "Life cycle" }),
        card("decay_curve", 12, { hint: "Rolling predictive power with exponential, linear and hyperbolic decay fits" }),
      ] },
      { id: "decay", label: "Decay", items: [
        card("long_short_sharpe_decay", 7, { view: "sharpeDecay", hint: "Rolling long-short Sharpe with discovery and publication marked" }),
        card("sharpe_life_cycle", 5, { view: "bars", hint: "Sharpe ratio in each phase", opts: { label: "period", value: "sharpe" } }),
        card("half_life_output", 4, { opts: { hero: ["half_life_months"] } }),
        card("decay_model_comparison", 8, { flush: true, hint: "Which decay shape fits best", opts: { hide: ["params"] } }),
        card("mclean_pontiff_comparison", 6, { opts: { hero: ["survival_fraction", "decay_t_stat"] } }),
        card("arbitrage_vs_datamining", 6, { hint: "Arbitrage predicts faster decay where trading is cheap" }),
      ] },
      { id: "arrival", label: "Arbitrage arrival", items: [
        card("andrews_break_chart", 12, { view: "breakScan", hint: "When did the signal break down?", opts: { info: "arbitrage_arrival" } }),
        card("international_replication", 12, { flush: true, hint: "Does the same decay show up in other markets?" }),
      ] },
    ],
    verdict: (r) => {
      const g = first(r, "vitality_gauge");
      const s = first(r, "anomaly_lifecycle_summary");
      const v = isNum(g?.vitality_score) ? (g?.vitality_score as number) : null;
      const sentence = typeof s?.summary === "string" ? s.summary.split(/(?<=\.)\s/).slice(0, 2).join(" ") : null;
      return { headline: sentence ? `${v !== null && v < 30 ? "Largely arbitraged away." : v !== null && v < 70 ? "Weakening." : "Still alive."} ${sentence}` : null, tone: v === null ? null : v >= 70 ? "up" : v >= 30 ? "warn" : "down" };
    },
  },

  "09": {
    sections: [
      { id: "effect", label: "Effect", intro: "The treated unit against its synthetic counterpart.", items: [
        card("treated_vs_synthetic_path", 8, { hint: "Treated path and its synthetic control" }),
        card("treatment_effect", 4, { opts: { hero: ["cumulative_effect_log", "mean_post_gap"] } }),
        card(["gap_plot", "placebo_gap_paths"], 8, { view: "gapPlot", title: "Gap against placebos", hint: "Treated gap (bold) against every donor run as a placebo" }),
        card("rmspe_ratio_chart", 4, { hint: "Post / pre fit ratio. Treated in colour." }),
        card("conformal_band", 12, { hint: "Monthly effect with a conformal confidence band" }),
      ] },
      { id: "donors", label: "Donors", items: [
        card("donor_weight_table", 6, { view: "donorWeights", hint: "Who the synthetic control is made of" }),
        card("leave_one_out_sensitivity", 6, { view: "forestPlot", hint: "Effect after dropping each donor", opts: { label: "excluded_donor", estimate: "post_effect", refX: null } }),
        card("donor_concentration", 6, { opts: { hero: ["effective_donors", "hhi", "top3_share"] } }),
        card("leave_one_out_summary", 6),
      ] },
      { id: "inference", label: "Inference", items: [
        tests(["rmspe_ratio_ranking", "pre_treatment_fit"], 6, "Placebo inference"),
        card("in_time_placebo", 6),
        card("variant_details", 6),
        card("staggered_adoption_scm", 6, { flush: true }),
        card("staggered_event_study", 12, { view: "eventStudy" }),
      ] },
      exportSection(["latex_export"]),
    ],
    verdict: (r) => {
      const t = first(r, "treatment_effect");
      const rk = first(r, "rmspe_ratio_ranking");
      if (!t) return { headline: null, tone: null };
      const p = isNum(rk?.placebo_p_value) ? (rk?.placebo_p_value as number) : null;
      return {
        headline: `${p !== null && p < 0.1 ? "Significant effect." : "Not distinguishable from placebos."} ${String(t.treated_unit)} after ${String(t.treatment_date).slice(0, 7)}: ${num(t.cumulative_effect_log, 3)} log cumulative return, placebo p = ${p === null ? "–" : p.toFixed(3)}.`,
        tone: p === null ? null : p < 0.1 ? "up" : "warn",
      };
    },
  },

  "11": {
    sections: [
      { id: "hurdle", label: "Hurdle", intro: "With hundreds of published factors, a new one needs a much higher t-statistic.", items: [
        card("harvey_liu_zhu_card", 12, { view: "hlzRuler" }),
      ] },
      { id: "position", label: "Position", items: [
        card("zoo_positioning_chart", 7, { hint: "Your signal among established factors" }),
        card("factor_correlation_map", 5, { hint: "Outlined cells: correlation above 0.7" }),
        card("extended_spanning_test", 6, { view: "spanning", hint: "Alpha after controlling for the factor library" }),
        card("correlation_with_existing_factors", 6, { view: "diverging", hint: "Signed correlation with each established factor" }),
        card("candidate_summary", 12, { opts: { hero: ["annual_sharpe", "t_stat", "ic_ir_annual"] } }),
      ] },
    ],
    verdict: (r) => {
      const c = first(r, "harvey_liu_zhu_card");
      if (!c) return { headline: null, tone: null };
      const t = Math.abs(isNum(c.observed_t) ? c.observed_t : 0);
      const req = isNum(c.required_t) ? c.required_t : 3;
      return { headline: `${t >= req ? "Clears the factor-zoo hurdle." : "Below the factor-zoo hurdle."} |t| = ${t.toFixed(2)} against a required ${req.toFixed(2)} (${label(c.threshold_rule)}).`, tone: t >= req ? "up" : "down" };
    },
  },
};

const EXPORT_RENDERS = new Set(["latex", "csv", "pdf"]);
const WIDE = new Set(["specificationCurve", "byChoice", "robustnessMatrix", "regressionTable", "publicationTable", "eventStudy", "lineChart", "coefficientPath", "heatmap", "regimeRibbon", "decayCurve", "syntheticPath", "reportCard", "dataTable"]);

/** The purpose-built layout, or one generated from the manifest so new outputs always appear. */
/**
 * Pages merged in the backend (section B): a feature's result also carries another feature's outputs
 * under a prefix. They get one section each, laid out like the source feature.
 */
const MERGES: Record<string, { prefix: string; from: string; label: string }[]> = {
  "01": [{ prefix: "model_checks__", from: "05", label: "Model checks" }],
  "02": [{ prefix: "regimes__", from: "04", label: "By regime" }],
  "07": [{ prefix: "synthetic__", from: "09", label: "Synthetic control" }],
  "08": [{ prefix: "factor_zoo__", from: "11", label: "Novelty" }],
};

function mergedSections(featureId: string): Section[] {
  return (MERGES[featureId] ?? []).map((m) => ({
    id: m.prefix.replace(/_+$/, ""),
    label: m.label,
    items: (LAYOUTS[m.from]?.sections ?? []).filter((sec) => sec.id !== "export").flatMap((sec) => sec.items).map((i) => ({ ...i, keys: i.keys.map((k) => m.prefix + k) })),
  }));
}

export function layoutFor(feature: FeatureSpec): FeatureLayout {
  const own = LAYOUTS[feature.id];
  const merged = mergedSections(feature.id);
  const custom = own && merged.length ? { ...own, sections: [...own.sections.filter((x) => x.id !== "export"), ...merged, ...own.sections.filter((x) => x.id === "export")] } : own;
  const placed = new Set(custom?.sections.flatMap((s) => s.items.flatMap((i) => i.keys)) ?? []);
  const prose = new Set(["summaryLine", "verdict"]);
  const prefixes = (MERGES[feature.id] ?? []).map((m) => m.prefix);
  const extra = feature.outputs.filter((o) => !placed.has(o.key) && !prefixes.some((pre) => o.key.startsWith(pre) && /(latex|csv|pdf|export)/i.test(o.render)) && !EXPORT_RENDERS.has(o.render) && !(custom && prose.has(o.render)) && o.render !== "decisionLedger");
  if (custom) {
    return extra.length ? { ...custom, sections: [...custom.sections, { id: "more", label: "More", items: extra.map((o) => card(o.key, WIDE.has(o.render) ? 12 : 6)) }] } : custom;
  }
  const exports = feature.outputs.filter((o) => EXPORT_RENDERS.has(o.render));
  return {
    sections: [
      { id: "results", label: "Results", items: extra.map((o) => card(o.key, WIDE.has(o.render) ? 12 : 6)) },
      ...(exports.length ? [exportSection(exports.map((o) => o.key))] : []),
    ],
  };
}

export function verdictFor(feature: FeatureSpec, result: FeatureResult): Verdict {
  const custom = LAYOUTS[feature.id]?.verdict;
  if (custom) return custom(result);
  if (typeof result.meta.headline === "string") return { headline: result.meta.headline, tone: null };
  const prose = feature.outputs.find((o) => o.render === "summaryLine" || o.render === "verdict");
  const row = prose ? rowsOf(result[prose.source][prose.key])[0] : undefined;
  const text = row ? [row.summary, row.message, row.verdict].find((v): v is string => typeof v === "string") : undefined;
  return { headline: text ?? null, tone: null };
}
