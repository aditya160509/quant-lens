"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Bars } from "@/charts/Bars";
import { DrawdownStrip } from "@/charts/Backtest";
import { Distribution } from "@/charts/Distribution";
import { TimeSeries } from "@/charts/TimeSeries";
import { Treemap } from "@/charts/Treemap";
import { XYPlot } from "@/charts/XYPlot";
import { DataTable } from "@/kit/DataTable";
import { isNum, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { money } from "../leads";
import { metaOf } from "../types";
import "../studio.css";

/** A card that could not be computed says why; it is never blank. */
export function Skipped({ reason }: { reason: string }) {
  return <div className="st-skip" role="status">skipped: {reason}</div>;
}

const usd = (v: number) => `$${Math.round(v).toLocaleString()}`;

/** Net against gross and the benchmark, with the underwater strip beneath. */
export function Equity({ rows, result, scope, keys }: ViewProps) {
  const m = metaOf(result);
  const [log, setLog] = useState(false);
  const data = useMemo(() => (log ? rows.map((r) => ({ ...r, strategy: isNum(r.strategy) ? Math.log10(r.strategy) : null, gross: isNum(r.gross) ? Math.log10(r.gross) : null, benchmark: isNum(r.benchmark) ? Math.log10(r.benchmark) : null })) : rows), [rows, log]);
  const series = [{ key: "strategy", label: "Net", color: "var(--accent)", width: 2 }, ...(m.costs_off ? [] : [{ key: "gross", label: "Gross", color: "var(--s3)", dash: true }]),
    ...(m.benchmark ? [{ key: "benchmark", label: m.benchmark, color: "var(--text-3)" }] : [])];
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <label className="st-toggle"><input type="checkbox" checked={log} onChange={(e) => setLog(e.target.checked)} />Log scale</label>
      <TimeSeries data={data} series={series} height={280} format={log ? (v) => usd(10 ** v) : usd} notesKey={`${scope}:${keys[0]}`} />
      <DrawdownStrip rows={rows} />
    </div>
  );
}

/** CAGR by start date; dates that break the drawdown limit are marked. */
export function StartDates({ rows }: ViewProps) {
  if (rows.length < 2) return <Skipped reason="the period is too short to move the start date" />;
  return <Bars bars={rows.map((r) => ({ label: String(r.start).slice(0, 7), value: isNum(r.cagr) ? r.cagr : 0, color: r.passes === false ? "var(--down)" : r.passes ? "var(--up)" : undefined,
    detail: [["Total return", pct(r.total_return)], ["Worst drawdown", pct(r.max_drawdown)], ["Trades", String(r.trades)], ["My limits", r.passes === null ? "—" : r.passes ? "pass" : "fail"]] }))}
    format={(v) => pct(v, 0)} signed={false} yLabel="CAGR" height={220} />;
}

export function Survivorship({ rows, result }: ViewProps) {
  const s = metaOf(result).survivorship;
  if (s.status !== "ok") return <Skipped reason={s.reason} />;
  return <TimeSeries data={rows} series={[{ key: "strategy", label: "Delisted kept", color: "var(--accent)", width: 2 }, { key: "survivors_only", label: "Survivors only", color: "var(--warn)" }]} height={220} format={usd} />;
}

/** Share of net profit from the best 1, 5 and 10 trades, and the CAGR left without them. */
export function CarriedBy({ rows }: ViewProps) {
  if (!rows.length || !rows.some((r) => isNum(r.share))) return <Skipped reason="no net profit to share out" />;
  return (
    <div className="st-pairs">
      {rows.map((r) => (
        <div key={String(r.top)} className="st-pair">
          <span>Best {String(r.top)}</span>
          <div className="bar"><i style={{ width: `${Math.min(100, Math.max(0, (r.share as number) * 100))}%` }} /></div>
          <b className="num">{pct(r.share, 0)}</b>
          <span />
          <span style={{ color: "var(--text-3)" }}>CAGR without them</span>
          <b className={`num ${isNum(r.cagr_without) && r.cagr_without < 0 ? "st-down" : ""}`}>{isNum(r.cagr_without) ? pct(r.cagr_without) : "—"}</b>
        </div>
      ))}
    </div>
  );
}

/** How far each trade went against and for the position before it closed. */
export function TradeShape({ rows }: ViewProps) {
  const pts = rows.filter((r) => isNum(r.mae) && isNum(r.mfe)).map((r) => ({ x: r.mae as number, y: r.mfe as number, group: (r.pnl as number) >= 0 ? "Winners" : "Losers", label: String(r.symbol),
    detail: [["Return", pct(r.return, 1)], ["Exit", String(r.exit_reason)], ["Entry", String(r.entry_date)]] as [string, string][] }));
  if (!pts.length) return <Skipped reason="no trades" />;
  return <XYPlot points={pts} xLabel="Worst move against (MAE)" yLabel="Best move for (MFE)" groupColors={{ Winners: "var(--up)", Losers: "var(--down)" }} formatX={(v) => pct(v, 0)} formatY={(v) => pct(v, 0)} height={300} />;
}

