"use client";

import { scaleLinear } from "d3";
import { useWidth } from "./core";

export type Bar = { label: string; value: number; note?: string; tone?: "accent" | "up" | "down" | "muted" };

/**
 * Ranked horizontal bars with direct labels: name and value on one line, the bar beneath,
 * an optional note under it. Diverging around zero when any value is negative.
 */
export function BarList({ bars, format = (v) => v.toFixed(2), max }: { bars: Bar[]; format?: (v: number) => string; max?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const hasNotes = bars.some((b) => b.note);
  const ROW = hasNotes ? 46 : 32;
  const height = bars.length * ROW;
  const lo = Math.min(0, ...bars.map((b) => b.value));
  const hi = max ?? Math.max(0, ...bars.map((b) => b.value));
  const x = scaleLinear().domain([lo, hi || 1]).range([0, Math.max(10, width)]);
  const color = (b: Bar) => b.tone === "up" ? "var(--up)" : b.tone === "down" ? "var(--down)" : b.tone === "muted" ? "var(--text-3)" : "var(--accent)";

  return (
    <div ref={ref}>
      {width > 0 ? (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Bar chart" style={{ display: "block", fontFamily: "var(--mono)" }}>
          {bars.map((b, i) => {
            const top = i * ROW;
            const x0 = x(Math.min(0, b.value));
            const w = Math.max(1, Math.abs(x(b.value) - x(0)));
            return (
              <g key={b.label}>
                <text x={0} y={top + 12} fontSize={12} fill="var(--text)" style={{ fontFamily: "var(--font)" }}>{b.label}</text>
                <text x={width} y={top + 12} textAnchor="end" fontSize={11.5} fill="var(--text-2)">{format(b.value)}</text>
                <rect x={0} y={top + 18} width={width} height={6} rx={3} fill="var(--grid)" />
                <rect x={x0} y={top + 18} width={w} height={6} rx={3} fill={color(b)} fillOpacity={b.tone === "muted" ? 0.5 : 0.9} />
                {b.note ? <text x={0} y={top + 37} fontSize={10.5} fill="var(--text-3)" style={{ fontFamily: "var(--font)" }}>{b.note}</text> : null}
              </g>
            );
          })}
          {lo < 0 ? <line x1={x(0)} x2={x(0)} y1={0} y2={height} stroke="var(--line-2)" /> : null}
        </svg>
      ) : <div style={{ height }} />}
    </div>
  );
}
