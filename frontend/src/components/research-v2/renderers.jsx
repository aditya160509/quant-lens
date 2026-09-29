"use client";

import { useMemo, useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { T, SERIES, axis, downloadBase64, downloadText, fmt, isNum, pColor, title, tooltipStyle } from "./format";

const H = 300;
const rowsOf = (v) => (Array.isArray(v) ? v : v && typeof v === "object" ? [v] : []);
const numericCols = (rows, skip = []) => [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((k) => !skip.includes(k) && rows.some((r) => isNum(r[k])));
const xKey = (rows) => ["date", "event_time", "event_day", "rank", "lag", "quantile", "x", "period", "portfolio"].find((k) => rows[0] && k in rows[0]) ?? Object.keys(rows[0] ?? {})[0];
const band = (rows, lo = "lower_95", hi = "upper_95") => rows.map((r) => ({ ...r, band: isNum(r[lo]) && isNum(r[hi]) ? [r[lo], r[hi]] : null }));

function Frame({ children, height = H }) {
  return <div style={{ width: "100%", height }}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>;
}

// ---------------------------------------------------------------- tables

export function DataTable({ value, maxRows = 200 }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return <div className="rv2-table-wrap"><table className="rv2-table"><thead><tr>{cols.map((c) => <th key={c}>{title(c)}</th>)}</tr></thead>
    <tbody>{rows.slice(0, maxRows).map((r, i) => <tr key={i}>{cols.map((c) => <td key={c} style={/p_value|pvalue/.test(c) ? { color: pColor(r[c]) } : undefined}>{fmt(r[c])}</td>)}</tr>)}</tbody></table>
    {rows.length > maxRows ? <small className="rv2-note">Showing {maxRows} of {rows.length} rows; the CSV export has all of them.</small> : null}</div>;
}

export function KeyValue({ value }) {
  const row = rowsOf(value)[0];
  if (!row) return <Empty />;
  const entries = Object.entries(row).flatMap(([k, v]) => (v && typeof v === "object" && !Array.isArray(v) ? Object.entries(v).map(([k2, v2]) => [`${k} ${k2}`, v2]) : [[k, v]]));
  return <dl className="rv2-kv">{entries.map(([k, v]) => <div key={k}><dt>{title(k)}</dt><dd style={/p_value|pvalue/.test(k) ? { color: pColor(v) } : undefined}>{fmt(v)}</dd></div>)}</dl>;
}

const STAT_KEYS = ["statistic", "sup_f", "f_stat", "chi2_stat", "grs_stat", "mr_statistic", "t_stat", "observed", "observed_t", "joint_p_value", "treated_ratio", "vitality_score", "condition_number", "post_pre_rmspe_ratio"];
const P_KEYS = ["p_value", "bootstrap_p_value", "placebo_p_value", "p_value_robust", "fisher_p_value"];

export function TestCard({ value }) {
  const row = rowsOf(value)[0];
  if (!row) return <Empty />;
  if (row.available === false) return <Note text={row.reason || row.status || "Not available for this configuration."} />;
  const statKey = STAT_KEYS.find((k) => isNum(row[k]));
  const pKey = P_KEYS.find((k) => isNum(row[k]));
  const verdict = row.verdict || row.message || row.fit_quality || row.bias_direction;
  const rest = Object.fromEntries(Object.entries(row).filter(([k]) => ![statKey, pKey, "verdict", "message"].includes(k)));
  return <div className="rv2-test">
    <div className="rv2-test-head">
      {statKey ? <div><span>{title(statKey)}</span><strong>{fmt(row[statKey], 3)}</strong></div> : null}
      {pKey ? <div><span>{title(pKey)}</span><strong style={{ color: pColor(row[pKey]) }}>{fmt(row[pKey], 4)}</strong></div> : null}
      {verdict ? <p>{verdict}</p> : null}
    </div>
    <KeyValue value={rest} />
  </div>;
}

export function Verdict({ value }) {
  const row = rowsOf(value)[0];
  if (!row) return <Empty />;
  const color = { green: T.green, amber: T.amber, red: T.red }[row.verdict] ?? T.amber;
  return <div className="rv2-verdict" style={{ borderColor: color }}>
    <strong style={{ color }}>{String(row.verdict).toUpperCase()}</strong>
    <p>{row.message ?? ""}</p>
    <KeyValue value={Object.fromEntries(Object.entries(row).filter(([k]) => !["verdict", "message"].includes(k)))} />
  </div>;
}

export function SummaryLine({ value }) {
  const row = rowsOf(value)[0];
  if (!row) return <Empty />;
  return <div className="rv2-summary-line"><p>{row.summary}</p><KeyValue value={Object.fromEntries(Object.entries(row).filter(([k]) => k !== "summary"))} /></div>;
}

export function Explanation({ value }) {
  const row = rowsOf(value)[0];
  if (!row) return <Empty />;
  return <div className="rv2-summary-line"><p>{row.explanation}</p><KeyValue value={Object.fromEntries(Object.entries(row).filter(([k]) => k !== "explanation"))} /></div>;
}

export function RegressionTable({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  if (rows[0].available === false) return <Note text={rows[0].reason} />;
  const label = ["term", "regime", "estimator", "factor"].find((k) => k in rows[0]);
  const coef = ["lambda", "coefficient", "estimate", "iv_coefficient"].find((k) => k in rows[0]);
  const se = ["nw_se", "se", "iv_se"].find((k) => k in rows[0]);
  const t = ["t_stat", "iv_t"].find((k) => k in rows[0]);
  const p = ["p_value", "iv_p"].find((k) => k in rows[0]);
  const extra = Object.keys(rows[0]).filter((k) => ![label, coef, se, t, p, "stars"].includes(k));
  return <div className="rv2-table-wrap"><table className="rv2-table rv2-reg"><thead><tr><th>{title(label)}</th><th>Estimate</th><th>SE</th><th>t</th><th>p</th>{extra.map((k) => <th key={k}>{title(k)}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}><td className="rv2-term">{fmt(r[label])}</td><td className="rv2-strong">{fmt(r[coef])}{r.stars ? <sup>{r.stars}</sup> : null}</td><td>{fmt(r[se])}</td><td>{fmt(r[t], 2)}</td><td style={{ color: pColor(r[p]) }}>{fmt(r[p], 4)}</td>{extra.map((k) => <td key={k}>{fmt(r[k])}</td>)}</tr>)}</tbody></table></div>;
}

export function PublicationTable({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const cols = Object.keys(rows[0]).filter((k) => !["row", "kind"].includes(k));
  const firstStat = rows.findIndex((r) => r.kind === "stat");
  return <div className="rv2-journal"><table><thead><tr><th />{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i} className={`${r.kind} ${i === firstStat ? "first-stat" : ""}`}><td>{r.row}</td>{cols.map((c) => <td key={c}>{r[c]}</td>)}</tr>)}</tbody></table></div>;
}

export function ReportCard({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  return <div className="rv2-report">{rows.map((r, i) => <div key={i} className={`rv2-report-row ${r.flag}`}>
    <i>{r.flag === "red" ? "!" : "✓"}</i>
    <div><strong>{r.test}</strong><span>{r.explanation}</span>{r.flag === "red" ? <em>{r.recommendation}</em> : null}</div>
    <div className="rv2-report-stat"><b>{fmt(r.statistic, 3)}</b><small>{isNum(r.p_value_or_threshold) ? `p = ${fmt(r.p_value_or_threshold, 4)}` : r.p_value_or_threshold ?? ""}</small></div>
  </div>)}</div>;
}

export function Scorecard({ value }) {
  const rows = rowsOf(value);
  return <div className="rv2-report">{rows.map((r, i) => <div key={i} className={`rv2-report-row ${r.pass ? "green" : "red"}`}>
    <i>{r.pass ? "✓" : "✗"}</i><div><strong>{title(r.placebo)}</strong><span>{r.criterion}</span></div>
    <div className="rv2-report-stat"><b>{fmt(r.statistic, 3)}</b><small>{isNum(r.p_value) ? `p = ${fmt(r.p_value, 4)}` : ""}</small></div>
  </div>)}</div>;
}

export function RobustnessMatrix({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const maxT = Math.max(2, ...rows.map((r) => Math.abs(r.t_stat ?? 0)));
  const cols = ["coefficient", "se", "t_stat", "p_value", "r2", "months", "ls_annual_return", "ls_t_stat"];
  return <div className="rv2-table-wrap"><table className="rv2-table"><thead><tr><th>Specification</th>{cols.map((c) => <th key={c}>{title(c)}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => {
      const t = r.t_stat ?? 0;
      const bg = r.sign_flip ? "rgba(226,110,92,.18)" : Math.abs(t) >= 1.96 ? `rgba(103,182,123,${0.12 + 0.3 * Math.min(1, Math.abs(t) / maxT)})` : "transparent";
      return <tr key={i} style={{ background: bg }}><td className="rv2-term">{r.specification}</td>{cols.map((c) => <td key={c}>{fmt(r[c])}</td>)}</tr>;
    })}</tbody></table></div>;
}

export function Latex({ value }) {
  const rows = rowsOf(value).filter((r) => r.latex);
  if (!rows.length) return <Empty />;
  return <div className="rv2-code-list">{rows.map((r, i) => <CodeBlock key={i} name={r.table || `table_${i + 1}`} text={r.latex} ext="tex" />)}</div>;
}

export function Csv({ value }) {
  const rows = rowsOf(value).filter((r) => r.csv);
  return <div className="rv2-downloads">{rows.map((r) => <button type="button" key={r.name} onClick={() => downloadText(`${r.name}.csv`, r.csv, "text/csv")}><Download size={13} /> {r.name}.csv</button>)}</div>;
}

export function Pdf({ value, response }) {
  const row = rowsOf(value)[0] ?? {};
  const base64 = response?.meta?.pdf_base64;
  return <div className="rv2-downloads"><button type="button" disabled={!base64} onClick={() => downloadBase64(row.filename || "research_v2_table.pdf", base64, "application/pdf")}><Download size={13} /> {row.filename || "PDF"} {row.bytes ? `(${Math.round(row.bytes / 1024)} KB)` : ""}</button></div>;
}

function CodeBlock({ name, text, ext }) {
  const [copied, setCopied] = useState(false);
  return <div className="rv2-code"><header><span>{name}.{ext}</span><div>
    <button type="button" onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1400); }}>{copied ? <Check size={13} /> : <Copy size={13} />}</button>
    <button type="button" onClick={() => downloadText(`${name}.${ext}`, text)}><Download size={13} /></button></div></header><pre>{text}</pre></div>;
}

