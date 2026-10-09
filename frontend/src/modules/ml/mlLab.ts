import {
  Activity, Binary, BrainCircuit, GitBranch, ScanSearch, ShieldCheck, Waves, Workflow,
} from "lucide-react";
import dynamic from "next/dynamic";
import { API_BASE_URL } from "@/lib/apiBase";
import type { LabConfig, FeatureMeta, Page } from "@/modules/research/lab";
import type { FeatureLayout, Item, Section } from "@/modules/research/layouts";
import { group, registerAlternates, registerViews } from "@/modules/research/outputs/registry";
import { isNum, out } from "@/modules/research/format";
import type { FeatureSpec, InputSpec, OutputSpec } from "@/modules/research/types";
import { takeaway } from "./takeaways";

/** ML features carry an "ml" prefix in the workspace so their runs and settings never collide with Research. */
const ID = (raw: string) => `ml${raw}`;
const RAW = (id: string) => id.replace(/^ml/, "");

const CATALOG: Record<string, FeatureMeta & { about: string }> = {
  mlvalidate: { name: "Validate my strategy", slug: "validate", icon: ShieldCheck, question: "Does my backtest hold up, and if not, exactly why?",
    about: "Upload your returns, predictions, feature panel or every trial you ran. The strategy is tested against simple controls, shuffled signals, purged cross-validation, a block bootstrap, a parameter sweep, a look-ahead audit and out-of-sample transfer, then given one verdict with the reasons ranked." },
  ml01: { name: "Purged CV for a model", slug: "cpcv", icon: ScanSearch, question: "Is the backtest Sharpe real, or an artefact of leaky validation?",
    about: "Combinatorial purged cross-validation: date groups are tested in every combination, with training rows that overlap a test label purged and an embargo after each test block. The spread of path Sharpes is the honest answer." },
  ml02: { name: "Alpha model", slug: "alpha", icon: BrainCircuit, question: "Which names does the model rank highest, and why?",
    about: "LightGBM and Ridge blended by validation, predicting 21-day returns, scored on a held-out period against simple controls and explained with exact TreeSHAP values. Add your own features as formulas or a CSV." },
  ml03: { name: "Volatility & risk today", slug: "volatility", icon: Activity, question: "How much risk is ahead, and how large should the position be?",
    about: "HAR-RV, EWMA, GJR-GARCH and a regime-switching choice between them forecast volatility at 1, 5 and 21 days, scored by QLIKE with Diebold–Mariano tests, plus VaR, expected shortfall and a target-risk position size." },
  ml04: { name: "Improve my strategy", slug: "barriers", icon: Binary, question: "Which trades hit their target before their stop, and does filtering them help?",
    about: "Events are labelled by which barrier the high/low path touches first. Same-bar touches stay ambiguous rather than guessed. Meta-labels and conformal intervals are fitted out of fold." },
  ml05: { name: "Allocation", slug: "allocation", icon: GitBranch, question: "How should capital be spread, and what should I trade today?",
    about: "Ledoit–Wolf minimum variance by default, with risk parity, inverse variance and equal weight as controls, refit monthly on past data, net of costs. Paste your holdings for a trade list." },
  ml06: { name: "Market state", slug: "regimes", icon: Waves, question: "Which market state are we in, and how long do states last?",
    about: "A hidden Markov model fitted on the training window and filtered forward without smoothing, so every date's state uses only data up to that date." },
};

const PAGES: Page[] = [
  { id: "validate", label: "Validate", icon: ShieldCheck, question: "Does the backtest hold up once leakage, luck and trial count are removed?", features: ["mlvalidate", "ml01", "ml04"] },
  { id: "alpha", label: "Alpha", icon: BrainCircuit, question: "Which names rank highest, why, and does the model beat simple alternatives?", features: ["ml02"] },
  { id: "risk", label: "Volatility & risk", icon: Activity, question: "How much risk is ahead, and which market state are we in?", features: ["ml03", "ml06"] },
  { id: "allocate", label: "Allocation", icon: GitBranch, question: "How should capital be spread when estimates are noisy?", features: ["ml05"] },
  { id: "studio", label: "Strategy studio", slug: "studio", icon: Workflow, question: "Signal, filter, size, allocate, validate: one pipeline.", features: [] },
];

