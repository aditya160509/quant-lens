"use client";

import { useMemo, useState, type ReactNode } from "react";
import { Bars } from "@/charts/Bars";
import { Beeswarm } from "@/charts/Beeswarm";
import { Dendrogram, leafOrder, type Merge } from "@/charts/Dendrogram";
import { Distribution } from "@/charts/Distribution";
import { Diverging } from "@/charts/Diverging";
import { Forest } from "@/charts/Forest";
import { Heatmap } from "@/charts/Heatmap";
import { Network } from "@/charts/Network";
import { StackedArea } from "@/charts/StackedArea";
import { TimeSeries, type Series } from "@/charts/TimeSeries";
import { Waterfall } from "@/charts/Waterfall";
import { XYPlot } from "@/charts/XYPlot";
import { SERIES, parseDate } from "@/charts/core";
import { Segmented } from "@/workspace/ui";
import { useRuns } from "@/modules/research/api";
import { isNum, label, out, pct } from "@/modules/research/format";
import { DataTable, Empty } from "@/modules/research/outputs/tables";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { Row } from "@/modules/research/types";

/* ---------------------------------------------------------------- helpers */

const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const n = (v: unknown) => (isNum(v) ? v : null);
const vals = (rows: Row[], k: string) => rows.map((r) => r[k]).filter(isNum);
const mean = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
const quantile = (sorted: number[], q: number) => (sorted.length ? sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(q * (sorted.length - 1))))] : NaN);
const sig = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(2) : Math.abs(v) >= 0.01 ? v.toFixed(3) : Number(v.toPrecision(2)).toString());
const pctFmt = (v: number) => `${(v * 100).toFixed(Math.abs(v) < 0.1 ? 2 : 1)}%`;

/** Long rows (x, series, y) to wide rows (x, one column per series), in first-seen series order. */
export function pivot(rows: Row[], x: string, s: string, y: string): { data: Row[]; keys: string[] } {
  const keys: string[] = [];
  const by = new Map<string, Row>();
  for (const r of rows) {
    const k = str(r[s]);
    if (!keys.includes(k)) keys.push(k);
    const xv = str(r[x]);
    const row = by.get(xv) ?? { [x]: r[x] };
    row[k] = r[y];
    by.set(xv, row);
  }
  const data = [...by.values()].sort((a, b) => ((parseDate(a[x]) ?? Number(a[x])) - (parseDate(b[x]) ?? Number(b[x]))));
  return { data, keys };
}

/** The settings this run was submitted with, from the local run history. */
function usePayload(scope: string): Record<string, unknown> {
  const jobId = scope.split(":")[1];
  return useRuns((s) => s.runs.find((r) => r.jobId === jobId)?.payload) ?? {};
}

function Stats({ items }: { items: [string, ReactNode, string?][] }) {
  return (
    <div className="ml-stats">
      {items.map(([l, v, tone]) => <div key={l}><span>{l}</span><b className="num" style={tone ? { color: tone } : undefined}>{v}</b></div>)}
    </div>
  );
}

function Picker<T extends string | number>({ label: l, value, options, onChange }: { label: string; value: T; options: T[]; onChange: (v: T) => void }) {
  if (options.length < 2) return null;
  return options.length <= 6
    ? <Segmented<T> label={l} value={value} onChange={onChange} options={options.map((o) => ({ value: o, label: typeof o === "string" ? o : String(o) }))} />
    : <select className="input" style={{ height: 28, width: "auto" }} aria-label={l} value={String(value)} onChange={(e) => onChange(options.find((o) => String(o) === e.target.value) as T)}>{options.map((o) => <option key={String(o)}>{String(o)}</option>)}</select>;
}

const Bar = ({ children }: { children: ReactNode }) => <div className="ml-bar">{children}</div>;

/* ---------------------------------------------------------------- generic, driven by the contract's encoding */

/** Any output the contract describes: its type and column roles pick the chart. */
export function MlAuto({ rows, spec, opts }: ViewProps) {
  const e = (spec?.encoding ?? {}) as { x?: string; y?: string; series?: string; value?: string | string[]; bin?: boolean };
  const type = spec?.type ?? "table";
  if (!rows.length) return <Empty />;
  if (type === "kpi") return <MlKpiRows rows={rows} />;
  if (type === "timeseries" && e.x) {
    if (e.series && e.y) {
      const { data, keys } = pivot(rows, e.x, e.series, e.y);
      return <TimeSeries data={data} x={e.x} height={280} series={keys.map((k, i) => ({ key: k, label: k, muted: keys.length > 8 && i >= 6 }))} />;
    }
    const ys = (e.y ? [e.y] : Object.keys(rows[0]).filter((k) => k !== e.x && isNum(rows[0][k]))).slice(0, 4);
    return <TimeSeries data={rows} x={e.x} height={260} series={ys.map((y) => ({ key: y, label: label(y) }))} refLines={[{ y: 0, color: "var(--line-3)" }]} />;
  }
  if (type === "bar" && e.bin && e.x) return <Distribution values={vals(rows, e.x)} xLabel={label(e.x)} observed={null} format={sig} />;
  if (type === "bar" && e.x && e.y) {
    const items = rows.filter((r) => isNum(r[e.y!])).map((r) => ({ label: label(str(r[e.x!])), value: r[e.y!] as number }));
    return items.length > 14 ? <Diverging rows={items.sort((a, b) => b.value - a.value)} format={sig} /> : <Bars bars={items} format={sig} yLabel={label(e.y)} />;
  }
  if (type === "scatter" && e.x && e.y) {
    const pts = rows.filter((r) => isNum(r[e.x!]) && isNum(r[e.y!])).map((r) => ({ x: r[e.x!] as number, y: r[e.y!] as number, group: e.series ? str(r[e.series]) : undefined }));
    return <XYPlot points={pts} xLabel={label(e.x)} yLabel={label(e.y)} robust />;
  }
  if (type === "heatmap") return <LongHeatmap rows={rows} />;
  return <DataTable rows={rows} opts={opts} />;
}

