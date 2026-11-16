"use client";

import { useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Bars } from "@/charts/Bars";
import { Heatmap } from "@/charts/Heatmap";
import { XYPlot } from "@/charts/XYPlot";
import { isNum, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { studio } from "../api";
import { Skipped } from "./BacktestViews";

type Plateau = { status: string; reason?: string; centre?: Record<string, number>; region?: Record<string, [number, number]>; centre_score?: number; best_score?: number };
type OptMeta = { plateau: Plateau; parameters: string[]; objective_label: string; strategy?: { id: string | null; version: number | null } };
const meta = (r: ViewProps["result"]) => r.meta as unknown as OptMeta;
const f2 = (v: number) => v.toFixed(2);

/** Objective over two chosen parameters; the plateau region is outlined. Other parameters show their best value per cell pair. */
export function ParamMap({ rows, result }: ViewProps) {
  const m = meta(result);
  const names = m.parameters;
  const cells = (result.tables.cells ?? []) as Record<string, number | null>[];
  const [ax, setAx] = useState<[string, string]>([names[0], names[1] ?? names[0]]);
  const grid = useMemo(() => {
    const xs = [...new Set(cells.map((c) => c[ax[0]] as number))].sort((a, b) => a - b);
    const ys = [...new Set(cells.map((c) => c[ax[1]] as number))].sort((a, b) => a - b);
    const v: (number | null)[][] = ys.map(() => xs.map(() => null));
    for (const c of cells) {
      const i = ys.indexOf(c[ax[1]] as number), j = xs.indexOf(c[ax[0]] as number);
      if (isNum(c.score) && (v[i][j] === null || c.score > (v[i][j] as number))) v[i][j] = c.score;
    }
    return { xs, ys, v };
  }, [cells, ax]);
  if (!rows.length) return <Skipped reason="no cells" />;
  if (grid.xs.length * grid.ys.length > 900) return <Skipped reason="too many distinct values for a map; use the table" />;
  const reg = m.plateau.status === "plateau" ? m.plateau.region : undefined;
  const inside = (val: number, k: string) => !!reg?.[k] && val >= reg[k][0] && val <= reg[k][1];
  const send = () => {
    const sid = m.strategy?.id;
    if (!sid || !m.plateau.centre) return;
    void studio<{ spec: { params: Record<string, { value: number }> } }>("GET", `/strategies/${sid}`).then((s) => {
      const params = Object.fromEntries(Object.entries(s.spec.params).map(([k, p]) => [k, { ...p, value: m.plateau.centre?.[k] ?? p.value }]));
      return studio<{ latest: number }>("PUT", `/strategies/${sid}`, { spec: { ...s.spec, params } });
    }).then((s) => toast.success(`Saved as version ${s.latest}`), (e) => toast.error(e instanceof Error ? e.message : "Failed"));
  };
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {names.length > 2 ? [0, 1].map((i) => (
          <select key={i} className="input" style={{ width: "auto" }} aria-label={i ? "Rows" : "Columns"} value={ax[i]} onChange={(e) => setAx(i ? [ax[0], e.target.value] : [e.target.value, ax[1]])}>
            {names.map((n) => <option key={n}>{n}</option>)}
          </select>
        )) : null}
        <span style={{ flex: 1 }} />
        {m.plateau.status === "plateau" && m.strategy?.id ? <button className="btn sm" onClick={send}>Send plateau centre to Build</button> : null}
      </div>
      <Heatmap rows={grid.ys.map(String)} cols={grid.xs.map(String)} values={grid.v} format={f2} rowTitle={ax[1]} colTitle={ax[0]}
        outline={(r, c) => inside(grid.ys[r], ax[1]) && inside(grid.xs[c], ax[0])} />
    </div>
  );
}

export function Importance({ rows }: ViewProps) {
  if (!rows.length) return <Skipped reason="needs at least 3 cells that differ" />;
  return <Bars bars={rows.map((r) => ({ label: String(r.parameter), value: r.share as number }))} format={(v) => pct(v, 0)} signed={false} yLabel="Share of variance" height={200} />;
}

export function Pareto({ rows, result }: ViewProps) {
  const cells = (result.tables.cells ?? []) as Record<string, number | null>[];
  const on = new Set(rows.map((r) => JSON.stringify(meta(result).parameters.map((k) => r[k]))));
  const pts = cells.filter((c) => isNum(c.sharpe) && isNum(c.max_drawdown)).map((c) => {
    const key = JSON.stringify(meta(result).parameters.map((k) => c[k]));
    return { x: c.max_drawdown as number, y: c.sharpe as number, group: on.has(key) ? "Best trade-off" : "Other cells", emphasis: on.has(key),
      detail: meta(result).parameters.map((k) => [k, String(c[k])] as [string, string]) };
  });
  return <XYPlot points={pts} xLabel="Worst drawdown" yLabel="Sharpe" formatX={(v) => pct(v, 0)} formatY={f2} height={260} groupColors={{ "Best trade-off": "var(--accent)", "Other cells": "var(--text-4)" }} />;
}
