"use client";

import { scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { AxisY, GridY, SERIES, Svg, fmtTick, useWidth } from "./core";

/** One merge of a scipy-style linkage: child ids (< n are leaves), merge height and cluster size. */
import { clusterIds, leafOrder, validLinkage, type Merge } from "./clustering";
export { leafOrder, type Merge } from "./clustering";

const M = { top: 10, right: 12, bottom: 64, left: 44 };

/**
 * Hierarchical-clustering tree. Leaves come out in seriated order (the order HRP allocates in);
 * branches below `cut` share a colour so clusters read at a glance. Hovering a leaf names it.
 */
function DendrogramImpl({ merges, leaves, height = 260, cut, activeLeaves = [], onHoverLeaf }: { merges: Merge[]; leaves: string[]; height?: number; cut?: number; activeLeaves?: string[]; onHoverLeaf?: (leaf: string | null) => void }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = leaves.length;
  const tree = useMemo(() => leafOrder(merges, n), [merges, n]);
  const top = Math.max(1e-9, ...merges.map((m) => m.distance));
  const threshold = cut ?? top * 0.7;
  const ys = scaleLinear().domain([0, top]).range([height - M.bottom, M.top]).nice();
  const step = (width - M.left - M.right) / Math.max(1, n);
  const clusters = clusterIds(merges, n, threshold);
  const pos = new Map<number, { x: number; h: number; c: number }>();
  tree.forEach((id, i) => pos.set(id, { x: M.left + step * (i + 0.5), h: 0, c: clusters[id] }));
  const links: { d: string; color: string }[] = [];
  merges.forEach((m, k) => {
    const a = pos.get(m.left), b = pos.get(m.right);
    if (!a || !b) return;
    const c = m.distance <= threshold && a.c === b.c ? a.c : -1;
    const color = c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)";
    links.push({ d: `M${a.x},${ys(a.h)}V${ys(m.distance)}H${b.x}V${ys(b.h)}`, color });
    pos.set(n + k, { x: (a.x + b.x) / 2, h: m.distance, c });

  });

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {!validLinkage(merges, n) ? <p className="chart-empty">A complete, valid linkage is required to draw the cluster tree.</p> : width > 0 && n > 1 ? (
        <Svg width={width} height={height} label="Cluster dendrogram" role="group" onPointerLeave={() => { setHover(null); onHoverLeaf?.(null); }}>
          <GridY scale={ys} x1={M.left} x2={width - M.right} ticks={4} zero={false} />
          <AxisY scale={ys} x={M.left} ticks={4} format={fmtTick} />
          <text x={M.left} y={M.top - 2} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>Distance</text>
          <line x1={M.left} x2={width - M.right} y1={ys(threshold)} y2={ys(threshold)} stroke="var(--warn)" strokeDasharray="4 3" opacity={0.6} />
          {links.map((l, i) => <path key={i} d={l.d} fill="none" stroke={l.color} strokeWidth={1.4} />)}
          {tree.map((id, i) => {
            const x = M.left + step * (i + 0.5);
            const c = pos.get(id)?.c ?? -1;
            return (
              <g key={id} role="img" tabIndex={0} aria-label={`${leaves[id]}, cluster ${c + 1}`} onFocus={() => { setHover(i); onHoverLeaf?.(leaves[id]); }} onBlur={() => { setHover(null); onHoverLeaf?.(null); }} onPointerEnter={() => { setHover(i); onHoverLeaf?.(leaves[id]); }}>
                <circle cx={x} cy={ys(0)} r={hover === i || activeLeaves.includes(leaves[id]) ? 4 : 2.6} fill={c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)"} />
                <text transform={`translate(${x},${ys(0) + 8}) rotate(55)`} fontSize={10.5} fill={hover === i || activeLeaves.includes(leaves[id]) ? "var(--text)" : "var(--text-3)"}>{leaves[id]}</text>
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}

export const Dendrogram = memo(DendrogramImpl);