/** Output → view. Anything not listed is drawn from the contract's type and encoding. */
const VIEW: Record<string, Record<string, string>> = {
  validate: { autopsy: "valAutopsy", controls: "valControls", cpcv: "valCpcv", monte_carlo: "valMonteCarlo", transfer: "valTransfer", plateau: "valPlateau", stability: "valStability",
    deflated_sharpe: "valOverfit", leakage: "valLeakage", improve: "valImprove", receipt: "valReceipt" },
  "01": { purged_vs_naive_cv_comparison: "mlLeakGap", cpcv_sharpe_distribution: "mlSharpeSpread", backtest_paths_chart: "mlPathFan", per_fold_performance: "mlFoldMatrix", probability_of_backtest_overfitting: "mlKpi", deflated_sharpe_ratio: "mlKpi", cpcv_path_metrics: "dataTable" },
  "02": { controls: "alphaControls", decile_spreads: "alphaDeciles", net_of_cost_curve: "alphaNetCurve", what_changed: "alphaWhatChanged", feature_drift: "alphaDrift", feature_families: "alphaFamilies", ensemble: "alphaEnsemble", prediction_rank_table: "mlRankTable", shap_beeswarm: "mlBeeswarm", shap_waterfall_top_signal: "mlWaterfall", model_ic_leaderboard: "mlLeaderboard", rolling_monthly_ic_series: "mlIcBars", training_audit: "mlReceipt" },
  "03": { risk_today: "riskToday", var_es: "riskVarEs", position_sizing: "strategyCompare", regime_probability: "riskStress", vol_term_structure: "mlTermStructure", forecast_tournament: "mlTournament", forecast_error_distribution: "mlTournament", ensemble_vol_forecast_weights: "mlStacked" },
  "04": { event_outcome_timeline: "barrierTimeline", label_method_comparison: "barrierMethods", meta_label_probability_distribution: "metaProbability", triple_barrier_label_distribution: "mlLabelMix", barrier_hit_path_examples: "mlBarrierScatter", barrier_sensitivity_surface: "mlBarrierSurface", cqr_coverage_audit: "mlCoverage", barrier_parameters: "mlReceipt" },
  "05": { controls_summary: "strategyCompare", controls_equity: "equityCompare", weight_stability: "allocStability", trade_list: "allocTrades", rebalance_log: "allocRebalances", holding_risk: "dataTable", hrp_weight_vector: "mlWeights", cluster_dendrograms: "mlDendrogram", risk_contribution_decomposition: "mlRiskContrib", walk_forward_allocation: "mlEquity", black_litterman_posterior_return_vector: "mlBlShift", bl_vs_pure_hrp_weight_comparison: "mlBlShift" },
  "06": { regime_vs_constant_exposure: "strategyCompare", regime_probability_time_series: "mlRegimes", parallel_gmm_regime_probabilities: "mlRegimes", regime_transition_heatmap: "mlTransition", transition_matrix: "mlTransition", regime_conditional_asset_returns: "mlRegimeReturns", ensemble_vs_hmm_comparison: "mlKpi", correlation_network_density: "mlKpi", current_regime_probabilities: "mlReceipt", training_audit: "mlReceipt" },
};

type RawInput = InputSpec & { integer?: boolean };
type RawOutput = { id?: string; key?: string; title?: string; label?: string; path?: string; location?: string; type?: string; encoding?: Record<string, unknown>; status?: string; primary?: boolean; depends_on?: unknown };
type RawFeature = { id: string; title: string; status?: string; inputs: RawInput[]; outputs: RawOutput[]; known_limitations?: string[] };

