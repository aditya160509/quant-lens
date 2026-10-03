"use client";

import * as d3 from "d3";
import { useMemo, useState } from "react";
import { BarList } from "@/charts/BarList";
import { Bars } from "@/charts/Bars";
import { SERIES, fmtTick, parseDate, robustExtent, useWidth } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { Forest, type ForestRow } from "@/charts/Forest";
import { Gauge } from "@/charts/Gauge";
import { Heatmap } from "@/charts/Heatmap";
import { PointRange, type PRSeries } from "@/charts/PointRange";
import { TimeSeries } from "@/charts/TimeSeries";
import { XYPlot } from "@/charts/XYPlot";
import { Segmented } from "@/workspace/ui";
import { first, fmtKey, isNum, label, num, out, pct, pval, tstat } from "../format";
import type { Row } from "../types";
import { DivergingBars, SimulateNull, withSwitch } from "./robustness";
import { Empty } from "./tables";
import type { ViewProps } from "./types";

const n = (v: unknown): number | null => (isNum(v) ? v : null);
const ret = (v: number) => pct(v, Math.abs(v) < 0.01 ? 2 : 1);
const f4 = (v: number) => num(v, 4);
const numericCols = (rows: Row[], skip: string[] = []) => [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((k) => !skip.includes(k) && rows.some((r) => isNum(r[k])));

// ---------------------------------------------------------------- time series

export function LineView({ rows, keys, opts, scope }: ViewProps) {
  if (!rows.length) return <Empty />;
  const x = (opts?.x as string | undefined) ?? "date";
  const keysToPlot = (opts?.series as string[] | undefined) ?? numericCols(rows, [x, "critical_5pct", "floor"]).slice(0, 6);
  if (!(x in rows[0])) {
    const [k] = keysToPlot;
    return <XYPlot points={[]} lines={[{ label: label(k), points: rows.map((r) => ({ x: n(r[x]) ?? 0, y: n(r[k]) ?? 0 })) }]} xLabel={label(x)} yLabel={label(k)} />;
  }
  const isRet = keysToPlot.every((k) => /return|ret$/.test(k));
  return (
    <TimeSeries data={rows} x={x} notesKey={`${scope}:${keys[0]}`}
      series={keysToPlot.map((k, i) => ({ key: k, label: label(k), color: SERIES[i % SERIES.length], width: k === "long_short" ? 2.2 : 1.5 }))}
      refLines={opts?.ref !== undefined ? [{ y: opts.ref as number }] : []}
      format={isRet ? ret : fmtTick} height={(opts?.height as number | undefined) ?? 260} />
  );
}

export function CoefficientPath({ rows, keys, scope }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sig = rows.filter((r) => isNum(r.lower_95) && isNum(r.upper_95) && ((r.lower_95 as number) > 0 || (r.upper_95 as number) < 0)).length;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <TimeSeries data={rows.map((r) => ({ ...r, sig: isNum(r.lower_95) && isNum(r.upper_95) && ((r.lower_95 as number) > 0 || (r.upper_95 as number) < 0) }))}
        series={[{ key: "beta", label: "Rolling slope", color: "var(--s1)", width: 1.8 }]} band={{ lo: "lower_95", hi: "upper_95", label: "95% band" }}
        refLines={[{ y: 0, dash: false }]} highlight="sig" format={f4} height={270} notesKey={`${scope}:${keys[0]}`} />
      <p className="stat-s">The slope is significant in {sig} of {rows.length} rolling windows (dots mark them).</p>
    </div>
  );
}

export function GrowthView({ rows, keys, scope }: ViewProps) {
  const data = useMemo(() => {
    const peaks: number[] = [];
    rows.forEach((r, i) => { const g = n(r.growth_of_1); peaks[i] = Math.max(i ? peaks[i - 1] : -Infinity, g ?? -Infinity); });
    return rows.map((r, i) => { const g = n(r.growth_of_1); return g === null ? r : { ...r, drawdown: g / peaks[i] - 1 }; });
  }, [rows]);
  if (!rows.length) return <Empty />;
  const last = n(rows[rows.length - 1].growth_of_1);
  const maxDd = Math.min(...data.map((r) => n(r.drawdown) ?? 0));
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 24 }}>
        <div><div className="stat-l">Final value of $1</div><div className="stat-v" style={{ color: last !== null && last >= 1 ? "var(--up)" : "var(--down)" }}>{last === null ? "–" : `$${last.toFixed(2)}`}</div></div>
        <div><div className="stat-l">Max drawdown</div><div className="stat-v" style={{ color: "var(--down)" }}>{pct(maxDd)}</div></div>
      </div>
      <TimeSeries data={data} series={[{ key: "growth_of_1", label: "Long-short growth of $1", kind: "area", color: "var(--s1)", width: 1.8 }]} refLines={[{ y: 1, dash: false }]} height={200} format={(v) => `$${v.toFixed(2)}`} notesKey={`${scope}:${keys[0]}`} />
      <TimeSeries data={data} series={[{ key: "drawdown", label: "Drawdown", kind: "area", color: "var(--down)" }]} height={110} format={(v) => pct(v, 0)} legend={false} />
    </div>
  );
}

export function CumulativeView({ rows, keys, scope }: ViewProps) {
  const cols = numericCols(rows, ["date"]);
  const data = useMemo(() => {
    const acc: Record<string, number> = Object.fromEntries(cols.map((c) => [c, 1]));
    return rows.map((r) => {
      const outRow: Row = { date: r.date };
      for (const c of cols) { const v = n(r[c]); if (v !== null) acc[c] *= 1 + v; outRow[c] = acc[c]; }
      return outRow;
    });
  }, [rows, cols]);
  if (!rows.length) return <Empty />;
  return (
    <TimeSeries data={data} height={280} notesKey={`${scope}:${keys[0]}`} format={(v) => `$${v.toFixed(2)}`} refLines={[{ y: 1, dash: false }]}
      series={cols.map((c, i) => ({ key: c, label: c === "long_short" ? "Long-short" : c, color: c === "long_short" ? "var(--text)" : SERIES[i % SERIES.length], width: c === "long_short" ? 2.2 : 1.4, dash: c === "long_short" }))} />
  );
}

