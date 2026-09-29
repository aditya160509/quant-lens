"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useDeferredValue, useMemo, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Columns3,
  Database,
  Download,
  FileJson,
  FolderOpen,
  ListFilter,
  Play,
  Search,
  SlidersHorizontal,
  Table2,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getResearchV2Feature, RESEARCH_V2_FEATURES } from "./registry";

const T = {
  page: "#080907", panel: "#0e100d", panelRaised: "#151812", screen: "#070806",
  border: "#2a2d25", borderSubtle: "#1c1f1a", grid: "#252820", amber: "#e6ad36",
  amberSoft: "rgba(230,173,54,.12)", text: "#f1efe7", secondary: "#aaa99f", muted: "#706f66",
  green: "#67b67b", red: "#e26e5c", blue: "#70a5d7", violet: "#a68ad2",
};
const SERIES = [T.amber, T.blue, T.green, T.violet, T.red];
const RESEARCH_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO", "BTC_USD", "ETH_USD"];

const axis = { tick: { fill: T.muted, fontSize: 10, fontFamily: "var(--font-ibm-plex-mono), monospace" }, axisLine: false, tickLine: false };
const tooltipStyle = { background: "#151812", border: `1px solid ${T.border}`, borderRadius: 7, color: T.text, fontSize: 11 };

const number = (value) => {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const title = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function rowsFrom(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "object") {
    if (Array.isArray(value.rows)) return value.rows;
    if (Array.isArray(value.data)) return value.data;
    const scalar = Object.entries(value).every(([, item]) => typeof item !== "object" || item === null);
    if (scalar) return Object.entries(value).map(([label, item]) => ({ label, value: item }));
  }
  return [];
}

function lookup(response, section) {
  if (!response) return null;
  return response?.[section.source]?.[section.dataKey] ?? null;
}

function chartData(value) {
  const rows = rowsFrom(value);
  if (!rows.length) return [];
  return rows.map((row, index) => {
    const out = { ...row, __x: row.date ?? row.month ?? row.period ?? row.time ?? row.t ?? row.name ?? row.label ?? `#${index + 1}` };
    for (const [key, item] of Object.entries(row)) {
      const parsed = number(item);
      if (parsed !== null) out[key] = parsed;
    }
    return out;
  });
}

function numericKeys(rows) {
  const keys = new Set();
  rows.forEach((row) => Object.entries(row).forEach(([key, value]) => {
    if (key !== "__x" && number(value) !== null) keys.add(key);
  }));
  return [...keys];
}

function buildPayload(form) {
  return Object.fromEntries(Object.entries(form).map(([key, value]) => {
    if (typeof value !== "string") return [key, value];
    if (/^(max_symbols|lookback_days|nw_lag|forward_months|sort_portfolios|rolling_window|bootstrap_replications|permutation_replications|max_specifications|donor_limit|significance_threshold)$/.test(key)) {
      const parsed = Number(value);
      return [key, Number.isFinite(parsed) ? parsed : value];
    }
    return [key, value];
  }));
}

function defaultForm(feature) {
  return Object.fromEntries(feature.fields.map((field) => [field.key, field.default ?? ""]));
}

function SymbolInput({ value, onChange, label, single = false }) {
  const [query, setQuery] = useState("");
  const selected = String(value || "").split(",").map((item) => item.trim()).filter(Boolean).filter((item) => item !== "master" && item !== "ff5_mom");
  const matches = useMemo(() => RESEARCH_TICKERS.filter((ticker) => ticker.includes(query.toUpperCase()) && !selected.includes(ticker)).slice(0, 7), [query, selected]);
  const add = (ticker) => {
    onChange(single ? ticker : [...selected, ticker].join(","));
    setQuery("");
  };
  const remove = (ticker) => onChange(selected.filter((item) => item !== ticker).join(","));
  return (
    <div className="rv2-symbol-shell">
      <div className="rv2-symbol-box">
        <span className="rv2-symbol-prefix">{single ? "TICKER" : "UNIVERSE"}</span>
        <div className="rv2-symbol-tokens">
          {selected.map((ticker) => <button type="button" key={ticker} onClick={() => remove(ticker)}>{ticker}<X size={11} /></button>)}
          <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && query.trim()) { event.preventDefault(); add(query.trim().toUpperCase()); }
          }} placeholder={selected.length ? "Add symbol" : `Search ${label.toLowerCase()}`} />
        </div>
      </div>
      {query && matches.length > 0 ? <div className="rv2-symbol-menu">{matches.map((ticker) => <button type="button" key={ticker} onClick={() => add(ticker)}><strong>{ticker}</strong><span>{ticker.includes("_") ? "digital asset" : "listed security"}</span><b>ADD</b></button>)}</div> : null}
      {!selected.length && (value === "master" || value === "ff5_mom") ? <small>{value === "master" ? "Master universe, server-resolved." : "Fama-French 5 plus momentum benchmark."}</small> : null}
    </div>
  );
}