/** Upload ids are chosen with the file picker, which uploads the CSV and fills in the id. */
const UPLOADS: Record<string, string> = { upload_id: "Your data", trials_upload_id: "Every trial you ran", benchmark_upload_id: "Benchmark returns" };
/** Raw JSON hand-offs are filled by "Validate this run" buttons, not typed. */
const HIDDEN_INPUTS = new Set(["source_result"]);
/** Hand-off ids arrive from another page's "Next" buttons; shown read-only-ish with a plain label. */
const HANDOFF_LABELS: Record<string, string> = { artifact_id: "From another page", alpha_artifact_id: "Alpha views from the Alpha page", regime_artifact_id: "Regimes from the Market state page" };
/** Holdings are typed as "AAPL 25%, MSFT 0.2" or one per line, and sent as {ticker: value}. */
const HOLDINGS = "holdings";

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
  // Designed views whose output the manifest does not list (newer tables) still get their view.
  for (const [key, render] of Object.entries(VIEW[f.id] ?? {})) {
    if (!seen.has(key)) outputs.push({ key, title: key, source: "tables", render });
  }
  for (const i of f.inputs) if (i.type === "ticker_list" || i.type === "text_list") LIST_KEYS.add(i.key);
  return {
    id, name: f.title, description: CATALOG[id]?.about ?? "",
    inputs: f.inputs.filter((i) => !HIDDEN_INPUTS.has(i.key)).map((i) => ({
      ...i, group: i.group || "Settings", default: Array.isArray(i.default) && i.type !== "multiselect" ? i.default.join(", ") : i.default,
      ...(UPLOADS[i.key] ? { type: "file" as const, label: UPLOADS[i.key] } : {}),
      ...(HANDOFF_LABELS[i.key] ? { label: HANDOFF_LABELS[i.key], help: `${i.help ?? ""} Filled in by the hand-off buttons; leave empty otherwise.`.trim() } : {}),
      ...(i.key === HOLDINGS ? { type: "text" as const, label: "Your holdings", default: "", help: "One per line or comma-separated: ticker and weight (AAPL 25%) or shares (AAPL 120) per the unit below. Leave empty for target weights only." } : {}),
    })),
    outputs,
  };
}

