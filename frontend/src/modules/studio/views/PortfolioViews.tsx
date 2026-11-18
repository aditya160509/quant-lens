"use client";

import { Dendrogram } from "@/charts/Dendrogram";
import { StackedArea } from "@/charts/StackedArea";
import { XYPlot } from "@/charts/XYPlot";
import type { ViewProps } from "@/modules/research/outputs/types";
import { Skipped } from "./BacktestViews";

type PMeta = { names: string[]; tree: { link: number[][]; order: number[] } | null };

/** Members clustered by correlation distance: the tree HRP splits risk down. */
export function Tree({ result }: ViewProps) {
  const m = result.meta as unknown as PMeta;
  if (!m.tree) return <Skipped reason="needs three or more members" />;
  return <Dendrogram merges={m.tree.link.map(([l, r, d, c]) => ({ left: l, right: r, distance: d, count: c }))} leaves={m.names} />;
}

/** Weights as they were re-estimated (quarterly, or each rotation). */
export function WeightsOverTime({ rows, result }: ViewProps) {
  const names = (result.meta as unknown as PMeta).names;
  if (rows.length < 2) return <Skipped reason="weights are fixed; set Weights to quarterly or turn on rotation" />;
  return <StackedArea data={rows} keys={names} title="Weights" />;
}

type Frontier = { points: { vol: number; ret: number }[]; chosen: { vol: number; ret: number }; members: { strategy: string; vol: number; ret: number }[] };
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

/** Long-only efficient frontier of the members, with the chosen mix and each member marked. */
export function FrontierView({ result }: ViewProps) {
  const f = (result.meta as { frontier?: Frontier }).frontier;
  if (!f || f.points.length < 3) return <Skipped reason="needs two or more members with history" />;
  const pts = [{ x: f.chosen.vol, y: f.chosen.ret, label: "This mix", emphasis: true }, ...f.members.map((m) => ({ x: m.vol, y: m.ret, label: m.strategy }))];
  return <XYPlot points={pts} lines={[{ label: "Frontier", points: f.points.map((p) => ({ x: p.vol, y: p.ret })), color: "var(--text-3)" }]} labelPoints
    xLabel="Volatility (annual)" yLabel="Return (annual)" formatX={pct} formatY={pct} height={300} />;
}

type Stats = { effective_bets?: number | null; diversification_ratio?: number | null; vol?: number | null; vol_at_corr_08?: number | null; rebalance_turnover?: number | null;
  rebalance_cost?: number | null; beta?: number | null; alpha?: number | null; information_ratio?: number | null; tracking_error?: number | null;
  netting?: { saved: number } | null; oos?: { in_sample_sharpe: number | null; out_of_sample_sharpe: number | null } | null };

/** Diversification, stress and benchmark numbers for the chosen mix, with any warnings first. */
export function RiskStats({ result }: ViewProps) {
  const m = result.meta as { stats?: Stats; warnings?: string[] };
  const s = m.stats;
  if (!s) return <Skipped reason="run the portfolio again to compute risk" />;
  const f = (v: number | null | undefined, k: "pct" | "x" | "n") => (v == null ? "—" : k === "pct" ? `${(v * 100).toFixed(1)}%` : k === "x" ? `${v.toFixed(2)}×` : v.toFixed(2));
  const rows: [string, string][] = [
    ["Effective number of bets", f(s.effective_bets, "n")], ["Diversification ratio", f(s.diversification_ratio, "x")],
    ["Volatility", f(s.vol, "pct")], ["Volatility if every pair correlated 0.8", f(s.vol_at_corr_08, "pct")],
    ["Rebalance turnover a year", f(s.rebalance_turnover, "pct")], ["Rebalance cost a year (10 bps)", f(s.rebalance_cost, "pct")],
    ["Netting saves (traded notional)", f(s.netting?.saved, "pct")],
    ["Sharpe, weights set on past year only", f(s.oos?.out_of_sample_sharpe, "n")], ["Sharpe, weights from whole period", f(s.oos?.in_sample_sharpe, "n")],
    ["Beta to benchmark", f(s.beta, "n")], ["Alpha a year", f(s.alpha, "pct")], ["Information ratio", f(s.information_ratio, "n")], ["Tracking error", f(s.tracking_error, "pct")],
  ];
  return (
    <div>
      {m.warnings?.map((w) => <p key={w} className="bd-find warning"><b>Check</b>{w}</p>)}
      <table className="pf-stats"><tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
    </div>
  );
}
