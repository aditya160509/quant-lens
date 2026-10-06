"use client";

import { useMemo, useState, type ReactNode } from "react";
import { create } from "zustand";
import { Bars } from "@/charts/Bars";
import { Beeswarm } from "@/charts/Beeswarm";
import { Dendrogram, leafOrder, type Merge } from "@/charts/Dendrogram";
import { Distribution } from "@/charts/Distribution";
import { Diverging } from "@/charts/Diverging";
import { Heatmap } from "@/charts/Heatmap";
import { StackedArea } from "@/charts/StackedArea";
import { TimeSeries, type Series } from "@/charts/TimeSeries";
import { Waterfall } from "@/charts/Waterfall";
import { XYPlot } from "@/charts/XYPlot";
import { parseDate } from "@/charts/core";
import { Segmented } from "@/workspace/ui";
import { isNum, label, out, pct } from "@/modules/research/format";
import { DataTable, Empty } from "@/modules/research/outputs/tables";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { Row } from "@/modules/research/types";

/* ---------------------------------------------------------------- helpers */

/** The name picked in the ranking; the waterfall explains it. Keyed by run so a new run starts at rank 1. */
export const usePick = create<{ picks: Record<string, string>; pick: (scope: string, t: string) => void }>()((set) => ({
  picks: {}, pick: (scope, t) => set((st) => ({ picks: { ...st.picks, [scope]: t } })),
}));
const runOf = (scope: string) => scope.split(":").slice(0, 2).join(":");
/** Proper names for model and estimator ids, so charts never show "Lightgbm" or "Ols3". */
const NAMES: Record<string, string> = {
  ensemble: "Ensemble", lightgbm: "LightGBM", ridge: "Ridge", ols3: "3-factor OLS", ic_composite: "IC composite", xgboost: "XGBoost", catboost: "CatBoost",
  har_rv: "HAR-RV", har: "HAR-RV", har_gbm: "HAR-GBM", har_ridge: "HAR-Ridge", har_x_elasticnet: "HAR-X ElasticNet", har_elasticnet: "HAR ElasticNet", ewma: "EWMA", gjr_garch: "GJR-GARCH", garch: "GARCH", regime_switch: "Regime switch", garman_klass: "Garman–Klass", yang_zhang: "Yang–Zhang", close_to_close: "Close-to-close",
};
const name = (k: string) => NAMES[k.toLowerCase().replace(/[\s-]+/g, "_")] ?? label(k);

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
  return <TimeSeries data={data} x="date" height={300} yLabel="Growth of $1, out of sample" series={series} band={{ lo: "lo", hi: "hi", label: "10–90% of paths", color: "color-mix(in oklch, var(--accent) 14%, transparent)" }} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />;
}

/** How much a naive split flatters the model: the Sharpe it reports minus the purged Sharpe. A large gap is leakage. */
export function MlLeakGap({ rows }: ViewProps) {
  const naive = n(rows.find((r) => /naive/i.test(str(r.method)))?.sharpe), purged = n(rows.find((r) => /purged/i.test(str(r.method)))?.sharpe);
  if (naive === null || purged === null) return <Empty />;
  const gap = naive - purged, rel = purged !== 0 ? gap / Math.abs(purged) : null;
  const tone = Math.abs(gap) < 0.1 ? "var(--up)" : Math.abs(gap) < 0.3 ? "var(--warn)" : "var(--down)";
  return (
    <div className="leak">
      <div><span>Naive split</span><b className="num">{naive.toFixed(2)}</b></div>
      <div className="arrow" aria-hidden>→</div>
      <div><span>Purged and embargoed</span><b className="num">{purged.toFixed(2)}</b></div>
      <div className="gap" style={{ ["--tone" as string]: tone }}><span>Leakage gap</span><b className="num">{gap >= 0 ? "+" : ""}{gap.toFixed(2)}</b><em>{rel === null ? "" : `${(rel * 100).toFixed(1)}% of the purged Sharpe`}</em></div>
      <p className="ml-note" style={{ gridColumn: "1 / -1" }}>{Math.abs(gap) < 0.1 ? "Purging barely moves the Sharpe: overlapping labels were not inflating this result." : gap > 0 ? "The naive split overstates the Sharpe: overlapping labels leak future information into training. Trust the purged number." : "The purged Sharpe is higher than the naive one; the difference is noise, not leakage."}</p>
    </div>
  );
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
export function MlRankTable({ rows, result, scope }: ViewProps) {
  const picked = usePick((st) => st.picks[runOf(scope)]);
  const pick = usePick((st) => st.pick);
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
          <div key={str(r.ticker)} className="ml-rank-r" role="button" tabIndex={0} aria-pressed={(picked ?? str(sorted[0]?.ticker)) === str(r.ticker)}
            title={`Explain ${str(r.ticker)}`} onClick={() => pick(runOf(scope), str(r.ticker))} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(runOf(scope), str(r.ticker)); } }}>
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