export function BoxSummary({ value }) {
  const r = rowsOf(value)[0];
  if (!r || !isNum(r.min)) return <Empty />;
  const lo = Math.min(r.min, 0), hi = Math.max(r.max, 0), span = hi - lo || 1;
  const pos = (v) => `${((v - lo) / span) * 100}%`;
  return <div className="rv2-box"><div className="rv2-box-track"><i className="zero" style={{ left: pos(0) }} /><b style={{ left: pos(r.q1), width: `calc(${pos(r.q3)} - ${pos(r.q1)})` }} /><em style={{ left: pos(r.median) }} /><s style={{ left: pos(r.min), width: `calc(${pos(r.max)} - ${pos(r.min)})` }} /></div>
    <KeyValue value={r} /></div>;
}

export function BarList({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  return <div className="rv2-barlist">{rows.map((r) => <div key={r.dimension}><span>{title(r.dimension)}</span><div><b style={{ width: `${Math.max(1, (r.variance_explained ?? 0) * 100)}%` }} /></div><em>{fmt((r.variance_explained ?? 0) * 100, 1)}%</em><small>{r.most_influential_choice}</small></div>)}</div>;
}

// ---------------------------------------------------------------- charts

export function LineChartR({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const x = xKey(rows);
  const keys = numericCols(rows, [x, "critical_5pct"]).slice(0, 5);
  return <Frame><LineChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey={x} {...axis} minTickGap={28} /><YAxis {...axis} width={56} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 10 }} />
    {keys.map((k, i) => <Line key={k} dataKey={k} name={title(k)} stroke={SERIES[i]} dot={false} strokeWidth={1.6} />)}</LineChart></Frame>;
}