export function RegimeTimeline({ result, keys, scope }: ViewProps) {
  const prob = out(result, "markov_state_probability");
  const regimes = out(result, keys[0] ?? "regime_timeline");
  const byDate = new Map(regimes.map((r) => [String(r.date), r.regime]));
  const data = (prob.length ? prob : regimes).map((r) => ({ ...r, regime: byDate.get(String(r.date)) ?? r.regime }));
  if (!data.length) return <Empty />;
  const def = first(result, "regime_definition");
  const on = typeof def?.description === "string" ? def.description : "Condition on";
  return (
    <TimeSeries data={data} height={240} notesKey={`${scope}:regimes`} format={(v) => pct(v, 0)} yLabel="P(high premium)"
      series={prob.length ? [{ key: "state_high_premium_probability", label: "Probability of the high-premium state", kind: "area", color: "var(--s1)" }] : []}
      ribbon={{ key: "regime", label: "Regime", colors: { on: "var(--warn)", off: "var(--s1)", [on]: "var(--warn)" } }} />
  );
}

export function BreakScan({ rows, result, keys, opts, scope }: ViewProps) {
  if (!rows.length) return <Empty text="Too few observations for a break scan." />;
  const crit = n(rows[0].critical_5pct);
  const info = first(result, (opts?.info as string | undefined) ?? "structural_break_tests");
  const markers = info && typeof info.break_date === "string" ? [{ date: info.break_date, label: `Most likely break ${String(info.break_date).slice(0, 7)}` }] : [];
  const regions = info && typeof info.break_ci90_low === "string" ? [{ from: info.break_ci90_low as string, to: (info.break_ci90_high as string | null) ?? undefined, label: "90% CI for the break date" }] : [];
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <TimeSeries data={rows} series={[{ key: "f_stat", label: "Chow F", color: "var(--s2)", width: 1.8 }]} refLines={crit !== null ? [{ y: crit, label: "5% critical value (sup-F)", color: "var(--down)" }] : []}
        markers={markers} regions={regions} format={(v) => v.toFixed(1)} height={250} notesKey={`${scope}:${keys[0]}`} />
      {info ? <p className="stat-s">sup-F {num(info.sup_f, 2)} against a 5% critical value of {num(info.critical_5pct, 2)}, p = {pval(info.p_value)}. Mean before {num(info.pre_mean, 4)}, after {num(info.post_mean, 4)}.</p> : null}
    </div>
  );
}

export function DecayCurve({ rows, result, keys, scope }: ViewProps) {
  if (!rows.length) return <Empty />;
  const markers = out(result, "event_markers").map((m) => ({ date: String(m.date), label: label(m.event), color: m.event === "discovery" ? "var(--warn)" : "var(--s4)" }));
  const floor = n(rows.find((r) => isNum(r.floor))?.floor);
  const fits = ["exponential_fit", "linear_fit", "hyperbolic_fit"].filter((k) => rows.some((r) => isNum(r[k])));
  const half = first(result, "half_life_output");
  return (
    <TimeSeries data={rows} height={300} markers={markers} notesKey={`${scope}:${keys[0]}`} format={f4}
      refLines={[{ y: 0, dash: false }, ...(floor !== null ? [{ y: floor, label: "Noise floor", color: "var(--text-3)" }] : [])]}
      regions={half && isNum(half.half_life_months) && markers[0] ? [] : []}
      series={[{ key: "rolling_metric", label: "Rolling predictive power", color: "var(--text)", width: 1.8 },
        ...fits.map((k, i) => ({ key: k, label: label(k.replace("_fit", "")), color: SERIES[(i + 1) % SERIES.length], dash: true }))]} />
  );
}

export function SharpeDecay({ rows, result, keys, scope }: ViewProps) {
  const markers = out(result, "event_markers").map((m) => ({ date: String(m.date), label: label(m.event), color: "var(--warn)" }));
  if (!rows.length) return <Empty />;
  return <TimeSeries data={rows} series={[{ key: "rolling_sharpe", label: "Rolling long-short Sharpe", kind: "area", color: "var(--s1)" }]} refLines={[{ y: 0, dash: false }]} markers={markers} height={240} format={(v) => v.toFixed(2)} notesKey={`${scope}:${keys[0]}`} />;
}

const SYN_M = { l: 44, r: 12, t: 12, b: 22 };

