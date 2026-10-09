import { isNum, out } from "@/modules/research/format";
import type { FeatureResult } from "@/modules/research/types";

/**
 * Exhibit titles that state the finding. Each generator reads one exhibit's data and returns a sentence,
 * or null when the data cannot support one (the card then keeps its descriptive title).
 * Keyed by "featureId:outputKey:view" (view empty for the designed default).
 */
type Row = Record<string, unknown>;
type Gen = (r: FeatureResult) => string | null;

const n = (v: unknown) => (isNum(v) ? v : null);
const f2 = (v: number) => v.toFixed(2);
const f3 = (v: number) => v.toFixed(3);
const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
const sec = (r: FeatureResult, k: string) => ((r as unknown as { sections?: Record<string, Row> }).sections?.[k] ?? {}) as Row;

const MODEL: Record<string, string> = {
  ensemble: "The ensemble", lightgbm: "LightGBM", ridge: "Ridge", ols3: "3-factor OLS", ic_composite: "the IC-weighted composite",
  min_variance: "Minimum variance", turnover_aware: "the no-trade-rule version", standard_hrp: "risk parity (HRP)", inverse_variance: "inverse variance", equal_weight: "equal weight",
  regime_filtered: "Regime-filtered exposure", constant_exposure: "constant exposure", unmanaged: "unmanaged", vol_targeted: "Vol-targeting",
  naive_cpcv: "a naive split", purged_cpcv: "purged CV",
};
const nm = (k: unknown) => MODEL[String(k)] ?? String(k).replace(/_/g, " ");
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Best row by a numeric column. */
const top = (rows: Row[], col: string) => rows.filter((x) => isNum(x[col])).sort((a, b) => (b[col] as number) - (a[col] as number))[0];