/** Text fields that hold lists ("AAPL, MSFT" or "1, 5, 21") go to the API as arrays. */
function payloadFor(payload: Record<string, unknown>) {
  const outp: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (k === HOLDINGS && typeof v === "string") {
      const pairs = v.split(/[\n,;]+/).map((x) => x.trim().split(/[\s:=]+/)).filter((x) => x.length >= 2 && x[0]);
      if (pairs.length) outp[k] = Object.fromEntries(pairs.map(([t, q]) => [t.toUpperCase(), q.endsWith("%") ? Number(q.slice(0, -1)) / 100 : Number(q)]));
    } else if (LIST_KEYS.has(k) && typeof v === "string") {
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
const ALLOC_NAMES: Record<string, string> = { equal_weight: "equal weight", inverse_variance: "inverse variance", standard_hrp: "risk parity (HRP)", nco: "nested clustered optimisation" };
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
      return v?.label ? { headline: v.headline || v.label, tone: VTONE[v.label] ?? null } : { headline: null, tone: null };
    },
  },
  ml01: {
    sections: [
      sec("result", "Result", [card("cpcv_sharpe_distribution", 12, { title: "Sharpe across every CPCV path" }), card("purged_vs_naive_cv_comparison", 12, { title: "What a naive split would have told you" }), card("backtest_paths_chart", 12, { title: "Every out-of-sample path" })]),
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
      sec("ranking", "Ranking", [card("prediction_rank_table", 7, { title: "Today's ranking · click a name" }), card("ticker_contributions", 5, { view: "mlWaterfall", title: "Why this name ranks here" })]),
      sec("changed", "What changed", [card("what_changed", 12, { title: "Moves since the last rebalance" })], "Names that entered or left the top of the ranking, with the features that moved them."),
      sec("controls", "Against controls", [card("controls", 12, { title: "The model against simple alternatives, held-out" }), card("decile_spreads", 6, { title: "Returns by prediction bucket" }), card("net_of_cost_curve", 6, { title: "Long-short after costs" })],
        "A model earns its complexity only if it beats Ridge, a 3-factor OLS and the IC-weighted composite out of sample."),
      sec("explain", "Explain", [card("shap_beeswarm", 7, { title: "What drives predictions" }), card("feature_families", 5, { title: "Contribution by feature family" })], "Exact TreeSHAP values on the latest predictions: direction, size and spread of each feature's effect."),
      sec("quality", "Model quality", [card("rolling_monthly_ic_series", 6, { title: "IC by month, held-out period" }), card("ensemble", 6, { title: "How the blend was chosen" }), card("feature_drift", 6, { title: "Feature drift and retrain check" }), card("training_audit", 6, { view: "mlProvenance", title: "Trained and tested on" }), card("model_ic_leaderboard", 12, { title: "Models by test IC" })]),
      sec("next", "Next", [card("training_audit", 12, { view: "mlNext", title: "Take this ranking further" })]),
      data(["current_predictions", "model_performance", "decile_summary", "heldout_predictions", "shap_feature_importance", "shap_waterfall_top_signal", "tuning_trials"]),
    ],
    verdict: (r) => {
      const c = out(r, "controls");
      const m = c.find((x) => x.primary), alts = c.filter((x) => !x.primary && isNum(x.test_ic)).sort((a, b) => (b.test_ic as number) - (a.test_ic as number));
      const best = alts[0], ic = m?.test_ic;
      if (!m || !isNum(ic)) return { headline: null, tone: null };
      const beats = best ? ic > (best.test_ic as number) : true;
      const name = (k: unknown) => ({ ensemble: "The ensemble", lightgbm: "LightGBM", ridge: "Ridge", ols3: "3-factor OLS", ic_composite: "the IC-weighted composite" } as Record<string, string>)[String(k)] ?? String(k);
      return {
        headline: `${name(m.model)} scores a held-out IC of ${fmt(ic, 3)}${best ? `, ${beats ? "beating" : "behind"} ${name(best.model)} (${fmt(best.test_ic, 3)})` : ""}; net Sharpe ${fmt(m.net_sharpe)}.${beats ? "" : " A simpler signal does as well: prefer it, or validate before trusting the model."}`,
        tone: ic <= 0 ? "down" : beats && ic > 0.03 ? "up" : "warn",
      };
    },
  },
  ml03: {
    sections: [
      sec("today", "Risk today", [card("risk_today", 12, { title: "Risk today" })]),
      sec("forecast", "Forecast", [card("forecast_rows", 12, { view: "mlVolPanel", title: "Forecast against realised volatility" }), card("vol_term_structure", 6, { title: "Term structure today" }), card("regime_probability", 6, { title: "Stress probability (filtered, no look-ahead)" })]),
      sec("tournament", "Model tournament", [card("forecast_tournament", 7, { title: "Loss by model and horizon" }), card("forecast_rows", 5, { view: "mlVolScatter", title: "Forecast vs realised" })],
        "QLIKE loss on the held-out period; Diebold–Mariano tests say whether the regime switch is significantly better than each single model."),
      sec("tail", "Tail risk and sizing", [card("var_es", 7, { title: "VaR and expected shortfall, with calibration" }), card("position_sizing", 5, { title: "Volatility-targeted vs unmanaged" })]),
      sec("about", "Provenance", [card("forecast_tournament", 12, { view: "mlProvenance", title: "Trained and tested on" })]),
      data(["forecast_error_distribution", "model_confidence_intervals", "realized_vol_estimator_comparison", "var_es_forecast", "watchlist_skipped"]),
    ],
    verdict: (r) => {
      const t = out(r, "risk_today")[0];
      if (!t) return { headline: null, tone: null };
      const sized = out(r, "position_sizing"), u = sized.find((x) => x.strategy === "unmanaged"), v = sized.find((x) => x.strategy === "vol_targeted");
      const helps = u && v && isNum(u.sharpe) && isNum(v.sharpe) ? v.sharpe > u.sharpe : null;
      return {
        headline: `${String(t.asset)} is in a ${String(t.regime)} regime: next-month volatility ${fmt((t.vol_21d as number) * 100, 0)}%, one-day 99% VaR ${fmt((t.var_99 as number) * 100, 1)}%. Target-risk size ${fmt(t.size_multiple)}×${helps === null ? "." : helps ? ", and vol-targeting improved Sharpe here." : ", but vol-targeting did not beat unmanaged here."}`,
        tone: String(t.regime) === "stress" ? "down" : "up",
      };
    },
  },
  ml04: {
    sections: [
      sec("labels", "Labels", [card("barrier_hit_path_examples", 8, { title: "Which barrier was hit, and when" }), card("triple_barrier_label_distribution", 4, { title: "Label mix" }), card("event_outcome_timeline", 12, { title: "Events over time" })]),
      sec("sensitivity", "Sensitivity", [card("barrier_sensitivity_surface", 7, { title: "Label mix by barrier width" }), card("label_method_comparison", 5, { title: "Fixed vs volatility-scaled barriers" })]),
      sec("meta", "Meta-labels", [card("meta_label_probability_distribution", 6), card("cqr_coverage_audit", 6, { title: "Conformal interval coverage" })]),
      data(["barrier_parameters", "label_audit", "barrier_sensitivity", "cqr_interval_width_distribution"]),
    ],
    verdict: (r) => {
      const mix = out(r, "triple_barrier_label_distribution");
      const tot = mix.reduce((t, x) => t + (isNum(x.count) ? x.count : 0), 0);
      const share = (l: number) => (tot ? (mix.find((x) => Number(x.label) === l)?.count as number ?? 0) / tot : 0);
      const p = out(r, "barrier_parameters")[0];
      const pt = isNum(p?.profit_taking) ? p.profit_taking : null, sl = isNum(p?.stop_loss) ? p.stop_loss : null;
      if (!tot || pt === null || sl === null) return { headline: null, tone: null };
      const edge = share(1) * pt - share(-1) * sl;
      const breakeven = sl / (pt + sl);
      return {
        headline: `Profit-taking hits first in ${fmt(share(1) * 100, 0)}% of events, the stop in ${fmt(share(-1) * 100, 0)}%. At ${fmt(pt * 100, 1)}% / ${fmt(sl * 100, 1)}% barriers that is about ${edge >= 0 ? "+" : ""}${fmt(edge * 100, 2)}% per event before costs; break-even needs a ${fmt(breakeven * 100, 0)}% hit rate.`,
        tone: edge > 0.002 ? "up" : edge > 0 ? "warn" : "down",
      };
    },
  },
  ml05: {
    sections: [
      sec("trade", "Your trades", [card("trade_list", 12, { title: "Rebalance your holdings" }), card("holding_risk", 12, { title: "Risk contribution per holding" })], "Shown when you paste holdings in the Study panel."),
      sec("weights", "Weights", [card(["weight_stability", "risk_contribution_decomposition"], 12, { title: "Target weights, their stability and where the risk sits" })]),
      sec("controls", "Against controls", [card("controls_summary", 12, { title: "Walk-forward, net of costs, against the controls" }), card("controls_equity", 8, { title: "Growth of $1 by allocation" }), card("rebalance_log", 4, { title: "Trade only when it pays" })],
        "Shrinkage minimum variance has to beat equal weight, inverse variance and risk parity after costs to earn its place."),
      sec("structure", "Cluster structure", [card("cluster_dendrograms", 12, { title: "Clustering tree and reordered correlations" })]),
      sec("bl", "With alpha views", [card("black_litterman_posterior_return_vector", 6, { title: "Prior → posterior returns" }), card("alpha_views", 6, { view: "mlBlWeights", title: "How the views tilt the weights" })]),
      sec("about", "Provenance", [card("allocation_training_audit", 6, { view: "mlProvenance", title: "Trained and tested on" }), card("allocation_training_audit", 6, { view: "mlNext", title: "Next" })]),
      data(["hrp_weights", "hrp_weight_vector", "black_litterman", "bl_vs_pure_hrp_weight_comparison", "alpha_views", "rebalance_summary", "walk_forward_allocation", "quasi_diagonalized_covariance_heatmap", "allocation_training_audit"]),
    ],
    verdict: (r) => {
      const c = out(r, "controls_summary");
      const m = c.find((x) => x.kind === "chosen") ?? c[0];
      const best = c.filter((x) => x !== m && !/chosen/.test(String(x.kind)) && isNum(x.sharpe)).sort((a, b) => (b.sharpe as number) - (a.sharpe as number))[0];
      if (!m || !isNum(m.sharpe)) return { headline: null, tone: null };
      const beats = best ? m.sharpe > (best.sharpe as number) : true;
      const trades = out(r, "rebalance_summary")[0];
      const lazy = c.find((x) => x.strategy === "turnover_aware");
      const lazyNote = lazy && isNum(lazy.sharpe) && lazy.sharpe > Math.max(m.sharpe as number, isNum(best?.sharpe) ? (best.sharpe as number) : -Infinity)
        ? ` Trading only when the gain beats the cost lifts it to ${fmt(lazy.sharpe)}, ahead of every control.` : "";
      return {
        headline: `${String(m.strategy) === "min_variance" ? "Shrinkage minimum variance" : String(m.strategy)} earns a net Sharpe of ${fmt(m.sharpe)} at ${fmt((m.annual_volatility as number) * 100, 1)}% volatility${best ? `, ${beats ? "ahead of" : "behind"} ${ALLOC_NAMES[String(best.strategy)] ?? String(best.strategy)} (${fmt(best.sharpe)})` : ""}.${lazyNote}${trades ? ` Rebalancing your holdings ${trades.trade_recommended ? "is worth its cost" : "is not worth its cost today"}.` : ""}`,
        tone: beats || lazyNote ? "up" : "warn",
      };
    },
  },
  ml06: {
    sections: [
      sec("state", "State", [card("regime_probability_time_series", 12, { title: "Regime probabilities (filtered, no look-ahead)" }), card("regime_transition_heatmap", 6, { title: "Transitions and expected duration" }), card("regime_conditional_asset_returns", 6, { title: "Mean daily return by regime" })]),
      sec("use", "Does it help?", [card("regime_vs_constant_exposure", 12, { title: "Regime-filtered exposure against the same average exposure held constant" })],
        "A regime model earns its place only if cutting exposure in stress beats holding the same average exposure all the time."),
      sec("checks", "Checks", [card("pc1_variance_monitor", 8, { title: "First principal component share" }), card("ensemble_vs_hmm_comparison", 4, { title: "Classifier agreement (out of sample)" }), card("parallel_gmm_regime_probabilities", 8, { title: "Gaussian mixture, for comparison" }), card("correlation_network_density", 4)]),
      sec("about", "Provenance", [card("training_audit", 6, { view: "mlProvenance", title: "Trained and tested on" }), card("training_audit", 6, { view: "mlNext", title: "Next" })]),
      data(["current_regime_probabilities", "transition_matrix", "training_audit"]),
    ],
    verdict: (r) => {
      const c = out(r, "current_regime_probabilities")[0];
      const cmp = out(r, "regime_vs_constant_exposure"), f = cmp.find((x) => x.strategy === "regime_filtered"), k = cmp.find((x) => x.strategy === "constant_exposure");
      if (!c) return { headline: null, tone: null };
      const sp = c.stress_probability;
      const helps = f && k && isNum(f.sharpe) && isNum(k.sharpe) ? f.sharpe > k.sharpe : null;
      return {
        headline: `Stress probability ${isNum(sp) ? `${fmt(sp * 100, 0)}%` : "–"} as of ${String(c.date)}.${helps === null ? "" : helps ? ` Cutting exposure in stress beat constant exposure (Sharpe ${fmt(f!.sharpe)} vs ${fmt(k!.sharpe)}).` : ` Cutting exposure in stress did not beat constant exposure (Sharpe ${fmt(f!.sharpe)} vs ${fmt(k!.sharpe)}).`}`,
        tone: isNum(sp) && sp > 0.5 ? "down" : helps === false ? "warn" : "up",
      };
    },
  },
};

