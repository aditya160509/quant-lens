"use client";

import { useMemo, type CSSProperties } from "react";
import { Empty } from "@/kit/DataTable";
import { isNum, pct } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./tearsheet.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Last equity value of each month, by key "YYYY-MM". */
function monthEnds(rows: Row[], key: "strategy" | "benchmark") {
  const out = new Map<string, number>();
  rows.forEach((r) => { const v = r[key]; if (isNum(v) && typeof r.date === "string") out.set(r.date.slice(0, 7), v); });
  return out;
}

function monthlyReturns(rows: Row[], key: "strategy" | "benchmark") {
  const ends = [...monthEnds(rows, key)];
  const first = rows.find((r) => isNum(r[key]))?.[key] as number | undefined;
  return new Map(ends.map(([m, v], i) => [m, v / (i ? ends[i - 1][1] : first ?? v) - 1]));
}

const tone = (v: number, lim: number): CSSProperties => {
  const a = Math.min(1, Math.abs(v) / lim) * 55;
  return { background: `color-mix(in oklch, ${v >= 0 ? "var(--up)" : "var(--down)"} ${a.toFixed(0)}%, transparent)` };
};

/** Month by year grid of strategy returns, with the year total and the benchmark year beside it. */
export function MonthlyHeatmap({ rows }: ViewProps) {
  const { years, grid, lim, yearRet, benchYear } = useMemo(() => {
    const m = monthlyReturns(rows, "strategy");
    const b = monthlyReturns(rows, "benchmark");
    const years = [...new Set([...m.keys()].map((k) => k.slice(0, 4)))].sort().reverse();
    const comp = (src: Map<string, number>, y: string) => { const v = [...src].filter(([k]) => k.startsWith(y)).map(([, r]) => r); return v.length ? v.reduce((a, r) => a * (1 + r), 1) - 1 : null; };
    const vals = [...m.values()].map(Math.abs).sort((a, c) => a - c);
    return { years, grid: m, lim: vals[Math.floor(vals.length * 0.9)] || 0.05, yearRet: (y: string) => comp(m, y), benchYear: (y: string) => comp(b, y) };
  }, [rows]);
  if (!years.length) return <Empty />;
  return (
    <div className="ts-wrap">
      <table className="ts-heat">
        <thead><tr><th />{MONTHS.map((m) => <th key={m}>{m}</th>)}<th className="yr">Year</th><th className="yr">SPY</th></tr></thead>
        <tbody>
          {years.map((y) => {
            const yr = yearRet(y), by = benchYear(y);
            return (
              <tr key={y}>
                <th>{y}</th>
                {MONTHS.map((_, i) => { const v = grid.get(`${y}-${String(i + 1).padStart(2, "0")}`); return <td key={i} className="num" style={isNum(v) ? tone(v, lim) : undefined}>{isNum(v) ? (v * 100).toFixed(1) : ""}</td>; })}
                <td className="num yr" style={isNum(yr) ? tone(yr, lim * 3) : undefined}>{isNum(yr) ? pct(yr, 1) : ""}</td>
                <td className="num yr bench" data-beat={isNum(yr) && isNum(by) ? yr > by : undefined}>{isNum(by) ? pct(by, 1) : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Daily return distribution of the strategy against the benchmark, with the median and 5% tail marked. */
export function ReturnHistogram({ rows }: ViewProps) {
  const data = useMemo(() => {
    const daily = (k: "strategy" | "benchmark") => rows.flatMap((r, i) => { const a = rows[i - 1]?.[k], b = r[k]; return i && isNum(a) && isNum(b) && a ? [b / a - 1] : []; });
    const s = daily("strategy"), b = daily("benchmark");
    if (s.length < 20) return null;
    const sorted = [...s].sort((x, y) => x - y);
    const lo = sorted[Math.floor(sorted.length * 0.005)], hi = sorted[Math.ceil(sorted.length * 0.995) - 1];
    const n = 41, w = (hi - lo) / n || 1e-4;
    const bin = (v: number[]) => { const c = Array(n).fill(0); v.forEach((x) => { c[Math.max(0, Math.min(n - 1, Math.floor((x - lo) / w)))]++; }); return c.map((k) => k / v.length); };
    return { s: bin(s), b: bin(b), lo, hi, w, median: sorted[sorted.length >> 1], var5: sorted[Math.floor(sorted.length * 0.05)] };
  }, [rows]);
  if (!data) return <Empty />;
  const top = Math.max(...data.s, ...data.b);
  const W = 100 / data.s.length;
  const xp = (v: number) => ((v - data.lo) / (data.hi - data.lo)) * 100;
  return (
    <div className="ts-hist">
      <svg viewBox="0 0 100 50" preserveAspectRatio="none" role="img" aria-label="Daily return distribution">
        {data.s.map((v, i) => <rect key={i} x={i * W + 0.1} width={W - 0.2} y={50 - (v / top) * 48} height={(v / top) * 48} fill={data.lo + (i + 0.5) * data.w < 0 ? "var(--down)" : "var(--up)"} fillOpacity={0.7} />)}
        <polyline fill="none" stroke="var(--text-3)" strokeWidth={0.4} vectorEffect="non-scaling-stroke" points={data.b.map((v, i) => `${(i + 0.5) * W},${50 - (v / top) * 48}`).join(" ")} />
        <line x1={xp(data.var5)} x2={xp(data.var5)} y1={0} y2={50} stroke="var(--warn)" strokeDasharray="1 1" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="ts-legend">
        <span><i className="sw strat" />Strategy</span><span><i className="sw bench" />SPY</span>
        <span>Median <b className="num">{pct(data.median, 2)}</b></span><span>5% worst day <b className="num" style={{ color: "var(--warn)" }}>{pct(data.var5, 2)}</b></span>
      </div>
    </div>
  );
}

/** Drawdown from the running peak, as a filled strip under the equity curve. */
export function Underwater({ rows }: ViewProps) {
  const pts = rows.filter((r) => isNum(r.drawdown)) as (Row & { drawdown: number })[];
  if (pts.length < 2) return <Empty />;
  const min = Math.min(-0.01, ...pts.map((r) => r.drawdown));
  const worst = pts.reduce((a, r) => (r.drawdown < a.drawdown ? r : a));
  const path = pts.map((r, i) => `${(i / (pts.length - 1)) * 100},${(r.drawdown / min) * 40}`).join(" L");
  return (
    <div className="ts-under">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={`Drawdown, worst ${pct(worst.drawdown, 1)}`}>
        <path d={`M0,0 L${path} L100,0 Z`} fill="color-mix(in oklch, var(--down) 30%, transparent)" stroke="var(--down)" strokeWidth={0.6} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="ts-legend"><span>Worst <b className="num" style={{ color: "var(--down)" }}>{pct(worst.drawdown, 1)}</b> on {String(worst.date).slice(0, 10)}</span><span>Now <b className="num">{pct(pts[pts.length - 1].drawdown, 1)}</b></span></div>
    </div>
  );
}
