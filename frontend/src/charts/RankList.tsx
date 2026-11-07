"use client";

import { useState, type ReactNode } from "react";

export type RankItem = { label: string; value: number; note?: ReactNode; delta?: number };

const SPARK_W = 56;
const SPARK_H = 14;

/**
 * Inline trend line. Purely decorative: the exact value sits beside it.
 * Non-finite samples are dropped rather than breaking the polyline.
 */
export function Spark({ values, width = SPARK_W, height = SPARK_H, color, dot = false, className = "rank-spark" }: {
  values: number[]; width?: number; height?: number; color?: string; dot?: boolean; className?: string;
}) {
  const finite = values.filter(Number.isFinite);
  if (finite.length < 2) return null;
  const lo = Math.min(...finite);
  const hi = Math.max(...finite);
  const span = hi - lo || 1;
  const x = (i: number) => (i / (finite.length - 1)) * width;
  const y = (v: number) => height - 2 - ((v - lo) / span) * (height - 4);
  const points = finite.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const rising = finite[finite.length - 1] >= finite[0];
  const stroke = color ?? (rising ? "var(--up)" : "var(--down)");
  return <svg className={className} width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden focusable="false">
    <polyline points={points} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
    {dot ? <circle cx={x(finite.length - 1)} cy={y(finite[finite.length - 1])} r={2.2} fill={stroke} /> : null}
  </svg>;
}
/** Ranked contributions with a bounded initial view and exact, selectable values. */
export function RankList({ items, format, top = 12, title }: { items: RankItem[]; format: (value: number) => string; top?: number; title: string }) {
  const [all, setAll] = useState(false);
  const sorted = items.filter((r) => Number.isFinite(r.value)).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const max = Math.max(...sorted.map((r) => Math.abs(r.value)), 1e-12);
  if (!sorted.length) return <p className="chart-empty">No finite values to rank.</p>;
  return <div className="rank-list">
    <ol aria-label={title}>{(all ? sorted : sorted.slice(0, top)).map((r, i) => {
      const parts = r.label.split("/");
      const leaf = parts.pop();
      return <li key={`${r.label}-${i}`}>
        <span className="num rank-position">{i + 1}</span>
        <span className="rank-name"><span className="num">{parts.length ? `${parts.join("/")}/` : ""}<b>{leaf}</b></span>{r.note ? <small>{r.note}</small> : null}<i className="rank-track" aria-hidden><i style={{ width: `${Math.abs(r.value) / max * 100}%`, background: r.value < 0 ? "var(--down)" : "var(--accent)" }} /></i></span>
        <span className="num rank-value">{format(r.value)}{r.delta !== undefined && Number.isFinite(r.delta) ? <small>Δ {r.delta > 0 ? "+" : ""}{format(r.delta)}</small> : null}</span>
      </li>;
    })}</ol>
    {sorted.length > top ? <button className="btn sm ghost" aria-expanded={all} onClick={() => setAll(!all)}>{all ? `Show top ${top}` : `Show all ${sorted.length}`}</button> : null}
  </div>;
}
