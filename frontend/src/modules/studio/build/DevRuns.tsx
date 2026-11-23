"use client";

import { Pin, PinOff } from "lucide-react";
import { useState } from "react";
import { SERIES } from "@/charts/core";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import type { QuickRun } from "./DevIDE";

export type RunEntry = { id: string; label: string; at: string; pinned: boolean; run: QuickRun; settings?: Record<string, unknown> };

/** What a run is searchable by: name, level, time, its settings (symbols, dates, costs) and the symbols it traded. */
const haystack = (r: RunEntry) => [r.label, r.run.level, r.at, JSON.stringify(r.settings ?? {}), [...new Set((r.run.result?.tables?.trades ?? []).map((t) => String(t.symbol ?? "")))].slice(0, 50).join(" ")].join(" ").toLowerCase();

const METRICS: [string, (r: QuickRun) => number | null | undefined, (v: number) => string][] = [
  ["Return", (r) => r.result?.meta?.total_return, (v) => `${(v * 100).toFixed(1)}%`],
  ["Sharpe", (r) => r.result?.meta?.metrics?.sharpe, (v) => v.toFixed(2)],
  ["Max drawdown", (r) => r.result?.meta?.metrics?.max_drawdown, (v) => `${(v * 100).toFixed(1)}%`],
  ["Trades", (r) => r.result?.meta?.metrics?.trades, (v) => String(v)],
];

/** Finished runs of this session: pin the ones to keep, tick two to diff their metrics and overlay their equity. */
export function DevRuns({ runs: all, onPin, onRename }: { runs: RunEntry[]; onPin: (id: string) => void; onRename: (id: string, label: string) => void }) {
  const [sel, setSel] = useState<string[]>([]);
  const [q, setQ] = useState(""), [naming, setNaming] = useState<string | null>(null);
  const runs = q.trim() ? all.filter((r) => q.toLowerCase().split(/\s+/).every((w) => haystack(r).includes(w))) : all;
  const pair = sel.map((id) => runs.find((r) => r.id === id)).filter((r): r is RunEntry => !!r);
  const [ra, rb] = pair;
  const curve = (() => {
    if (!ra || !rb) return [];
    const [a, b] = [ra, rb].map((r) => new Map((r.run.result?.charts?.equity_curve ?? []).map((p) => [p.date, p.strategy])));
    const base = (m: Map<string, number>) => m.values().next().value ?? 1;
    const [ba, bb] = [base(a), base(b)];
    return [...new Set([...a.keys(), ...b.keys()])].toSorted().map((date) => ({ date, a: a.has(date) ? a.get(date)! / ba : null, b: b.has(date) ? b.get(date)! / bb : null }));
  })();
  if (!all.length) return <p className="dv-empty">Finished runs appear here</p>;
  const tick = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  return (
    <div className="dv-tear">
      <input className="input sm" type="search" aria-label="Search runs" placeholder="Search runs: name, symbol, date, level" value={q} onChange={(e) => setQ(e.target.value)} />
      {!runs.length ? <p className="dv-empty">No run matches</p> : null}
      <div className="dv-runs" role="list">
        {runs.map((r) => (
          <div key={r.id} role="listitem" className="dv-run" data-on={sel.includes(r.id) || undefined}>
            <input type="checkbox" aria-label={`Compare ${r.label}`} checked={sel.includes(r.id)} onChange={() => tick(r.id)} />
            {naming === r.id
              ? <input className="input sm dv-runname" aria-label="Run name" autoFocus defaultValue={r.label} onBlur={(e) => { const n = e.currentTarget.value.trim(); if (n) onRename(r.id, n); setNaming(null); }} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") setNaming(null); }} />
              : <button className="dv-runname" onDoubleClick={() => setNaming(r.id)} title="Double click to rename" onClick={() => tick(r.id)}>{r.label}</button>}
            <span>{r.at}</span>
            <span data-num>{METRICS[0][2](METRICS[0][1](r.run) ?? 0)}</span>
            <button className="icon-btn" aria-pressed={r.pinned} aria-label={r.pinned ? "Unpin" : "Pin"} title={r.pinned ? "Unpin" : "Pin"} onClick={() => onPin(r.id)}>{r.pinned ? <PinOff size={13} /> : <Pin size={13} />}</button>
          </div>
        ))}
      </div>
      {pair.length === 2 ? <>
        <DataTable rows={METRICS.map(([name, get, f]) => { const [x, y] = [get(pair[0].run), get(pair[1].run)]; return { metric: name, [pair[0].label]: x == null ? "—" : f(x), [pair[1].label]: y == null ? "—" : f(y), change: x == null || y == null ? "—" : f(y - x), percent: x == null || y == null || !x ? "—" : `${(((y - x) / Math.abs(x)) * 100).toFixed(0)}%` }; })} />
        <div className="dv-plot"><b>Equity, rebased to 1</b><TimeSeries data={curve} height={200} series={[{ key: "a", label: pair[0].label, color: SERIES[0] }, { key: "b", label: pair[1].label, color: SERIES[1] }]} /></div>
      </> : <p className="dv-empty">Tick two runs to compare</p>}
    </div>
  );
}