const GEN: Record<string, Gen> = {
  /* ---------------- Alpha */
  "ml02:controls:": (r) => {
    const rows = out(r, "controls");
    const m = rows.find((x) => x.primary), best = top(rows.filter((x) => !x.primary), "test_ic");
    const ic = n(m?.test_ic), t = n(m?.ic_tstat);
    if (!m || ic === null) return null;
    const vs = best && isNum(best.test_ic) ? `${ic > best.test_ic ? "beats" : "trails"} ${nm(best.model)} (${f3(ic)} vs ${f3(best.test_ic)})` : `scores ${f3(ic)}`;
    const sig = t !== null && Math.abs(t) < 1.96 ? "; its interval includes zero" : "";
    return `${cap(nm(m.model))} ${vs} on held-out IC${sig}`;
  },
  "ml02:controls:alphaRadar": (r) => {
    const rows = out(r, "controls"), m = rows.find((x) => x.primary);
    if (!m) return null;
    const cols = ["test_ic", "ic_tstat", "ew_spread", "vw_spread", "net_sharpe", "capacity_usd"];
    const wins = cols.filter((c) => isNum(m[c]) && rows.every((x) => x === m || !isNum(x[c]) || (m[c] as number) >= (x[c] as number))).length;
    return `${cap(nm(m.model))} leads on ${wins} of ${cols.length} return and capacity metrics`;
  },
  "ml05:controls_summary:strategyRadar": (r) => {
    const rows = out(r, "controls_summary"), ch = rows.find((x) => x.kind === "chosen");
    if (!ch) return null;
    const best = top(rows.filter((x) => x !== ch), "sharpe");
    const lessRisk = rows.filter((x) => x !== ch && isNum(x.annual_volatility) && isNum(ch.annual_volatility) && (ch.annual_volatility as number) < (x.annual_volatility as number)).length;
    return `${cap(nm(ch.strategy))} carries less risk than ${lessRisk} of ${rows.length - 1} alternatives${best && isNum(best.sharpe) && isNum(ch.sharpe) && best.sharpe > ch.sharpe ? `, but ${nm(best.strategy)} earns more per unit of it` : ""}`;
  },
  "ml02:decile_spreads:": (r) => {
    const s = out(r, "decile_summary").find((x) => x.model === "ensemble" && x.weighting === "equal") ?? out(r, "decile_summary")[0];
    const sp = n(s?.spread), t = n(s?.t_stat);
    if (sp === null) return null;
    return `Top bucket ${sp >= 0 ? "beats" : "lags"} bottom by ${pct(Math.abs(sp), 2)} per rebalance${t !== null ? ` (t = ${f2(t)})` : ""}`;
  },
  "ml02:net_of_cost_curve:": (r) => {
    const rows = out(r, "net_of_cost_curve");
    const last = new Map<string, number>();
    for (const x of rows) if (isNum(x.equity)) last.set(String(x.model), x.equity);
    const ens = last.get("ensemble") ?? [...last.values()][0];
    if (ens === undefined) return null;
    const others = [...last.entries()].filter(([k]) => k !== "ensemble").sort((a, b) => b[1] - a[1]);
    return `After costs, $1 in the long-short became $${f2(ens)}${others[0] ? `; best alternative ${nm(others[0][0])} reached $${f2(others[0][1])}` : ""}`;
  },
  "ml02:rolling_monthly_ic_series:": (r) => {
    const v = out(r, "rolling_monthly_ic_series").map((x) => x.rolling_ic).filter(isNum);
    if (!v.length) return null;
    const pos = v.filter((x) => x > 0).length;
    return `IC was positive in ${pos} of ${v.length} held-out months (mean ${f3(v.reduce((a, b) => a + b, 0) / v.length)})`;
  },
  "ml02:feature_families:": (r) => {
    const rows = out(r, "feature_families").filter((x) => isNum(x.mean_abs_shap));
    const tot = rows.reduce((a, x) => a + (x.mean_abs_shap as number), 0);
    const b = top(rows, "mean_abs_shap");
    return b && tot > 0 ? `${cap(String(b.family).replace(/_/g, " "))} features carry ${pct((b.mean_abs_shap as number) / tot, 0)} of the model's attribution` : null;
  },
  "ml02:shap_beeswarm:": (r) => {
    const b = top(out(r, "shap_feature_importance"), "mean_abs_shap");
    return b ? `${cap(String(b.feature).replace(/_/g, " "))} moves predictions the most` : null;
  },
  "ml02:ensemble:": (r) => {
    const c = out(r, "ensemble").find((x) => x.chosen);
    return c && isNum(c.lightgbm) ? `Validation chose ${pct(c.lightgbm, 0)} LightGBM, ${pct(1 - c.lightgbm, 0)} Ridge${isNum(c.validation_ic) ? ` (validation IC ${f3(c.validation_ic)})` : ""}` : null;
  },
  "ml02:what_changed:": (r) => {
    const rows = out(r, "what_changed");
    const up = rows.filter((x) => isNum(x.rank_change) && x.rank_change > 0).length;
    return rows.length ? `${rows.length} names moved since the last rebalance; ${up} rose` : null;
  },

  /* ---------------- Volatility & risk */
  "ml03:var_es:": (r) => {
    const v = out(r, "var_es").find((x) => x.horizon === 1 && x.level === 0.99) ?? out(r, "var_es")[0];
    if (!v || !isNum(v.var)) return null;
    const br = n(v.oos_breach_rate), p = n(v.kupiec_p_value);
    return `One-day ${pct(v.level as number, 0)} VaR is ${pct(v.var, 1)}${br !== null ? `; breached ${pct(br, 1)} of held-out days vs ${pct(1 - (v.level as number), 0)} expected${p !== null ? (p < 0.05 ? ", miscalibrated" : ", calibration passes") : ""}` : ""}`;
  },
  "ml03:position_sizing:": (r) => {
    const rows = out(r, "position_sizing");
    const u = rows.find((x) => x.strategy === "unmanaged"), v = rows.find((x) => x.strategy === "vol_targeted");
    if (!isNum(u?.sharpe) || !isNum(v?.sharpe)) return null;
    const dd = isNum(u?.max_drawdown) && isNum(v?.max_drawdown) ? `, drawdown ${pct(v.max_drawdown as number, 0)} vs ${pct(u.max_drawdown as number, 0)}` : "";
    return `Vol-targeting ${v.sharpe > u.sharpe ? "raised" : "lowered"} Sharpe to ${f2(v.sharpe)} from ${f2(u.sharpe)}${dd}`;
  },
  "ml03:forecast_tournament:": (r) => {
    const rows = out(r, "forecast_tournament").filter((x) => x.horizon === 21 && isNum(x.qlike));
    const best = rows.sort((a, b) => (a.qlike as number) - (b.qlike as number))[0];
    return best ? `${cap(nm(best.model))} has the lowest 21-day forecast loss` : null;
  },

  /* ---------------- Market state */
  "ml06:regime_vs_constant_exposure:": (r) => {
    const rows = out(r, "regime_vs_constant_exposure");
    const f = rows.find((x) => x.strategy === "regime_filtered"), c = rows.find((x) => x.strategy === "constant_exposure");
    if (!isNum(f?.sharpe) || !isNum(c?.sharpe)) return null;
    return `At the same average exposure, regime switching ${f.sharpe > c.sharpe ? "raised" : "lowered"} Sharpe to ${f2(f.sharpe)} from ${f2(c.sharpe)}`;
  },

  "ml06:regime_probability_time_series:": (r) => {
    const rows = out(r, "regime_probability_time_series");
    const keys = Object.keys(rows[0] ?? {}).filter((k) => /^state_\d+$/.test(k));
    if (!rows.length || !keys.length) return null;
    const dom = (x: Row) => keys.reduce((a, k) => ((n(x[k]) ?? 0) > (n(x[a]) ?? 0) ? k : a), keys[0]);
    const now = dom(rows[rows.length - 1]);
    let run = 1;
    for (let i = rows.length - 2; i >= 0 && dom(rows[i]) === now; i--) run++;
    return `${stateName(r, now)} for the last ${run} sessions`;
  },
  "ml06:regime_transition_heatmap:": (r) => {
    const m = out(r, "regime_transition_heatmap").filter((x) => x.row === x.col && isNum(x.value) && (x.value as number) < 1);
    const longest = m.sort((a, b) => (b.value as number) - (a.value as number))[0];
    return longest ? `${stateName(r, `state_${String(longest.row).replace(/\D/g, "")}`)} is the most persistent state: about ${Math.round(1 / (1 - (longest.value as number)))} sessions per visit` : null;
  },
  "ml06:regime_conditional_asset_returns:": (r) => {
    const rows = out(r, "regime_conditional_asset_returns").filter((x) => isNum(x.mean_log_return));
    const stress = rows.filter((x) => /stress/i.test(stateName(r, `state_${String(x.regime).replace(/\D/g, "")}`)));
    const worst = (stress.length ? stress : rows).sort((a, b) => (a.mean_log_return as number) - (b.mean_log_return as number))[0];
    return worst ? `${String(worst.asset)} is hurt most${stress.length ? " in stress" : ""}: ${pct(worst.mean_log_return as number, 2)} a day` : null;
  },

  /* ---------------- Improve */
  "ml04:label_method_comparison:": (r) => {
    const rows = out(r, "label_method_comparison");
    const f = rows.find((x) => x.method === "fixed"), v = rows.find((x) => x.method === "vol_scaled");
    return isNum(f?.negative_rate) && isNum(v?.negative_rate) ? `Volatility-scaled barriers stop out ${pct(v.negative_rate, 0)} of trades vs ${pct(f.negative_rate, 0)} with fixed barriers` : null;
  },
  "ml04:cqr_coverage_audit:": (r) => {
    const rows = out(r, "cqr_coverage_audit").filter((x) => isNum(x.empirical_coverage));
    if (!rows.length) return null;
    const avg = rows.reduce((a, x) => a + (x.empirical_coverage as number), 0) / rows.length, tgt = n(rows[0].target_coverage);
    return `Intervals covered ${pct(avg, 0)} of outcomes${tgt !== null ? ` against a ${pct(tgt, 0)} target${avg < tgt - 0.03 ? ": too narrow" : avg > tgt + 0.05 ? ": conservative" : ""}` : ""}`;
  },

  /* ---------------- Allocation */
  "ml05:controls_equity:": (r) => {
    const last = new Map<string, number>();
    for (const x of out(r, "controls_equity")) if (isNum(x.equity)) last.set(String(x.strategy), x.equity);
    const ranked = [...last.entries()].sort((a, b) => b[1] - a[1]);
    return ranked.length ? `${cap(nm(ranked[0][0]))} grew $1 the most, to $${f2(ranked[0][1])}` : null;
  },
  "ml05:trade_list:": (r) => {
    const rows = out(r, "trade_list").filter((x) => isNum(x.trade_weight) && Math.abs(x.trade_weight as number) > 1e-4);
    const s = out(r, "rebalance_summary")[0];
    return rows.length ? `${rows.length} trades${s && isNum(s.cost_bps) ? ` costing ${(s.cost_bps as number).toFixed(1)} bps` : ""}${s ? (s.trade_recommended ? "; worth making" : "; the expected gain does not cover the cost") : ""}` : "No trades needed";
  },
  "ml05:weight_stability:": (r) => {
    const rows = out(r, "weight_stability").filter((x) => isNum(x.p05) && isNum(x.p95));
    const wide = rows.sort((a, b) => ((b.p95 as number) - (b.p05 as number)) - ((a.p95 as number) - (a.p05 as number)))[0];
    return wide ? `${String(wide.asset)}'s weight is the least certain: ${pct(wide.p05 as number, 0)} to ${pct(wide.p95 as number, 0)} across resamples` : null;
  },
  "ml05:controls_summary:": (r) => {
    const rows = out(r, "controls_summary");
    const ch = rows.find((x) => x.kind === "chosen"), best = top(rows.filter((x) => x.kind === "control"), "sharpe");
    if (!isNum(ch?.sharpe)) return null;
    return best && isNum(best.sharpe) ? `${cap(nm(ch.strategy))} ${ch.sharpe >= best.sharpe ? "beats" : "trails"} ${nm(best.strategy)} on Sharpe (${f2(ch.sharpe)} vs ${f2(best.sharpe)})` : `${cap(nm(ch.strategy))} earned Sharpe ${f2(ch.sharpe)}`;
  },
  "ml05:risk_contribution_decomposition:": (r) => {
    const rows = out(r, "risk_contribution_decomposition");
    const b = top(rows, "risk_contribution");
    return b && rows.length ? `${String(b.asset)} carries ${pct(b.risk_contribution as number, 0)} of portfolio risk (equal share ${pct(1 / rows.length, 0)})` : null;
  },

  /* ---------------- Purged CV */
  "ml01:purged_vs_naive_cv_comparison:": (r) => {
    const rows = out(r, "purged_vs_naive_cv_comparison");
    const nv = n(rows.find((x) => x.method === "naive_cpcv")?.sharpe), pg = n(rows.find((x) => x.method === "purged_cpcv")?.sharpe);
    return nv !== null && pg !== null ? `Purging moves Sharpe from ${f2(nv)} to ${f2(pg)}${nv > pg ? ": the naive split overstated it" : ""}` : null;
  },
  "ml01:cpcv_sharpe_distribution:": (r) => {
    const s = out(r, "cpcv_sharpe_distribution").map((x) => x.sharpe).filter(isNum).sort((a, b) => a - b);
    return s.length ? `${s.filter((x) => x > 0).length} of ${s.length} purged paths have a positive Sharpe` : null;
  },

  /* ---------------- Validate */
  "mlvalidate:controls:": (r) => {
    const c = sec(r, "controls");
    const s = n(c.strategy_sharpe), b = n(c.best_control_sharpe);
    return s !== null && b !== null ? `Sharpe ${f2(s)} ${s > b ? "beats" : "trails"} the best simple alternative, ${nm(c.best_control)} (${f2(b)})` : null;
  },
  "mlvalidate:monte_carlo:": (r) => {
    const p = n(sec(r, "monte_carlo").prob_sharpe_not_positive);
    return p !== null ? `${pct(p, 0)} of resampled histories have no positive Sharpe` : null;
  },
  "mlvalidate:transfer:": (r) => {
    const t = sec(r, "transfer");
    return t.status === "computed" ? (t.outcome === "pass" ? "The edge carries over to other tickers and later dates" : `The edge does not transfer: worst Sharpe ${isNum(t.min_transfer_sharpe) ? f2(t.min_transfer_sharpe) : "–"}`) : null;
  },
  "mlvalidate:plateau:": (r) => {
    const p = sec(r, "plateau");
    return p.status === "computed" ? (p.label === "plateau" ? "Neighbouring settings perform similarly: a plateau, not a peak" : "Performance falls off near the chosen settings: a peak") : null;
  },
  "mlvalidate:leakage:": (r) => (sec(r, "leakage").badge === "pass" ? "No look-ahead found" : sec(r, "leakage").badge ? "Look-ahead check flagged a problem" : null),
  "mlvalidate:cpcv:": (r) => {
    const d = sec(r, "cpcv").distribution as Row | undefined;
    return d && isNum(d.p50) ? `Median split Sharpe ${f2(d.p50)}${isNum(d.share_positive) ? `; ${pct(d.share_positive, 0)} of splits positive` : ""}${isNum(d.p5) ? `, worst 5% below ${f2(d.p5)}` : ""}` : null;
  },
};

/** Calm / Normal / Stress from the API's state labels, else "State n". */
function stateName(r: FeatureResult, key: string) {
  const labels = ((r.meta as unknown as Row).state_labels ?? {}) as Record<string, string>;
  return labels[key] ?? `State ${key.replace(/\D/g, "")}`;
}

export function takeaway(featureId: string, key: string, view: string | undefined, result: FeatureResult): string | null {
  const g = GEN[`${featureId}:${key}:${view ?? ""}`];
  if (!g) return null;
  try {
    return g(result);
  } catch {
    return null;
  }
}