/** Treated vs synthetic path with effect arrow and parallelogram, time-weight strip, and a slider that shifts the control onto the treated path. */
export function SyntheticPath({ rows, result }: ViewProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [shift, setShift] = useState(0);
  const t = first(result, "treatment_effect");
  const pts = useMemo(() => rows.map((r) => ({ d: parseDate(r.date), y: n(r.treated), s: n(r.synthetic), w: n(r.time_weight), post: r.post === true })).filter((r): r is { d: number; y: number; s: number; w: number | null; post: boolean } => r.d !== null && r.y !== null && r.s !== null), [rows]);
  if (!pts.length) return <Empty />;
  const H = 300, WH = 18;
  const pre = pts.filter((p) => !p.post), post = pts.filter((p) => p.post);
  const preGap = pre.length ? d3.mean(pre, (p) => p.y - p.s) ?? 0 : 0;
  const off = shift * preGap;
  const x = d3.scaleLinear(d3.extent(pts, (p) => p.d) as [number, number], [SYN_M.l, Math.max(SYN_M.l + 1, width - SYN_M.r)]);
  const ext = d3.extent(pts.flatMap((p) => [p.y, p.s + off])) as [number, number];
  const y = d3.scaleLinear(ext, [H - SYN_M.b, SYN_M.t]).nice();
  const line = (f: (p: (typeof pts)[number]) => number) => d3.line<(typeof pts)[number]>().x((p) => x(p.d)).y((p) => y(f(p)))(pts) ?? "";
  const tau = post.length ? (d3.mean(post, (p) => p.y - p.s - off) ?? 0) : 0;
  const x0 = post.length ? x(post[0].d) : 0, x1 = post.length ? x(post[post.length - 1].d) : 0;
  const sy0 = post.length ? y(post[0].s + off) : 0, sy1 = post.length ? y(post[post.length - 1].s + off) : 0;
  const ty0 = post.length ? y(post[0].y) : 0, ty1 = post.length ? y(post[post.length - 1].y) : 0;
  const wmax = Math.max(1e-9, ...pts.map((p) => p.w ?? 0));
  const hasW = pts.some((p) => p.w !== null);
  const bw = Math.max(1, (x.range()[1] - x.range()[0]) / pts.length);
  return (
    <div ref={ref}>
      {width > 0 ? (
        <svg width={width} height={H + (hasW ? WH + 6 : 0)} role="img" aria-label="Treated and synthetic path" style={{ display: "block", fontFamily: "var(--mono)" }}>
          {y.ticks(5).map((v) => <g key={v}><line x1={SYN_M.l} x2={width - SYN_M.r} y1={y(v)} y2={y(v)} stroke="var(--line)" /><text x={SYN_M.l - 6} y={y(v)} dy={3} fontSize={10} textAnchor="end" fill="var(--text-3)">{fmtTick(v)}</text></g>)}
          {x.ticks(6).map((v) => <text key={v} x={x(v)} y={H - 6} fontSize={10} textAnchor="middle" fill="var(--text-3)">{new Date(v).getUTCFullYear()}</text>)}
          {post.length ? <path d={`M${x0},${sy0} L${x1},${sy1} L${x1},${ty1} L${x0},${ty0} Z`} fill="var(--accent)" opacity={0.1} /> : null}
          <path d={line((p) => p.s + off)} fill="none" stroke="var(--s1)" strokeWidth={1.8} strokeDasharray="5 3" />
          <path d={line((p) => p.y)} fill="none" stroke="var(--s2)" strokeWidth={2.2} />
          {post.length ? <g>
            <line x1={x1 + 4} x2={x1 + 4} y1={(sy1 + ty1) / 2 + (ty1 < sy1 ? 8 : -8) * -1} y2={ty1} stroke="var(--accent)" strokeWidth={1.6} />
            <path d={`M${x1 + 4},${ty1} l-3,${ty1 < sy1 ? 6 : -6} h6 Z`} fill="var(--accent)" />
            <line x1={x1 + 4} x2={x1 + 4} y1={sy1} y2={(sy1 + ty1) / 2} stroke="var(--accent)" strokeWidth={1.6} />
            <text x={x1 - 6} y={(sy1 + ty1) / 2} dy={3} textAnchor="end" fontSize={11} fill="var(--accent)">effect {tau.toFixed(3)}</text>
          </g> : null}
          {hasW ? <g transform={`translate(0,${H + 6})`}>
            {pts.map((p, i) => <rect key={i} x={x(p.d)} width={bw} height={WH} fill="var(--s3)" opacity={0.15 + 0.85 * ((p.w ?? 0) / wmax)} />)}
            <text x={SYN_M.l - 6} y={WH / 2} dy={3} fontSize={9} textAnchor="end" fill="var(--text-3)">time wt</text>
          </g> : null}
        </svg>
      ) : null}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
        <span className="stat-l" style={{ whiteSpace: "nowrap" }}>Shift {String(t?.treated_unit ?? "treated")} control</span>
        <input className="vw-slider" type="range" min={0} max={1} step={0.01} value={shift} onChange={(e) => setShift(Number(e.target.value))} aria-label="Shift synthetic control onto the treated pre-period" />
        <span className="num" style={{ fontSize: 12, color: "var(--text-2)" }}>{shift === 0 ? "as fitted" : `${Math.round(shift * 100)}% to treated`}</span>
      </div>
    </div>
  );
}

/** Treated gap against labelled top-donor placebo paths; click a path or label to highlight it. */
export function GapWithPlacebos({ result }: ViewProps) {
  const gap = out(result, "gap_plot");
  const placebo = out(result, "placebo_gap_paths");
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hl, setHl] = useState<string | null>(null);
  const paths = useMemo(() => {
    const m = new Map<string, { d: number; g: number }[]>();
    for (const r of placebo) { const d = parseDate(r.date), g = n(r.gap); if (d === null || g === null) continue; const u = String(r.unit); m.set(u, [...(m.get(u) ?? []), { d, g }]); }
    return [...m].map(([u, v]) => ({ u, v: v.sort((a, b) => a.d - b.d), score: Math.max(...v.map((q) => Math.abs(q.g))) })).sort((a, b) => b.score - a.score).slice(0, 80);
  }, [placebo]);
  const treated = useMemo(() => gap.map((r) => ({ d: parseDate(r.date), g: n(r.gap), post: r.post === true })).filter((r): r is { d: number; g: number; post: boolean } => r.d !== null && r.g !== null).sort((a, b) => a.d - b.d), [gap]);
  if (!treated.length) return <Empty />;
  const H = 300, m = { l: 44, r: 90, t: 12, b: 22 };
  const all = [...treated.map((p) => p.g), ...paths.flatMap((p) => p.v.map((q) => q.g))];
  const [elo, ehi] = robustExtent(all);
  const x = d3.scaleLinear(d3.extent(treated, (p) => p.d) as [number, number], [m.l, Math.max(m.l + 1, width - m.r)]);
  const y = d3.scaleLinear([elo, ehi], [H - m.b, m.t]);
  const ln = (v: { d: number; g: number }[]) => d3.line<{ d: number; g: number }>().x((p) => x(p.d)).y((p) => y(Math.max(elo, Math.min(ehi, p.g))))(v) ?? "";
  const labelled = new Set(paths.slice(0, 5).map((p) => p.u));
  const start = treated.find((p) => p.post)?.d;
  return (
    <div ref={ref}>
      {width > 0 ? (
        <svg width={width} height={H} role="img" aria-label="Treated gap against placebo gaps" style={{ display: "block", fontFamily: "var(--mono)" }} onClick={() => setHl(null)}>
          {y.ticks(5).map((v) => <g key={v}><line x1={m.l} x2={width - m.r} y1={y(v)} y2={y(v)} stroke={v === 0 ? "var(--line-3)" : "var(--line)"} /><text x={m.l - 6} y={y(v)} dy={3} fontSize={10} textAnchor="end" fill="var(--text-3)">{fmtTick(v)}</text></g>)}
          {x.ticks(6).map((v) => <text key={v} x={x(v)} y={H - 6} fontSize={10} textAnchor="middle" fill="var(--text-3)">{new Date(v).getUTCFullYear()}</text>)}
          {start ? <line x1={x(start)} x2={x(start)} y1={m.t} y2={H - m.b} stroke="var(--warn)" strokeDasharray="3 3" /> : null}
          {paths.map((p) => {
            const on = hl === p.u;
            const last = p.v[p.v.length - 1];
            return (
              <g key={p.u} onClick={(e) => { e.stopPropagation(); setHl(on ? null : p.u); }} style={{ cursor: "pointer" }}>
                <path d={ln(p.v)} fill="none" stroke={on ? "var(--s4)" : "var(--text-3)"} strokeWidth={on ? 2.2 : 1} opacity={hl && !on ? 0.12 : on ? 1 : 0.35} />
                <path d={ln(p.v)} fill="none" stroke="transparent" strokeWidth={8} />
                {(labelled.has(p.u) || on) && last ? <text x={x(last.d) + 4} y={y(Math.max(elo, Math.min(ehi, last.g)))} dy={3} fontSize={10} fill={on ? "var(--s4)" : "var(--text-3)"}>{p.u}</text> : null}
              </g>
            );
          })}
          <path d={ln(treated)} fill="none" stroke="var(--s2)" strokeWidth={2.6} opacity={hl ? 0.5 : 1} />
        </svg>
      ) : null}
      <p className="stat-s">Click a donor path to highlight it; the five most extreme donors are labelled.</p>
    </div>
  );
}