export function CoefficientPath({ value }) {
  const rows = band(rowsOf(value));
  if (!rows.length) return <Empty />;
  return <Frame><ComposedChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} /><Tooltip contentStyle={tooltipStyle} />
    <Area dataKey="band" stroke="none" fill={T.amber} fillOpacity={0.14} name="95% band" /><Line dataKey="beta" stroke={T.amber} dot={false} strokeWidth={1.8} name="Slope" /><ReferenceLine y={0} stroke={T.muted} strokeDasharray="3 3" /></ComposedChart></Frame>;
}

export function PortfolioLadder({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  return <><Frame height={230}><BarChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="portfolio" {...axis} /><YAxis {...axis} width={56} /><Tooltip contentStyle={tooltipStyle} /><ReferenceLine y={0} stroke={T.muted} />
    <Bar dataKey="mean_return" name="Mean return" radius={[3, 3, 0, 0]}>{rows.map((r, i) => <Cell key={i} fill={r.portfolio === "long_short" ? T.amber : (r.mean_return ?? 0) >= 0 ? T.blue : T.red} />)}</Bar></BarChart></Frame><DataTable value={rows} /></>;
}

export function Heatmap({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const label = Object.keys(rows[0])[0];
  const cols = Object.keys(rows[0]).filter((k) => k !== label);
  const vals = rows.flatMap((r) => cols.map((c) => r[c])).filter(isNum);
  const max = Math.max(1e-9, ...vals.map(Math.abs));
  const color = (v) => (isNum(v) ? (v >= 0 ? `rgba(103,182,123,${0.15 + 0.7 * Math.abs(v) / max})` : `rgba(226,110,92,${0.15 + 0.7 * Math.abs(v) / max})`) : "transparent");
  return <div className="rv2-table-wrap"><table className="rv2-table rv2-heat"><thead><tr><th />{cols.map((c) => <th key={c}>{title(c)}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}><td className="rv2-term">{r[label]}</td>{cols.map((c) => <td key={c} style={{ background: color(r[c]) }}>{fmt(r[c], 4)}</td>)}</tr>)}</tbody></table></div>;
}

export function CorrelationMatrix({ value }) {
  return <Heatmap value={value} />;
}

export function SpecificationCurve({ value }) {
  const rows = band(rowsOf(value)).map((r) => ({ ...r, sig: (r.p_value ?? 1) < 0.05 }));
  if (!rows.length) return <Empty />;
  return <Frame><ComposedChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="rank" {...axis} /><YAxis {...axis} width={56} /><Tooltip contentStyle={tooltipStyle} labelFormatter={(r) => rows[r - 1]?.specification} />
    <Area dataKey="band" stroke="none" fill={T.blue} fillOpacity={0.15} name="95% CI" /><Scatter dataKey="coefficient" name="Coefficient">{rows.map((r, i) => <Cell key={i} fill={r.sig ? T.green : T.muted} />)}</Scatter><ReferenceLine y={0} stroke={T.muted} strokeDasharray="3 3" /></ComposedChart></Frame>;
}

const DEFAULTS = new Set(["full", "none", "all", "raw", "base", "nw_auto", "equal"]);
export function DecisionLedger({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const dims = Object.keys(rows[0]).filter((k) => !["rank", "specification"].includes(k));
  return <div className="rv2-ledger" style={{ gridTemplateColumns: `120px repeat(${rows.length}, minmax(6px, 1fr))` }}>
    {dims.map((d) => <div className="rv2-ledger-row" key={d} style={{ display: "contents" }}><span>{title(d)}</span>{rows.map((r, i) => <i key={i} title={`${r.specification}: ${r[d]}`} className={DEFAULTS.has(r[d]) ? "" : "on"} />)}</div>)}
  </div>;
}

function histogram(values, bins = 30) {
  const v = values.filter(isNum);
  if (!v.length) return [];
  const lo = Math.min(...v), hi = Math.max(...v), w = (hi - lo) / bins || 1;
  const out = Array.from({ length: bins }, (_, i) => ({ x: lo + (i + 0.5) * w, count: 0 }));
  v.forEach((x) => { out[Math.min(bins - 1, Math.floor((x - lo) / w))].count += 1; });
  return out;
}

function observedFor(key, response) {
  const t = response?.tables ?? {};
  const c = response?.charts ?? {};
  if (key === "permutation_null_histogram") return c.permutation_real_t?.[0]?.t_stat;
  if (key === "permutation_null") return t.curve_level_joint_p_value?.[0]?.observed;
  if (key === "did_placebo_distribution") return t.did_placebo_treatment?.[0]?.real_estimate;
  return undefined;
}

export function NullDistribution({ value, response, outputKey }) {
  const rows = rowsOf(value);
  const k = numericCols(rows)[0];
  const data = histogram(rows.map((r) => r[k]));
  const observed = observedFor(outputKey, response);
  if (!data.length) return <Empty />;
  return <Frame><BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} {...axis} tickFormatter={(v) => fmt(v, 2)} /><YAxis {...axis} width={40} /><Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => fmt(v, 3)} />
    <Bar dataKey="count" fill={T.muted} />{isNum(observed) ? <ReferenceLine x={observed} stroke={T.red} strokeWidth={2} label={{ value: `observed ${fmt(observed, 2)}`, fill: T.red, fontSize: 10, position: "top" }} /> : null}</BarChart></Frame>;
}

