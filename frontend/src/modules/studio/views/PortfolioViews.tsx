"use client";

import { Dendrogram } from "@/charts/Dendrogram";
import { StackedArea } from "@/charts/StackedArea";
import { useState } from "react";
import toast from "react-hot-toast";
import { XYPlot } from "@/charts/XYPlot";
import type { ViewProps } from "@/modules/research/outputs/types";
import { studio } from "../api";
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
  netting?: { saved: number } | null; book_gross?: number | null; book_net?: number | null; book_beta?: number | null; oos?: { in_sample_sharpe: number | null; out_of_sample_sharpe: number | null } | null };

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
    ["Gross exposure, last bar", f(s.book_gross, "pct")], ["Net exposure, last bar", f(s.book_net, "pct")], ["Beta of names held", f(s.book_beta, "n")],
    ["Beta to benchmark", f(s.beta, "n")], ["Alpha a year", f(s.alpha, "pct")], ["Information ratio", f(s.information_ratio, "n")], ["Tracking error", f(s.tracking_error, "pct")],
  ];
  return (
    <div>
      {m.warnings?.map((w) => <p key={w} className="bd-find warning"><b>Check</b>{w}</p>)}
      <table className="pf-stats"><tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
    </div>
  );
}

type Member = { name: string; strategy_id: string; version: number; weight: number };
type Book = { book: { id: string; from: string }; as_of: string; stale: boolean; status: string; reason: string | null; orders: { symbol: string; action: string; shares: number }[];
  netting_saves: number; attribution: { strategy: string; weight: number; return: number; contribution: number }[]; paper_return: number | null; paper_sharpe: number | null };

/** Freeze this mix as one paper book; today's orders netted by symbol and paper P&L by member. */
export function DeployBook({ result }: ViewProps) {
  const members = (result.meta as { member_ids?: Member[] }).member_ids;
  const [from, setFrom] = useState("");
  const [busy, setBusy] = useState(false);
  const [b, setB] = useState<Book | null>(null);
  if (!members?.length) return <Skipped reason="run the portfolio again to deploy it" />;
  const deploy = () => {
    setBusy(true);
    void studio<{ id: string }>("POST", "/books", { members: members.map(({ strategy_id, version, weight }) => ({ strategy_id, version, weight })), as_of: from || null })
      .then((k) => studio<Book>("POST", `/books/${k.id}/today`, { payload: {} }))
      .then(setB, (e) => toast.error(e instanceof Error ? e.message : "Failed")).finally(() => setBusy(false));
  };
  const orders = b?.orders.map((o) => `${o.action.toUpperCase()} ${o.shares} ${o.symbol}`).join("\n") ?? "";
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <table className="pf-stats"><tbody>{members.map((m) => <tr key={m.strategy_id}><th>{m.name}</th><td>{pct(m.weight)}</td></tr>)}</tbody></table>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" type="date" aria-label="Backdate start" value={from} onChange={(e) => setFrom(e.target.value)} />
        <button className="btn" disabled={busy} onClick={deploy}>{busy ? "Deploying…" : "Deploy to paper"}</button>
      </div>
      {b ? (
        <>
          {b.stale ? <span className="chip down" style={{ justifySelf: "start" }}>data ends {b.as_of}</span> : null}
          {b.status === "ok" && b.paper_return != null
            ? <div className="st-fig"><b>{(b.paper_return * 100).toFixed(1)}%</b><span>paper since {b.book.from} · Sharpe {b.paper_sharpe?.toFixed(2) ?? "—"}</span></div>
            : <Skipped reason={b.reason ?? "waiting"} />}
          {b.attribution.length ? <table className="pf-stats"><tbody>{b.attribution.map((a) => <tr key={a.strategy}><th>{a.strategy}</th><td>{(a.contribution * 100).toFixed(1)}%</td></tr>)}</tbody></table> : null}
          {orders ? <pre className="bd-code" style={{ margin: 0 }}>{orders}</pre> : <Skipped reason={`no orders on ${b.as_of}`} />}
          {orders && b.netting_saves > 0.005 ? <p className="bd-find"><b>Netting</b>saves {(b.netting_saves * 100).toFixed(0)}% of shares</p> : null}
        </>
      ) : null}
    </div>
  );
}
