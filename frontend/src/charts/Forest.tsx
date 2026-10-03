"use client";

import { scaleLinear } from "d3";
import { useState } from "react";
import { Svg, crisp, fmtTick, useWidth } from "./core";

export type ForestRow = { label: string; sub?: string; estimate: number; lo: number | null; hi: number | null; tone?: "up" | "down" | "muted" | "accent"; note?: string; bold?: boolean };

/**
 * Forest plot: one row per estimate with its confidence interval, a zero line,
 * and the numbers printed on the right so the chart doubles as a table.
 */
export function Forest({ rows, format = (v: number) => v.toFixed(4), refX = 0, refLabel }: { rows: ForestRow[]; format?: (v: number) => string; refX?: number | null; refLabel?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const ROW = 34;
  const LABEL = Math.min(200, Math.max(110, width * 0.26));
  const VALUE = Math.min(190, Math.max(130, width * 0.24));
  const height = rows.length * ROW + 26;
  const vals = rows.flatMap((r) => [r.estimate, r.lo ?? r.estimate, r.hi ?? r.estimate]).concat(refX === null ? [] : [refX]).filter(Number.isFinite);
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo || 1) * 0.06;
  const xs = scaleLinear().domain([lo - pad, hi + pad]).range([LABEL + 8, Math.max(LABEL + 40, width - VALUE - 8)]).nice();
  const tone = (r: ForestRow) => {
    if (r.tone === "muted") return "var(--text-3)";
    if (r.tone === "accent") return "var(--accent)";
    if (r.tone) return `var(--${r.tone})`;
    const sig = r.lo !== null && r.hi !== null && (r.lo > 0 || r.hi < 0);
    return sig ? (r.estimate > 0 ? "var(--up)" : "var(--down)") : "var(--text-2)";
  };

  return (
    <div ref={ref}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Forest plot of estimates" onPointerLeave={() => setHover(null)}>
          {xs.ticks(5).map((t) => (
            <g key={t}>
              <line x1={crisp(xs(t))} x2={crisp(xs(t))} y1={4} y2={height - 22} stroke="var(--grid)" />
              <text x={xs(t)} y={height - 6} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">{fmtTick(t)}</text>
            </g>
          ))}
          {refX !== null ? (
            <g>
              <line x1={crisp(xs(refX))} x2={crisp(xs(refX))} y1={2} y2={height - 22} stroke="var(--line-3)" />
              {refLabel ? <text x={xs(refX) + 4} y={10} fontSize={10} fill="var(--text-3)" style={{ fontFamily: "var(--font)" }}>{refLabel}</text> : null}
            </g>
          ) : null}
          {rows.map((r, i) => {
            const y = i * ROW + ROW / 2 + 4;
            const c = tone(r);
            return (
              <g key={i} onPointerEnter={() => setHover(i)}>
                <rect x={0} y={y - ROW / 2} width={width} height={ROW} rx={6} fill={hover === i ? "var(--panel-2)" : "transparent"} />
                <text x={4} y={r.sub ? y - 2 : y} dy="0.32em" fontSize={12.5} fill="var(--text)" fontWeight={r.bold ? 600 : 450} style={{ fontFamily: "var(--font)" }}>{r.label}</text>
                {r.sub ? <text x={4} y={y + 11} dy="0.32em" fontSize={10.5} fill="var(--text-3)" style={{ fontFamily: "var(--font)" }}>{r.sub}</text> : null}
                {r.lo !== null && r.hi !== null ? <line x1={xs(r.lo)} x2={xs(r.hi)} y1={y} y2={y} stroke={c} strokeWidth={2.2} strokeLinecap="round" strokeOpacity={0.55} /> : null}
                <rect x={xs(r.estimate) - 4.5} y={y - 4.5} width={9} height={9} rx={2} fill={c} transform={`rotate(45 ${xs(r.estimate)} ${y})`} />
                <text x={width - 4} y={y - 1} textAnchor="end" dy="0.32em" fontSize={12} fill="var(--text)">{format(r.estimate)}</text>
                {r.lo !== null && r.hi !== null ? <text x={width - 4} y={y + 12} textAnchor="end" dy="0.32em" fontSize={10.5} fill="var(--text-3)">[{format(r.lo)}, {format(r.hi)}]</text> : r.note ? <text x={width - 4} y={y + 12} textAnchor="end" dy="0.32em" fontSize={10.5} fill="var(--text-3)">{r.note}</text> : null}
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}