export function Distribution({ value }) {
  const rows = rowsOf(value);
  const k = numericCols(rows)[0];
  const data = histogram(rows.map((r) => r[k]));
  if (!data.length) return <Empty />;
  return <Frame><BarChart data={data}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="x" {...axis} tickFormatter={(v) => fmt(v, 3)} /><YAxis {...axis} width={40} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="count" fill={T.amber} /><ReferenceLine x={0} stroke={T.muted} /></BarChart></Frame>;
}

export function BarCompare({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const label = Object.keys(rows[0])[0];
  const k = numericCols(rows)[0];
  return <Frame height={220}><BarChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey={label} {...axis} /><YAxis {...axis} width={56} /><Tooltip contentStyle={tooltipStyle} /><ReferenceLine y={0} stroke={T.muted} /><Bar dataKey={k} fill={T.amber} radius={[3, 3, 0, 0]} /></BarChart></Frame>;
}

export function ForestPlot({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const label = ["column", "regime", "factor"].find((k) => k in rows[0]);
  const lo = Math.min(0, ...rows.map((r) => r.lower_95).filter(isNum)), hi = Math.max(0, ...rows.map((r) => r.upper_95).filter(isNum));
  const span = hi - lo || 1, pos = (v) => `${((v - lo) / span) * 100}%`;
  return <div className="rv2-forest">{rows.map((r, i) => <div key={i}><span>{r[label]}{r.tag === "confirmatory" ? " ●" : ""}</span>
    <div className="track"><i style={{ left: pos(0) }} /><b style={{ left: pos(r.lower_95), width: `calc(${pos(r.upper_95)} - ${pos(r.lower_95)})`, background: r.lower_95 > 0 || r.upper_95 < 0 ? T.green : T.muted }} /><em style={{ left: pos(r.coefficient) }} /></div>
    <small>{fmt(r.coefficient)} [{fmt(r.lower_95)}, {fmt(r.upper_95)}]</small></div>)}</div>;
}

export function RegimeRibbon({ value }) {
  const rows = rowsOf(value).filter((r) => r.regime);
  if (!rows.length) return <Empty />;
  const states = [...new Set(rows.map((r) => r.regime))];
  return <div className="rv2-ribbon"><div className="strip">{rows.map((r, i) => <i key={i} title={`${r.date}: ${r.regime}`} style={{ background: SERIES[states.indexOf(r.regime) % SERIES.length] }} />)}</div>
    <div className="legend">{states.map((s, i) => <span key={s}><i style={{ background: SERIES[i % SERIES.length] }} />{s}</span>)}<small>{rows[0].date} → {rows[rows.length - 1].date}</small></div></div>;
}

export function Correlogram({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const bandV = rows[0].upper_95;
  return <Frame height={240}><BarChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="lag" {...axis} /><YAxis {...axis} width={48} /><Tooltip contentStyle={tooltipStyle} />
    <ReferenceLine y={bandV} stroke={T.red} strokeDasharray="3 3" /><ReferenceLine y={-bandV} stroke={T.red} strokeDasharray="3 3" /><ReferenceLine y={0} stroke={T.muted} />
    <Bar dataKey="acf">{rows.map((r, i) => <Cell key={i} fill={r.significant ? T.red : T.blue} />)}</Bar></BarChart></Frame>;
}

export function ScatterPlot({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const [x, y] = numericCols(rows);
  return <Frame><ScatterChart margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} /><XAxis dataKey={x} name={title(x)} {...axis} tickFormatter={(v) => fmt(v, 3)} /><YAxis dataKey={y} name={title(y)} {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><ZAxis range={[10, 10]} /><Tooltip contentStyle={tooltipStyle} /><Scatter data={rows} fill={T.blue} fillOpacity={0.5} /></ScatterChart></Frame>;
}

export function BreakScan({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty text="Too few observations for a break scan." />;
  const crit = rows[0].critical_5pct;
  return <Frame><LineChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={48} /><Tooltip contentStyle={tooltipStyle} /><Line dataKey="f_stat" stroke={T.amber} dot={false} name="Chow F" />
    {isNum(crit) ? <ReferenceLine y={crit} stroke={T.red} strokeDasharray="4 4" label={{ value: "5% critical (sup-F)", fill: T.red, fontSize: 10, position: "insideTopRight" }} /> : null}</LineChart></Frame>;
}

export function PartialResiduals({ value }) {
  const rows = rowsOf(value);
  const groups = useMemo(() => rows.reduce((acc, r) => ({ ...acc, [r.regressor]: [...(acc[r.regressor] ?? []), r] }), {}), [rows]);
  if (!rows.length) return <Empty />;
  return <div className="rv2-multiples">{Object.entries(groups).map(([name, g]) => <div key={name}><span>{title(name)}</span><Frame height={170}><ComposedChart data={g}><CartesianGrid stroke={T.grid} /><XAxis dataKey="x" type="number" {...axis} tickFormatter={(v) => fmt(v, 2)} /><YAxis {...axis} width={48} tickFormatter={(v) => fmt(v, 3)} /><Scatter dataKey="component_plus_residual" fill={T.blue} /><Line dataKey="linear_fit" stroke={T.amber} dot={false} /></ComposedChart></Frame></div>)}</div>;
}

export function QQPlot({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const lim = Math.max(...rows.map((r) => Math.max(Math.abs(r.theoretical), Math.abs(r.sample))));
  return <Frame><ScatterChart><CartesianGrid stroke={T.grid} /><XAxis dataKey="theoretical" type="number" domain={[-lim, lim]} {...axis} tickFormatter={(v) => fmt(v, 1)} /><YAxis dataKey="sample" type="number" domain={[-lim, lim]} {...axis} width={40} tickFormatter={(v) => fmt(v, 1)} /><ReferenceLine segment={[{ x: -lim, y: -lim }, { x: lim, y: lim }]} stroke={T.muted} strokeDasharray="3 3" /><Scatter data={rows} fill={T.amber} /></ScatterChart></Frame>;
}

export function EventStudy({ value }) {
  const rows = band(rowsOf(value));
  if (!rows.length) return <Empty />;
  const x = ["event_time", "event_day"].find((k) => k in rows[0]) ?? xKey(rows);
  const y = ["estimate", "mean_car", "pooled_effect"].find((k) => k in rows[0]) ?? numericCols(rows, [x])[0];
  return <Frame><ComposedChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey={x} {...axis} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} />
    <Area dataKey="band" stroke="none" fill={T.amber} fillOpacity={0.15} name="95% CI" /><Line dataKey={y} stroke={T.amber} strokeWidth={1.8} dot={{ r: 2 }} name={title(y)} /><ReferenceLine y={0} stroke={T.muted} /><ReferenceLine x={0} stroke={T.red} strokeDasharray="3 3" /></ComposedChart></Frame>;
}

export function BaconScatter({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const types = [...new Set(rows.map((r) => r.comparison))];
  const twfe = rows[0].twfe_implied;
  return <Frame><ScatterChart margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} /><XAxis dataKey="weight" name="Weight" {...axis} tickFormatter={(v) => fmt(v, 2)} /><YAxis dataKey="estimate" name="2x2 DiD" {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 10 }} />
    {isNum(twfe) ? <ReferenceLine y={twfe} stroke={T.amber} strokeDasharray="4 4" label={{ value: "TWFE", fill: T.amber, fontSize: 10 }} /> : null}
    {types.map((t, i) => <Scatter key={t} name={t} data={rows.filter((r) => r.comparison === t)} fill={SERIES[i + 1]} />)}</ScatterChart></Frame>;
}

export function RdPlot({ value, response }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const cutoff = response?.tables?.rd_estimate?.[0]?.cutoff;
  const left = rows.filter((r) => r.side === "left"), right = rows.filter((r) => r.side === "right");
  return <Frame><ComposedChart margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} /><XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} {...axis} tickFormatter={(v) => fmt(v, 1)} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} />
    <Scatter data={left} dataKey="y" fill={T.blue} /><Scatter data={right} dataKey="y" fill={T.green} /><Line data={left} dataKey="fit" stroke={T.blue} dot={false} /><Line data={right} dataKey="fit" stroke={T.green} dot={false} />
    {isNum(cutoff) ? <ReferenceLine x={cutoff} stroke={T.red} strokeDasharray="4 4" /> : null}</ComposedChart></Frame>;
}

export function Density({ value, response }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const cutoff = response?.tables?.rd_estimate?.[0]?.cutoff;
  return <Frame height={230}><BarChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="x" {...axis} tickFormatter={(v) => fmt(v, 1)} /><YAxis {...axis} width={40} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="count">{rows.map((r, i) => <Cell key={i} fill={r.side === "left" ? T.blue : T.green} />)}</Bar>{isNum(cutoff) ? <ReferenceLine x={cutoff} stroke={T.red} /> : null}</BarChart></Frame>;
}

export function PlaceboCutoffs({ value }) {
  const rows = rowsOf(value).map((r) => ({ ...r, band: isNum(r.ci_robust_low) ? [r.ci_robust_low, r.ci_robust_high] : null }));
  if (!rows.length) return <Empty />;
  const x = "bandwidth_multiple" in rows[0] ? "bandwidth_multiple" : "cutoff";
  const sorted = [...rows].sort((a, b) => a[x] - b[x]);
  return <Frame><ComposedChart data={sorted}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey={x} {...axis} tickFormatter={(v) => fmt(v, 2)} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} /><ReferenceLine y={0} stroke={T.muted} />
    <Area dataKey="band" stroke="none" fill={T.blue} fillOpacity={0.15} name="Robust 95% CI" /><Scatter dataKey="estimate_bias_corrected" name="Estimate">{sorted.map((r, i) => <Cell key={i} fill={r.real_cutoff || r.bandwidth_multiple === 1 ? T.red : T.amber} />)}</Scatter></ComposedChart></Frame>;
}

