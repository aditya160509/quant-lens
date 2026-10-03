"use client";

import { extent, scaleBand, scaleSqrt } from "d3";
import { memo, useState } from "react";
import { Readout, ReadoutRow, ReadoutTitle, Svg, diverging, fmtTick, useWidth } from "./core";

export type DotCell = { x: string | number; y: string | number; value: number; size?: number };

export type DotGridProps = {
  cells: DotCell[];
  xLabel?: string;
  yLabel?: string;
  metricLabel?: string;
  height?: number;
  format?: (v: number) => string;
  selected?: { x: string | number; y: string | number } | null;
  onSelect?: (cell: DotCell) => void;
};

const M = { top: 8, right: 8, bottom: 40, left: 52 };

/** Parameter-sweep grid: one dot per (x, y) pair, coloured by the metric on a diverging scale. */
function DotGridImpl({ cells, xLabel, yLabel, metricLabel = "Value", height = 240, format = fmtTick, selected, onSelect }: DotGridProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<DotCell | null>(null);
  const xv = [...new Set(cells.map((c) => c.x))].sort((a, b) => (typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b))));
  const yv = [...new Set(cells.map((c) => c.y))].sort((a, b) => (typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b))));
  const xs = scaleBand<string | number>().domain(xv).range([M.left, Math.max(M.left + 20, width - M.right)]);
  const ys = scaleBand<string | number>().domain(yv).range([M.top, height - M.bottom]);
  const maxAbs = Math.max(1e-9, ...cells.map((c) => Math.abs(c.value)));
  const [s0, s1] = extent(cells, (c) => c.size ?? 1) as [number, number];
  const rMax = Math.max(3, Math.min(xs.bandwidth(), ys.bandwidth()) / 2 - 2);
  const rs = scaleSqrt().domain([Math.min(0, s0 ?? 0), s1 || 1]).range([2, rMax]);
  const same = (c: { x: unknown; y: unknown }, o?: { x: unknown; y: unknown } | null) => !!o && c.x === o.x && c.y === o.y;
  const hasSize = cells.some((c) => c.size !== undefined);
  const skip = (n: number) => Math.max(1, Math.ceil(n / Math.max(1, Math.floor((width - M.left) / 44))));

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label={`${metricLabel} by ${xLabel ?? "x"} and ${yLabel ?? "y"}`} onPointerLeave={() => setHover(null)}>
          {xv.map((v, i) => i % skip(xv.length) === 0 ? <text key={String(v)} x={(xs(v) ?? 0) + xs.bandwidth() / 2} y={height - M.bottom + 14} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">{String(v)}</text> : null)}
          {yv.map((v) => <text key={String(v)} x={M.left - 8} y={(ys(v) ?? 0) + ys.bandwidth() / 2} dy="0.32em" textAnchor="end" fontSize={10.5} fill="var(--text-3)">{String(v)}</text>)}
          {xLabel ? <text x={(M.left + width - M.right) / 2} y={height - 6} textAnchor="middle" fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{xLabel}</text> : null}
          {yLabel ? <text x={4} y={M.top + 4} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{yLabel}</text> : null}
          {cells.map((c) => {
            const cx = (xs(c.x) ?? 0) + xs.bandwidth() / 2;
            const cy = (ys(c.y) ?? 0) + ys.bandwidth() / 2;
            const r = hasSize ? rs(c.size ?? 0) : rMax * 0.7;
            const sel = same(c, selected);
            return (
              <circle key={`${c.x}|${c.y}`} cx={cx} cy={cy} r={r} fill={diverging(c.value / maxAbs)}
                stroke={sel ? "var(--text)" : same(c, hover) ? "var(--text-2)" : "none"} strokeWidth={sel ? 2 : 1.5}
                style={{ cursor: onSelect ? "pointer" : undefined, transition: "r 120ms" }}
                onPointerEnter={() => setHover(c)} onClick={() => onSelect?.(c)} />
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
      {hover && width > 0 ? (
        <Readout x={(xs(hover.x) ?? 0) + xs.bandwidth() / 2} y={(ys(hover.y) ?? 0)} width={width} w={170}>
          <ReadoutTitle>{`${xLabel ?? "x"} ${hover.x}, ${yLabel ?? "y"} ${hover.y}`}</ReadoutTitle>
          <ReadoutRow label={metricLabel} value={format(hover.value)} />
          {hover.size !== undefined ? <ReadoutRow label="Size" value={format(hover.size)} /> : null}
        </Readout>
      ) : null}
    </div>
  );
}

export const DotGrid = memo(DotGridImpl);
