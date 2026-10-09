"use client";

import { line as d3line, scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { AxisLabel, AxisX, AxisY, GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtTick, nearest, robustExtent, useWidth } from "./core";

export type PRSeries = { label: string; color?: string; points: { x: number; y: number; lo?: number | null; hi?: number | null }[]; bandStyle?: "whiskers" | "ribbon" };

type Props = {
  series: PRSeries[];
  xLabel: string;
  yLabel: string;
  height?: number;
  /** Vertical marker, e.g. the event date or the true cutoff. */
  event?: { x: number; label: string } | null;
  /** Shade x below the event as the pre-period. */
  shadePre?: boolean;
  format?: (v: number) => string;
  formatX?: (v: number) => string;
  refY?: number | null;
  robust?: boolean;
  highlightX?: number | null;
};

const M = { top: 16, right: 16, bottom: 34, left: 56 };

/**
 * Estimates with confidence intervals over a numeric x: event studies, bandwidth sensitivity,
 * placebo cutoffs. Several series are dodged so their intervals never overlap.
 */
function PointRangeImpl({ series, xLabel, yLabel, height = 300, event = null, shadePre = false, format = fmtTick, formatX = (v) => String(v), refY = 0, robust = true, highlightX = null }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hoverX, setHoverX] = useState<number | null>(null);
  const allX = useMemo(() => [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b), [series]);
  const yVals = series.flatMap((s) => s.points.flatMap((p) => [p.y, p.lo ?? p.y, p.hi ?? p.y]));
  const [ya, yb] = robust ? robustExtent([...yVals, ...(refY === null ? [] : [refY])], 0.08, 0.01) : [Math.min(...yVals), Math.max(...yVals)];
  const xMin = allX[0] ?? 0, xMax = allX[allX.length - 1] ?? 1;
  const step = allX.length > 1 ? Math.min(...allX.slice(1).map((v, i) => v - allX[i])) : 1;
  const xs = scaleLinear().domain([xMin - step * 0.6, xMax + step * 0.6]).range([M.left, Math.max(M.left + 20, width - M.right)]);
  const ys = scaleLinear().domain([ya, yb]).range([height - M.bottom, M.top]).nice();
  const [yMin, yMax] = ys.domain();
  const clamp = (v: number) => Math.max(yMin, Math.min(yMax, v));
  const px = Math.abs(xs(step) - xs(0));
  const dodge = series.length > 1 ? Math.min(px * 0.6, 14) / series.length : 0;
  const dense = allX.length > 40;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    if (!allX.length) return;
    setHoverX(allX[nearest(allX, xs.invert(e.clientX - b.left))]);
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {series.length > 1 ? <div style={{ marginBottom: 6 }}><Legend items={series.map((s, i) => ({ label: s.label, color: s.color ?? SERIES[i % SERIES.length] }))} /></div> : null}
      {width > 0 ? (
        <Svg width={width} height={height} label={`${yLabel} by ${xLabel}`} onPointerMove={onMove} onPointerLeave={() => setHoverX(null)}>
          {shadePre && event ? <rect x={M.left} y={M.top} width={Math.max(0, xs(event.x) - M.left)} height={height - M.top - M.bottom} fill="var(--text)" fillOpacity={0.03} /> : null}
          <GridY scale={ys} x1={M.left} x2={width - M.right} ticks={5} zero={false} />
          {refY !== null && refY >= yMin && refY <= yMax ? <line x1={M.left} x2={width - M.right} y1={crisp(ys(refY))} y2={crisp(ys(refY))} stroke="var(--line-3)" /> : null}
          <AxisY scale={ys} x={M.left} ticks={5} format={format} spine />
          <AxisX scale={xs} y={height - M.bottom} ticks={Math.min(10, allX.length)} format={(v) => formatX(v)} />
          <AxisLabel x={width - M.right} y={height - 2} anchor="end">{xLabel}</AxisLabel>
          <AxisLabel x={M.left} y={M.top - 5}>{yLabel}</AxisLabel>
          {event ? (
            <g>
              <line x1={crisp(xs(event.x))} x2={crisp(xs(event.x))} y1={M.top} y2={height - M.bottom} stroke="var(--warn)" strokeDasharray="4 3" />
              <text x={xs(event.x) + 5} y={M.top + 11} fontSize={10.5} fill="var(--warn)" style={{ fontFamily: "var(--font)" }}>{event.label}</text>
            </g>
          ) : null}
          {hoverX !== null ? <line x1={crisp(xs(hoverX))} x2={crisp(xs(hoverX))} y1={M.top} y2={height - M.bottom} stroke="var(--text-3)" strokeDasharray="2 3" /> : null}
          {series.map((s, si) => {
            const c = s.color ?? SERIES[si % SERIES.length];
            const off = (si - (series.length - 1) / 2) * dodge;
            const pts = [...s.points].sort((a, b) => a.x - b.x);
            const path = d3line<{ x: number; y: number }>().x((p) => xs(p.x) + off).y((p) => ys(clamp(p.y)))(pts) ?? "";
            const ribbon = s.bandStyle === "ribbon" || dense;
            const ribbonPath = ribbon
              ? `${pts.filter((p) => p.hi != null).map((p, i) => `${i ? "L" : "M"}${xs(p.x) + off},${ys(clamp(p.hi as number))}`).join("")}${[...pts].reverse().filter((p) => p.lo != null).map((p) => `L${xs(p.x) + off},${ys(clamp(p.lo as number))}`).join("")}Z`
              : null;
            return (
              <g key={s.label}>
                {ribbonPath ? <path d={ribbonPath} fill={c} fillOpacity={0.14} /> : null}
                <path d={path} fill="none" stroke={c} strokeWidth={1.5} strokeOpacity={0.7} />
                {pts.map((p) => {
                  const x = xs(p.x) + off;
                  const hl = highlightX !== null && p.x === highlightX;
                  return (
                    <g key={p.x}>
                      {!ribbon && p.lo != null && p.hi != null ? <line x1={x} x2={x} y1={ys(clamp(p.lo))} y2={ys(clamp(p.hi))} stroke={c} strokeWidth={1.6} strokeOpacity={0.55} strokeLinecap="round" /> : null}
                      <circle cx={x} cy={ys(clamp(p.y))} r={hl ? 5 : dense ? 2 : 3.2} fill={hl ? "var(--warn)" : c} stroke="var(--panel)" strokeWidth={hl ? 1.5 : 1} />
                    </g>
                  );
                })}
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
      {hoverX !== null ? (
        <Readout x={xs(hoverX)} y={18} width={width} w={230}>
          <ReadoutTitle>{xLabel} {formatX(hoverX)}</ReadoutTitle>
          {series.map((s, i) => {
            const p = s.points.find((q) => q.x === hoverX);
            if (!p) return null;
            return <ReadoutRow key={s.label} label={s.label} swatch={s.color ?? SERIES[i % SERIES.length]} value={`${format(p.y)}${p.lo != null && p.hi != null ? `  [${format(p.lo)}, ${format(p.hi)}]` : ""}`} />;
          })}
        </Readout>
      ) : null}
    </div>
  );
}

export const PointRange = memo(PointRangeImpl);