export function VitalityGauge({ value }) {
  const r = rowsOf(value)[0];
  if (!r || !isNum(r.vitality_score)) return <Empty />;
  const v = r.vitality_score, shown = Math.max(0, Math.min(100, v));
  const color = v < 0 ? "#9b2c22" : v < 30 ? T.red : v < 70 ? T.amber : T.green;
  return <div className="rv2-gauge"><svg viewBox="0 0 200 118"><path d="M20 104 A80 80 0 0 1 180 104" fill="none" stroke={T.border} strokeWidth="14" strokeLinecap="round" /><path d="M20 104 A80 80 0 0 1 180 104" fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" pathLength="100" strokeDasharray="100" strokeDashoffset={100 - shown} /></svg>
    <strong style={{ color }}>{fmt(v, 0)}</strong><span>{r.zone}</span><small>Recent {r.recent_window_months}m performance as % of in-sample ({fmt(r.in_sample_mean)})</small></div>;
}

export function DecayCurve({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const fits = Object.keys(rows[0]).filter((k) => k.endsWith("_fit"));
  const floor = rows[0].floor;
  return <Frame><LineChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 10 }} />
    <Line dataKey="rolling_metric" stroke={T.text} dot={false} name="Rolling metric" />{fits.map((k, i) => <Line key={k} dataKey={k} stroke={SERIES[i]} dot={false} strokeDasharray="5 3" name={title(k)} />)}{isNum(floor) ? <ReferenceLine y={floor} stroke={T.muted} strokeDasharray="2 4" label={{ value: "floor", fill: T.muted, fontSize: 10 }} /> : null}<ReferenceLine y={0} stroke={T.muted} /></LineChart></Frame>;
}

