"use client";

import { Diverging } from "@/charts/Diverging";
import * as d3 from "d3";
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { Segmented } from "@/workspace/ui";
import { useWidth } from "@/charts/core";
import { BarList } from "@/charts/BarList";
import { SpecCurve, type Spec } from "@/charts/SpecCurve";
import { cell, choiceLabel, first, isNum, label, num, pTone, pct, pval, specTitle, toneVar, tstat } from "../format";
import { useSelection } from "../selection";
import type { Row } from "../types";
import { DataTable, Empty, TBar } from "@/kit/DataTable";
import type { ViewProps } from "./types";

/** Columns of a specification row that describe analyst choices rather than results. */
export const DECISIONS = ["time_window", "subsample", "crisis", "universe", "transform", "controls", "standard_errors", "weighting"] as const;

const fmtCoef = (v: number) => num(v, 4);

export function SpecificationCurveView({ rows }: ViewProps) {
  const select = useSelection((s) => s.select);
  const base = rows.find((r) => r.specification === "base");
  const specs = useMemo<Spec[]>(() => rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => isNum(r.coefficient))
    .map(({ r, i }) => ({
      id: String(i),
      estimate: r.coefficient as number,
      lo: isNum(r.lower_95) ? r.lower_95 : null,
      hi: isNum(r.upper_95) ? r.upper_95 : null,
      significant: r.significant_5pct === true,
      choices: Object.fromEntries(DECISIONS.filter((d) => d in r).map((d) => [d, String(r[d])])),
      extra: [["t-stat", tstat(r.t_stat)], ["p-value", pval(r.p_value)], ["Months", num(r.months)]] as [string, string][],
    })), [rows]);
  const dims = DECISIONS.map((d) => ({ key: d, label: label(d), base: base ? String(base[d]) : undefined }));
  const byId = useMemo(() => new Map(rows.map((r, i) => [String(i), r])), [rows]);

  const onHover = useCallback((s: Spec | null) => {
    if (!s) return;
    const r = byId.get(s.id);
    if (!r) return;
    select({
      title: specTitle(r.specification),
      rows: [
        ["Coefficient", <span key="c" className="num" style={{ color: r.significant_5pct ? (s.estimate > 0 ? "var(--up)" : "var(--down)") : undefined }}>{fmtCoef(s.estimate)}</span>],
        ["Standard error", <span key="se" className="num">{num(r.se, 4)}</span>],
        ["t-stat", <span key="t" className="num">{tstat(r.t_stat)}</span>],
        ["p-value", <span key="p" className="num" style={{ color: toneVar(pTone(r.p_value)) }}>{pval(r.p_value)}</span>],
        ["Months", <span key="m" className="num">{num(r.months)}</span>],
        ["L/S annual return", <span key="ls" className="num">{pct(r.ls_annual_return, 2)}</span>],
        ["L/S Sharpe", <span key="sh" className="num">{num(r.ls_sharpe, 2)}</span>],
        ...DECISIONS.filter((d) => d in r).map((d) => [label(d), choiceLabel(d, String(r[d]))] as [string, string]),
      ],
    });
  }, [byId, select]);

  if (!specs.length) return <Empty />;
  const sig = specs.filter((s) => s.significant).length;
  const pos = specs.filter((s) => s.estimate > 0).length;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <span className="chip">{specs.length} specifications</span>
        <span className={`chip ${sig / specs.length >= 0.5 ? "up" : sig / specs.length >= 0.2 ? "warn" : "down"}`}>{sig} significant at 5%</span>
        <span className="chip">{pos} positive · {specs.length - pos} negative</span>
      </div>
      <SpecCurve specs={specs} dimensions={dims} formatChoice={choiceLabel} formatValue={fmtCoef} yLabel="Slope" onHover={onHover} />
      <SampleStrip rows={rows} />
    </div>
  );
}

