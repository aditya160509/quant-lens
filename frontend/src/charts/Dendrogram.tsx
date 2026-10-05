"use client";

import { scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { AxisY, GridY, SERIES, Svg, fmtTick, useWidth } from "./core";

/** One merge of a scipy-style linkage: child ids (< n are leaves), merge height and cluster size. */
export type Merge = { left: number; right: number; distance: number; count?: number };

const M = { top: 10, right: 12, bottom: 64, left: 44 };

/**
 * Hierarchical-clustering tree. Leaves come out in seriated order (the order HRP allocates in);
 * branches below `cut` share a colour so clusters read at a glance. Hovering a leaf names it.
 */
function DendrogramImpl({ merges, leaves, height = 260, cut }: { merges: Merge[]; leaves: string[]; height?: number; cut?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = leaves.length;
  const tree = useMemo(() => leafOrder(merges, n), [merges, n]);
  const top = Math.max(1e-9, ...merges.map((m) => m.distance));
  const threshold = cut ?? top * 0.7;
  const ys = scaleLinear().domain([0, top]).range([height - M.bottom, M.top]).nice();
  const step = (width - M.left - M.right) / Math.max(1, n);
  const pos = new Map<number, { x: number; h: number; c: number }>();
  tree.forEach((id, i) => pos.set(id, { x: M.left + step * (i + 0.5), h: 0, c: -1 }));
  let cluster = 0;
  const links: { d: string; color: string }[] = [];
  merges.forEach((m, k) => {
    const a = pos.get(m.left), b = pos.get(m.right);
    if (!a || !b) return;
    const c = m.distance <= threshold ? (a.c >= 0 ? a.c : b.c >= 0 ? b.c : cluster++) : -1;
    const color = c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)";
    links.push({ d: `M${a.x},${ys(a.h)}V${ys(m.distance)}H${b.x}V${ys(b.h)}`, color });
    pos.set(n + k, { x: (a.x + b.x) / 2, h: m.distance, c });
    const paint = (id: number) => { const p = pos.get(id); if (p && p.c < 0 && c >= 0) p.c = c; if (id >= n) { const mm = merges[id - n]; if (mm) { paint(mm.left); paint(mm.right); } } };
    if (c >= 0) { paint(m.left); paint(m.right); }
  });

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 && n > 1 ? (
        <Svg width={width} height={height} label="Cluster dendrogram" onPointerLeave={() => setHover(null)}>
          <GridY scale={ys} x1={M.left} x2={width - M.right} ticks={4} zero={false} />
          <AxisY scale={ys} x={M.left} ticks={4} format={fmtTick} />
          <text x={M.left} y={M.top - 2} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>Distance</text>
          <line x1={M.left} x2={width - M.right} y1={ys(threshold)} y2={ys(threshold)} stroke="var(--warn)" strokeDasharray="4 3" opacity={0.6} />
          {links.map((l, i) => <path key={i} d={l.d} fill="none" stroke={l.color} strokeWidth={1.4} />)}
          {tree.map((id, i) => {
            const x = M.left + step * (i + 0.5);
            const c = pos.get(id)?.c ?? -1;
            return (
              <g key={id} onPointerEnter={() => setHover(i)}>
                <circle cx={x} cy={ys(0)} r={hover === i ? 4 : 2.6} fill={c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)"} />
                <text transform={`translate(${x},${ys(0) + 8}) rotate(55)`} fontSize={10.5} fill={hover === i ? "var(--text)" : "var(--text-3)"}>{leaves[id]}</text>
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}

export const Dendrogram = memo(DendrogramImpl);

/** Leaf order of a linkage, for reordering a matrix to match the tree. */
export function leafOrder(merges: Merge[], n: number): number[] {
  const order: number[] = [];
  const walk = (id: number) => { if (id < n) order.push(id); else { const m = merges[id - n]; if (m) { walk(m.left); walk(m.right); } } };
  if (merges.length) walk(n + merges.length - 1);
  return order.length === n ? order : Array.from({ length: n }, (_, i) => i);
}
