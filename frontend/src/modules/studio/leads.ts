import { isNum, pct } from "@/modules/research/format";
import type { FeatureResult, Row } from "@/modules/research/types";
import { metaOf } from "./types";

const money = (v: number) => (v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v.toFixed(0)}`);
export { money };

/** The one-line finding on each card (Outputs v2): built from the run's own numbers, or null when there is nothing to say. */
export function lead(view: string, r: FeatureResult): string | null {
  const m = metaOf(r), x = m.metrics;
  const rows = (k: string) => ((r.tables[k] ?? r.charts[k] ?? []) as Row[]);
  switch (view) {
    case "stEquity": return isNum(x.cagr) ? `Net ${pct(x.cagr)} a year against ${m.benchmark ?? "no benchmark"}${isNum(x.benchmark_cagr) ? ` ${pct(x.benchmark_cagr)}` : ""}` : null;
    case "stStartDates": { const s = m.start_dates; return s.of ? `Positive from ${s.positive} of ${s.of} start dates; CAGR ${pct(s.cagr_low, 0)} to ${pct(s.cagr_high, 0)}` : null; }
    case "stSurvivorship": { const s = m.survivorship; if (s.status !== "ok" || !isNum(s.with_delisted) || !isNum(s.survivors_only)) return null;
      const d = s.survivors_only - s.with_delisted; return `Dead companies ${d >= 0 ? "cost" : "added"} ${Math.abs(d * 100).toFixed(1)} points a year (${pct(s.survivors_only)} vs ${pct(s.with_delisted)})`; }
    case "stCarriedBy": { const c = rows("carried_by").find((q) => q.top === 5) ?? rows("carried_by")[0];
      return c && isNum(c.share) ? `Best ${String(c.top)} trade${c.top === 1 ? "" : "s"} made ${pct(c.share, 0)} of profit${isNum(c.cagr_without) ? `; without them CAGR ${pct(c.cagr_without)}` : ""}` : "No net profit to share out"; }
    case "stTradeShape": { const t = rows("trades"), losers = t.filter((q) => isNum(q.pnl) && q.pnl < 0), risk = losers.filter((q) => isNum(q.risk) && isNum(q.mfe) && isNum(q.entry) && isNum(q.shares));
      if (risk.length >= 5) { const hit = risk.filter((q) => (q.mfe as number) * (q.entry as number) * (q.shares as number) >= (q.risk as number)).length; return `Losers reached +1R in ${pct(hit / risk.length, 0)} of cases`; }
      return isNum(x.win_rate) ? `${pct(x.win_rate, 0)} win; average win ${isNum(x.avg_win) ? money(x.avg_win) : "—"}, loss ${isNum(x.avg_loss) ? money(Math.abs(x.avg_loss)) : "—"}` : null; }
    case "stByRegime": { const t = rows("by_regime")[0]; return t && isNum(t.share) ? `${pct(t.share, 0)} of profit in ${String(t.regime)} (${String(t.trades)} trades)` : null; }
    case "stSeasonality": { const s = [...rows("seasonality")].sort((a, b) => (b.mean as number) - (a.mean as number)); return s.length >= 12 ? `Best month ${String(s[0].month)} ${pct(s[0].mean, 1)}; worst ${String(s.at(-1)!.month)} ${pct(s.at(-1)!.mean, 1)}` : null; }
    case "stContributors": { const n = rows("per_name"); if (!n.length) return null; let acc = 0, k = 0; const tot = n.reduce((a, q) => a + Math.max(0, q.pnl as number), 0);
      for (const q of n) { if (acc >= tot / 2) break; acc += Math.max(0, q.pnl as number); k++; } return tot > 0 ? `${k} of ${n.length} names made half the profit` : null; }
    case "stTradeFan": return isNum(m.paths.drawdown_p95) ? `95% of reshuffled paths stay above ${pct(m.paths.drawdown_p95, 0)} drawdown (actual ${pct(x.max_drawdown, 0)})` : null;
    case "stRuin": { const r = rows("ruin").find((q) => q.drawdown === 0.3); return r ? `P(drawdown > 30%) = ${pct(r.probability, 0)}` : null; }
    case "stStabilityOpt": { const st = (r.meta as { stability?: { within_20pct: number; cells: number } }).stability; return st ? `${pct(st.within_20pct, 0)} of ${st.cells} neighbours within 20% of the best` : null; }
    case "stSpread": { const l = (r.meta as { spread_labels?: string[] }).spread_labels ?? []; return l.length ? `${l.length} settings on the plateau; best ${l[0]}` : null; }
    case "stTimeline": { const t = rows("by_regime")[0]; return t ? `Most profit came in ${String(t.regime)}` : null; }
    case "stConditions": { const c = rows("conditions").filter((q) => isNum(q.sharpe)).sort((a, b) => (a.sharpe as number) - (b.sharpe as number))[0]; return c ? `Weakest: ${String(c.condition).toLowerCase()}, Sharpe ${(c.sharpe as number).toFixed(2)}` : null; }
    case "stRuleCheck": { const c = m.rule_check; return c?.starts ? `Passes from ${c.pass} of ${c.starts} start dates (${pct(c.pass_share ?? 0, 0)})` : null; }
    case "stHoldings": { const n = rows("per_name"); return n.length ? `${n.length} names traded; ${n.filter((q) => (q.pnl as number) > 0).length} made money` : null; }
    case "stStreaks": return isNum(m.paths.streak_p95) ? `95th percentile losing streak ${m.paths.streak_p95} trades; actual ${m.paths.streak_actual}` : null;
    case "dataTable": return null;
    case "monthlyHeatmap": return isNum(m.without_best_months) ? `Without the best 3 months: CAGR ${pct(m.without_best_months)}` : null;
    case "stCrises": { const c = [...rows("crises")].sort((a, b) => (a.benchmark as number) - (b.benchmark as number))[0];
      return c && isNum(c.strategy) ? `${pct(c.strategy, 0)} vs ${m.benchmark ?? "benchmark"} ${pct(c.benchmark, 0)} in ${String(c.period)}` : "No crisis period inside this data"; }
    case "stDrawdowns": { const d = rows("drawdowns")[0]; return d && isNum(d.months) ? `Deepest drawdown ${pct(d.depth, 0)}, ${(d.months as number).toFixed(0)} months${d.recovered ? "" : ", not recovered"}` : "No drawdown"; }
    case "stStability": { const t = m.thirds_sharpe; if (t.length !== 3 || !t.every(isNum)) return null;
      return `Sharpe ${t[0].toFixed(1)} first third, ${t[2].toFixed(1)} last third${t[2] < t[0] - 0.5 ? ": decaying" : t[2] > t[0] + 0.5 ? ": improving" : ""}`; }
    case "stCosts": return m.costs_off ? "Costs off" : isNum(m.costs.share_of_gross) ? `Costs ate ${pct(m.costs.share_of_gross, 0)} of gross profit` : `Costs ${money(m.costs.total)}; no gross profit to compare`;
    case "stCapacity": return isNum(m.capacity) ? `About ${money(m.capacity)} before one trade in ten exceeds 1% of the day's volume` : null;
    case "stExposure": return `In the market ${pct(m.exposure.time_in_market, 0)} of days; average exposure ${pct(m.exposure.avg_gross, 0)}`;
    default: return null;
  }
}