function Field({ field, value, onChange }) {
  const multi = field.type === "ticker_list";
  if (multi || field.type === "ticker") return <label className="rv2-field"><span>{field.label}</span><SymbolInput value={value} onChange={onChange} label={field.label} single={field.type === "ticker"} /></label>;
  if (field.type === "select") return <label className="rv2-field"><span>{field.label}</span><div className="rv2-chip-row">{field.options.map((option) => <button type="button" className={String(option) === String(value) ? "active" : ""} onClick={() => onChange(option)} key={String(option)}>{String(option).replaceAll("_", " ")}</button>)}</div></label>;
  if (field.type === "json") return <label className="rv2-field rv2-field-wide"><span>{field.label}</span><textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder='{"column":"definition"}' spellCheck="false" /></label>;
  if (field.type === "date") return <label className="rv2-field"><span>{field.label}</span><input type="date" value={value || ""} onChange={(event) => onChange(event.target.value)} /></label>;
  if (field.type === "file_path") return <label className="rv2-field rv2-file-field"><span>{field.label}</span><div><FolderOpen size={15} /><input value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder="Optional server-side path" /></div><small>Optional. A blank value keeps the data-loader default.</small></label>;
  return <label className="rv2-field"><span>{field.label}<b>{value}</b></span><input type="number" value={value ?? ""} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ConfigCurtain({ open, onClose, feature, form, setForm, onRun }) {
  const groups = useMemo(() => feature.fields.reduce((acc, field) => ({ ...acc, [field.group]: [...(acc[field.group] || []), field] }), {}), [feature.fields]);
  return <AnimatePresence>{open ? <motion.div className="rv2-curtain" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
    <motion.section initial={{ y: -28, opacity: 0.6 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }} transition={{ type: "spring", stiffness: 280, damping: 28 }} onMouseDown={(event) => event.stopPropagation()}>
      <header><div><p>Research V2 / F{feature.id}</p><h2>Study configuration</h2></div><button type="button" onClick={onClose} aria-label="Close input form"><X size={18} /></button></header>
      <div className="rv2-form">{Object.entries(groups).map(([group, fields]) => <div className="rv2-form-group" key={group}><h3>{group}</h3><div>{fields.map((field) => <Field key={field.key} field={field} value={form[field.key]} onChange={(value) => setForm((current) => ({ ...current, [field.key]: value }))} />)}</div></div>)}</div>
      <footer><span>Inputs mirror the Research V2 backend contract.</span><div><button type="button" onClick={() => setForm(defaultForm(feature))}>Restore defaults</button><button type="button" className="run" onClick={() => { onRun(buildPayload(form)); onClose(); }}><Play size={14} /> Run study</button></div></footer>
    </motion.section>
  </motion.div> : null}</AnimatePresence>;
}

function Heatmap({ value }) {
  const rows = rowsFrom(value);
  const normalized = rows.flatMap((row, index) => {
    if (row.row !== undefined && row.col !== undefined) return [{ row: row.row, col: row.col, value: number(row.value) ?? 0 }];
    return Object.entries(row).filter(([key, item]) => key !== "row" && number(item) !== null).map(([key, item]) => ({ row: row.row ?? row.name ?? `R${index + 1}`, col: key, value: number(item) }));
  });
  const rowNames = [...new Set(normalized.map((cell) => String(cell.row)))]; const colNames = [...new Set(normalized.map((cell) => String(cell.col)))];
  const max = Math.max(0.001, ...normalized.map((cell) => Math.abs(cell.value)));
  return <div className="rv2-heatmap-wrap"><div className="rv2-heatmap" style={{ gridTemplateColumns: `96px repeat(${Math.max(1, colNames.length)}, minmax(52px, 1fr))` }}><i /><>{colNames.map((col) => <b key={col}>{col}</b>)}</>{rowNames.map((row) => <><strong key={`${row}:label`}>{row}</strong>{colNames.map((col) => { const cell = normalized.find((item) => String(item.row) === row && String(item.col) === col); const item = cell?.value ?? 0; const alpha = 0.12 + Math.min(0.8, Math.abs(item) / max * 0.76); const color = item < 0 ? `rgba(112,165,215,${alpha})` : `rgba(230,173,54,${alpha})`; return <span key={`${row}:${col}`} title={`${row} / ${col}: ${item.toFixed(4)}`} style={{ background: color }}>{item.toFixed(2)}</span>; })}</>)}</div></div>;
}

function GenericChart({ value, type }) {
  const specialized = ResearchVisual({ value, type });
  if (specialized) return specialized;
  const data = chartData(value); const keys = numericKeys(data).slice(0, 4);
  if (type === "metrics") return <MetricDeck value={value} />;
  if (type === "heatmap") return <Heatmap value={value} />;
  if (!data.length || !keys.length) return <CompactTable value={value} />;
  if (type === "waterfall") return <ResponsiveContainer width="100%" height={310}><BarChart data={data}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="__x" {...axis} /><YAxis {...axis} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey={keys[0]} radius={[3, 3, 0, 0]}>{data.map((row, index) => <Cell key={index} fill={row[keys[0]] >= 0 ? T.green : T.red} />)}</Bar></BarChart></ResponsiveContainer>;
  if (type === "table") return <CompactTable value={value} />;
  const Component = type === "line" ? LineChart : AreaChart;
  return <ResponsiveContainer width="100%" height={310}><Component data={data} margin={{ top: 12, right: 12, left: -12, bottom: 0 }}><defs>{keys.map((key, index) => <linearGradient key={key} id={`rv2-${key}`} x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={SERIES[index]} stopOpacity={0.26} /><stop offset="96%" stopColor={SERIES[index]} stopOpacity={0} /></linearGradient>)}</defs><CartesianGrid stroke={T.grid} strokeDasharray="2 4" vertical={false} /><XAxis dataKey="__x" {...axis} minTickGap={32} /><YAxis {...axis} /><Tooltip contentStyle={tooltipStyle} />{keys.map((key, index) => type === "line" ? <Line key={key} type="monotone" dataKey={key} stroke={SERIES[index]} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: T.screen, stroke: SERIES[index], strokeWidth: 2 }} /> : <Area key={key} type="monotone" dataKey={key} stroke={SERIES[index]} strokeWidth={2} fill={`url(#rv2-${key})`} />)}</Component></ResponsiveContainer>;
}

function CompactTable({ value }) {
  const rows = rowsFrom(value); const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))].slice(0, 8);
  if (!rows.length) return <div className="rv2-no-data">The backend returned this key without a tabular payload.</div>;
  return <div className="rv2-table-wrap"><table className="rv2-table"><thead><tr>{columns.map((column) => <th key={column}>{title(column)}</th>)}</tr></thead><tbody>{rows.slice(0, 50).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{typeof row[column] === "object" ? JSON.stringify(row[column]) : String(row[column] ?? "-")}</td>)}</tr>)}</tbody></table></div>;
}

function MetricDeck({ value }) {
  const rows = rowsFrom(value); return <div className="rv2-metrics">{rows.slice(0, 6).map((row, index) => { const label = row.label ?? row.name ?? Object.keys(row)[0] ?? `Metric ${index + 1}`; const raw = row.value ?? row.score ?? row[Object.keys(row).find((key) => number(row[key]) !== null)] ?? "-"; return <div key={index}><span>{title(label)}</span><strong>{number(raw) !== null ? Number(raw).toFixed(3) : String(raw)}</strong><small>Research output</small></div>; })}</div>;
}

function firstNumeric(row) {
  if (!row) return null;
  const preferred = ["estimate", "coefficient", "beta", "effect", "value", "statistic", "t_stat", "score", "p_value"];
  for (const key of preferred) { const parsed = number(row[key]); if (parsed !== null) return { key, value: parsed }; }
  for (const [key, item] of Object.entries(row)) { const parsed = number(item); if (parsed !== null) return { key, value: parsed }; }
  return null;
}

