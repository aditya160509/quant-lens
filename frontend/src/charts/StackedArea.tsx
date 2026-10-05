"use client";

import { area, scaleLinear, stack, stackOffsetExpand, stackOffsetNone, stackOrderInsideOut } from "d3";
import { memo, useMemo, useState } from "react";
import { AxisY, GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtDate, fmtTick, nearest, parseDate, useWidth } from "./core";

type Row = Record<string, unknown>;
const M = { top: 10, right: 52, bottom: 24, left: 8 };

/**
 * Shares over time (model weights, allocations, regime probabilities) as stacked areas.
 * Layers are ordered inside-out so the largest share sits in the middle and edges stay calm;
 * the readout lists exact values, which stacked areas cannot show by height alone.
 */
function StackedAreaImpl({ data, x = "date", keys, labels, height = 260, normalize = true, format }: {
  data: Row[]; x?: string; keys: string[]; labels?: Record<string, string>; height?: number; normalize?: boolean; format?: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const fmt = format ?? (normalize ? (v: number) => `${(v * 100).toFixed(1)}%` : fmtTick);
  const rows = useMemo(() => data.map((r) => ({ t: parseDate(r[x]) ?? 0, ...Object.fromEntries(keys.map((k) => [k, typeof r[k] === "number" && Number.isFinite(r[k]) ? (r[k] as number) : 0])) }))
    .filter((r) => r.t).sort((a, b) => a.t - b.t), [data, x, keys]);
  const layers = useMemo(() => stack<Record<string, number>>().keys(keys).order(stackOrderInsideOut).offset(normalize ? stackOffsetExpand : stackOffsetNone)(rows as unknown as Record<string, number>[]), [rows, keys, normalize]);
  const color = (k: string) => SERIES[keys.indexOf(k) % SERIES.length];
  if (!rows.length) return null;
  const t0 = rows[0].t, t1 = rows[rows.length - 1].t;
  const xs = scaleLinear().domain([t0, t1]).range([M.left, Math.max(M.left + 10, width - M.right)]);
  const top = normalize ? 1 : Math.max(1e-12, ...layers.flatMap((l) => l.map((d) => d[1])));
  const ys = scaleLinear().domain([0, top]).range([height - M.bottom, M.top]).nice();
  const path = area<[number, number] & { data: Record<string, number> }>().x((d) => xs(d.data.t)).y0((d) => ys(d[0])).y1((d) => ys(d[1]));
  const times = rows.map((r) => r.t);
  const hr = hover === null ? null : rows[hover] as Record<string, number>;
  const ticks = xs.ticks(Math.max(2, Math.floor(width / 110)));

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div style={{ marginBottom: 6 }}><Legend items={keys.map((k) => ({ label: labels?.[k] ?? k, color: color(k), value: hr ? fmt(hr[k]) : undefined }))} /></div>
      {width > 0 ? (
        <Svg width={width} height={height} label="Stacked area chart"
          onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(nearest(times, xs.invert(e.clientX - r.left))); }}
          onPointerLeave={() => setHover(null)}>
          <GridY scale={ys} x1={M.left} x2={width - M.right} ticks={4} />
          {layers.map((l) => <path key={l.key} d={path(l as never) ?? ""} fill={color(l.key)} fillOpacity={0.78} stroke="var(--panel)" strokeWidth={0.6} />)}
          <AxisY scale={ys} x={width - M.right} ticks={4} format={fmt} side="right" />
          {ticks.map((t) => <text key={t} x={xs(t)} y={height - 6} textAnchor="middle" fontSize={10.5} fill="var(--text-4)">{fmtDate(t)}</text>)}
          {hover !== null ? <line x1={crisp(xs(rows[hover].t))} x2={crisp(xs(rows[hover].t))} y1={M.top} y2={height - M.bottom} stroke="var(--text-3)" strokeDasharray="3 3" /> : null}
        </Svg>
      ) : <div style={{ height }} />}
      {hr && hover !== null ? (
        <Readout x={xs(rows[hover].t)} y={30} width={width} w={210}>
          <ReadoutTitle>{fmtDate(rows[hover].t, true)}</ReadoutTitle>
          {[...keys].sort((a, b) => hr[b] - hr[a]).slice(0, 10).map((k) => <ReadoutRow key={k} label={labels?.[k] ?? k} value={fmt(hr[k])} swatch={color(k)} />)}
        </Readout>
      ) : null}
    </div>
  );
}

export const StackedArea = memo(StackedAreaImpl);
