"use client";

import { bin, extent } from "d3";
import { scaleLinear } from "d3";
import { useMemo, useState } from "react";
import { AxisLabel, AxisX, Readout, ReadoutRow, Svg, crisp, useWidth } from "./core";

type Props = {
  values: number[];
  observed?: number | null;
  /** Which tail counts as "as extreme as observed". */
  tail?: "right" | "left" | "two";
  xLabel?: string;
  observedLabel?: string;
  height?: number;
  format?: (v: number) => string;
};

/**
 * Null or sampling distribution as a histogram, with the observed statistic marked
 * and the tail beyond it shaded, so the shaded share reads as the p-value.
 */
export function Distribution({ values, observed = null, tail = "right", xLabel = "Statistic", observedLabel = "Observed", height = 220, format = (v) => v.toFixed(2) }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const M = { top: 26, right: 12, bottom: 30, left: 12 };

  const { bins, x } = useMemo(() => {
    const clean = values.filter(Number.isFinite);
    const [a, b] = extent([...clean, ...(observed !== null && Number.isFinite(observed) ? [observed] : [])]) as [number, number];
    const pad = (b - a || 1) * 0.06;
    const x = scaleLinear().domain([a - pad, b + pad]).nice();
    const bins = bin().domain(x.domain() as [number, number]).thresholds(x.ticks(Math.min(40, Math.max(12, Math.round(Math.sqrt(clean.length) * 2)))))(clean);
    return { bins, x };
  }, [values, observed]);

  x.range([M.left, Math.max(M.left + 10, width - M.right)]);
  const yMax = Math.max(1, ...bins.map((b) => b.length));
  const y = scaleLinear().domain([0, yMax]).range([height - M.bottom, M.top]);
  const n = values.filter(Number.isFinite).length;
  const inTail = (v: number) => observed === null ? false
    : tail === "right" ? v >= observed : tail === "left" ? v <= observed : Math.abs(v) >= Math.abs(observed);
  const tailShare = observed === null || !n ? null : values.filter((v) => Number.isFinite(v) && inTail(v)).length / n;
  const hb = hover === null ? null : bins[hover];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label={`${xLabel} distribution`}
          onPointerMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const v = x.invert(e.clientX - r.left);
            const i = bins.findIndex((b) => (b.x0 ?? 0) <= v && v < (b.x1 ?? 0));
            setHover(i >= 0 ? i : null);
          }}
          onPointerLeave={() => setHover(null)}>
          <line x1={M.left} x2={width - M.right} y1={crisp(y(0))} y2={crisp(y(0))} stroke="var(--line-2)" />
          {bins.map((b, i) => {
            const mid = ((b.x0 ?? 0) + (b.x1 ?? 0)) / 2;
            const shaded = inTail(mid);
            const w = Math.max(1, x(b.x1 ?? 0) - x(b.x0 ?? 0) - 1);
            return (
              <rect key={i} x={x(b.x0 ?? 0) + 0.5} y={y(b.length)} width={w} height={y(0) - y(b.length)} rx={1}
                fill={shaded ? "var(--accent)" : "var(--text-3)"} fillOpacity={hover === i ? 0.9 : shaded ? 0.7 : 0.35} />
            );
          })}
          <AxisX scale={x} y={height - M.bottom} ticks={7} />
          <AxisLabel x={width - M.right} y={height - 2} anchor="end">{xLabel}</AxisLabel>
          {observed !== null && Number.isFinite(observed) ? (
            <g>
              <line x1={crisp(x(observed))} x2={crisp(x(observed))} y1={M.top - 6} y2={y(0)} stroke="var(--text)" strokeWidth={1.5} />
              <text x={x(observed)} y={M.top - 12} textAnchor={x(observed) > width - 120 ? "end" : x(observed) < 120 ? "start" : "middle"} fontSize={10.5} fill="var(--text)">
                {observedLabel} {format(observed)}{tailShare !== null ? `  ·  ${(tailShare * 100).toFixed(1)}% as extreme` : ""}
              </text>
            </g>
          ) : null}
        </Svg>
      ) : <div style={{ height }} />}
      {hb ? (
        <Readout x={x(((hb.x0 ?? 0) + (hb.x1 ?? 0)) / 2)} y={8} width={width}>
          <ReadoutRow label="Range" value={`${format(hb.x0 ?? 0)} to ${format(hb.x1 ?? 0)}`} />
          <ReadoutRow label="Draws" value={`${hb.length} of ${n}`} />
          <ReadoutRow label="Share" value={`${((hb.length / Math.max(1, n)) * 100).toFixed(1)}%`} />
        </Readout>
      ) : null}
    </div>
  );
}
