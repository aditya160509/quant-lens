import {
  Activity, Binary, BrainCircuit, GitBranch, Layers, ScanSearch, ShieldCheck, Waves,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/apiBase";
import type { LabConfig, FeatureMeta, Page } from "@/modules/research/lab";
import type { FeatureLayout, Item, Section } from "@/modules/research/layouts";
import { group, registerViews } from "@/modules/research/outputs/registry";
import { isNum, out } from "@/modules/research/format";
import type { FeatureSpec, InputSpec, OutputSpec } from "@/modules/research/types";

/** ML features carry an "ml" prefix in the workspace so their runs and settings never collide with Research. */
const ID = (raw: string) => `ml${raw}`;
const RAW = (id: string) => id.replace(/^ml/, "");

const CATALOG: Record<string, FeatureMeta & { about: string }> = {
  mlvalidate: { name: "Validate my strategy", slug: "validate", icon: ShieldCheck, question: "Does my backtest hold up, and if not, exactly why?",
    about: "Upload your returns, predictions, feature panel or every trial you ran. The strategy is tested against simple controls, shuffled signals, purged cross-validation, a block bootstrap, a parameter sweep, a look-ahead audit and out-of-sample transfer, then given one verdict with the reasons ranked." },
  ml01: { name: "Purged CV for a model", slug: "cpcv", icon: ScanSearch, question: "Is the backtest Sharpe real, or an artefact of leaky validation?",
    about: "Combinatorial purged cross-validation: date groups are tested in every combination, with training rows that overlap a test label purged and an embargo after each test block. The spread of path Sharpes is the honest answer." },
  ml02: { name: "Alpha model", slug: "alpha", icon: BrainCircuit, question: "Which names does the model rank highest, and why?",
    about: "Gradient-boosted and linear models chosen by nested chronological validation, scored by information coefficient on a held-out period, and explained with exact SHAP values." },
  ml03: { name: "Volatility forecasts", slug: "volatility", icon: Activity, question: "How volatile will this asset be, and which model forecasts it best?",
    about: "HAR family models and ARCH-type models forecast realised volatility at several horizons, with intervals calibrated before the hold-out and scored by QLIKE and MAE." },
  ml04: { name: "Improve my strategy", slug: "barriers", icon: Binary, question: "Which trades hit their target before their stop, and does filtering them help?",
    about: "Events are labelled by which barrier the high/low path touches first. Same-bar touches stay ambiguous rather than guessed. Meta-labels and conformal intervals are fitted out of fold." },
  ml05: { name: "Allocation", slug: "allocation", icon: GitBranch, question: "How should capital be spread when estimates are noisy?",
    about: "Hierarchical risk parity, nested clustered optimisation and minimum variance, refit monthly on past data only, traded at the next close with turnover costs." },
  ml06: { name: "Market state", slug: "regimes", icon: Waves, question: "Which market state are we in, and how long do states last?",
    about: "A hidden Markov model fitted on the training window and filtered forward without smoothing, so every date's state uses only data up to that date." },
  ml08: { name: "Composite baseline", slug: "composite", icon: Layers, question: "How should factors be combined into one score, and does it hold up?",
    about: "Factors weighted by their historical IC and IC-IR, re-selected on past data only, and traded long-short with lagged execution and costs." },
};

const PAGES: Page[] = [
  { id: "validate", label: "Validate", icon: ShieldCheck, question: "Does the backtest hold up once leakage, luck and trial count are removed?", features: ["mlvalidate", "ml01", "ml04"] },
  { id: "alpha", label: "Alpha", icon: BrainCircuit, question: "Which names rank highest, why, and does the ranking beat a simple composite?", features: ["ml02", "ml08"] },
  { id: "risk", label: "Volatility & risk", icon: Activity, question: "How much risk is ahead, and which market state are we in?", features: ["ml03", "ml06"] },
  { id: "allocate", label: "Allocation", icon: GitBranch, question: "How should capital be spread when estimates are noisy?", features: ["ml05"] },
];

/** Output → view. Anything not listed is drawn from the contract's type and encoding. */
const VIEW: Record<string, Record<string, string>> = {
  validate: { autopsy: "valAutopsy", controls: "valControls", cpcv: "valCpcv", monte_carlo: "valMonteCarlo", transfer: "valTransfer", plateau: "valPlateau", stability: "valStability",
    deflated_sharpe: "valOverfit", leakage: "valLeakage", improve: "valImprove", receipt: "valReceipt" },
  "01": { cpcv_sharpe_distribution: "mlSharpeSpread", backtest_paths_chart: "mlPathFan", per_fold_performance: "mlFoldMatrix", probability_of_backtest_overfitting: "mlKpi", deflated_sharpe_ratio: "mlKpi", cpcv_path_metrics: "dataTable" },
  "02": { prediction_rank_table: "mlRankTable", shap_beeswarm: "mlBeeswarm", shap_waterfall_top_signal: "mlWaterfall", model_ic_leaderboard: "mlLeaderboard", rolling_monthly_ic_series: "mlIcBars", training_audit: "mlReceipt" },
  "03": { vol_forecast_panel: "mlVolPanel", realized_vs_predicted: "mlVolScatter", vol_term_structure: "mlTermStructure", forecast_tournament: "mlTournament", forecast_error_distribution: "mlTournament", ensemble_vol_forecast_weights: "mlStacked" },
  "04": { triple_barrier_label_distribution: "mlLabelMix", barrier_hit_path_examples: "mlBarrierScatter", barrier_sensitivity_surface: "mlBarrierSurface", cqr_coverage_audit: "mlCoverage", barrier_parameters: "mlReceipt" },
  "05": { hrp_weight_vector: "mlWeights", cluster_dendrograms: "mlDendrogram", risk_contribution_decomposition: "mlRiskContrib", walk_forward_allocation: "mlEquity", black_litterman_posterior_return_vector: "mlBlShift", bl_vs_pure_hrp_weight_comparison: "mlBlShift" },
  "06": { regime_probability_time_series: "mlRegimes", parallel_gmm_regime_probabilities: "mlRegimes", regime_transition_heatmap: "mlTransition", transition_matrix: "mlTransition", regime_conditional_asset_returns: "mlRegimeReturns", ensemble_vs_hmm_comparison: "mlKpi", correlation_network_density: "mlKpi", current_regime_probabilities: "mlReceipt", training_audit: "mlReceipt" },
  "08": { long_short_backtest: "mlEquity", ic_weighted_composite_weights: "mlWeights", walk_forward_weight_stability: "mlStacked" },
};

type RawInput = InputSpec & { integer?: boolean };
type RawOutput = { id?: string; key?: string; title?: string; label?: string; path?: string; location?: string; type?: string; encoding?: Record<string, unknown>; status?: string; primary?: boolean; depends_on?: unknown };
type RawFeature = { id: string; title: string; status?: string; inputs: RawInput[]; outputs: RawOutput[]; known_limitations?: string[] };

/** Upload ids are chosen with the file picker, which uploads the CSV and fills in the id. */
const UPLOADS: Record<string, string> = { upload_id: "Your data", trials_upload_id: "Every trial you ran", benchmark_upload_id: "Benchmark returns" };
/** Raw JSON hand-offs are filled by "Validate this run" buttons, not typed. */
const HIDDEN_INPUTS = new Set(["source_result"]);

/** Inputs whose text value is sent as a list. */
const LIST_KEYS = new Set<string>();

function toSpec(f: RawFeature): FeatureSpec {
  const id = ID(f.id);
  const seen = new Set<string>();
  const outputs: OutputSpec[] = [];
  for (const o of f.outputs) {
    const key = o.id ?? o.key ?? "";
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const source = (o.path?.split(".")[0] ?? o.location ?? "charts") as OutputSpec["source"];
    outputs.push({ key, title: o.title ?? o.label ?? key, source, render: VIEW[f.id]?.[key] ?? (o.type === "table" ? "dataTable" : "mlAuto"), primary: o.primary, encoding: o.encoding, type: o.type, status: o.status });
  }
  for (const i of f.inputs) if (i.type === "ticker_list" || i.type === "text_list") LIST_KEYS.add(i.key);
  return {
    id, name: f.title, description: CATALOG[id]?.about ?? "",
    inputs: f.inputs.filter((i) => !HIDDEN_INPUTS.has(i.key)).map((i) => ({
      ...i, group: i.group || "Settings", default: Array.isArray(i.default) && i.type !== "multiselect" ? i.default.join(", ") : i.default,
      ...(UPLOADS[i.key] ? { type: "file" as const, label: UPLOADS[i.key] } : {}),
    })),
    outputs,
  };
}

/** Text fields that hold lists ("AAPL, MSFT" or "1, 5, 21") go to the API as arrays. */
function payloadFor(payload: Record<string, unknown>) {
  const outp: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (LIST_KEYS.has(k) && typeof v === "string") {
      const parts = v.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
      outp[k] = parts.every((p) => /^-?\d+(\.\d+)?$/.test(p)) ? parts.map(Number) : parts.map((p) => p.toUpperCase());
    } else outp[k] = v;
  }
  return outp;
}