export function SyntheticPath({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const start = rows.find((r) => r.post)?.date;
  return <Frame><LineChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 2)} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 10 }} />
    {start ? <ReferenceArea x1={start} x2={rows[rows.length - 1].date} fill={T.amber} fillOpacity={0.06} /> : null}<Line dataKey="treated" stroke={T.amber} dot={false} strokeWidth={2} name="Treated" /><Line dataKey="synthetic" stroke={T.blue} dot={false} strokeDasharray="5 3" name="Synthetic" /></LineChart></Frame>;
}

export function GapPlot({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  const start = rows.find((r) => r.post)?.date;
  return <Frame height={240}><LineChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 2)} /><Tooltip contentStyle={tooltipStyle} /><ReferenceLine y={0} stroke={T.muted} />{start ? <ReferenceLine x={start} stroke={T.red} strokeDasharray="4 4" /> : null}<Line dataKey="gap" stroke={T.amber} dot={false} /></LineChart></Frame>;
}

export function PlaceboPaths({ value, response }) {
  const rows = rowsOf(value);
  const treated = rowsOf(response?.charts?.gap_plot);
  const data = useMemo(() => {
    const byDate = new Map(treated.map((r) => [r.date, { date: r.date, treated: r.gap }]));
    rows.forEach((r) => { const d = byDate.get(r.date) ?? { date: r.date }; d[r.unit] = r.gap; byDate.set(r.date, d); });
    return [...byDate.values()];
  }, [rows, treated]);
  const units = [...new Set(rows.map((r) => r.unit))].slice(0, 60);
  if (!rows.length) return <Empty />;
  return <Frame><LineChart data={data}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 2)} />
    {units.map((u) => <Line key={u} dataKey={u} stroke={T.muted} strokeOpacity={0.35} dot={false} isAnimationActive={false} />)}<Line dataKey="treated" stroke={T.red} strokeWidth={2.2} dot={false} /></LineChart></Frame>;
}