function RegressionTable({ value, forest = false }) {
  const rows = rowsFrom(value).slice(0, 20);
  if (!rows.length) return <CompactTable value={value} />;
  const normalized = rows.map((row, index) => {
    const estimate = firstNumeric(row); const stderr = number(row.std_error ?? row.se ?? row.stderr); const label = row.term ?? row.factor ?? row.variable ?? row.name ?? row.label ?? `Term ${index + 1}`;
    return { row, label, estimate: estimate?.value ?? 0, stderr: stderr ?? Math.abs(estimate?.value ?? 0) * 0.22 };
  });
  if (!forest) return <div className="rv2-regression"><div className="rv2-regression-head"><span>TERM</span><span>ESTIMATE</span><span>T / Z</span><span>P-VALUE</span><span>INTERPRETATION</span></div>{normalized.map((item) => { const tStat = number(item.row.t_stat ?? item.row.t ?? item.row.z_score); const p = number(item.row.p_value ?? item.row.p); return <div className="rv2-regression-row" key={item.label}><strong>{title(item.label)}</strong><b className={item.estimate >= 0 ? "pos" : "neg"}>{item.estimate.toFixed(4)}</b><span>{tStat === null ? "-" : tStat.toFixed(2)}</span><span>{p === null ? "-" : p.toFixed(3)}</span><em>{p !== null && p < .05 ? "statistically reliable" : "review uncertainty"}</em></div>; })}</div>;
  const max = Math.max(.00001, ...normalized.map((item) => Math.abs(item.estimate) + 1.96 * item.stderr));
  return <div className="rv2-forest">{normalized.map((item) => { const left = 50 + item.estimate / max * 44; const width = Math.max(2, item.stderr * 1.96 / max * 88); return <div className="rv2-forest-row" key={item.label}><span>{title(item.label)}</span><div><i className="zero" /><b style={{ left: `${left - width / 2}%`, width: `${width}%` }} /><em className={item.estimate >= 0 ? "pos" : "neg"} style={{ left: `${left}%` }} /></div><strong>{item.estimate.toFixed(3)}</strong></div>; })}</div>;
}

function DecisionLedger({ value }) {
  const rows = rowsFrom(value); if (!rows.length) return <CompactTable value={value} />;
  return <div className="rv2-ledger">{rows.slice(0, 18).map((row, index) => { const entries = Object.entries(row).filter(([, item]) => item !== null && item !== undefined).slice(0, 4); return <div key={index}><i>{String(index + 1).padStart(2, "0")}</i>{entries.map(([key, item]) => <span key={key}><small>{title(key)}</small><b>{String(item)}</b></span>)}</div>; })}</div>;
}

function SpecificationCurve({ value }) {
  const data = chartData(value); const key = numericKeys(data).find((item) => /coefficient|estimate|beta|value/.test(item)) ?? numericKeys(data)[0];
  if (!data.length || !key) return <CompactTable value={value} />;
  return <div className="rv2-spec-curve"><div className="rv2-spec-summary"><span>SPECIFICATION PATH</span><b>{data.length} choices tested</b><em>Each bar is one admissible research decision.</em></div><ResponsiveContainer width="100%" height={280}><BarChart data={data}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey="__x" {...axis} hide /><YAxis {...axis} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey={key} radius={[2, 2, 0, 0]}>{data.map((row, index) => <Cell key={index} fill={row[key] >= 0 ? T.amber : T.blue} />)}</Bar></BarChart></ResponsiveContainer></div>;
}

function Distribution({ value, qq = false }) {
  const data = chartData(value); const keys = numericKeys(data); const y = keys.find((key) => /count|density|frequency|observed|sample/.test(key)) ?? keys[0]; const x = keys.find((key) => /quantile|theoretical|x|value|bin/.test(key)) ?? "__x";
  if (!data.length || !y) return <CompactTable value={value} />;
  if (qq) return <div className="rv2-qq"><div className="rv2-qq-square"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><line x1="8" y1="92" x2="92" y2="8" stroke={T.muted} strokeDasharray="3 3" />{data.slice(0, 90).map((row, index) => { const a = number(row[x]) ?? index; const b = number(row[y]) ?? index; const min = -3; const max = 3; const cx = 8 + Math.max(0, Math.min(84, (a - min) / (max - min) * 84)); const cy = 92 - Math.max(0, Math.min(84, (b - min) / (max - min) * 84)); return <circle key={index} cx={cx} cy={cy} r="1.1" fill={T.amber} />; })}</svg></div><div><b>Normal Q-Q adequacy</b><span>Points should track the diagonal. Tail displacement signals density misspecification.</span></div></div>;
  return <ResponsiveContainer width="100%" height={290}><BarChart data={data}><CartesianGrid stroke={T.grid} vertical={false} /><XAxis dataKey={x} {...axis} /><YAxis {...axis} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey={y} fill={T.amber} radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer>;
}

function RegimeRibbon({ value }) {
  const data = chartData(value); const keys = numericKeys(data).filter((key) => !/index|state|date|time/.test(key)).slice(0, 5);
  if (!data.length || !keys.length) return <CompactTable value={value} />;
  return <div className="rv2-regime"><div className="rv2-regime-legend">{keys.map((key, index) => <span key={key}><i style={{ background: SERIES[index] }} />{title(key)}</span>)}</div><div className="rv2-regime-ribbon">{data.map((row, index) => { const total = keys.reduce((sum, key) => sum + Math.max(0, row[key] ?? 0), 0) || 1; return <div key={index} title={String(row.__x)}>{keys.map((key, keyIndex) => <i key={key} style={{ width: `${Math.max(2, Math.max(0, row[key] ?? 0) / total * 100)}%`, background: SERIES[keyIndex] }} />)}</div>; })}</div><div className="rv2-regime-axis"><span>{data[0]?.__x}</span><span>{data.at(-1)?.__x}</span></div></div>;
}

function EventStudy({ value, synthetic = false, gap = false }) {
  const data = chartData(value); const keys = numericKeys(data).slice(0, 3); if (!data.length || !keys.length) return <CompactTable value={value} />;
  return <div className="rv2-event"><div className="rv2-event-strip"><span>{synthetic ? "TREATED VS SYNTHETIC" : gap ? "POST-TREATMENT GAP" : "EVENT WINDOW"}</span><b>t = 0</b><em>Event anchor marked in amber</em></div><ResponsiveContainer width="100%" height={310}><LineChart data={data}><CartesianGrid stroke={T.grid} strokeDasharray="2 4" vertical={false} /><XAxis dataKey="__x" {...axis} minTickGap={26} /><YAxis {...axis} /><Tooltip contentStyle={tooltipStyle} />{keys.map((key, index) => <Line key={key} type="monotone" dataKey={key} stroke={index === 0 ? T.amber : SERIES[index]} strokeWidth={index === 0 ? 2.5 : 1.7} dot={false} />)}</LineChart></ResponsiveContainer></div>;
}