/* ---------------------------------------------------------------- layouts */

const card = (keys: string | string[], span: number, extra: Omit<Item, "keys" | "span"> = {}): Item => ({ keys: Array.isArray(keys) ? keys : [keys], span, ...extra });
const sec = (id: string, labelText: string, items: Item[], intro?: string): Section => ({ id, label: labelText, intro, items });
const data = (keys: string[]): Section => sec("data", "Data", keys.map((k) => card(k, 12)), "Every number behind the charts, for export or your own checks.");

const fmt = (v: unknown, d = 2) => (isNum(v) ? v.toFixed(d) : "–");

/** Validate returns its verdict at the top level of the result. */
const verdictOf = (r: unknown) => (r as { verdict?: { label?: string; headline?: string } }).verdict;
const VTONE: Record<string, "up" | "warn" | "down"> = { "HELD UP": "up", MIXED: "warn", FAILED: "down" };

const LAYOUTS: Record<string, FeatureLayout> = {
  mlvalidate: {
    sections: [
      sec("verdict", "Verdict", [card("autopsy", 12, { view: "valVerdict", title: "The verdict and every check behind it", flush: false })]),
      sec("why", "Why", [card("autopsy", 7, { title: "Overfitting autopsy: causes ranked" }), card("autopsy", 5, { view: "valCostCurve", title: "Sharpe as costs rise" })],
        "Each way a backtest can lie, scored by how much of the result it explains."),
      sec("controls", "Against controls", [card("controls", 7, { title: "Your strategy against simple alternatives" }), card("controls", 5, { view: "valShuffle", title: "Against shuffled signals" })],
        "The verdict is measured against the best of these, never against zero."),
      sec("robust", "Robustness", [card("cpcv", 4, { title: "Purged cross-validation" }), card("monte_carlo", 4, { title: "Block bootstrap" }), card("transfer", 4, { title: "Out-of-sample transfer" }),
        card("plateau", 7, { title: "Parameter sweep" }), card(["deflated_sharpe", "pbo", "min_backtest_length"], 5, { title: "Trial count and history" }), card("stability", 6, { title: "Seed stability" }), card("leakage", 6, { title: "Look-ahead audit" })]),
      sec("improve", "Improve", [card("improve", 12, { title: "Improve my strategy: meta-label filter and sizing" })], "A second model learns which of your trades to skip or shrink, fitted out of fold. Always shown beside the strategy as uploaded."),
      sec("receipt", "Receipt", [card(["receipt", "data_quality"], 12, { title: "Reproducibility receipt" })]),
    ],
    verdict: (r) => {
      const v = verdictOf(r);
      return v?.label ? { headline: `${v.label}. ${v.headline ?? ""}`, tone: VTONE[v.label] ?? null } : { headline: null, tone: null };
    },
  },
  ml01: {
    sections: [
      sec("result", "Result", [card("cpcv_sharpe_distribution", 12, { title: "Sharpe across every CPCV path" }), card("backtest_paths_chart", 8, { title: "Backtest paths" }), card("purged_vs_naive_cv_comparison", 4, { title: "Purged vs naive CV", hint: "The gap is the leakage a naive split hides." })]),
      sec("protocol", "Protocol", [card("per_fold_performance", 12, { view: "mlFoldMatrix", title: "Train, purge and test by split", flush: false }), card("embargo_sensitivity", 6), card(["probability_of_backtest_overfitting", "deflated_sharpe_ratio"], 6, { title: "Overfitting tests" })],
        "Which data trained and tested each split, and whether the result survives a longer embargo."),
      data(["per_fold_performance", "cpcv_path_metrics"]),
    ],
    verdict: (r) => {
      const s = out(r, "cpcv_sharpe_distribution").map((x) => x.sharpe).filter(isNum).sort((a, b) => a - b);
      if (!s.length) return { headline: null, tone: null };
      const med = s[Math.floor(s.length / 2)], pos = s.filter((x) => x > 0).length / s.length;
      return { headline: `Median path Sharpe ${fmt(med)} across ${s.length} purged paths; ${Math.round(pos * 100)}% are positive. Worst path ${fmt(s[0])}, best ${fmt(s[s.length - 1])}.`, tone: med > 0.5 && pos >= 0.8 ? "up" : med > 0 ? "warn" : "down" };
    },
  },
  ml02: {
    sections: [
      sec("ranking", "Ranking", [card("prediction_rank_table", 7, { title: "Today's ranking" }), card("shap_waterfall_top_signal", 5, { title: "Why the top name ranks first" })]),
      sec("explain", "Explain", [card("shap_beeswarm", 7, { title: "What drives predictions" }), card("shap_feature_importance", 5, { title: "Mean |SHAP| by feature" })], "Exact SHAP values on the latest predictions: direction, size and spread of each feature's effect."),
      sec("quality", "Model quality", [card("model_ic_leaderboard", 6, { title: "Models by test IC" }), card("rolling_monthly_ic_series", 6, { title: "IC by month, held-out period" }), card("tuning_trials", 6), card("training_audit", 6, { title: "Training receipt" })]),
      data(["current_predictions", "model_performance", "heldout_predictions"]),
    ],
    verdict: (r) => {
      const lb = out(r, "model_ic_leaderboard");
      const chosen = String(r.summary_cards?.find((c) => /selected model/i.test(c.label))?.value ?? "");
      const m = lb.find((x) => String(x.model) === chosen) ?? [...lb].filter((x) => isNum(x.test_ic)).sort((a, b) => (b.test_ic as number) - (a.test_ic as number))[0];
      const top = out(r, "prediction_rank_table").find((x) => x.rank === 1);
      const ic = m?.test_ic;
      return { headline: m && isNum(ic) ? `Selected model ${String(m.model)}: held-out IC ${fmt(ic, 3)}.${top ? ` Top-ranked name today: ${String(top.ticker)}.` : ""}` : null, tone: isNum(ic) ? (ic > 0.03 ? "up" : ic > 0 ? "warn" : "down") : null };
    },
  },
  ml03: {
    sections: [
      sec("forecast", "Forecast", [card("vol_forecast_panel", 12, { title: "Forecast against realised volatility" }), card("vol_term_structure", 6, { title: "Term structure today" }), card("realized_vol_estimator_comparison", 6, { title: "Volatility estimators now" })]),
      sec("tournament", "Model tournament", [card("forecast_tournament", 6, { title: "Loss by model and horizon" }), card("realized_vs_predicted", 6, { title: "Forecast vs realised" }), card("garch_model_selection", 6), card("garch_leverage_news_impact_curve", 6, { title: "News impact curves" }), card("ensemble_vol_forecast_weights", 12)]),
      data(["forecast_rows", "forecast_error_distribution", "model_confidence_intervals"]),
    ],
  },
  ml04: {
    sections: [
      sec("labels", "Labels", [card("barrier_hit_path_examples", 8, { title: "Which barrier was hit, and when" }), card("triple_barrier_label_distribution", 4, { title: "Label mix" }), card("event_outcome_timeline", 12, { title: "Events over time" })]),
      sec("sensitivity", "Sensitivity", [card("barrier_sensitivity_surface", 7, { title: "Label mix by barrier width" }), card("label_method_comparison", 5, { title: "Fixed vs volatility-scaled barriers" })]),
      sec("meta", "Meta-labels", [card("meta_label_probability_distribution", 6), card("cqr_coverage_audit", 6, { title: "Conformal interval coverage" }), card("cqr_interval_width_distribution", 6)]),
      data(["barrier_parameters", "label_audit", "barrier_sensitivity"]),
    ],
  },
  ml05: {
    sections: [
      sec("weights", "Weights", [card("hrp_weight_vector", 6, { title: "Allocation" }), card("risk_contribution_decomposition", 6, { title: "Risk contribution" })]),
      sec("structure", "Cluster structure", [card("cluster_dendrograms", 12, { title: "Clustering tree and reordered correlations" })]),
      sec("backtest", "Walk-forward", [card("walk_forward_allocation", 12, { title: "Monthly refits, next-close execution, net of costs" })]),
      sec("bl", "Black–Litterman", [card("black_litterman_posterior_return_vector", 6, { title: "Prior → posterior returns" }), card("bl_vs_pure_hrp_weight_comparison", 6, { title: "Posterior weight vs allocation" })]),
      data(["hrp_weights", "black_litterman", "quasi_diagonalized_covariance_heatmap", "allocation_training_audit"]),
    ],
  },
  ml06: {
    sections: [
      sec("state", "State", [card("regime_probability_time_series", 12, { title: "Regime probabilities (filtered, no look-ahead)" }), card("regime_transition_heatmap", 6, { title: "Transitions and expected duration" }), card("regime_conditional_asset_returns", 6, { title: "Mean daily return by regime" })]),
      sec("checks", "Checks", [card("pc1_variance_monitor", 8, { title: "First principal component share" }), card("ensemble_vs_hmm_comparison", 4, { title: "Classifier agreement (out of sample)" }), card("parallel_gmm_regime_probabilities", 8, { title: "Gaussian mixture, for comparison" }), card("correlation_network_density", 4)]),
      data(["current_regime_probabilities", "transition_matrix", "training_audit"]),
    ],
    verdict: (r) => {
      const c = out(r, "current_regime_probabilities")[0];
      return { headline: c ? `Current state ${String(c.dominant_state)} as of ${String(c.date)}.` : null, tone: null };
    },
  },
  ml08: {
    sections: [
      sec("performance", "Performance", [card("long_short_backtest", 12, { title: "Composite long-short, net of costs" })]),
      sec("weights", "Weights", [card("ic_weighted_composite_weights", 5, { title: "Latest factor weights" }), card("walk_forward_weight_stability", 7, { title: "Weights through time" }), card("factor_correlation_heatmap", 7, { title: "Factor correlations" }), card("composite_signal_distribution", 5, { title: "Latest composite scores" })]),
      data(["latest_composite_scores", "factor_weights", "training_audit"]),
    ],
  },
};