/** SHAP values per name for the 12 most important features; the rest are summarised in a note so the chart stays readable. */
export function MlBeeswarm({ rows }: ViewProps) {
  const { points, hidden } = useMemo(() => {
    const imp = new Map<string, number>();
    for (const r of rows) if (isNum(r.shap_value)) imp.set(str(r.feature), (imp.get(str(r.feature)) ?? 0) + Math.abs(r.shap_value));
    const keep = new Set([...imp.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([f]) => f));
    return {
      points: rows.filter((r) => isNum(r.shap_value) && keep.has(str(r.feature))).map((r) => ({ row: label(str(r.feature)), value: r.shap_value as number, color: n(r.feature_value), label: str(r.ticker) })),
      hidden: Math.max(0, imp.size - keep.size),
    };
  }, [rows]);
  if (!rows.length) return <Empty />;
  return (
    <div>
      <Beeswarm points={points} />
      <p className="ml-note">Each dot is one name; colour is the feature&apos;s value (high or low within the date), position its push on the prediction.{hidden ? ` ${hidden} weaker features are left out; see the family breakdown.` : ""}</p>
    </div>
  );
}

export function MlWaterfall({ rows, result, scope }: ViewProps) {
  const contrib = out(result, "ticker_contributions");
  const ranked = useMemo(() => [...contrib].sort((a, b) => (n(a.rank) ?? 0) - (n(b.rank) ?? 0)), [contrib]);
  const picked = usePick((st) => st.picks[runOf(scope)]);
  const pick = usePick((st) => st.pick);
  if (ranked.length) {
    const t = picked && ranked.some((r) => str(r.ticker) === picked) ? picked : str(ranked[0].ticker);
    const row = ranked.find((r) => str(r.ticker) === t)!;
    const c = (row.contributions ?? {}) as Record<string, number>;
    return (
      <div>
        <Bar>
          <Picker<string> label="Name" value={t} options={ranked.map((r) => str(r.ticker))} onChange={(v) => pick(runOf(scope), v)} />
          <span className="ml-sub" style={{ margin: 0 }}>Rank {str(row.rank)} of {ranked.length} · predicted {pctFmt(n(row.prediction) ?? 0)} · click any name in the ranking</span>
        </Bar>
        <Waterfall base={n(row.base_value) ?? 0} items={Object.entries(c).filter(([, v]) => isNum(v)).map(([k, v]) => ({ label: label(k), value: v }))} format={(v) => pctFmt(v)} />
      </div>
    );
  }
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
    .map((r) => ({ label: name(str(r[nameKey])), value: r[metric] as number, note: Object.entries(r).filter(([k, v]) => k !== metric && isNum(v)).map(([k, v]) => `${label(k)} ${sig(v as number)}`).join(" · ") }));
  return (
    <div>
      <div className="ml-sub">{label(metric)}, best first</div>
      <Diverging rows={items} format={sig} labelWidth={150} />
    </div>
  );
}

/* ---------------------------------------------------------------- F03 volatility */

/** Forecast against what happened, one model and horizon at a time, with the forecast interval. */
/** The model with the lowest QLIKE at a horizon: the honest default to look at first. */
function bestModel(result: ViewProps["result"], h: number, fallback: string) {
  const t = out(result, "forecast_tournament").filter((r) => Number(r.horizon) === h && isNum(r.qlike)).sort((a, b) => (a.qlike as number) - (b.qlike as number));
  return t.length ? str(t[0].model) : fallback;
}
const defaultHorizon = (hs: number[]) => (hs.includes(21) ? 21 : hs[hs.length - 1] ?? 1);