export function AttributionBars({ rows }: ViewProps) {
  const bars = rows
    .map((r: Row) => {
      const v = [r.variance_explained, r.share, r.value, r.importance].find(isNum);
      const name = String(r.dimension ?? r.label ?? r.name ?? "");
      if (v === undefined || !name) return null;
      const note = r.most_influential_choice ? `Most influential: ${choiceLabel(name, String(r.most_influential_choice))}${isNum(r.choices) ? ` · ${r.choices} choices` : ""}` : undefined;
      return { label: label(name), value: v, note };
    })
    .filter((b): b is NonNullable<typeof b> => b !== null)
    .sort((a, b) => b.value - a.value);
  if (!bars.length) return <DataTable rows={rows} />;
  const share = bars.every((b) => b.value >= 0 && b.value <= 1);
  return <BarList bars={bars} format={(v) => (share ? `${(v * 100).toFixed(1)}%` : num(v, 3))} max={share ? 1 : undefined} />;
}

/** The full specification grid: estimate with an inline CI bar, t-statistic bar, and economic size. */
export function RobustnessMatrix({ rows }: ViewProps) {
  const ok = rows.filter((r) => isNum(r.coefficient));
  const domain = useMemo(() => {
    const v = ok.flatMap((r) => [r.lower_95, r.upper_95, r.coefficient]).filter(isNum).sort((a, b) => a - b);
    if (!v.length) return [-1, 1] as const;
    const q = (p: number) => v[Math.round(p * (v.length - 1))];
    return [Math.min(0, q(0.05)), Math.max(0, q(0.95))] as const;
  }, [ok]);
  if (!ok.length) return <DataTable rows={rows} />;
  const W = 130;
  const sx = (v: number) => Math.max(0, Math.min(W, ((v - domain[0]) / (domain[1] - domain[0] || 1)) * W));
  return (
    <div className="tbl-wrap" style={{ maxHeight: 560 }}>
      <table className="tbl">
        <thead>
          <tr><th>Specification</th><th className="r">Coefficient</th><th style={{ width: W + 24 }}>95% CI</th><th>t-stat</th><th className="r">p</th><th className="r">Months</th><th className="r">L/S annual</th><th className="r">L/S Sharpe</th></tr>
        </thead>
        <tbody>
          {ok.map((r, i) => {
            const sig = r.significant_5pct === true;
            const c = r.coefficient as number;
            const color = sig ? (c > 0 ? "var(--up)" : "var(--down)") : "var(--text-3)";
            return (
              <tr key={i}>
                <td className="strong">{specTitle(r.specification)}</td>
                <td className="r num" style={{ color: sig ? color : "var(--text)" }}>{fmtCoef(c)}</td>
                <td>
                  <svg width={W} height={12} style={{ display: "block" }} aria-hidden>
                    <line x1={sx(0)} x2={sx(0)} y1={0} y2={12} stroke="var(--line-3)" />
                    {isNum(r.lower_95) && isNum(r.upper_95) ? <line x1={sx(r.lower_95)} x2={sx(r.upper_95)} y1={6} y2={6} stroke={color} strokeWidth={2} strokeOpacity={0.55} strokeLinecap="round" /> : null}
                    <circle cx={sx(c)} cy={6} r={3} fill={color} />
                  </svg>
                </td>
                <td>{isNum(r.t_stat) ? <TBar t={r.t_stat} width={72} /> : "–"}</td>
                <td className="r num" style={{ color: toneVar(pTone(r.p_value)) }}>{cell(r.p_value, "p_value")}</td>
                <td className="r num">{num(r.months)}</td>
                <td className="r num">{pct(r.ls_annual_return, 1)}</td>
                <td className="r num">{num(r.ls_sharpe, 2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Strongest and weakest specifications side by side with the five-number summary of all estimates. */
export function StabilityView({ result }: ViewProps) {
  const box = first(result, "coefficient_stability_stats");
  const strong = first(result, "strongest_specification");
  const weak = first(result, "weakest_specification");
  const q = box ? ["min", "q1", "median", "q3", "max"].map((k) => (isNum(box[k]) ? (box[k] as number) : null)) : [];
  const outliers = box && Array.isArray(box.outliers) ? box.outliers.map(String) : [];
  const lo = Math.min(0, ...(q.filter((v) => v !== null) as number[]));
  const hi = Math.max(0, ...(q.filter((v) => v !== null) as number[]));
  const X = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`;
  return (
    <div style={{ display: "grid", gap: 18 }}>
      {q.length && q.every((v) => v !== null) ? (
        <div>
          <div style={{ position: "relative", height: 34 }}>
            <div style={{ position: "absolute", left: X(0), top: 0, bottom: 0, width: 1, background: "var(--line-3)" }} />
            <div style={{ position: "absolute", left: X(q[0] as number), width: `calc(${X(q[4] as number)} - ${X(q[0] as number)})`, top: 16, height: 2, background: "var(--text-3)" }} />
            <div style={{ position: "absolute", left: X(q[1] as number), width: `calc(${X(q[3] as number)} - ${X(q[1] as number)})`, top: 8, height: 18, borderRadius: 4, background: "var(--accent-soft)", boxShadow: "inset 0 0 0 1px var(--accent-line)" }} />
            <div style={{ position: "absolute", left: X(q[2] as number), top: 5, height: 24, width: 2.5, borderRadius: 2, background: "var(--accent)" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", marginTop: 6 }}>
            {["Min", "Q1", "Median", "Q3", "Max"].map((l, i) => <div key={l}><div className="stat-l">{l}</div><div className="num" style={{ color: l === "Median" ? "var(--text)" : "var(--text-2)" }}>{num(q[i], 4)}</div></div>)}
          </div>
        </div>
      ) : null}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {[["Strongest", strong, "var(--up)"], ["Weakest", weak, "var(--down)"]].map(([title, r, c]) => r ? (
          <div key={title as string} style={{ padding: 12, borderRadius: 10, background: "var(--panel-2)", boxShadow: "inset 0 0 0 1px var(--line)" }}>
            <div className="stat-l">{title as string}</div>
            <div style={{ fontWeight: 550, margin: "2px 0 6px" }}>{specTitle((r as Row).specification)}</div>
            <div style={{ display: "flex", gap: 16 }}>
              <span className="num" style={{ color: c as string }}>{num((r as Row).coefficient, 4)}</span>
              <span className="num" style={{ color: "var(--text-3)" }}>t {tstat((r as Row).t_stat)}</span>
              <span className="num" style={{ color: "var(--text-3)" }}>{num((r as Row).months)} months</span>
            </div>
          </div>
        ) : null)}
      </div>
      {outliers.length ? (
        <div>
          <div className="stat-l" style={{ marginBottom: 6 }}>{outliers.length} outlying specifications</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{outliers.map((o) => <span key={o} className="chip">{specTitle(o)}</span>)}</div>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- shared views

/** Chart/table switch inside a card: wraps a chart view and its tabular twin. */
export function withSwitch(Chart: ComponentType<ViewProps>, a = "Chart", b = "Table", Alt: ComponentType<ViewProps> = DataTable): ComponentType<ViewProps> {
  return function Switched(p: ViewProps) {
    const [v, setV] = useState<"a" | "b">("a");
    return (
      <div>
        <div className="vw-head"><span /><Segmented<"a" | "b"> label="View" value={v} onChange={setV} options={[{ value: "a", label: a }, { value: "b", label: b }]} /></div>
        {v === "a" ? <Chart {...p} /> : <Alt {...p} />}
      </div>
    );
  };
}

export type DivItem = { label: string; value: number };

/** Profits-and-losses style bars on a centre axis: an All row on top, toned value at the end of each bar. */
export function DivergingBars({ items, format = (v: number) => num(v, 3), allLabel = "All", total }: { items: DivItem[]; format?: (v: number) => string; allLabel?: string; total?: number }) {
  const rows = [...items].sort((x, y) => y.value - x.value);
  return <Diverging rows={rows} all={{ label: allLabel, value: total ?? rows.reduce((s, d) => s + d.value, 0) }} format={format} />;
}

const nonEmpty = <T,>(xs: T[]) => xs.length > 0;

/** Signed contributions (factor zoo, attribution) as diverging bars with a chart/table switch. */
export function DivergingView({ rows }: ViewProps) {
  const items = rows.map((r) => {
    const v = [r.contribution, r.correlation, r.corr, r.value, r.share, r.variance_explained, r.importance, r.post_pre_ratio].find(isNum);
    const name = String(r.dimension ?? r.label ?? r.name ?? r.factor ?? r.unit ?? "");
    return v === undefined || !name ? null : { label: label(name), value: v };
  }).filter((d): d is DivItem => d !== null);
  if (!nonEmpty(items)) return <DataTable rows={rows} />;
  return <DivergingBars items={items} />;
}

const quantile = (s: number[], p: number) => s[Math.min(s.length - 1, Math.max(0, Math.round(p * (s.length - 1))))];

/** Estimates grouped by the value of each analyst choice: box plots plus median, MAD and IQR. */
export function ByChoice({ rows }: ViewProps) {
  const [dim, setDim] = useState<string>("");
  const dims = DECISIONS.filter((d) => rows.some((r) => d in r));
  const active = dim || dims[0];
  const groups = (() => {
    if (!active) return [];
    const m = new Map<string, number[]>();
    for (const r of rows) if (isNum(r.coefficient) && active in r) { const k = String(r[active]); m.set(k, [...(m.get(k) ?? []), r.coefficient]); }
    return [...m].map(([k, v]) => {
      const s = [...v].sort((a, b) => a - b);
      const med = quantile(s, 0.5);
      const mad = quantile(s.map((x) => Math.abs(x - med)).sort((a, b) => a - b), 0.5);
      return { k, n: s.length, min: s[0], q1: quantile(s, 0.25), med, q3: quantile(s, 0.75), max: s[s.length - 1], mad };
    });
  })();
  if (!groups.length) return <Empty />;
  const lo = Math.min(0, ...groups.map((g) => g.min)), hi = Math.max(0, ...groups.map((g) => g.max));
  const X = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`;
  return (
    <div>
      <div className="vw-head">
        <Segmented<string> label="Choice" value={active} onChange={setDim} options={dims.map((d) => ({ value: d, label: label(d) }))} />
      </div>
      {groups.map((g) => (
        <div key={g.k} className="dv-row" style={{ height: 30 }}>
          <span className="nm">{choiceLabel(active, g.k)} <span style={{ color: "var(--text-3)" }}>n={g.n}</span></span>
          <div className="dv-track">
            <div className="dv-axis" style={{ left: X(0) }} />
            <div style={{ position: "absolute", left: X(g.min), width: `calc(${X(g.max)} - ${X(g.min)})`, height: 2, background: "var(--text-3)" }} />
            <div style={{ position: "absolute", left: X(g.q1), width: `calc(${X(g.q3)} - ${X(g.q1)})`, height: 16, borderRadius: 3, background: "var(--accent-soft)", boxShadow: "inset 0 0 0 1px var(--accent-line)" }} />
            <div style={{ position: "absolute", left: X(g.med), height: 20, width: 2.5, background: "var(--accent)" }} />
          </div>
        </div>
      ))}
      <table className="vw-mini">
        <thead><tr><th>{label(active)}</th><th>N</th><th>Median</th><th>MAD</th><th>IQR</th></tr></thead>
        <tbody>{groups.map((g) => <tr key={g.k}><td>{choiceLabel(active, g.k)}</td><td>{g.n}</td><td>{num(g.med, 4)}</td><td>{num(g.mad, 4)}</td><td>{num(g.q3 - g.q1, 4)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

/** Sample-size strip under the specification curve: months per specification in curve order. */
export function SampleStrip({ rows }: { rows: Row[] }) {
  const ok = rows.filter((r) => isNum(r.coefficient)).sort((a, b) => (a.coefficient as number) - (b.coefficient as number));
  const ns = ok.map((r) => (isNum(r.months) ? r.months : 0));
  const mx = Math.max(1, ...ns);
  if (!ok.length || !ns.some(Boolean)) return null;
  return (
    <div>
      <div className="stat-l" style={{ marginBottom: 2 }}>Months per specification (max {mx})</div>
      <svg width="100%" height={28} viewBox={`0 0 ${ns.length} 28`} preserveAspectRatio="none" role="img" aria-label="Sample size per specification">
        {ns.map((v, i) => <rect key={i} x={i} width={0.8} y={28 - (v / mx) * 28} height={(v / mx) * 28} fill="var(--text-3)" opacity={0.6} />)}
      </svg>
    </div>
  );
}

/** Simulate the null: draw permutations one batch at a time, watch the histogram build, read p. */
export function SimulateNull({ values, observed, tail = "two", xLabel }: { values: number[]; observed: number | null; tail?: "right" | "left" | "two"; xLabel: string }) {
  const [drawn, setDrawn] = useState(0);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) cancelAnimationFrame(timer.current); }, []);
  const total = values.length;
  const run = (count: number) => {
    let target = Math.min(total, drawn + count);
    const step = () => {
      setDrawn((d) => { const nd = Math.min(target, d + Math.max(1, Math.ceil(count / 40))); if (nd < target) timer.current = requestAnimationFrame(step); return nd; });
    };
    if (drawn >= total) target = 0;
    step();
  };
  const [ref, width] = useWidth<HTMLDivElement>();
  const H = 170, m = { l: 8, r: 8, t: 8, b: 22 };
  const ext = useMemo(() => { const e = d3.extent([...values, ...(observed !== null ? [observed] : [])]) as [number, number]; return e; }, [values, observed]);
  const bins = useMemo(() => d3.bin().domain(ext).thresholds(24)(values.slice(0, drawn)), [values, ext, drawn]);
  const full = useMemo(() => d3.bin().domain(ext).thresholds(24)(values), [values, ext]);
  const x = d3.scaleLinear(ext, [m.l, Math.max(m.l + 1, width - m.r)]);
  const y = d3.scaleLinear([0, Math.max(1, d3.max(full, (b) => b.length) ?? 1)], [H - m.b, m.t]);
  const seen = values.slice(0, drawn);
  const hits = observed === null ? 0 : seen.filter((v) => (tail === "right" ? v >= observed : tail === "left" ? v <= observed : Math.abs(v) >= Math.abs(observed))).length;
  const p = seen.length ? (hits + 1) / (seen.length + 1) : null;
  return (
    <div ref={ref}>
      <div className="vw-head">
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" className="vw-btn" onClick={() => run(1)}>Draw 1</button>
          <button type="button" className="vw-btn" onClick={() => run(50)}>Draw 50</button>
          <button type="button" className="vw-btn" onClick={() => run(total)}>Draw all {total}</button>
          <button type="button" className="vw-btn" onClick={() => setDrawn(0)}>Reset</button>
        </div>
        <span className="num" style={{ fontSize: 12, color: "var(--text-2)" }}>{drawn}/{total} draws · p = {p === null ? "–" : p.toFixed(3)}</span>
      </div>
      {width > 0 ? (
        <svg width={width} height={H} role="img" aria-label="Simulated null distribution" style={{ display: "block", fontFamily: "var(--mono)" }}>
          {bins.map((b, i) => <rect key={i} x={x(b.x0 ?? 0) + 0.5} width={Math.max(0, x(b.x1 ?? 0) - x(b.x0 ?? 0) - 1)} y={y(b.length)} height={y(0) - y(b.length)} fill="var(--s1)" opacity={0.75} />)}
          <line x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} stroke="var(--line-3)" />
          {observed !== null ? <g><line x1={x(observed)} x2={x(observed)} y1={m.t} y2={y(0)} stroke="var(--accent)" strokeWidth={2} /><text x={x(observed)} y={m.t + 8} dx={4} fontSize={10} fill="var(--accent)">Observed {observed.toFixed(3)}</text></g> : null}
          {x.ticks(5).map((t) => <text key={t} x={x(t)} y={H - 6} fontSize={10} textAnchor="middle" fill="var(--text-3)">{t}</text>)}
        </svg>
      ) : null}
      <div className="stat-l">{xLabel}</div>
    </div>
  );
}