function LongHeatmap({ rows, format = sig, rowKey = "row", colKey = "col", valueKey = "value" }: { rows: Row[]; format?: (v: number) => string; rowKey?: string; colKey?: string; valueKey?: string }) {
  const rs = [...new Set(rows.map((r) => str(r[rowKey])))], cs = [...new Set(rows.map((r) => str(r[colKey])))];
  const cell = new Map(rows.map((r) => [`${str(r[rowKey])}|${str(r[colKey])}`, n(r[valueKey])]));
  return <Heatmap rows={rs.map(label)} cols={cs.map(label)} values={rs.map((a) => cs.map((b) => cell.get(`${a}|${b}`) ?? null))} format={format} />;
}

/** Headline figures; an unavailable figure says why instead of showing a number. */
function MlKpiRows({ rows }: { rows: Row[] }) {
  const r = rows[0];
  const unavailable = r.status === "unavailable" || r.status === "conditional";
  const items = Object.entries(r).filter(([k, v]) => isNum(v) && k !== "status");
  return (
    <div>
      {items.length ? <Stats items={items.map(([k, v]) => [label(k), sig(v as number)])} /> : null}
      {unavailable ? <p className="ml-note"><b>{label(str(r.status))}.</b> {str(r.reason)}</p> : null}
    </div>
  );
}
export const MlKpi = ({ rows }: ViewProps) => (rows.length ? <MlKpiRows rows={rows} /> : <Empty />);

