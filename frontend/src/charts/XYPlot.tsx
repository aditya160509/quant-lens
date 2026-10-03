"use client";

import { line as d3line, scaleLinear } from "d3";
import { useMemo, useState, type ReactNode } from "react";
import { AxisLabel, AxisX, AxisY, GridX, GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtTick, robustExtent, useWidth } from "./core";

export type XYPoint = { x: number; y: number; label?: string; group?: string; size?: number; emphasis?: boolean; detail?: [string, string][] };

type Props = {
  points: XYPoint[];
  /** Lines drawn through ordered points, e.g. fitted values either side of a cutoff. */
  lines?: { label: string; points: { x: number; y: number }[]; color?: string; dash?: boolean }[];
  xLabel: string;
  yLabel: string;
  height?: number;
  refX?: { x: number; label?: string; color?: string }[];
  refY?: { y: number; label?: string; color?: string }[];
  diagonal?: boolean;
  quadrants?: [string, string, string, string];
  labelPoints?: boolean;
  groupColors?: Record<string, string>;
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
  robust?: boolean;
  square?: boolean;
  footer?: ReactNode;
};

const M = { top: 14, right: 16, bottom: 34, left: 52 };

/** Scatter plot with optional fitted lines, reference lines, quadrant labels and nearest-point readout. */
export function XYPlot({
  points, lines = [], xLabel, yLabel, height = 300, refX = [], refY = [], diagonal = false, quadrants, labelPoints = false,
  groupColors, formatX = fmtTick, formatY = fmtTick, robust = false, square = false, footer,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const groups = useMemo(() => [...new Set(points.map((p) => p.group ?? ""))], [points]);
  const colorOf = (g = "") => groupColors?.[g] ?? (groups.length > 1 ? SERIES[groups.indexOf(g) % SERIES.length] : "var(--s1)");

  const [xd, yd] = useMemo(() => {
    const xsv = [...points.map((p) => p.x), ...lines.flatMap((l) => l.points.map((p) => p.x)), ...refX.map((r) => r.x)];
    const ysv = [...points.map((p) => p.y), ...lines.flatMap((l) => l.points.map((p) => p.y)), ...refY.map((r) => r.y)];
    const ext = (v: number[]): [number, number] => {
      if (robust) return robustExtent(v, 0.06, 0.01);
      const f = v.filter(Number.isFinite);
      const lo = Math.min(...f), hi = Math.max(...f), pad = (hi - lo || 1) * 0.08;
      return [lo - pad, hi + pad];
    };
    let xe = ext(xsv);
    let ye = ext(ysv);
    if (square) { const lo = Math.min(xe[0], ye[0]); const hi = Math.max(xe[1], ye[1]); xe = [lo, hi]; ye = [lo, hi]; }
    return [xe, ye];
  }, [points, lines, refX, refY, robust, square]);

  const plotW = Math.max(40, width - M.left - M.right);
  const xs = scaleLinear().domain(xd).range([M.left, M.left + plotW]).nice();
  const ys = scaleLinear().domain(yd).range([height - M.bottom, M.top]).nice();
  const inside = (p: { x: number; y: number }) => p.x >= xs.domain()[0] && p.x <= xs.domain()[1] && p.y >= ys.domain()[0] && p.y <= ys.domain()[1];
  const shown = points.filter(inside);
  const hp = hover === null ? null : shown[hover];
  const r = shown.length > 600 ? 1.8 : shown.length > 120 ? 2.6 : 4;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - b.left, my = e.clientY - b.top;
    let best = -1, bestD = 24 * 24;
    shown.forEach((p, i) => { const dx = xs(p.x) - mx, dy = ys(p.y) - my, d = dx * dx + dy * dy; if (d < bestD) { bestD = d; best = i; } });
    setHover(best >= 0 ? best : null);
  };

  const [xa, xb] = xs.domain();
  const [ya, yb] = ys.domain();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {groups.length > 1 || lines.length ? (
        <div style={{ marginBottom: 6 }}>
          <Legend items={[...groups.filter(Boolean).map((g) => ({ label: g, color: colorOf(g) })), ...lines.map((l, i) => ({ label: l.label, color: l.color ?? SERIES[(i + 1) % SERIES.length], dash: l.dash }))]} />
        </div>
      ) : null}
      {width > 0 ? (
        <Svg width={width} height={height} label={`${yLabel} against ${xLabel}`} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
          <GridY scale={ys} x1={M.left} x2={M.left + plotW} ticks={5} />
          <GridX scale={xs} y1={M.top} y2={height - M.bottom} ticks={6} />
          {xa < 0 && xb > 0 ? <line x1={crisp(xs(0))} x2={crisp(xs(0))} y1={M.top} y2={height - M.bottom} stroke="var(--line-3)" /> : null}
          <AxisY scale={ys} x={M.left} ticks={5} format={formatY} />
          <AxisX scale={xs} y={height - M.bottom} ticks={6} format={formatX} />
          <AxisLabel x={M.left + plotW} y={height - 2} anchor="end">{xLabel}</AxisLabel>
          <AxisLabel x={M.left} y={M.top - 4}>{yLabel}</AxisLabel>
          {quadrants ? (
            <g style={{ fontFamily: "var(--font)" }} fontSize={11} fill="var(--text-4)">
              <text x={M.left + plotW - 6} y={M.top + 14} textAnchor="end">{quadrants[0]}</text>
              <text x={M.left + 6} y={M.top + 14}>{quadrants[1]}</text>
              <text x={M.left + 6} y={height - M.bottom - 8}>{quadrants[2]}</text>
              <text x={M.left + plotW - 6} y={height - M.bottom - 8} textAnchor="end">{quadrants[3]}</text>
            </g>
          ) : null}
          {diagonal ? <line x1={xs(Math.max(xa, ya))} y1={ys(Math.max(xa, ya))} x2={xs(Math.min(xb, yb))} y2={ys(Math.min(xb, yb))} stroke="var(--text-3)" strokeDasharray="4 4" /> : null}
          {refX.map((l, i) => (
            <g key={`rx${i}`}>
              <line x1={crisp(xs(l.x))} x2={crisp(xs(l.x))} y1={M.top} y2={height - M.bottom} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={xs(l.x) + 5} y={M.top + 11} fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
            </g>
          ))}
          {refY.map((l, i) => (
            <g key={`ry${i}`}>
              <line x1={M.left} x2={M.left + plotW} y1={crisp(ys(l.y))} y2={crisp(ys(l.y))} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={M.left + plotW - 4} y={ys(l.y) - 5} textAnchor="end" fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
            </g>
          ))}
          {shown.map((p, i) => (
            <circle key={i} cx={xs(p.x)} cy={ys(p.y)} r={p.size ?? (p.emphasis ? r + 2.5 : r)} fill={p.emphasis ? "var(--warn)" : colorOf(p.group)}
              fillOpacity={p.emphasis ? 1 : shown.length > 300 ? 0.35 : 0.75} stroke={p.emphasis ? "var(--panel)" : "none"} strokeWidth={1.5} />
          ))}
          {lines.map((l, i) => {
            const d = d3line<{ x: number; y: number }>().x((p) => xs(p.x)).y((p) => ys(p.y))([...l.points].filter(inside).sort((a, b) => a.x - b.x));
            return <path key={l.label} d={d ?? ""} fill="none" stroke={l.color ?? SERIES[(i + 1) % SERIES.length]} strokeWidth={2} strokeDasharray={l.dash ? "5 4" : undefined} />;
          })}
          {labelPoints ? shown.filter((p) => p.label).map((p, i) => (
            <text key={`l${i}`} x={xs(p.x)} y={ys(p.y) - (p.emphasis ? 11 : 8)} textAnchor="middle" fontSize={10.5} fill={p.emphasis ? "var(--text)" : "var(--text-2)"} style={{ fontFamily: "var(--font)" }} fontWeight={p.emphasis ? 600 : 400}>{p.label}</text>
          )) : null}
          {hp ? <circle cx={xs(hp.x)} cy={ys(hp.y)} r={(hp.size ?? r) + 3} fill="none" stroke="var(--text)" strokeWidth={1.5} /> : null}
        </Svg>
      ) : <div style={{ height }} />}
      {hp ? (
        <Readout x={xs(hp.x)} y={Math.max(0, ys(hp.y) - 40)} width={width} w={210}>
          {hp.label ? <ReadoutTitle>{hp.label}</ReadoutTitle> : null}
          <ReadoutRow label={xLabel} value={formatX(hp.x)} />
          <ReadoutRow label={yLabel} value={formatY(hp.y)} />
          {hp.group ? <ReadoutRow label="Group" value={hp.group} /> : null}
          {hp.detail?.map(([k, v]) => <ReadoutRow key={k} label={k} value={v} />)}
        </Readout>
      ) : null}
      {footer}
    </div>
  );
}
