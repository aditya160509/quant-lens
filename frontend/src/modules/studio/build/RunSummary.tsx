"use client";

import { DrawdownStrip } from "@/charts/Backtest";
import { SERIES } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import type { QuickRun } from "./DevIDE";

const pct = (v?: number | null) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const sign = (v: number | null | undefined, f: (x: number) => string) => (v == null ? "" : `${v >= 0 ? "+" : "−"}${f(Math.abs(v))}`);
/** Below this many closed trades, ratios such as win rate and profit factor are noise and show as n/a. */
export const MIN_TRADES = 10;

export type Stat = { label: string; value: string; tone?: "up" | "down" | null; sub?: string; muted?: boolean; title?: string };
/** One row of figures, the single stat style for Tester and Results. */
export function StatStrip({ stats }: { stats: Stat[] }) {
  return <dl className="dv-strip">{stats.map((s) => <div key={s.label} title={s.title}><dt>{s.label}</dt><dd className="num" data-tone={s.tone ?? undefined} data-muted={s.muted || undefined}>{s.value}{s.sub ? <small>{s.sub}</small> : null}</dd></div>)}</dl>;
}

/** A finished run at a glance: what was run, one stat strip, equity with drawdown, trades. Used by Build's Results tab and the Report page. */
export function RunSummary({ quick }: { quick: QuickRun }) {
  const m = quick.result?.meta, d = quick.delta;
  if (!m) return null;
  const x = m.metrics ?? {}, n = x.trades ?? 0, few = n < MIN_TRADES, open = m.open_trades ?? 0;
  const thin = (v: string) => (few ? { value: "n/a", muted: true, title: `${n} closed trade${n === 1 ? "" : "s"}: too few for this ratio` } : { value: v });
  const stats: Stat[] = [
    { label: "Return", value: pct(m.total_return), tone: (m.total_return ?? 0) >= 0 ? "up" : "down", sub: d ? sign(d.total_return, (v) => `${(v * 100).toFixed(1)} pts`) : undefined },
    { label: "CAGR", value: pct(x.cagr) },
    { label: "Sharpe", value: x.sharpe?.toFixed(2) ?? "—", sub: d ? sign(d.sharpe, (v) => v.toFixed(2)) : undefined },
    { label: "Max drawdown", value: pct(x.max_drawdown), tone: "down" },
    { label: "Win rate", ...thin(x.win_rate == null ? "—" : `${(x.win_rate * 100).toFixed(1)}%`) },
    { label: "Profit factor", ...thin(x.profit_factor?.toFixed(2) ?? "—") },
    { label: "Trades", value: String(n), sub: open ? `${open} open` : undefined, title: `${n} closed${open ? `, ${open} still open at the end` : ""}; trade stats count closed trades` },
    { label: "Exposure", value: m.exposure?.time_in_market == null ? "—" : `${Math.round(m.exposure.time_in_market * 100)}%`, title: "Share of days with a position" },
  ];
  const curve = quick.result?.charts?.equity_curve ?? [];
  let peak = -Infinity;
  const dd = curve.map((r) => { peak = Math.max(peak, r.strategy); return { date: r.date, drawdown: peak > 0 ? r.strategy / peak - 1 : 0 }; });
  const trades = quick.result?.tables?.trades ?? [];
  const firstEntry = trades.reduce<string | null>((a, t) => { const e = String(t.entry_date ?? ""); return e && (!a || e < a) ? e : a; }, null);
  const idle = firstEntry && curve[0] && firstEntry > curve[0].date ? firstEntry : null;
  const u = m.universe, p = m.period;
  const scope = [quick.level === "quick" ? "Quick run" : "Full run", u?.held != null ? `${u.held} name${u.held === 1 ? "" : "s"}` : null, p ? `${p[0]} → ${p[1]}` : null,
    m.holdout_from ? `hold-out from ${m.holdout_from} excluded` : null, m.fill_model === "same_close" ? "fills same close" : m.fill_model ? "fills next open" : null, m.data_version ? `data ${m.data_version}` : null].filter(Boolean).join(" · ");
  const split = m.trade_split, twoSided = !!split && (split.long?.count ?? 0) > 0 && (split.short?.count ?? 0) > 0;
  return (
    <>
      <p className="dv-scope">{scope}</p>
      <StatStrip stats={stats} />
      {curve.length ? <div className="dv-plot"><b>Equity vs {m.benchmark ?? "benchmark"}{idle ? <span className="dv-count"> · no positions until {idle}</span> : null}</b>
        <TimeSeries data={curve} height={260} series={[{ key: "strategy", label: "Strategy", color: SERIES[0] }, { key: "benchmark", label: m.benchmark ?? "Benchmark", color: "var(--text-3)" }]} />
        <DrawdownStrip rows={dd} /></div> : null}
      {twoSided ? <div className="dv-plot"><b>Closed trades by side</b><DataTable rows={["all", "long", "short"].map((side) => { const v = split![side] ?? {}; return { side, trades: v.count ?? 0, win_rate: v.win_rate ?? null, profit_factor: v.profit_factor ?? null, avg_win: v.avg_win ?? null, avg_loss: v.avg_loss ?? null, expectancy: v.expectancy ?? null }; })} /></div> : null}
      {trades.length ? <>
        <div className="dv-plot"><b>Return per trade</b><Distribution values={trades.map((t) => t.return).filter((value): value is number => typeof value === "number" && Number.isFinite(value))} xLabel="Return per trade" height={180} format={(v) => `${(v * 100).toFixed(1)}%`} /></div>
        <div className="dv-plot"><b>Trades</b><DataTable rows={trades} opts={{ viewKey: "studio:dev:quicktrades" }} /></div>
      </> : null}
    </>
  );
}
