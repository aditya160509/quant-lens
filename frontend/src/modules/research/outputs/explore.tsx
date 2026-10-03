"use client";

import { useMemo } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { Bars } from "@/charts/Bars";
import { parseDate } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { Diverging } from "@/charts/Diverging";
import { Heatmap } from "@/charts/Heatmap";
import { TimeSeries } from "@/charts/TimeSeries";
import { XYPlot } from "@/charts/XYPlot";
import { label } from "../format";
import { DataTable } from "./tables";

/**
 * "View as": any output can be re-drawn as any chart its columns support, with the
 * columns, grouping, sorting and transforms chosen by the reader. Choices persist per card.
 */

type Row = Record<string, unknown>;
type ColKind = "number" | "date" | "text" | "bool";
export type ViewKind = "line" | "area" | "step" | "bars" | "hbars" | "scatter" | "histogram" | "heatmap" | "table";
export type ExploreConfig = {
  kind: ViewKind;
  x?: string;
  ys?: string[];
  group?: string;
  sort?: "none" | "asc" | "desc";
  limit?: number;
  transform?: "none" | "cumulative" | "rebase" | "zscore" | "rank";
  zeroFill?: boolean;
};

export const VIEW_LABEL: Record<ViewKind, string> = {
  line: "Line", area: "Area", step: "Step", bars: "Columns", hbars: "Bars (diverging)",
  scatter: "Scatter", histogram: "Histogram", heatmap: "Heatmap", table: "Table",
};

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Column types, judged on the first 200 rows so wide outputs stay cheap. */
export function profile(rows: Row[]): Record<string, ColKind> {
  const sample = rows.slice(0, 200);
  const cols = [...new Set(sample.flatMap((r) => Object.keys(r)))];
  const out: Record<string, ColKind> = {};
  for (const c of cols) {
    const vals = sample.map((r) => r[c]).filter((v) => v !== null && v !== undefined && v !== "");
    if (!vals.length) continue;
    if (vals.every((v) => typeof v === "boolean")) out[c] = "bool";
    else if (vals.every(isNum)) out[c] = "number";
    else if (vals.every((v) => typeof v === "string" && /^\d{4}-\d{2}(-\d{2})?/.test(v) && parseDate(v) !== null)) out[c] = "date";
    else if (vals.every((v) => typeof v === "string" || typeof v === "number")) out[c] = "text";
  }
  return out;
}

/** The chart kinds this output's columns can support, best first. */
export function viewsFor(rows: Row[]): ViewKind[] {
  const p = profile(rows);
  const nums = Object.keys(p).filter((c) => p[c] === "number");
  const dates = Object.keys(p).filter((c) => p[c] === "date");
  const cats = Object.keys(p).filter((c) => p[c] === "text");
  const v: ViewKind[] = [];
  if (!nums.length) return ["table"];
  if (dates.length || nums.length >= 2) v.push("line", "area", "step");
  if (cats.length || rows.length <= 60) v.push("bars", "hbars");
  if (nums.length >= 2) v.push("scatter");
  if (rows.length >= 8) v.push("histogram");
  if (cats.length >= 2 || (cats.length >= 1 && nums.length >= 2)) v.push("heatmap");
  v.push("table");
  return v;
}

/** Sensible starting columns for a kind, so switching views never shows an empty chart. */
export function defaults(rows: Row[], kind: ViewKind): ExploreConfig {
  const p = profile(rows);
  const nums = Object.keys(p).filter((c) => p[c] === "number");
  const dates = Object.keys(p).filter((c) => p[c] === "date");
  const cats = Object.keys(p).filter((c) => p[c] === "text");
  const timeX = dates[0] ?? nums[0];
  switch (kind) {
    case "line": case "area": case "step":
      return { kind, x: timeX, ys: nums.filter((c) => c !== timeX).slice(0, 3), transform: "none" };
    case "bars": case "hbars":
      return { kind, x: cats[0] ?? dates[0] ?? nums[0], ys: [nums.find((c) => c !== (cats[0] ?? nums[0])) ?? nums[0]], sort: kind === "hbars" ? "desc" : "none", limit: 40 };
    case "scatter":
      return { kind, x: nums[0], ys: [nums[1] ?? nums[0]], group: cats[0] };
    case "histogram":
      return { kind, ys: [nums[0]] };
    case "heatmap":
      return { kind, x: cats[1] ?? undefined, group: cats[0], ys: cats[1] ? [nums[0]] : nums.slice(0, 8) };
    default:
      return { kind: "table" };
  }
}

type Store = { configs: Record<string, ExploreConfig>; set: (id: string, c: ExploreConfig | null) => void };
export const useExplore = create<Store>()(persist((set) => ({
  configs: {},
  set: (id, c) => set((s) => {
    const { [id]: _, ...rest } = s.configs;
    void _;
    return { configs: c ? { ...rest, [id]: c } : rest };
  }),
}), { name: "research-explore", storage: createJSONStorage(() => localStorage) }));

