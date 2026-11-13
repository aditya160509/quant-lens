"use client";

import { useState } from "react";
import { isNum, pct } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import "./backtest.css";

const Empty = () => <p className="chart-empty">Nothing to show.</p>;

/** Drawdown from the running peak across the full width, with a hover readout. */
export function DrawdownStrip({ rows }: { rows: Row[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = rows.filter((r) => isNum(r.drawdown)) as (Row & { drawdown: number })[];
  if (pts.length < 2) return <Empty />;
  const min = Math.min(-0.01, ...pts.map((r) => r.drawdown));
  const worst = pts.reduce((a, r) => (r.drawdown < a.drawdown ? r : a));
  const x = (i: number) => (i / (pts.length - 1)) * 100;
  const path = pts.map((r, i) => `${x(i)},${(r.drawdown / min) * 40}`).join(" L");
  const h = hover === null ? null : pts[hover];
  const grid = [0.25, 0.5, 0.75].map((f) => f * min);
  return (
    <div className="ts-under">
      <div className="dd-plot" onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(Math.max(0, Math.min(pts.length - 1, Math.round(((e.clientX - r.left) / r.width) * (pts.length - 1))))); }} onPointerLeave={() => setHover(null)}>
        <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={`Drawdown, worst ${pct(worst.drawdown, 1)}`}>
          {grid.map((g) => <line key={g} x1={0} x2={100} y1={(g / min) * 40} y2={(g / min) * 40} stroke="var(--grid)" strokeDasharray="1 1" vectorEffect="non-scaling-stroke" />)}
          <path d={`M0,0 L${path} L100,0 Z`} fill="color-mix(in oklch, var(--down) 22%, transparent)" stroke="var(--down)" strokeWidth={1.25} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          {h && hover !== null ? <line x1={x(hover)} x2={x(hover)} y1={0} y2={40} stroke="var(--line-3)" vectorEffect="non-scaling-stroke" /> : null}
        </svg>
        <div className="dd-y num">{grid.map((g) => <span key={g} style={{ top: `${(g / min) * 100}%` }}>{pct(g, 0)}</span>)}</div>
        {h && hover !== null ? <div className="dd-tip num" style={{ left: `${x(hover)}%` }}><span>{String(h.date).slice(0, 10)}</span><b>{pct(h.drawdown, 1)}</b></div> : null}
      </div>
      <div className="ts-g-axis num"><span>{String(pts[0].date).slice(0, 10)}</span><span>{String(pts[pts.length - 1].date).slice(0, 10)}</span></div>
      <div className="ts-legend"><span>Worst <b className="num" style={{ color: "var(--down)" }}>{pct(worst.drawdown, 1)}</b> on {String(worst.date).slice(0, 10)}</span><span>Now <b className="num">{pct(pts[pts.length - 1].drawdown, 1)}</b></span></div>
    </div>
  );
}


/** Every holding as a bar from entry to exit (open ones run to the end), coloured by its net result. */
export function HoldingsTimeline({ rows, onSelect }: { rows: Row[]; onSelect?: (ticker: string) => void }) {
  const eps = rows.filter((r) => r.entry_date);
  if (!eps.length) return <Empty />;
  const t = (d: unknown) => new Date(String(d)).getTime();
  // shortcut: open holdings end at the last date seen in the log, not the curve end; pass the curve end if bars look short.
  const start = Math.min(...eps.map((r) => t(r.entry_date))), end = Math.max(...eps.map((r) => t(r.exit_date ?? r.last_mark_date ?? r.entry_date)));
  const span = end - start || 1;
  const names = [...new Set(eps.map((r) => String(r.ticker)))].slice(0, 60);
  return (
    <div className="ts-gantt">
      {names.map((n) => (
        <div key={n} className="ts-g-row">
          <button type="button" className="tk-link" onClick={() => onSelect?.(n)}>{n}</button>
          <span className="ts-g-track">
            {eps.filter((r) => String(r.ticker) === n).map((r, i) => {
              const a = (t(r.entry_date) - start) / span, b = ((r.exit_date ? t(r.exit_date) : end) - start) / span;
              const v = isNum(r.net_pnl_contribution) ? r.net_pnl_contribution : isNum(r.price_return) ? r.price_return : 0;
              return <i key={i} className={v >= 0 ? "up" : "down"} data-open={!r.exit_date} style={{ left: `${a * 100}%`, width: `${Math.max(0.4, (b - a) * 100)}%` }} title={`${String(r.entry_date).slice(0, 10)} → ${r.exit_date ? String(r.exit_date).slice(0, 10) : "open"} · ${pct(v, 2)}`} />;
            })}
          </span>
        </div>
      ))}
      <div className="ts-g-axis num"><span>{new Date(start).toISOString().slice(0, 10)}</span><span>{new Date(end).toISOString().slice(0, 10)}</span></div>
    </div>
  );
}