export function PlaceboRanking({ value }) {
  const rows = rowsOf(value);
  if (!rows.length) return <Empty />;
  return <Frame><BarChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="unit" {...axis} hide /><YAxis {...axis} width={48} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="post_pre_ratio" name="Post/pre RMSPE">{rows.map((r, i) => <Cell key={i} fill={r.treated ? T.red : T.muted} />)}</Bar></BarChart></Frame>;
}

export function ConformalBand({ value }) {
  const rows = band(rowsOf(value), "lower", "upper");
  if (!rows.length) return <Empty />;
  return <Frame><ComposedChart data={rows}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="date" {...axis} minTickGap={28} /><YAxis {...axis} width={56} tickFormatter={(v) => fmt(v, 3)} /><Tooltip contentStyle={tooltipStyle} /><Area dataKey="band" stroke="none" fill={T.violet} fillOpacity={0.2} name={`${Math.round((rows[0].coverage ?? 0.9) * 100)}% conformal`} /><Line dataKey="effect" stroke={T.violet} dot={{ r: 2 }} name="Monthly effect" /><ReferenceLine y={0} stroke={T.muted} /></ComposedChart></Frame>;
}

export function ZooScatter({ value }) {
  const rows = rowsOf(value).filter((r) => isNum(r.ic_ir) || isNum(r.sharpe));
  if (!rows.length) return <Empty />;
  const pts = rows.map((r) => ({ ...r, ic_ir: r.ic_ir ?? 0, sharpe: r.sharpe ?? 0 }));
  return <Frame><ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 0 }}><CartesianGrid stroke={T.grid} /><XAxis dataKey="ic_ir" name="IC-IR" {...axis} tickFormatter={(v) => fmt(v, 2)} /><YAxis dataKey="sharpe" name="L/S Sharpe" {...axis} width={48} tickFormatter={(v) => fmt(v, 2)} /><ZAxis range={[70, 70]} /><Tooltip contentStyle={tooltipStyle} formatter={(v) => fmt(v, 3)} labelFormatter={() => ""} /><ReferenceLine x={0} stroke={T.muted} /><ReferenceLine y={0} stroke={T.muted} />
    <Scatter data={pts} label={{ dataKey: "factor", fill: T.secondary, fontSize: 9, position: "top" }}>{pts.map((r, i) => <Cell key={i} fill={r.candidate ? T.amber : T.blue} />)}</Scatter></ScatterChart></Frame>;
}

