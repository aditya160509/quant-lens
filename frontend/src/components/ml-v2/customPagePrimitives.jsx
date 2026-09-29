"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  Copy,
  Download,
  Eraser,
  Film,
  Maximize2,
  Pencil,
  Play,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { runMlV2Feature, searchMlV2Symbols } from "@/lib/api";
import { getMlV2Feature, getMlV2Sections, ML_V2_FEATURES } from "./registry";

const TOKENS = {
  ink: "#070707",
  panel: "#0C0C0D",
  screen: "#101011",
  raised: "#151516",
  input: "#0E1014",
  rule: "#26262A",
  ruleSoft: "#1A1A1C",
  ruleStrong: "#3A3A3F",
  ink_text: "#EDEDEC",
  text: "#EDEDEC",
  secondary: "#9A9A9E",
  muted: "#5C5C61",
  signal: "#FF8A1E",
  signalDim: "#7A4A1E",
  pos: "#2BA85E",
  neg: "#D6453A",
  neutral: "#5B7C9E",
  catA: "#FF8A1E",
  catB: "#5B7C9E",
  catC: "#8A7CA8",
  catD: "#2BA85E",
};

const SERIES = [TOKENS.signal, TOKENS.neutral, TOKENS.pos, TOKENS.catC, TOKENS.neg, "#C9A227", "#6E8FA8", "#A8826E"];