const V = group(() => import("./views") as Promise<Record<string, unknown>>);
const VV = group(() => import("./validateViews") as Promise<Record<string, unknown>>);
registerViews({
  valVerdict: VV.ValVerdict, valAutopsy: VV.ValAutopsy, valCostCurve: VV.ValCostCurve, valControls: VV.ValControls, valShuffle: VV.ValShuffle, valCpcv: VV.ValCpcv, valMonteCarlo: VV.ValMonteCarlo,
  valTransfer: VV.ValTransfer, valPlateau: VV.ValPlateau, valStability: VV.ValStability, valOverfit: VV.ValOverfit, valLeakage: VV.ValLeakage, valImprove: VV.ValImprove, valReceipt: VV.ValReceipt,
}, ["valCostCurve", "valControls", "valTransfer", "valPlateau", "valStability"]);
registerViews({
  mlAuto: V.MlAuto, mlKpi: V.MlKpi, mlReceipt: V.MlReceipt, mlEquity: V.MlEquity, mlSharpeSpread: V.MlSharpeSpread, mlPathFan: V.MlPathFan, mlFoldMatrix: V.MlFoldMatrix,
  mlRankTable: V.MlRankTable, mlBeeswarm: V.MlBeeswarm, mlWaterfall: V.MlWaterfall, mlIcBars: V.MlIcBars, mlLeaderboard: V.MlLeaderboard, mlVolPanel: V.MlVolPanel,
  mlVolScatter: V.MlVolScatter, mlTermStructure: V.MlTermStructure, mlTournament: V.MlTournament, mlBarrierScatter: V.MlBarrierScatter, mlBarrierSurface: V.MlBarrierSurface, mlLabelMix: V.MlLabelMix,
  mlCoverage: V.MlCoverage, mlWeights: V.MlWeights, mlRiskContrib: V.MlRiskContrib, mlDendrogram: V.MlDendrogram, mlBlShift: V.MlBlShift, mlRegimes: V.MlRegimes,
  mlTransition: V.MlTransition, mlRegimeReturns: V.MlRegimeReturns, mlStacked: V.MlStacked,
 
 
}, ["mlAuto", "mlEquity", "mlPathFan", "mlBeeswarm", "mlWaterfall", "mlIcBars", "mlLeaderboard", "mlVolPanel", "mlVolScatter", "mlTermStructure", "mlTournament", "mlBarrierScatter",
  "mlBarrierSurface", "mlLabelMix", "mlCoverage", "mlWeights", "mlRiskContrib", "mlDendrogram", "mlBlShift", "mlRegimes", "mlTransition", "mlRegimeReturns", "mlStacked",
  "mlSharpeSpread"]);