export function ConformalBand({ rows, keys, scope }: ViewProps) {
  if (!rows.length) return <Empty />;
  const cov = n(rows[0].coverage);
  return <TimeSeries data={rows} series={[{ key: "effect", label: "Monthly effect", color: "var(--s4)", width: 1.8 }]} band={{ lo: "lower", hi: "upper", color: "color-mix(in oklch, var(--s4) 18%, transparent)", label: `${cov ? Math.round(cov * 100) : 90}% conformal band` }} refLines={[{ y: 0, dash: false }]} height={240} format={(v) => v.toFixed(3)} notesKey={`${scope}:${keys[0]}`} />;
}

// ---------------------------------------------------------------- bars

export function PortfolioLadder({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const bars = rows.map((r) => {
    const m = n(r.mean_return) ?? 0;
    const se = isNum(r.std) && isNum(r.periods) && (r.periods as number) > 0 ? (r.std as number) / Math.sqrt(r.periods as number) : null;
    const ls = r.portfolio === "long_short";
    return {
      label: ls ? "Long-short" : String(r.portfolio), value: m, lo: se === null ? null : m - 1.96 * se, hi: se === null ? null : m + 1.96 * se,
      color: ls ? (m >= 0 ? "var(--up)" : "var(--down)") : "var(--s1)",
      detail: [["t-stat", tstat(r.t_stat)], ["Annual Sharpe", num(r.sharpe_annual, 2)], ["Bootstrap p", pval(r.bootstrap_p_value)], ["Alpha", ret(n(r.alpha) ?? 0)], ["Months", fmtKey("periods", r.periods)]] as [string, string][],
    };
  });
  return <Bars bars={bars} format={ret} signed={false} height={260} yLabel="Mean monthly return" />;
}

export function BarsView({ rows, opts }: ViewProps) {
  if (!rows.length) return <Empty />;
  const r0 = rows[0];
  const lab = (opts?.label as string | undefined) ?? Object.keys(r0).find((k) => typeof r0[k] === "string") ?? Object.keys(r0)[0];
  const val = (opts?.value as string | undefined) ?? numericCols(rows, [lab])[0];
  const isRet = /return|spread|share|power/.test(val);
  return <Bars bars={rows.map((r) => ({ label: label(r[lab]), value: n(r[val]) ?? 0, detail: Object.entries(r).filter(([k]) => k !== lab && k !== val).map(([k, v]) => [label(k), fmtKey(k, v)] as [string, string]) }))}
    format={isRet ? ret : (v) => num(v, 3)} refLines={(opts?.refLines as { y: number; label?: string }[] | undefined) ?? []} signed={opts?.signed !== false} yLabel={label(val)} height={(opts?.height as number | undefined) ?? 220} />;
}

export function Correlogram({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const band = n(rows[0].upper_95) ?? 0;
  const sig = rows.filter((r) => r.significant === true).length;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <Bars bars={rows.map((r) => ({ label: String(r.lag), value: n(r.acf) ?? 0, color: r.significant ? "var(--down)" : "var(--s1)" }))} refLines={[{ y: band, label: "95% band", color: "var(--text-3)" }, { y: -band, color: "var(--text-3)" }]} format={(v) => v.toFixed(2)} valueLabels={false} height={220} />
      <p className="stat-s">{sig ? `${sig} lag${sig > 1 ? "s" : ""} outside the band: residuals are autocorrelated.` : "Every lag sits inside the band: no residual autocorrelation."}</p>
    </div>
  );
}

function PlaceboRankingBars({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(b.post_pre_ratio) ?? 0) - (n(a.post_pre_ratio) ?? 0));
  const rank = sorted.findIndex((r) => r.treated === true) + 1;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <Bars bars={sorted.map((r) => ({ label: String(r.unit), value: n(r.post_pre_ratio) ?? 0, color: r.treated ? "var(--s2)" : "color-mix(in oklch, var(--text-3) 70%, transparent)" }))} format={(v) => v.toFixed(1)} signed={false} valueLabels={false} hideLabels height={220} yLabel="Post / pre RMSPE" />
      {rank ? <p className="stat-s">The treated unit ranks {rank} of {sorted.length}: a permutation p-value of {(rank / sorted.length).toFixed(3)}.</p> : null}
    </div>
  );
}

export const PlaceboRanking = withSwitch(PlaceboRankingBars, "Ranking", "Contribution", function PlaceboDiverging({ rows }: ViewProps) {
  const base = d3.median(rows, (r) => n(r.post_pre_ratio)) ?? 0;
  return <DivergingBars items={rows.map((r) => ({ label: String(r.unit), value: (n(r.post_pre_ratio) ?? 0) - base })).filter((d) => d.value !== 0 || true).slice(0, 25)} format={(v) => num(v, 2)} allLabel="Treated vs median" total={((n(rows.find((r) => r.treated === true)?.post_pre_ratio) ?? base) - base)} />;
});

