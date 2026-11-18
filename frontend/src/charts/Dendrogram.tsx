"use client";

import { scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { SERIES, Svg, fmtTick, useWidth } from "./core";

/** One merge of a scipy-style linkage: child ids (< n are leaves), merge height and cluster size. */
import { clusterIds, leafOrder, validLinkage, type Merge } from "./clustering";
export { leafOrder, type Merge } from "./clustering";

const ROW = 28;
const M = { top: 8, right: 16, bottom: 28 };

/**
 * Hierarchical-clustering tree, drawn sideways: leaves are rows with their names on the left, distance runs left to right.
 * Leaves come out in seriated order (the order HRP allocates in); branches below `cut` share a colour so clusters read at a glance.
 * Height follows the leaf count, so a three-member tree is short and a fifty-name tree still has room for every label.
 */
function DendrogramImpl({ merges, leaves, cut, activeLeaves = [], onHoverLeaf }: { merges: Merge[]; leaves: string[]; height?: number; cut?: number; activeLeaves?: string[]; onHoverLeaf?: (leaf: string | null) => void }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = leaves.length;
  const tree = useMemo(() => leafOrder(merges, n), [merges, n]);
  const top = Math.max(1e-9, ...merges.map((m) => m.distance));
  const threshold = cut ?? top * 0.7;
  const label = Math.min(220, Math.max(64, ...leaves.map((l) => l.length * 6.6))) + 12;
  const height = M.top + n * ROW + M.bottom;
  const xs = scaleLinear().domain([0, top]).range([label, Math.max(label + 40, width - M.right)]).nice();
  const yOf = (i: number) => M.top + ROW * (i + 0.5);
  const clusters = clusterIds(merges, n, threshold);
  const pos = new Map<number, { y: number; h: number; c: number }>();
  tree.forEach((id, i) => pos.set(id, { y: yOf(i), h: 0, c: clusters[id] }));
  const links: { d: string; color: string }[] = [];
  merges.forEach((m, k) => {
    const a = pos.get(m.left), b = pos.get(m.right);
    if (!a || !b) return;
    const c = m.distance <= threshold && a.c === b.c ? a.c : -1;
    const color = c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)";
    links.push({ d: `M${xs(a.h)},${a.y}H${xs(m.distance)}V${b.y}H${xs(b.h)}`, color });
    pos.set(n + k, { y: (a.y + b.y) / 2, h: m.distance, c });
  });
  const ticks = xs.ticks(5);
  const base = M.top + n * ROW;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {!validLinkage(merges, n) ? <p className="chart-empty">A complete, valid linkage is required to draw the cluster tree.</p> : width > 0 && n > 1 ? (
        <Svg width={width} height={height} label="Cluster dendrogram" role="group" onPointerLeave={() => { setHover(null); onHoverLeaf?.(null); }}>
          {ticks.map((t) => <line key={t} x1={xs(t)} x2={xs(t)} y1={M.top} y2={base} stroke="var(--grid)" />)}
          {ticks.map((t) => <text key={`l${t}`} x={xs(t)} y={base + 16} textAnchor="middle" fontSize={11} fill="var(--text-3)" style={{ fontVariantNumeric: "tabular-nums" }}>{fmtTick(t)}</text>)}
          <line x1={xs(threshold)} x2={xs(threshold)} y1={M.top} y2={base} stroke="var(--warn)" strokeDasharray="4 3" opacity={0.7}><title>{`Cut at distance ${fmtTick(threshold)}: branches left of it form one cluster`}</title></line>
          {links.map((l, i) => <path key={i} d={l.d} fill="none" stroke={l.color} strokeWidth={1.5} />)}
          {tree.map((id, i) => {
            const y = yOf(i);
            const c = pos.get(id)?.c ?? -1;
            const on = hover === i || activeLeaves.includes(leaves[id]);
            return (
              <g key={id} role="img" tabIndex={0} aria-label={`${leaves[id]}, cluster ${c + 1}`} onFocus={() => { setHover(i); onHoverLeaf?.(leaves[id]); }} onBlur={() => { setHover(null); onHoverLeaf?.(null); }} onPointerEnter={() => { setHover(i); onHoverLeaf?.(leaves[id]); }}>
                <rect x={0} y={y - ROW / 2} width={label} height={ROW} fill="transparent" />
                <text x={label - 10} y={y} dy="0.35em" textAnchor="end" fontSize={12} fill={on ? "var(--text)" : "var(--text-2)"}>{leaves[id]}</text>
                <circle cx={xs(0)} cy={y} r={on ? 4 : 3} fill={c >= 0 ? SERIES[c % SERIES.length] : "var(--text-3)"} />
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}

export const Dendrogram = memo(DendrogramImpl);