export const ML_LAB: LabConfig = {
  id: "ml",
  title: "Machine learning",
  root: "/ml",
  base: `${API_BASE_URL}/ml/v2`,
  catalog: CATALOG,
  pages: PAGES,
  layouts: LAYOUTS,
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => ID(f.id) in CATALOG).map(toSpec),
  submit: (featureId, payload) => ({ path: `/features/${RAW(featureId)}/jobs`, body: payloadFor(payload) }),
  signal: false,
  defaultUniverse: "35 US large caps",
  overview: {
    intro: "Four pages, one rule: nothing ships unless it holds up out of sample. Every split is chronological and purged, every result is measured against simple controls, and anything the data cannot support is marked unavailable rather than approximated.",
    stages: [
      { id: "validate", label: "Validate", intro: "Kill bad ideas cheaply: purged cross-validation, overfitting tests and a barrier-based trade filter.", ids: ["mlvalidate", "ml01", "ml04"] },
      { id: "alpha", label: "Alpha", intro: "A cross-sectional ranking explained name by name, beside the IC-weighted composite it has to beat.", ids: ["ml02", "ml08"] },
      { id: "risk", label: "Volatility & risk", intro: "Forecast volatility with a scored model tournament, and read the market state without look-ahead.", ids: ["ml03", "ml06"] },
      { id: "allocate", label: "Allocation", intro: "Shrinkage-based weights with risk-parity and equal-weight controls, tested walk-forward net of costs.", ids: ["ml05"] },
    ],
  },
};