function transformed(rows: Row[], ys: string[], t: ExploreConfig["transform"]): Row[] {
  if (!t || t === "none") return rows;
  const out = rows.map((r) => ({ ...r }));
  for (const y of ys) {
    const vals = out.map((r) => (isNum(r[y]) ? (r[y] as number) : null));
    if (t === "cumulative") { let acc = 0; out.forEach((r, i) => { const v = vals[i]; if (v !== null) { acc += v; r[y] = acc; } }); }
    if (t === "rebase") { const base = vals.find((v) => v !== null && v !== 0); if (base) out.forEach((r, i) => { const v = vals[i]; if (v !== null) r[y] = (v / base) * 100; }); }
    if (t === "zscore") {
      const f = vals.filter((v): v is number => v !== null); const m = f.reduce((a, b) => a + b, 0) / (f.length || 1);
      const sd = Math.sqrt(f.reduce((a, b) => a + (b - m) ** 2, 0) / Math.max(1, f.length - 1)) || 1;
      out.forEach((r, i) => { const v = vals[i]; if (v !== null) r[y] = (v - m) / sd; });
    }
    if (t === "rank") {
      const order = vals.map((v, i) => [v, i] as const).filter(([v]) => v !== null).sort((a, b) => (a[0] as number) - (b[0] as number));
      order.forEach(([, i], k) => { out[i][y] = order.length > 1 ? k / (order.length - 1) : 0.5; });
    }
  }
  return out;
}

/** Series label; keeps the overlay suffix " · B" upper-case. */
const seriesLabel = (y: string) => (y.endsWith(" · B") ? `${label(y.slice(0, -4))} · B` : label(y));

const text = (v: unknown) => (v === null || v === undefined ? "–" : typeof v === "string" ? v : String(v));

/** Draws rows the way the config says. */
export function Explore({ rows, config }: { rows: Row[]; config: ExploreConfig }) {
  const { kind, x, ys = [], group, sort = "none", limit, transform } = config;
  const data = useMemo(() => transformed(rows, ys, transform), [rows, ys, transform]);
  if (!rows.length) return null;

  if (kind === "table") return <DataTable rows={rows} />;

  if (kind === "line" || kind === "area" || kind === "step") {
    const p = profile(rows);
    const xKey = x ?? "date";
    if (p[xKey] === "date") {
      return <TimeSeries data={data} x={xKey} height={280} zeroFill={config.zeroFill}
        series={ys.map((y) => ({ key: y, label: seriesLabel(y), kind, dash: y.endsWith(" · B") }))} refLines={transform === "rebase" ? [{ y: 100, dash: true }] : undefined} />;
    }
    // Numeric x: ordered line through the points.
    const sorted = [...data].filter((r) => isNum(r[xKey])).sort((a, b) => (a[xKey] as number) - (b[xKey] as number));
    return <XYPlot points={[]} xLabel={label(xKey)} yLabel={ys.map(label).join(", ")} height={280}
      lines={ys.map((y) => ({ label: seriesLabel(y), dash: y.endsWith(" · B"), points: sorted.filter((r) => isNum(r[y])).map((r) => ({ x: r[xKey] as number, y: r[y] as number })) }))} />;
  }

  if (kind === "bars" || kind === "hbars") {
    const y = ys[0];
    let items = data.filter((r) => isNum(r[y])).map((r) => ({ label: x ? label(text(r[x])) : "", value: r[y] as number }));
    if (sort !== "none") items = items.sort((a, b) => (sort === "asc" ? a.value - b.value : b.value - a.value));
    if (limit) items = items.slice(0, limit);
    if (kind === "hbars") return <Diverging rows={items} />;
    return <Bars bars={items} height={260} yLabel={label(y)} hideLabels={items.length > 30} />;
  }

  if (kind === "scatter") {
    const xKey = x as string, y = ys[0];
    const pts = data.filter((r) => isNum(r[xKey]) && isNum(r[y])).map((r) => ({ x: r[xKey] as number, y: r[y] as number, group: group ? text(r[group]) : undefined }));
    return <XYPlot points={pts} xLabel={label(xKey)} yLabel={label(y)} height={300} robust />;
  }

  if (kind === "histogram") {
    const y = ys[0];
    return <Distribution values={data.map((r) => r[y]).filter(isNum)} xLabel={label(y)} observed={null} format={(v) => Number(v.toPrecision(3)).toString()} />;
  }

  // Heatmap: either long form (row cat × col cat → value) or wide form (row cat × numeric columns).
  const rowKey = group as string;
  if (x) {
    const y = ys[0];
    const rs = [...new Set(data.map((r) => text(r[rowKey])))], cs = [...new Set(data.map((r) => text(r[x])))];
    const cell = new Map(data.map((r) => [`${text(r[rowKey])}|${text(r[x])}`, isNum(r[y]) ? (r[y] as number) : null]));
    return <Heatmap rows={rs.map(label)} cols={cs.map(label)} values={rs.map((a) => cs.map((b) => cell.get(`${a}|${b}`) ?? null))} rowTitle={label(rowKey)} colTitle={label(x)} />;
  }
  const take = data.slice(0, limit ?? 40);
  return <Heatmap rows={take.map((r) => label(text(r[rowKey])))} cols={ys.map(label)} values={take.map((r) => ys.map((c) => (isNum(r[c]) ? (r[c] as number) : null)))} rowTitle={label(rowKey)} />;
}

