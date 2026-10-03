"use client";

import { scaleBand, scaleLinear } from "d3";
import { useState } from "react";
import { AxisY, GridY, Readout, ReadoutRow, ReadoutTitle, Svg, crisp, fmtTick, useWidth } from "./core";

export type BarDatum = { label: string; value: number; lo?: number | null; hi?: number | null; color?: string; detail?: [string, string][] };

type Props = {
  bars: BarDatum[];
  height?: number;
  format?: (v: number) => string;
  refLines?: { y: number; label?: string; color?: string }[];
  /** Colour bars by sign (up/down) unless a bar sets its own colour. */
  signed?: boolean;
  valueLabels?: boolean;
  yLabel?: string;
  /** Hide category labels when there are too many to read. */
  hideLabels?: boolean;
};

const M = { top: 18, right: 12, bottom: 30, left: 48 };

/** Vertical bars with optional confidence whiskers, reference lines and per-bar readout. */
export function Bars({ bars, height = 240, format = fmtTick, refLines = [], signed = true, valueLabels, yLabel, hideLabels }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const showValues = valueLabels ?? bars.length <= 12;
  const values = bars.flatMap((b) => [b.value, b.lo ?? b.value, b.hi ?? b.value]).concat(refLines.map((r) => r.y), [0]).filter(Number.isFinite);
  const ys = scaleLinear().domain([Math.min(...values), Math.max(...values)]).range([height - M.bottom, M.top]).nice();
  const xs = scaleBand().domain(bars.map((_, i) => `${i}`)).range([M.left, Math.max(M.left + 10, width - M.right)]).paddingInner(bars.length > 30 ? 0.15 : 0.32).paddingOuter(0.2);
  const zero = ys(0);
  const color = (b: BarDatum) => b.color ?? (signed ? (b.value >= 0 ? "var(--up)" : "var(--down)") : "var(--s1)");
  const hb = hover === null ? null : bars[hover];
  const labels = !hideLabels && bars.length <= 24;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Bar chart" onPointerLeave={() => setHover(null)}>
          <GridY scale={ys} x1={M.left} x2={width - M.right} ticks={5} />
          <AxisY scale={ys} x={M.left} ticks={5} format={format} />
          {yLabel ? <text x={M.left} y={M.top - 6} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{yLabel}</text> : null}
          {bars.map((b, i) => {
            const x = xs(`${i}`) ?? 0;
            const w = xs.bandwidth();
            const y = ys(b.value);
            const active = hover === i;
            return (
              <g key={i} onPointerEnter={() => setHover(i)}>
                <rect x={x - xs.step() * 0.15} y={M.top} width={xs.step()} height={height - M.top - M.bottom} fill="transparent" />
                <rect x={x} y={Math.min(y, zero)} width={w} height={Math.max(1, Math.abs(zero - y))} rx={Math.min(3, w / 3)} fill={color(b)} fillOpacity={hover === null || active ? 0.88 : 0.45} />
                {b.lo !== null && b.lo !== undefined && b.hi !== null && b.hi !== undefined ? (
                  <g stroke="var(--text-2)" strokeWidth={1.2}>
                    <line x1={x + w / 2} x2={x + w / 2} y1={ys(b.lo)} y2={ys(b.hi)} />
                    <line x1={x + w / 2 - 4} x2={x + w / 2 + 4} y1={ys(b.lo)} y2={ys(b.lo)} />
                    <line x1={x + w / 2 - 4} x2={x + w / 2 + 4} y1={ys(b.hi)} y2={ys(b.hi)} />
                  </g>
                ) : null}
                {showValues ? <text x={x + w / 2} y={b.value >= 0 ? Math.min(y, ys(b.hi ?? b.value)) - 5 : Math.max(y, ys(b.lo ?? b.value)) + 13} textAnchor="middle" fontSize={10.5} fill="var(--text-2)">{format(b.value)}</text> : null}
                {labels ? <text x={x + w / 2} y={height - M.bottom + 16} textAnchor="middle" fontSize={10.5} fill={active ? "var(--text)" : "var(--text-3)"} style={{ fontFamily: "var(--font)" }}>{b.label.length > 12 ? `${b.label.slice(0, 11)}…` : b.label}</text> : null}
              </g>
            );
          })}
          <line x1={M.left} x2={width - M.right} y1={crisp(zero)} y2={crisp(zero)} stroke="var(--line-3)" />
          {refLines.map((l, i) => (
            <g key={i}>
              <line x1={M.left} x2={width - M.right} y1={crisp(ys(l.y))} y2={crisp(ys(l.y))} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={width - M.right} y={ys(l.y) - 5} textAnchor="end" fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
            </g>
          ))}
        </Svg>
      ) : <div style={{ height }} />}
      {hb && hover !== null ? (
        <Readout x={(xs(`${hover}`) ?? 0) + xs.bandwidth() / 2} y={10} width={width} w={210}>
          <ReadoutTitle>{hb.label}</ReadoutTitle>
          <ReadoutRow label="Value" value={format(hb.value)} tone={color(hb)} />
          {hb.lo !== null && hb.lo !== undefined && hb.hi !== null && hb.hi !== undefined ? <ReadoutRow label="95% CI" value={`${format(hb.lo)} to ${format(hb.hi)}`} /> : null}
          {hb.detail?.map(([k, v]) => <ReadoutRow key={k} label={k} value={v} />)}
        </Readout>
      ) : null}
    </div>
  );
}
