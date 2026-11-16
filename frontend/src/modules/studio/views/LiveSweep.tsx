"use client";

import { useMemo } from "react";
import { Heatmap } from "@/charts/Heatmap";
import type { FeatureSpec } from "@/modules/research/types";

type Partial = { x: string; y: string | null; cells: [number, number, number | null][] };

/** Optimise while running: the parameter map filling in as cells finish. */
export default function LiveSweep({ feature, progress }: { feature: FeatureSpec; progress: unknown }) {
  const p = (progress as { partial?: Partial } | null)?.partial;
  const grid = useMemo(() => {
    if (!p) return null;
    const xs = [...new Set(p.cells.map((c) => c[0]))].sort((a, b) => a - b), ys = [...new Set(p.cells.map((c) => c[1]))].sort((a, b) => a - b);
    const v: (number | null)[][] = ys.map(() => xs.map(() => null));
    for (const [x, y, s] of p.cells) if (s !== null) v[ys.indexOf(y)][xs.indexOf(x)] = Math.max(v[ys.indexOf(y)][xs.indexOf(x)] ?? -Infinity, s);
    return { xs, ys, v };
  }, [p]);
  if (feature.id !== "st02" || !p || !grid || grid.xs.length * grid.ys.length > 900) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <Heatmap rows={grid.ys.map(String)} cols={grid.xs.map(String)} values={grid.v} format={(v) => v.toFixed(2)} rowTitle={p.y ?? ""} colTitle={p.x} />
    </div>
  );
}