const V = group(() => import("./views") as Promise<Record<string, unknown>>);
const VV = group(() => import("./validateViews") as Promise<Record<string, unknown>>);
const PV = group(() => import("./pageViews") as Promise<Record<string, unknown>>);
registerViews({
  mlProvenance: PV.MlProvenance, mlNext: PV.MlNext, alphaControls: PV.AlphaControls, alphaDeciles: PV.AlphaDeciles, alphaNetCurve: PV.AlphaNetCurve, alphaWhatChanged: PV.AlphaWhatChanged,
  alphaFamilies: PV.AlphaFamilies, alphaDrift: PV.AlphaDrift, alphaEnsemble: PV.AlphaEnsemble, riskToday: PV.RiskToday, riskVarEs: PV.RiskVarEs, strategyCompare: PV.StrategyCompare, riskStress: PV.RiskStress,
  allocStability: PV.AllocStability, allocTrades: PV.AllocTrades, allocRebalances: PV.AllocRebalances, alphaSectors: PV.AlphaSectors, allocSectors: PV.AllocSectors, shapImportance: PV.ShapImportance, regimeSpells: PV.RegimeSpells, barrierTimeline: PV.BarrierTimeline, barrierMethods: PV.BarrierMethods, metaProbability: PV.MetaProbability, equityCompare: PV.EquityCompare,
}, ["barrierTimeline", "metaProbability", "equityCompare", "alphaControls", "alphaDeciles", "alphaNetCurve", "alphaEnsemble", "strategyCompare", "riskStress"]);
registerViews({
  valVerdict: VV.ValVerdict, valAutopsy: VV.ValAutopsy, valCostCurve: VV.ValCostCurve, valControls: VV.ValControls, valShuffle: VV.ValShuffle, valCpcv: VV.ValCpcv, valMonteCarlo: VV.ValMonteCarlo,
  valTransfer: VV.ValTransfer, valPlateau: VV.ValPlateau, valStability: VV.ValStability, valOverfit: VV.ValOverfit, valLeakage: VV.ValLeakage, valImprove: VV.ValImprove, valReceipt: VV.ValReceipt,
}, ["valCostCurve", "valControls", "valTransfer", "valPlateau", "valStability"]);
registerViews({
  mlAuto: V.MlAuto, mlKpi: V.MlKpi, mlReceipt: V.MlReceipt, mlEquity: V.MlEquity, mlSharpeSpread: V.MlSharpeSpread, mlPathFan: V.MlPathFan, mlFoldMatrix: V.MlFoldMatrix,
  mlRankTable: V.MlRankTable, mlBeeswarm: V.MlBeeswarm, mlWaterfall: V.MlWaterfall, mlIcBars: V.MlIcBars, mlLeaderboard: V.MlLeaderboard, mlVolPanel: V.MlVolPanel,
  mlVolScatter: V.MlVolScatter, mlTermStructure: V.MlTermStructure, mlTournament: V.MlTournament, mlBarrierScatter: V.MlBarrierScatter, mlBarrierSurface: V.MlBarrierSurface, mlLabelMix: V.MlLabelMix,
  mlCoverage: V.MlCoverage, mlWeights: V.MlWeights, mlRiskContrib: V.MlRiskContrib, mlDendrogram: V.MlDendrogram, mlBlShift: V.MlBlShift, mlLeakGap: V.MlLeakGap, mlBlWeights: V.MlBlWeights, mlRegimes: V.MlRegimes,
  mlTransition: V.MlTransition, mlRegimeReturns: V.MlRegimeReturns, mlStacked: V.MlStacked,
 
 
}, ["mlAuto", "mlEquity", "mlPathFan", "mlBeeswarm", "mlWaterfall", "mlIcBars", "mlLeaderboard", "mlVolPanel", "mlVolScatter", "mlTermStructure", "mlTournament", "mlBarrierScatter",
  "mlBarrierSurface", "mlLabelMix", "mlCoverage", "mlWeights", "mlRiskContrib", "mlDendrogram", "mlBlShift", "mlRegimes", "mlTransition", "mlRegimeReturns", "mlStacked",
  "mlSharpeSpread"]);