// ---------------------------------------------------------------- dispatch

function Empty({ text = "No rows for this configuration." }) { return <div className="rv2-empty">{text}</div>; }
function Note({ text }) { return <div className="rv2-empty">{text}</div>; }

export const RENDERERS = {
  dataTable: DataTable, keyValue: KeyValue, testCard: TestCard, verdict: Verdict, summaryLine: SummaryLine, explanation: Explanation,
  regressionTable: RegressionTable, publicationTable: PublicationTable, reportCard: ReportCard, scorecard: Scorecard, robustnessMatrix: RobustnessMatrix,
  latex: Latex, csv: Csv, pdf: Pdf, boxSummary: BoxSummary, barList: BarList, lineChart: LineChartR, coefficientPath: CoefficientPath,
  portfolioLadder: PortfolioLadder, heatmap: Heatmap, correlationMatrix: CorrelationMatrix, specificationCurve: SpecificationCurve,
  decisionLedger: DecisionLedger, nullDistribution: NullDistribution, distribution: Distribution, barCompare: BarCompare, forestPlot: ForestPlot,
  regimeRibbon: RegimeRibbon, correlogram: Correlogram, scatter: ScatterPlot, breakScan: BreakScan, partialResiduals: PartialResiduals,
  qqPlot: QQPlot, eventStudy: EventStudy, baconScatter: BaconScatter, rdPlot: RdPlot, density: Density, placeboCutoffs: PlaceboCutoffs,
  vitalityGauge: VitalityGauge, decayCurve: DecayCurve, syntheticPath: SyntheticPath, gapPlot: GapPlot, placeboPaths: PlaceboPaths,
  placeboRanking: PlaceboRanking, conformalBand: ConformalBand, zooScatter: ZooScatter,
};

export function RenderOutput({ output, response }) {
  const value = response?.[output.source]?.[output.key];
  const Component = RENDERERS[output.render] ?? DataTable;
  if (value === undefined || value === null || (Array.isArray(value) && !value.length)) return <Empty text="Not produced for this configuration." />;
  return <Component value={value} response={response} outputKey={output.key} />;
}
