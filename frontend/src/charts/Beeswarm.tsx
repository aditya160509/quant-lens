"use client";

import { scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { Readout, ReadoutRow, ReadoutTitle, Svg, crisp, fmtTick, robustExtent, useWidth } from "./core";

export type SwarmPoint = { row: string; value: number; color: number | null; label?: string };

const M = { top: 8, right: 16, bottom: 26, left: 120 };
const ROW = 26;

/**
 * SHAP-style beeswarm: one row per feature (ordered by mean |value|), one dot per observation at its
 * contribution, piled up so density shows, coloured low to high by the feature's own value.
 */
function BeeswarmImpl({ points, maxRows = 14, xLabel = "Contribution to prediction", format = fmtTick }: { points: SwarmPoint[]; maxRows?: number; xLabel?: string; format?: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const rows = useMemo(() => {
    const by = new Map<string, SwarmPoint[]>();
    points.forEach((p) => by.set(p.row, [...(by.get(p.row) ?? []), p]));
    return [...by.entries()].map(([row, ps]) => ({ row, ps, imp: ps.reduce((a, p) => a + Math.abs(p.value), 0) / ps.length })).sort((a, b) => b.imp - a.imp).slice(0, maxRows);
  }, [points, maxRows]);
  const height = M.top + M.bottom + rows.length * ROW;
  const [lo, hi] = robustExtent(rows.flatMap((r) => r.ps.map((p) => p.value)), 0.05, 0.005);
  const xs = scaleLinear().domain([Math.min(lo, 0), Math.max(hi, 0)]).range([M.left, Math.max(M.left + 10, width - M.right)]).nice();
  const dots = useMemo(() => {
    const out: { x: number; y: number; c: string; p: SwarmPoint }[] = [];
    rows.forEach((r, ri) => {
      const cs = r.ps.map((p) => p.color).filter((v): v is number => v !== null && Number.isFinite(v)).sort((a, b) => a - b);
      const q = (v: number) => (cs.length < 2 ? 0.5 : cs.findIndex((c) => c >= v) / (cs.length - 1));
      const bins = new Map<number, number>();
      const cy = M.top + ri * ROW + ROW / 2;
      [...r.ps].sort((a, b) => a.value - b.value).forEach((p) => {
        const x = xs(p.value);
        const b = Math.round(x / 3);
        const k = bins.get(b) ?? 0;
        bins.set(b, k + 1);
        const off = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 2.4;
        const t = p.color === null ? null : q(p.color);
        out.push({ x, y: cy + Math.max(-ROW / 2 + 3, Math.min(ROW / 2 - 3, off)), c: t === null ? "var(--text-4)" : `color-mix(in oklch, var(--down) ${Math.round(t * 100)}%, var(--s1))`, p });
      });
    });
    return out;
  }, [rows, xs]);
  const hd = hover === null ? null : dots[hover];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Beeswarm of contributions" onPointerLeave={() => setHover(null)}
          onPointerMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect(); const mx = e.clientX - r.left, my = e.clientY - r.top;
            let best = -1, bd = 64;
            dots.forEach((d, i) => { const dd = (d.x - mx) ** 2 + (d.y - my) ** 2; if (dd < bd) { bd = dd; best = i; } });
            setHover(best >= 0 ? best : null);
          }}>
          {rows.map((r, i) => (
            <g key={r.row}>
              <line x1={M.left} x2={width - M.right} y1={crisp(M.top + i * ROW + ROW / 2)} y2={crisp(M.top + i * ROW + ROW / 2)} stroke="var(--line)" />
              <text x={M.left - 10} y={M.top + i * ROW + ROW / 2 + 4} textAnchor="end" fontSize={11} fill="var(--text-2)" style={{ fontFamily: "var(--font)" }}>{r.row.length > 18 ? `${r.row.slice(0, 17)}…` : r.row}</text>
            </g>
          ))}
          <line x1={crisp(xs(0))} x2={crisp(xs(0))} y1={M.top} y2={height - M.bottom} stroke="var(--line-3)" />
          {dots.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={hover === i ? 3.6 : 2.2} fill={d.c} fillOpacity={0.85} />)}
          {xs.ticks(5).map((t) => <text key={t} x={xs(t)} y={height - 8} textAnchor="middle" fontSize={10.5} fill="var(--text-4)">{format(t)}</text>)}
          <text x={width - M.right} y={height - 8} textAnchor="end" fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{xLabel}</text>
        </Svg>
      ) : <div style={{ height }} />}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--text-3)", marginTop: 4, paddingLeft: M.left }}>
        Feature value <span style={{ width: 90, height: 6, borderRadius: 3, background: "linear-gradient(90deg, var(--s1), var(--down))" }} /> low → high
      </div>
      {hd ? (
        <Readout x={hd.x} y={Math.max(0, hd.y - 40)} width={width} w={200}>
          <ReadoutTitle>{hd.p.row}</ReadoutTitle>
          {hd.p.label ? <ReadoutRow label="Name" value={hd.p.label} /> : null}
          <ReadoutRow label="Contribution" value={format(hd.p.value)} tone={hd.p.value >= 0 ? "var(--up)" : "var(--down)"} />
          <ReadoutRow label="Feature value" value={hd.p.color === null ? "–" : fmtTick(hd.p.color)} />
        </Readout>
      ) : null}
    </div>
  );
}

export const Beeswarm = memo(BeeswarmImpl);