registerAlternates({
  mlRankTable: [{ label: "By sector", view: "alphaSectors" }],
  allocStability: [{ label: "By sector", view: "allocSectors" }],
  mlBeeswarm: [{ label: "Importance ranking", view: "shapImportance" }, { label: "By feature family", view: "alphaFamilies" }],
  mlVolPanel: [{ label: "Calibration (forecast vs realised)", view: "mlVolScatter" }],
  mlVolScatter: [{ label: "Through time", view: "mlVolPanel" }],
  mlRegimes: [{ label: "Spell history", view: "regimeSpells" }],
});

const StudioPage = dynamic(() => import("./StudioPage").then((m) => m.StudioPage));
const VerifiedPage = dynamic(() => import("./VerifiedPage").then((m) => m.VerifiedPage));

export const ML_LAB: LabConfig = {
  id: "ml",
  takeaway,
  title: "Machine learning",
  root: "/ml",
  base: `${API_BASE_URL}/ml/v2`,
  catalog: CATALOG,
  pages: PAGES,
  layouts: LAYOUTS,
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => ID(f.id) in CATALOG).map(toSpec),
  submit: (featureId, payload) => ({ path: `/features/${RAW(featureId)}/jobs`, body: payloadFor(payload) }),
  signal: false,
  specials: { studio: StudioPage, verified: VerifiedPage },
  emptyHint: (id) => (id === "mlvalidate"
    ? "Upload your returns, predictions, feature panel or every trial you ran in the Study panel, or send a run here from Alpha or Allocation. Then press Validate."
    : "Defaults run on 35 US large caps in a few seconds. Change the universe or settings in the Study panel, or just run it."),
  runLabel: (id) => (id === "mlvalidate" ? "Validate" : id === "ml05" ? "Allocate" : id === "ml03" || id === "ml06" ? "Forecast" : "Train and test"),
  defaultUniverse: "35 US large caps",
  overview: {
    actions: [
      { id: "mlvalidate", title: "Validate my strategy", body: "Upload returns, predictions or every trial you ran. Get HELD UP, MIXED or FAILED, and the exact reason.", cta: "Upload and validate" },
      { id: "ml02", title: "Today's ranking", body: "35 large caps ranked by expected 21-day return, each explained feature by feature, beside the simple signal it has to beat.", cta: "Rank the universe" },
      { id: "ml03", title: "Risk today", body: "Next-day to next-month volatility with calibrated ranges, VaR, the market state and a target-risk position size.", cta: "Read today's risk" },
    ],
    words: { tests: "Pages", pass: "Held up", mixed: "Mixed", fail: "Failed" },
    intro: "Four pages, one rule: nothing ships unless it holds up out of sample. Every split is chronological and purged, every result is measured against simple controls, and anything the data cannot support is marked unavailable rather than approximated.",
    stages: [
      { id: "validate", label: "Validate", intro: "Kill bad ideas cheaply: purged cross-validation, overfitting tests and a barrier-based trade filter.", ids: ["mlvalidate", "ml01", "ml04"] },
      { id: "alpha", label: "Alpha", intro: "A cross-sectional ranking explained name by name, measured against Ridge, a 3-factor OLS and the IC-weighted composite.", ids: ["ml02"] },
      { id: "risk", label: "Volatility & risk", intro: "Forecast volatility with a scored model tournament, and read the market state without look-ahead.", ids: ["ml03", "ml06"] },
      { id: "allocate", label: "Allocation", intro: "Shrinkage-based weights with risk-parity and equal-weight controls, tested walk-forward net of costs.", ids: ["ml05"] },
    ],
  },
};