function VitalityGauge({ value }) {
  const row = rowsFrom(value)[0] ?? {}; const metric = firstNumeric(row); const score = Math.max(0, Math.min(100, (metric?.value ?? 0) <= 1 ? (metric?.value ?? 0) * 100 : metric?.value ?? 0));
  const r = 74; const circumference = Math.PI * r; const offset = circumference - score / 100 * circumference;
  return <div className="rv2-vitality"><svg viewBox="0 0 200 122"><path d="M26 104 A74 74 0 0 1 174 104" fill="none" stroke={T.border} strokeWidth="13" strokeLinecap="round" /><path d="M26 104 A74 74 0 0 1 174 104" fill="none" stroke={score > 66 ? T.green : score > 35 ? T.amber : T.red} strokeWidth="13" strokeLinecap="round" pathLength="100" strokeDasharray="100" strokeDashoffset={100 - score} /><text x="100" y="92" textAnchor="middle" fill={T.text} fontSize="32" fontWeight="800">{score.toFixed(0)}</text></svg><strong>{title(row.label ?? row.name ?? "Signal vitality")}</strong><span>{score > 66 ? "SURVIVING" : score > 35 ? "DECAYING" : "WEAK"}</span></div>;
}

function ResearchVisual({ value, type }) {
  if (type === "regressionTable") return <RegressionTable value={value} />;
  if (type === "forestPlot") return <RegressionTable value={value} forest />;
  if (type === "specificationCurve" || type === "thresholdCurve" || type === "coefficientPath") return <SpecificationCurve value={value} />;
  if (type === "decisionLedger" || type === "publicationTable" || type === "comparisonTable" || type === "donorWeights" || type === "sensitivityTable") return type === "publicationTable" ? <CompactTable value={value} /> : <DecisionLedger value={value} />;
  if (type === "nullDistribution" || type === "distribution") return <Distribution value={value} />;
  if (type === "qqPlot") return <Distribution value={value} qq />;
  if (type === "regimeRibbon") return <RegimeRibbon value={value} />;
  if (type === "eventStudy") return <EventStudy value={value} />;
  if (type === "syntheticPath") return <EventStudy value={value} synthetic />;
  if (type === "gapPlot") return <EventStudy value={value} gap />;
  if (type === "vitalityGauge") return <VitalityGauge value={value} />;
  if (type === "testCard" || type === "verdict") return <MetricDeck value={value} />;
  if (type === "portfolioLadder" || type === "placeboRanking" || type === "regimeBars" || type === "rddPlot" || type === "scatterDiagnostic" || type === "breakScan" || type === "correlogram" || type === "treatmentTimeline" || type === "zooMap") return <GenericChart value={value} type="line" />;
  return null;
}

function PdfReport({ value, response }) {
  const descriptor = rowsFrom(value)[0] ?? {};
  const base64 = response?.meta?.pdf_base64;
  const download = () => {
    if (!base64 || typeof window === "undefined") return;
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = descriptor.filename || "atlas_research_v2_publication_table.pdf"; anchor.click(); URL.revokeObjectURL(url);
  };
  return <div className="rv2-pdf-report">
    <div className="rv2-pdf-sheet"><p>ATLAS RESEARCH V2</p><h4>Publication Table</h4><i /><span>{descriptor.filename || "atlas_research_v2_publication_table.pdf"}</span><small>{descriptor.bytes ? `${Number(descriptor.bytes).toLocaleString()} bytes` : "PDF report descriptor"}</small></div>
    <div className="rv2-pdf-copy"><strong>{descriptor.status === "rendered" ? "PDF ready" : "PDF pending"}</strong><span>{descriptor.status === "rendered" ? "Rendered in memory by the Research V2 service." : descriptor.reason || "Run Feature 06 to produce the report."}</span><button type="button" onClick={download} disabled={!base64}><Download size={14} /> Download PDF</button></div>
    <style jsx>{`
      .rv2-pdf-report{min-height:250px;display:grid;grid-template-columns:210px minmax(0,1fr);align-items:center;gap:28px;padding:18px}.rv2-pdf-sheet{min-height:212px;padding:22px 18px;border:1px solid #d8d4c7;border-radius:3px;background:#f7f5ee;color:#252520;box-shadow:8px 12px 0 rgba(0,0,0,.24);display:flex;flex-direction:column}.rv2-pdf-sheet p{margin:0;color:#9a7628;font:900 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.14em}.rv2-pdf-sheet h4{margin:28px 0 10px;font-family:Georgia,serif;font-size:23px;letter-spacing:-.05em}.rv2-pdf-sheet i{height:1px;background:#bcb7a7;margin:0 0 12px}.rv2-pdf-sheet span{font:800 9px var(--font-ibm-plex-mono),monospace;color:#55534c}.rv2-pdf-sheet small{margin-top:auto;color:#827d70;font:800 8px var(--font-ibm-plex-mono),monospace}.rv2-pdf-copy{display:grid;align-content:center;gap:9px}.rv2-pdf-copy strong{font-size:16px}.rv2-pdf-copy span{max-width:360px;color:${T.secondary};font-size:12px;line-height:1.55}.rv2-pdf-copy button{width:max-content;height:35px;margin-top:6px;padding:0 11px;border:1px solid ${T.amber};border-radius:6px;background:${T.amber};color:#161207;display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:900;cursor:pointer}.rv2-pdf-copy button:disabled{opacity:.42;cursor:not-allowed}@media(max-width:600px){.rv2-pdf-report{grid-template-columns:1fr}.rv2-pdf-sheet{max-width:220px}}
    `}</style>
  </div>;
}