export function TradeReturns({ rows }: ViewProps) {
  const v = rows.map((r) => r.return).filter(isNum);
  return v.length < 5 ? <Skipped reason={`only ${v.length} trades`} /> : <Distribution values={v} observed={0} tail="two" xLabel="Return per trade" observedLabel="Break even" format={(x) => pct(x, 1)} />;
}

export function HoldTime({ rows }: ViewProps) {
  const w = rows.filter((r) => (r.pnl as number) >= 0).map((r) => r.bars).filter(isNum), l = rows.filter((r) => (r.pnl as number) < 0).map((r) => r.bars).filter(isNum);
  if (w.length + l.length < 5) return <Skipped reason={`only ${w.length + l.length} trades`} />;
  const q = (a: number[], p: number) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : 0; };
  return <Bars bars={[["Winners", w], ["Losers", l]].map(([label, a]) => ({ label: label as string, value: q(a as number[], 0.5), lo: q(a as number[], 0.25), hi: q(a as number[], 0.75), color: label === "Winners" ? "var(--up)" : "var(--down)" }))}
    format={(v) => `${v.toFixed(0)} bars`} signed={false} yLabel="Median bars held (25th to 75th)" height={220} />;
}

/** Strategy against the benchmark through each crisis that falls inside the data. */
export function Crises({ rows, result }: ViewProps) {
  if (!rows.length) return <Skipped reason="no crisis period falls inside this data" />;
  const bench = metaOf(result).benchmark ?? "Benchmark";
  const max = Math.max(1e-9, ...rows.flatMap((r) => [Math.abs((r.strategy as number) ?? 0), Math.abs((r.benchmark as number) ?? 0)]));
  return (
    <div className="st-pairs">
      {rows.map((r) => (
        <div key={String(r.period)} style={{ display: "grid", gap: 4 }}>
          <div className="st-pair"><span title={`${String(r.from)} to ${String(r.to)}`}>{String(r.period)}</span><div className="bar"><i className={(r.strategy as number) < 0 ? "neg" : ""} style={{ width: `${(Math.abs(r.strategy as number) / max) * 100}%` }} /></div><b className="num">{pct(r.strategy, 0)}</b></div>
          {isNum(r.benchmark) ? <div className="st-pair"><span style={{ color: "var(--text-4)" }}>{bench}</span><div className="bar"><i className="dim" style={{ width: `${(Math.abs(r.benchmark) / max) * 100}%` }} /></div><b className="num" style={{ color: "var(--text-3)" }}>{pct(r.benchmark, 0)}</b></div> : null}
        </div>
      ))}
    </div>
  );
}

export function Drawdowns({ rows, result }: ViewProps) {
  const curve = (result.charts.equity_curve ?? []) as ViewProps["rows"];
  return <div style={{ display: "grid", gap: 10 }}><DrawdownStrip rows={curve} /><DataTable rows={rows} opts={{ maxHeight: 220 }} /></div>;
}

export function Stability({ rows, result }: ViewProps) {
  if (rows.length < 2) return <Skipped reason="needs at least six months of bars" />;
  const beta = rows.some((r) => isNum(r.beta_12m));
  return <TimeSeries data={rows} series={[{ key: "sharpe_6m", label: "Sharpe 6M", color: "var(--s2)" }, { key: "sharpe_12m", label: "Sharpe 12M", color: "var(--accent)", width: 2 },
    ...(beta ? [{ key: "beta_12m", label: `Beta to ${metaOf(result).benchmark ?? "benchmark"}`, color: "var(--text-3)", dash: true }] : [])]} refLines={[{ y: 0 }]} height={240} format={(v) => v.toFixed(1)} />;
}

export function Costs({ result }: ViewProps) {
  const c = metaOf(result).costs;
  const max = Math.max(Math.abs(c.gross_return), Math.abs(c.net_return), 1e-9);
  return (
    <div className="st-pairs">
      {[["Gross", c.gross_return], ["Net", c.net_return]].map(([l, v]) => <div key={l as string} className="st-pair"><span>{l}</span><div className="bar"><i className={(v as number) < 0 ? "neg" : ""} style={{ width: `${(Math.abs(v as number) / max) * 100}%` }} /></div><b className="num">{pct(v, 0)}</b></div>)}
      <div className="st-fig"><b>{usd(c.total)}</b><span>paid · turnover {c.turnover_per_year.toFixed(1)}× a year</span></div>
    </div>
  );
}

