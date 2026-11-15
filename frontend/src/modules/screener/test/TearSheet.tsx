"use client";

import { useMemo } from "react";
import { CalendarHeatmap } from "@/charts/CalendarHeatmap";
import { Distribution } from "@/charts/Distribution";
import { Diverging } from "@/charts/Diverging";
import { DrawdownStrip, HoldingsTimeline } from "@/charts/Backtest";
import { Heatmap } from "@/charts/Heatmap";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, pct } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./tearsheet.css";


/** Last equity value of each month, by key "YYYY-MM". */
function monthEnds(rows: Row[], key: "strategy") {
  const out = new Map<string, number>();
  rows.forEach((r) => { const v = r[key]; if (isNum(v) && typeof r.date === "string") out.set(r.date.slice(0, 7), v); });
  return out;
}

function monthlyReturns(rows: Row[], key: "strategy") {
  const ends = [...monthEnds(rows, key)];
  const first = rows.find((r) => isNum(r[key]))?.[key] as number | undefined;
  return new Map(ends.map(([m, v], i) => [m, v / (i ? ends[i - 1][1] : first ?? v) - 1]));
}

/** Monthly strategy returns on the shared calendar heatmap. */
export function MonthlyHeatmap({ rows }: ViewProps) {
  const data = useMemo(() => [...monthlyReturns(rows, "strategy")].map(([m, value]) => ({ date: `${m}-15`, value })), [rows]);
  return <CalendarHeatmap title="Monthly returns" data={data} aggregate="sum" format={(v) => pct(v, 1)} />;
}

/** Daily strategy returns on the shared distribution, worst 5% day marked. */
export function ReturnHistogram({ rows }: ViewProps) {
  const daily = useMemo(() => rows.flatMap((r, i) => { const a = rows[i - 1]?.strategy, b = r.strategy; return i && isNum(a) && isNum(b) && a ? [b / a - 1] : []; }), [rows]);
  if (daily.length < 20) return <Empty />;
  const var5 = [...daily].sort((x, y) => x - y)[Math.floor(daily.length * 0.05)];
  return <Distribution values={daily} observed={var5} tail="left" xLabel="Daily return" observedLabel="5% worst day" format={(v) => pct(v, 2)} />;
}

/** Net contribution per name on the shared diverging bars, best and worst 12; a bar opens the drawer. */
export function AttributionBars({ rows }: ViewProps) {
  const vals = rows.filter((r) => isNum(r.net_pnl_contribution)).map((r) => ({ label: String(r.ticker), value: r.net_pnl_contribution as number })).sort((a, b) => b.value - a.value);
  if (!vals.length) return <Empty />;
  return <Diverging rows={vals.length > 24 ? [...vals.slice(0, 12), ...vals.slice(-12)] : vals} format={(v) => pct(v, 2)} labelWidth={72} onSelect={(r) => openQuickLook(r.label)} />;
}

export function Underwater({ rows }: ViewProps) { return <DrawdownStrip rows={rows} />; }
export function HoldingsGantt({ rows }: ViewProps) { return <HoldingsTimeline rows={rows} onSelect={openQuickLook} />; }

type Pt = { t: number; s: number; b: number | null };

/** Dated equity points from the curve rows: strategy and, when present, the benchmark. */
function points(rows: Row[]): Pt[] {
  return rows.flatMap((r) => (typeof r.date === "string" && isNum(r.strategy) ? [{ t: Date.parse(r.date), s: r.strategy, b: isNum(r.benchmark) ? r.benchmark : null }] : []));
}

const YEAR = 365.25 * 86_400_000;

function statsOf(p: Pt[], key: "s" | "b") {
  const v = p.map((x) => x[key]).filter(isNum);
  if (v.length < 20) return null;
  const rets = v.slice(1).map((x, i) => x / v[i] - 1);
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, rets.length - 1));
  let peak = v[0], dd = 0;
  v.forEach((x) => { peak = Math.max(peak, x); dd = Math.min(dd, x / peak - 1); });
  const years = (p.at(-1)!.t - p[0].t) / YEAR;
  return { cagr: years > 0 ? (v.at(-1)! / v[0]) ** (1 / years) - 1 : null, vol: sd * Math.sqrt(252), sharpe: sd ? (mean / sd) * Math.sqrt(252) : null, dd };
}

/** Return, volatility, Sharpe (no risk-free) and worst drawdown over 1, 3, 5 years and the whole run, against the benchmark. */
export function HorizonTable({ rows }: ViewProps) {
  const p = useMemo(() => points(rows), [rows]);
  if (p.length < 20) return <Empty />;
  const end = p.at(-1)!.t;
  const spans = [["1Y", 1], ["3Y", 3], ["5Y", 5], ["All", 0]] as const;
  const lines = spans.filter(([, y]) => !y || end - p[0].t >= y * YEAR * 0.98).map(([l, y]) => {
    const cut = y ? p.filter((x) => x.t >= end - y * YEAR) : p;
    return { l, s: statsOf(cut, "s"), b: statsOf(cut, "b") };
  });
  const cell = (v: number | null | undefined, f: (n: number) => string) => (isNum(v) ? f(v) : "–");
  return (
    <table className="tbl ts-h">
      <thead><tr><th>Span</th><th className="r">CAGR</th><th className="r">Benchmark</th><th className="r">Volatility</th><th className="r">Sharpe</th><th className="r">Worst drawdown</th></tr></thead>
      <tbody>{lines.map(({ l, s, b }) => (
        <tr key={l}><td>{l}</td><td className="r num">{cell(s?.cagr, (v) => pct(v, 1))}</td><td className="r num">{cell(b?.cagr, (v) => pct(v, 1))}</td><td className="r num">{cell(s?.vol, (v) => pct(v, 1))}</td><td className="r num">{cell(s?.sharpe, (v) => v.toFixed(2))}</td><td className="r num">{cell(s?.dd, (v) => pct(v, 1))}</td></tr>
      ))}</tbody>
    </table>
  );
}

