"use client";

import { useState, type ReactNode } from "react";

export type RankItem = { label: string; value: number; note?: ReactNode; delta?: number };
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