function OutputCard({ section, response }) {
  const [collapsed, setCollapsed] = useState(false); const value = lookup(response, section); const available = value !== null && value !== undefined;
  return <motion.article id={section.id} className={`rv2-output rv2-${section.rank}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <header><div><p>{section.source}.{section.dataKey}</p><h3>{section.title}</h3></div><div className="rv2-card-actions"><span>{section.chartType}</span><button type="button" onClick={() => setCollapsed((current) => !current)} aria-label={`${collapsed ? "Expand" : "Collapse"} ${section.title}`}>{collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</button></div></header>
    {!collapsed ? <div className="rv2-output-body">{available ? section.dataKey === "pdf_report" ? <PdfReport value={value} response={response} /> : <GenericChart value={value} type={section.chartType} /> : <div className="rv2-await"><Database size={18} /><div><strong>Awaiting study result</strong><span>{section.source}.{section.dataKey} is registered and ready for the Research V2 response.</span></div></div>}</div> : null}
  </motion.article>;
}

function OutputRail({ feature, sections, active, onSelect, filter, setFilter }) {
  const deferredFilter = useDeferredValue(filter);
  const visible = sections.filter((section) => section.title.toLowerCase().includes(deferredFilter.toLowerCase()) || section.dataKey.includes(deferredFilter.toLowerCase()));
  return <aside className="rv2-rail"><div className="rv2-rail-head"><span>OUTPUT BOOK</span><b>{sections.length}</b></div><label className="rv2-output-search"><Search size={13} /><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter outputs" /></label><nav>{visible.map((section, index) => <button key={section.id} type="button" onClick={() => onSelect(section.id)} className={active === section.id ? "active" : ""}><i>{String(index + 1).padStart(2, "0")}</i><span>{section.title}</span><em>{section.source === "charts" ? <BarChart3 size={12} /> : <Table2 size={12} />}</em></button>)}</nav><div className="rv2-rail-foot"><CircleDot size={12} /> {feature.id === "07" || feature.id === "09" ? "Research-grade design" : "Output contract mapped"}</div></aside>;
}

export function ResearchV2Workbench({ featureId, response = null, onRun }) {
  const feature = getResearchV2Feature(featureId); const [form, setForm] = useState(() => defaultForm(feature)); const [configOpen, setConfigOpen] = useState(false); const [filter, setFilter] = useState(""); const [active, setActive] = useState(feature.sections[0]?.id);
  const run = (payload) => { onRun?.(payload); };
  const scrollTo = (id) => { setActive(id); document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  return <main className="rv2-workbench"><header className="rv2-topbar"><Link href="/labs/research-v2" className="rv2-brand">ATLAS <span>/ RESEARCH</span></Link><div className="rv2-breadcrumb">F{feature.id} <b>/</b> {feature.title}</div><div className="rv2-topbar-space" /><span className="rv2-contract"><CircleDot size={11} /> CONTRACT READY</span><button type="button" className="rv2-config-trigger" onClick={() => setConfigOpen(true)}><SlidersHorizontal size={14} /> Configure study</button></header>
    <section className="rv2-feature-head"><div><p>Research V2 / Feature {feature.id}</p><h1>{feature.title}</h1><span>{feature.description}</span></div><div className="rv2-run-meta"><strong>{response ? "COMPUTED" : "CONFIGURED"}</strong><span>{response ? "Response contract resolved" : `${feature.sections.length} output contracts`}</span><button type="button" onClick={() => run(buildPayload(form))}><Play size={15} /> Run study</button></div></section>
    <section className="rv2-study-strip"><div><Columns3 size={14} /><span>{form.universe || "master"}</span></div><div><ListFilter size={14} /><span>{form.signal || form.identification_design || "research"}</span></div><div><FileJson size={14} /><span>{form.lookback_days ? `${form.lookback_days}d window` : "contract-bound"}</span></div></section>
    <section className="rv2-workspace"><OutputRail feature={feature} sections={feature.sections} active={active} onSelect={scrollTo} filter={filter} setFilter={setFilter} /><div className="rv2-output-stack">{feature.sections.map((section) => <OutputCard key={section.id} section={section} response={response} />)}</div></section>
    <ConfigCurtain open={configOpen} onClose={() => setConfigOpen(false)} feature={feature} form={form} setForm={setForm} onRun={run} />
    <style jsx global>{`${styles}${researchVisualStyles}`}</style>
  </main>;
}

export function ResearchV2Home() {
  return <main className="rv2-home"><section className="rv2-home-hero"><p>ATLAS / RESEARCH V2</p><h1>Evidence before conviction.</h1><span>Ten research-grade modules for testing a signal, breaking it, and documenting what survives.</span><div><Link href="/labs/research-v2/feature-01">Open canonical test <Play size={14} /></Link><a href="#research-v2-modules">Browse modules</a></div></section><section id="research-v2-modules" className="rv2-module-grid">{RESEARCH_V2_FEATURES.map((feature) => <Link key={feature.id} href={`/labs/research-v2/${feature.slug}`}><p>F{feature.id}</p><h2>{feature.title}</h2><span>{feature.description}</span><b>{feature.sections.length} outputs <ChevronDown size={14} /></b></Link>)}</section><style jsx global>{`${styles}${researchVisualStyles}`}</style></main>;
}

const styles = `
  .rv2-workbench,.rv2-home{min-height:100dvh;background:${T.page};color:${T.text};font-family:var(--font-dm-sans),system-ui,sans-serif}.rv2-workbench{padding:20px 26px 130px}.rv2-topbar{height:52px;display:flex;align-items:center;gap:16px;border-bottom:1px solid ${T.borderSubtle};position:sticky;top:0;z-index:20;background:rgba(8,9,7,.9);backdrop-filter:blur(18px)}.rv2-brand{color:${T.amber};text-decoration:none;font:900 12px var(--font-ibm-plex-mono),monospace;letter-spacing:.16em}.rv2-brand span{color:${T.muted};font-weight:700}.rv2-breadcrumb{font-size:12px;color:${T.secondary};font-weight:700}.rv2-breadcrumb b{color:${T.muted};margin:0 5px}.rv2-topbar-space{flex:1}.rv2-contract{display:inline-flex;align-items:center;gap:6px;color:${T.green};font:800 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.11em}.rv2-config-trigger,.rv2-run-meta button{height:34px;padding:0 12px;border:1px solid rgba(230,173,54,.45);border-radius:7px;background:${T.amberSoft};color:${T.amber};display:inline-flex;align-items:center;gap:7px;font:800 11px var(--font-dm-sans),sans-serif;cursor:pointer}.rv2-feature-head{max-width:1500px;margin:34px auto 18px;display:flex;align-items:end;justify-content:space-between;gap:26px}.rv2-feature-head p,.rv2-home-hero p{margin:0;color:${T.amber};font:900 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.18em;text-transform:uppercase}.rv2-feature-head h1{margin:8px 0;font-size:clamp(30px,4vw,48px);line-height:1;letter-spacing:-.045em}.rv2-feature-head>div>span{display:block;max-width:720px;color:${T.secondary};font-size:15px;line-height:1.6}.rv2-run-meta{display:grid;justify-items:end;gap:5px;min-width:190px}.rv2-run-meta strong{color:${T.green};font:900 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.14em}.rv2-run-meta>span{font-size:11px!important;color:${T.muted}!important}.rv2-run-meta button{margin-top:5px;background:${T.amber};color:#17130a;border-color:${T.amber};height:38px}.rv2-study-strip{max-width:1500px;margin:0 auto 16px;display:flex;flex-wrap:wrap;gap:7px}.rv2-study-strip div{height:30px;padding:0 10px;border:1px solid ${T.border};background:${T.panel};border-radius:6px;display:inline-flex;align-items:center;gap:7px;color:${T.secondary};font:800 10px var(--font-ibm-plex-mono),monospace}.rv2-study-strip svg{color:${T.amber}}.rv2-workspace{max-width:1500px;margin:0 auto;display:grid;grid-template-columns:244px minmax(0,1fr);gap:18px;align-items:start}.rv2-rail{position:sticky;top:68px;border:1px solid ${T.border};background:linear-gradient(180deg,rgba(21,24,18,.94),rgba(10,12,9,.94));border-radius:10px;overflow:hidden}.rv2-rail-head{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid ${T.borderSubtle};font:900 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.15em;color:${T.amber}.rv2-rail-head b{color:${T.secondary};font-size:11px}.rv2-output-search{height:40px;margin:8px;border:1px solid ${T.border};border-radius:6px;background:${T.screen};display:flex;align-items:center;gap:7px;padding:0 9px;color:${T.muted}.rv2-output-search input{width:100%;border:0;outline:0;background:transparent;color:${T.text};font-size:11px}.rv2-rail nav{max-height:calc(100dvh - 250px);overflow:auto;padding:2px 6px 8px}.rv2-rail nav button{width:100%;min-height:39px;padding:7px 6px;border:0;border-left:2px solid transparent;background:transparent;color:${T.muted};display:grid;grid-template-columns:24px 1fr 15px;gap:5px;align-items:center;text-align:left;cursor:pointer;transition:background .14s,color .14s,border-color .14s}.rv2-rail nav button:hover{color:${T.text};background:rgba(255,255,255,.035)}.rv2-rail nav button.active{color:${T.text};background:${T.amberSoft};border-left-color:${T.amber}}.rv2-rail nav i{font:900 9px var(--font-ibm-plex-mono),monospace;color:${T.amber};font-style:normal}.rv2-rail nav span{font-size:11px;font-weight:700;line-height:1.25}.rv2-rail nav em{color:${T.muted};display:grid;place-items:center}.rv2-rail-foot{height:34px;padding:0 10px;border-top:1px solid ${T.borderSubtle};display:flex;align-items:center;gap:6px;color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.08em;text-transform:uppercase}.rv2-output-stack{display:grid;gap:12px;min-width:0}.rv2-output{position:relative;border:1px solid ${T.border};border-radius:10px;background:linear-gradient(145deg,rgba(17,20,15,.96),rgba(10,11,9,.98));padding:15px;overflow:hidden;scroll-margin-top:82px}.rv2-output:before{content:"";position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(230,173,54,.34),transparent)}.rv2-output.rv2-primary{border-left:3px solid ${T.amber};padding-left:13px;box-shadow:0 12px 40px rgba(0,0,0,.18)}.rv2-output header{min-height:34px;display:flex;justify-content:space-between;gap:12px;align-items:start;margin-bottom:12px}.rv2-output header p{margin:0 0 4px;color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.09em}.rv2-output header h3{margin:0;font-size:14px;letter-spacing:-.01em}.rv2-card-actions{display:flex;align-items:center;gap:7px}.rv2-card-actions span{color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace;text-transform:uppercase}.rv2-card-actions button{width:29px;height:29px;border:1px solid ${T.border};border-radius:6px;background:${T.screen};color:${T.secondary};display:grid;place-items:center;cursor:pointer}.rv2-output-body{min-height:116px;border-top:1px solid ${T.borderSubtle};padding-top:12px}.rv2-await{min-height:116px;display:flex;align-items:center;justify-content:center;gap:10px;color:${T.muted};font-size:11px}.rv2-await svg{color:${T.amber}}.rv2-await strong{display:block;color:${T.secondary};margin-bottom:3px}.rv2-await span{display:block;font:10px var(--font-ibm-plex-mono),monospace}.rv2-no-data{min-height:100px;display:grid;place-items:center;color:${T.muted};font:11px var(--font-ibm-plex-mono),monospace}.rv2-table-wrap{overflow:auto;max-height:430px}.rv2-table{width:100%;border-collapse:collapse;font-size:11px}.rv2-table th{position:sticky;top:0;background:${T.panelRaised};color:${T.secondary};text-align:left;font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.08em;text-transform:uppercase}.rv2-table th,.rv2-table td{padding:9px 10px;border-bottom:1px solid ${T.borderSubtle};white-space:nowrap}.rv2-table td{color:${T.secondary};font-family:var(--font-ibm-plex-mono),monospace}.rv2-table tbody tr:hover td{background:rgba(230,173,54,.045);color:${T.text}}.rv2-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px}.rv2-metrics div{min-height:104px;padding:12px;border:1px solid ${T.borderSubtle};border-radius:8px;background:radial-gradient(circle at 100% 0,rgba(230,173,54,.09),transparent 43%),${T.screen}}.rv2-metrics span,.rv2-metrics small{display:block;color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.08em;text-transform:uppercase}.rv2-metrics strong{display:block;margin:10px 0 5px;color:${T.text};font-size:25px;letter-spacing:-.04em}.rv2-heatmap-wrap{overflow:auto}.rv2-heatmap{min-width:540px;display:grid;gap:2px;align-items:center}.rv2-heatmap>b,.rv2-heatmap>strong{padding:6px;color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace;text-transform:uppercase}.rv2-heatmap>strong{color:${T.secondary}}.rv2-heatmap>span{height:34px;display:grid;place-items:center;border-radius:3px;color:#fff;font:800 10px var(--font-ibm-plex-mono),monospace}.rv2-curtain{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.72);backdrop-filter:blur(14px);overflow:auto;padding:34px}.rv2-curtain section{width:min(1320px,100%);margin:auto;border:1px solid ${T.border};border-radius:14px;background:linear-gradient(180deg,#151812,#090a08);box-shadow:0 38px 120px rgba(0,0,0,.78)}.rv2-curtain header,.rv2-curtain footer{min-height:62px;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid ${T.borderSubtle}}.rv2-curtain footer{border-bottom:0;border-top:1px solid ${T.borderSubtle};color:${T.muted};font-size:11px}.rv2-curtain header p{margin:0;color:${T.amber};font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.13em}.rv2-curtain header h2{margin:4px 0 0;font-size:17px}.rv2-curtain header>button{width:34px;height:34px;border:1px solid ${T.border};background:${T.screen};border-radius:7px;color:${T.secondary};display:grid;place-items:center;cursor:pointer}.rv2-curtain footer>div{display:flex;gap:7px}.rv2-curtain footer button{height:34px;padding:0 11px;border:1px solid ${T.border};border-radius:7px;background:${T.screen};color:${T.secondary};font-size:11px;font-weight:800;cursor:pointer}.rv2-curtain footer button.run{background:${T.amber};border-color:${T.amber};color:#17130a;display:inline-flex;align-items:center;gap:6px}.rv2-form{padding:4px 18px 14px}.rv2-form-group{display:grid;grid-template-columns:165px 1fr;gap:18px;padding:15px 0;border-top:1px solid ${T.borderSubtle}}.rv2-form-group:first-child{border-top:0}.rv2-form-group h3{margin:3px 0;color:${T.muted};font:800 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.13em;text-transform:uppercase}.rv2-form-group>div{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:13px}.rv2-field{display:grid;gap:6px;min-width:0}.rv2-field-wide{grid-column:1/-1}.rv2-field>span{display:flex;justify-content:space-between;color:${T.secondary};font-size:11px;font-weight:800}.rv2-field>span b{color:${T.amber};font:800 10px var(--font-ibm-plex-mono),monospace}.rv2-field input,.rv2-field textarea{width:100%;box-sizing:border-box;border:1px solid ${T.border};border-radius:6px;background:${T.screen};color:${T.text};outline:0;padding:0 10px;height:36px;font-size:12px}.rv2-field textarea{height:82px;padding:9px;font-family:var(--font-ibm-plex-mono),monospace;resize:vertical}.rv2-field input:focus,.rv2-field textarea:focus{border-color:rgba(230,173,54,.65);box-shadow:0 0 0 2px rgba(230,173,54,.1)}.rv2-chip-row{display:flex;gap:5px;flex-wrap:wrap}.rv2-chip-row button{height:29px;padding:0 9px;border:1px solid ${T.border};border-radius:5px;background:${T.screen};color:${T.muted};font-size:10px;font-weight:800;cursor:pointer;text-transform:capitalize}.rv2-chip-row button.active{border-color:rgba(230,173,54,.54);background:${T.amberSoft};color:${T.amber}}.rv2-file-field>div{display:flex;align-items:center;gap:8px;border:1px solid ${T.border};border-radius:6px;background:${T.screen};padding:0 9px;color:${T.muted}}.rv2-file-field input{border:0;box-shadow:none;background:transparent;padding:0}.rv2-file-field small,.rv2-symbol-shell small{color:${T.muted};font-size:10px}.rv2-symbol-shell{position:relative}.rv2-symbol-box{min-height:38px;display:flex;gap:8px;align-items:start;padding:6px 8px;border:1px solid ${T.border};border-radius:6px;background:${T.screen}}.rv2-symbol-prefix{margin-top:5px;color:${T.amber};font:800 8px var(--font-ibm-plex-mono),monospace;letter-spacing:.08em}.rv2-symbol-tokens{min-width:0;flex:1;display:flex;gap:4px;flex-wrap:wrap}.rv2-symbol-tokens button{height:24px;padding:0 5px;border:1px solid rgba(230,173,54,.35);border-radius:4px;background:${T.amberSoft};color:${T.amber};display:inline-flex;align-items:center;gap:4px;font:800 10px var(--font-ibm-plex-mono),monospace;cursor:pointer}.rv2-symbol-tokens input{height:24px!important;min-width:100px;flex:1;padding:0!important;border:0!important;box-shadow:none!important;background:transparent!important}.rv2-symbol-menu{position:absolute;z-index:9;top:calc(100% + 5px);left:0;right:0;border:1px solid ${T.border};border-radius:8px;background:#090a08;box-shadow:0 20px 70px rgba(0,0,0,.7);overflow:hidden}.rv2-symbol-menu button{width:100%;height:37px;padding:0 10px;border:0;border-bottom:1px solid ${T.borderSubtle};background:transparent;display:grid;grid-template-columns:78px 1fr auto;text-align:left;align-items:center;color:${T.secondary};cursor:pointer}.rv2-symbol-menu button:hover{background:${T.amberSoft}}.rv2-symbol-menu strong{color:${T.text};font:800 10px var(--font-ibm-plex-mono),monospace}.rv2-symbol-menu span{font-size:10px;color:${T.muted}}.rv2-symbol-menu b{color:${T.amber};font:800 9px var(--font-ibm-plex-mono),monospace}.rv2-home{padding:clamp(28px,6vw,92px) 28px 130px}.rv2-home-hero{max-width:850px;margin:0 auto 70px;padding:clamp(52px,11vw,130px) 0 48px;border-bottom:1px solid ${T.borderSubtle};background:radial-gradient(ellipse 70% 65% at 80% 15%,rgba(230,173,54,.12),transparent 56%)}.rv2-home-hero h1{margin:14px 0;font-size:clamp(48px,8vw,104px);line-height:.9;letter-spacing:-.065em}.rv2-home-hero>span{display:block;max-width:580px;color:${T.secondary};font-size:18px;line-height:1.55}.rv2-home-hero>div{display:flex;gap:10px;margin-top:26px}.rv2-home-hero a{height:40px;padding:0 13px;border:1px solid ${T.border};border-radius:6px;background:${T.panel};color:${T.secondary};text-decoration:none;display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:800}.rv2-home-hero a:first-child{background:${T.amber};border-color:${T.amber};color:#17130a}.rv2-module-grid{max-width:1250px;margin:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:10px}.rv2-module-grid a{min-height:230px;padding:18px;border:1px solid ${T.border};border-radius:10px;background:linear-gradient(145deg,${T.panel},${T.screen});display:flex;flex-direction:column;color:${T.text};text-decoration:none;transition:transform .18s ease,border-color .18s ease,background .18s ease}.rv2-module-grid a:hover{transform:translateY(-5px);border-color:rgba(230,173,54,.48);background:linear-gradient(145deg,#1a1b14,${T.screen})}.rv2-module-grid p{margin:0;color:${T.amber};font:800 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.13em}.rv2-module-grid h2{margin:15px 0 8px;font-size:20px;letter-spacing:-.03em}.rv2-module-grid span{color:${T.secondary};font-size:12px;line-height:1.55}.rv2-module-grid b{margin-top:auto;padding-top:18px;display:flex;align-items:center;justify-content:space-between;color:${T.muted};font:800 10px var(--font-ibm-plex-mono),monospace}@media(max-width:900px){.rv2-workbench{padding:12px 12px 104px}.rv2-feature-head{margin-top:23px;display:grid}.rv2-run-meta{justify-items:start}.rv2-workspace{grid-template-columns:1fr}.rv2-rail{position:relative;top:0}.rv2-rail nav{max-height:186px}.rv2-form-group{grid-template-columns:1fr}.rv2-curtain{padding:12px}.rv2-curtain footer{align-items:flex-start;gap:12px;flex-direction:column}.rv2-topbar{gap:8px}.rv2-breadcrumb{display:none}.rv2-contract{display:none}.rv2-home{padding-inline:18px}.rv2-home-hero{margin-bottom:34px}}
`;

const researchVisualStyles = `
  .rv2-output{content-visibility:auto;contain-intrinsic-size:420px}.rv2-output:after{content:"";position:absolute;right:13px;bottom:10px;color:rgba(230,173,54,.065);font:900 52px var(--font-ibm-plex-mono),monospace;letter-spacing:-.1em;pointer-events:none}.rv2-output.rv2-primary:after{content:"RESEARCH"}.rv2-regression{border:1px solid ${T.borderSubtle};border-radius:8px;overflow:auto}.rv2-regression-head,.rv2-regression-row{min-width:720px;display:grid;grid-template-columns:minmax(150px,1.6fr) 100px 80px 90px minmax(150px,1fr);gap:12px;align-items:center;padding:10px 12px;border-bottom:1px solid ${T.borderSubtle}}.rv2-regression-head{background:${T.panelRaised};color:${T.muted};font:900 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.08em}.rv2-regression-row{background:rgba(0,0,0,.08);font-size:11px}.rv2-regression-row:hover{background:rgba(230,173,54,.055)}.rv2-regression-row strong{color:${T.text}}.rv2-regression-row b{font-family:var(--font-ibm-plex-mono),monospace}.rv2-regression-row b.pos{color:${T.green}}.rv2-regression-row b.neg{color:${T.red}}.rv2-regression-row span{color:${T.secondary};font-family:var(--font-ibm-plex-mono),monospace}.rv2-regression-row em{color:${T.muted};font-size:10px;font-style:normal}.rv2-forest{display:grid;gap:8px;padding:8px 0}.rv2-forest-row{display:grid;grid-template-columns:minmax(120px,1fr) minmax(260px,2fr) 64px;gap:12px;align-items:center;min-height:28px;font-size:11px}.rv2-forest-row>span{color:${T.secondary};font-weight:700}.rv2-forest-row>div{height:24px;position:relative;background:linear-gradient(90deg,transparent 49.8%,${T.border} 49.8%,${T.border} 50.2%,transparent 50.2%)}.rv2-forest-row .zero{position:absolute;left:50%;top:0;bottom:0;width:1px;background:${T.muted}}.rv2-forest-row b{position:absolute;top:11px;height:2px;background:${T.blue};border-radius:999px;transform:translateX(-50%)}.rv2-forest-row em{position:absolute;top:6px;width:11px;height:11px;border-radius:50%;transform:translateX(-50%);background:${T.amber};box-shadow:0 0 0 3px rgba(230,173,54,.15)}.rv2-forest-row em.neg{background:${T.red};box-shadow:0 0 0 3px rgba(226,110,92,.12)}.rv2-forest-row>strong{text-align:right;color:${T.secondary};font:800 10px var(--font-ibm-plex-mono),monospace}.rv2-ledger{display:grid;gap:2px}.rv2-ledger>div{display:grid;grid-template-columns:28px repeat(4,minmax(0,1fr));gap:9px;align-items:center;min-height:46px;padding:6px 8px;border-bottom:1px solid ${T.borderSubtle};background:rgba(0,0,0,.08)}.rv2-ledger>div:hover{background:rgba(230,173,54,.05)}.rv2-ledger>div>i{color:${T.amber};font:900 10px var(--font-ibm-plex-mono),monospace;font-style:normal}.rv2-ledger span{min-width:0}.rv2-ledger small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:${T.muted};font:800 8px var(--font-ibm-plex-mono),monospace;letter-spacing:.06em;text-transform:uppercase}.rv2-ledger b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:${T.secondary};font-size:10px}.rv2-spec-curve{display:grid;gap:8px}.rv2-spec-summary{min-height:34px;padding:0 10px;border-left:3px solid ${T.amber};background:rgba(230,173,54,.055);display:flex;align-items:center;gap:11px;overflow:auto;white-space:nowrap}.rv2-spec-summary span{color:${T.amber};font:900 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.1em}.rv2-spec-summary b{color:${T.text};font-size:11px}.rv2-spec-summary em{color:${T.muted};font-size:10px;font-style:normal}.rv2-qq{display:grid;grid-template-columns:minmax(240px,1fr) 220px;gap:20px;align-items:center;min-height:280px}.rv2-qq-square{aspect-ratio:1;border:1px solid ${T.border};background:radial-gradient(circle at 50% 50%,rgba(230,173,54,.07),transparent 52%),${T.screen};padding:12px}.rv2-qq-square svg{width:100%;height:100%}.rv2-qq>div:last-child{display:grid;gap:7px}.rv2-qq b{font-size:15px}.rv2-qq span{color:${T.secondary};font-size:12px;line-height:1.5}.rv2-regime{display:grid;gap:10px}.rv2-regime-legend{display:flex;flex-wrap:wrap;gap:7px 12px}.rv2-regime-legend span{display:inline-flex;align-items:center;gap:6px;color:${T.secondary};font:800 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.06em;text-transform:uppercase}.rv2-regime-legend i{width:8px;height:8px;border-radius:2px}.rv2-regime-ribbon{height:150px;border:1px solid ${T.border};background:${T.screen};display:flex;align-items:stretch;overflow:hidden}.rv2-regime-ribbon>div{min-width:2px;flex:1;display:flex;flex-direction:column;justify-content:flex-end}.rv2-regime-ribbon>div:hover{filter:brightness(1.35);transform:scaleY(1.03);transform-origin:bottom}.rv2-regime-ribbon i{display:block;min-height:1px;transition:width .2s ease}.rv2-regime-axis{display:flex;justify-content:space-between;color:${T.muted};font:800 9px var(--font-ibm-plex-mono),monospace}.rv2-event{display:grid;gap:8px}.rv2-event-strip{min-height:32px;display:flex;align-items:center;gap:10px;padding:0 10px;border:1px solid ${T.borderSubtle};background:${T.screen};overflow:auto;white-space:nowrap}.rv2-event-strip span{color:${T.amber};font:900 9px var(--font-ibm-plex-mono),monospace;letter-spacing:.1em}.rv2-event-strip b{color:${T.text};font:800 11px var(--font-ibm-plex-mono),monospace}.rv2-event-strip em{color:${T.muted};font-size:10px;font-style:normal}.rv2-vitality{min-height:300px;display:grid;place-items:center;align-content:center;gap:2px}.rv2-vitality svg{width:min(360px,100%);filter:drop-shadow(0 24px 42px rgba(0,0,0,.38))}.rv2-vitality strong{font-size:14px}.rv2-vitality span{color:${T.muted};font:900 10px var(--font-ibm-plex-mono),monospace;letter-spacing:.15em}.rv2-output.rv2-primary .rv2-output-body{min-height:320px}.rv2-output:has(.rv2-regression),.rv2-output:has(.rv2-ledger),.rv2-output:has(.rv2-table-wrap){content-visibility:visible}@media(max-width:760px){.rv2-regression-head,.rv2-regression-row{min-width:650px}.rv2-forest-row{grid-template-columns:100px minmax(190px,1fr) 54px}.rv2-ledger>div{grid-template-columns:24px repeat(2,minmax(0,1fr))}.rv2-ledger>div span:nth-last-child(-n+2){display:none}.rv2-qq{grid-template-columns:1fr}.rv2-qq-square{max-width:320px}.rv2-output.rv2-primary .rv2-output-body{min-height:200px}}
`;
