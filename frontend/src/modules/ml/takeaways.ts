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

  "ml02:prediction_rank_table:": (r) => {
    const rows = [...out(r, "current_predictions")].filter((x) => isNum(x.prediction)).sort((a, b) => (b.prediction as number) - (a.prediction as number));
    return rows.length ? `${String(rows[0].ticker)} ranks first, expected ${pct(rows[0].prediction as number, 2)} over 21 days; ${String(rows[rows.length - 1].ticker)} last` : null;
  },
  "ml02:model_ic_leaderboard:": (r) => {
    const b = top(out(r, "model_ic_leaderboard"), "test_ic");
    return b ? `${cap(nm(b.model))} has the best test IC, ${f3(b.test_ic as number)}` : null;
  },

  /* ---------------- Volatility & risk */
  "ml03:risk_today:": (r) => {
    const t = out(r, "risk_today")[0];
    return t && isNum(t.range_21d_low) && isNum(t.range_21d_high) ? `${String(t.asset)}'s likely one-month range is ${pct(t.range_21d_low, 0)} to +${pct(t.range_21d_high, 0)}` : null;
  },
  "ml03:vol_term_structure:": (r) => {
    const rows = out(r, "vol_term_structure").filter((x) => isNum(x.forecast_vol) && isNum(x.horizon));
    const by = (h: number) => rows.filter((x) => x.horizon === h).map((x) => x.forecast_vol as number);
    const hs = [...new Set(rows.map((x) => x.horizon as number))].sort((a, b) => a - b);
    if (hs.length < 2) return null;
    const avg = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
    const a = avg(by(hs[0])), b = avg(by(hs[hs.length - 1]));
    return `Models expect volatility to ${b > a * 1.03 ? "rise" : b < a * 0.97 ? "fall" : "hold"}: ${pct(a, 0)} at ${hs[0]} day${hs[0] > 1 ? "s" : ""}, ${pct(b, 0)} at ${hs[hs.length - 1]}`;
  },
  "ml03:regime_probability:": (r) => {
    const rows = out(r, "regime_probability").filter((x) => isNum(x.stress_probability));
    const last = rows[rows.length - 1];
    return last ? `Stress probability is ${pct(last.stress_probability as number, 0)} today; above 50% on ${rows.filter((x) => (x.stress_probability as number) > 0.5).length} of ${rows.length} days` : null;
  },
  "ml03:forecast_rows:mlVolScatter": (r) => {
    const rows = out(r, "forecast_rows").filter((x) => x.horizon === 21 && isNum(x.forecast_vol) && isNum(x.realized_vol));
    if (rows.length < 10) return null;
    const over = rows.filter((x) => (x.forecast_vol as number) > (x.realized_vol as number)).length / rows.length;
    return `Forecasts ran above realised volatility ${pct(over, 0)} of the time at 21 days`;
  },
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
  "ml04:triple_barrier_label_distribution:": (r) => {
    const rows = out(r, "triple_barrier_label_distribution").filter((x) => isNum(x.count));
    const tot = rows.reduce((a, x) => a + (x.count as number), 0);
    const stop = rows.find((x) => Number(x.label) === -1), pt = rows.find((x) => Number(x.label) === 1);
    return tot && stop && pt ? `${pct((stop.count as number) / tot, 0)} of trades hit the stop first, ${pct((pt.count as number) / tot, 0)} the target` : null;
  },
  "ml04:event_outcome_timeline:": (r) => {
    const rows = out(r, "event_outcome_timeline");
    if (!rows.length) return null;
    const stop = rows.filter((x) => Number(x.label) === -1).length;
    return `Of the latest ${rows.length} events, ${pct(stop / rows.length, 0)} touched the stop-loss first`;
  },
  "ml04:barrier_hit_path_examples:": (r) => {
    const rows = out(r, "barrier_hit_path_examples");
    if (!rows.length) return null;
    const pt = rows.filter((x) => Number(x.label) === 1).length, stop = rows.filter((x) => Number(x.label) === -1).length;
    return `In ${rows.length} sampled trades the stop was hit ${stop} times, the target ${pt}`;
  },
  "ml04:barrier_sensitivity_surface:": (r) => {
    const rows = out(r, "barrier_sensitivity_surface").filter((x) => isNum(x.negative_rate) && isNum(x.stop_loss));
    if (rows.length < 2) return null;
    const lo = rows.reduce((a, x) => ((x.negative_rate as number) < (a.negative_rate as number) ? x : a)), hi = rows.reduce((a, x) => ((x.negative_rate as number) > (a.negative_rate as number) ? x : a));
    return `Stop-outs range from ${pct(lo.negative_rate as number, 0)} to ${pct(hi.negative_rate as number, 0)} across barrier widths`;
  },
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
  "ml05:holding_risk:": (r) => {
    const rows = out(r, "holding_risk").filter((x) => isNum(x.current_risk_contribution));
    const b = top(rows, "current_risk_contribution");
    if (!b) return null;
    const after = n(b.target_risk_contribution);
    return `${String(b.asset)} carries ${pct(b.current_risk_contribution as number, 0)} of portfolio risk now${after !== null ? `, ${pct(after, 0)} after the trades` : ""}`;
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

  "ml05:rebalance_log:": (r) => {
    const rows = out(r, "rebalance_log");
    return rows.length ? `Traded at ${rows.filter((x) => x.traded).length} of ${rows.length} rebalances; the rest did not pay for their cost` : null;
  },
  "ml05:black_litterman_posterior_return_vector:": (r) => {
    const rows = out(r, "black_litterman").filter((x) => isNum(x.posterior_return) && isNum(x.reference_prior_return));
    const b = rows.sort((a, c) => Math.abs((c.posterior_return as number) - (c.reference_prior_return as number)) - Math.abs((a.posterior_return as number) - (a.reference_prior_return as number)))[0];
    if (!b) return null;
    const d = (b.posterior_return as number) - (b.reference_prior_return as number);
    return Math.abs(d) < 1e-6 ? "Without alpha views the posterior equals the prior" : `The views move ${String(b.asset)} most: ${d > 0 ? "+" : ""}${pct(d, 1)} expected return`;
  },
  "ml06:ensemble_vs_hmm_comparison:": (r) => {
    const a = n(out(r, "ensemble_vs_hmm_comparison")[0]?.oos_agreement);
    return a !== null ? `An independent classifier agrees with the state on ${pct(a, 0)} of held-out days` : null;
  },
  "ml06:pc1_variance_monitor:": (r) => {
    const v = out(r, "pc1_variance_monitor").map((x) => x.pc1_explained_variance).filter(isNum);
    if (!v.length) return null;
    const avg = v.reduce((a, b) => a + b, 0) / v.length, now = v[v.length - 1];
    return `One factor explains ${pct(now, 0)} of moves now, vs ${pct(avg, 0)} on average${now > avg * 1.2 ? ": stocks are moving together" : ""}`;
  },
  "ml06:correlation_network_density:": (r) => {
    const d = out(r, "correlation_network_density")[0];
    return d && isNum(d.density) ? `${pct(d.density, 0)} of stock pairs are strongly correlated (|ρ| > ${isNum(d.absolute_correlation_threshold) ? d.absolute_correlation_threshold : "?"})` : null;
  },

  /* ---------------- Purged CV */
  "ml01:per_fold_performance:mlFoldMatrix": (r) => {
    const rows = out(r, "per_fold_performance");
    return rows.length ? `${rows.length} splits, each purged of ${isNum(rows[0].purged_observations) ? rows[0].purged_observations : "overlapping"} observations around the test window` : null;
  },
  "ml01:probability_of_backtest_overfitting:": (r) => {
    const x = out(r, "probability_of_backtest_overfitting")[0];
    return x && isNum(x.pbo) ? `Probability of backtest overfitting ${pct(x.pbo, 0)}` : x?.status === "unavailable" ? "Overfitting tests need every trial you ran" : null;
  },
  "ml01:purged_vs_naive_cv_comparison:": (r) => {
    const rows = out(r, "purged_vs_naive_cv_comparison");
    const nv = n(rows.find((x) => x.method === "naive_cpcv")?.sharpe), pg = n(rows.find((x) => x.method === "purged_cpcv")?.sharpe);
    if (nv === null || pg === null) return null;
    return Math.abs(nv - pg) < 0.1 ? `Purging barely moves Sharpe (${f2(nv)} to ${f2(pg)}): no leakage inflation` : `Purging moves Sharpe from ${f2(nv)} to ${f2(pg)}${nv > pg ? ": the naive split overstated it" : ""}`;
  },
  "ml01:backtest_paths_chart:": (r) => {
    const last = new Map<string, number>();
    for (const x of out(r, "backtest_paths_chart")) if (isNum(x.equity)) last.set(String(x.path), x.equity);
    const v = [...last.values()].sort((a, b) => a - b);
    if (!v.length) return null;
    return `Median path turned $1 into $${f2(v[Math.floor(v.length / 2)])}; ${v.filter((x) => x > 1).length} of ${v.length} paths made money`;
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
  "mlvalidate:autopsy:": (r) => {
    const c = ((sec(r, "autopsy").ranked_causes as Row[]) ?? []).filter((x) => isNum(x.severity)).sort((a, b) => (b.severity as number) - (a.severity as number));
    const serious = c.filter((x) => (x.severity as number) >= 0.66).length;
    return c.length ? (serious ? `${serious} of ${c.length} causes explain most of the result; worst: ${String(c[0].phrase ?? c[0].cause).replace(/_/g, " ")}` : "No cause explains a large share of the result") : null;
  },
  "mlvalidate:autopsy:valCostCurve": (r) => {
    const cost = ((sec(r, "autopsy").ranked_causes as Row[]) ?? []).find((x) => isNum(x.breakeven_bps));
    return cost ? `The edge survives costs up to ${(cost.breakeven_bps as number).toFixed(0)} bps per unit of turnover` : null;
  },
  "mlvalidate:controls:valShuffle": (r) => {
    const sh = sec(r, "controls").shuffled as Row | undefined, s = n(sec(r, "controls").strategy_sharpe);
    if (!sh || !isNum(sh.p_value)) return null;
    return `${pct(sh.p_value, 0)} of shuffled signals did as well${s !== null ? ` as Sharpe ${f2(s)}` : ""}${sh.p_value < 0.05 ? ": unlikely to be luck" : ": luck cannot be ruled out"}`;
  },
  "mlvalidate:deflated_sharpe:": (r) => {
    const d = sec(r, "deflated_sharpe");
    return isNum(d.dsr) ? `Deflated Sharpe ${f2(d.dsr)} after ${isNum(d.trials) ? d.trials : "?"} trial${d.trials === 1 ? "" : "s"}${d.dsr >= 0.95 ? ": significant" : ": short of the 0.95 bar"}` : null;
  },
  "mlvalidate:improve:": (r) => {
    const im = sec(r, "improve");
    if (im.status !== "ok" || !isNum(im.sharpe_delta)) return null;
    return im.improved ? `Meta-labelling adds ${f2(im.sharpe_delta)} Sharpe: ${String(im.best_variant).replace(/_/g, " ")} is better` : `Filtering does not help: the best variant changes Sharpe by ${im.sharpe_delta >= 0 ? "+" : ""}${f2(im.sharpe_delta)}`;
  },
  "mlvalidate:receipt:": (r) => {
    const h = sec(r, "receipt").receipt_sha256;
    return typeof h === "string" ? `Reproducible: rerun the same settings to get receipt ${h.slice(0, 12)}…` : null;
  },
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