type Episode = { start: number; trough: number; end: number | null; depth: number };

/** The five deepest peak-to-trough falls: start, trough, recovery (or still open) and depth. */
function episodes(p: Pt[]): Episode[] {
  const out: Episode[] = [];
  let peak = p[0], low: Pt | null = null;
  p.forEach((x) => {
    if (x.s >= (peak?.s ?? 0)) {
      if (low && low.s < peak.s) out.push({ start: peak.t, trough: low.t, end: x.t, depth: low.s / peak.s - 1 });
      peak = x; low = null;
    } else if (!low || x.s < low.s) low = x;
  });
  if (low && peak && low.s < peak.s) out.push({ start: peak.t, trough: low.t, end: null, depth: low.s / peak.s - 1 });
  return out.sort((a, b) => a.depth - b.depth).slice(0, 5);
}

/** Longest and current run of negative values. */
function streak(r: number[]) { let best = 0, cur = 0; r.forEach((x) => { cur = x < 0 ? cur + 1 : 0; best = Math.max(best, cur); }); return { best, cur }; }

/** One drawdown story: the underwater chart with the five worst falls marked and numbered, then the falls and the losing streaks. */
export function DrawdownStory({ rows }: ViewProps) {
  const { eps, day, week } = useMemo(() => {
    const p = points(rows);
    const weekEnd = new Map<string, number>();
    p.forEach((x) => { const d = new Date(x.t); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7)); weekEnd.set(d.toISOString().slice(0, 10), x.s); });
    const w = [...weekEnd.values()];
    return { eps: episodes(p), day: streak(p.slice(1).map((x, i) => x.s / p[i].s - 1)), week: streak(w.slice(1).map((x, i) => x / w[i] - 1)) };
  }, [rows]);
  const d = (t: number) => new Date(t).toISOString().slice(0, 10);
  const days = (a: number, b: number) => Math.round((b - a) / 86_400_000);
  return (
    <div className="ts-story">
      <DrawdownStrip rows={rows} marks={eps.map((e, i) => ({ from: d(e.start), to: e.end ? d(e.end) : null, label: String(i + 1) }))} />
      {eps.length ? (
        <table className="tbl ts-h">
          <thead><tr><th>#</th><th>Peak</th><th>Trough</th><th>Recovered</th><th className="r">Depth</th><th className="r">Days</th></tr></thead>
          <tbody>{eps.map((e, i) => <tr key={e.start}><td className="num">{i + 1}</td><td className="num">{d(e.start)}</td><td className="num">{d(e.trough)}</td><td className="num">{e.end ? d(e.end) : "Open"}</td><td className="r num" style={{ color: "var(--down)" }}>{pct(e.depth, 1)}</td><td className="r num">{days(e.start, e.end ?? Date.now())}</td></tr>)}</tbody>
        </table>
      ) : null}
      <div className="ts-streaks">
        {([["Losing days in a row", day], ["Losing weeks in a row", week]] as const).map(([l, v]) => (
          <div key={l}><span>{l}</span><b className="num">{v.best}</b><small className="num">now {v.cur}</small></div>
        ))}
      </div>
    </div>
  );
}

/** Weekly strategy returns, one row per year, one cell per ISO week. */
export function WeeklyHeatmap({ rows }: ViewProps) {
  const grid = useMemo(() => {
    const p = points(rows);
    const last = new Map<string, number>();
    p.forEach((x) => {
      const d = new Date(x.t);
      const th = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 3 - ((d.getUTCDay() + 6) % 7)));
      // ISO week: the week's Thursday decides the year; count weeks from 1 January of that year.
      const wk = 1 + Math.floor((th.getTime() - Date.UTC(th.getUTCFullYear(), 0, 1)) / (7 * 86_400_000));
      last.set(`${th.getUTCFullYear()}-${wk}`, x.s);
    });
    const keys = [...last.keys()];
    const ret = new Map(keys.slice(1).map((k, i) => [k, last.get(k)! / last.get(keys[i])! - 1]));
    const years = [...new Set(keys.map((k) => k.split("-")[0]))];
    return { years, values: years.map((y) => Array.from({ length: 53 }, (_, w) => ret.get(`${y}-${w + 1}`) ?? null)) };
  }, [rows]);
  if (!grid.years.length) return <Empty />;
  return <Heatmap rows={grid.years} cols={Array.from({ length: 53 }, (_, w) => String(w + 1))} values={grid.values} centered format={(v) => pct(v, 1)} rowTitle="Year" colTitle="Week" />;
}

/** Calendar-year return of the strategy and the benchmark, and the difference. */
export function YearlyVsBenchmark({ rows }: ViewProps) {
  const g = useMemo(() => {
    const p = points(rows);
    const ends = new Map<string, Pt>();
    p.forEach((x) => ends.set(new Date(x.t).getUTCFullYear().toString(), x));
    const ys = [...ends.keys()];
    const first = p[0];
    return ys.map((y, i) => {
      const a = i ? ends.get(ys[i - 1])! : first, z = ends.get(y)!;
      const s = z.s / a.s - 1, b = isNum(z.b) && isNum(a.b) ? z.b / a.b - 1 : null;
      return { y, row: [s, b, b === null ? null : s - b] };
    });
  }, [rows]);
  if (!g.length) return <Empty />;
  return <Heatmap rows={g.map((x) => x.y)} cols={["Strategy", "Benchmark", "Difference"]} values={g.map((x) => x.row)} centered format={(v) => pct(v, 1)} rowTitle="Year" />;
}
