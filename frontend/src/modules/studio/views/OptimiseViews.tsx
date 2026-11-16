"use client";

import { useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Bars } from "@/charts/Bars";
import { Heatmap } from "@/charts/Heatmap";
import { TimeSeries } from "@/charts/TimeSeries";
import { XYPlot } from "@/charts/XYPlot";
import { Distribution } from "@/charts/Distribution";
import { PlotlyChart } from "@/components/ui/plotly-chart";
import { isNum, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { studio } from "../api";
import { Skipped } from "./BacktestViews";

type Plateau = { status: string; reason?: string; centre?: Record<string, number>; region?: Record<string, [number, number]>; centre_score?: number; best_score?: number };
type OptMeta = { plateau: Plateau; parameters: string[]; objective_label: string; strategy?: { id: string | null; version: number | null }; stability: { radius: number; cells: number; within_20pct: number } | null; spread_labels: string[] };
const meta = (r: ViewProps["result"]) => r.meta as unknown as OptMeta;
const f2 = (v: number) => v.toFixed(2);

/** Objective over two chosen parameters; the plateau region is outlined. Other parameters show their best value per cell pair. */
export function ParamMap({ rows, result }: ViewProps) {
  const m = meta(result);
  const names = m.parameters;
  const cells = (result.tables.cells ?? []) as Record<string, number | null>[];
  const [ax, setAx] = useState<[string, string]>([names[0], names[1] ?? names[0]]);
  const [three, setThree] = useState(false);
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
        {names.length > 1 ? <label className="st-toggle"><input type="checkbox" checked={three} onChange={(e) => setThree(e.target.checked)} />3D</label> : null}
        {m.plateau.status === "plateau" && m.strategy?.id ? <button className="btn sm" onClick={send}>Send plateau centre to Build</button> : null}
      </div>
      {three ? (
        <PlotlyChart className="op-3d" style={{ width: "100%", height: 420 }} config={{ displaylogo: false, responsive: true, scrollZoom: false }}
          data={[{ type: "surface", x: grid.xs, y: grid.ys, z: grid.v, colorscale: "Viridis", showscale: false, hovertemplate: `${ax[0]} %{x}<br>${ax[1]} %{y}<br>${m.objective_label} %{z:.2f}<extra></extra>` }]}
          layout={{ margin: { l: 0, r: 0, t: 0, b: 0 }, paper_bgcolor: "rgba(0,0,0,0)", font: { color: "#9aa0a6", size: 11 },
            scene: { xaxis: { title: { text: ax[0] } }, yaxis: { title: { text: ax[1] } }, zaxis: { title: { text: m.objective_label } } } }} />
      ) : (
        <Heatmap rows={grid.ys.map(String)} cols={grid.xs.map(String)} values={grid.v} format={f2} rowTitle={ax[1]} colTitle={ax[0]}
          outline={(r, c) => inside(grid.ys[r], ax[1]) && inside(grid.xs[c], ax[0])} />
      )}
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

/** Cells around the plateau centre: share within 20% of the best, and how their scores spread. */
export function Stability({ rows, result }: ViewProps) {
  const st = meta(result).stability;
  const v = rows.map((r) => r.score).filter(isNum);
  if (!st || v.length < 2) return <Skipped reason="too few cells near the centre" />;
  const share = st.within_20pct, C = Math.PI * 46;
  return (
    <div className="op-stab">
      <svg viewBox="0 0 120 70" width={150} height={88} role="img" aria-label={`${pct(share, 0)} of neighbours within 20% of the best`}>
        <path d="M14 62 A46 46 0 0 1 106 62" fill="none" stroke="var(--line-2)" strokeWidth={10} />
        <path d="M14 62 A46 46 0 0 1 106 62" fill="none" stroke={share >= 0.7 ? "var(--up)" : share >= 0.4 ? "var(--warn)" : "var(--down)"} strokeWidth={10} strokeDasharray={`${share * C} ${C}`} />
        <text x={60} y={58} textAnchor="middle" className="bt-rule-n">{pct(share, 0)}</text>
      </svg>
      <Distribution values={v} observed={Math.max(...v)} tail="two" xLabel={`${meta(result).objective_label} of the ${st.cells} cells within ${st.radius} step${st.radius > 1 ? "s" : ""}`} observedLabel="Best" format={f2} />
    </div>
  );
}

/** Equity of every setting on the plateau; the best is drawn bold. */
export function Spread({ rows, result }: ViewProps) {
  const labels = meta(result).spread_labels ?? [];
  if (!labels.length) return <Skipped reason="no plateau cells" />;
  return <TimeSeries data={rows} series={labels.map((l, j) => ({ key: `c${j}`, label: l, color: j ? "var(--text-4)" : "var(--accent)", width: j ? 1 : 2.5, muted: j > 0 }))} height={260} legend={false}
    format={(v) => `$${Math.round(v).toLocaleString()}`} />;
}
