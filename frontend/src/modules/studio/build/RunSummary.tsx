"use client";

import { SERIES } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import type { QuickRun } from "./DevIDE";

const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const sign = (v: number | null | undefined, f: (x: number) => string) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${f(v)}`);

/** A finished run at a glance: KPIs with the change from the last run, summary cards, equity against the benchmark, trades. Used by Build's Results tab and the Report page. */
export function RunSummary({ quick }: { quick: QuickRun }) {
  const m = quick.result?.meta, d = quick.delta;
  if (!m) return null;
  return (
    <>
      <div className="kpis">
        <div className="kpi"><span>Return</span><b>{pct(m.total_return)}</b>{d ? <i className="dv-delta">{sign(d.total_return, (x) => `${(x * 100).toFixed(1)} pts`)}</i> : null}</div>
        <div className="kpi"><span>Sharpe</span><b>{m.metrics?.sharpe?.toFixed(2) ?? "—"}</b>{d ? <i className="dv-delta">{sign(d.sharpe, (x) => x.toFixed(2))}</i> : null}</div>
        <div className="kpi"><span>Max drawdown</span><b>{m.metrics?.max_drawdown != null ? pct(m.metrics.max_drawdown) : "—"}</b></div>
        <div className="kpi"><span>Trades</span><b>{m.metrics?.trades ?? "—"}</b>{d ? <i className="dv-delta">{sign(d.trades, (x) => String(x))}</i> : null}</div>
      </div>

      {quick?.result?.summary_cards?.length ? <div className="dv-cards">{quick.result.summary_cards.filter((c) => !/^(sharpe|max drawdown|trades)$/i.test(c.label)).map((c) => <span key={c.label}><i>{c.label}</i><b>{c.value == null ? "—" : /win/i.test(c.label) ? `${(c.value * 100).toFixed(1)}%` : /drawdown|cagr/i.test(c.label) ? pct(c.value) : c.value.toFixed(2)}</b></span>)}</div> : null}
      {quick?.result?.charts?.equity_curve?.length ? <div className="dv-plot"><b>Equity vs benchmark</b><TimeSeries data={quick.result.charts.equity_curve} height={280}
        series={[{ key: "strategy", label: "Strategy", color: SERIES[0] }, { key: "benchmark", label: "Benchmark", color: "var(--text-3)" }]} /></div> : null}
      {m.trade_split ? <div className="dv-plot"><b>Closed trades by side</b><DataTable rows={Object.entries(m.trade_split).map(([side, v]) => ({ side, trades: v.count ?? 0, win_rate: v.win_rate ?? null, profit_factor: v.profit_factor ?? null, avg_win: v.avg_win ?? null, avg_loss: v.avg_loss ?? null, expectancy: v.expectancy ?? null }))} /></div> : null}
      {quick?.result?.tables?.trades?.length ? <>
        <div className="dv-plot"><b>Return per trade</b><Distribution values={quick.result.tables.trades.map((t) => t.return).filter((value): value is number => typeof value === "number" && Number.isFinite(value))} xLabel="Return per trade" height={180} format={(v) => `${(v * 100).toFixed(1)}%`} /></div>
        <div className="dv-plot"><b>Trades</b><DataTable rows={quick.result.tables.trades} opts={{ viewKey: "studio:dev:quicktrades" }} /></div>
      </> : null}
    </>
  );
}