/** One model's forecast against what volatility turned out to be, with its calibrated interval. Defaults to the
 * tournament winner at the 21-day horizon, where forecasts are decision-relevant and realised volatility is not noise. */
export function MlVolPanel({ rows, result }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const horizons = useMemo(() => [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b), [rows]);
  const [h, setH] = useState<number | null>(null);
  const hh = h ?? defaultHorizon(horizons);
  const [picked, setModel] = useState<string | null>(null);
  const model = picked ?? bestModel(result, hh, models[0] ?? "");
  const ci = out(result, "model_confidence_intervals");
  const data = useMemo(() => {
    const band = new Map(ci.filter((r) => str(r.model) === model && Number(r.horizon) === hh).map((r) => [str(r.date), r]));
    return rows.filter((r) => str(r.model) === model && Number(r.horizon) === hh).map((r) => ({ ...r, lower: band.get(str(r.date))?.lower ?? null, upper: band.get(str(r.date))?.upper ?? null }));
  }, [rows, ci, model, hh]);
  const tour = out(result, "forecast_tournament").find((r) => str(r.model) === model && Number(r.horizon) === hh);
  if (!rows.length) return <Empty />;
  return (
    <div>
      <Bar>
        <select className="input" style={{ height: 28, width: "auto" }} aria-label="Model" value={model} onChange={(e) => setModel(e.target.value)}>
          {models.map((m) => <option key={m} value={m}>{name(m)}{m === bestModel(result, hh, "") ? " · best" : ""}</option>)}
        </select>
        <Segmented<string> label="Horizon" value={String(hh)} onChange={(v) => setH(Number(v))} options={horizons.map((x) => ({ value: String(x), label: `${x}d` }))} />
      </Bar>
      {tour ? <Stats items={[["QLIKE", sig(n(tour.qlike) ?? NaN)], ["MAE", pctFmt(n(tour.mae) ?? NaN)], ["Interval coverage", isNum(tour.interval_coverage) ? pct(tour.interval_coverage, 0) : "–"]]} /> : null}
      <TimeSeries data={data} x="date" height={280} format={pctFmt} yLabel="Annualised volatility"
        series={[{ key: "realized_vol", label: "Realised", color: "var(--text-4)", width: 1 }, { key: "forecast_vol", label: `${name(model)} forecast`, color: "var(--accent)", width: 2 }]}
        band={data.some((r) => isNum(r.lower)) ? { lo: "lower", hi: "upper", label: "Forecast interval", color: "color-mix(in oklch, var(--accent) 12%, transparent)" } : undefined} />
    </div>
  );
}

/** Is the forecast calibrated? Forecasts are sorted into ten bins and each bin's average realised volatility is
 * plotted: a calibrated model sits on the diagonal. Raw points stay faint behind it. */
export function MlVolScatter({ rows, result }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const horizons = useMemo(() => [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b), [rows]);
  const [h, setH] = useState<number | null>(null);
  const hh = h ?? defaultHorizon(horizons);
  const [picked, setModel] = useState<string | null>(null);
  const model = picked ?? bestModel(result, hh, models[0] ?? "");
  const { pts, curve } = useMemo(() => {
    const sel = rows.filter((r) => str(r.model) === model && Number(r.horizon) === hh && isNum(r.forecast_vol) && isNum(r.realized_vol))
      .map((r) => ({ x: r.forecast_vol as number, y: r.realized_vol as number })).sort((a, b) => a.x - b.x);
    const bins = 10, out: { x: number; y: number }[] = [];
    for (let i = 0; i < bins; i++) {
      const chunk = sel.slice(Math.floor((i * sel.length) / bins), Math.floor(((i + 1) * sel.length) / bins));
      if (chunk.length) out.push({ x: mean(chunk.map((c) => c.x)), y: mean(chunk.map((c) => c.y)) });
    }
    return { pts: sel.map((p) => ({ ...p, group: "Each forecast" })), curve: out };
  }, [rows, model, hh]);
  if (!rows.length) return <Empty />;
  return (
    <div>
      <Bar>
        <select className="input" style={{ height: 28, width: "auto" }} aria-label="Model" value={model} onChange={(e) => setModel(e.target.value)}>
          {models.map((m) => <option key={m} value={m}>{name(m)}</option>)}
        </select>
        <Segmented<string> label="Horizon" value={String(hh)} onChange={(v) => setH(Number(v))} options={horizons.map((x) => ({ value: String(x), label: `${x}d` }))} />
      </Bar>
      <XYPlot points={pts} xLabel="Forecast volatility" yLabel="Realised volatility" diagonal robust formatX={pctFmt} formatY={pctFmt}
        groupColors={{ "Each forecast": "color-mix(in oklch, var(--text-3) 35%, transparent)" }}
        lines={[{ label: "Average realised, by forecast decile", color: "var(--accent)", points: curve }]} />
      <p className="ml-note">On the dashed diagonal the forecast is right on average. Above it the model under-forecasts risk; below it, over-forecasts.</p>
    </div>
  );
}