export function Capacity({ result }: ViewProps) {
  const cap = metaOf(result).capacity;
  return isNum(cap) ? <div className="st-fig"><b>{money(cap)}</b><span>starting capital</span></div> : <Skipped reason="no volume on the entry bars" />;
}

export function Exposure({ rows }: ViewProps) {
  return rows.length < 2 ? <Skipped reason="no bars" /> : <TimeSeries data={rows} series={[{ key: "gross", label: "Gross", kind: "area", color: "var(--accent)" }, { key: "net", label: "Net", color: "var(--text-2)" }]} height={200} format={(v) => pct(v, 0)} />;
}

/** Return and trade count per market regime at entry. */
export function ByRegime({ rows }: ViewProps) {
  if (!rows.length) return <Skipped reason="needs a benchmark to label regimes" />;
  return <Bars bars={rows.map((r) => ({ label: String(r.regime), value: r.pnl as number, detail: [["Trades", String(r.trades)], ["Win rate", pct(r.win_rate, 0)], ["Average return", pct(r.avg_return, 1)], ["Share of profit", pct(r.share, 0)], ["Days in regime", String(r.days)]] }))}
    format={(v) => money(v)} height={240} />;
}

export function Seasonality({ rows }: ViewProps) {
  if (rows.length < 12) return <Skipped reason="needs at least a full year of months" />;
  return <Bars bars={rows.map((r) => ({ label: String(r.month), value: r.mean as number, detail: [["Positive in", `${pct(r.hit_rate, 0)} of ${String(r.years)} years`]] }))} format={(v) => pct(v, 1)} height={220} />;
}

export function PerName({ rows }: ViewProps) {
  return <DataTable rows={rows} opts={{ maxHeight: 520, max: 100000, viewKey: "studio-names" }} />;
}

export function Contributors({ rows }: ViewProps) {
  const top = [...rows.slice(0, 10), ...rows.slice(-5).filter((r) => (r.pnl as number) < 0 && !rows.slice(0, 10).includes(r))];
  return <Bars bars={top.map((r) => ({ label: String(r.symbol), value: r.pnl as number, detail: [["Trades", String(r.trades)], ["Win rate", pct(r.win_rate, 0)]] }))} format={(v) => money(v)} height={240} />;
}

/** Same trades, reshuffled order: the band of equity paths luck alone could have dealt. */
export function TradeFan({ rows, result }: ViewProps) {
  const p = metaOf(result).paths;
  if (!rows.length) return <Skipped reason={p.reason ?? "fewer than 10 closed trades"} />;
  const line = (k: string, label: string, color: string, dash?: boolean) => ({ label, color, dash, points: rows.map((r) => ({ x: r.trade as number, y: r[k] as number })) });
  return <XYPlot points={[]} lines={[line("p5", "5th", "var(--text-4)", true), line("p25", "25th", "var(--text-3)"), line("p50", "Median", "var(--accent)"), line("p75", "75th", "var(--text-3)"), line("p95", "95th", "var(--text-4)", true)]}
    xLabel="Trade" yLabel="Equity" height={260} formatX={(v) => String(Math.round(v))} formatY={usd} />;
}

export function Ruin({ rows }: ViewProps) {
  return <Bars bars={rows.map((r) => ({ label: `> ${pct(r.drawdown, 0)}`, value: r.probability as number }))} format={(v) => pct(v, 0)} signed={false} yLabel="Chance" height={200} />;
}

export function Streaks({ rows, result }: ViewProps) {
  const p = metaOf(result).paths;
  if (!rows.length) return <Skipped reason={p.reason ?? "fewer than 10 closed trades"} />;
  return <Bars bars={rows.map((r) => ({ label: String(r.length), value: r.share as number, color: r.length === p.streak_actual ? "var(--accent)" : undefined }))} format={(v) => pct(v, 0)} signed={false} yLabel="Share of paths" height={200} />;
}

/** The most-traded names, each opening Chart with this run's trades on price (C-4). */
export function OnChart({ rows, result }: ViewProps) {
  const { run: runMeta, strategy } = result.meta as { run?: { id: string }; strategy?: { id?: string } };
  const run = runMeta?.id;
  const top = [...rows].sort((a, b) => (b.trades as number) - (a.trades as number)).slice(0, 12);
  if (!run || !top.length) return <Skipped reason="no trades to show" />;
  return (
    <div className="ch-chips">
      {top.map((r) => <Link key={String(r.symbol)} className="chip" href={`/studio/build${strategy?.id ? `/${strategy.id}` : ""}?ui=dev&symbol=${encodeURIComponent(String(r.symbol))}`}>{String(r.symbol)} · {String(r.trades)}</Link>)}
    </div>
  );
}