function numberLike(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const n = Number(String(value).replace(/[$,%]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function formatValue(value) {
  const n = numberLike(value);
  if (n == null) return value == null ? "—" : String(value);
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return Math.round(n).toLocaleString();
  if (abs > 0 && abs < 0.01) return n.toExponential(2);
  if (abs <= 1) return n.toFixed(4);
  return n.toFixed(3).replace(/\.?0+$/, "");
}

function titleize(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function rowsFrom(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map((item, i) => (item && typeof item === "object" ? item : { name: String(i + 1), value: item }));
  if (typeof value === "object") {
    if (Array.isArray(value.rows)) return rowsFrom(value.rows);
    if (Array.isArray(value.data)) return rowsFrom(value.data);
    return Object.entries(value).map(([name, val]) => (val && typeof val === "object" && !Array.isArray(val) ? { name, ...val } : { name, value: val }));
  }
  return [{ name: "Value", value }];
}

function pickData(response, section) {
  if (!response) return null;
  if (section.source === "summary") return response.summary_cards || response.summary || null;
  const source = response[section.source] || {};
  return source[section.dataKey] ?? response.charts?.[section.dataKey] ?? response.tables?.[section.dataKey] ?? response.meta?.[section.dataKey] ?? null;
}

function inferKeys(rows, config = {}) {
  const sample = rows.find(Boolean) || {};
  const keys = Object.keys(sample);
  const xKey = config.xKey || keys.find((key) => /date|time|horizon|fold|path|model|asset|ticker|factor|feature|regime|state|bucket|name|metric|component/i.test(key)) || keys[0] || "name";
  const yKeys = config.yKeys || keys.filter((key) => key !== xKey && numberLike(sample[key]) != null).slice(0, 8);
  return { xKey, yKeys: yKeys.length ? yKeys : ["value"] };
}

function axis() {
  return {
    tick: { fill: TOKENS.secondary, fontSize: 11, fontFamily: "IBM Plex Mono, Courier New, monospace" },
    axisLine: false,
    tickLine: false,
  };
}

function moveById(list, fromId, toId) {
  if (!fromId || !toId || fromId === toId) return list;
  const next = [...list];
  const from = next.indexOf(fromId);
  const to = next.indexOf(toId);
  if (from < 0 || to < 0) return list;
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function MlTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="ml-tooltip">
      <b>{label}</b>
      {payload.map((entry, index) => (
        <span key={`${entry.dataKey}-${index}`}>
          <i style={{ background: entry.color || TOKENS.signal }} />
          {entry.name || entry.dataKey}
          <strong>{formatValue(entry.value)}</strong>
        </span>
      ))}
    </div>
  );
}

function FieldInput({ field, value, onChange }) {
  const key = String(field.key || "");
  const options = field.options || [];
  const type = field.type || "text";
  const isTicker = /symbol|ticker|asset|universe/i.test(key) || type === "ticker_list";
  if (isTicker) {
    return <TerminalTickerInput label={titleize(field.key)} multi={type === "ticker_list" || /symbols|assets|universe/i.test(key)} value={value} onChange={onChange} />;
  }
  if (type === "multi_select") {
    const selected = Array.isArray(value) ? value.map(String) : String(value || "").split(",").map((v) => v.trim()).filter(Boolean);
    return (
      <label className="ml-field wide">
        <span>{titleize(field.key)}</span>
        <div className="ml-token-grid">
          {options.map((opt) => {
            const active = selected.includes(String(opt));
            return (
              <button key={String(opt)} type="button" className={active ? "active" : ""} onClick={() => {
                const next = active ? selected.filter((item) => item !== String(opt)) : [...selected, String(opt)];
                onChange(next);
              }}>{String(opt)}</button>
            );
          })}
        </div>
      </label>
    );
  }
  if (type === "select" || type === "integer" || type === "float") {
    return (
      <label className="ml-field">
        <span>{titleize(field.key)}</span>
        <select value={String(value ?? field.default ?? options[0] ?? "")} onChange={(event) => onChange(event.target.value)}>
          {options.length ? options.map((opt) => <option value={String(opt)} key={String(opt)}>{String(opt)}</option>) : <option value={String(value ?? field.default ?? "")}>{String(value ?? field.default ?? "")}</option>}
        </select>
      </label>
    );
  }
  return (
    <label className="ml-field">
      <span>{titleize(field.key)}</span>
      <input value={Array.isArray(value) ? value.join(",") : String(value ?? "")} onChange={(event) => onChange(event.target.value)} placeholder={field.description || field.source || ""} />
    </label>
  );
}

function TerminalTickerInput({ label, value, onChange, multi }) {
  const [query, setQuery] = useState("");
  const [remoteSuggestions, setRemoteSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);
  const tokens = String(Array.isArray(value) ? value.join(",") : value || "").split(",").map((item) => item.trim()).filter(Boolean);
  const fallback = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO", "BTC_USD", "ETH_USD", "AAPL", "MSFT", "NVDA", "AMZN", "META"];
  const suggestions = (remoteSuggestions.length ? remoteSuggestions : fallback.map((symbol) => ({ symbol, name: "Fallback symbol", asset_type: "local" })))
    .filter((item) => item.symbol?.toLowerCase().includes(query.toLowerCase()) && !tokens.includes(item.symbol))
    .slice(0, 8);
  useEffect(() => {
    const clean = query.trim();
    if (clean.length < 1) {
      setRemoteSuggestions([]);
      setSearching(false);
      return undefined;
    }
    let active = true;
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const response = await searchMlV2Symbols(clean, { limit: 12 });
        const list = response?.symbols || response?.data || response || [];
        const normalized = Array.isArray(list)
          ? list.map((item) => typeof item === "string" ? { symbol: item, name: "Local universe", asset_type: "local" } : {
            symbol: String(item.symbol || item.ticker || item.name || "").toUpperCase(),
            name: item.name || item.company || item.description || item.asset_type || "Local universe",
            asset_type: item.asset_type || item.type || item.exchange || "local",
          }).filter((item) => item.symbol)
          : [];
        if (active) setRemoteSuggestions(normalized);
      } catch {
        if (active) setRemoteSuggestions([]);
      } finally {
        if (active) setSearching(false);
      }
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);
  function add(symbol) {
    const next = multi ? [...tokens, symbol] : [symbol];
    onChange(multi ? next.join(",") : symbol);
    setQuery("");
  }
  function remove(symbol) {
    onChange(tokens.filter((item) => item !== symbol).join(","));
  }
  return (
    <label className="ml-field wide ticker-field">
      <span>{label}</span>
      <div className="ml-ticker-box">
        {tokens.map((token) => <button type="button" key={token} onClick={() => remove(token)}>{token}<em>×</em></button>)}
        <input value={query} onChange={(event) => setQuery(event.target.value.toUpperCase())} onKeyDown={(event) => {
          if (event.key === "Enter" && query) { event.preventDefault(); add(query); }
        }} placeholder={tokens.length ? "Add ticker…" : "Type ticker, Enter"} />
        {query ? (
          <div className="ml-ticker-menu">
            {searching ? <span className="ticker-searching">Searching local universe...</span> : null}
            {suggestions.length ? suggestions.map((s) => <button type="button" key={s.symbol} onClick={() => add(s.symbol)}><b>{s.symbol}</b><small>{s.name} · {s.asset_type}</small></button>) : <button type="button" onClick={() => add(query)}><b>{query}</b><small>Add custom</small></button>}
          </div>
        ) : null}
      </div>
    </label>
  );
}

function MLTable({ data, searchQuery = "" }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 500), [data]);
  const cols = useMemo(() => [...new Set(rows.slice(0, 80).flatMap((r) => Object.keys(r)))].slice(0, 14), [rows]);
  const [sort, setSort] = useState({ key: "", dir: "asc" });
  const sortKey = sort.key || cols[0];
  const colStats = useMemo(() => Object.fromEntries(cols.map((col) => {
    const nums = rows.map((r) => numberLike(r[col])).filter((v) => v != null);
    return [col, { max: Math.max(1e-9, ...nums.map(Math.abs)) }];
  })), [cols, rows]);
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    const av = numberLike(a[sortKey]) ?? String(a[sortKey] ?? "");
    const bv = numberLike(b[sortKey]) ?? String(b[sortKey] ?? "");
    const result = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
    return sort.dir === "asc" ? result : -result;
  }), [rows, sort.dir, sortKey]);
  const q = searchQuery.trim().toLowerCase();
  if (!rows.length) return <MLEmpty />;
  return (
    <div className="ml-table-v3-wrap">
      <table className="ml-table-v3">
        <thead><tr>{cols.map((col) => <th key={col} className={sortKey === col ? "sorted" : ""} onClick={() => setSort((s) => ({ key: col, dir: s.key === col && s.dir === "asc" ? "desc" : "asc" }))}>{titleize(col)}<em>{sortKey === col ? (sort.dir === "asc" ? " ↑" : " ↓") : " ↕"}</em></th>)}</tr></thead>
        <tbody>
          {sorted.slice(0, 300).map((row, index) => (
            <tr key={index}>
              {cols.map((col, colIndex) => {
                const n = numberLike(row[col]);
                const alpha = n == null || colIndex === 0 ? 0 : Math.min(0.42, (Math.abs(n) / colStats[col].max) * 0.35 + 0.04);
                const bg = n == null ? undefined : n < 0 ? `rgba(255,77,106,${alpha})` : `rgba(0,229,160,${alpha * 0.75})`;
                const hit = q && String(row[col] ?? "").toLowerCase().includes(q);
                return (
                  <td key={col} className={[n != null ? (n < 0 ? "neg num" : "pos num") : "", hit ? "hit" : ""].filter(Boolean).join(" ")} style={{ background: bg }}>
                    {formatValue(row[col])}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ml-table-footer">{sorted.length} rows · {cols.length} columns{sorted.length > 300 ? " · first 300 shown" : ""}</div>
    </div>
  );
}

function MLPercentileArc({ value }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct > 80 ? TOKENS.neg : pct > 60 ? TOKENS.signal : TOKENS.pos;
  const dash = (pct / 100) * 88;
  return (
    <svg className="metric-arc" viewBox="0 0 72 40" aria-label={`${pct.toFixed(0)} percentile`}>
      <path d="M 8 34 A 28 28 0 0 1 64 34" fill="none" stroke={TOKENS.rule} strokeWidth="5" strokeLinecap="round" />
      <path d="M 8 34 A 28 28 0 0 1 64 34" fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${dash} 88`} />
      <text x="36" y="33" textAnchor="middle" fill={color} fontSize="10" fontWeight="900" fontFamily="IBM Plex Mono, monospace">{pct.toFixed(0)}p</text>
    </svg>
  );
}

function MLMetricPanel({ data }) {
  const rows = rowsFrom(data).slice(0, 8);
  if (!rows.length) return <MLEmpty />;
  const [headline, ...rest] = rows;
  const renderTile = (row, big) => {
    const label = row.label || row.metric || row.name || row.model || "Metric";
    const value = row.value ?? row.score ?? row.ic ?? row.sharpe ?? row.weight ?? row.probability;
    const delta = numberLike(row.delta ?? row.change);
    return (
      <div className={big ? "ml-headline-metric-v4" : "ml-metric-v4"} key={label}>
        <span className="metric-label-v4">{titleize(label)}</span>
        <strong className="metric-value-v4">{formatValue(value)}</strong>
        {delta != null ? <small className={delta >= 0 ? "pos" : "neg"}>{delta >= 0 ? "▲" : "▼"} {formatValue(Math.abs(delta))}</small> : null}
      </div>
    );
  };
  return (
    <div className="ml-metric-stack-v4">
      {renderTile(headline, true)}
      {rest.length ? <div className="ml-metric-grid-v4">{rest.map((row) => renderTile(row, false))}</div> : null}
    </div>
  );
}

function LineLikeChart({ data, type = "line", config = {} }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <MLEmpty />;
  const { xKey, yKeys } = inferKeys(rows, config);
  const Chart = type === "area" ? AreaChart : LineChart;
  return (
    <div className="ml-chart">
      <ResponsiveContainer width="100%" height={380}>
        <Chart data={rows} margin={{ top: 14, right: 22, left: -8, bottom: 8 }}>
          <defs>{yKeys.map((key, i) => <linearGradient id={`ml-grad-${key}`} key={key} x1="0" y1="0" x2="0" y2="1"><stop offset="4%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.36} /><stop offset="96%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.02} /></linearGradient>)}</defs>
          <CartesianGrid stroke={TOKENS.ruleSoft} strokeOpacity={0.55} vertical={false} />
          <XAxis dataKey={xKey} {...axis()} minTickGap={26} />
          <YAxis {...axis()} />
          <Tooltip content={<MlTooltip />} />
          {yKeys.map((key, i) => type === "area" ? <Area key={key} dataKey={key} stroke={SERIES[i % SERIES.length]} fill={`url(#ml-grad-${key})`} strokeWidth={2} dot={false} type="monotone" /> : <Line key={key} dataKey={key} stroke={SERIES[i % SERIES.length]} strokeWidth={2} dot={false} type="monotone" activeDot={{ r: 5, fill: TOKENS.screen, stroke: SERIES[i % SERIES.length], strokeWidth: 2 }} />)}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

function BarLikeChart({ data, horizontal = false }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <MLEmpty />;
  const { xKey, yKeys } = inferKeys(rows);
  const y = yKeys[0] || "value";
  return (
    <div className="ml-chart">
      <ResponsiveContainer width="100%" height={380}>
        <BarChart data={rows.slice(0, 80)} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 14, right: 22, left: horizontal ? 92 : -8, bottom: 8 }}>
          <CartesianGrid stroke={TOKENS.ruleSoft} strokeOpacity={0.55} vertical={false} />
          {horizontal ? <XAxis type="number" {...axis()} /> : <XAxis dataKey={xKey} {...axis()} minTickGap={18} />}
          {horizontal ? <YAxis type="category" dataKey={xKey} {...axis()} width={92} /> : <YAxis {...axis()} />}
          <Tooltip content={<MlTooltip />} />
          <ReferenceLine x={horizontal ? 0 : undefined} y={!horizontal ? 0 : undefined} stroke={TOKENS.muted} strokeDasharray="4 4" />
          <Bar dataKey={y} radius={[3, 3, 0, 0]}>{rows.slice(0, 80).map((row, index) => <Cell key={index} fill={(numberLike(row[y]) ?? 0) < 0 ? TOKENS.neg : SERIES[index % SERIES.length]} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Histogram({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <MLEmpty />;
  const sample = rows[0] || {};
  const valueKey = Object.keys(sample).find((key) => numberLike(sample[key]) != null) || "value";
  const values = rows.map((row) => numberLike(row[valueKey])).filter((v) => v != null);
  if (!values.length) return <MLTable data={data} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const bins = 18;
  const counts = Array.from({ length: bins }, (_, i) => ({ bucket: min + ((max - min) * i) / bins, count: 0 }));
  values.forEach((v) => counts[Math.min(bins - 1, Math.max(0, Math.floor(((v - min) / Math.max(max - min, 1e-9)) * bins)))].count += 1);
  return <BarLikeChart data={counts} />;
}

function MLHeatmap({ data, config = {} }) {
  const rows = rowsFrom(data);
  const [hovered, setHovered] = useState(null);
  if (!rows.length) return <MLEmpty />;
  const sample = rows[0] || {};
  const rowKey = config.rowKey || Object.keys(sample).find((k) => /row|source|from|asset|factor|regime/i.test(k)) || "row";
  const colKey = config.colKey || Object.keys(sample).find((k) => /col|target|to|model|feature|state/i.test(k) && k !== rowKey) || "col";
  const valueKey = config.valueKey || Object.keys(sample).find((k) => k !== rowKey && k !== colKey && numberLike(sample[k]) != null) || "value";
  const rowLabels = [...new Set(rows.map((r) => String(r[rowKey] ?? "")))].filter(Boolean).slice(0, 48);
  const colLabels = [...new Set(rows.map((r) => String(r[colKey] ?? "")))].filter(Boolean).slice(0, 48);
  const maxAbs = Math.max(1e-9, ...rows.map((r) => Math.abs(numberLike(r[valueKey]) ?? 0)));
  const valMap = new Map(rows.map((r) => [`${r[rowKey]}|${r[colKey]}`, numberLike(r[valueKey]) ?? 0]));
  return (
    <div className="ml-heatmap-v3-shell">
      <div className="ml-heatmap-v3" style={{ "--hm-cols": colLabels.length }}>
        <div className="hm-corner" />
        {colLabels.map((col) => <b key={col} className={hovered?.col === col ? "hm-hi" : ""}>{col}</b>)}
        {rowLabels.map((row) => (
          <Fragment key={row}>
            <b className={`hm-row-label ${hovered?.row === row ? "hm-hi" : ""}`}>{row}</b>
            {colLabels.map((col) => {
              const v = valMap.get(`${row}|${col}`) ?? 0;
              const diag = row === col;
              const alpha = Math.min(0.88, (Math.abs(v) / maxAbs) * 0.8 + 0.08);
              const bg = diag ? "linear-gradient(135deg,rgba(0,212,255,.18),rgba(0,212,255,.05))" : config.diverging && v < 0 ? `rgba(77,158,255,${alpha})` : v < 0 ? `rgba(255,77,106,${alpha})` : `rgba(0,212,255,${alpha})`;
              const dim = hovered && hovered.row !== row && hovered.col !== col;
              return <i key={`${row}-${col}`} className={[diag ? "hm-diag" : "", dim ? "hm-dim" : ""].filter(Boolean).join(" ")} style={{ background: bg, boxShadow: Math.abs(v) / maxAbs > 0.7 ? `0 0 16px ${v < 0 ? "rgba(77,158,255,.3)" : "rgba(0,212,255,.28)"}` : "none" }} onMouseEnter={() => setHovered({ row, col, v })} onMouseLeave={() => setHovered(null)}>{diag ? "—" : Math.abs(v) > 0.3 || maxAbs > 10 ? formatValue(v) : ""}</i>;
            })}
          </Fragment>
        ))}
      </div>
      {hovered ? <div className="hm-hover-tip"><strong>{hovered.row} × {hovered.col}</strong><b>{formatValue(hovered.v)}</b><span>{((Math.abs(hovered.v) / maxAbs) * 100).toFixed(0)}% of max</span></div> : null}
      <div className="hm-scale"><span>{config.diverging ? `-${formatValue(maxAbs)}` : "0"}</span><i className={config.diverging ? "hm-scale-div" : "hm-scale-pos"} /><span>{formatValue(maxAbs)}</span></div>
    </div>
  );
}

function ScatterView({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <MLEmpty />;
  const numeric = Object.keys(rows[0] || {}).filter((key) => numberLike(rows[0][key]) != null);
  const x = numeric[0] || "x";
  const y = numeric[1] || numeric[0] || "value";
  return (
    <div className="ml-chart">
      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 14, right: 22, left: -8, bottom: 8 }}>
          <CartesianGrid stroke={TOKENS.ruleSoft} strokeOpacity={0.55} vertical={false} />
          <XAxis dataKey={x} type="number" {...axis()} />
          <YAxis dataKey={y} type="number" {...axis()} />
          <Tooltip content={<MlTooltip />} />
          <Scatter data={rows} fill={TOKENS.signal} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function Quadrant({ data }) {
  const rows = rowsFrom(data);
  const row = rows[0] || {};
  const dsr = numberLike(row.deflated_sharpe_ratio ?? row.dsr ?? row.value ?? rows.find((r) => /sharpe/i.test(String(r.name)))?.value) ?? 0;
  const pbo = numberLike(row.probability_of_backtest_overfitting ?? row.pbo ?? rows.find((r) => /pbo|overfit/i.test(String(r.name)))?.value) ?? 0.5;
  const history = Array.isArray(row.history) ? row.history.slice(-12) : [];
  const px = (p) => 8 + Math.max(0, Math.min(1, p)) * 84;
  const py = (d) => 92 - Math.max(0, Math.min(1, (d + 1) / 2)) * 84;
  return (
    <div className="ml-quadrant-v4">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <rect x="50" y="0" width="50" height="100" fill={TOKENS.neg} opacity="0.05" />
        <line x1="50" y1="0" x2="50" y2="100" stroke={TOKENS.ruleStrong} strokeDasharray="2 2" />
        <line x1="0" y1="46" x2="100" y2="46" stroke={TOKENS.ruleSoft} />
        <text x="2" y="3" fontSize="3.2" fill={TOKENS.muted}>DSR</text>
        <text x="92" y="98" fontSize="3.2" fill={TOKENS.muted}>PBO</text>
        <text x="51" y="98" fontSize="2.6" fill={TOKENS.neg} opacity="0.6">DANGER &gt; 0.5</text>
        {history.map((h, i) => <circle key={i} cx={px(numberLike(h.pbo) ?? 0.5)} cy={py(numberLike(h.dsr) ?? 0)} r="1.1" fill={TOKENS.muted} opacity={0.25 + (i / history.length) * 0.35} />)}
        <circle cx={px(pbo)} cy={py(dsr)} r="2.4" fill={TOKENS.signal} />
      </svg>
      <div className="quadrant-readout-v4"><span>DSR <b>{formatValue(dsr)}</b></span><span>PBO <b className={pbo > 0.5 ? "neg" : "pos"}>{formatValue(pbo)}</b></span></div>
    </div>
  );
}

function useForceLayout(nodes, edges) {
  return useMemo(() => {
    const n = nodes.length;
    if (!n) return new Map();
    let pos = new Map(nodes.map((id, i) => [id, { x: 50 + 30 * Math.cos((i / n) * 6.28), y: 50 + 30 * Math.sin((i / n) * 6.28) }]));
    const adj = new Map(nodes.map((id) => [id, new Set()]));
    edges.forEach((e) => { adj.get(e.a)?.add(e.b); adj.get(e.b)?.add(e.a); });
    for (let iter = 0; iter < 200; iter++) {
      const disp = new Map(nodes.map((id) => [id, { x: 0, y: 0 }]));
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
        const a = pos.get(nodes[i]);
        const b = pos.get(nodes[j]);
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.max(0.5, Math.hypot(dx, dy));
        const rep = 38 / (dist * dist);
        disp.get(nodes[i]).x += (dx / dist) * rep;
        disp.get(nodes[i]).y += (dy / dist) * rep;
        disp.get(nodes[j]).x -= (dx / dist) * rep;
        disp.get(nodes[j]).y -= (dy / dist) * rep;
      }
      edges.forEach((e) => {
        const a = pos.get(e.a);
        const b = pos.get(e.b);
        if (!a || !b) return;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.max(0.5, Math.hypot(dx, dy));
        const attr = (dist * dist) / 90;
        disp.get(e.a).x -= (dx / dist) * attr;
        disp.get(e.a).y -= (dy / dist) * attr;
        disp.get(e.b).x += (dx / dist) * attr;
        disp.get(e.b).y += (dy / dist) * attr;
      });
      const next = new Map();
      nodes.forEach((id) => {
        const p = pos.get(id);
        const d = disp.get(id);
        next.set(id, { x: Math.max(6, Math.min(94, p.x + Math.max(-2, Math.min(2, d.x)))), y: Math.max(6, Math.min(94, p.y + Math.max(-2, Math.min(2, d.y)))) });
      });
      pos = next;
    }
    return pos;
  }, [nodes, edges]);
}

function NetworkView({ data }) {
  const rows = rowsFrom(data).slice(0, 120);
  const edges = useMemo(() => rows.map((r) => ({ a: String(r.source ?? r.from ?? ""), b: String(r.target ?? r.to ?? ""), w: numberLike(r.weight ?? r.value) ?? 0 })).filter((e) => e.a && e.b), [rows]);
  const nodes = useMemo(() => [...new Set(edges.flatMap((e) => [e.a, e.b]))].slice(0, 32), [edges]);
  const pos = useForceLayout(nodes, edges);
  if (!nodes.length) return <MLEmpty />;
  return (
    <div className="ml-network-v4">
      <svg viewBox="0 0 100 100">
        {edges.map((edge, i) => {
          const a = pos.get(edge.a);
          const b = pos.get(edge.b);
          if (!a || !b) return null;
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={edge.w < 0 ? TOKENS.neg : TOKENS.signal} strokeWidth={Math.min(2.4, Math.max(0.3, Math.abs(edge.w) * 2.4))} opacity="0.4" />;
        })}
        {nodes.map((node, i) => {
          const p = pos.get(node);
          return <g key={node}><circle cx={p.x} cy={p.y} r="2.6" fill={SERIES[i % SERIES.length]} /><text x={p.x + 3.4} y={p.y + 1.2}>{node}</text></g>;
        })}
      </svg>
    </div>
  );
}

const EMPTY_COPY = {
  cpcv_overfitting: "Shows whether your backtest Sharpe survives correction for the number of trials run. Flags overfitting risk.",
  dsr_pbo_quadrant: "Plots deflated Sharpe against probability of backtest overfitting. Bottom-right is the danger zone.",
  causal_network: "Maps which markets lead or lag each other once confounding factors are removed.",
};

function MLEmpty({ section, response }) {
  const copy = EMPTY_COPY[section?.id];
  return (
    <div className="ml-empty-v4">
      <b>{copy ? "Not yet run" : response ? "Output unavailable" : "Awaiting run"}</b>
      <span>{copy || "Configure inputs and run the analysis to populate this output."}</span>
    </div>
  );
}

function renderSection(section, data, response, searchQuery = "") {
  const type = String(section.chartType || "").toLowerCase();
  if (type.includes("metric") || type.includes("gauge") || type.includes("panel")) return <MLMetricPanel data={data} />;
  if (type.includes("table") || type.includes("scoreboard")) return <MLTable data={data} searchQuery={searchQuery} />;
  if (type.includes("heatmap") || type.includes("attention")) return <MLHeatmap data={data} config={section.config || {}} />;
  if (type.includes("histogram") || type.includes("distribution")) return <Histogram data={data} />;
  if (type.includes("bar") || type.includes("waterfall") || type.includes("importance")) return <BarLikeChart data={data} horizontal />;
  if (type.includes("scatter") || type.includes("ice") || type.includes("surface")) return <ScatterView data={data} />;
  if (type.includes("network") || type.includes("graph")) return <NetworkView data={data} />;
  if (type.includes("quadrant") || type.includes("decision")) return <Quadrant data={data} />;
  if (type.includes("area") || type.includes("stack")) return <LineLikeChart data={data} type="area" />;
  return data ? <LineLikeChart data={data} type="line" /> : <MLEmpty section={section} response={response} />;
}

function MLHeaderSparkline({ data, primaryKey }) {
  const rows = rowsFrom(data);
  if (rows.length < 3) return null;
  const sample = rows[0] || {};
  const key = primaryKey || Object.keys(sample).find((k) => numberLike(sample[k]) != null);
  if (!key) return null;
  const values = rows.map((r) => numberLike(r[key])).filter((v) => v != null);
  if (values.length < 3) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((v, i) => `${(i / (values.length - 1)) * 100},${22 - ((v - min) / range) * 20}`).join(" ");
  const lastUp = values.at(-1) >= values.at(-2);
  return <svg className="ml-header-spark" viewBox="0 0 100 26" aria-hidden><polyline points={points} fill="none" stroke={lastUp ? TOKENS.pos : TOKENS.neg} strokeWidth="1.4" /></svg>;
}

function MLDrawingCanvas({ enabled, resetKey }) {
  const ref = useRef(null);
  const drawing = useRef(false);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const resize = () => {
      const rect = parent.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.lineWidth = 2.2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = TOKENS.signal;
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [resetKey, enabled]);
  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, ref.current.width, ref.current.height);
  }, [resetKey]);
  if (!enabled) return null;
  return (
    <canvas ref={ref} className="ml-drawing-canvas" onPointerDown={(event) => {
      drawing.current = true;
      const ctx = event.currentTarget.getContext("2d");
      ctx.beginPath();
      ctx.moveTo(event.nativeEvent.offsetX, event.nativeEvent.offsetY);
    }} onPointerMove={(event) => {
      if (!drawing.current) return;
      const ctx = event.currentTarget.getContext("2d");
      ctx.lineTo(event.nativeEvent.offsetX, event.nativeEvent.offsetY);
      ctx.stroke();
    }} onPointerUp={() => { drawing.current = false; }} onPointerLeave={() => { drawing.current = false; }} />
  );
}

function FeatureHero({ feature, sections, onRun, loading, accent }) {
  return (
    <section className="ml-hero-v4" style={{ "--feature-accent": accent }}>
      <div className="hero-rule-top" />
      <div className="hero-inner-v4">
        <div className="hero-crumb-v4">
          <Link href="/labs/ml-v2">NEXUS</Link>
          <span>/</span>
          <span>ML V2</span>
          <span>/</span>
          <span>F{String(feature.id).padStart(2, "0")}</span>
        </div>
        <div className="hero-row-v4">
          <h1 className="hero-title-v4">{feature.title}</h1>
          <button className="ml-run-v4" onClick={onRun} disabled={loading} type="button">
            <Play size={14} fill="currentColor" />
            <span>{loading ? "COMPUTING" : "RUN"}</span>
          </button>
        </div>
        <p className="hero-desc-v4">{feature.description}</p>
        <div className="hero-stat-line-v4">
          <span><b>{sections.length}</b>OUTPUTS</span>
          <span className="rule-sep" />
          <span><b>{feature.researchOnly?.length || 0}</b>RESEARCH-ONLY</span>
          <span className="rule-sep" />
          <span><b>{feature.defaults?.compute_mode?.toUpperCase() || "REALTIME"}</b>MODE</span>
        </div>
        {feature.researchOnly?.length ? (
          <details className="research-roadmap-v4">
            <summary>Research roadmap</summary>
            <div>{feature.researchOnly.map((item) => <span key={item}>{titleize(item)}</span>)}</div>
          </details>
        ) : null}
      </div>
    </section>
  );
}

function StatusBadge({ status }) {
  if (!status || status === "live") return null;
  const labels = { live_proxy: "PROXY", research_proxy: "RESEARCH PROXY", live_fast_grid: "FAST GRID" };
  return <span className="status-badge-v4">{labels[status] || String(status).toUpperCase()}</span>;
}

function MLRunProgress({ running, progress }) {
  if (!running && progress === 0) return null;
  return <div className={`ml-run-progress ${running ? "running" : "complete"}`}><div className="ml-run-bar" /><div className="ml-run-stage"><span className="ml-stage-dot" /><span>{running ? "COMPUTING OUTPUTS" : "RUN COMPLETE"}</span></div></div>;
}

function MLTopbar({ featureId, query, setQuery, onExport, onInputOpen }) {
  return (
    <header className="ml-topbar">
      <div className="ml-topbar-brand"><span className="ml-topbar-logo">ATLAS</span><span className="ml-topbar-sep">/</span><span className="ml-topbar-module">ML V2</span><span className="ml-topbar-sep">/</span><span className="ml-topbar-fid">F{String(featureId).padStart(2, "0")}</span></div>
      <div className="ml-topbar-search"><Search size={13} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search outputs… (⌘K)" />{query ? <button onClick={() => setQuery("")} type="button"><X size={12} /></button> : null}</div>
      <div className="ml-topbar-actions">
        <button type="button" onClick={onInputOpen} className="ml-topbar-btn"><SlidersHorizontal size={14} /><span>Input Contract</span></button>
        <button type="button" onClick={onExport} className="ml-topbar-btn"><Download size={14} /><span>Export</span></button>
        <div className="ml-topbar-kbd"><kbd>F</kbd><span>Cinema</span></div>
        <div className="ml-topbar-kbd"><kbd>ESC</kbd><span>Close</span></div>
      </div>
    </header>
  );
}

function MLStickySummary({ sections, activeId, response }) {
  const section = sections.find((s) => s.id === activeId) || sections[0];
  const data = section ? pickData(response, section) : null;
  const nums = rowsFrom(data).flatMap((r) => Object.entries(r).map(([k, v]) => ({ k, v: numberLike(v) })).filter((x) => x.v != null)).slice(0, 5);
  if (!response || !nums.length) return null;
  return <div className="ml-sticky-summary"><span className="ml-summary-label">{section?.title}</span>{nums.map(({ k, v }) => <div className="ml-summary-stat" key={k}><em>{titleize(k)}</em><b>{formatValue(v)}</b></div>)}</div>;
}

function MLOutputDock({ sections, activeId, onJump, cinemaId, onReorder }) {
  const [dragging, setDragging] = useState(null);
  const primaryIds = new Set(sections.filter((s) => s.rank === "primary").map((s) => s.id));
  return (
    <nav className="ml-dock" aria-label="ML outputs">
      <strong className="ml-dock-label">OUTPUTS</strong>
      {sections.map((section, index) => <button key={section.id} className={["ml-dock-btn", activeId === section.id ? "active" : "", primaryIds.has(section.id) ? "primary" : "", dragging === section.id ? "dragging" : "", cinemaId && cinemaId !== section.id ? "dimmed" : ""].filter(Boolean).join(" ")} draggable onClick={() => onJump(section.id)} onDragStart={() => setDragging(section.id)} onDragEnd={() => setDragging(null)} onDragOver={(e) => e.preventDefault()} onDrop={() => { onReorder?.(dragging, section.id); setDragging(null); }} title={section.title} type="button"><span className="dock-index">{String(index + 1).padStart(2, "0")}</span><BarChart3 size={15} /><em className="dock-label">{section.title}</em>{primaryIds.has(section.id) ? <i className="dock-primary-pip" /> : null}</button>)}
    </nav>
  );
}

function MLOutputCard({ section, response, index, activeId, onActive, cinemaId, onCinema, searchQuery }) {
  const [full, setFull] = useState(false);
  const [draw, setDraw] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const data = pickData(response, section);
  const focused = cinemaId === section.id;
  const dimmed = cinemaId && !focused;
  return (
    <motion.article id={section.id} className={["ml-card-v3", section.rank === "primary" ? "primary" : "", activeId === section.id ? "active" : "", full ? "fullscreen" : "", focused ? "cinema-focused" : "", dimmed ? "cinema-dimmed" : ""].filter(Boolean).join(" ")} initial={{ opacity: 0, y: 28, filter: "blur(4px)" }} animate={{ opacity: dimmed ? 0.06 : 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 0.38, delay: section.rank === "primary" ? index * 0.03 : 0.12 + index * 0.035, ease: [0.16, 1, 0.3, 1] }} onMouseEnter={() => onActive(section.id)}>
      <div className="card-top-border" />
      <header className="ml-card-header">
        <div className="card-meta"><code className="card-source">{section.source}.{section.dataKey}</code><h3 className="card-title">{section.title}<StatusBadge status={section.status || response?.[section.source]?.status} /></h3></div>
        <MLHeaderSparkline data={data} primaryKey={section.primaryKey} />
        <div className="card-actions">
          <button type="button" title="Annotate" onClick={() => setDraw((v) => !v)} className={draw ? "active" : ""}><Pencil size={13} /></button>
          <button type="button" title="Clear annotations" onClick={() => setResetKey((k) => k + 1)}><Eraser size={13} /></button>
          <button type="button" title="Copy data" onClick={() => navigator.clipboard?.writeText(JSON.stringify(data ?? {}, null, 2))}><Copy size={13} /></button>
          <button type="button" title="Download JSON" onClick={() => downloadText(`ml-v2-${section.id}.json`, JSON.stringify(data ?? {}, null, 2), "application/json")}><Download size={13} /></button>
          <button type="button" title="Focus this output" onClick={() => onCinema(focused ? null : section.id)} className={`cinema-btn-v4 ${focused ? "active" : ""}`}><Film size={13} /><span>Focus</span></button>
          <button type="button" title="Fullscreen" onClick={() => setFull((v) => !v)}><Maximize2 size={13} /></button>
        </div>
      </header>
      <div className="annotation-corner" title="Annotation canvas available"><Pencil size={11} /></div>
      <div className="ml-screen-v3">{data ? renderSection(section, data, response, searchQuery) : <MLEmpty section={section} response={response} />}<MLDrawingCanvas enabled={draw} resetKey={resetKey} /></div>
    </motion.article>
  );
}

function MLToastRack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return <div className="ml-toast-rack" role="region" aria-live="polite"><AnimatePresence>{toasts.map((toast) => <motion.div key={toast.id} className={`ml-toast ml-toast-${toast.type}`} initial={{ opacity: 0, x: 40, scale: 0.96 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 40, scale: 0.96 }} transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}><span className="toast-pip" /><span className="toast-msg">{toast.message}</span><button onClick={() => onDismiss(toast.id)} type="button">×</button></motion.div>)}</AnimatePresence></div>;
}

function downloadText(filename, text, type = "text/plain") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function MLExportModal({ feature, form, sections, response, onClose }) {
  const [copied, setCopied] = useState("");
  const jsonText = JSON.stringify({ feature: { id: feature.id, title: feature.title }, form, sections: sections.map(({ id, title, source, dataKey, chartType }) => ({ id, title, source, dataKey, chartType })), response, exported_at: new Date().toISOString() }, null, 2);
  const tsvText = sections.map((section) => {
    const rows = rowsFrom(pickData(response, section));
    if (!rows.length) return "";
    const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
    return [`# ${section.title}`, cols.join("\t"), ...rows.map((r) => cols.map((c) => r[c] ?? "").join("\t"))].join("\n");
  }).filter(Boolean).join("\n\n");
  async function copy(text, label) {
    await navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 1600);
  }
  return (
    <motion.div className="ml-export-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.section className="ml-export-modal" initial={{ y: 32, opacity: 0, scale: 0.97 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 32, opacity: 0, scale: 0.97 }} onClick={(e) => e.stopPropagation()}>
        <header><div><p>EXPORT SURFACE</p><h2>F{feature.id} · {feature.title}</h2></div><button onClick={onClose} type="button"><X size={16} /></button></header>
        <div className="ml-export-grid">
          {[{ icon: <Download size={18} />, label: "Workspace JSON", sub: "Full payload with inputs and all outputs.", onClick: () => downloadText(`atlas-ml-f${feature.id}-workspace.json`, jsonText, "application/json") }, { icon: <Download size={18} />, label: "Excel TSV", sub: "All tables as tab-separated values.", onClick: () => downloadText(`atlas-ml-f${feature.id}-outputs.tsv`, tsvText || "No tabular outputs", "text/tab-separated-values") }, { icon: <Copy size={18} />, label: "Copy JSON", sub: copied === "json" ? "Copied!" : "Copy workspace config to clipboard.", onClick: () => copy(jsonText, "json") }, { icon: <Copy size={18} />, label: "Copy TSV", sub: copied === "tsv" ? "Copied!" : "Copy all tables for Excel.", onClick: () => copy(tsvText || "No outputs", "tsv") }].map((item) => <button key={item.label} onClick={item.onClick} type="button" className="ml-export-option"><div className="export-icon">{item.icon}</div><b>{item.label}</b><span>{item.sub}</span></button>)}
        </div>
        <textarea readOnly value={tsvText || jsonText} />
      </motion.section>
    </motion.div>
  );
}

function MLInputCurtain({ feature, form, setForm, open, onClose, onRun, loading }) {
  if (!open) return null;
  return (
    <motion.div className="ml-curtain-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.section className="ml-curtain-panel" initial={{ y: -48, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -48, opacity: 0 }} transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.36 }} onClick={(e) => e.stopPropagation()}>
        <header className="ml-curtain-header"><div><p>INPUT CONTRACT</p><h2>F{feature.id} · {feature.title}</h2></div><button onClick={onClose} type="button"><X size={16} /></button></header>
        <div className="ml-curtain-body"><div className="ml-field-grid-v3">{(feature.fields || []).map((field) => <FieldInput key={field.key} field={field} value={form[field.key]} onChange={(value) => setForm((current) => ({ ...current, [field.key]: value }))} />)}</div></div>
        <footer className="ml-curtain-footer"><button onClick={onClose} type="button" className="ml-curtain-close">Close</button><button onClick={onRun} disabled={loading} type="button" className="ml-curtain-run"><Play size={15} fill="currentColor" />{loading ? "Computing…" : "Run analysis"}</button></footer>
      </motion.section>
    </motion.div>
  );
}

export function MLV2Workbench({ featureId }) {
  const feature = useMemo(() => getMlV2Feature(featureId), [featureId]);
  const sections = useMemo(() => getMlV2Sections(featureId), [featureId]);
  const accentMap = { A: TOKENS.catA, B: TOKENS.catB, C: TOKENS.catC, D: TOKENS.catD };
  const accent = accentMap[feature.category] || TOKENS.signal;
  const [form, setForm] = useState(() => ({ ...(feature.defaults || {}) }));
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState(sections[0]?.id);
  const [cinemaId, setCinemaId] = useState(null);
  const [inputOpen, setInputOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [sectionOrder, setSectionOrder] = useState(() => sections.map((s) => s.id));
  const toastId = useRef(0);
  const orderedSections = useMemo(() => {
    const byId = new Map(sections.map((s) => [s.id, s]));
    return sectionOrder.map((id) => byId.get(id)).filter(Boolean);
  }, [sections, sectionOrder]);
  const filtered = useMemo(() => query ? orderedSections.filter((s) => `${s.title} ${s.dataKey} ${s.chartType}`.toLowerCase().includes(query.toLowerCase())) : orderedSections, [orderedSections, query]);

  function pushToast(message, type = "info") {
    const id = ++toastId.current;
    setToasts((current) => [...current.slice(-3), { id, message, type }]);
    setTimeout(() => setToasts((current) => current.filter((item) => item.id !== id)), 4400);
  }

  function jumpTo(id) {
    setActiveId(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function run() {
    setLoading(true);
    setProgress(0.06);
    setError("");
    const timer = setInterval(() => setProgress((value) => Math.min(0.92, value + 0.07)), 280);
    try {
      const result = await runMlV2Feature(feature.id, form);
      setResponse(result);
      setProgress(1);
      pushToast(`Run complete — ${orderedSections.length} outputs ready`, "success");
      window.localStorage?.setItem(`quant360:ml-v2:${feature.id}:latest`, JSON.stringify(result?.summary_cards || []));
    } catch (err) {
      setError(err?.message || "ML V2 API route is not wired yet.");
      pushToast(err?.message || "Run failed", "error");
    } finally {
      clearInterval(timer);
      setLoading(false);
      setTimeout(() => setProgress(0), 900);
    }
  }

  useEffect(() => {
    const handler = (event) => {
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.key === "Escape") { setCinemaId(null); setInputOpen(false); setExportOpen(false); }
      if (event.key.toLowerCase() === "f" && activeId) { event.preventDefault(); setCinemaId((current) => current === activeId ? null : activeId); }
      if (event.key.toLowerCase() === "e" && event.metaKey) { event.preventDefault(); setExportOpen((value) => !value); }
      if (event.key.toLowerCase() === "k" && event.metaKey) { event.preventDefault(); setQuery(""); setTimeout(() => document.querySelector(".ml-topbar-search input")?.focus(), 50); }
      if (event.key === "ArrowDown") { event.preventDefault(); const i = orderedSections.findIndex((s) => s.id === activeId); if (i < orderedSections.length - 1) jumpTo(orderedSections[i + 1].id); }
      if (event.key === "ArrowUp") { event.preventDefault(); const i = orderedSections.findIndex((s) => s.id === activeId); if (i > 0) jumpTo(orderedSections[i - 1].id); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activeId, orderedSections]);

  return (
    <main className={`ml-v2-shell-v3 ${cinemaId ? "cinema-active" : ""}`}>
      <MLTopbar featureId={feature.id} query={query} setQuery={setQuery} onExport={() => setExportOpen(true)} onInputOpen={() => setInputOpen(true)} />
      <MLRunProgress running={loading} progress={progress} />
      <MLStickySummary sections={orderedSections} activeId={activeId} response={response} />
      <FeatureHero feature={feature} sections={orderedSections} onRun={run} loading={loading} accent={accent} />
      {error ? <div className="ml-error-v3"><AlertTriangle size={16} />{error}</div> : null}
      <section className="ml-workspace-v3">
        <MLOutputDock sections={filtered} activeId={activeId} onJump={jumpTo} cinemaId={cinemaId} onReorder={(from, to) => setSectionOrder((order) => moveById(order, from, to))} />
        <div className="ml-stack-v3">{filtered.map((section, index) => <MLOutputCard key={section.id} section={section} response={response} index={index} activeId={activeId} onActive={setActiveId} cinemaId={cinemaId} onCinema={setCinemaId} searchQuery={query} />)}</div>
      </section>
      <AnimatePresence>
        {inputOpen ? <MLInputCurtain feature={feature} form={form} setForm={setForm} open={inputOpen} onClose={() => setInputOpen(false)} onRun={run} loading={loading} /> : null}
        {exportOpen ? <MLExportModal feature={feature} form={form} sections={orderedSections} response={response} onClose={() => setExportOpen(false)} /> : null}
      </AnimatePresence>
      <MLToastRack toasts={toasts} onDismiss={(id) => setToasts((current) => current.filter((item) => item.id !== id))} />
      <style jsx global>{ML_STYLES}</style>
    </main>
  );
}

export function MLV2HomePage() {
  return (
    <main className="ml-v2-page ml-home">
      <section className="ml-home-hero">
        <p>ATLAS // MACHINE LEARNING LAB</p>
        <h1>Research-grade ML diagnostics for systematic strategies.</h1>
        <span>CPCV, boosted alpha, GARCH, meta-labeling, HRP, regimes, DMA, IC weighting, pairs, microstructure, causal discovery, and sequence alpha.</span>
      </section>
      <section className="ml-home-grid">
        {ML_V2_FEATURES.map((feature) => (
          <Link href={`/labs/ml-v2/${feature.slug}`} key={feature.id} className="ml-home-card">
            <small>ML{feature.id}</small>
            <h2>{feature.title}</h2>
            <p>{feature.description}</p>
            <em>{feature.outputs?.length || 0} outputs</em>
          </Link>
        ))}
      </section>
      <style jsx global>{ML_STYLES}</style>
    </main>
  );
}

const ML_STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
  .ml-v2-shell, .ml-v2-page, .ml-v2-shell-v3 { min-height: 100dvh; background: ${TOKENS.ink}; color: ${TOKENS.text}; }
  .ml-v2-page, .ml-v2-shell-v3 { padding: 0 clamp(18px, 3vw, 52px) 120px; font-family: "IBM Plex Sans Condensed", -apple-system, sans-serif; }
  .mono, .ml-table-v3 td.num, .card-source, .ml-table-v3 th, .metric-value, .metric-delta,
  .ml-summary-stat b, .hero-fid, .ml-topbar-logo, .ml-topbar-fid, .metric-value-v4 {
    font-family: "IBM Plex Mono", "Courier New", monospace;
    font-variant-numeric: tabular-nums slashed-zero;
  }
  .ml-topbar { position: sticky; top: 0; z-index: 60; height: 52px; display: flex; align-items: center; gap: 16px; margin: 0 calc(clamp(18px, 3vw, 52px) * -1); padding: 0 clamp(18px, 3vw, 52px); background: rgba(3,3,4,.88); border-bottom: 1px solid ${TOKENS.ruleSoft}; backdrop-filter: blur(20px); }
  .ml-topbar-brand { display:flex; align-items:center; gap:8px; flex-shrink:0; }
  .ml-topbar-logo { color:${TOKENS.signal}; font:900 11px "IBM Plex Mono", monospace; letter-spacing:.22em; }
  .ml-topbar-sep { color:${TOKENS.rule}; }
  .ml-topbar-module { color:${TOKENS.secondary}; font:800 11px "IBM Plex Mono", monospace; letter-spacing:.12em; }
  .ml-topbar-fid { color:${TOKENS.signal}; font:900 11px "IBM Plex Mono", monospace; }
  .ml-topbar-search { flex:1; max-width:360px; height:34px; border:1px solid ${TOKENS.rule}; border-radius:10px; background:${TOKENS.input}; display:flex; align-items:center; gap:8px; padding:0 11px; color:${TOKENS.muted}; margin:0 auto; }
  .ml-topbar-search input { flex:1; min-width:0; border:0; background:transparent; color:${TOKENS.text}; outline:0; font-size:12px; }
  .ml-topbar-search button { background:transparent; border:0; color:${TOKENS.muted}; cursor:pointer; display:grid; place-items:center; }
  .ml-topbar-search:focus-within { border-color:rgba(0,212,255,.45); box-shadow:0 0 0 3px rgba(0,212,255,.08); }
  .ml-topbar-actions { display:flex; align-items:center; gap:8px; margin-left:auto; }
  .ml-topbar-btn { height:34px; display:inline-flex; align-items:center; gap:7px; border:1px solid ${TOKENS.rule}; border-radius:9px; background:${TOKENS.raised}; color:${TOKENS.secondary}; padding:0 12px; font:800 11px "IBM Plex Mono", monospace; letter-spacing:.08em; cursor:pointer; }
  .ml-topbar-btn:hover { border-color:rgba(0,212,255,.45); color:${TOKENS.signal}; background:rgba(0,212,255,.06); }
  .ml-topbar-kbd { display:flex; align-items:center; gap:5px; color:${TOKENS.muted}; font:900 9px "IBM Plex Mono", monospace; }
  .ml-topbar-kbd kbd { height:20px; padding:0 5px; border:1px solid ${TOKENS.rule}; border-radius:4px; background:${TOKENS.raised}; color:${TOKENS.secondary}; font-size:9px; display:inline-flex; align-items:center; }
  .ml-run-progress { position: sticky; top: 52px; z-index: 50; height: 36px; margin: 0 calc(clamp(18px, 3vw, 52px) * -1); background: ${TOKENS.panel}; border-bottom: 1px solid ${TOKENS.ruleSoft}; overflow: hidden; }
  .ml-run-bar { height:2px; background:linear-gradient(90deg, transparent, ${TOKENS.signal}, transparent); position:absolute; top:0; left:0; width:38%; box-shadow:0 0 18px rgba(255,138,30,.35); }
  .ml-run-progress.running .ml-run-bar { animation:runIndeterminate 1.1s ease-in-out infinite; }
  .ml-run-progress.complete .ml-run-bar { width:100%; background:${TOKENS.pos}; }
  .ml-run-stage { height:34px; display:flex; align-items:center; gap:9px; padding:0 clamp(18px, 3vw, 52px); color:${TOKENS.muted}; font:900 10px "IBM Plex Mono", monospace; letter-spacing:.14em; }
  .ml-stage-dot { width:7px; height:7px; border-radius:50%; background:${TOKENS.signal}; }
  .ml-run-stage b { margin-left:auto; color:${TOKENS.signal}; }
  .ml-sticky-summary { position:sticky; top:52px; z-index:40; height:38px; display:flex; align-items:center; gap:0; margin:0 calc(clamp(18px, 3vw, 52px) * -1); background:rgba(3,3,4,.82); border-bottom:1px solid ${TOKENS.ruleSoft}; backdrop-filter:blur(14px); padding:0 clamp(18px, 3vw, 52px); overflow-x:auto; scrollbar-width:none; }
  .ml-sticky-summary::-webkit-scrollbar { display:none; }
  .ml-summary-label { color:${TOKENS.signal}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.18em; text-transform:uppercase; margin-right:16px; flex-shrink:0; }
  .ml-summary-stat { display:flex; align-items:center; gap:6px; padding:0 14px; border-left:1px solid ${TOKENS.ruleSoft}; flex-shrink:0; }
  .ml-summary-stat em { color:${TOKENS.muted}; font:800 9px "IBM Plex Mono", monospace; letter-spacing:.1em; font-style:normal; text-transform:uppercase; }
  .ml-summary-stat b { color:${TOKENS.text}; font:900 11px "IBM Plex Mono", monospace; }
  .ml-hero-v4 { position:relative; border:1px solid ${TOKENS.rule}; border-radius:4px; padding:32px 36px; margin:20px 0 16px; background:${TOKENS.panel}; }
  .hero-rule-top { position:absolute; top:-1px; left:0; right:0; height:2px; background:var(--feature-accent, ${TOKENS.signal}); }
  .hero-inner-v4 { position:relative; }
  .hero-crumb-v4 { display:flex; gap:6px; color:${TOKENS.muted}; font:600 10px "IBM Plex Mono", monospace; letter-spacing:.14em; margin-bottom:18px; }
  .hero-crumb-v4 a { color:var(--feature-accent, ${TOKENS.signal}); text-decoration:none; }
  .hero-row-v4 { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; flex-wrap:wrap; }
  .hero-title-v4 { margin:0; font:700 clamp(26px,3.4vw,40px)/1.05 "IBM Plex Sans Condensed", sans-serif; letter-spacing:-.01em; color:${TOKENS.text}; }
  .hero-desc-v4 { color:${TOKENS.secondary}; font-size:14px; line-height:1.65; max-width:680px; margin:14px 0 0; }
  .hero-stat-line-v4 { display:flex; align-items:center; gap:12px; margin-top:20px; padding-top:16px; border-top:1px solid ${TOKENS.ruleSoft}; }
  .hero-stat-line-v4 span { display:flex; align-items:center; gap:6px; color:${TOKENS.muted}; font:600 10px "IBM Plex Mono", monospace; letter-spacing:.1em; }
  .hero-stat-line-v4 b { color:${TOKENS.text}; font-size:13px; }
  .rule-sep { width:1px; height:12px; background:${TOKENS.ruleSoft}; }
  .research-roadmap-v4 { margin-top:14px; border-top:1px solid ${TOKENS.ruleSoft}; padding-top:12px; }
  .research-roadmap-v4 summary { cursor:pointer; color:${TOKENS.muted}; font:700 10px "IBM Plex Mono", monospace; letter-spacing:.12em; text-transform:uppercase; }
  .research-roadmap-v4 div { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .research-roadmap-v4 span { border:1px solid ${TOKENS.rule}; color:${TOKENS.secondary}; background:${TOKENS.input}; border-radius:2px; padding:4px 6px; font:600 10px "IBM Plex Mono", monospace; }
  .ml-run-v4 { height:38px; padding:0 18px; border:1px solid var(--feature-accent, ${TOKENS.signal}); border-radius:3px; background:transparent; color:var(--feature-accent, ${TOKENS.signal}); display:flex; align-items:center; gap:8px; font:700 11px "IBM Plex Mono", monospace; letter-spacing:.14em; cursor:pointer; transition:background .12s; }
  .ml-run-v4:hover:not(:disabled) { background:color-mix(in srgb, var(--feature-accent, ${TOKENS.signal}) 12%, transparent); }
  .ml-run-v4:disabled { opacity:.45; cursor:wait; }
  .hero-inner, .ml-run-v3 { position:relative; z-index:2; }
  .hero-breadcrumb { display:flex; align-items:center; gap:6px; color:${TOKENS.muted}; font:800 10px "IBM Plex Mono", monospace; letter-spacing:.2em; margin-bottom:20px; }
  .hero-breadcrumb a { color:${TOKENS.signal}; text-decoration:none; }
  .hero-title { margin:0 0 14px; font:700 clamp(32px,5vw,68px)/.92 "IBM Plex Sans Condensed", sans-serif; letter-spacing:-.04em; color:${TOKENS.text}; display:flex; align-items:baseline; gap:18px; flex-wrap:wrap; }
  .hero-fid { font-family:"IBM Plex Mono", monospace; font-size:clamp(14px,2vw,22px); color:${TOKENS.signal}; letter-spacing:.1em; font-weight:900; border:1px solid rgba(0,212,255,.35); border-radius:7px; padding:4px 10px; background:rgba(0,212,255,.07); align-self:center; flex-shrink:0; }
  .hero-desc { color:${TOKENS.secondary}; font-size:16px; line-height:1.7; max-width:720px; margin:0 0 20px; }
  .hero-meta-strip { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
  .hero-meta-pill { display:inline-flex; align-items:center; gap:6px; height:26px; border:1px solid ${TOKENS.rule}; border-radius:999px; padding:0 10px; color:${TOKENS.muted}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.16em; background:rgba(255,255,255,.025); }
  .hero-meta-pill--live { border-color:rgba(0,229,160,.35); color:${TOKENS.pos}; background:rgba(0,229,160,.06); }
  .hero-live-dot { background:${TOKENS.pos}; }
  .hero-notes { display:flex; flex-direction:column; gap:5px; }
  .hero-notes span { display:flex; align-items:flex-start; gap:7px; color:${TOKENS.muted}; font-size:11px; line-height:1.5; }
  .hero-notes svg { flex-shrink:0; margin-top:2px; color:${TOKENS.signal}; }
  .ml-run-v3 { flex-shrink:0; width:180px; height:56px; border:1px solid rgba(0,212,255,.42); border-radius:14px; background:linear-gradient(135deg, rgba(0,212,255,.18), rgba(0,212,255,.06)); cursor:pointer; overflow:hidden; align-self:flex-end; }
  .ml-run-v3:disabled { opacity:.5; cursor:wait; }
  .run-inner { position:relative; z-index:1; display:flex; align-items:center; justify-content:center; gap:10px; color:${TOKENS.signal}; font:900 12px "IBM Plex Mono", monospace; letter-spacing:.18em; height:100%; }
  .run-glow { position:absolute; inset:0; background:radial-gradient(circle at 50% 120%, rgba(0,212,255,.4), transparent 60%); opacity:0; transition:opacity .3s ease; }
  .ml-run-v3:hover:not(:disabled) .run-glow { opacity:1; }
  .ml-workspace-v3 { display:grid; grid-template-columns:80px minmax(0, 1fr); gap:18px; align-items:start; }
  .ml-stack-v3 { display:grid; gap:14px; }
  .ml-error-v3 { margin:0 0 16px; min-height:46px; border:1px solid rgba(255,77,106,.3); background:rgba(255,77,106,.07); color:${TOKENS.neg}; border-radius:12px; display:flex; align-items:center; gap:10px; padding:0 16px; font-size:13px; }
  .ml-dock { position:sticky; top:74px; max-height:calc(100dvh - 100px); overflow-y:auto; overflow-x:hidden; padding:10px 8px; border:1px solid ${TOKENS.rule}; border-radius:22px; background:rgba(7,8,10,.84); backdrop-filter:blur(18px); display:flex; flex-direction:column; align-items:center; gap:6px; box-shadow:0 24px 80px rgba(0,0,0,.5); scrollbar-width:none; }
  .ml-dock::-webkit-scrollbar { display:none; }
  .ml-dock-label { writing-mode:vertical-rl; color:${TOKENS.signal}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.26em; margin:8px 0 10px; opacity:.7; }
  .ml-dock-btn { width:52px; min-height:46px; border:1px solid ${TOKENS.rule}; border-radius:14px; background:${TOKENS.input}; color:${TOKENS.muted}; display:grid; place-items:center; position:relative; cursor:pointer; transition:transform .18s cubic-bezier(.16,1,.3,1), background .18s, color .18s, border-color .18s, box-shadow .18s; }
  .ml-dock-btn:hover { transform:translateX(8px) scale(1.1); background:rgba(0,212,255,.08); color:${TOKENS.signal}; border-color:rgba(0,212,255,.4); }
  .ml-dock-btn.active { transform:translateX(12px) scale(1.15); background:rgba(0,212,255,.14); color:${TOKENS.signal}; border-color:rgba(0,212,255,.7); box-shadow:0 0 24px rgba(0,212,255,.2); }
  .ml-dock-btn.dragging { opacity:.35; transform:translateX(6px) scale(.94); }
  .ml-dock-btn.dimmed { opacity:.2; pointer-events:none; }
  .dock-index { position:absolute; top:4px; left:5px; font:900 8px "IBM Plex Mono", monospace; color:${TOKENS.muted}; }
  .dock-label { position:absolute; left:66px; white-space:nowrap; opacity:0; pointer-events:none; background:${TOKENS.raised}; border:1px solid ${TOKENS.rule}; border-radius:9px; padding:7px 11px; color:${TOKENS.text}; font:700 12px "IBM Plex Sans Condensed", sans-serif; font-style:normal; box-shadow:0 8px 32px rgba(0,0,0,.5); transition:opacity .12s ease; z-index:5; }
  .ml-dock-btn:hover .dock-label { opacity:1; }
  .dock-primary-pip { position:absolute; top:5px; right:5px; width:5px; height:5px; border-radius:50%; background:${TOKENS.signal}; box-shadow:0 0 6px rgba(245,164,0,.8); }
  .ml-card-v3 { position:relative; border:1px solid ${TOKENS.rule}; border-radius:20px; background:linear-gradient(180deg, rgba(17,19,24,.97), rgba(7,8,10,.99)); box-shadow:inset 0 1px 0 rgba(255,255,255,.04), 0 20px 60px rgba(0,0,0,.35); overflow:hidden; transition:border-color .2s, box-shadow .2s, opacity .25s; }
  .ml-card-v3.active { border-color:rgba(0,212,255,.55); box-shadow:0 0 0 1px rgba(0,212,255,.12), 0 0 50px rgba(0,212,255,.07), 0 24px 80px rgba(0,0,0,.4); }
  .ml-card-v3.primary { border-left:3px solid ${TOKENS.signal}; }
  .ml-card-v3.fullscreen { position:fixed; z-index:120; inset:16px; border-radius:22px; overflow:auto; }
  .ml-card-v3.cinema-focused { z-index:20; box-shadow:0 0 0 1px rgba(0,212,255,.5), 0 0 120px rgba(0,212,255,.12), 0 40px 140px rgba(0,0,0,.7); }
  .ml-card-v3.cinema-dimmed { pointer-events:none; user-select:none; }
  .card-top-border { position:absolute; left:0; right:0; top:0; height:1px; background:linear-gradient(90deg, transparent, rgba(255,255,255,.12), transparent); }
  .ml-card-v3.primary .card-top-border { background:linear-gradient(90deg, transparent, rgba(0,212,255,.7), transparent); }
  .ml-card-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding:16px 18px 0; }
  .card-meta { flex:1; min-width:0; }
  .card-source { display:block; color:${TOKENS.muted}; font:800 9px "IBM Plex Mono", monospace; letter-spacing:.12em; text-transform:uppercase; margin-bottom:5px; }
  .card-title { margin:0; font-size:15px; font-weight:800; letter-spacing:-.015em; color:${TOKENS.text}; line-height:1.3; }
  .status-badge-v4 { display:inline-flex; align-items:center; height:18px; padding:0 6px; border:1px solid ${TOKENS.ruleStrong}; border-radius:2px; color:${TOKENS.muted}; font:700 8px "IBM Plex Mono", monospace; letter-spacing:.1em; margin-left:8px; vertical-align:middle; }
  .card-actions { display:flex; gap:5px; flex-shrink:0; }
  .card-actions button { width:30px; height:30px; display:grid; place-items:center; border:1px solid ${TOKENS.rule}; border-radius:8px; background:${TOKENS.input}; color:${TOKENS.muted}; cursor:pointer; transition:color .15s, border-color .15s, background .15s; }
  .card-actions button:hover { color:${TOKENS.signal}; border-color:rgba(0,212,255,.4); background:rgba(0,212,255,.07); }
  .card-actions button.active { color:${TOKENS.signal}; border-color:rgba(245,164,0,.5); background:rgba(245,164,0,.1); }
  .cinema-btn-v4 { width:auto !important; padding:0 10px !important; gap:6px; font:600 10px "IBM Plex Mono", monospace; letter-spacing:.06em; display:inline-flex !important; }
  .cinema-btn-v4.active { background:color-mix(in srgb, ${TOKENS.signal} 14%, transparent) !important; border-color:${TOKENS.signal} !important; color:${TOKENS.signal} !important; }
  .annotation-corner { position:absolute; right:13px; bottom:13px; width:22px; height:22px; border:1px solid ${TOKENS.ruleSoft}; border-radius:3px; color:${TOKENS.muted}; background:${TOKENS.panel}; display:grid; place-items:center; z-index:3; opacity:.55; pointer-events:none; }
  .ml-card-v3:hover .annotation-corner { opacity:1; color:${TOKENS.signal}; border-color:${TOKENS.signalDim}; }
  .ml-header-spark { width:110px; height:28px; flex-shrink:0; margin:0 8px; }
  .ml-screen-v3 { position:relative; min-height:200px; padding:16px 18px 18px; background:radial-gradient(ellipse at 50% 0%, rgba(0,212,255,.06), transparent 50%), linear-gradient(180deg, ${TOKENS.screen}, #070809); margin:12px 10px 10px; border-radius:14px; border:1px solid ${TOKENS.ruleSoft}; cursor:crosshair; overflow:auto; }
  .ml-screen-v3::after { content:""; pointer-events:none; position:absolute; inset:0; border-radius:14px; background:linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px); background-size:28px 28px; }
  .ml-drawing-canvas { position:absolute; inset:0; z-index:8; border-radius:14px; touch-action:none; cursor:crosshair; }
  .ml-chart { min-height:380px; }
  .ml-tooltip { min-width:180px; border:1px solid ${TOKENS.rule}; border-radius:8px; background:rgba(8,8,8,.96); padding:10px 12px; box-shadow:0 20px 80px rgba(0,0,0,.65); }
  .ml-tooltip b { display:block; color:${TOKENS.text}; margin-bottom:8px; }
  .ml-tooltip span { display:flex; align-items:center; justify-content:space-between; gap:12px; color:${TOKENS.secondary}; font-size:12px; }
  .ml-tooltip i { width:9px; height:9px; border-radius:99px; }
  .ml-tooltip strong { margin-left:auto; color:${TOKENS.text}; font-family:"IBM Plex Mono", monospace; }
  .ml-table-v3-wrap { max-height:560px; overflow:auto; border-radius:12px; border:1px solid ${TOKENS.ruleSoft}; }
  .ml-table-v3 { width:100%; border-collapse:collapse; font-size:12px; }
  .ml-table-v3 th { position:sticky; top:0; z-index:3; background:${TOKENS.screen}; color:${TOKENS.signal}; text-align:left; padding:10px 12px; border-bottom:1px solid ${TOKENS.rule}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.1em; text-transform:uppercase; cursor:pointer; user-select:none; white-space:nowrap; }
  .ml-table-v3 th.sorted { background:${TOKENS.raised}; color:${TOKENS.text}; }
  .ml-table-v3 th em { font-style:normal; color:${TOKENS.muted}; }
  .ml-table-v3 td { height:40px; padding:0 12px; border-bottom:1px solid ${TOKENS.input}; color:${TOKENS.secondary}; font-family:"IBM Plex Mono", monospace; position:relative; overflow:hidden; white-space:nowrap; }
  .ml-table-v3 td.pos { color:${TOKENS.pos}; }
  .ml-table-v3 td.neg { color:${TOKENS.neg}; }
  .ml-table-v3 td.hit { outline:1px solid ${TOKENS.signal}; background:rgba(0,212,255,.1) !important; color:${TOKENS.text} !important; }
  .ml-table-v3 tr:hover td { background:rgba(0,212,255,.04) !important; color:${TOKENS.text}; }
  .ml-table-v3 th:first-child, .ml-table-v3 td:first-child { position:sticky; left:0; z-index:2; background:${TOKENS.screen}; }
  .ml-table-v3 th:first-child { z-index:4; }
  .ml-table-footer { padding:7px 12px; background:#0A0C0F; border-top:1px solid ${TOKENS.ruleSoft}; color:${TOKENS.muted}; font:800 9px "IBM Plex Mono", monospace; letter-spacing:.1em; }
  .ml-metric-stack-v4 { display:grid; gap:14px; }
  .ml-headline-metric-v4 { border:1px solid ${TOKENS.rule}; border-left:3px solid ${TOKENS.signal}; border-radius:3px; padding:18px 20px; background:${TOKENS.input}; }
  .ml-headline-metric-v4 .metric-value-v4 { font-size:36px; }
  .ml-metric-grid-v4 { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:8px; }
  .ml-metric-v4, .ml-headline-metric-v4 { display:grid; gap:4px; }
  .ml-metric-v4 { border:1px solid ${TOKENS.ruleSoft}; border-radius:3px; padding:12px 14px; }
  .metric-label-v4 { color:${TOKENS.muted}; font:600 9px "IBM Plex Mono", monospace; letter-spacing:.12em; text-transform:uppercase; }
  .metric-value-v4 { font:700 20px "IBM Plex Mono", monospace; color:${TOKENS.text}; }
  .metric-value-v4 + small.pos { color:${TOKENS.pos}; }
  .metric-value-v4 + small.neg { color:${TOKENS.neg}; }
  .ml-metric-grid-v3 { display:grid; grid-template-columns:repeat(auto-fit, minmax(190px,1fr)); gap:10px; }
  .ml-metric-v3 { border:1px solid ${TOKENS.rule}; border-radius:14px; padding:16px; background:linear-gradient(135deg, rgba(255,255,255,.025), rgba(0,0,0,.1)); display:grid; grid-template-columns:1fr 76px; gap:6px 10px; align-items:start; transition:border-color .15s, transform .15s; }
  .ml-metric-v3:hover { transform:translateY(-2px); border-color:rgba(0,212,255,.35); }
  .ml-metric-v3.trend-up { box-shadow:inset 3px 0 0 rgba(0,229,160,.55); }
  .ml-metric-v3.trend-dn { box-shadow:inset 3px 0 0 rgba(255,77,106,.55); }
  .metric-label { grid-column:1/-1; color:${TOKENS.muted}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.14em; text-transform:uppercase; }
  .metric-value { font:900 28px "IBM Plex Mono", monospace; color:${TOKENS.text}; letter-spacing:-.03em; }
  .metric-delta { font:900 10px "IBM Plex Mono", monospace; }
  .metric-delta.pos { color:${TOKENS.pos}; }
  .metric-delta.neg { color:${TOKENS.neg}; }
  .metric-arc { grid-row:2/4; grid-column:2; width:76px; height:44px; }
  .metric-sub { grid-column:1; color:${TOKENS.muted}; font-size:10px; font-style:normal; line-height:1.4; }
  .ml-heatmap-v3-shell { display:grid; gap:10px; }
  .ml-heatmap-v3 { display:grid; grid-template-columns:110px repeat(var(--hm-cols), minmax(40px, 1fr)); gap:3px; overflow:auto; }
  .ml-heatmap-v3 b { min-height:32px; display:grid; place-items:center; color:${TOKENS.muted}; font:900 9px "IBM Plex Mono", monospace; text-transform:uppercase; letter-spacing:.08em; }
  .hm-row-label { justify-content:start !important; padding-left:8px; }
  .hm-hi { color:${TOKENS.signal} !important; }
  .ml-heatmap-v3 i { min-height:40px; border-radius:6px; display:grid; place-items:center; color:${TOKENS.text}; font:800 10px "IBM Plex Mono", monospace; font-style:normal; transition:opacity .12s, transform .12s, filter .12s; cursor:crosshair; }
  .ml-heatmap-v3 i:hover { transform:scale(1.06); filter:brightness(1.2); z-index:1; }
  .hm-dim { opacity:.18; }
  .hm-diag { color:${TOKENS.signal}; border:1px solid rgba(0,212,255,.2); }
  .hm-hover-tip { display:flex; align-items:center; gap:10px; padding:8px 12px; border-left:3px solid ${TOKENS.signal}; background:rgba(0,212,255,.06); border-radius:0 8px 8px 0; color:${TOKENS.secondary}; font:800 11px "IBM Plex Mono", monospace; }
  .hm-hover-tip strong { color:${TOKENS.text}; }
  .hm-hover-tip b { color:${TOKENS.signal}; }
  .hm-scale { display:grid; grid-template-columns:auto 1fr auto; gap:8px; align-items:center; color:${TOKENS.muted}; font:900 9px "IBM Plex Mono", monospace; }
  .hm-scale-pos, .hm-scale-div { height:6px; border-radius:999px; }
  .hm-scale-pos { background:linear-gradient(90deg, rgba(0,212,255,.05), rgba(0,212,255,.9)); }
  .hm-scale-div { background:linear-gradient(90deg, rgba(77,158,255,.8), rgba(255,255,255,.08), rgba(0,212,255,.8)); }
  .ml-network-v4 svg { width:100%; min-height:420px; }
  .ml-network-v4 text { fill:${TOKENS.secondary}; font-size:2.8px; font-family:"IBM Plex Mono", monospace; }
  .ml-quadrant-v4 { display:grid; gap:10px; }
  .ml-quadrant-v4 svg { width:100%; height:340px; border:1px solid ${TOKENS.ruleSoft}; border-radius:4px; background:${TOKENS.input}; }
  .quadrant-readout-v4 { display:flex; gap:18px; font:600 11px "IBM Plex Mono", monospace; color:${TOKENS.secondary}; }
  .quadrant-readout-v4 b { color:${TOKENS.text}; margin-left:6px; }
  .quadrant-readout-v4 b.neg { color:${TOKENS.neg}; }
  .quadrant-readout-v4 b.pos { color:${TOKENS.pos}; }
  .ml-quadrant { height:360px; position:relative; border:1px solid ${TOKENS.ruleSoft}; background:linear-gradient(90deg, rgba(255,77,106,.08) 0 50%, rgba(0,229,160,.08) 50% 100%); border-radius:10px; overflow:hidden; }
  .ml-quadrant:before, .ml-quadrant:after { content:""; position:absolute; background:${TOKENS.ruleSoft}; }
  .ml-quadrant:before { left:50%; top:0; bottom:0; width:1px; }
  .ml-quadrant:after { top:50%; left:0; right:0; height:1px; }
  .ml-quadrant i { position:absolute; width:18px; height:18px; margin:-9px; border-radius:99px; background:${TOKENS.signal}; box-shadow:0 0 34px rgba(0,212,255,.6); z-index:2; }
  .ml-quadrant span, .ml-quadrant strong { position:absolute; left:16px; color:${TOKENS.secondary}; }
  .ml-quadrant span { bottom:44px; }
  .ml-quadrant strong { bottom:18px; color:${TOKENS.text}; font-family:"IBM Plex Mono", monospace; }
  .q-axis { position:absolute; color:${TOKENS.muted}; font-size:10px; font-weight:900; letter-spacing:.12em; }
  .q-axis.vertical { left:12px; top:12px; }
  .q-axis.horizontal { right:12px; bottom:12px; }
  .ml-empty-v4 { min-height:160px; display:grid; place-items:center; text-align:center; gap:8px; border:1px dashed ${TOKENS.ruleSoft}; border-radius:4px; padding:24px; }
  .ml-empty-v4 b { color:${TOKENS.secondary}; font:600 12px "IBM Plex Sans Condensed", sans-serif; }
  .ml-empty-v4 span { color:${TOKENS.muted}; font-size:11px; max-width:420px; line-height:1.6; }
  .ml-empty-v3 { min-height:180px; display:grid; place-items:center; text-align:center; gap:10px; border:1px dashed ${TOKENS.rule}; border-radius:14px; padding:28px; }
  .empty-icon { width:46px; height:46px; border:1px solid ${TOKENS.rule}; border-radius:12px; background:${TOKENS.input}; display:grid; place-items:center; color:${TOKENS.muted}; margin:0 auto; }
  .ml-empty-v3 b { color:${TOKENS.secondary}; font-size:13px; }
  .ml-empty-v3 span { color:${TOKENS.muted}; font:800 10px "IBM Plex Mono", monospace; letter-spacing:.08em; line-height:1.7; max-width:580px; }
  .ml-toast-rack { position:fixed; right:22px; bottom:22px; z-index:500; display:flex; flex-direction:column-reverse; gap:8px; max-width:380px; }
  .ml-toast { min-height:44px; padding:0 10px 0 14px; border:1px solid ${TOKENS.rule}; border-radius:12px; background:rgba(7,8,10,.96); backdrop-filter:blur(18px); display:flex; align-items:center; gap:10px; color:${TOKENS.text}; font-size:12px; box-shadow:0 12px 40px rgba(0,0,0,.5); }
  .ml-toast-success { border-color:rgba(0,229,160,.35); }
  .ml-toast-warning { border-color:rgba(245,164,0,.4); }
  .ml-toast-error { border-color:rgba(255,77,106,.4); }
  .ml-toast-info { border-color:rgba(0,212,255,.35); }
  .toast-pip { width:7px; height:7px; border-radius:50%; flex-shrink:0; background:${TOKENS.signal}; }
  .ml-toast-success .toast-pip { background:${TOKENS.pos}; }
  .ml-toast-warning .toast-pip { background:${TOKENS.signal}; }
  .ml-toast-error .toast-pip { background:${TOKENS.neg}; }
  .toast-msg { flex:1; font-size:12px; }
  .ml-toast button { border:0; background:transparent; color:${TOKENS.muted}; font-size:18px; cursor:pointer; line-height:1; }
  .ml-export-overlay, .ml-curtain-overlay { position:fixed; inset:0; z-index:200; background:rgba(0,0,0,.78); backdrop-filter:blur(20px); display:grid; place-items:center; padding:24px; overflow:auto; }
  .ml-export-modal, .ml-curtain-panel { width:min(860px, calc(100vw - 48px)); max-height:calc(100dvh - 48px); overflow:auto; border:1px solid ${TOKENS.rule}; border-radius:20px; background:linear-gradient(180deg, ${TOKENS.raised}, ${TOKENS.panel}); box-shadow:0 40px 140px rgba(0,0,0,.8); }
  .ml-curtain-panel { width:min(1320px, calc(100vw - 56px)); }
  .ml-export-modal header, .ml-curtain-header { min-height:64px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; border-bottom:1px solid ${TOKENS.ruleSoft}; }
  .ml-export-modal header p, .ml-curtain-header p { margin:0; color:${TOKENS.signal}; font:900 9px "IBM Plex Mono", monospace; letter-spacing:.2em; }
  .ml-export-modal header h2, .ml-curtain-header h2 { margin:3px 0 0; font-size:17px; }
  .ml-export-modal header button, .ml-curtain-header button { width:34px; height:34px; border:1px solid ${TOKENS.rule}; border-radius:9px; background:${TOKENS.input}; color:${TOKENS.secondary}; display:grid; place-items:center; cursor:pointer; }
  .ml-export-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; padding:16px; }
  .ml-export-option { min-height:120px; text-align:left; border:1px solid ${TOKENS.rule}; border-radius:14px; background:${TOKENS.input}; color:${TOKENS.secondary}; padding:14px; display:grid; gap:6px; align-content:start; cursor:pointer; }
  .ml-export-option:hover { border-color:rgba(0,212,255,.45); background:rgba(0,212,255,.06); }
  .export-icon { color:${TOKENS.signal}; margin-bottom:2px; }
  .ml-export-option b { color:${TOKENS.text}; font-size:13px; }
  .ml-export-option span { font-size:11px; line-height:1.45; }
  .ml-export-modal textarea { display:block; width:calc(100% - 32px); height:180px; margin:0 16px 16px; border:1px solid ${TOKENS.rule}; border-radius:12px; background:#050507; color:${TOKENS.muted}; padding:12px; font:11px "IBM Plex Mono", monospace; resize:vertical; }
  .ml-curtain-body { padding:22px; }
  .ml-field-grid-v3 { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:14px; }
  .ml-field { display:grid; gap:7px; }
  .ml-field.wide { grid-column:span 2; }
  .ml-field span { color:${TOKENS.secondary}; font-size:11px; font-weight:750; }
  .ml-field input, .ml-field select { height:38px; border:1px solid ${TOKENS.rule}; background:${TOKENS.input}; color:${TOKENS.text}; border-radius:8px; padding:0 11px; outline:none; }
  .ml-field input:focus, .ml-field select:focus { border-color:${TOKENS.signal}; box-shadow:0 0 0 2px rgba(0,212,255,.12); }
  .ml-token-grid { display:flex; flex-wrap:wrap; gap:6px; }
  .ml-token-grid button, .ml-ticker-box button { height:30px; border:1px solid ${TOKENS.rule}; border-radius:7px; background:#101010; color:${TOKENS.secondary}; font-size:11px; font-weight:800; cursor:pointer; }
  .ml-token-grid button.active, .ml-ticker-box button { background:rgba(0,212,255,.1); color:${TOKENS.signal}; border-color:rgba(0,212,255,.42); }
  .ml-ticker-box { min-height:42px; border:1px solid ${TOKENS.rule}; border-radius:9px; background:${TOKENS.input}; display:flex; flex-wrap:wrap; align-items:center; gap:6px; padding:5px; position:relative; }
  .ml-ticker-box input { flex:1; min-width:130px; height:30px; border:0; background:transparent; box-shadow:none; padding:0 6px; color:${TOKENS.text}; outline:0; }
  .ml-ticker-box em { margin-left:6px; font-style:normal; color:${TOKENS.muted}; }
  .ml-ticker-menu { position:absolute; top:calc(100% + 6px); left:0; width:min(520px, 100%); border:1px solid ${TOKENS.rule}; border-radius:10px; background:#090909; padding:6px; z-index:30; box-shadow:0 20px 70px rgba(0,0,0,.55); }
  .ml-ticker-menu button { width:100%; height:42px; display:flex; justify-content:space-between; align-items:center; padding:0 10px; background:transparent; border-color:transparent; }
  .ml-ticker-menu small { color:${TOKENS.muted}; }
  .ticker-searching { display:block; padding:7px 10px; color:${TOKENS.muted}; font:600 10px "IBM Plex Mono", monospace; letter-spacing:.08em; text-transform:uppercase; }
  .ml-curtain-footer { min-height:64px; display:flex; align-items:center; justify-content:flex-end; gap:10px; padding:0 22px; border-top:1px solid ${TOKENS.ruleSoft}; }
  .ml-curtain-close, .ml-curtain-run { height:38px; border:1px solid ${TOKENS.rule}; background:${TOKENS.input}; color:${TOKENS.secondary}; border-radius:10px; padding:0 14px; font:800 11px "IBM Plex Mono", monospace; cursor:pointer; }
  .ml-curtain-run { border-color:rgba(0,212,255,.42); background:linear-gradient(135deg, rgba(0,212,255,.18), rgba(0,212,255,.06)); color:${TOKENS.signal}; padding:0 18px; font-weight:900; letter-spacing:.12em; display:flex; align-items:center; gap:8px; }
  .cinema-active .ml-dock { opacity:.22; }
  .ml-home-hero { min-height:70vh; display:grid; place-content:center; text-align:center; }
  .ml-home-hero p { color:${TOKENS.signal}; font:900 11px "IBM Plex Mono", monospace; letter-spacing:.24em; }
  .ml-home-hero h1 { margin:14px 0 10px; max-width:980px; font-family:"IBM Plex Sans Condensed", -apple-system, sans-serif; font-size:clamp(38px, 6vw, 76px); line-height:.95; letter-spacing:-.045em; }
  .ml-home-hero span { color:${TOKENS.secondary}; font-size:16px; line-height:1.7; max-width:780px; }
  .ml-home-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px,1fr)); gap:12px; }
  .ml-home-card { min-height:240px; display:flex; flex-direction:column; justify-content:space-between; border:1px solid ${TOKENS.rule}; border-radius:16px; background:linear-gradient(180deg, rgba(17,19,24,.95), rgba(7,8,10,.98)); padding:20px; color:${TOKENS.text}; text-decoration:none; transition:transform 160ms ease, border-color 160ms ease; }
  .ml-home-card:hover { transform:translateY(-6px); border-color:${TOKENS.signal}; }
  .ml-home-card small, .ml-home-card em { color:${TOKENS.signal}; font-family:"IBM Plex Mono", monospace; font-style:normal; }
  .ml-home-card h2 { margin:12px 0; font-size:22px; letter-spacing:-.02em; }
  .ml-home-card p { color:${TOKENS.secondary}; line-height:1.6; }
  @keyframes runIndeterminate { 0% { transform:translateX(-110%); } 100% { transform:translateX(280%); } }
  @media (max-width: 1100px) { .ml-topbar-kbd { display:none; } .ml-workspace-v3 { grid-template-columns:64px minmax(0,1fr); } .ml-minimap { display:none; } }
  @media (max-width: 900px) { .ml-v2-shell-v3 { padding-left:16px; padding-right:16px; } .ml-workspace-v3 { grid-template-columns:1fr; } .ml-dock { display:none; } .ml-field.wide { grid-column:span 1; } .ml-hero-v3 { align-items:flex-start; flex-direction:column; padding:28px; } .ml-export-grid { grid-template-columns:1fr; } .ml-topbar { overflow-x:auto; } .ml-topbar-actions span, .ml-topbar-kbd { display:none; } }
`;
