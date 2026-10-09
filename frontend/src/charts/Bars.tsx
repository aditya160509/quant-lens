"use client";

import { scaleBand, scaleLinear } from "d3";
import { memo, useState } from "react";
import { AxisY, Readout, ReadoutRow, ReadoutTitle, Svg, crisp, fmtTick, useWidth } from "./core";

/** `muted` marks a comparator (control, baseline, alternative): drawn pale with an outline so the bar under test stands out. */
export type BarDatum = { label: string; value: number; lo?: number | null; hi?: number | null; color?: string; muted?: boolean; detail?: [string, string][] };

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

/** A bar rounded only at its value end, so it reads as growing from the zero line. */
function barPath(x: number, w: number, y: number, zero: number) {
  const h = Math.max(1, Math.abs(zero - y));
  const r = Math.min(1.5, w / 4, h);
  if (y <= zero) {
    const t = zero - h;
    return `M${x},${zero}V${t + r}Q${x},${t} ${x + r},${t}H${x + w - r}Q${x + w},${t} ${x + w},${t + r}V${zero}Z`;
  }
  const b = zero + h;
  return `M${x},${zero}V${b - r}Q${x},${b} ${x + r},${b}H${x + w - r}Q${x + w},${b} ${x + w},${b - r}V${zero}Z`;
}

/** Vertical bars with optional confidence whiskers, reference lines and per-bar readout. */
function BarsImpl({ bars, height = 240, format = fmtTick, refLines = [], signed = true, valueLabels, yLabel, hideLabels }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const showValues = valueLabels ?? bars.length <= 14;
  const values = bars.flatMap((b) => [b.value, b.lo ?? b.value, b.hi ?? b.value]).concat(refLines.map((r) => r.y), [0]).filter(Number.isFinite);
  // A y-axis title sits above the plot, so leave room for it and for the tallest bar's value label.
  const top = M.top + (yLabel ? 12 : 0);
  const ys = scaleLinear().domain([Math.min(...values), Math.max(...values)]).range([height - M.bottom, top]).nice();
  const xs = scaleBand().domain(bars.map((_, i) => `${i}`)).range([M.left, Math.max(M.left + 10, width - M.right)]).paddingInner(bars.length > 30 ? 0.15 : 0.32).paddingOuter(0.2);
  const zero = ys(0);
  const color = (b: BarDatum) => b.color ?? (b.muted ? "var(--ctl)" : signed ? (b.value >= 0 ? "var(--up)" : "var(--down)") : "var(--s1)");
  const hb = hover === null ? null : bars[hover];
  const labels = !hideLabels && bars.length <= 24;
  // Bars never grow fatter than 56 px: wide bars read as blocks, not as values.
  const bw = Math.min(56, xs.bandwidth());
  const off = (xs.bandwidth() - bw) / 2;
  const maxChars = Math.max(4, Math.floor(xs.step() / 6.2));
  const valuesFit = showValues && bw >= 22;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Bar chart" onPointerLeave={() => setHover(null)}>
          <AxisY scale={ys} x={M.left - 4} ticks={5} format={format} spine />
          {yLabel ? <text x={M.left} y={M.top - 6} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{yLabel}</text> : null}
          {bars.map((b, i) => {
            const x = (xs(`${i}`) ?? 0) + off;
            const w = bw;
            const y = ys(b.value);
            const active = hover === i;
            return (
              <g key={i} onPointerEnter={() => setHover(i)}>
                <rect x={x - off - xs.step() * 0.15} y={top} width={xs.step()} height={height - top - M.bottom} fill="transparent" />
                <path d={barPath(x, w, y, zero)} fill={color(b)} fillOpacity={(b.muted ? 0.28 : 0.92) * (hover === null || active ? 1 : 0.5)}
                  stroke={b.muted ? color(b) : "none"} strokeOpacity={hover === null || active ? 0.9 : 0.45} strokeWidth={1} />
                {b.lo !== null && b.lo !== undefined && b.hi !== null && b.hi !== undefined ? (
                  <g stroke="var(--text)" strokeOpacity={0.75} strokeWidth={1.1}>
                    <line x1={x + w / 2} x2={x + w / 2} y1={ys(b.lo)} y2={ys(b.hi)} />
                    <line x1={x + w / 2 - 4} x2={x + w / 2 + 4} y1={ys(b.lo)} y2={ys(b.lo)} />
                    <line x1={x + w / 2 - 4} x2={x + w / 2 + 4} y1={ys(b.hi)} y2={ys(b.hi)} />
                  </g>
                ) : null}
                {valuesFit || (showValues && active) ? (() => {
                  // Negative values label below the bar unless that would run into the category labels; then inside it.
                  const below = Math.max(y, ys(b.lo ?? b.value)) + 13;
                  const inside = b.value < 0 && below > height - M.bottom - 2;
                  return <text x={x + w / 2} y={b.value >= 0 ? Math.min(y, ys(b.hi ?? b.value)) - 5 : inside ? y - 5 : below} textAnchor="middle" fontSize={10.5} fill={inside ? "var(--panel)" : "var(--text-2)"} fontWeight={inside ? 600 : undefined}>{format(b.value)}</text>;
                })() : null}
                {labels ? <text x={x + w / 2} y={height - M.bottom + 16} textAnchor="middle" fontSize={10.5} fill={active ? "var(--text)" : "var(--text-3)"} style={{ fontFamily: "var(--font)" }}>{b.label.length > maxChars ? `${b.label.slice(0, maxChars - 1)}…` : b.label}</text> : null}
              </g>
            );
          })}
          <line x1={M.left} x2={width - M.right} y1={crisp(zero)} y2={crisp(zero)} stroke="var(--line-3)" />
          {refLines.map((l, i) => (
            <g key={i}>
              <line x1={M.left} x2={width - M.right} y1={crisp(ys(l.y))} y2={crisp(ys(l.y))} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={width - M.right - 2} y={ys(l.y) - 5} textAnchor="end" paintOrder="stroke" stroke="var(--panel)" strokeWidth={3} fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
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

export const Bars = memo(BarsImpl);
