"use client";

import { memo, useMemo, useState } from "react";
import { SERIES, Svg, useWidth } from "./core";

export type Edge = { source: string; target: string; weight: number; note?: string };

/**
 * Nodes on a circle, edges drawn with thickness and opacity by weight (0..1). Deterministic layout,
 * so the same universe always draws the same picture; hovering a node isolates its links.
 */
function NetworkImpl({ edges, nodes: given, height = 300, groups }: { edges: Edge[]; nodes?: string[]; height?: number; groups?: Record<string, string> }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);
  const nodes = useMemo(() => given ?? [...new Set(edges.flatMap((e) => [e.source, e.target]))].sort(), [given, edges]);
  const groupList = useMemo(() => [...new Set(nodes.map((n) => groups?.[n] ?? ""))], [nodes, groups]);
  const ordered = useMemo(() => [...nodes].sort((a, b) => groupList.indexOf(groups?.[a] ?? "") - groupList.indexOf(groups?.[b] ?? "") || a.localeCompare(b)), [nodes, groups, groupList]);
  const r = Math.max(40, Math.min(width, height) / 2 - 46);
  const cx = width / 2, cy = height / 2;
  const at = new Map(ordered.map((n, i) => { const a = (i / ordered.length) * Math.PI * 2 - Math.PI / 2; return [n, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), a }]; }));
  const degree = new Map<string, number>();
  edges.forEach((e) => { degree.set(e.source, (degree.get(e.source) ?? 0) + 1); degree.set(e.target, (degree.get(e.target) ?? 0) + 1); });
  const color = (n: string) => SERIES[Math.max(0, groupList.indexOf(groups?.[n] ?? "")) % SERIES.length];

  return (
    <div ref={ref}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Network" onPointerLeave={() => setHover(null)}>
          {edges.map((e, i) => {
            const a = at.get(e.source), b = at.get(e.target);
            if (!a || !b) return null;
            const on = !hover || hover === e.source || hover === e.target;
            const w = Math.max(0, Math.min(1, e.weight));
            return <path key={i} d={`M${a.x},${a.y}Q${cx},${cy} ${b.x},${b.y}`} fill="none" stroke="var(--accent)" strokeWidth={0.8 + w * 3.2} strokeOpacity={on ? 0.25 + w * 0.6 : 0.05}><title>{`${e.source} – ${e.target}${e.note ? ` · ${e.note}` : ""}`}</title></path>;
          })}
          {ordered.map((n) => {
            const p = at.get(n)!;
            const d = degree.get(n) ?? 0;
            const right = Math.cos(p.a) >= 0;
            return (
              <g key={n} onPointerEnter={() => setHover(n)} style={{ cursor: "default" }}>
                <circle cx={p.x} cy={p.y} r={3 + Math.min(6, d * 1.2)} fill={d ? color(n) : "var(--panel-3)"} stroke="var(--panel)" strokeWidth={1.5} opacity={!hover || hover === n || edges.some((e) => (e.source === hover && e.target === n) || (e.target === hover && e.source === n)) ? 1 : 0.3} />
                <text x={p.x + (right ? 10 : -10)} y={p.y + 4} textAnchor={right ? "start" : "end"} fontSize={10.5} fill={hover === n ? "var(--text)" : d ? "var(--text-2)" : "var(--text-4)"}>{n}</text>
              </g>
            );
          })}
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}

export const Network = memo(NetworkImpl);