export function DensityView({ rows, result }: ViewProps) {
  if (!rows.length) return <Empty />;
  const est = first(result, "rd_estimate");
  const test = first(result, "rd_density_test");
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <Bars bars={rows.map((r) => ({ label: num(r.x, 0), value: n(r.count) ?? 0, color: r.side === "left" ? "var(--s1)" : "var(--s3)" }))} format={(v) => v.toFixed(0)} signed={false} valueLabels={false} height={210} yLabel="Observations per bin" />
      <p className="stat-s">Cutoff at {num(est?.cutoff, 1)}. Manipulation test p = {pval(test?.p_value)}: {test?.manipulation_detected ? "bunching at the cutoff, so the design is suspect." : "no bunching at the cutoff."}</p>
    </div>
  );
}

export function DonorWeights({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return <BarList bars={[...rows].sort((a, b) => (n(b.weight) ?? 0) - (n(a.weight) ?? 0)).map((r) => ({ label: String(r.donor), value: n(r.weight) ?? 0, note: [r.sector, isNum(r.pre_volatility) ? `vol ${pct(r.pre_volatility)}` : null].filter(Boolean).join(" · ") }))} format={(v) => pct(v)} max={1} />;
}

// ---------------------------------------------------------------- distributions

function observedFrom(result: ViewProps["result"], hint?: { key: string; field: string }) {
  if (hint) { const v = n(first(result, hint.key)?.[hint.field]); if (v !== null) return v; }
  for (const v of Object.values(result.tables)) {
    for (const r of Array.isArray(v) ? v : []) {
      const k = ["observed", "observed_t", "real_estimate", "real_t_stat"].find((x) => isNum((r as Row)[x]));
      if (k) return (r as Row)[k] as number;
    }
  }
  return null;
}

export function NullDistributionView({ rows, result, opts }: ViewProps) {
  const [sim, setSim] = useState(false);
  const key = rows[0] ? Object.keys(rows[0]).find((k) => isNum(rows[0][k])) : undefined;
  const values = useMemo(() => (key ? rows.map((r) => r[key]).filter(isNum) : []), [rows, key]);
  if (!values.length) return <Empty />;
  const observed = observedFrom(result, opts?.observed as { key: string; field: string } | undefined);
  const tail = (opts?.tail as "right" | "left" | "two" | undefined) ?? "two";
  const xLabel = (opts?.xLabel as string | undefined) ?? label(key);
  return (
    <div>
      <div className="vw-head"><span /><Segmented label="Null view" value={sim ? "sim" : "static"} onChange={(v) => setSim(v === "sim")} options={[{ value: "static", label: "Distribution" }, { value: "sim", label: "Simulate the null" }]} /></div>
      {sim ? <SimulateNull values={values} observed={observed} tail={tail} xLabel={xLabel} /> : <Distribution values={values} observed={observed} tail={tail} xLabel={xLabel} observedLabel={(opts?.observedLabel as string | undefined) ?? "Observed"} format={(v) => v.toFixed(Math.abs(v) < 0.1 ? 3 : 2)} />}
    </div>
  );
}

export function HistogramView({ rows, opts }: ViewProps) {
  const key = rows[0] ? Object.keys(rows[0]).find((k) => isNum(rows[0][k])) : undefined;
  const values = useMemo(() => (key ? rows.map((r) => r[key]).filter(isNum) : []), [rows, key]);
  if (!values.length) return <Empty />;
  return <Distribution values={values} observed={opts?.zero === false ? null : 0} observedLabel="Zero" tail="right" xLabel={label(key)} format={(v) => v.toFixed(3)} />;
}

// ---------------------------------------------------------------- scatter

export function ScatterView({ rows, opts }: ViewProps) {
  const [x, y] = (opts?.xy as [string, string] | undefined) ?? numericCols(rows).slice(0, 2);
  if (!rows.length || !x || !y) return <Empty />;
  return <XYPlot points={rows.map((r) => ({ x: n(r[x]) ?? 0, y: n(r[y]) ?? 0 }))} xLabel={label(x)} yLabel={label(y)} robust formatX={fmtTick} formatY={fmtTick} height={280} />;
}

export function QQView({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return <XYPlot points={rows.map((r) => ({ x: n(r.theoretical) ?? 0, y: n(r.sample) ?? 0 }))} xLabel="Normal quantile" yLabel="Sample quantile" diagonal square height={280} formatX={(v) => v.toFixed(1)} formatY={(v) => v.toFixed(1)} />;
}

export function PartialResiduals({ rows }: ViewProps) {
  const groups = useMemo(() => rows.reduce<Record<string, Row[]>>((acc, r) => ({ ...acc, [String(r.regressor)]: [...(acc[String(r.regressor)] ?? []), r] }), {}), [rows]);
  if (!rows.length) return <Empty />;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
      {Object.entries(groups).map(([name, g]) => (
        <div key={name}>
          <div style={{ fontSize: 12, fontWeight: 550, marginBottom: 4 }}>{label(name)}</div>
          <XYPlot points={g.map((r) => ({ x: n(r.x) ?? 0, y: n(r.component_plus_residual) ?? 0 }))} lines={[{ label: "Linear fit", points: g.map((r) => ({ x: n(r.x) ?? 0, y: n(r.linear_fit) ?? 0 })), color: "var(--s2)" }]}
            xLabel={label(name)} yLabel="Component + residual" height={200} formatX={fmtTick} formatY={fmtTick} robust />
        </div>
      ))}
    </div>
  );
}

export function BaconScatter({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const twfe = n(rows[0].twfe_implied);
  const forbidden = rows.filter((r) => r.forbidden_comparison === true).reduce((s, r) => s + (n(r.weight) ?? 0), 0);
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <XYPlot points={rows.map((r) => ({ x: n(r.weight) ?? 0, y: n(r.estimate) ?? 0, group: String(r.comparison), detail: [["Treated cohort", String(r.treated_cohort)], ["Control", String(r.control_cohort)], ["Contribution", num(r.contribution, 4)]] }))}
        xLabel="Weight in TWFE" yLabel="2×2 DiD estimate" refY={twfe !== null ? [{ y: twfe, label: `TWFE ${twfe.toFixed(4)}` }] : []} robust height={280} formatX={(v) => v.toFixed(3)} formatY={(v) => v.toFixed(3)} />
      <p className="stat-s">{pct(forbidden)} of the TWFE weight comes from forbidden comparisons (already-treated units used as controls).</p>
    </div>
  );
}

export function RdPlot({ rows, result }: ViewProps) {
  if (!rows.length) return <Empty />;
  const est = first(result, "rd_estimate");
  const cutoff = n(est?.cutoff);
  const left = rows.filter((r) => r.side === "left");
  const right = rows.filter((r) => r.side === "right");
  const fit = (rs: Row[]) => rs.filter((r) => isNum(r.fit)).map((r) => ({ x: r.x as number, y: r.fit as number }));
  return (
    <XYPlot points={rows.map((r) => ({ x: n(r.x) ?? 0, y: n(r.y) ?? 0, group: r.side === "left" ? "Below cutoff" : "Above cutoff", size: Math.max(2.5, Math.min(7, Math.sqrt(n(r.n) ?? 9))), detail: [["Observations", fmtKey("n", r.n)]] }))}
      groupColors={{ "Below cutoff": "var(--s1)", "Above cutoff": "var(--s3)" }}
      lines={[{ label: "Fit below", points: fit(left), color: "var(--s1)" }, { label: "Fit above", points: fit(right), color: "var(--s3)" }]}
      refX={cutoff !== null ? [{ x: cutoff, label: `Cutoff ${cutoff}` }] : []}
      xLabel={String(est?.running_unit ?? est?.running_variable ?? "Running variable")} yLabel="Outcome (binned mean)" height={320} formatX={fmtTick} formatY={(v) => v.toFixed(3)} />
  );
}

export function ZooScatter({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return (
    <XYPlot points={rows.map((r) => ({ x: n(r.ic_ir) ?? 0, y: n(r.sharpe) ?? 0, label: r.candidate ? "Your signal" : label(r.factor), emphasis: r.candidate === true }))}
      xLabel="IC information ratio" yLabel="Long-short Sharpe" labelPoints quadrants={["Strong on both", "Sharpe only", "Weak on both", "IC only"]} height={320} formatX={(v) => v.toFixed(2)} formatY={(v) => v.toFixed(2)} />
  );
}

export function ArCurve({ rows, result }: ViewProps) {
  if (!rows.length) return <Empty />;
  const set = first(result, "anderson_rubin_confidence_set");
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <XYPlot points={[]} lines={[{ label: "AR test p-value", points: rows.map((r) => ({ x: n(r.beta0) ?? 0, y: n(r.p_value) ?? 0 })), color: "var(--s1)" }]} refY={[{ y: 0.05, label: "5% level" }]}
        xLabel="Hypothesised coefficient" yLabel="p-value" height={240} formatX={(v) => v.toExponential(1)} formatY={(v) => v.toFixed(2)} />
      {set ? <p className="stat-s">Weak-instrument-robust 95% set: {String(set.description ?? "")}{isNum(set.low) ? ` [${num(set.low, 5)}, ${num(set.high, 5)}]` : ""}.</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- point ranges

const EVENT_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];

export function EventStudy({ result, keys, opts }: ViewProps) {
  const [win, setWin] = useState<number>((opts?.window as number | undefined) ?? 12);
  const names = (opts?.names as string[] | undefined) ?? keys.map(label);
  const series: PRSeries[] = keys.map((k, i) => {
    const rows = out(result, k);
    const xk = ["event_time", "event_day"].find((x) => rows[0] && x in rows[0]) ?? "event_time";
    const yk = ["estimate", "mean_car", "pooled_effect"].find((y) => rows[0] && y in rows[0]) ?? "estimate";
    return {
      label: names[i] ?? label(k), color: EVENT_COLORS[i % EVENT_COLORS.length],
      points: rows.map((r) => ({ x: n(r[xk]) ?? 0, y: n(r[yk]) ?? 0, lo: n(r.lower_95), hi: n(r.upper_95) })).filter((p) => win <= 0 || Math.abs(p.x) <= win),
    };
  }).filter((s) => s.points.length);
  if (!series.length) return <Empty />;
  const daily = keys.some((k) => /car/.test(k));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {!daily ? (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Segmented<number> label="Event window" value={win} onChange={setWin} options={[{ value: 6, label: "±6" }, { value: 12, label: "±12" }, { value: 24, label: "±24" }, { value: 0, label: "All" }]} />
        </div>
      ) : null}
      <PointRange series={series.map((s) => ({ ...s, bandStyle: daily ? "ribbon" : "whiskers" }))} event={{ x: daily ? 0 : -0.5, label: "Event" }} shadePre
        xLabel={daily ? "Days from event" : "Months from treatment"} yLabel={daily ? "Mean CAR" : "Effect"} format={(v) => (daily ? pct(v, 1) : v.toFixed(3))} height={300} />
    </div>
  );
}

export function SensitivityView({ rows, opts }: ViewProps) {
  if (!rows.length) return <Empty />;
  const x = (opts?.x as string | undefined) ?? ("bandwidth_multiple" in rows[0] ? "bandwidth_multiple" : "cutoff");
  const real = x === "bandwidth_multiple" ? 1 : rows.find((r) => r.shift_pct === 0)?.cutoff;
  return (
    <PointRange series={[{ label: "Bias-corrected estimate", color: "var(--s1)", points: rows.map((r) => ({ x: n(r[x]) ?? 0, y: n(r.estimate_bias_corrected ?? r.estimate) ?? 0, lo: n(r.ci_robust_low), hi: n(r.ci_robust_high) })) }]}
      xLabel={x === "bandwidth_multiple" ? "Bandwidth (× optimal)" : "Cutoff"} yLabel="Estimate" highlightX={isNum(real) ? real : null} format={(v) => v.toFixed(3)} formatX={(v) => (x === "bandwidth_multiple" ? `${v}×` : String(v))} height={250} />
  );
}

export function QuantileView({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return (
    <PointRange series={[{ label: "Slope on condition", color: "var(--s1)", points: rows.map((r) => {
      const y = n(r.slope_on_condition) ?? 0, se = n(r.se);
      return { x: n(r.quantile) ?? 0, y, lo: se === null ? null : y - 1.96 * se, hi: se === null ? null : y + 1.96 * se };
    }) }]} xLabel="Return quantile" yLabel="Slope" formatX={(v) => `${Math.round(v * 100)}th`} format={(v) => v.toFixed(3)} height={240} robust={false} />
  );
}

// ---------------------------------------------------------------- forests

export function ForestView({ rows, opts }: ViewProps) {
  if (!rows.length) return <Empty />;
  const r0 = rows[0];
  const lab = (opts?.label as string | undefined) ?? ["column", "regime", "factor", "estimator", "covariate", "excluded_donor", "cohort"].find((k) => k in r0) ?? Object.keys(r0)[0];
  const est = (opts?.estimate as string | undefined) ?? ["coefficient", "estimate", "estimate_bias_corrected", "post_effect", "standardized_mean_difference"].find((k) => k in r0) ?? "estimate";
  const lo = ["lower_95", "ci_robust_low"].find((k) => k in r0);
  const hi = ["upper_95", "ci_robust_high"].find((k) => k in r0);
  const rowsF: ForestRow[] = rows.map((r) => ({
    label: label(r[lab]), sub: r.tag ? label(r.tag) : r.nobs ? `N ${fmtKey("nobs", r.nobs)}` : undefined,
    estimate: n(r[est]) ?? 0, lo: lo ? n(r[lo]) : null, hi: hi ? n(r[hi]) : null,
    tone: r.tag === "confirmatory" ? "accent" : undefined,
  }));
  return <Forest rows={rowsF} format={(v) => num(v, Math.abs(v) < 0.1 ? 4 : 3)} refX={(opts?.refX as number | null | undefined) ?? 0} />;
}

export function LovePlot({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const bad = rows.filter((r) => r.imbalanced === true).length;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <Forest rows={rows.map((r) => ({ label: label(r.covariate), sub: `treated ${num(r.treated_mean, 2)} · control ${num(r.control_mean, 2)}`, estimate: n(r.standardized_mean_difference) ?? 0, lo: null, hi: null, tone: r.imbalanced ? "down" : "up" }))} format={(v) => v.toFixed(2)} refLabel="balanced" />
      <p className="stat-s">{bad ? `${bad} covariate${bad > 1 ? "s are" : " is"} imbalanced (|SMD| above 0.1) before matching.` : "Every covariate is balanced (|SMD| at most 0.1)."}</p>
    </div>
  );
}

export function SpanningBetas({ rows }: ViewProps) {
  const r = rows[0];
  if (!r) return <Empty />;
  const factors = Object.keys(r).filter((k) => k.startsWith("beta_")).map((k) => k.slice(5));
  const rowsF: ForestRow[] = factors.map((f) => {
    const b = n(r[`beta_${f}`]) ?? 0, t = n(r[`t_${f}`]);
    const se = t ? Math.abs(b / t) : null;
    return { label: label(f), estimate: b, lo: se === null ? null : b - 1.96 * se, hi: se === null ? null : b + 1.96 * se };
  });
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 28 }}>
        <div><div className="stat-l">Alpha (monthly)</div><div className="stat-v">{ret(n(r.alpha) ?? 0)}</div></div>
        <div><div className="stat-l">Alpha t</div><div className="stat-v">{tstat(r.alpha_t ?? r.t)}</div></div>
        <div><div className="stat-l">R²</div><div className="stat-v">{pct(r.r2, 0)}</div></div>
      </div>
      {rowsF.length ? <Forest rows={rowsF} format={(v) => v.toFixed(3)} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------- heatmaps

export function DoubleSort({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const lab = Object.keys(rows[0])[0];
  const cols = Object.keys(rows[0]).filter((k) => k !== lab && k !== "row_spread");
  return <Heatmap rows={rows.map((r) => String(r[lab]).replace("S1_", "Signal "))} cols={cols.map((c) => c.replace("S2_", ""))} values={rows.map((r) => cols.map((c) => n(r[c])))} format={(v) => pct(v, 2)} rowTitle="Signal bucket" colTitle="Second sort" margin={rows.some((r) => "row_spread" in r) ? { label: "Spread", values: rows.map((r) => n(r.row_spread)) } : undefined} />;
}

export function CorrelationMap({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const cols = Object.keys(rows[0]).filter((k) => k !== "factor");
  return <Heatmap rows={rows.map((r) => (r.factor === "candidate" ? "Your signal" : label(r.factor)))} cols={cols.map((c) => (c === "candidate" ? "Signal" : label(c)))} values={rows.map((r) => cols.map((c) => n(r[c])))} format={(v) => v.toFixed(2)} highlightRow={rows.findIndex((r) => r.factor === "candidate")} outline={(i, j) => i !== j && Math.abs(n(rows[i][cols[j]]) ?? 0) >= 0.7} />;
}

// ---------------------------------------------------------------- gauges and rulers

export function VitalityGauge({ rows }: ViewProps) {
  const r = rows[0];
  if (!r || !isNum(r.vitality_score)) return <Empty />;
  return <Gauge value={r.vitality_score as number} min={-100} max={150} label="Vitality score"
    zones={[{ to: 0, color: "var(--down)", label: "Dead" }, { to: 30, color: "var(--s5)", label: "Fading" }, { to: 70, color: "var(--warn)", label: "Weakened" }, { to: 150, color: "var(--up)", label: "Alive" }]}
    sub={`Last ${num(r.recent_window_months)} months at ${num(r.vitality_score, 0)}% of the in-sample strength (${num(r.in_sample_mean, 4)}). Zone: ${label(r.zone)}.`} />;
}

/** Observed t against every multiple-testing hurdle on one ruler. */
export function HlzRuler({ rows }: ViewProps) {
  const r = rows[0];
  if (!r) return <Empty />;
  const t = Math.abs(n(r.observed_t) ?? 0);
  const marks = [
    ["t = 2.0", r["threshold_t_2.0"]], ["t = 3.0", r["threshold_t_3.0"]], ["HLZ BHY", r.threshold_hlz_bhy], ["HLZ Holm", r.threshold_hlz_holm],
    ["HLZ Bonferroni", r.threshold_hlz_bonferroni], ["Bonferroni now", r.threshold_bonferroni_current],
  ].filter((m): m is [string, number] => isNum(m[1])).sort((a, b) => a[1] - b[1]);
  const max = Math.max(4.5, t * 1.15, ...marks.map((m) => m[1] * 1.08));
  const X = (v: number) => `${(v / max) * 100}%`;
  const req = n(r.required_t) ?? 3;
  const pass = t >= req;
  return (
    <div style={{ display: "grid", gap: 18 }}>
      <div style={{ display: "flex", gap: 28, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div><div className="stat-l">Your |t| ({String(r.observed_t_source ?? "")})</div><div className="stat-v lg" style={{ color: pass ? "var(--up)" : "var(--down)" }}>{t.toFixed(2)}</div></div>
        <div><div className="stat-l">Required ({label(r.threshold_rule)})</div><div className="stat-v lg">{req.toFixed(2)}</div></div>
        <span className={`chip ${pass ? "up" : "down"}`} style={{ marginBottom: 6 }}>{pass ? "Clears the hurdle" : "Below the hurdle"}</span>
      </div>
      <div style={{ position: "relative", height: 74, margin: "0 6px" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 30, height: 8, borderRadius: 4, background: "linear-gradient(90deg, var(--down-soft), var(--warn-soft) 55%, var(--up-soft))" }} />
        {marks.map(([name, v], i) => (
          <div key={name} style={{ position: "absolute", left: X(v), top: i % 2 ? 42 : 0, transform: "translateX(-50%)", textAlign: "center", fontSize: 11, color: "var(--text-3)", whiteSpace: "nowrap" }}>
            {i % 2 ? <div style={{ width: 1, height: 10, background: "var(--line-3)", margin: "0 auto 2px" }} /> : null}
            <span>{name} <span className="num">{v.toFixed(2)}</span></span>
            {i % 2 ? null : <div style={{ width: 1, height: 12, background: "var(--line-3)", margin: "2px auto 0" }} />}
          </div>
        ))}
        <div style={{ position: "absolute", left: X(t), top: 22, transform: "translateX(-50%)", width: 4, height: 24, borderRadius: 2, background: pass ? "var(--up)" : "var(--down)", boxShadow: "0 0 0 3px var(--panel)" }} />
      </div>
      {typeof r.note === "string" ? <p className="stat-s">{r.note}</p> : null}
    </div>
  );
}

export function FirstStage({ rows }: ViewProps) {
  const r = rows[0];
  if (!r) return <Empty />;
  const f = n(r.f_stat) ?? 0;
  const max = Math.max(120, f * 1.1);
  const X = (v: number) => `${(Math.min(v, max) / max) * 100}%`;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        <div><div className="stat-l">First-stage F</div><div className="stat-v lg" style={{ color: f >= 104.7 ? "var(--up)" : f >= 10 ? "var(--warn)" : "var(--down)" }}>{f.toFixed(2)}</div></div>
        <div><div className="stat-l">Partial R²</div><div className="stat-v">{pct(r.partial_r2, 1)}</div></div>
        <div><div className="stat-l">Endogenous</div><div className="stat-v" style={{ fontSize: 16 }}>{label(r.endogenous)}</div></div>
      </div>
      <div style={{ position: "relative", height: 46 }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 18, height: 8, borderRadius: 4, background: "var(--grid)" }} />
        <div style={{ position: "absolute", left: 0, width: X(f), top: 18, height: 8, borderRadius: 4, background: f >= 104.7 ? "var(--up)" : f >= 10 ? "var(--warn)" : "var(--down)" }} />
        {[[10, "Staiger-Stock 10"], [104.7, "Lee et al. 104.7"]].map(([v, l]) => (
          <div key={String(l)} style={{ position: "absolute", left: X(v as number), top: 0, transform: "translateX(-50%)", fontSize: 11, color: "var(--text-3)", textAlign: "center", whiteSpace: "nowrap" }}>
            {l}<div style={{ width: 1, height: 30, background: "var(--line-3)", margin: "2px auto 0" }} />
          </div>
        ))}
      </div>
      <p className="stat-s">{f >= 104.7 ? "Strong instruments by the modern standard." : f >= 10 ? "Passes the classic rule of thumb but not the stricter Lee et al. bar: t-based inference can still be off." : "Weak instruments: rely on the Anderson-Rubin set, not the 2SLS t-statistic."}</p>
    </div>
  );
}

export function OosCompare({ result }: ViewProps) {
  const r = first(result, "mclean_pontiff_oos");
  if (!r) return <Empty />;
  const ratio = n(r.oos_is_ratio);
  const tone = r.color === "green" ? "var(--up)" : r.color === "red" ? "var(--down)" : "var(--warn)";
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        <div><div className="stat-l">OOS / IS ratio</div><div className="stat-v lg" style={{ color: tone }}>{ratio === null ? "–" : ratio.toFixed(2)}</div></div>
        <div><div className="stat-l">Split</div><div className="stat-v" style={{ fontSize: 16 }}>{String(r.split_date ?? "").slice(0, 7)}</div></div>
      </div>
      <Bars bars={[
        { label: `In sample (${fmtKey("months", r.is_months)}m)`, value: n(r.is_coefficient) ?? 0, color: "var(--s1)", detail: [["t", tstat(r.is_t)]] },
        { label: `Out of sample (${fmtKey("months", r.oos_months)}m)`, value: n(r.oos_coefficient) ?? 0, color: tone, detail: [["t", tstat(r.oos_t)]] },
      ]} format={f4} signed={false} height={190} />
      <p className="stat-s">Above 0.7 the effect holds out of sample, 0.3 to 0.7 it decays, below 0.3 it is mostly gone.</p>
    </div>
  );
}

export function PowerBars({ rows }: ViewProps) {
  const r = rows[0];
  if (!r) return <Empty />;
  const items = Object.entries(r).filter(([k]) => k.startsWith("power_") || k === "battery_power").filter(([, v]) => isNum(v)) as [string, number][];
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <BarList bars={items.map(([k, v]) => ({ label: label(k.replace("power_", "")), value: v, tone: v >= 0.8 ? "up" : v >= 0.5 ? "accent" : "down" }))} format={(v) => pct(v, 0)} max={1} />
      {typeof r.message === "string" ? <p className="stat-s">{r.message}</p> : null}
    </div>
  );
}