/** Key/value receipt: what the model was trained on, when and how. */
export function MlReceipt({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  if (rows.length > 1) return <DataTable rows={rows} />;
  const flat = Object.entries(rows[0]).flatMap(([k, v]) => (v && typeof v === "object" && !Array.isArray(v) ? Object.entries(v as Row).map(([k2, v2]) => [`${k} · ${k2}`, v2] as const) : [[k, v] as const]));
  return (
    <dl className="ml-receipt">
      {flat.map(([k, v]) => <div key={k}><dt>{label(k)}</dt><dd className="num">{isNum(v) ? (Number.isInteger(v) ? v.toLocaleString() : sig(v)) : typeof v === "boolean" ? (v ? "Yes" : "No") : Array.isArray(v) ? v.join(", ") : str(v) || "–"}</dd></div>)}
    </dl>
  );
}

/* ---------------------------------------------------------------- performance */

/** Equity curve, drawdown underneath, and the figures a reader checks first. Net of costs. */
export function MlEquity({ rows }: ViewProps) {
  const data = useMemo(() => {
    const outRows: Row[] = [];
    let peak = -Infinity;
    for (const r of rows) { const e = n(r.equity) ?? NaN; peak = Math.max(peak, e); outRows.push({ ...r, drawdown: Number.isFinite(e) ? e / peak - 1 : null }); }
    return outRows;
  }, [rows]);
  if (!rows.length) return <Empty />;
  const net = vals(rows, "net_return");
  const sd = Math.sqrt(mean(net.map((x) => (x - mean(net)) ** 2)));
  const sharpe = sd > 0 ? (mean(net) / sd) * Math.sqrt(252) : NaN;
  const eq = vals(rows, "equity");
  const years = rows.length / 252;
  const cagr = eq.length ? (eq[eq.length - 1] / (eq[0] || 1)) ** (1 / Math.max(years, 1e-9)) - 1 : NaN;
  const mdd = Math.min(...vals(data, "drawdown"));
  const turnover = mean(vals(rows, "turnover").filter((t) => t > 0));
  const costs = vals(rows, "cost_fraction").reduce((a, b) => a + b, 0);
  return (
    <div>
      <Stats items={[["Annual return", pctFmt(cagr), cagr >= 0 ? "var(--up)" : "var(--down)"], ["Sharpe (net)", Number.isFinite(sharpe) ? sharpe.toFixed(2) : "–"], ["Max drawdown", pctFmt(mdd), "var(--down)"], ["Avg turnover", Number.isFinite(turnover) ? pctFmt(turnover) : "–"], ["Total costs", pctFmt(costs)]]} />
      <TimeSeries data={data} x="date" height={230} series={[{ key: "equity", label: "Equity (net)", kind: "area" }]} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />
      <TimeSeries data={data} x="date" height={110} series={[{ key: "drawdown", label: "Drawdown", kind: "area", color: "var(--down)" }]} format={pctFmt} legend={false} />
    </div>
  );
}

/* ---------------------------------------------------------------- F01 CPCV */

/** Every CPCV path's Sharpe as a dot, with the spread and the overfitting tests beside it. */
export function MlSharpeSpread({ rows, result }: ViewProps) {
  const s = vals(rows, "sharpe").sort((a, b) => a - b);
  const pbo = out(result, "probability_of_backtest_overfitting")[0];
  const naive = out(result, "purged_vs_naive_cv_comparison");
  if (!s.length) return <Empty />;
  const purged = n(naive.find((r) => /purged/.test(str(r.method)))?.sharpe), nv = n(naive.find((r) => /naive/.test(str(r.method)))?.sharpe);
  return (
    <div>
      <Stats items={[["Paths", s.length], ["Median Sharpe", sig(quantile(s, 0.5))], ["Worst", sig(s[0]), s[0] < 0 ? "var(--down)" : undefined], ["Best", sig(s[s.length - 1])], ["Share > 0", pct(s.filter((x) => x > 0).length / s.length, 0)],
        ...(purged !== null && nv !== null ? [["Leakage gap", sig(nv - purged), nv - purged > 0 ? "var(--warn)" : undefined] as [string, string, string?]] : [])]} />
      {s.length >= 12 ? <Distribution values={s} observed={quantile(s, 0.5)} observedLabel="Median" xLabel="Annualised Sharpe by path" format={sig} />
        : <Bars bars={rows.filter((r) => isNum(r.sharpe)).map((r, i) => ({ label: `Path ${i + 1}`, value: r.sharpe as number })).sort((a, b) => a.value - b.value)} format={sig} height={200} refLines={[{ y: quantile(s, 0.5), label: "median" }]} yLabel="Annualised Sharpe" />}
      {pbo && (pbo.status === "unavailable" || pbo.pbo === null) ? <p className="ml-note"><b>PBO and deflated Sharpe not computed.</b> {str(pbo.reason)}. CPCV paths are not strategy trials, so they cannot be used for it.</p> : null}
    </div>
  );
}

/** All CPCV paths faint, the median bold, the 10–90% band shaded: the honest picture is the spread. */
export function MlPathFan({ rows }: ViewProps) {
  const { data, keys } = useMemo(() => {
    const p = pivot(rows, "date", "path", "equity");
    const data = p.data.map((r) => {
      const v = p.keys.map((k) => r[k]).filter(isNum).sort((a, b) => a - b);
      return { ...r, median: quantile(v, 0.5), lo: quantile(v, 0.1), hi: quantile(v, 0.9) };
    });
    return { data, keys: p.keys };
  }, [rows]);
  if (!rows.length) return <Empty />;
  const series: Series[] = [...keys.map((k) => ({ key: k, label: `Path ${k}`, muted: true })), { key: "median", label: "Median path", width: 2.2 }];
  return <TimeSeries data={data} x="date" height={300} series={series} band={{ lo: "lo", hi: "hi", label: "10–90% of paths" }} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />;
}

/** Which date groups trained and tested in each split, and how much was purged around the test blocks. */
export function MlFoldMatrix({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const groups = Math.max(...rows.flatMap((r) => (Array.isArray(r.test_groups) ? (r.test_groups as number[]) : []))) + 1;
  const purged = vals(rows, "purged_observations");
  return (
    <div>
      <Stats items={[["Splits", rows.length], ["Date groups", groups], ["Purged per split", purged.length ? Math.round(mean(purged)).toLocaleString() : "–"], ["Embargo", `${str(rows[0].embargo_sessions)} sessions`]]} />
      <div className="ml-folds" style={{ gridTemplateColumns: `64px repeat(${groups}, 1fr) 70px 70px` }}>
        <span className="h">Split</span>{Array.from({ length: groups }, (_, g) => <span key={g} className="h">G{g + 1}</span>)}<span className="h r">Purged SR</span><span className="h r">Naive SR</span>
        {rows.map((r) => {
          const test = new Set(Array.isArray(r.test_groups) ? (r.test_groups as number[]) : []);
          return [
            <span key="s" className="num">{str(r.split)}</span>,
            ...Array.from({ length: groups }, (_, g) => {
              const edge = !test.has(g) && (test.has(g - 1) || test.has(g + 1));
              return <i key={g} className={test.has(g) ? "test" : edge ? "purge" : "train"} title={test.has(g) ? "Test" : edge ? "Train, purged and embargoed next to the test block" : "Train"} />;
            }),
            <span key="p" className="num r" style={{ color: (n(r.purged_sharpe) ?? 0) >= 0 ? "var(--up)" : "var(--down)" }}>{isNum(r.purged_sharpe) ? r.purged_sharpe.toFixed(2) : "–"}</span>,
            <span key="n" className="num r" style={{ color: "var(--text-3)" }}>{isNum(r.naive_sharpe) ? r.naive_sharpe.toFixed(2) : "–"}</span>,
          ];
        })}
      </div>
      <div className="ml-legend"><i className="train" />Train<i className="purge" />Train, purge and embargo applied<i className="test" />Test</div>
    </div>
  );
}

/* ---------------------------------------------------------------- F02 alpha */

/** Today's ranking with each name's score, decile and the features that pushed it there. */
export function MlRankTable({ rows, result }: ViewProps) {
  const swarm = out(result, "shap_beeswarm");
  const drivers = useMemo(() => {
    const by = new Map<string, Row[]>();
    swarm.forEach((r) => by.set(str(r.ticker), [...(by.get(str(r.ticker)) ?? []), r]));
    return by;
  }, [swarm]);
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(a.rank) ?? 0) - (n(b.rank) ?? 0));
  const preds = vals(sorted, "prediction");
  const maxAbs = Math.max(...preds.map(Math.abs), 1e-12);
  return (
    <div className="ml-rank">
      <div className="ml-rank-h"><span>#</span><span>Ticker</span><span>Sector</span><span>Predicted return</span><span>Top drivers</span></div>
      {sorted.map((r, i) => {
        const p = n(r.prediction) ?? 0;
        const d = (drivers.get(str(r.ticker)) ?? []).filter((x) => isNum(x.shap_value)).sort((a, b) => Math.abs(b.shap_value as number) - Math.abs(a.shap_value as number)).slice(0, 3);
        return (
          <div key={str(r.ticker)} className="ml-rank-r">
            <span className="num">{i + 1}</span>
            <b>{str(r.ticker)}</b>
            <span className="muted">{str(r.sector)}</span>
            <span className="ml-rank-cell"><em className="num" style={{ color: p >= 0 ? "var(--up)" : "var(--down)" }}>{pctFmt(p)}</em><span className="ml-rank-bar"><i style={{ width: `${(Math.abs(p) / maxAbs) * 50}%`, [p >= 0 ? "left" : "right"]: "50%", background: p >= 0 ? "var(--up)" : "var(--down)" }} /></span></span>
            <span className="ml-drivers">{d.map((x) => <span key={str(x.feature)} className={(x.shap_value as number) >= 0 ? "up" : "down"}>{label(str(x.feature))}</span>)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function MlBeeswarm({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return <Beeswarm points={rows.filter((r) => isNum(r.shap_value)).map((r) => ({ row: label(str(r.feature)), value: r.shap_value as number, color: n(r.feature_value), label: str(r.ticker) }))} />;
}

export function MlWaterfall({ rows, result }: ViewProps) {
  const base = n(result.meta.shap_base_value) ?? 0;
  if (!rows.length) return <Empty />;
  return <Waterfall base={base} items={rows.filter((r) => isNum(r.shap_value)).map((r) => ({ label: label(str(r.feature)), value: r.shap_value as number }))} format={(v) => pctFmt(v)} />;
}

/** IC by month with its average: a signal that works shows more green than red, not one lucky month. */
export function MlIcBars({ rows, spec }: ViewProps) {
  const e = (spec?.encoding ?? {}) as { x?: string; y?: string };
  const x = e.x ?? (rows[0] && "month" in rows[0] ? "month" : "date");
  const y = e.y ?? Object.keys(rows[0] ?? {}).find((k) => /ic/i.test(k) && isNum(rows[0][k])) ?? "ic";
  if (!rows.length) return <Empty />;
  const v = vals(rows, y);
  const m = mean(v), sd = Math.sqrt(mean(v.map((a) => (a - m) ** 2)));
  return (
    <div>
      <Stats items={[["Mean IC", sig(m), m >= 0 ? "var(--up)" : "var(--down)"], ["IC IR", sd > 0 ? (m / sd).toFixed(2) : "–"], ["Positive", pct(v.filter((a) => a > 0).length / (v.length || 1), 0)], ["Periods", v.length]]} />
      <Bars bars={rows.filter((r) => isNum(r[y])).map((r) => ({ label: str(r[x]), value: r[y] as number }))} format={sig} refLines={[{ y: m, label: "mean" }]} hideLabels={rows.length > 24} />
    </div>
  );
}

/** Models side by side on validation and test IC, with each one's ensemble weight. */
export function MlLeaderboard({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const nameKey = ["model", "architecture", "signal", "factor"].find((k) => k in rows[0]) ?? Object.keys(rows[0])[0];
  const metric = ["test_ic", "spearman_ic", "mean_daily_ic", "validation_ic", "ic"].find((k) => k in rows[0] && isNum(rows[0][k])) ?? Object.keys(rows[0]).find((k) => isNum(rows[0][k]))!;
  const items = [...rows].filter((r) => isNum(r[metric])).sort((a, b) => (b[metric] as number) - (a[metric] as number))
    .map((r) => ({ label: label(str(r[nameKey])), value: r[metric] as number, note: Object.entries(r).filter(([k, v]) => k !== metric && isNum(v)).map(([k, v]) => `${label(k)} ${sig(v as number)}`).join(" · ") }));
  return (
    <div>
      <div className="ml-sub">{label(metric)}, best first</div>
      <Diverging rows={items} format={sig} labelWidth={150} />
    </div>
  );
}

/* ---------------------------------------------------------------- F03 volatility */

/** Forecast against what happened, one model and horizon at a time, with the forecast interval. */
export function MlVolPanel({ rows, result }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const horizons = useMemo(() => [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b), [rows]);
  const [model, setModel] = useState(models[0] ?? "");
  const [h, setH] = useState(horizons[0] ?? 1);
  const ci = out(result, "model_confidence_intervals");
  const data = useMemo(() => {
    const band = new Map(ci.filter((r) => str(r.model) === model && Number(r.horizon) === h).map((r) => [str(r.date), r]));
    return rows.filter((r) => str(r.model) === model && Number(r.horizon) === h).map((r) => ({ ...r, lower: band.get(str(r.date))?.lower ?? null, upper: band.get(str(r.date))?.upper ?? null }));
  }, [rows, ci, model, h]);
  const tour = out(result, "forecast_tournament").find((r) => str(r.model) === model && Number(r.horizon) === h);
  if (!rows.length) return <Empty />;
  return (
    <div>
      <Bar><Picker label="Model" value={model} options={models} onChange={setModel} /><Picker label="Horizon (sessions)" value={h} options={horizons} onChange={setH} /></Bar>
      {tour ? <Stats items={[["MAE", sig(n(tour.mae) ?? NaN)], ["QLIKE", sig(n(tour.qlike) ?? NaN)], ["Interval coverage", isNum(tour.interval_coverage) ? pct(tour.interval_coverage, 0) : "–"]]} /> : null}
      <TimeSeries data={data} x="date" height={280} format={pctFmt}
        series={[{ key: "realized_vol", label: "Realised", color: "var(--text-3)", width: 1 }, { key: "forecast_vol", label: `${model} forecast`, width: 1.8 }]}
        band={data.some((r) => isNum(r.lower)) ? { lo: "lower", hi: "upper", label: "Forecast interval" } : undefined} />
    </div>
  );
}

export function MlVolScatter({ rows }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const horizons = useMemo(() => [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b), [rows]);
  const [h, setH] = useState(horizons[0] ?? 1);
  if (!rows.length) return <Empty />;
  const pts = rows.filter((r) => Number(r.horizon) === h && isNum(r.forecast_vol) && isNum(r.realized_vol)).map((r) => ({ x: r.forecast_vol as number, y: r.realized_vol as number, group: str(r.model) }));
  return (
    <div>
      <Bar><Picker label="Horizon" value={h} options={horizons} onChange={setH} /></Bar>
      <XYPlot points={pts} xLabel="Forecast volatility" yLabel="Realised volatility" diagonal robust formatX={pctFmt} formatY={pctFmt}
        groupColors={Object.fromEntries(models.map((m, i) => [m, SERIES[i % SERIES.length]]))} />
    </div>
  );
}

/** Forecast volatility across horizons, per model: the term structure today. */
export function MlTermStructure({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const models = [...new Set(rows.map((r) => str(r.model)))];
  return <XYPlot points={[]} xLabel="Horizon (sessions)" yLabel="Forecast volatility" formatY={pctFmt}
    lines={models.map((m, i) => ({ label: m, color: SERIES[i % SERIES.length], points: rows.filter((r) => str(r.model) === m && isNum(r.forecast_vol)).map((r) => ({ x: Number(r.horizon), y: r.forecast_vol as number })).sort((a, b) => a.x - b.x) }))} />;
}

/** Loss by model and horizon; lower is better, so the darkest cell is the winner. */
export function MlTournament({ rows }: ViewProps) {
  const metrics = ["qlike", "mae", "interval_coverage"].filter((k) => rows.some((r) => isNum(r[k])));
  const [metric, setMetric] = useState(metrics[0] ?? "mae");
  if (!rows.length) return <Empty />;
  return (
    <div>
      <Bar><Picker label="Loss" value={metric} options={metrics} onChange={setMetric} /></Bar>
      <LongHeatmap rows={rows.map((r) => ({ row: r.model, col: `h=${str(r.horizon)}`, value: r[metric] }))} format={metric === "interval_coverage" ? pctFmt : sig} />
    </div>
  );
}

/* ---------------------------------------------------------------- F04 barriers */

/** Every event: days until a barrier was touched against the return it locked in, by which barrier won. */
export function MlBarrierScatter({ rows, result }: ViewProps) {
  const params = out(result, "barrier_parameters")[0] ?? {};
  if (!rows.length) return <Empty />;
  const day = 86_400_000;
  const pts = rows.filter((r) => isNum(r.forward_return)).map((r) => {
    const a = parseDate(r.date), b = parseDate(r.touch_date);
    return { x: a && b ? Math.round((b - a) / day) : 0, y: r.forward_return as number, group: label(str(r.touch_type || (r.label === 0 ? "vertical" : ""))), label: `${str(r.ticker)} ${str(r.date)}` };
  });
  const pt = n(params.profit_taking), sl = n(params.stop_loss);
  const by = (g: string) => pts.filter((p) => p.group === g).length;
  const groups = [...new Set(pts.map((p) => p.group))];
  return (
    <div>
      <Stats items={groups.map((g) => [g, `${by(g)} (${pct(by(g) / pts.length, 0)})`] as [string, string])} />
      <XYPlot points={pts} xLabel="Calendar days to first touch" yLabel="Return at touch" formatY={pctFmt}
        refY={[...(pt !== null ? [{ y: pt, label: "profit-taking", color: "var(--up)" }] : []), ...(sl !== null ? [{ y: -sl, label: "stop-loss", color: "var(--down)" }] : [])]}
        groupColors={{ [label("profit_taking")]: "var(--up)", [label("stop_loss")]: "var(--down)", [label("vertical")]: "var(--text-3)" }} />
    </div>
  );
}

/** Share of events per label: −1 stop-loss first, 0 time barrier, +1 profit-taking first. */
export function MlLabelMix({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const total = rows.reduce((a, r) => a + (n(r.count) ?? 0), 0) || 1;
  const name: Record<string, string> = { "-1": "Stop-loss first", "0": "Time barrier", "1": "Profit-taking first" };
  const color: Record<string, string> = { "-1": "var(--down)", "0": "var(--text-3)", "1": "var(--up)" };
  return <Bars bars={[...rows].sort((a, b) => Number(a.label) - Number(b.label)).map((r) => { const k = String(Number(r.label)); return { label: name[k] ?? k, value: (n(r.count) ?? 0) / total, color: color[k], detail: [["Events", (n(r.count) ?? 0).toLocaleString()]] as [string, string][] }; })} format={pctFmt} signed={false} />;
}

/** How the label mix moves with the barrier widths; the chosen pair is outlined. */
export function MlBarrierSurface({ rows, result }: ViewProps) {
  const metrics = ["positive_rate", "negative_rate", "ambiguous_events", "events"].filter((k) => rows.some((r) => isNum(r[k])));
  const [metric, setMetric] = useState(metrics[0] ?? "positive_rate");
  const chosen = out(result, "barrier_parameters")[0] ?? {};
  if (!rows.length) return <Empty />;
  const rs = [...new Set(rows.map((r) => Number(r.profit_taking)))].sort((a, b) => a - b), cs = [...new Set(rows.map((r) => Number(r.stop_loss)))].sort((a, b) => a - b);
  const cell = new Map(rows.map((r) => [`${r.profit_taking}|${r.stop_loss}`, n(r[metric])]));
  return (
    <div>
      <Bar><Picker label="Metric" value={metric} options={metrics} onChange={setMetric} /></Bar>
      <Heatmap rows={rs.map((v) => `PT ${pctFmt(v)}`)} cols={cs.map((v) => `SL ${pctFmt(v)}`)} values={rs.map((a) => cs.map((b) => cell.get(`${a}|${b}`) ?? null))} centered={false}
        format={/rate/.test(metric) ? pctFmt : (v) => v.toLocaleString()} rowTitle="Profit-taking" colTitle="Stop-loss"
        outline={(i, j) => rs[i] === Number(chosen.profit_taking) && cs[j] === Number(chosen.stop_loss)} />
    </div>
  );
}

export function MlCoverage({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const target = n(rows[0].target_coverage);
  return <TimeSeries data={rows} x="date" height={220} format={pctFmt} series={[{ key: "empirical_coverage", label: "Empirical coverage" }]} refLines={target !== null ? [{ y: target, label: "target", color: "var(--warn)", dash: true }] : []} />;
}

/* ---------------------------------------------------------------- F05 allocation */

/** Weights largest first, each bar labelled with its sector. */
export function MlWeights({ rows, spec }: ViewProps) {
  const e = (spec?.encoding ?? {}) as { x?: string; y?: string };
  const name = e.x ?? (rows[0] && "asset" in rows[0] ? "asset" : Object.keys(rows[0] ?? {})[0]);
  const w = e.y ?? (rows[0] && "weight" in rows[0] ? "weight" : Object.keys(rows[0] ?? {}).find((k) => isNum(rows[0][k])) ?? "weight");
  if (!rows.length) return <Empty />;
  const v = vals(rows, w);
  const hhi = v.reduce((a, b) => a + b * b, 0);
  return (
    <div>
      <Stats items={[["Assets", v.length], ["Largest", pctFmt(Math.max(...v))], ["Effective N", hhi > 0 ? (1 / hhi).toFixed(1) : "–"], ["Gross", pctFmt(v.reduce((a, b) => a + Math.abs(b), 0))]]} />
      <Diverging rows={[...rows].filter((r) => isNum(r[w])).sort((a, b) => (b[w] as number) - (a[w] as number)).map((r) => ({ label: str(r[name]), value: r[w] as number, note: str(r.sector) }))} format={pctFmt} labelWidth={110} />
    </div>
  );
}

/** Risk contribution per asset against the equal-risk line: bars far above it dominate portfolio risk. */
export function MlRiskContrib({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].filter((r) => isNum(r.risk_contribution)).sort((a, b) => (b.risk_contribution as number) - (a.risk_contribution as number));
  return <Bars bars={sorted.map((r) => ({ label: str(r.asset), value: r.risk_contribution as number }))} signed={false} format={pctFmt} refLines={[{ y: 1 / sorted.length, label: "equal risk" }]} />;
}

/** The clustering tree, and the covariance matrix reordered to match it so blocks line up. */
export function MlDendrogram({ rows, result }: ViewProps) {
  const cov = out(result, "quasi_diagonalized_covariance_heatmap");
  // The linkage indexes assets in input order (the weight vector); the covariance arrives already in leaf order.
  const assets = out(result, "hrp_weight_vector").map((r) => str(r.asset));
  const order = useMemo(() => [...new Set(cov.map((r) => str(r.row)))], [cov]);
  const merges = rows.map((r) => ({ left: Number(r.left), right: Number(r.right), distance: Number(r.distance), count: n(r.count) ?? undefined })) as Merge[];
  if (!rows.length || assets.length < 2) return <Empty />;
  const treeOrder = leafOrder(merges, assets.length).map((i) => assets[i]);
  const matrix = order.length ? order : treeOrder;
  const cell = new Map(cov.map((r) => [`${str(r.row)}|${str(r.col)}`, n(r.value)]));
  const d = matrix.map((a) => Math.sqrt(Math.max(cell.get(`${a}|${a}`) ?? 0, 1e-18)));
  return (
    <div>
      <Dendrogram merges={merges} leaves={assets} />
      {cov.length ? <Heatmap rows={matrix} cols={matrix} values={matrix.map((a, i) => matrix.map((b, j) => { const c = cell.get(`${a}|${b}`); return c === null || c === undefined ? null : c / (d[i] * d[j]); }))} format={(v) => v.toFixed(2)} /> : null}
      <p className="ml-note">Correlations implied by the covariance, in HRP&apos;s seriated order. Square blocks along the diagonal are the clusters HRP splits on.{order.length && order.join() !== treeOrder.join() ? " The matrix order is the API's quasi-diagonal order." : ""}</p>
    </div>
  );
}

/** Reference prior against the Black–Litterman posterior, per asset. */
export function MlBlShift({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const a = "reference_prior_return" in rows[0] ? "reference_prior_return" : "allocation_weight";
  const b = "posterior_return" in rows[0] ? "posterior_return" : "black_litterman";
  const moved = rows.filter((r) => Math.abs((n(r[b]) ?? 0) - (n(r[a]) ?? 0)) > 1e-12).length;
  return (
    <div>
      {moved === 0 ? <p className="ml-note"><b>No views moved the prior.</b> With no views supplied, the posterior equals the equal-weight reference prior.</p> : null}
      <Diverging rows={[...rows].sort((x, y) => ((n(y[b]) ?? 0) - (n(y[a]) ?? 0)) - ((n(x[b]) ?? 0) - (n(x[a]) ?? 0))).map((r) => ({ label: str(r.asset), value: (n(r[b]) ?? 0) - (n(r[a]) ?? 0), note: `${label(a)} ${pctFmt(n(r[a]) ?? 0)} → ${label(b)} ${pctFmt(n(r[b]) ?? 0)}` }))} format={pctFmt} labelWidth={110} />
    </div>
  );
}

/* ---------------------------------------------------------------- F06 regimes, F07 online learning, shares over time */

/** State probabilities over time; the dominant state reads as the widest band. */
export function MlRegimes({ rows }: ViewProps) {
  const keys = Object.keys(rows[0] ?? {}).filter((k) => /^(state|component)_\d+$/.test(k));
  if (!rows.length || !keys.length) return <Empty />;
  const dom = rows.map((r) => str(r.dominant_state ?? keys.reduce((a, k) => ((n(r[k]) ?? 0) > (n(r[a]) ?? 0) ? k : a), keys[0])));
  let run = 1;
  for (let i = dom.length - 2; i >= 0 && dom[i] === dom[dom.length - 1]; i--) run++;
  return (
    <div>
      <Stats items={[["Current state", dom[dom.length - 1].replace(/^\D+_/, "")], ["Days in state", run], ...keys.map((k) => [`Time in ${label(k)}`, pct(dom.filter((d) => d === k.replace(/^\D+_/, "") || d === k).length / dom.length, 0)] as [string, string])]} />
      <StackedArea data={rows} keys={keys} labels={Object.fromEntries(keys.map((k) => [k, label(k)]))} height={240} />
    </div>
  );
}

/** Transition probabilities with each state's expected length (1 / (1 − stay probability)). */
export function MlTransition({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const rs = [...new Set(rows.map((r) => str(r.row)))], cs = [...new Set(rows.map((r) => str(r.col)))];
  const cell = new Map(rows.map((r) => [`${str(r.row)}|${str(r.col)}`, n(r.value)]));
  return <Heatmap rows={rs.map(label)} cols={cs.map(label)} centered={false} format={pctFmt} rowTitle="From" colTitle="To"
    values={rs.map((a) => cs.map((b) => cell.get(`${a}|${b}`) ?? null))}
    margin={{ label: "Expected days", values: rs.map((a) => { const p = cell.get(`${a}|${a}`); return p !== null && p !== undefined && p < 1 ? 1 / (1 - p) : null; }) }} />;
}

/** Mean return of each asset inside each regime. */
export function MlRegimeReturns({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return <LongHeatmap rows={rows.map((r) => ({ row: r.asset, col: `State ${str(r.regime)}`, value: r.mean_log_return }))} format={pctFmt} />;
}

/** Long weights per date and model as a stacked share chart. */
export function MlStacked({ rows, spec }: ViewProps) {
  const e = (spec?.encoding ?? {}) as { x?: string; y?: string; series?: string };
  const x = e.x ?? "date", s = e.series ?? (rows[0] && "model" in rows[0] ? "model" : "factor"), y = e.y ?? "weight";
  const { data, keys } = useMemo(() => pivot(rows, x, s, y), [rows, x, s, y]);
  if (!rows.length) return <Empty />;
  const signed = rows.some((r) => (n(r[y]) ?? 0) < 0);
  if (signed) return <TimeSeries data={data} x={x} height={260} series={keys.map((k) => ({ key: k, label: label(k) }))} refLines={[{ y: 0, color: "var(--line-3)" }]} />;
  return <StackedArea data={data} x={x} keys={keys} labels={Object.fromEntries(keys.map((k) => [k, label(k)]))} />;
}

export function MlRegret({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const last = rows[rows.length - 1];
  return (
    <div>
      <Stats items={[["Final regret", sig(n(last.obs_regret) ?? NaN)], ["Online loss", sig(n(last.obs_cumulative_loss) ?? NaN)], ["Best fixed model loss", sig(n(last.best_fixed_model_loss) ?? NaN)]]} />
      <TimeSeries data={rows} x="date" height={240} series={[{ key: "obs_cumulative_loss", label: "Online ensemble" }, { key: "best_fixed_model_loss", label: "Best single model in hindsight", dash: true }, { key: "obs_regret", label: "Regret", kind: "area", color: "var(--warn)" }]} />
    </div>
  );
}

/** Reliability: predicted against realised by bucket; points on the diagonal are calibrated. */
export function MlCalibration({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const pts = rows.filter((r) => isNum(r.mean_prediction) && isNum(r.mean_realized)).map((r) => ({ x: r.mean_prediction as number, y: r.mean_realized as number, label: `Bucket ${str(r.bucket)}`, size: n(r.observations) ?? undefined }));
  return <XYPlot points={pts} lines={[{ label: "Buckets", points: [...pts].sort((a, b) => a.x - b.x) }]} xLabel="Mean prediction" yLabel="Mean realised" diagonal labelPoints formatX={pctFmt} formatY={pctFmt} />;
}

/* ---------------------------------------------------------------- F08 composite, F10 microstructure */

/** A matrix of latest values per name, each column scored against its own cross-section. */
export function MlCrossSection({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const name = "ticker" in rows[0] ? "ticker" : Object.keys(rows[0])[0];
  const cols = Object.keys(rows[0]).filter((k) => k !== name && isNum(rows.find((r) => isNum(r[k]))?.[k]));
  const z = cols.map((c) => { const v = vals(rows, c); const m = mean(v); const sd = Math.sqrt(mean(v.map((a) => (a - m) ** 2))) || 1; return (x: unknown) => (isNum(x) ? Math.max(-3, Math.min(3, (x - m) / sd)) : null); });
  return (
    <div>
      <Heatmap rows={rows.map((r) => str(r[name]))} cols={cols.map(label)} values={rows.map((r) => cols.map((c, j) => z[j](r[c])))} format={(v) => v.toFixed(1)} />
      <p className="ml-note">Cells are z-scores within each column, so colour compares names on the same signal. Hover shows the score; the table view has raw values.</p>
    </div>
  );
}

/** One equity curve per signal (long-short, net), so families compare on one axis. */
export function MlSignalEquity({ rows }: ViewProps) {
  const { data, keys } = useMemo(() => pivot(rows, "date", "signal", "equity"), [rows]);
  if (!rows.length) return <Empty />;
  return <TimeSeries data={data} x="date" height={300} series={keys.map((k) => ({ key: k, label: label(k) }))} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />;
}

/** Wide date × ticker surface as faint lines with the cross-sectional median in bold. */
export function MlTimeSurface({ rows }: ViewProps) {
  const keys = Object.keys(rows[0] ?? {}).filter((k) => k !== "date");
  const data = useMemo(() => rows.map((r) => { const v = keys.map((k) => r[k]).filter(isNum).sort((a, b) => a - b); return { ...r, median: v.length ? quantile(v, 0.5) : null }; }), [rows, keys]);
  if (!rows.length) return <Empty />;
  return <TimeSeries data={data} x="date" height={280} series={[...keys.map((k) => ({ key: k, label: k, muted: true })), { key: "median", label: "Median", width: 2.2 }]} />;
}

/* ---------------------------------------------------------------- F09 pairs */

/** The spread z-score with entry and exit bands and the trades it triggered. */
export function MlZBand({ rows, result, scope }: ViewProps) {
  const payload = usePayload(scope);
  const entry = Number(payload.entry_z ?? 2), exit = Number(payload.exit_z ?? 0.5);
  const sig2 = out(result, "entry_exit_signal_timeline");
  const pair = out(result, "training_audit")[0]?.selected_pair as Row | undefined;
  const { markers, regions } = useMemo(() => {
    const markers: { date: string; label: string; color?: string }[] = [];
    const regions: { from: string; to?: string; color?: string }[] = [];
    let open: { from: string; d: number } | null = null;
    sig2.forEach((r, i) => {
      const d = Number(r.direction ?? 0), prev = i ? Number(sig2[i - 1].direction ?? 0) : 0;
      if (d !== prev) {
        if (open) { regions.push({ from: open.from, to: str(r.date), color: open.d > 0 ? "var(--up)" : "var(--down)" }); open = null; }
        if (d !== 0) { open = { from: str(r.date), d }; markers.push({ date: str(r.date), label: d > 0 ? "Long spread" : "Short spread", color: d > 0 ? "var(--up)" : "var(--down)" }); }
      }
    });
    if (open) regions.push({ from: (open as { from: string }).from, color: (open as { d: number }).d > 0 ? "var(--up)" : "var(--down)" });
    return { markers, regions };
  }, [sig2]);
  if (!rows.length) return <Empty text="No pair passed the formation test, so the strategy held cash." />;
  return (
    <div>
      <Stats items={[["Pair", pair ? `${str(pair.asset_a)} / ${str(pair.asset_b)}` : "–"], ["Trades", markers.length], ["Engle–Granger p", pair && isNum(pair.engle_granger_pvalue) ? pair.engle_granger_pvalue.toFixed(4) : "–"], ["Entry / exit", `±${entry} / ±${exit}`]]} />
      <TimeSeries data={rows} x="date" height={280} series={[{ key: "zscore", label: "Spread z-score" }]} markers={markers.slice(-40)} regions={regions.map((r) => ({ ...r, label: undefined }))}
        refLines={[{ y: entry, label: `+${entry}`, color: "var(--down)", dash: true }, { y: -entry, label: `−${entry}`, color: "var(--up)", dash: true }, { y: exit, color: "var(--line-3)", dash: true }, { y: -exit, color: "var(--line-3)", dash: true }, { y: 0, color: "var(--line-3)" }]} />
    </div>
  );
}

export function MlNetwork({ rows, result }: ViewProps) {
  const cand = out(result, "pair_candidate_leaderboard");
  if (!rows.length && !cand.length) return <Empty />;
  const nodes = [...new Set(cand.flatMap((r) => [str(r.asset_a), str(r.asset_b)]))];
  const edges = rows.map((r) => ({ source: str(r.source), target: str(r.target), weight: 1 - Math.min(1, (n(r.pvalue) ?? 1) * 10), note: `p = ${sig(n(r.pvalue) ?? NaN)}` }));
  return (
    <div>
      <Network edges={edges} nodes={nodes.length ? nodes : undefined} />
      <p className="ml-note">Links are pairs that passed the Engle–Granger test in the formation window; thicker means a smaller p-value. Unlinked names were screened and failed.</p>
    </div>
  );
}

/* ---------------------------------------------------------------- F11 DML, F12 sequence */

/** Each factor's conditional effect with its 95% interval, beside the naive one-factor slope. */
export function MlCoefCI({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].filter((r) => isNum(r.dml_ape)).sort((a, b) => (b.dml_ape as number) - (a.dml_ape as number));
  return (
    <div>
      <Forest format={sig} refLabel="no effect"
        rows={sorted.map((r) => ({ label: label(str(r.factor)), estimate: r.dml_ape as number, lo: n(r.lower), hi: n(r.upper), tone: (n(r.lower) ?? 0) > 0 ? "up" : (n(r.upper) ?? 0) < 0 ? "down" : "muted", note: isNum(r.univariate_slope) ? `one-factor slope ${sig(r.univariate_slope)}` : undefined }))} />
      <p className="ml-note">Effects are conditional associations after cross-fitted adjustment for the other factors, not causal effects.</p>
    </div>
  );
}

/** Adjusted effect against the naive slope: points off the diagonal are where controls changed the answer. */
export function MlAdjustment({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const pts = rows.filter((r) => isNum(r.univariate_slope) && isNum(r.dml_ape)).map((r) => ({ x: r.univariate_slope as number, y: r.dml_ape as number, label: label(str(r.factor)) }));
  return <XYPlot points={pts} xLabel="One-factor slope" yLabel="Adjusted effect (DML)" diagonal labelPoints formatX={sig} formatY={sig} refX={[{ x: 0, color: "var(--line-3)" }]} refY={[{ y: 0, color: "var(--line-3)" }]} />;
}

/** Effect over time per factor, one small chart each, with its ±1.96 SE band. */
export function MlApePaths({ rows }: ViewProps) {
  const factors = useMemo(() => [...new Set(rows.map((r) => str(r.factor)))], [rows]);
  if (!rows.length) return <Empty />;
  return (
    <div className="x-facets">
      {factors.slice(0, 12).map((f) => {
        const data = rows.filter((r) => str(r.factor) === f).map((r) => ({ ...r, lo: isNum(r.ape) && isNum(r.se) ? r.ape - 1.96 * r.se : null, hi: isNum(r.ape) && isNum(r.se) ? r.ape + 1.96 * r.se : null }));
        return <div key={f} className="x-facet"><div className="x-facet-h">{label(f)}</div><TimeSeries data={data} x="date" height={150} legend={false} series={[{ key: "ape", label: "Effect" }]} band={{ lo: "lo", hi: "hi" }} refLines={[{ y: 0, color: "var(--line-3)" }]} /></div>;
      })}
    </div>
  );
}

export function MlLoss({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const archs = [...new Set(rows.map((r) => str(r.architecture)))];
  const ys = ["training_mse", "validation_mse"].filter((k) => rows.some((r) => isNum(r[k])));
  return <XYPlot points={[]} xLabel="Epoch" yLabel="MSE"
    lines={archs.flatMap((a, i) => ys.map((y) => ({ label: `${a} ${y.startsWith("val") ? "validation" : "train"}`, color: SERIES[i % SERIES.length], dash: y.startsWith("val"), points: rows.filter((r) => str(r.architecture) === a && isNum(r[y])).map((r) => ({ x: Number(r.epoch), y: r[y] as number })) })))} />;
}

/** Monthly out-of-sample IC per architecture. */
export function MlMonthlyIc({ rows }: ViewProps) {
  const { data, keys } = useMemo(() => pivot(rows, "month", "architecture", "ic"), [rows]);
  if (!rows.length) return <Empty />;
  if (keys.length === 1) return <MlIcBars rows={rows.map((r) => ({ month: r.month, ic: r.ic }))} result={{} as never} feature={{} as never} keys={[]} scope="" spec={{ key: "", title: "", source: "charts", render: "", encoding: { x: "month", y: "ic" } }} />;
  return <Heatmap rows={keys} cols={data.map((r) => str(r.month))} values={keys.map((k) => data.map((r) => n(r[k])))} format={(v) => v.toFixed(2)} />;
}

