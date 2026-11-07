"use client";

import { useState, type ReactNode } from "react";

export type RankItem = { label: string; value: number; note?: ReactNode; delta?: number; /** Recent history, oldest first; drawn as a small trend beside the value. */ spark?: number[] };

const SPARK_W = 56;
const SPARK_H = 14;

/** Inline trend line for a ranked row. Purely decorative: the exact value sits beside it. */
export function Spark({ values }: { values: number[] }) {
  const finite = values.filter(Number.isFinite);
  if (finite.length < 2) return null;
  const lo = Math.min(...finite);
  const hi = Math.max(...finite);
  const span = hi - lo || 1;
  const step = SPARK_W / (values.length - 1);
  const points = values.map((v, i) => `${i * step},${SPARK_H - ((v - lo) / span) * (SPARK_H - 2) - 1}`).join(" ");
  const rising = values[values.length - 1] >= values[0];
  return <svg className="rank-spark" width={SPARK_W} height={SPARK_H} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} aria-hidden focusable="false">
    <polyline points={points} fill="none" stroke={rising ? "var(--up)" : "var(--down)"} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
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
        <span className="num rank-value">{r.spark && r.spark.length > 1 ? <Spark values={r.spark} /> : null}{format(r.value)}{r.delta !== undefined && Number.isFinite(r.delta) ? <small>Δ {r.delta > 0 ? "+" : ""}{format(r.delta)}</small> : null}</span>
      </li>;
    })}</ol>
    {sorted.length > top ? <button className="btn sm ghost" aria-expanded={all} onClick={() => setAll(!all)}>{all ? `Show top ${top}` : `Show all ${sorted.length}`}</button> : null}
  </div>;
}