/** Today's forecast for every model at every horizon; the tournament winner per horizon is marked. */
export function MlTermStructure({ rows, result }: ViewProps) {
  if (!rows.length) return <Empty />;
  const models = [...new Set(rows.map((r) => str(r.model)))];
  const hs = [...new Set(rows.map((r) => Number(r.horizon)))].filter((x) => x > 0).sort((a, b) => a - b);
  const get = (m: string, h: number) => n(rows.find((r) => str(r.model) === m && Number(r.horizon) === h)?.forecast_vol);
  const all = rows.map((r) => n(r.forecast_vol)).filter((v): v is number => v !== null);
  const lo = Math.min(...all), hi = Math.max(...all);
  return (
    <div className="ml-table-wrap">
      <table className="ml-table term">
        <thead><tr><th>Model</th>{hs.map((h) => <th key={h}>{h === 1 ? "1 day" : h === 5 ? "1 week" : h === 21 ? "1 month" : h === 63 ? "3 months" : `${h}d`}</th>)}</tr></thead>
        <tbody>
          {models.map((m) => (
            <tr key={m}>
              <td>{name(m)}</td>
              {hs.map((h) => {
                const v = get(m, h), best = bestModel(result, h, "") === m;
                return (
                  <td key={h} className="num" data-best={best || undefined}>
                    <span className="term-bar" style={{ width: v === null ? 0 : `${12 + ((v - lo) / (hi - lo || 1)) * 88}%` }} />
                    <b>{v === null ? "–" : pctFmt(v)}</b>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="ml-note">Annualised volatility forecast from today, by horizon. Outlined: the model with the lowest held-out QLIKE at that horizon.</p>
    </div>
  );
}

const LOSS: Record<string, { label: string; better: "low" | "nominal"; fmt: (v: number) => string }> = {
  qlike: { label: "QLIKE", better: "low", fmt: (v) => v.toFixed(3) },
  mae: { label: "MAE", better: "low", fmt: (v) => pctFmt(v) },
  interval_coverage: { label: "Coverage", better: "nominal", fmt: (v) => pct(v, 0) },
};

/** Every model against every horizon. Cells are ranked within their horizon, so the winner stands out whatever the
 * sign of the loss; the gap to the winner is shown, and Diebold–Mariano marks whether the regime switch beats a model. */
export function MlTournament({ rows }: ViewProps) {
  const metrics = Object.keys(LOSS).filter((k) => rows.some((r) => isNum(r[k])));
  const [metric, setMetric] = useState(metrics[0] ?? "qlike");
  if (!rows.length) return <Empty />;
  const L = LOSS[metric] ?? LOSS.qlike;
  const models = [...new Set(rows.map((r) => str(r.model)))];
  const hs = [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b);
  const cell = (m: string, h: number) => rows.find((r) => str(r.model) === m && Number(r.horizon) === h);
  const nominal = 0.9;
  const score = (v: number) => (L.better === "low" ? v : Math.abs(v - nominal));
  const ranks = new Map<string, number>();
  for (const h of hs) {
    const col = models.map((m) => ({ m, v: n(cell(m, h)?.[metric]) })).filter((c): c is { m: string; v: number } => c.v !== null).sort((a, b) => score(a.v) - score(b.v));
    col.forEach((c, i) => ranks.set(`${c.m}|${h}`, col.length > 1 ? i / (col.length - 1) : 0));
  }
  const best = (h: number) => models.find((m) => ranks.get(`${m}|${h}`) === 0);
  const wins = Object.fromEntries(models.map((m) => [m, hs.filter((h) => best(h) === m).length]));
  return (
    <div>
      <Bar><Segmented<string> label="Loss" value={metric} onChange={setMetric} options={metrics.map((k) => ({ value: k, label: LOSS[k].label }))} /></Bar>
      <div className="ml-table-wrap">
        <table className="ml-table tourney">
          <thead><tr><th>Model</th>{hs.map((h) => <th key={h}>{h}d</th>)}<th>Wins</th></tr></thead>
          <tbody>
            {[...models].sort((a, b) => wins[b] - wins[a]).map((m) => (
              <tr key={m}>
                <td>{name(m)}</td>
                {hs.map((h) => {
                  const r = cell(m, h), v = n(r?.[metric]), rank = ranks.get(`${m}|${h}`) ?? 1, b = best(h);
                  const bv = n(cell(b ?? "", h)?.[metric]);
                  const gap = v !== null && bv !== null && bv !== 0 && L.better === "low" && b !== m ? (v - bv) / Math.abs(bv) : null;
                  const dm = n(r?.dm_p_value), dmStat = n(r?.dm_stat_vs_regime_switch);
                  return (
                    <td key={h} className="num" data-best={b === m || undefined} style={{ ["--rank" as string]: String(1 - rank) }}>
                      <b>{v === null ? "–" : L.fmt(v)}</b>
                      {gap !== null ? <em>+{(gap * 100).toFixed(1)}%</em> : b === m ? <em>best</em> : null}
                      {metric === "qlike" && dm !== null && dm < 0.05 && m !== "regime_switch" ? <i title={`Diebold–Mariano p = ${dm.toFixed(3)}: the regime switch is significantly ${dmStat !== null && dmStat > 0 ? "better" : "worse"}`} data-s={dmStat !== null && dmStat > 0 ? "worse" : "better"} /> : null}
                    </td>
                  );
                })}
                <td className="num">{wins[m] || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ml-note">{L.better === "low" ? `Lower ${L.label} is better; each column is ranked on its own and the gap to the column's winner is shown.` : `Coverage should match the ${pct(nominal, 0)} nominal level; the closest wins.`} Dots compare each model with the regime switch (Diebold–Mariano, 5%): red, the regime switch is significantly better than this model; green, significantly worse.</p>
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
      <Stats items={[...groups.map((g) => [g, `${by(g)} (${pct(by(g) / pts.length, 0)})`] as [string, string]), ["Shown", `${pts.length} sample events`]]} />
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
      <Bar><Picker<string> label="Metric" value={metric} options={metrics} onChange={setMetric} /></Bar>
      <Heatmap rows={rs.map((v) => `PT ${pctFmt(v)}`)} cols={cs.map((v) => `SL ${pctFmt(v)}`)} values={rs.map((a) => cs.map((b) => cell.get(`${a}|${b}`) ?? null))} centered={false}
        format={/rate/.test(metric) ? pctFmt : (v) => v.toLocaleString()} rowTitle="Profit-taking" colTitle="Stop-loss"
        outline={(i, j) => rs[i] === Number(chosen.profit_taking) && cs[j] === Number(chosen.stop_loss)} />
    </div>
  );
}

export function MlCoverage({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const target = n(rows[0].target_coverage);
  const avg = mean(vals(rows, "empirical_coverage"));
  const diff = target !== null ? avg - target : null;
  const read = diff === null ? "" : Math.abs(diff) <= 0.03 ? "Calibrated: realised outcomes fall inside the interval about as often as promised."
    : diff > 0 ? `Over-covering by ${pct(diff, 0)}: the intervals are wider than they need to be, so they understate how precise the forecast is.`
    : `Under-covering by ${pct(-diff, 0)}: outcomes escape the interval more often than promised, so risk is understated.`;
  return (
    <div>
      <Stats items={[["Average coverage", pct(avg, 0), diff !== null && Math.abs(diff) <= 0.03 ? "var(--up)" : "var(--warn)"], ["Target", target === null ? "–" : pct(target, 0)], ["Dates", rows.length]]} />
      <TimeSeries data={rows} x="date" height={200} format={pctFmt} yLabel="Share of outcomes inside the interval" series={[{ key: "empirical_coverage", label: "Empirical coverage", color: "var(--accent)" }]} refLines={target !== null ? [{ y: target, label: "target", color: "var(--warn)", dash: true }] : []} />
      {read ? <p className="ml-note">{read}</p> : null}
    </div>
  );
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
      {cov.length ? <CorrMap names={matrix} value={(i, j) => { const c = cell.get(`${matrix[i]}|${matrix[j]}`); return c === null || c === undefined ? null : c / (d[i] * d[j]); }} /> : null}
      <p className="ml-note">Correlations implied by the covariance, in HRP&apos;s seriated order. Square blocks along the diagonal are the clusters HRP splits on.{order.length && order.join() !== treeOrder.join() ? " The matrix order is the API's quasi-diagonal order." : ""}</p>
    </div>
  );
}

/** A correlation matrix that stays readable at any size: square cells sized to the card, colour for the value,
 * the exact pair on hover, and numbers printed only when the matrix is small enough to read them. */
function CorrMap({ names, value }: { names: string[]; value: (i: number, j: number) => number | null }) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const N = names.length, numbers = N <= 12;
  const colour = (v: number | null) => (v === null ? "transparent" : v >= 0 ? `color-mix(in oklch, var(--up) ${Math.round(Math.min(1, v) * 85)}%, var(--panel-2))` : `color-mix(in oklch, var(--down) ${Math.round(Math.min(1, -v) * 85)}%, var(--panel-2))`);
  const hv = hover ? value(hover[0], hover[1]) : null;
  return (
    <div className="corr">
      <div className="corr-read">{hover ? <><b>{names[hover[0]]}</b> × <b>{names[hover[1]]}</b> <span className="num" style={{ color: hv !== null && hv < 0 ? "var(--down)" : "var(--up)" }}>{hv === null ? "–" : hv.toFixed(2)}</span></> : <span>Hover a cell for the pair and its correlation</span>}</div>
      <div className="corr-grid" style={{ gridTemplateColumns: `52px repeat(${N}, minmax(0, 1fr))` }} onPointerLeave={() => setHover(null)}>
        {names.map((r, i) => [
          <span key={`l${r}`} className="corr-l" data-on={hover?.[0] === i || undefined}>{r}</span>,
          ...names.map((c, j) => {
            const v = value(i, j);
            return <i key={`${r}|${c}`} style={{ background: colour(v) }} data-x={hover && (hover[0] === i || hover[1] === j) ? "1" : undefined} onPointerEnter={() => setHover([i, j])}>{numbers && v !== null ? v.toFixed(2) : null}</i>;
          }),
        ])}
      </div>
      <div className="corr-key"><span>−1</span><i /><span>0</span><i /><span>+1</span></div>
    </div>
  );
}

/** Reference prior against the Black–Litterman posterior, per asset. Without views there is nothing to show but the way to add them. */
export function MlBlShift({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const a = "reference_prior_return" in rows[0] ? "reference_prior_return" : "allocation_weight";
  const b = "posterior_return" in rows[0] ? "posterior_return" : "black_litterman";
  const moved = rows.filter((r) => Math.abs((n(r[b]) ?? 0) - (n(r[a]) ?? 0)) > 1e-12).length;
  return (
    <div>
      {moved === 0 ? null : <Diverging rows={[...rows].sort((x, y) => ((n(y[b]) ?? 0) - (n(y[a]) ?? 0)) - ((n(x[b]) ?? 0) - (n(x[a]) ?? 0))).map((r) => ({ label: str(r.asset), value: (n(r[b]) ?? 0) - (n(r[a]) ?? 0), note: `${label(a)} ${pctFmt(n(r[a]) ?? 0)} → ${label(b)} ${pctFmt(n(r[b]) ?? 0)}` }))} format={pctFmt} labelWidth={110} />}
      {moved === 0 ? <div className="val-unavail"><b>No alpha views yet</b><span>Run the Alpha page and press &ldquo;Use as allocation views&rdquo;: its scores become Black–Litterman views, scaled by the held-out IC, and this page shows how they tilt the weights.</span></div> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- F06 regimes, F07 online learning, shares over time */

/** State probabilities over time; the dominant state reads as the widest band. */
/** Plain state names from the API (Calm / Normal / Stress by training volatility), with a colour that means the same everywhere. */
function useStateNames(result: ViewProps["result"]) {
  const labels = ((result.meta as Row).state_labels ?? {}) as Record<string, string>;
  const nameOf = (k: string) => labels[k] ?? labels[`state_${k.replace(/^\D+_?/, "")}`] ?? label(k);
  const colourOf = (k: string) => { const s = nameOf(k); return s === "Stress" ? "var(--down)" : s === "Calm" ? "var(--up)" : s.startsWith("Normal") ? "var(--s1)" : undefined; };
  return { nameOf, colourOf };
}

/** Filtered probability of each state through time; the current state and how long it has lasted lead. */
export function MlRegimes({ rows, result }: ViewProps) {
  const keys = Object.keys(rows[0] ?? {}).filter((k) => /^(state|component)_\d+$/.test(k));
  const { nameOf, colourOf } = useStateNames(result);
  if (!rows.length || !keys.length) return <Empty />;
  const top = (r: Row) => keys.reduce((a, k) => ((n(r[k]) ?? 0) > (n(r[a]) ?? 0) ? k : a), keys[0]);
  const dom = rows.map(top);
  let run = 1;
  for (let i = dom.length - 2; i >= 0 && dom[i] === dom[dom.length - 1]; i--) run++;
  const isState = keys[0].startsWith("state");
  const colors = isState ? Object.fromEntries(keys.map((k) => [k, colourOf(k)]).filter(([, c]) => c)) as Record<string, string> : undefined;
  const now = dom[dom.length - 1];
  return (
    <div>
      <Stats items={[["Current state", isState ? nameOf(now) : label(now), isState ? colourOf(now) : undefined], ["Days in state", run], ...keys.map((k) => [`Time in ${isState ? nameOf(k) : label(k)}`, pct(dom.filter((d) => d === k).length / dom.length, 0)] as [string, string])]} />
      <StackedArea data={rows} keys={keys} colors={colors} labels={Object.fromEntries(keys.map((k) => [k, isState ? nameOf(k) : label(k)]))} height={240} />
    </div>
  );
}

/** How likely each state is to persist or switch tomorrow, and how long a stay lasts on average (1 / (1 − stay)). */
export function MlTransition({ rows, result }: ViewProps) {
  const { nameOf, colourOf } = useStateNames(result);
  if (!rows.length) return <Empty />;
  const rs = [...new Set(rows.map((r) => str(r.row)))], cs = [...new Set(rows.map((r) => str(r.col)))];
  const cell = new Map(rows.map((r) => [`${str(r.row)}|${str(r.col)}`, n(r.value)]));
  return (
    <div className="ml-table-wrap">
      <table className="ml-table trans">
        <thead><tr><th>From \ to</th>{cs.map((c) => <th key={c}>{nameOf(c)}</th>)}<th>Typical stay</th></tr></thead>
        <tbody>
          {rs.map((a) => {
            const stay = cell.get(`${a}|${a}`);
            const days = stay !== null && stay !== undefined && stay < 1 ? 1 / (1 - stay) : null;
            return (
              <tr key={a}>
                <td><span className="dot" style={{ background: colourOf(a) ?? "var(--text-3)" }} />{nameOf(a)}</td>
                {cs.map((b) => { const v = cell.get(`${a}|${b}`) ?? null; return <td key={b} className="num" data-self={a === b || undefined} style={{ ["--p" as string]: String(v ?? 0) }}>{v === null ? "–" : v < 0.0005 ? "<0.1%" : pct(v, 1)}</td>; })}
                <td className="num"><b>{days === null ? "–" : days >= 252 ? `${(days / 252).toFixed(1)} yr` : `${Math.round(days)} days`}</b></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="ml-note">Each row is today&apos;s state; cells are the chance of being in each state tomorrow. Typical stay is how many sessions a visit lasts on average.</p>
    </div>
  );
}

/** How each name behaved in each state: the average across names first, then the names most and least hurt by stress. */
export function MlRegimeReturns({ rows, result }: ViewProps) {
  const { nameOf, colourOf } = useStateNames(result);
  const [all, setAll] = useState(false);
  if (!rows.length) return <Empty />;
  const states = [...new Set(rows.map((r) => str(r.regime)))].sort();
  const key = (s: string) => `state_${s}`;
  const assets = [...new Set(rows.map((r) => str(r.asset)))];
  const val = (a: string, s: string) => n(rows.find((r) => str(r.asset) === a && str(r.regime) === s)?.mean_log_return);
  const stressS = states.find((s) => nameOf(key(s)) === "Stress"), calmS = states.find((s) => nameOf(key(s)) === "Calm");
  const gap = (a: string) => (stressS && calmS ? (val(a, stressS) ?? 0) - (val(a, calmS) ?? 0) : 0);
  const sorted = [...assets].sort((x, y) => gap(x) - gap(y));
  const shown = all || sorted.length <= 12 ? sorted : [...sorted.slice(0, 6), ...sorted.slice(-6)];
  const avg = (s: string) => mean(assets.map((a) => val(a, s)).filter((v): v is number => v !== null));
  const max = Math.max(...rows.map((r) => Math.abs(n(r.mean_log_return) ?? 0)), 1e-9);
  const tint = (v: number | null) => (v === null ? undefined : `color-mix(in oklch, ${v >= 0 ? "var(--up)" : "var(--down)"} ${Math.round((Math.abs(v) / max) * 55)}%, transparent)`);
  return (
    <div className="ml-table-wrap">
      <table className="ml-table regret">
        <thead><tr><th>Name</th>{states.map((s) => <th key={s}><span className="dot" style={{ background: colourOf(key(s)) ?? "var(--text-3)" }} />{nameOf(key(s))}</th>)}{stressS && calmS ? <th>Stress − calm</th> : null}</tr></thead>
        <tbody>
          <tr className="avg"><td>Average name</td>{states.map((s) => <td key={s} className="num">{pctFmt(avg(s))}</td>)}{stressS && calmS ? <td className="num">{pctFmt(avg(stressS) - avg(calmS))}</td> : null}</tr>
          {shown.map((a, i) => (
            <tr key={a} data-split={!all && sorted.length > 12 && i === 6 ? true : undefined}>
              <td>{a}</td>
              {states.map((s) => { const v = val(a, s); return <td key={s} className="num" style={{ background: tint(v) }}>{v === null ? "–" : pctFmt(v)}</td>; })}
              {stressS && calmS ? <td className="num" style={{ color: gap(a) < 0 ? "var(--down)" : "var(--up)" }}>{pctFmt(gap(a))}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > 12 ? <button type="button" className="link" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setAll((v) => !v)}>{all ? "Show the 6 most and least hurt" : `Show all ${sorted.length} names`}</button> : null}
      <p className="ml-note">Mean daily log return inside each state, same period (descriptive, not a strategy). Sorted from the names hurt most by stress to the most resilient.</p>
    </div>
  );
}

/** Long weights per date and model as a stacked share chart. */
export function MlStacked({ rows, spec }: ViewProps) {
  const e = (spec?.encoding ?? {}) as { x?: string; y?: string; series?: string };
  const x = e.x ?? "date", s = e.series ?? (rows[0] && "model" in rows[0] ? "model" : "factor"), y = e.y ?? "weight";
  const { data, keys } = useMemo(() => pivot(rows, x, s, y), [rows, x, s, y]);
  if (!rows.length) return <Empty />;
  const signed = rows.some((r) => (n(r[y]) ?? 0) < 0);
  if (signed) return <TimeSeries data={data} x={x} height={260} series={keys.map((k) => ({ key: k, label: name(k) }))} refLines={[{ y: 0, color: "var(--line-3)" }]} />;
  return <StackedArea data={data} x={x} keys={keys} labels={Object.fromEntries(keys.map((k) => [k, name(k)]))} />;
}

/** Black–Litterman weight minus the plain allocation, shown only once alpha views exist. */
export function MlBlWeights({ result, ...rest }: ViewProps) {
  return <MlBlShift {...rest} result={result} rows={out(result, "bl_vs_pure_hrp_weight_comparison")} />;
}
