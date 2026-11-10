"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/modules/research/api";
import { fmtKey } from "@/modules/research/format";
import { send } from "../api";

export type Dist = { lo?: number; hi?: number; bins?: number[]; kept?: number[]; known: number; total: number; median?: number; min?: number; max?: number };
export type Preview = { universe: number; passed: number; stages: { stage: string; key?: string | null; remaining: number; removed: number }[]; dist: Record<string, Dist>; mix?: Record<string, Record<string, number>> };

/** Filter prefix ("pe") to its column ("trailing_pe"), from the server's own filter list. */
export function useFilterColumns() {
  const q = useQuery({ queryKey: ["screener", "filter-keys"], queryFn: () => get<Record<string, [string, string]>>("/filters/keys"), staleTime: Infinity });
  return useMemo(() => Object.fromEntries(Object.entries(q.data ?? {}).map(([col, [lo]]) => [lo.replace(/_min$/, ""), col])), [q.data]);
}

/** Live pass counts and distributions for the form as it is edited, debounced, from a cached panel. */
export function useFilterPreview(payload: Record<string, unknown>, fields: string[]) {
  const body = JSON.stringify({ payload, fields: [...new Set(fields)].sort() });
  const [settled, setSettled] = useState(body);
  useEffect(() => { const id = setTimeout(() => setSettled(body), 350); return () => clearTimeout(id); }, [body]);
  return useQuery({
    queryKey: ["screener", "preview", settled],
    queryFn: () => send<Preview>("POST", "/filters/preview", JSON.parse(settled)),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
    retry: false,
  });
}

/** Remaining names after the stage that applied this filter, if it removed any. */
export const stageFor = (p: Preview | undefined, prefix: string) => p?.stages.find((s) => s.key === prefix);

/** Real distribution of one metric with the kept names overlaid, and a two-handle range over it. */
export function HistogramRange({ column, dist, min, max, onChange }: { column: string; dist?: Dist; min: unknown; max: unknown; onChange: (lo: string, hi: string) => void }) {
  if (!dist?.bins || dist.lo === undefined || dist.hi === undefined) return dist ? <div className="hr-empty">{dist.known} of {dist.total} known</div> : <div className="hr-empty">Loading distribution…</div>;
  const { bins, kept = [], lo, hi } = dist;
  const top = Math.max(1, ...bins);
  const step = (hi - lo) / 200 || 1e-6;
  const num = (v: unknown, d: number) => (v === "" || v === undefined || v === null || Number.isNaN(Number(v)) ? d : Math.min(hi, Math.max(lo, Number(v))));
  const a = num(min, lo), b = num(max, hi);
  const round = (v: number) => String(Number(v.toPrecision(3)));
  const W = 100 / bins.length;
  return (
    <div className="hr">
      <svg viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden>
        {bins.map((v, i) => <rect key={i} x={i * W + 0.15} width={W - 0.3} y={36 - (v / top) * 34} height={(v / top) * 34} fill="var(--line-3, var(--text-4))" opacity={0.5} />)}
        {kept.map((v, i) => <rect key={`k${i}`} x={i * W + 0.15} width={W - 0.3} y={36 - (v / top) * 34} height={(v / top) * 34} fill="var(--accent)" />)}
      </svg>
      <div className="hr-range">
        <input type="range" aria-label="Minimum" min={lo} max={hi} step={step} value={a} onChange={(e) => onChange(Number(e.target.value) <= lo ? "" : round(Math.min(Number(e.target.value), b)), max === undefined ? "" : String(max))} />
        <input type="range" aria-label="Maximum" min={lo} max={hi} step={step} value={b} onChange={(e) => onChange(min === undefined ? "" : String(min), Number(e.target.value) >= hi ? "" : round(Math.max(Number(e.target.value), a)))} />
      </div>
      <div className="hr-axis num"><span>{fmtKey(column, lo)}</span><span>median {fmtKey(column, dist.median)}</span><span>{fmtKey(column, hi)}</span></div>
      <div className="hr-known">{dist.known} of {dist.total} known</div>
    </div>
  );
}

/** Sector make-up of the universe as one thin stacked bar; hover a segment for its name and count. */
export function MixBar({ mix }: { mix?: Record<string, number> }) {
  const parts = Object.entries(mix ?? {}).filter(([k]) => k !== "Unknown");
  const total = parts.reduce((n, [, v]) => n + v, 0);
  if (!total) return null;
  return (
    <span className="ub-mix" role="img" aria-label={`Sector mix: ${parts.map(([k, v]) => `${k} ${v}`).join(", ")}`}>
      {parts.map(([k, v], i) => <i key={k} title={`${k}: ${v}`} style={{ flex: v, background: `oklch(0.64 0.12 ${(i * 47 + 258) % 360})` }} />)}
    </span>
  );
}