const REGIME_COLORS: Record<string, string> = { "trend up, low vol": "var(--up)", "trend up, high vol": "var(--s3)", "trend down, low vol": "var(--warn)", "trend down, high vol": "var(--down)", "warm-up": "var(--line-2)" };

/** Equity against the benchmark with the market regime of each day as a strip underneath. */
export function Timeline({ rows, result }: ViewProps) {
  const m = metaOf(result);
  if (!rows.some((r) => r.regime)) return <Skipped reason="no benchmark to label regimes" />;
  return <TimeSeries data={rows} series={[{ key: "strategy", label: "Strategy", color: "var(--accent)", width: 2 }, ...(m.benchmark ? [{ key: "benchmark", label: m.benchmark, color: "var(--text-3)" }] : [])]}
    ribbon={{ key: "regime", label: "Regime", colors: REGIME_COLORS }} height={280} format={usd} />;
}

/** Daily results split by market conditions known the night before. */
export function Conditions({ rows }: ViewProps) {
  if (!rows.length) return <Skipped reason="no market series for this period" />;
  return (
    <table className="vt-table">
      <thead><tr><th>When</th><th className="num">Days</th><th className="num">Annual return</th><th className="num">Sharpe</th><th className="num">Up days</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={String(r.condition)}>
          <td>{String(r.condition)}</td><td className="num">{pct(r.share_of_days, 0)}</td>
          <td className={`num ${isNum(r.annual_return) && r.annual_return < 0 ? "st-down" : ""}`}>{pct(r.annual_return, 1)}</td>
          <td className={`num ${isNum(r.sharpe) && r.sharpe < 0 ? "st-down" : ""}`}>{isNum(r.sharpe) ? r.sharpe.toFixed(2) : "—"}</td><td className="num">{pct(r.hit_rate, 0)}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

/** Prop-style rules from every monthly start date: how often the target is reached before a rule breaks. */
export function RuleCheck({ rows, result }: ViewProps) {
  const c = metaOf(result).rule_check;
  if (!c?.starts) return <Skipped reason="the period is too short for a start-date sweep" />;
  const parts: [string, number, string][] = [["Passed", c.pass, "var(--up)"], ["Daily loss", c.fail_daily_loss, "var(--down)"], ["Drawdown", c.fail_drawdown, "var(--warn)"], ["Still open", c.open, "var(--line-2)"]];
  const R = 46, C = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="bt-rule">
      <svg viewBox="0 0 120 120" width={140} height={140} role="img" aria-label={`Passed from ${c.pass} of ${c.starts} start dates`}>
        {parts.map(([k, v, col]) => { const len = (v / c.starts) * C, el = <circle key={k} cx={60} cy={60} r={R} fill="none" stroke={col} strokeWidth={12} strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc} transform="rotate(-90 60 60)" />; acc += len; return el; })}
        <text x={60} y={58} textAnchor="middle" className="bt-rule-n">{pct(c.pass_share ?? 0, 0)}</text>
        <text x={60} y={74} textAnchor="middle" className="bt-rule-l">passed</text>
      </svg>
      <div className="bt-rule-t">
        <p className="bd-meta" style={{ margin: 0 }}>Target {pct(c.target, 0)} after {c.min_days}+ days · daily loss {pct(c.daily_loss, 0)} · drawdown {pct(c.max_dd, 0)} · {c.starts} starts</p>
        {parts.map(([k, v, col]) => <div key={k} className="bt-row"><i className="bt-dot" style={{ background: col }} /><span>{k}</span><b className="num">{v}</b></div>)}
        {isNum(c.median_days_to_pass) ? <div className="bt-row"><i className="bt-dot" /><span>Median days to pass</span><b className="num">{c.median_days_to_pass.toFixed(0)}</b></div> : null}
        <DataTable rows={rows} opts={{ maxHeight: 200 }} />
      </div>
    </div>
  );
}

/** Where the profit sat: names sized by P&L, and how many were held over time. */
export function Holdings({ rows, result }: ViewProps) {
  const held = (result.tables.holdings ?? []) as { date: string; names: number }[];
  const items = rows.filter((r) => isNum(r.pnl) && r.pnl !== 0).slice(0, 200).map((r) => ({ label: String(r.symbol), group: String(r.symbol), size: Math.abs(r.pnl as number), colorValue: r.pnl as number }));
  if (!items.length) return <Skipped reason="no closed trades" />;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <Treemap title="Profit and loss by name" sizeLabel="P&L" colorLabel="P&L" items={items} format={usd} colorFormat={usd} />
      <TimeSeries data={held} series={[{ key: "names", label: "Names held", color: "var(--accent)", kind: "step" }]} height={160} format={(v) => v.toFixed(0)} />
    </div>
  );
}