/** Column and transform pickers for the chosen view. */
export function ExploreControls({ rows, config, onChange }: { rows: Row[]; config: ExploreConfig; onChange: (c: ExploreConfig) => void }) {
  const p = profile(rows);
  const cols = Object.keys(p);
  const nums = cols.filter((c) => p[c] === "number");
  const cats = cols.filter((c) => p[c] !== "number");
  const k = config.kind;
  const sel = (name: string, value: string | undefined, options: string[], set: (v: string | undefined) => void, allowNone = false) => (
    <label className="xc">
      <span>{name}</span>
      <select value={value ?? ""} onChange={(e) => set(e.target.value || undefined)}>
        {allowNone ? <option value="">None</option> : null}
        {options.map((o) => <option key={o} value={o}>{label(o)}</option>)}
      </select>
    </label>
  );
  const toggleY = (c: string) => {
    const cur = config.ys ?? [];
    const multi = k === "line" || k === "area" || k === "step" || (k === "heatmap" && !config.x);
    onChange({ ...config, ys: multi ? (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]) : [c] });
  };
  if (k === "table") return null;
  return (
    <div className="xctl">
      {k !== "histogram" && !(k === "heatmap" && !config.x) ? sel(k === "heatmap" ? "Columns" : "X", config.x, k === "scatter" ? nums : k === "heatmap" ? cats : cols, (v) => onChange({ ...config, x: v }), k === "heatmap") : null}
      {k === "scatter" || k === "heatmap" ? sel(k === "heatmap" ? "Rows" : "Colour", config.group, cats, (v) => onChange({ ...config, group: v }), k === "scatter") : null}
      <div className="xc ys">
        <span>{k === "line" || k === "area" || k === "step" || (k === "heatmap" && !config.x) ? "Series" : "Value"}</span>
        <div className="xpills">
          {nums.slice(0, 16).map((c) => (
            <button key={c} type="button" className="pill" aria-pressed={(config.ys ?? []).includes(c)} onClick={() => toggleY(c)}>{label(c)}</button>
          ))}
        </div>
      </div>
      {k === "line" || k === "area" || k === "step" ? sel("Transform", config.transform ?? "none", ["none", "cumulative", "rebase", "zscore", "rank"], (v) => onChange({ ...config, transform: (v ?? "none") as ExploreConfig["transform"] })) : null}
      {k === "area" ? (
        <label className="xc"><span>Fill</span><button type="button" className="pill" aria-pressed={Boolean(config.zeroFill)} onClick={() => onChange({ ...config, zeroFill: !config.zeroFill })}>Green / red at zero</button></label>
      ) : null}
      {k === "bars" || k === "hbars" ? (
        <>
          {sel("Sort", config.sort ?? "none", ["none", "desc", "asc"], (v) => onChange({ ...config, sort: (v ?? "none") as ExploreConfig["sort"] }))}
          {sel("Show", String(config.limit ?? 40), ["10", "20", "40", "100", "1000"], (v) => onChange({ ...config, limit: Number(v) }))}
        </>
      ) : null}
    </div>
  );
}

/**
 * Two runs of the same output on one time axis: run B's numeric columns are added with a " · B"
 * suffix, joined on the shared date (or first) column. Returns the merged rows and the line config.
 */
export function overlay(a: Row[], b: Row[]): { rows: Row[]; config: ExploreConfig } | null {
  const p = profile(a);
  const x = Object.keys(p).find((c) => p[c] === "date") ?? Object.keys(p).find((c) => p[c] === "number");
  if (!x) return null;
  const ys = Object.keys(p).filter((c) => p[c] === "number" && c !== x).slice(0, 2);
  if (!ys.length) return null;
  const byX = new Map<string, Row>();
  for (const r of a) byX.set(String(r[x]), { [x]: r[x], ...Object.fromEntries(ys.map((y) => [y, r[y]])) });
  for (const r of b) {
    const k = String(r[x]);
    const row = byX.get(k) ?? { [x]: r[x] };
    for (const y of ys) row[`${y} · B`] = r[y];
    byX.set(k, row);
  }
  const rows = [...byX.values()].sort((m, n) => (String(m[x]) < String(n[x]) ? -1 : 1));
  return { rows, config: { kind: "line", x, ys: ys.flatMap((y) => [y, `${y} · B`]) } };
}
