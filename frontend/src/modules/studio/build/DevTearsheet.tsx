"use client";

import { Settings2 } from "lucide-react";
import { useMemo, useState } from "react";
import { SERIES } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { Heatmap } from "@/charts/Heatmap";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import type { QuickRun } from "./DevIDE";
import { drawdown, monthly, returns, rollingSharpe, stats, topDrawdowns } from "./devStats";

const SECTIONS = ["Statistics", "Monthly returns", "Drawdown", "Rolling Sharpe", "Distribution"] as const;
const KEY = "studio:dev:tearsheet";
const pc = (v: number | null) => (v === null ? "—" : `${(v * 100).toFixed(1)}%`);
const fx = (v: number | null) => (v === null ? "—" : v.toFixed(2));
const ANNUAL = "Annualised over 252 periods a year with a zero risk-free rate";
const TIPS: Record<string, string> = { CAGR: "Compound annual growth from first to last equity, by calendar days", Sharpe: ANNUAL, Sortino: `${ANNUAL}; downside deviation only`, Calmar: "CAGR over max drawdown", Volatility: ANNUAL };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** One scrollable page over a finished run: statistics, monthly returns, drawdowns, rolling Sharpe, return distribution. */
export function DevTearsheet({ quick }: { quick: QuickRun | null }) {
  const [off, setOff] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; } });
  const toggle = (s: string) => setOff((o) => { const n = o.includes(s) ? o.filter((x) => x !== s) : [...o, s]; try { localStorage.setItem(KEY, JSON.stringify(n)); } catch { /* blocked */ } return n; });
  const eq = useMemo(() => (quick?.result?.charts?.equity_curve ?? []).map((p) => ({ date: p.date, value: p.strategy })), [quick]);
  const s = useMemo(() => (eq.length > 1 ? stats(eq) : null), [eq]);
  const mo = useMemo(() => monthly(eq), [eq]);
  const dd = useMemo(() => drawdown(eq), [eq]);
  const worst = useMemo(() => topDrawdowns(eq), [eq]);
  const roll = useMemo(() => rollingSharpe(eq), [eq]);
  const trades = quick?.result?.tables?.trades ?? [];
  if (!s) return <p className="dv-empty">Run a backtest to see its tearsheet</p>;
  const on = (n: string) => !off.includes(n);
  const rate = (trades.length ? trades.filter((t) => Number(t.pnl) > 0).length / trades.length : 0);
  const gain = trades.reduce((a, t) => a + Math.max(0, Number(t.pnl)), 0), loss = trades.reduce((a, t) => a + Math.min(0, Number(t.pnl)), 0);
  const cards: [string, string][] = [["CAGR", pc(s.cagr)], ["Sharpe", fx(s.sharpe)], ["Sortino", fx(s.sortino)], ["Max drawdown", pc(s.maxdd)], ["Calmar", fx(s.calmar)], ["Volatility", pc(s.vol)], ["Best day", pc(s.best)], ["Worst day", pc(s.worst)],
    ["Win rate", pc(rate)], ["Profit factor", loss ? (gain / -loss).toFixed(2) : "—"]];
  return (
    <div className="dv-tear">
      <details className="dv-view dv-gear" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
        <summary className="icon-btn" aria-label="Sections" title="Sections"><Settings2 size={14} /></summary>
        <div className="dv-menu" role="menu">{SECTIONS.map((n) => <button key={n} role="menuitemcheckbox" aria-checked={on(n)} onClick={() => toggle(n)}>{n}</button>)}</div>
      </details>
      {on("Statistics") ? <div className="dv-cards">{cards.map(([k, v]) => <span key={k} title={TIPS[k]}><i>{k}</i><b>{v}</b></span>)}</div> : null}
      {on("Monthly returns") && mo.years.length ? <div className="dv-plot"><b>Monthly returns</b><Heatmap rows={mo.years} cols={MONTHS} values={mo.values} format={pc} /></div> : null}
      {on("Drawdown") ? <div className="dv-plot"><b>Underwater</b>
        <TimeSeries data={dd} height={160} series={[{ key: "dd", label: "Drawdown", color: SERIES[1] }]} />
        <DataTable rows={worst.map((d, i) => ({ rank: i + 1, depth: d.depth, start: d.start, trough: d.trough, recovered: d.end ?? "open", days: Math.round(d.days) }))} /></div> : null}
      {on("Rolling Sharpe") && roll.length ? <div className="dv-plot"><b>Rolling Sharpe, 63 days</b><TimeSeries data={roll} height={160} series={[{ key: "sharpe", label: "Sharpe", color: SERIES[0] }]} refLines={[{ y: 0 }]} /></div> : null}
      {on("Distribution") ? <div className="dv-plot"><b>Daily returns</b><Distribution values={returns(eq)} xLabel="Daily return" height={180} /></div> : null}
    </div>
  );
}
