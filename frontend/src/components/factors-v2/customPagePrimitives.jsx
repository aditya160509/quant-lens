"use client";

import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useMutation } from "@tanstack/react-query";
import { Command } from "cmdk";
import toast from "react-hot-toast";
import { useDebounce } from "use-debounce";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Cell,
  Legend,
  ErrorBar,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, Camera, Check, CheckCircle2, ChevronDown, Copy, Database, Download, GripVertical, Info, Loader2, Maximize2, MessageSquare, Minimize2, Pencil, Play, Search, Send, X } from "lucide-react";
import { runFactorsV2Feature, searchFactorsV2Symbols } from "@/lib/api";
import { useFactorsV2AnnotationStore } from "@/stores/factorsV2AnnotationStore";
import { getFactorsV2Feature } from "./registry";

export const TOKENS = {
  page: "#050505",
  panel: "#0B0B0B",
  elevated: "#15120B",
  input: "#111111",
  active: "#1C1710",
  border: "#2E2618",
  borderSubtle: "#1C1710",
  grid: "#2A3548",
  accent: "#F5A400",
  accentMuted: "#C78600",
  accentGlow: "rgba(245,164,0,0.18)",
  text: "#F4F1EA",
  secondary: "#A8A29A",
  muted: "#6F675C",
  textFaint: "#6F675C",
  textDisabled: "#4A4238",
  green: "#22C55E",
  greenMuted: "rgba(34,197,94,0.1)",
  red: "#EF4444",
  redMuted: "rgba(239,68,68,0.1)",
  amber: "#F5A400",
  amberMuted: "rgba(245,164,0,0.12)",
  purple: "#8B5CF6",
  teal: "#14B8A6",
  tealMuted: "rgba(20,184,166,0.1)",
};

export const SERIES = ["#F5A400", "#22C55E", "#E8D18A", "#EF4444", "#14B8A6", "#8B5CF6", "#F97316", "#EC4899"];

const tickStyle = {
  fill: TOKENS.secondary,
  fontSize: 11,
  fontFamily: "JetBrains Mono, Fira Code, Consolas, monospace",
};

const axisProps = { tick: tickStyle, axisLine: false, tickLine: false };

const constraintDescriptions = {
  realtime_cap_monte_carlo: "Monte Carlo is capped in realtime mode to preserve interactive latency. Research Mode expands the simulation budget.",
  realtime_cap_dcc: "DCC-GARCH is capped by factor count in realtime. Research Mode enables the heavier covariance path.",
  realtime_cap_var: "VAR lag length and bootstrap depth are capped in realtime. Research Mode enables the larger stress-test path.",
  realtime_cap_pdf: "PDF output is capped by page count in realtime. Longer reports return async metadata.",
};

function numberLike(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const parsed = Number(value.replace(/[$,%]/g, "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function titleize(value) {
  return String(value ?? "").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatValue(value) {
  if (value == null || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "-";
    const abs = Math.abs(value);
    if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
    if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
    if (abs >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (abs > 0 && abs < 0.01) return value.toFixed(4);
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

const CustomTooltip = memo(function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">{label}</div>
      {payload.map((entry, index) => (
        <div className="tooltip-row" key={`${entry.dataKey}-${index}`}>
          <span>{entry.name || entry.dataKey}</span>
          <b style={{ color: entry.color }}>{formatValue(entry.value)}</b>
        </div>
      ))}
    </div>
  );
});

const ChartSyncContext = createContext(null);

function ChartSyncProvider({ children }) {
  const subscribers = useRef(new Set());
  const broadcast = useCallback((label) => {
    subscribers.current.forEach((listener) => listener(label));
  }, []);
  const subscribe = useCallback((listener) => {
    subscribers.current.add(listener);
    return () => subscribers.current.delete(listener);
  }, []);
  const value = useMemo(() => ({ broadcast, subscribe }), [broadcast, subscribe]);
  return <ChartSyncContext.Provider value={value}>{children}</ChartSyncContext.Provider>;
}

function useSyncedChart() {
  const context = useContext(ChartSyncContext);
  const [syncedLabel, setSyncedLabel] = useState(null);
  useEffect(() => {
    if (!context) return undefined;
    return context.subscribe(setSyncedLabel);
  }, [context]);
  const onMouseMove = useCallback((state) => {
    if (state?.activeLabel != null) context?.broadcast(state.activeLabel);
  }, [context]);
  const onMouseLeave = useCallback(() => context?.broadcast(null), [context]);
  return { syncedLabel, onMouseMove, onMouseLeave };
}

function AnimatedNumber({ value }) {
  const target = numberLike(value);
  const previous = useRef(null);
  const rafRef = useRef(0);
  const [display, setDisplay] = useState(target ?? value);
  useEffect(() => {
    if (target == null) {
      previous.current = null;
      return undefined;
    }
    const from = previous.current == null ? target : Number(previous.current);
    previous.current = target;
    if (from === target) {
      return undefined;
    }
    const start = performance.now();
    function tick(now) {
      const progress = Math.min((now - start) / 600, 1);
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplay(from + (target - from) * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    }
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, value]);
  return formatValue(target == null ? value : display);
}

function DeltaLabel({ delta, positiveDirection = "up" }) {
  const n = numberLike(delta);
  if (n == null) return <small>{delta}</small>;
  const good = positiveDirection === "down" ? n < 0 : n > 0;
  const color = n === 0 ? TOKENS.secondary : good ? TOKENS.green : TOKENS.red;
  const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "—";
  return <small className="delta-label" style={{ color }}><span>{arrow}</span>{formatValue(Math.abs(n))}</small>;
}

function RangeBar({ row }) {
  const pct = numberLike(row?.pct ?? row?.percentile ?? row?.rank_pct);
  if (pct == null) return null;
  const bounded = Math.max(0, Math.min(100, pct));
  const color = bounded >= 70 ? TOKENS.red : bounded >= 40 ? TOKENS.amber : TOKENS.green;
  return <div className="metric-range"><i style={{ width: `${bounded}%`, background: color }}><b style={{ background: color }} /></i></div>;
}

function Sparkline({ value, index }) {
  const numeric = numberLike(value) ?? 0;
  const points = Array.from({ length: 18 }, (_, i) => {
    const x = (i / 17) * 88;
    const y = 18 - (Math.sin(i / 2 + index) * 5 + numeric % 11) * 0.55 - i * 0.18;
    return `${x.toFixed(1)},${Math.max(3, Math.min(28, y)).toFixed(1)}`;
  }).join(" ");
  return (
    <svg className="metric-spark" viewBox="0 0 88 32" aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}

function rowsFrom(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    if (!value.length) return [];
    return typeof value[0] === "object" ? value : value.map((item, index) => ({ name: String(index + 1), value: item }));
  }
  if (typeof value !== "object") return [{ name: "Value", value }];
  const recordArrayKey = Object.keys(value).find((key) => Array.isArray(value[key]) && value[key].some((row) => row && typeof row === "object"));
  if (recordArrayKey) return value[recordArrayKey];
  const seriesKeys = Object.keys(value).filter((key) => Array.isArray(value[key]));
  if (seriesKeys.length) {
    const length = Math.max(...seriesKeys.map((key) => value[key].length));
    return Array.from({ length }, (_, index) => {
      const row = { index };
      for (const key of seriesKeys) row[key] = value[key][index];
      return row;
    });
  }
  return Object.entries(value).map(([key, item]) => (item && typeof item === "object" && !Array.isArray(item) ? { name: titleize(key), ...item } : { name: titleize(key), value: item }));
}

function copyRowsAsTsv(value) {
  const rows = rowsFrom(value);
  if (!rows.length || typeof navigator === "undefined") return;
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row || {})))];
  const tsv = [
    columns.join("\t"),
    ...rows.map((row) => columns.map((column) => row?.[column] ?? "").join("\t")),
  ].join("\n");
  navigator.clipboard?.writeText(tsv);
}

function categoryColor(category) {
  return {
    SIGNAL: TOKENS.accent,
    RISK: TOKENS.red,
    ACTION: TOKENS.green,
    QUESTION: TOKENS.amber,
  }[category || "QUESTION"] || TOKENS.amber;
}

function nearestDataAnchor(event, cardData) {
  const rows = rowsFrom(cardData);
  if (!rows.length) return null;
  const rect = event.currentTarget.getBoundingClientRect();
  const relX = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
  const index = Math.max(0, Math.min(rows.length - 1, Math.round(relX * (rows.length - 1))));
  const row = rows[index] || {};
  const keys = Object.keys(row);
  const xKey = keys.find((key) => /date|time|month|year|horizon|name|factor|component/i.test(key)) || keys[0];
  const yKey = keys.find((key) => key !== xKey && numberLike(row[key]) != null);
  return { index, key: xKey, x: row[xKey], y_key: yKey, y: yKey ? row[yKey] : null };
}

function clusterSortLabels(cells, labels) {
  if (labels.length < 3) return labels;
  const matrix = new Map();
  for (const cell of cells) {
    const row = String(cell.row);
    const col = String(cell.col);
    if (!matrix.has(row)) matrix.set(row, new Map());
    matrix.get(row).set(col, numberLike(cell.value) ?? 0);
  }
  const visited = new Set([labels[0]]);
  const order = [labels[0]];
  while (order.length < labels.length) {
    const last = order[order.length - 1];
    let nearest = null;
    let bestDistance = Infinity;
    for (const candidate of labels) {
      if (visited.has(candidate)) continue;
      const correlation = Math.abs(matrix.get(last)?.get(candidate) ?? matrix.get(candidate)?.get(last) ?? 0);
      const distance = 1 - correlation;
      if (distance < bestDistance) {
        bestDistance = distance;
        nearest = candidate;
      }
    }
    if (!nearest) break;
    visited.add(nearest);
    order.push(nearest);
  }
  return order.length === labels.length ? order : labels;
}

async function captureElementAsPng(sectionId) {
  const node = document.getElementById(sectionId);
  if (!node) return;
  try {
    const { default: html2canvas } = await import("html2canvas");
    const canvas = await html2canvas(node, { backgroundColor: TOKENS.panel, scale: 2 });
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      try {
        if (navigator.clipboard && window.ClipboardItem) {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
          return;
        }
      } catch {
        // Fall through to download.
      }
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `quant360_${sectionId}.png`;
      link.click();
      URL.revokeObjectURL(link.href);
    });
  } catch (error) {
    console.error("Chart capture failed", error);
  }
}

function inferKeys(rows, config = {}) {
  const first = rows.find((row) => row && typeof row === "object") || {};
  const keys = Object.keys(first);
  const xKey = config.xKey || keys.find((key) => /date|time|year|month|horizon|aum|risk|vol|name|factor|regime|sector|component|scenario|index/i.test(key)) || keys[0] || "name";
  const yKeys = config.yKeys?.length ? config.yKeys : keys.filter((key) => key !== xKey && rows.some((row) => numberLike(row?.[key]) != null)).slice(0, 8);
  return { xKey, yKeys: yKeys.length ? yKeys : ["value"] };
}

function parseFieldValue(field, value) {
  if (field.type === "number") {
    if (value == null || String(value).trim() === "") return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  if (field.type === "textarea") {
    const trimmed = String(value || "").trim();
    if (!trimmed) return undefined;
    try {
      return JSON.parse(trimmed);
    } catch {
      return trimmed;
    }
  }
  if (value === "true") return true;
  if (value === "false") return false;
  if (typeof value === "string" && value.includes(",") && !["fund_name", "custom_narrative", "fund_disclosures"].includes(field.key)) {
    return value.split(",").map((part) => {
      const clean = part.trim();
      const asNumber = Number(clean);
      return Number.isFinite(asNumber) ? asNumber : clean;
    });
  }
  return value;
}

function initialForm(feature) {
  const state = {};
  for (const field of feature.fields || []) {
    const value = feature.defaults?.[field.key];
    state[field.key] = Array.isArray(value) ? value.join(",") : value ?? "";
  }
  return state;
}

function payloadFromForm(feature, form) {
  const payload = {};
  for (const field of feature.fields || []) {
    const parsed = parseFieldValue(field, form[field.key]);
    if (parsed !== undefined && parsed !== "") payload[field.key] = parsed;
  }
  return payload;
}

function featureNarrative(feature) {
  const map = {
    "01": "valuation spread · factor PE ratio · implied return",
    "02": "portfolio tilt · unintended exposure · DDQ disclosure",
    "03": "active return · attribution · selection vs harvest",
    "04": "regime probability · transition risk · timing signal",
    "05": "IC decay · half-life · rebalance cost-benefit",
    "06": "crowding pct · crash probability · deleveraging risk",
    "07": "net backtest · implementation shortfall · capacity",
    "08": "factor covariance · crisis correlation · condition number",
    "09": "capacity ceiling · slippage by AUM · liquidation time",
    "10": "factor QP optimizer · robust weights · FAP diagnostic",
    "11": "stress PnL · reverse scenario · contagion IRF",
    "12": "factor DNA · purity score · archetype classifier",
    "13": "IC drift · CUSUM break · crowding velocity · health score",
    "14": "ILPA DDQ · PDF export · AIMA cross-reference",
  };
  return map[feature?.id] || feature?.description || "";
}

function inferSectionRank(section, index) {
  if (section.rank) return section.rank;
  if (index === 0) return "primary";
  if (section.chartType === "table" || section.chartType === "textBlock" || section.chartType === "pdfDownload" || section.source === "meta") return "contextual";
  return "supporting";
}

function inferComputeCost(section, rank) {
  if (section.computeCost) return section.computeCost;
  const haystack = `${section.id} ${section.title} ${section.dataKey}`.toLowerCase();
  if (/monte|dcc|bootstrap|robust|garch|normal-vs-crisis|covariance|var|pdf|report/.test(haystack)) return 4;
  if (section.chartType === "heatmap" || section.chartType === "normalVsCrisis" || section.chartType === "backtestSplit" || section.chartType === "radar") return 3;
  if (rank === "contextual") return 1;
  return 2;
}

function inferDefaultSelected(section, computeCost) {
  if (section.defaultSelected != null) return section.defaultSelected;
  const haystack = `${section.id} ${section.title} ${section.dataKey}`.toLowerCase();
  if (computeCost >= 5) return false;
  if (/monte-carlo|rolling-correlation|historical-analog|robust-vs-standard|crowding-league|deleveraging-risk|timing-regression/.test(haystack)) return false;
  return true;
}

function buildSectionDescription(feature, section, rank) {
  if (section.description) return section.description;
  const context = featureNarrative(feature);
  const title = section.title || titleize(section.id);
  const source = `${section.source || "response"}.${section.dataKey || "data"}`;
  if (rank === "primary") {
    return `${title} is the primary decision surface for ${context}. It reads ${source} and should be reviewed first because it anchors the feature's headline recommendation.`;
  }
  if (rank === "contextual") {
    return `${title} is the audit/reference layer for ${context}. It exposes ${source} so the headline outputs can be traced back to exact rows, parameters, or report artifacts.`;
  }
  if (section.chartType === "heatmap") return `${title} maps pairwise or cross-sectional intensity for ${context}. Darker cells identify where concentration, correlation, or regime dependence requires drill-down.`;
  if (section.chartType === "waterfall") return `${title} decomposes total impact into additive components for ${context}, making the running contribution chain visible from first driver to final result.`;
  if (section.chartType === "line" || section.chartType === "area" || section.chartType === "stackedArea") return `${title} shows how ${context} evolves through time. Breaks, crossings, and persistent trends are the signals to investigate.`;
  if (section.chartType === "gauge" || section.chartType === "summaryGauges") return `${title} compresses the feature's top-line state into percentile-style readings so elevated, normal, and benign conditions are immediately visible.`;
  return `${title} supports ${context} by rendering ${source} as a ${titleize(section.chartType || "output")} for fast review and export.`;
}

function buildSectionInsight(feature, section, rank) {
  if (section.insight !== undefined) return section.insight;
  const title = section.title || titleize(section.id);
  if (rank === "contextual") return null;
  const lower = `${section.id} ${title}`.toLowerCase();
  if (/exposure|tilt/.test(lower)) return "Treat exposures beyond mandate thresholds as disclosure items first and optimization inputs second; the linked heatmaps and tables identify which holdings create the tilt.";
  if (/waterfall|attribution|contribution/.test(lower)) return "The largest signed component explains the economic source of the result; persistent positives indicate skill, while one-off negatives should be tied to timing or regime context.";
  if (/regime|transition/.test(lower)) return "Act on probability changes, not hard labels: rising stress or transition probability should lower confidence in factor persistence and widen risk assumptions.";
  if (/decay|half-life|icir|rebalancing/.test(lower)) return "Use the half-life and cost peak together: rebalance before signal decay dominates, but not so frequently that implementation shortfall consumes the premium.";
  if (/crowding|crash|deleveraging/.test(lower)) return "Elevated crowding is a sizing and exit-liquidity warning; link it to covariance and stress outputs before increasing exposure.";
  if (/capacity|slippage|aum|liquidate/.test(lower)) return "The investable capacity is where net alpha, liquidity, and liquidation time remain jointly acceptable; do not size to gross alpha alone.";
  if (/frontier|allocation|optimizer|constraint|risk budget/.test(lower)) return "Use the selected point only if the constraint table and risk budget agree; otherwise the optimizer is exposing a hidden model-alignment problem.";
  if (/stress|scenario|contagion|reverse/.test(lower)) return "The relevant risk is the path to breach, not the average loss; use reverse stress and contagion outputs to identify what must be hedged first.";
  if (/dna|classifier|purity|anatomy/.test(lower)) return "A durable factor should score well on persistence, independence, and purity simultaneously; weak classification confidence means the signal needs more evidence before allocator use.";
  if (/health|alert|structural|velocity/.test(lower)) return "Escalate deteriorating signals before realized PnL fails; structural breaks and crowding acceleration are leading indicators, not post-mortem diagnostics.";
  if (/report|pdf|audit|ddq/.test(lower)) return "This output is designed for reuse in allocator material; verify audit metadata and section coverage before exporting or sharing.";
  return `${title} should be interpreted with the primary output and linked sections; use it to confirm whether the headline result is broad-based, persistent, and implementation-ready.`;
}

function enrichSections(sections, feature) {
  const base = sections.map((section, index) => {
    const rank = inferSectionRank(section, index);
    const computeCost = inferComputeCost(section, rank);
    return {
      ...section,
      rank,
      computeCost,
      defaultSelected: inferDefaultSelected(section, computeCost),
      description: buildSectionDescription(feature, section, rank),
      insight: buildSectionInsight(feature, section, rank),
    };
  });
  return base.map((section, index) => {
    const primary = base.find((item) => item.rank === "primary" && item.id !== section.id);
    const firstSupport = base.find((item) => item.rank === "supporting" && item.id !== section.id);
    const contextual = base.find((item) => item.rank === "contextual" && item.id !== section.id);
    const linkedSections = section.linkedSections || [primary?.id, section.rank === "primary" ? firstSupport?.id : contextual?.id].filter(Boolean).slice(0, 2);
    return { ...section, linkedSections };
  });
}

function buildOutputManifest(sections) {
  return sections.map((section, index) => ({
    id: section.id,
    label: section.title,
    description: section.description || `${titleize(section.chartType)} output from ${section.source || "auto"}.${section.dataKey}`,
    dependsOn: section.dependsOn || ["compute_mode", section.dataKey].filter(Boolean),
    computeCost: section.computeCost || Math.min(5, Math.max(1, Math.ceil((index + 1) / 2))),
    defaultSelected: section.defaultSelected !== false,
  }));
}

function orderedSections(sections, selectedOutputIds) {
  const byId = new Map(sections.map((section) => [section.id, section]));
  return selectedOutputIds.map((id) => byId.get(id)).filter(Boolean);
}

function decorateSection(section, index, ordered) {
  const fallbackLinks = ordered
    .filter((item) => item.id !== section.id)
    .slice(Math.max(0, index - 1), Math.max(0, index - 1) + 2)
    .map((item) => item.id);
  return {
    ...section,
    linkedSections: (section.linkedSections?.length ? section.linkedSections : fallbackLinks).filter((id) => id !== section.id).slice(0, 2),
  };
}

function moveItem(ids, fromId, toId) {
  if (!fromId || !toId || fromId === toId) return ids;
  const next = ids.filter((id) => id !== fromId);
  const targetIndex = next.indexOf(toId);
  if (targetIndex < 0) return ids;
  next.splice(targetIndex, 0, fromId);
  return next;
}

function OutputConfigurator({ manifest, selectedOutputIds, setSelectedOutputIds, profiles, profileName, setProfileName, saveProfile, loadProfile }) {
  const [open, setOpen] = useState(false);
  const [draggingId, setDraggingId] = useState(null);
  const visibleManifest = [
    ...selectedOutputIds.map((id) => manifest.find((item) => item.id === id)).filter(Boolean),
    ...manifest.filter((item) => !selectedOutputIds.includes(item.id)),
  ];
  return (
    <section className="output-config-v2">
      <button className="output-config-header" onClick={() => setOpen((current) => !current)} type="button">
        <span>Output book</span>
        <em>{selectedOutputIds.length}/{manifest.length} selected</em>
        <div className="config-profile-tools">
          <select aria-label="Saved output profiles" onChange={(event) => loadProfile(event.target.value)} onClick={(event) => event.stopPropagation()} value="">
            <option value="">Load profile</option>
            {profiles.map((profile) => <option key={profile.name} value={profile.name}>{profile.name}</option>)}
          </select>
        </div>
        <ChevronDown size={13} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 200ms ease" }} />
      </button>
      {open ? (
        <div className="output-config-body">
          <div className="output-config-actions">
            <button onClick={() => setSelectedOutputIds(manifest.map((item) => item.id))} type="button">All</button>
            <button onClick={() => setSelectedOutputIds([])} type="button">None</button>
            <input aria-label="Output profile name" placeholder="Save as..." value={profileName} onChange={(event) => setProfileName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") saveProfile(); }} />
            <button onClick={saveProfile} type="button">Save</button>
          </div>
          <div className="output-config-list">
            {visibleManifest.map((item) => {
              const selected = selectedOutputIds.includes(item.id);
              return (
                <div
                  className={`config-row ${selected ? "on" : ""}`}
                  draggable={selected}
                  key={item.id}
                  onClick={() => setSelectedOutputIds((current) => selected ? current.filter((id) => id !== item.id) : [...current, item.id])}
                  onDragOver={(event) => event.preventDefault()}
                  onDragStart={() => setDraggingId(item.id)}
                  onDrop={(event) => {
                    event.stopPropagation();
                    setSelectedOutputIds((current) => moveItem(current, draggingId, item.id));
                  }}
                >
                  <i className={`config-check ${selected ? "on" : ""}`}>{selected ? <Check size={10} /> : null}</i>
                  <GripVertical className="drag-handle" size={13} />
                  <span className="config-name" title={item.description}>{item.label}</span>
                  <span className={`config-cost cost-${item.computeCost}`} title={`Compute cost ${item.computeCost}`}>{item.computeCost}</span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function FieldControl({ field, value, onChange, compact = false }) {
  const controlId = `f2-${field.key}-${compact ? "quick" : "full"}`;
  return (
    <label className={`${field.type === "textarea" ? "field wide" : "field"} ${compact ? "compact" : ""}`} htmlFor={controlId}>
      <span>{field.label}</span>
      {field.type === "select" ? (
        <select id={controlId} value={String(value)} onChange={(event) => onChange(event.target.value)}>
          {(field.options || []).map((option) => <option key={String(option)} value={String(option)}>{formatValue(option)}</option>)}
        </select>
      ) : field.type === "textarea" ? (
        <textarea id={controlId} placeholder={field.placeholder || "Optional JSON payload"} value={value} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input id={controlId} placeholder={field.placeholder || ""} type={field.type === "number" ? "number" : "text"} value={value} onChange={(event) => onChange(event.target.value)} />
      )}
      {field.helper && !compact ? <small>{field.helper}</small> : null}
    </label>
  );
}

function fieldGroupFor(field) {
  const key = String(field.key || "").toLowerCase();
  if (["compute_mode", "as_of_date", "start_date", "end_date", "window_days", "lookback_days", "horizon_days"].some((token) => key.includes(token))) return "Run window";
  if (["universe", "portfolio", "benchmark", "factor", "factors", "ticker", "asset", "sector"].some((token) => key.includes(token))) return "Universe and signal";
  if (["method", "model", "estimator", "scenario", "regime", "rebalance", "frequency", "optimizer"].some((token) => key.includes(token))) return "Model controls";
  if (["cost", "aum", "adv", "capacity", "threshold", "confidence", "bootstrap", "simulation"].some((token) => key.includes(token))) return "Constraints";
  return "Parameters";
}

const tickerFallbacks = [
  ["SPY", "SPDR S&P 500 ETF"],
  ["QQQ", "Invesco Nasdaq 100 ETF"],
  ["IWM", "iShares Russell 2000 ETF"],
  ["DIA", "SPDR Dow Jones ETF"],
  ["TLT", "iShares 20+ Year Treasury ETF"],
  ["GLD", "SPDR Gold Shares"],
  ["AAPL", "Apple Inc."],
  ["MSFT", "Microsoft Corp."],
  ["NVDA", "NVIDIA Corp."],
  ["AMZN", "Amazon.com Inc."],
  ["META", "Meta Platforms Inc."],
  ["GOOGL", "Alphabet Inc."],
  ["TSLA", "Tesla Inc."],
  ["AMD", "Advanced Micro Devices"],
  ["XLF", "Financial Select Sector SPDR"],
  ["XLK", "Technology Select Sector SPDR"],
  ["XLE", "Energy Select Sector SPDR"],
  ["XLV", "Health Care Select Sector SPDR"],
];

function TickerSearchInput({ value, onChange, onCommit, placeholder }) {
  const [query, setQuery] = useState(String(value || ""));
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setQuery(String(value || ""));
  }, [value]);

  useEffect(() => {
    let active = true;
    const clean = query.trim();
    if (clean.length < 1) {
      setResults([]);
      setLoading(false);
      return undefined;
    }
    const timer = window.setTimeout(async () => {
      const needle = clean.toUpperCase();
      const fallback = tickerFallbacks
        .filter(([symbol, name]) => symbol.includes(needle) || name.toUpperCase().includes(needle))
        .slice(0, 7)
        .map(([symbol, name]) => ({ symbol, name, asset_type: "equity", source: "fallback" }));
      setLoading(true);
      try {
        const response = await searchFactorsV2Symbols(clean, { limit: 9 });
        if (!active) return;
        const apiRows = Array.isArray(response?.symbols) ? response.symbols : [];
        setResults(apiRows.length ? apiRows : fallback);
      } catch {
        if (active) setResults(fallback);
      } finally {
        if (active) setLoading(false);
      }
    }, 120);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  function commit(symbol) {
    setQuery(symbol);
    onChange(symbol);
    onCommit?.(symbol);
    setOpen(false);
  }

  return (
    <div className="ticker-search">
      <Search size={13} />
      <input
        value={query}
        placeholder={placeholder}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          const next = event.target.value.toUpperCase();
          setQuery(next);
          onChange(next);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && results.length ? (
        <div className="ticker-results">
          {results.map((item) => (
            <button key={item.symbol} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => commit(item.symbol)}>
              <b>{item.symbol}</b>
              <span>{item.name}</span>
              <em>{[item.asset_type, item.sector || item.industry, item.last_price != null ? formatValue(item.last_price) : null].filter(Boolean).join(" · ")}</em>
            </button>
          ))}
        </div>
      ) : open && loading ? (
        <div className="ticker-results"><div className="ticker-loading">Searching local universe...</div></div>
      ) : null}
    </div>
  );
}

function numericPresets(field, raw) {
  if (Array.isArray(field.presets)) return field.presets;
  const key = String(field.key || "").toLowerCase();
  if (/window|lookback|history|estimation/.test(key)) return [126, 252, 504, 756, 1260, 2520];
  if (/threshold|percentile|confidence/.test(key)) return [25, 50, 70, 80, 95];
  if (/bps|cost/.test(key)) return [0, 5, 8, 12, 25];
  if (/aum/.test(key)) return [10000000, 100000000, 1000000000, 2500000000];
  if (/participation|cap|turnover|loss|penalty|lambda/.test(key)) return [0.05, 0.1, 0.15, 0.25, 0.5];
  if (/samples|simulation|points|tickers/.test(key)) return [50, 100, 160, 250, 500];
  return raw ? [raw / 2, raw, raw * 2].filter((item, index, arr) => Number.isFinite(item) && arr.indexOf(item) === index) : [];
}

function stepNumber(field, value, direction) {
  const raw = numberLike(value) ?? 0;
  const step = numberLike(field.step) ?? (/participation|turnover|loss|penalty|lambda/.test(String(field.key || "").toLowerCase()) ? 0.01 : 1);
  const min = field.min != null ? Number(field.min) : -Infinity;
  const max = field.max != null ? Number(field.max) : Infinity;
  const next = Math.max(min, Math.min(max, raw + step * direction));
  return Number.isInteger(step) ? String(Math.round(next)) : String(Number(next.toFixed(4)));
}

function tokenOptionsFor(field) {
  if (field.options?.length) return field.options;
  const key = String(field.key || "").toLowerCase();
  if (/factor|signal|metric/.test(key)) return ["value_pb", "momentum_12_1", "quality_roe", "low_vol", "size", "investment", "profitability"];
  if (/horizon/.test(key)) return [1, 5, 10, 21, 42, 63, 126, 252];
  if (/section/.test(key)) return ["exposures", "attribution", "crowding", "capacity", "stress", "health", "ddq"];
  return [];
}

function TokenInput({ field, value, onChange }) {
  const selected = String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
  const [draft, setDraft] = useState("");
  const options = tokenOptionsFor(field).filter((option) => !selected.includes(String(option)));
  const commit = (item) => {
    const clean = String(item || "").trim();
    if (!clean || selected.includes(clean)) return;
    onChange([...selected, clean].join(","));
    setDraft("");
  };
  const remove = (item) => onChange(selected.filter((current) => current !== item).join(","));
  return (
    <div className="token-field">
      <div className="token-list">
        {selected.map((item) => (
          <button key={item} type="button" onClick={() => remove(item)}>
            {formatValue(item)} <X size={10} />
          </button>
        ))}
        <input
          value={draft}
          placeholder={selected.length ? "Add..." : field.placeholder || "Type and Enter"}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              commit(draft);
            }
            if (event.key === "Backspace" && !draft && selected.length) remove(selected[selected.length - 1]);
          }}
        />
      </div>
      {options.length ? (
        <div className="pro-mini-chips">
          {options.slice(0, 8).map((option) => <button key={String(option)} type="button" onClick={() => commit(option)}>{formatValue(option)}</button>)}
        </div>
      ) : null}
    </div>
  );
}

function MultiTickerInput({ value, onChange, placeholder }) {
  const selected = String(value || "").split(",").map((item) => item.trim().toUpperCase()).filter(Boolean);
  const [draft, setDraft] = useState("");
  const add = (symbol) => {
    const clean = String(symbol || "").trim().toUpperCase();
    if (!clean || selected.includes(clean)) return;
    onChange([...selected, clean].join(","));
    setDraft("");
  };
  const remove = (symbol) => onChange(selected.filter((item) => item !== symbol).join(","));
  return (
    <div className="multi-ticker">
      <div className="multi-ticker-strip">
        {selected.map((symbol) => (
          <button key={symbol} type="button" onClick={() => remove(symbol)}>
            <b>{symbol}</b><X size={10} />
          </button>
        ))}
        <TickerSearchInput value={draft} onChange={setDraft} onCommit={add} placeholder={selected.length ? "Add ticker..." : placeholder} />
      </div>
    </div>
  );
}

function parseHoldings(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    if (Array.isArray(parsed) && parsed.length) {
      return parsed.map((row) => ({ ticker: String(row.ticker || row.symbol || "").toUpperCase(), weight: numberLike(row.weight) ?? 0 })).filter((row) => row.ticker);
    }
  } catch {
    // Fall through to defaults.
  }
  return [{ ticker: "SPY", weight: 0.5 }, { ticker: "QQQ", weight: 0.5 }];
}

function HoldingsInput({ value, onChange }) {
  const rows = useMemo(() => parseHoldings(value), [value]);
  const commitRows = (nextRows) => onChange(JSON.stringify(nextRows.filter((row) => row.ticker).map((row) => ({ ticker: row.ticker.toUpperCase(), weight: Number(row.weight) || 0 }))));
  const update = (index, patch) => commitRows(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  return (
    <div className="portfolio-input">
      <div className="portfolio-head"><span>Ticker</span><span>Weight</span><span /></div>
      {rows.map((row, index) => (
        <div className="portfolio-row" key={`${row.ticker}-${index}`}>
          <TickerSearchInput value={row.ticker} onChange={(ticker) => update(index, { ticker })} placeholder="Search ticker..." />
          <input className="pro-number-input" type="number" step="0.01" value={row.weight} onChange={(event) => update(index, { weight: event.target.value })} />
          <button type="button" onClick={() => commitRows(rows.filter((_, rowIndex) => rowIndex !== index))}><X size={13} /></button>
        </div>
      ))}
      <div className="portfolio-actions">
        <button type="button" onClick={() => commitRows([...rows, { ticker: "", weight: 0 }])}>Add line</button>
        <button type="button" onClick={() => commitRows(rows.map((row) => ({ ...row, weight: Number((1 / Math.max(1, rows.length)).toFixed(4)) })))}>Equal weight</button>
      </div>
    </div>
  );
}

function ProFormField({ field, value, onChange }) {
  const numeric = field.type === "number";
  const options = field.options || [];
  const key = String(field.key || "").toLowerCase();
  const isTickerField = field.inputType === "ticker" || /(^ticker$|_ticker$|ticker_symbol|benchmark|symbol|asset)/.test(key);
  const isMultiTickerField = field.inputType === "multiTicker" || /custom_universe_tickers|comparison_portfolios|ticker_list/.test(key);
  const isTokenField = field.type === "tokens" || field.inputType === "tokens" || field.inputType === "multiFactor" || (typeof value === "string" && value.includes(",") && /factor|horizon|metric|section|signal/.test(key));
  if (isMultiTickerField) {
    return (
      <div className="pro-field pro-field-wide">
        <label className="pro-field-label">{field.label}</label>
        <MultiTickerInput value={value} onChange={onChange} placeholder={field.placeholder || "Search and add tickers..."} />
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (field.inputType === "holdings" || key === "holdings" || /portfolio_holdings/.test(key)) {
    return (
      <div className="pro-field pro-field-wide">
        <label className="pro-field-label">{field.label}</label>
        <HoldingsInput value={value} onChange={onChange} />
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (isTokenField) {
    return (
      <div className="pro-field">
        <label className="pro-field-label">{field.label}</label>
        <TokenInput field={field} value={value} onChange={onChange} />
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (isTickerField) {
    return (
      <div className="pro-field">
        <label className="pro-field-label">{field.label}</label>
        <TickerSearchInput value={value} onChange={onChange} placeholder={`Search ${field.label}...`} />
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (options.length > 0 && options.length <= 5) {
    return (
      <div className="pro-field">
        <label className="pro-field-label">{field.label}</label>
        <div className="pro-chips">
          {options.map((option) => (
            <button className={String(value) === String(option) ? "active" : ""} key={String(option)} onClick={() => onChange(String(option))} type="button">
              {formatValue(option)}
            </button>
          ))}
        </div>
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (options.length > 5) {
    return (
      <div className="pro-field">
        <label className="pro-field-label">{field.label}</label>
        <select className="pro-select" value={String(value)} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => <option key={String(option)} value={String(option)}>{formatValue(option)}</option>)}
        </select>
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (numeric) {
    const raw = numberLike(value) ?? numberLike(field.default) ?? 0;
    const min = field.min ?? (raw >= 0 ? 0 : Math.floor(raw * 2));
    const max = field.max ?? Math.max(Number(min) + 1, raw * 2 || 100);
    const presets = numericPresets(field, raw).filter((item) => numberLike(item) != null).slice(0, 6);
    return (
      <div className="pro-field pro-field-number">
        <label className="pro-field-label">{field.label}<span className="pro-range-value">{formatValue(raw)}</span></label>
        <div className="pro-number-shell">
          <input className="pro-number-input" min={min} max={max} step={field.step || 1} type="number" value={value} onChange={(event) => onChange(event.target.value)} />
          <div className="pro-stepper">
            <button type="button" onClick={() => onChange(stepNumber(field, value, 1))}>+</button>
            <button type="button" onClick={() => onChange(stepNumber(field, value, -1))}>−</button>
          </div>
        </div>
        {presets.length ? (
          <div className="pro-mini-chips">
            {presets.map((preset) => <button key={String(preset)} type="button" onClick={() => onChange(String(preset))}>{formatValue(preset)}</button>)}
          </div>
        ) : null}
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  if (field.type === "textarea") {
    return (
      <div className="pro-field pro-field-wide">
        <label className="pro-field-label">{field.label}</label>
        <textarea className="pro-textarea" placeholder={field.placeholder || "Optional JSON"} value={value} onChange={(event) => onChange(event.target.value)} />
        {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
      </div>
    );
  }
  return (
    <div className="pro-field">
      <label className="pro-field-label">{field.label}</label>
      <input className="pro-input" placeholder={field.placeholder || ""} type="text" value={value} onChange={(event) => onChange(event.target.value)} />
      {field.helper ? <span className="pro-field-helper">{field.helper}</span> : null}
    </div>
  );
}

function GroupedInputForm({ feature, form, onChange }) {
  const groups = useMemo(() => {
    const next = new Map();
    (feature.fields || []).forEach((field) => {
      const group = field.group || fieldGroupFor(field);
      next.set(group, [...(next.get(group) || []), field]);
    });
    return [...next.entries()];
  }, [feature]);
  return (
    <div className="pro-form">
      {groups.map(([group, fields]) => (
        <section className="pro-form-group" key={group}>
          <div className="pro-form-label">{group}</div>
          <div className="pro-form-fields">
            {fields.map((field) => (
              <ProFormField field={field} key={field.key} value={form[field.key]} onChange={(value) => onChange(field.key, value)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function pickData(response, section) {
  if (!response) return null;
  const keys = [section.dataKey, ...(section.fallbackKeys || [])].filter(Boolean);
  if (section.source === "summary") return response.summary_cards || null;
  if (section.source === "alerts") return response.alerts || null;
  for (const source of [section.source, "charts", "tables", "meta", "summary_cards"].filter(Boolean)) {
    const container = source === "summary_cards" ? { summary_cards: response.summary_cards } : response[source];
    if (!container) continue;
    for (const key of keys) {
      if (container[key] != null) return container[key];
    }
  }
  return null;
}

function EmptySection({ response, section }) {
  if (!response) {
    return (
      <div className="f2-empty-minimal">
        <span className="empty-status">◌</span>
        <span>Awaiting run</span>
      </div>
    );
  }
  const available = response
    ? ["charts", "tables", "meta"].flatMap((source) => Object.keys(response[source] || {}).map((key) => `${source}.${key}`)).slice(0, 6)
    : [];
  return (
    <div className="f2-empty-minimal missing">
      <span className="empty-status">✕</span>
      <span>{section.source || "data"}.{section.dataKey} not returned</span>
      {available.length ? <span className="empty-available">available: {available.join(" · ")}</span> : null}
    </div>
  );
}

function generateInsight(section, data) {
  if (section.rank === "contextual") return null;
  const rows = rowsFrom(data);
  if (!rows.length) return null;
  const numeric = rows.flatMap((row) => Object.entries(row || {})
    .map(([key, value]) => ({ key, value: numberLike(value), label: row.label || row.name || row.factor || row.component || row.regime || key }))
    .filter((item) => item.value != null));
  if (section.chartType === "waterfall") {
    const top = [...numeric].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0];
    if (!top) return null;
    return `${titleize(top.label)}: ${top.value >= 0 ? "+" : ""}${formatValue(top.value)} · ${top.value >= 0 ? "largest contributor" : "largest drag"}`;
  }
  if (section.chartType === "gauge" || section.chartType === "summaryGauges") {
    const first = rows[0] || {};
    const value = numberLike(first.value ?? first.score ?? first.percentile ?? first.current);
    if (value == null) return null;
    const label = first.label || first.name || section.title;
    if (value >= 80) return `${label}: ${value.toFixed(0)}th pct · ELEVATED`;
    if (value >= 60) return `${label}: ${value.toFixed(0)}th pct · WATCH`;
    if (value <= 25) return `${label}: ${value.toFixed(0)}th pct · LOW`;
    return `${label}: ${value.toFixed(0)}th pct · NORMAL`;
  }
  if (section.chartType === "table") {
    const top = [...numeric].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0];
    return top ? `${rows.length} rows · largest: ${titleize(top.label)} ${formatValue(top.value)}` : `${rows.length} rows returned`;
  }
  if (["line", "area", "stackedArea"].includes(section.chartType)) {
    const firstRow = rows[0] || {};
    const lastRow = rows[rows.length - 1] || {};
    const key = Object.keys(lastRow).find((candidate) => candidate !== "date" && candidate !== "name" && numberLike(lastRow[candidate]) != null);
    const start = numberLike(firstRow[key]);
    const end = numberLike(lastRow[key]);
    if (start == null || end == null) return null;
    const change = ((end - start) / Math.abs(start || 1)) * 100;
    return `${end >= start ? "UP" : "DOWN"} ${change >= 0 ? "+" : ""}${change.toFixed(1)}% · latest ${formatValue(end)}`;
  }
  if (section.chartType === "heatmap") {
    const top = [...numeric].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0];
    return top ? `Strongest cell: ${titleize(top.label)} ${formatValue(top.value)}` : null;
  }
  if (numeric.length) {
    const top = [...numeric].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0];
    return `${titleize(top.label)} ${formatValue(top.value)} · top driver`;
  }
  return null;
}

function MetricDeck({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 8), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "summary_cards" }} />;
  return (
    <div className="metric-deck">
      {rows.map((row, index) => {
        const label = row.label || row.title || row.name || row.metric || `Metric ${index + 1}`;
        const value = row.value ?? row.score ?? row.percentile ?? row.current ?? row.amount;
        return (
          <div className="metric-card" key={`${label}-${index}`}>
            <span>{label}</span>
            <strong className="mono"><AnimatedNumber value={value} /></strong>
            {row.delta != null ? <DeltaLabel delta={row.delta} positiveDirection={config.positiveDirection || row.positiveDirection || "up"} /> : row.subtitle || row.description ? <small>{row.subtitle || row.description}</small> : null}
            <RangeBar row={row} />
            <Sparkline index={index} value={value} />
          </div>
        );
      })}
    </div>
  );
}

function polarToCartesian(cx, cy, r, angle) {
  const rad = ((angle - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

function Gauge({ data, config = {} }) {
  const first = useMemo(() => rowsFrom(data)[0] || {}, [data]);
  const raw = first.value ?? first.score ?? first.percentile ?? first.current;
  const value = Math.max(0, Math.min(100, numberLike(raw) ?? 0));
  const full = config.fullRing || /crowding/i.test(String(first.label || first.name || ""));
  const color = value >= 70 ? TOKENS.red : value >= 40 ? TOKENS.amber : TOKENS.green;
  const start = full ? 0 : -90;
  const end = full ? 360 : 90;
  const sweep = start + ((end - start) * value) / 100;
  const needle = polarToCartesian(150, 150, full ? 96 : 112, sweep);
  return (
    <div className="gauge-layout">
      <svg className={`pro-gauge ${full ? "full" : "semi"}`} data-stress={value >= 70 ? "high" : value >= 40 ? "medium" : "low"} viewBox="0 0 300 190" role="img" aria-label={`Gauge value ${value.toFixed(1)}`}>
        <path d={arcPath(150, 150, 112, start, end)} className="gauge-track" />
        <path d={arcPath(150, 150, 112, start, Math.min(sweep, 30))} className="gauge-green" />
        {value > 30 ? <path d={arcPath(150, 150, 112, 30, Math.min(sweep, 70))} className="gauge-amber" /> : null}
        {value > 70 ? <path d={arcPath(150, 150, 112, 70, sweep)} className="gauge-red" /> : null}
        <line x1="150" y1="150" x2={needle.x} y2={needle.y} className="gauge-needle" />
        <circle cx="150" cy="150" r="7" className="gauge-pivot" />
        <text x="150" y="118" textAnchor="middle" className="gauge-value">{value.toFixed(1)}</text>
        <text x="150" y="140" textAnchor="middle" className="gauge-label">{first.label || first.name || "Percentile"}</text>
      </svg>
    </div>
  );
}

function Heatmap({ data, config = {} }) {
  const [sortMode, setSortMode] = useState(config.defaultSort || "native");
  const cells = useMemo(() => {
    if (Array.isArray(data?.matrix) && Array.isArray(data?.columns)) {
      return data.matrix.flatMap((row, rowIndex) => row.map((value, colIndex) => ({ row: data.index?.[rowIndex] || data.rows?.[rowIndex] || rowIndex, col: data.columns[colIndex], value })));
    }
    return rowsFrom(data).flatMap((row, rowIndex) => {
      const rowName = row.row || row.name || row.factor || row.sector || row.regime || rowIndex;
      return Object.entries(row).filter(([key]) => !["row", "name", "factor", "sector", "regime"].includes(key)).map(([key, value]) => ({ row: rowName, col: key, value }));
    });
  }, [data]);
  if (!cells.length) return <EmptySection section={{ dataKey: "heatmap" }} />;
  let rowLabels = [...new Set(cells.map((cell) => String(cell.row)))];
  let colLabels = [...new Set(cells.map((cell) => String(cell.col)))];
  if (sortMode === "name") {
    rowLabels = [...rowLabels].sort();
    colLabels = [...colLabels].sort();
  } else if (sortMode === "magnitude") {
    const score = (label, axis) => cells.filter((cell) => String(axis === "row" ? cell.row : cell.col) === label).reduce((sum, cell) => sum + Math.abs(numberLike(cell.value) ?? 0), 0);
    rowLabels = [...rowLabels].sort((a, b) => score(b, "row") - score(a, "row"));
    colLabels = [...colLabels].sort((a, b) => score(b, "col") - score(a, "col"));
  } else if (sortMode === "cluster") {
    rowLabels = clusterSortLabels(cells, rowLabels);
    colLabels = clusterSortLabels(cells.map((cell) => ({ row: cell.col, col: cell.row, value: cell.value })), colLabels);
  }
  const magnitudes = cells.map((cell) => Math.abs(numberLike(cell.value) ?? 0));
  const max = Math.max(1, ...magnitudes);
  const colorFor = (value) => {
    const n = numberLike(value) ?? 0;
    const opacity = Math.min(0.88, Math.abs(n) / max);
    if (config.palette === "diverging") return n >= 0 ? `rgba(248,81,73,${0.16 + opacity})` : `rgba(245,164,0,${0.16 + opacity})`;
    return n >= 0 ? `rgba(63,185,80,${0.13 + opacity})` : `rgba(248,81,73,${0.13 + opacity})`;
  };
  return (
    <div className="heatmap-wrap">
      <div className="heatmap-tools">
        <span>Sort matrix</span>
        <select value={sortMode} onChange={(event) => setSortMode(event.target.value)}>
          <option value="native">Native</option>
          <option value="magnitude">Loading magnitude</option>
          <option value="cluster">Similarity cluster</option>
          <option value="name">Factor name</option>
        </select>
      </div>
      <div className="heatmap-grid" style={{ gridTemplateColumns: `150px repeat(${colLabels.length}, minmax(82px, 1fr))` }}>
        <div className="heatmap-head" />
        {colLabels.map((col) => <div className="heatmap-head" key={col}>{titleize(col)}</div>)}
        {rowLabels.flatMap((row, rowIndex) => [
          <div className="heatmap-row-label" key={`${row}-label`}>{titleize(row)}</div>,
          ...colLabels.map((col) => {
            const cell = cells.find((item) => String(item.row) === row && String(item.col) === col);
            const n = Math.abs(numberLike(cell?.value) ?? 0);
            return <div className={`heatmap-cell mono ${n > 0.6 ? "strong-cell" : ""}`} key={`${row}-${col}`} style={{ animationDelay: `${rowIndex * 20}ms`, background: colorFor(cell?.value) }}>{formatValue(cell?.value)}</div>;
          }),
        ])}
      </div>
    </div>
  );
}

function DataTable({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const columns = useMemo(() => [...new Set(rows.flatMap((row) => Object.keys(row || {})))].slice(0, 14), [rows]);
  const [sort, setSort] = useState({ key: columns[0] || "name", dir: "asc" });
  const sortedRows = useMemo(() => {
    const next = [...rows];
    next.sort((a, b) => {
      const av = numberLike(a?.[sort.key]) ?? String(a?.[sort.key] ?? "");
      const bv = numberLike(b?.[sort.key]) ?? String(b?.[sort.key] ?? "");
      const result = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? result : -result;
    });
    return next;
  }, [rows, sort]);
  const visibleRows = useMemo(() => sortedRows.slice(0, 500).map((row) => Object.fromEntries(columns.map((column) => [column, {
    raw: row?.[column],
    n: numberLike(row?.[column]),
    formatted: formatValue(row?.[column]),
  }]))), [columns, sortedRows]);
  if (!rows.length) return <EmptySection section={{ dataKey: "table" }} />;
  return (
    <div className="table-scroll">
      <table className="f2-table">
        <thead><tr>{columns.map((column) => <th data-sorted={sort.key === column ? "true" : undefined} key={column}><button type="button" onClick={() => setSort((current) => ({ key: column, dir: current.key === column && current.dir === "asc" ? "desc" : "asc" }))}>{titleize(column)}<span>{sort.key === column ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}</span></button></th>)}</tr></thead>
        <tbody>
          {visibleRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column, columnIndex) => {
                const cell = row?.[column] || {};
                const value = cell.raw;
                const n = cell.n;
                const threshold = config.colorByThreshold && n != null ? (n >= 20 ? "negative" : n >= 10 ? "warning" : "positive") : "";
                const sign = (config.colorBySign || config.viableColumn || config.flagAbsTstat2) && n != null ? (n > 0 ? "positive" : n < 0 ? "negative" : "") : "";
                const intensity = config.colorByIntensity && n != null ? `rgba(245,164,0,${Math.min(0.8, Math.abs(n))})` : undefined;
                return <td className={`${n != null ? "mono" : ""} ${threshold || sign}`} key={column} style={{ background: intensity }}>{columnIndex === 0 ? titleize(value) : cell.formatted}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextBlock({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  if (!data) return <EmptySection section={{ dataKey: "text" }} />;
  if (typeof data === "string") return <div className={`text-block ${config.alert ? "alert" : ""}`}>{data}</div>;
  return (
    <div className={`text-block ${config.alert ? "alert" : ""}`}>
      {rows.map((row, index) => (
        <div className="text-row" key={index}>
          <strong>{row.title || row.name || row.section || `Section ${index + 1}`}</strong>
          <p>{row.text || row.body || row.value || row.description || JSON.stringify(row)}</p>
        </div>
      ))}
    </div>
  );
}

function PdfDownload({ response }) {
  const pdf = response?.meta?.pdf_base64;
  const disabled = typeof pdf !== "string" || pdf.length < 20;
  return (
    <button
      className="pdf-button"
      disabled={disabled}
      onClick={() => {
        if (disabled) return;
        const link = document.createElement("a");
        link.href = `data:application/pdf;base64,${pdf}`;
        link.download = "factors-v2-allocator-report.pdf";
        link.click();
      }}
      type="button"
    >
      <Download size={18} />
      {disabled ? "PDF payload not returned" : "Download allocator PDF"}
    </button>
  );
}

function ProgressBars({ data }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 12), [data]);
  return (
    <div className="progress-stack">
      {rows.map((row, index) => {
        const label = row.label || row.name || row.regime || row.factor || `Item ${index + 1}`;
        const value = Math.max(0, Math.min(1, numberLike(row.value ?? row.probability ?? row.weight ?? row.score) ?? 0));
        return (
          <div className="progress-row" key={label}>
            <span>{titleize(label)}</span>
            <div><i style={{ width: `${value * 100}%`, background: SERIES[index % SERIES.length] }} /></div>
            <b className="mono">{(value * 100).toFixed(1)}%</b>
          </div>
        );
      })}
    </div>
  );
}

function RadarVisual({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 12).map((row, index) => ({ axis: row.axis || row.name || row.factor || `Axis ${index + 1}`, value: numberLike(row.value ?? row.score ?? row.weight) ?? 0 })), [data]);
  return (
    <ResponsiveContainer height={370} width="100%">
      <RadarChart data={rows} outerRadius={config.outerRadius || "72%"}>
        <PolarGrid stroke={TOKENS.grid} strokeOpacity={0.5} />
        <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
        <PolarRadiusAxis axisLine={false} tick={{ fill: TOKENS.secondary, fontSize: 10 }} tickLine={false} />
        <Radar dataKey="value" fill={config.fill || TOKENS.accent} fillOpacity={config.fillOpacity ?? 0.18} stroke={config.stroke || TOKENS.accent} strokeWidth={2} />
        <Tooltip content={<CustomTooltip />} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function Waterfall({ data }) {
  const [hovered, setHovered] = useState(null);
  const rows = useMemo(() => rowsFrom(data).map((row, index) => ({ name: row.name || row.component || row.factor || `Step ${index + 1}`, value: numberLike(row.value ?? row.contribution ?? row.effect ?? row.return) ?? 0 })), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "waterfall" }} />;
  const running = rows.reduce((acc, row, index) => {
    const previous = index ? acc[index - 1].end : 0;
    acc.push({ ...row, start: previous, end: previous + row.value });
    return acc;
  }, []);
  const min = Math.min(0, ...running.map((row) => Math.min(row.start, row.end)));
  const max = Math.max(0, ...running.map((row) => Math.max(row.start, row.end)));
  const span = max - min || 1;
  const y = (value) => 330 - ((value - min) / span) * 260;
  const width = 920;
  const gap = width / Math.max(running.length, 1);
  const barWidth = Math.max(28, Math.min(62, gap * 0.54));
  return (
    <div className="waterfall-svg-wrap">
      <svg className="waterfall-svg" viewBox={`0 0 ${width} 380`} role="img" aria-label="Waterfall attribution chart">
        {[0, .25, .5, .75, 1].map((tick) => <line key={tick} x1="42" x2={width - 20} y1={70 + tick * 260} y2={70 + tick * 260} className="wf-grid" />)}
        <line x1="42" x2={width - 20} y1={y(0)} y2={y(0)} className="wf-zero" />
        {running.map((row, index) => {
          const x = 58 + index * gap;
          const y1 = y(row.start);
          const y2 = y(row.end);
          const top = Math.min(y1, y2);
          const height = Math.max(2, Math.abs(y2 - y1));
          const positive = row.value >= 0;
          const nextX = 58 + (index + 1) * gap;
          return (
            <g key={row.name} onMouseEnter={() => setHovered({ ...row, x: x + barWidth / 2, y: top })} onMouseLeave={() => setHovered(null)}>
              <rect x={x} y={top} width={barWidth} height={height} rx="5" className={positive ? "wf-positive" : "wf-negative"} />
              {index < running.length - 1 ? <line x1={x + barWidth} x2={nextX} y1={y2} y2={y2} className="wf-connector" /> : null}
              <circle cx={x + barWidth / 2} cy={y2} r="3" className="wf-dot" />
              <text x={x + barWidth / 2} y="356" textAnchor="middle" className="wf-label">{titleize(row.name).slice(0, 16)}</text>
              <text x={x + barWidth / 2} y={top - 8} textAnchor="middle" className="wf-value">{formatValue(row.value)}</text>
            </g>
          );
        })}
      </svg>
      {hovered ? (
        <div className="waterfall-tooltip" style={{ left: `${Math.min(82, Math.max(8, (hovered.x / width) * 100))}%`, top: `${Math.max(8, hovered.y / 3.8)}%` }}>
          <strong>{titleize(hovered.name)}</strong>
          <span>Value <b className={hovered.value >= 0 ? "positive" : "negative"}>{hovered.value >= 0 ? "+" : ""}{formatValue(hovered.value)}</b></span>
          <span>Running total <b>{formatValue(hovered.end)}</b></span>
          <span>Basis points <b>{(hovered.value * 10000).toFixed(0)} bps</b></span>
          <span>% of total <b>{running.at(-1)?.end ? ((hovered.value / Math.abs(running.at(-1).end)) * 100).toFixed(1) : "0.0"}%</b></span>
        </div>
      ) : null}
    </div>
  );
}

function PieVisual({ data, donut = false }) {
  const rows = useMemo(() => rowsFrom(data).map((row, index) => ({ name: row.name || row.factor || row.segment || `Slice ${index + 1}`, value: Math.abs(numberLike(row.value ?? row.weight ?? row.allocation) ?? 0) })), [data]);
  return (
    <ResponsiveContainer height={340} width="100%">
      <PieChart>
        <Pie data={rows} dataKey="value" innerRadius={donut ? 68 : 0} nameKey="name" outerRadius={118} paddingAngle={2}>
          {rows.map((_, index) => <Cell fill={SERIES[index % SERIES.length]} key={index} />)}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

function Classifier({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 4), [data]);
  const total = rows.reduce((sum, row) => sum + Math.abs(numberLike(row.value ?? row.probability ?? row.weight) ?? 0), 0) || 1;
  const dominant = rows.reduce((best, row) => (numberLike(row.value ?? row.probability ?? row.weight) ?? 0) > (numberLike(best?.value ?? best?.probability ?? best?.weight) ?? -Infinity) ? row : best, null);
  return (
    <div className="classifier">
      <span>Dominant archetype</span>
      <strong>{titleize(dominant?.name || dominant?.class || "Unclassified")}</strong>
      <div className="classifier-bar">
        {rows.map((row, index) => {
          const value = Math.abs(numberLike(row.value ?? row.probability ?? row.weight) ?? 0);
          return <i key={index} style={{ width: `${(value / total) * 100}%`, background: (config.seriesColors || SERIES)[index % SERIES.length] }} title={row.name || row.class} />;
        })}
      </div>
    </div>
  );
}

function StandardChart({ data, type, config = {} }) {
  const [hidden, setHidden] = useState(() => new Set());
  const rows = useMemo(() => rowsFrom(data), [data]);
  const { syncedLabel, onMouseLeave, onMouseMove } = useSyncedChart();
  const { xKey, yKeys } = useMemo(() => inferKeys(rows, config), [rows, config]);
  if (!rows.length) return <EmptySection section={{ dataKey: type }} />;
  const colors = config.seriesColors || SERIES;
  if (type === "scatter") {
    return (
      <ResponsiveContainer height={390} width="100%">
        <ScatterChart margin={{ top: 16, right: 28, left: 8, bottom: 14 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey={config.xKey || yKeys[0] || xKey} type="number" {...axisProps} />
          <YAxis dataKey={config.yKeys?.[0] || yKeys[1] || "value"} type="number" {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter data={rows} fill={TOKENS.accent} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }
  if (type === "horizontalBar" || type === "groupedHorizontalBar") {
    return (
      <ResponsiveContainer height={Math.max(330, rows.length * 34)} width="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 14, right: 26, left: 6, bottom: 12 }}>
          <CartesianGrid horizontal={false} stroke={TOKENS.grid} strokeOpacity={0.5} />
          <XAxis type="number" {...axisProps} />
          <YAxis dataKey={xKey} type="category" width={150} {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          {config.referenceLines?.map((line, index) => <ReferenceLine key={index} stroke={line.stroke || TOKENS.amber} strokeDasharray={line.strokeDasharray || "4 4"} x={line.value} />)}
          {yKeys.map((key, index) => (
            <Bar dataKey={key} fill={colors[index % colors.length]} key={key} radius={[0, 4, 4, 0]}>
              {config.colorBySign ? rows.map((row, cellIndex) => <Cell fill={(numberLike(row[key]) ?? 0) >= 0 ? (config.positiveColor || TOKENS.green) : (config.negativeColor || TOKENS.red)} key={cellIndex} />) : null}
              {(config.errorBars || rows.some((row) => row.error != null || row.stderr != null || row.ci_width != null)) ? <ErrorBar dataKey="error" stroke={TOKENS.secondary} width={4} /> : null}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  if (type === "bar" || type === "stackedBar") {
    return (
      <ResponsiveContainer height={370} width="100%">
        <BarChart data={rows} margin={{ top: 14, right: 26, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          {config.referenceLines?.map((line, index) => <ReferenceLine key={index} label={line.label} stroke={line.stroke || TOKENS.amber} strokeDasharray={line.strokeDasharray || "4 4"} y={line.value} />)}
          {yKeys.map((key, index) => (
            <Bar dataKey={key} fill={colors[index % colors.length]} key={key} radius={[4, 4, 0, 0]} stackId={type === "stackedBar" || config.stacked ? "stack" : undefined}>
              {rows.map((row, cellIndex) => {
                const n = numberLike(row[key]) ?? 0;
                const violates = /quintile/i.test(String(row[xKey] ?? "")) && cellIndex > 0 && n > (numberLike(rows[cellIndex - 1]?.[key]) ?? Infinity);
                return <Cell className={violates ? "violates-monotone" : ""} fill={config.colorBySign ? (n >= 0 ? (config.positiveColor || TOKENS.green) : (config.negativeColor || TOKENS.red)) : colors[cellIndex % colors.length]} key={cellIndex} stroke={violates ? TOKENS.amber : undefined} strokeDasharray={violates ? "4 3" : undefined} strokeWidth={violates ? 2 : 0} />;
              })}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  const Chart = type === "line" ? LineChart : AreaChart;
  const yValues = rows.flatMap((row) => yKeys.map((key) => numberLike(row[key])).filter((value) => value != null));
  const yMin = Math.min(...yValues, 0);
  const yMax = Math.max(...yValues, 0);
  const zeroStop = yMax === yMin ? 50 : Math.max(0, Math.min(100, ((yMax - 0) / (yMax - yMin)) * 100));
  return (
    <ResponsiveContainer height={400} width="100%">
      <Chart data={rows} margin={{ top: 14, right: 26, left: 6, bottom: 12 }} onMouseLeave={onMouseLeave} onMouseMove={onMouseMove}>
        <defs>
          {yKeys.map((key, index) => {
            const color = colors[index % colors.length];
            return (
              <linearGradient id={`grad-${type}-${key.replace(/[^a-z0-9]/gi, "")}-${index}`} key={key} x1="0" x2="0" y1="0" y2="1">
                {config.colorBySign ? <>
                  <stop offset="0%" stopColor={TOKENS.green} stopOpacity={0.28} />
                  <stop offset={`${zeroStop}%`} stopColor={color} stopOpacity={0.08} />
                  <stop offset="100%" stopColor={TOKENS.red} stopOpacity={0.3} />
                </> : <>
                  <stop offset="0%" stopColor={color} stopOpacity={config.fillOpacity ?? 0.32} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </>}
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.5} vertical={false} />
        <XAxis dataKey={xKey} scale={config.logX ? "log" : undefined} type={config.logX ? "number" : undefined} domain={config.logX ? ["dataMin", "dataMax"] : undefined} {...axisProps} />
        <YAxis domain={config.yDomain || ["auto", "auto"]} {...axisProps} />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ color: TOKENS.secondary, fontSize: 12 }}
          onClick={(entry) => setHidden((current) => {
            const next = new Set(current);
            if (next.has(entry.dataKey)) next.delete(entry.dataKey);
            else next.add(entry.dataKey);
            return next;
          })}
        />
        {config.referenceAreas?.map((area, index) => <ReferenceArea fill={area.fill} fillOpacity={area.fillOpacity ?? 0.08} key={index} y1={area.y1} y2={area.y2} />)}
        {config.referenceLines?.map((line, index) => <ReferenceLine key={index} label={line.label} stroke={line.stroke || TOKENS.amber} strokeDasharray={line.strokeDasharray || "4 4"} y={line.value} />)}
        {syncedLabel != null ? <ReferenceLine stroke={TOKENS.accent} strokeDasharray="2 4" strokeOpacity={0.5} x={syncedLabel} /> : null}
        {yKeys.map((key, index) => type === "line" ? (
          <Line activeDot={{ r: 6, strokeWidth: 2, stroke: colors[index % colors.length], fill: TOKENS.panel }} dataKey={key} dot={false} key={key} stroke={colors[index % colors.length]} strokeDasharray={config.dashed ? "5 5" : undefined} strokeOpacity={hidden.has(key) ? 0.15 : 1} strokeWidth={2} type="monotone" />
        ) : (
          <Area dataKey={key} fill={`url(#grad-${type}-${key.replace(/[^a-z0-9]/gi, "")}-${index})`} fillOpacity={hidden.has(key) ? 0.15 : 1} key={key} stackId={type === "stackedArea" || config.stacked ? "stack" : undefined} stroke={colors[index % colors.length]} strokeOpacity={hidden.has(key) ? 0.15 : 1} strokeWidth={2} type="monotone" />
        ))}
        {rows.length > 18 && ["line", "area", "stackedArea"].includes(type) ? <Brush dataKey={xKey} fill={TOKENS.elevated} height={28} stroke={TOKENS.border} travellerWidth={8} /> : null}
      </Chart>
    </ResponsiveContainer>
  );
}

function BacktestSplit({ response, section }) {
  const equity = pickData(response, section);
  const drawdown = response?.charts?.drawdown;
  return (
    <div className="split-backtest">
      <div className="split-top"><StandardChart config={{ seriesColors: ["#3FB950", "#F5A400", "#8B949E"], fillOpacity: 0.16 }} data={equity} type="area" /></div>
      <div className="split-bottom"><StandardChart config={{ seriesColors: ["#F85149"], yDomain: ["auto", 0] }} data={drawdown} type="area" /></div>
    </div>
  );
}

function NormalVsCrisis({ data }) {
  const payload = data && typeof data === "object" ? data : {};
  return (
    <div className="triple-heatmap">
      <div><h4>Normal Regime</h4><Heatmap config={{ palette: "diverging" }} data={payload.normal || payload.normal_covariance || payload.normal_correlation || payload} /></div>
      <div><h4>Crisis Regime</h4><Heatmap config={{ palette: "diverging" }} data={payload.crisis || payload.crisis_covariance || payload.crisis_correlation || payload} /></div>
      <div><h4>Delta</h4><Heatmap config={{ palette: "diverging" }} data={payload.delta || payload.difference || payload} /></div>
    </div>
  );
}

function MultiFactorGaugePanel({ data }) {
  const rows = useMemo(() => rowsFrom(data).map((row, index) => {
    const percentile = numberLike(row.percentile ?? row.value ?? row.score ?? row.current) ?? 50;
    return {
      ...row,
      factor: row.factor || row.label || row.name || `factor_${index + 1}`,
      label: row.label || row.factor || row.name || `Factor ${index + 1}`,
      percentile: Math.max(0, Math.min(100, percentile)),
      implied_return: numberLike(row.implied_return ?? row.implied_return_pct ?? row.expected_12m_return),
      delta: numberLike(row.delta_1m ?? row.delta),
    };
  }), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "gauge_panel" }} />;
  const sorted = [...rows].sort((a, b) => b.percentile - a.percentile);
  const attractive = [...rows].sort((a, b) => a.percentile - b.percentile)[0];
  const stretched = sorted[0];
  return (
    <div className="mfg-panel">
      <div className="mfg-extremes">
        <div className="mfg-extreme-card red">
          <span>Most Stretched</span>
          <strong>{titleize(stretched?.label)}</strong>
          <b className="mono">{stretched?.percentile.toFixed(1)}th pct</b>
        </div>
        <div className="mfg-extreme-card green">
          <span>Most Attractive</span>
          <strong>{titleize(attractive?.label)}</strong>
          <b className="mono">{attractive?.percentile.toFixed(1)}th pct</b>
        </div>
      </div>
      <div className="mfg-grid">
        {rows.map((row, index) => {
          const status = row.percentile >= 70 ? "stretched" : row.percentile <= 30 ? "cheap" : "neutral";
          const color = status === "stretched" ? TOKENS.red : status === "cheap" ? TOKENS.green : TOKENS.amber;
          return (
            <div className={`mfg-card status-${status}`} key={`${row.factor}-${index}`}>
              <div className="mfg-bar-track">
                <div className="mfg-bar-fill" style={{ background: color, width: `${row.percentile}%` }} />
                <div className="mfg-threshold" style={{ left: "30%" }} />
                <div className="mfg-threshold" style={{ left: "70%" }} />
              </div>
              <div className="mfg-card-body">
                <div className="mfg-factor-name">{titleize(row.label)}</div>
                <div className="mfg-pct mono" style={{ color }}>{row.percentile.toFixed(1)}<sup>th</sup></div>
                {row.implied_return != null ? (
                  <div className={`mfg-implied mono ${row.implied_return >= 0 ? "positive" : "negative"}`}>
                    {row.implied_return >= 0 ? "+" : ""}{(row.implied_return * (Math.abs(row.implied_return) < 1 ? 100 : 1)).toFixed(1)}% implied 12M
                  </div>
                ) : null}
                {row.delta != null ? (
                  <div className="mfg-delta">
                    <DeltaLabel delta={row.delta} positiveDirection="down" />
                    <small>1M chg</small>
                  </div>
                ) : null}
                <Sparkline index={index} value={row.percentile} />
              </div>
              <div className="mfg-badge" style={{ background: color }}>{status.toUpperCase()}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AlertFeed({ data }) {
  const alerts = useMemo(() => rowsFrom(data), [data]);
  const [filter, setFilter] = useState("ALL");
  const visible = filter === "ALL" ? alerts : alerts.filter((alert) => String(alert.status || alert.state || "open").toUpperCase() === filter);
  return (
    <div className="alert-feed">
      <div className="alert-feed-header">
        <span className="alert-feed-count">{alerts.filter((alert) => !alert.resolved).length} open</span>
        <div className="alert-feed-filters">
          {["ALL", "OPEN", "TRIGGERED", "RESOLVED"].map((item) => (
            <button className={filter === item ? "active" : ""} key={item} onClick={() => setFilter(item)} type="button">{item}</button>
          ))}
        </div>
      </div>
      <div className="alert-list">
        {visible.map((alert, index) => {
          const pct = numberLike(alert.percentile ?? alert.current_pct ?? alert.value);
          const color = pct == null ? TOKENS.amber : pct >= 70 ? TOKENS.red : pct <= 30 ? TOKENS.green : TOKENS.amber;
          return (
            <div className={`alert-row ${alert.resolved ? "resolved" : "open"}`} key={`${alert.factor || alert.message}-${index}`}>
              <i className="alert-dot" style={{ background: color }} />
              <div className="alert-content">
                <strong>{titleize(alert.factor || alert.label || alert.level || "Alert")}</strong>
                <span>{alert.message || alert.title || "Threshold crossed on latest run."}</span>
                <div className="alert-meta">
                  {pct != null ? <b className="mono" style={{ color }}>{formatValue(pct)}th pct</b> : null}
                  <small>{alert.triggered_at || alert.date || alert.level || "latest"}</small>
                  {alert.resolved ? <em className="resolved-badge">RESOLVED</em> : null}
                </div>
              </div>
            </div>
          );
        })}
        {!visible.length ? <div className="alert-empty">No alerts match this filter.</div> : null}
      </div>
    </div>
  );
}

function AnnotatedTimeSeries({ response, section }) {
  const data = pickData(response, section);
  const rows = useMemo(() => rowsFrom(data), [data]);
  const crisisAnchors = useMemo(() => rowsFrom(response?.charts?.[section.config?.crisisDataKey] || response?.tables?.crisis_anchor_percentiles || []), [response, section.config?.crisisDataKey]);
  const { xKey, yKeys } = useMemo(() => inferKeys(rows, section.config), [rows, section.config]);
  if (!rows.length) return <EmptySection response={response} section={section} />;
  const colors = section.config?.seriesColors || SERIES;
  return (
    <div className="annotated-ts">
      <ResponsiveContainer height={420} width="100%">
        <AreaChart data={rows} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <defs>
            {yKeys.map((key, index) => (
              <linearGradient id={`ats-grad-${key.replace(/[^a-z0-9]/gi, "")}-${index}`} key={key} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={colors[index % colors.length]} stopOpacity={0.3} />
                <stop offset="100%" stopColor={colors[index % colors.length]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} />
          <YAxis domain={section.config?.yDomain || [0, 100]} {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceArea y1={70} y2={100} fill={TOKENS.red} fillOpacity={0.05} />
          <ReferenceArea y1={0} y2={30} fill={TOKENS.green} fillOpacity={0.05} />
          <ReferenceLine y={70} stroke={TOKENS.red} strokeDasharray="4 4" strokeOpacity={0.75} label={{ value: "Stretched", fill: TOKENS.red, fontSize: 10, position: "insideTopRight" }} />
          <ReferenceLine y={30} stroke={TOKENS.green} strokeDasharray="4 4" strokeOpacity={0.75} label={{ value: "Cheap", fill: TOKENS.green, fontSize: 10, position: "insideBottomRight" }} />
          {crisisAnchors.slice(0, 10).map((anchor, index) => (
            <ReferenceLine
              key={`${anchor.anchor || anchor.label}-${index}`}
              stroke={TOKENS.amber}
              strokeDasharray="3 5"
              strokeOpacity={0.6}
              x={anchor.used_date || anchor.date || anchor.anchor_date}
              label={{ value: anchor.anchor || anchor.label || anchor.event, fill: TOKENS.amber, fontSize: 9, angle: -90, position: "insideTopLeft" }}
            />
          ))}
          {yKeys.map((key, index) => (
            <Area dataKey={key} dot={false} fill={`url(#ats-grad-${key.replace(/[^a-z0-9]/gi, "")}-${index})`} key={key} stroke={colors[index % colors.length]} strokeWidth={2} type="monotone" />
          ))}
          {rows.length > 20 ? <Brush dataKey={xKey} fill={TOKENS.elevated} height={28} stroke={TOKENS.border} travellerWidth={8} /> : null}
        </AreaChart>
      </ResponsiveContainer>
      {crisisAnchors.length ? (
        <div className="crisis-legend">
          {crisisAnchors.slice(0, 8).map((anchor, index) => (
            <div className="crisis-chip" key={index}>
              <i />
              <span>{anchor.anchor || anchor.label || anchor.event}</span>
              <b className="mono">{anchor.used_date || anchor.date || anchor.anchor_date}</b>
              {anchor.percentile != null ? <em>{formatValue(anchor.percentile)}th pct</em> : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RollingExposureHeatmap({ data, config = {} }) {
  const snapshots = useMemo(() => {
    if (Array.isArray(data?.snapshots)) return data.snapshots;
    if (Array.isArray(data)) return [{ date: "latest", matrix: data }];
    return [data];
  }, [data]);
  const [frame, setFrame] = useState(Math.max(0, snapshots.length - 1));
  const [playing, setPlaying] = useState(false);
  const rafRef = useRef(null);
  const lastRef = useRef(0);
  useEffect(() => {
    if (!playing || snapshots.length <= 1) return undefined;
    const tick = (now) => {
      if (!lastRef.current || now - lastRef.current > (config.frameDurationMs || 320)) {
        lastRef.current = now;
        setFrame((current) => {
          const next = current >= snapshots.length - 1 ? 0 : current + 1;
          return next;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing, snapshots.length, config.frameDurationMs]);
  const current = snapshots[Math.min(frame, snapshots.length - 1)] || snapshots[0];
  return (
    <div className="rolling-heatmap">
      <div className="rolling-controls">
        <button onClick={() => { setFrame(0); setPlaying(false); }} type="button">⏮</button>
        <button onClick={() => setFrame((value) => Math.max(0, value - 1))} type="button">◀</button>
        <button className={playing ? "active" : ""} onClick={() => setPlaying((value) => !value)} type="button">{playing ? "PAUSE" : "PLAY"}</button>
        <button onClick={() => setFrame((value) => Math.min(snapshots.length - 1, value + 1))} type="button">▶</button>
        <div className="rolling-scrubber">
          <input max={Math.max(0, snapshots.length - 1)} min={0} onChange={(event) => { setPlaying(false); setFrame(Number(event.target.value)); }} type="range" value={frame} />
        </div>
        <span className="rolling-date mono">{current?.date || current?.as_of || "latest"}</span>
        <span className="rolling-count mono">{frame + 1}/{snapshots.length}</span>
      </div>
      <Heatmap config={{ ...config, defaultSort: config.defaultSort || "magnitude" }} data={current?.matrix || current} />
    </div>
  );
}

function RegimeTrendPanel({ data }) {
  const rows = useMemo(() => rowsFrom(data).map((row) => {
    const probability = Math.max(0, Math.min(1, numberLike(row.prob_now ?? row.probability ?? row.value) ?? 0));
    return {
      state: row.state || row.regime || row.label || row.name,
      probability,
      change30: numberLike(row.change_30d ?? row.delta_30d) ?? 0,
      change90: numberLike(row.change_90d ?? row.delta_90d) ?? 0,
    };
  }), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "current_regime_trend" }} />;
  return (
    <div className="regime-trend-panel">
      <div className="regime-stack-label">Current Regime Probability</div>
      <div className="regime-stack">
        {rows.map((row, index) => <i key={row.state || index} style={{ background: SERIES[index % SERIES.length], width: `${row.probability * 100}%` }} title={`${row.state}: ${(row.probability * 100).toFixed(1)}%`} />)}
      </div>
      <div className="regime-trend-grid">
        {rows.map((row, index) => (
          <div className="regime-trend-card" key={row.state || index}>
            <span><i style={{ background: SERIES[index % SERIES.length] }} />{titleize(row.state)}</span>
            <b className="mono">{(row.probability * 100).toFixed(1)}%</b>
            <small className={row.change30 >= 0 ? "positive" : "negative"}>30D {row.change30 >= 0 ? "+" : ""}{(row.change30 * 100).toFixed(1)}pp</small>
            <small className={row.change90 >= 0 ? "positive" : "negative"}>90D {row.change90 >= 0 ? "+" : ""}{(row.change90 * 100).toFixed(1)}pp</small>
          </div>
        ))}
      </div>
    </div>
  );
}

function DecileReturnChart({ data }) {
  const rows = useMemo(() => rowsFrom(data).map((row, index) => ({
    bucket: row.decile || row.quintile || row.bucket || `D${index + 1}`,
    annual_return: numberLike(row.annual_return ?? row.value ?? row.return) ?? 0,
    n_stocks: numberLike(row.n_stocks ?? row.count),
  })), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "decile_return" }} />;
  return (
    <div className="decile-return-panel">
      <StandardChart config={{ colorBySign: true, positiveColor: TOKENS.green, negativeColor: TOKENS.red }} data={rows} type="bar" />
      <div className="decile-ribbon">
        {rows.map((row, index) => {
          const value = row.annual_return * (Math.abs(row.annual_return) < 2 ? 100 : 1);
          return <span className={row.annual_return >= 0 ? "positive" : "negative"} key={row.bucket}>{row.bucket}: {value >= 0 ? "+" : ""}{value.toFixed(1)}%</span>;
        })}
      </div>
    </div>
  );
}

function HierarchicalHeatmap({ data, config = {} }) {
  return (
    <div className="hierarchical-heatmap">
      <div className="hierarchy-note"><span>Clustered by absolute similarity</span><b>HIERARCHICAL VIEW</b></div>
      <Heatmap config={{ ...config, defaultSort: "cluster" }} data={data} />
    </div>
  );
}

function MultiPortfolioCompare({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "multi_portfolio_comparison" }} />;
  const portfolios = [...new Set(rows.map((row) => row.portfolio).filter(Boolean))].slice(0, 6);
  const factors = [...new Set(rows.map((row) => row.factor).filter(Boolean))];
  const chartRows = factors.map((factor) => {
    const row = { factor };
    rows.filter((item) => item.factor === factor).forEach((item) => {
      row[item.portfolio] = numberLike(item.exposure ?? item.characteristic_exposure ?? item.value) ?? 0;
    });
    return row;
  });
  return (
    <div className="portfolio-compare">
      <ResponsiveContainer height={Math.max(300, factors.length * 48)} width="100%">
        <BarChart data={chartRows} layout="vertical" margin={{ top: 8, right: 24, left: 16, bottom: 8 }}>
          <CartesianGrid horizontal={false} stroke={TOKENS.grid} strokeOpacity={0.45} />
          <XAxis type="number" {...axisProps} />
          <YAxis dataKey="factor" type="category" width={150} {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine stroke={TOKENS.secondary} strokeDasharray="3 3" x={0} />
          {portfolios.map((portfolio, index) => <Bar barSize={12} dataKey={portfolio} fill={SERIES[index % SERIES.length]} key={portfolio} radius={[0, 4, 4, 0]} />)}
        </BarChart>
      </ResponsiveContainer>
      <div className="mini-legend">{portfolios.map((portfolio, index) => <span key={portfolio}><i style={{ background: SERIES[index % SERIES.length] }} />{portfolio}</span>)}</div>
    </div>
  );
}

function StackedAttributionWaterfall({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "stacked_active_return_waterfall" }} />;
  const keys = ["allocation_effect", "selection_effect", "interaction_effect", "carryover_contribution", "active_contribution"].filter((key) => rows.some((row) => numberLike(row[key]) != null));
  const chartRows = rows.map((row) => ({
    sector: row.sector || row.component || row.factor || row.name,
    ...Object.fromEntries(keys.map((key) => [key, numberLike(row[key]) ?? 0])),
    total: numberLike(row.total_effect ?? row.total_active_return ?? row.value) ?? keys.reduce((sum, key) => sum + (numberLike(row[key]) ?? 0), 0),
  })).slice(0, 14);
  return (
    <div className="stacked-attribution">
      <ResponsiveContainer height={Math.max(320, chartRows.length * 42)} width="100%">
        <BarChart data={chartRows} layout="vertical" margin={{ top: 8, right: 24, left: 12, bottom: 8 }}>
          <CartesianGrid horizontal={false} stroke={TOKENS.grid} strokeOpacity={0.38} />
          <XAxis type="number" {...axisProps} />
          <YAxis dataKey="sector" type="category" width={150} {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine stroke={TOKENS.secondary} strokeDasharray="3 3" x={0} />
          {keys.map((key, index) => <Bar dataKey={key} fill={SERIES[index % SERIES.length]} key={key} radius={[0, 3, 3, 0]} stackId="active" />)}
        </BarChart>
      </ResponsiveContainer>
      <div className="mini-legend">{keys.map((key, index) => <span key={key}><i style={{ background: SERIES[index % SERIES.length] }} />{titleize(key)}</span>)}</div>
    </div>
  );
}

function FreshnessScore({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "decision_freshness_score" }} />;
  const aggregate = rows.find((row) => row.period_start === "aggregate" || row.component === "decision_freshness_score") || rows[rows.length - 1];
  const score = Math.max(0, Math.min(100, (numberLike(aggregate.decision_freshness_score ?? aggregate.value ?? aggregate.freshness_score) ?? 0) * 100));
  const color = score >= 65 ? TOKENS.green : score >= 35 ? TOKENS.amber : TOKENS.red;
  return (
    <div className="freshness-score">
      <div className="freshness-dial" style={{ "--score": `${score}%`, "--score-color": color }}>
        <b>{score.toFixed(0)}</b>
        <span>freshness</span>
      </div>
      <DataTable data={rows} />
    </div>
  );
}

function CrossSectorDecay({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "cross_sector_decay" }} />;
  const sectors = [...new Set(rows.map((row) => row.sector).filter(Boolean))].slice(0, 8);
  const selected = sectors[0];
  const chartRows = rows.filter((row) => row.sector === selected || !row.sector).slice(0, 120);
  return (
    <div className="sector-decay">
      <div className="mini-legend">{sectors.map((sector, index) => <span key={sector}><i style={{ background: SERIES[index % SERIES.length] }} />{sector}</span>)}</div>
      <ResponsiveContainer height={340} width="100%">
        <LineChart data={chartRows} margin={{ top: 10, right: 24, left: 4, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="horizon" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine stroke={TOKENS.secondary} strokeDasharray="3 3" y={0} />
          <Line activeDot={{ r: 6, strokeWidth: 2, stroke: TOKENS.accent, fill: TOKENS.panel }} dataKey="mean_ic" dot={false} stroke={TOKENS.accent} strokeWidth={2.4} type="monotone" />
          <Line dataKey="icir" dot={false} stroke={TOKENS.teal} strokeDasharray="5 5" strokeWidth={1.8} type="monotone" />
        </LineChart>
      </ResponsiveContainer>
      <DataTable data={rows.slice(0, 80)} />
    </div>
  );
}

function MultiFactorRadar({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "multi_factor_power_radar" }} />;
  const factors = [...new Set(rows.map((row) => row.factor).filter(Boolean))].slice(0, 4);
  const axes = [...new Set(rows.map((row) => row.axis).filter(Boolean))];
  const chartRows = axes.map((axis) => {
    const out = { axis };
    rows.filter((row) => row.axis === axis).forEach((row) => {
      out[row.factor] = numberLike(row.value) ?? 0;
    });
    return out;
  });
  return (
    <div className="multi-radar">
      <ResponsiveContainer height={380} width="100%">
        <RadarChart data={chartRows}>
          <PolarGrid stroke={TOKENS.border} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: TOKENS.muted, fontSize: 10 }} />
          {factors.map((factor, index) => <Radar dataKey={factor} fill={SERIES[index % SERIES.length]} fillOpacity={0.08 + index * 0.02} key={factor} stroke={SERIES[index % SERIES.length]} strokeWidth={2} />)}
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
      <div className="mini-legend">{factors.map((factor, index) => <span key={factor}><i style={{ background: SERIES[index % SERIES.length] }} />{factor}</span>)}</div>
    </div>
  );
}

function CrowdingOverlay({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "crowding_return_overlay" }} />;
  const events = rows.filter((row) => row.event || row.crash_flag).slice(-8);
  return (
    <div className="crowding-overlay">
      <ResponsiveContainer height={360} width="100%">
        <LineChart data={rows} margin={{ top: 10, right: 24, left: 2, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="date" minTickGap={28} {...axisProps} />
          <YAxis yAxisId="left" domain={[0, 100]} {...axisProps} />
          <YAxis yAxisId="right" orientation="right" {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine yAxisId="left" stroke={TOKENS.red} strokeDasharray="4 4" y={70} />
          <Line yAxisId="left" dataKey="crowding" dot={false} stroke={TOKENS.amber} strokeWidth={2.4} type="monotone" />
          <Line yAxisId="right" dataKey="forward_63d_return" dot={false} stroke={TOKENS.teal} strokeDasharray="5 5" strokeWidth={1.8} type="monotone" />
        </LineChart>
      </ResponsiveContainer>
      {events.length ? <div className="event-strip">{events.map((event) => <span key={`${event.date}-${event.event || "crash"}`}>{event.date} · {event.event || "crash risk"}</span>)}</div> : null}
    </div>
  );
}

function AdvCapacityCurve({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <EmptySection section={{ dataKey: "adv_capacity_curve" }} />;
  return (
    <div className="adv-capacity">
      <ResponsiveContainer height={360} width="100%">
        <AreaChart data={rows} margin={{ top: 12, right: 24, left: 2, bottom: 12 }}>
          <defs>
            <linearGradient id="adv-cap-grad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={TOKENS.green} stopOpacity={0.28} />
              <stop offset="100%" stopColor={TOKENS.red} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="aum_label" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine stroke={TOKENS.secondary} strokeDasharray="3 3" y={0} />
          <Area dataKey="net_alpha_bps" fill="url(#adv-cap-grad)" stroke={TOKENS.amber} strokeWidth={2.3} type="monotone" />
          <Line dataKey="impact_drag_bps" dot={false} stroke={TOKENS.red} strokeDasharray="5 5" strokeWidth={1.8} type="monotone" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function CrisisPresetComparison({ data }) {
  const presets = data?.presets || rowsFrom(data);
  const [active, setActive] = useState(0);
  if (!presets.length) return <EmptySection section={{ dataKey: "crisis_preset_comparison" }} />;
  const current = presets[Math.min(active, presets.length - 1)];
  return (
    <div className="crisis-presets">
      <div className="preset-tabs">
        {presets.map((preset, index) => <button className={index === active ? "active" : ""} key={preset.preset || index} onClick={() => setActive(index)} type="button">{preset.preset || `Preset ${index + 1}`}</button>)}
      </div>
      <NormalVsCrisis data={current} />
    </div>
  );
}

export function RenderFeatureSection({ response, section }) {
  if (section.chartType === "pdfDownload") return <PdfDownload response={response} />;
  if (section.chartType === "backtestSplit") return <BacktestSplit response={response} section={section} />;
  if (section.chartType === "annotatedTimeSeries") return <AnnotatedTimeSeries response={response} section={section} />;
  const data = pickData(response, section);
  if (!data) return <EmptySection response={response} section={section} />;
  if (section.chartType === "multiPortfolioCompare") return <MultiPortfolioCompare data={data} />;
  if (section.chartType === "stackedAttributionWaterfall") return <StackedAttributionWaterfall data={data} />;
  if (section.chartType === "freshnessScore") return <FreshnessScore data={data} />;
  if (section.chartType === "crossSectorDecay") return <CrossSectorDecay data={data} />;
  if (section.chartType === "multiFactorRadar") return <MultiFactorRadar data={data} />;
  if (section.chartType === "crowdingOverlay") return <CrowdingOverlay data={data} />;
  if (section.chartType === "advCapacityCurve") return <AdvCapacityCurve data={data} />;
  if (section.chartType === "crisisPresetComparison") return <CrisisPresetComparison data={data} />;
  if (section.chartType === "multiFactorGaugePanel") return <MultiFactorGaugePanel data={data} />;
  if (section.chartType === "alertFeed") return <AlertFeed data={data} />;
  if (section.chartType === "rollingHeatmap") return <RollingExposureHeatmap config={section.config} data={data} />;
  if (section.chartType === "regimeTrend") return <RegimeTrendPanel data={data} />;
  if (section.chartType === "decileReturn") return <DecileReturnChart data={data} />;
  if (section.chartType === "hierarchicalHeatmap") return <HierarchicalHeatmap config={section.config} data={data} />;
  if (section.chartType === "summaryGauges") return <MetricDeck config={section.config} data={data} />;
  if (section.chartType === "gauge") return <Gauge config={section.config} data={data} />;
  if (section.chartType === "table") return <DataTable config={section.config} data={data} />;
  if (section.chartType === "heatmap") return <Heatmap config={section.config} data={data} />;
  if (section.chartType === "waterfall") return <Waterfall data={data} />;
  if (section.chartType === "radar") return <RadarVisual config={section.config} data={data} />;
  if (section.chartType === "progressBars") return <ProgressBars data={data} />;
  if (section.chartType === "textBlock") return <TextBlock config={section.config} data={data} />;
  if (section.chartType === "pie") return <PieVisual data={data} />;
  if (section.chartType === "donut") return <PieVisual data={data} donut />;
  if (section.chartType === "classifier") return <Classifier config={section.config} data={data} />;
  if (section.chartType === "normalVsCrisis") return <NormalVsCrisis data={data} />;
  return <StandardChart config={section.config} data={data} type={section.chartType} />;
}

function StatusPanels({ data, error }) {
  const alerts = data?.alerts || [];
  if (!error && !alerts.length) return null;
  return (
    <div className="status-panels">
      {error ? <div className="status-card danger"><AlertTriangle size={18} /><span>{error}</span></div> : null}
      {alerts.slice(0, 2).map((alert, index) => <div className="status-card warning" key={index}><AlertTriangle size={18} /><span>{alert.message || alert.title || formatValue(alert)}</span></div>)}
    </div>
  );
}

function LoadingSection({ section }) {
  const isTable = section.chartType === "table";
  const isGauge = section.chartType === "gauge" || section.chartType === "summaryGauges";
  const isHeatmap = section.chartType === "heatmap" || section.chartType === "normalVsCrisis";
  if (isGauge) {
    return (
      <div className="skeleton-gauge-grid" aria-label={`${section.title} loading`}>
        {Array.from({ length: section.chartType === "summaryGauges" ? 4 : 1 }, (_, index) => <i key={index} />)}
      </div>
    );
  }
  if (isTable) {
    return (
      <div className="skeleton-table" aria-label={`${section.title} loading`}>
        {Array.from({ length: 7 }, (_, row) => (
          <div key={row}>
            {Array.from({ length: 5 }, (_, cell) => <i key={cell} />)}
          </div>
        ))}
      </div>
    );
  }
  if (isHeatmap) {
    return (
      <div className="skeleton-heatmap" aria-label={`${section.title} loading`}>
        {Array.from({ length: 64 }, (_, index) => <i key={index} />)}
      </div>
    );
  }
  return (
    <div className="skeleton-chart" aria-label={`${section.title} loading`}>
      <i />
      <i />
      <i />
      <i />
    </div>
  );
}

function InfoTooltip({ text }) {
  const [show, setShow] = useState(false);
  return (
    <div className="info-wrap">
      <button
        aria-label="Output methodology"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        type="button"
      >
        <Info size={16} />
      </button>
      {show ? <div className="info-popover">{text}</div> : null}
    </div>
  );
}

function ConstraintPill({ text }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="constraint-item">
      <button className="constraint-pill" onClick={() => setExpanded((current) => !current)} type="button">
        {text} {expanded ? "▲" : "▼"}
      </button>
      {expanded ? <div className="constraint-detail">{constraintDescriptions[text] || "Research Mode relaxes or routes this constraint through cached/asynchronous compute."}</div> : null}
    </div>
  );
}

function ImportWorkspaceButton({ onImport }) {
  const inputRef = useRef(null);
  async function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const workspace = JSON.parse(await file.text());
      if (!workspace.feature_id || !workspace.payload) throw new Error("Invalid Factors V2 workspace file.");
      onImport(workspace);
      toast.success("Workspace imported");
    } catch (err) {
      toast.error(err?.message || "Failed to import workspace");
    } finally {
      event.target.value = "";
    }
  }
  return (
    <>
      <input ref={inputRef} type="file" accept="application/json,.json" hidden onChange={handleFile} />
      <button className="ghost-button" onClick={() => inputRef.current?.click()} type="button">Import</button>
    </>
  );
}

const PINNED_SUMMARY_IDS = ["01", "04", "06", "13"];
const subscribePinnedSummaries = (onStoreChange) => {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
};
const readPinnedSummarySnapshot = () => JSON.stringify(
  PINNED_SUMMARY_IDS.map((id) => window.localStorage.getItem(`quant360:factors-v2:${id}:latest-summary`)),
);
const readEmptyPinnedSummarySnapshot = () => "[]";

function PinnedSummaryStrip() {
  const snapshot = useSyncExternalStore(
    subscribePinnedSummaries,
    readPinnedSummarySnapshot,
    readEmptyPinnedSummarySnapshot,
  );
  const metrics = useMemo(() => {
    const values = JSON.parse(snapshot);
    return PINNED_SUMMARY_IDS.flatMap((id, index) => {
      try {
        const cards = JSON.parse(values[index] || "[]");
        return (Array.isArray(cards) ? cards.slice(0, 1) : []).map((card) => ({
          id,
          label: card.label || card.name || `F${id}`,
          value: card.value ?? card.score ?? card.percentile,
          delta: card.delta,
        }));
      } catch {
        return [];
      }
    }).filter((item) => item.value != null);
  }, [snapshot]);
  if (!metrics.length) return null;
  return (
    <div className="pinned-summary-strip">
      {metrics.map((metric) => (
        <a href={`/labs/factors-v2/feature-${metric.id}`} key={metric.id}>
          <span>F{metric.id}</span>
          <b>{formatValue(metric.value)}</b>
          <small>{metric.label}</small>
          {metric.delta != null ? <DeltaLabel delta={metric.delta} /> : null}
        </a>
      ))}
    </div>
  );
}

function LiveClock({ live }) {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className={`live-dot ${live ? "live" : ""}`}>
      <i />
      <span>{live ? "LIVE" : "DORMANT API"}</span>
      <b>{time}</b>
    </div>
  );
}

function AnnotationDrawer({ annotations, sections, onClose, onReply, onResolve, onJump }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("ALL");
  const [replyText, setReplyText] = useState({});
  const sectionNames = new Map(sections.map((section) => [section.id, section.title]));
  const filtered = annotations.filter((annotation) => {
    const haystack = `${annotation.text} ${annotation.category || ""} ${sectionNames.get(annotation.chart_id) || ""} ${(annotation.thread || []).map((reply) => reply.text).join(" ")}`.toLowerCase();
    return haystack.includes(search.toLowerCase()) && (category === "ALL" || annotation.category === category);
  });
  return (
    <aside className="annotation-drawer">
      <div className="drawer-head">
        <div><p>Annotations</p><h3>Workspace notes</h3></div>
        <button aria-label="Close annotations" onClick={onClose} type="button"><X size={16} /></button>
      </div>
      <div className="annotation-filters">
        <label><Search size={14} /><input placeholder="Search notes, charts, replies..." value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          {["ALL", "QUESTION", "RISK", "SIGNAL", "ACTION"].map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      {filtered.length ? filtered.map((annotation, index) => (
        <div className={`annotation-list-item ${annotation.resolved ? "resolved" : ""}`} key={annotation.id}>
          <button className="annotation-jump" onClick={() => onJump(annotation)} type="button">
            <span className="mono">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong><i style={{ background: categoryColor(annotation.category) }} />{sectionNames.get(annotation.chart_id) || annotation.chart_id}</strong>
              <p>{annotation.text}</p>
              {annotation.data_anchor ? <small>Anchor: {formatValue(annotation.data_anchor.x)} {annotation.data_anchor.y_key ? `· ${annotation.data_anchor.y_key}: ${formatValue(annotation.data_anchor.y)}` : ""}</small> : null}
              <small>{annotation.created_at}</small>
            </div>
          </button>
          {(annotation.thread || []).length ? <div className="annotation-thread">{annotation.thread.map((reply) => <p key={reply.id}><b>{reply.author}</b>{reply.text}<small>{reply.created_at}</small></p>)}</div> : null}
          <div className="reply-box">
            <input placeholder="Reply..." value={replyText[annotation.id] || ""} onChange={(event) => setReplyText((current) => ({ ...current, [annotation.id]: event.target.value }))} />
            <button onClick={() => {
              const clean = (replyText[annotation.id] || "").trim();
              if (!clean) return;
              onReply(annotation.id, clean, annotation.chart_id);
              setReplyText((current) => ({ ...current, [annotation.id]: "" }));
            }} type="button"><Send size={13} /></button>
            <button onClick={() => onResolve(annotation.id, annotation.chart_id)} type="button"><Check size={14} /></button>
          </div>
        </div>
      )) : <div className="drawer-empty">No chart annotations match this filter. Enable annotation mode on any output card, then click the visual area.</div>}
    </aside>
  );
}

function DrillDownDrawer({ point, onClose }) {
  if (!point) return null;
  return (
    <aside className="drilldown-drawer">
      <div className="drawer-head">
        <div>
          <p>Drill-down</p>
          <h3>{point.section?.title || "Selected point"}</h3>
        </div>
        <button aria-label="Close drill-down" onClick={onClose} type="button"><X size={16} /></button>
      </div>
      <div className="drill-anchor">
        <b>{formatValue(point.anchor?.x ?? point.anchor?.index)}</b>
        {point.anchor?.y_key ? <span>{point.anchor.y_key}: {formatValue(point.anchor.y)}</span> : null}
      </div>
      <DataTable data={point.rows || []} />
    </aside>
  );
}

function PreflightIllustration() {
  return (
    <svg className="preflight-illustration" viewBox="0 0 220 150" aria-hidden="true">
      <circle cx="110" cy="82" r="58" />
      <path d="M54 96 A58 58 0 0 1 166 96" />
      <path d="M76 96 A34 34 0 0 1 144 96" />
      <line x1="110" y1="96" x2="142" y2="70" />
      <circle cx="110" cy="96" r="5" />
      <text x="110" y="132" textAnchor="middle">WAITING FOR FACTOR RUN</text>
    </svg>
  );
}


function PreflightState({ feature, loading, onRun, selectedSections }) {
  const top = (selectedSections || []).slice(0, 4);
  return (
    <section className="preflight-card preflight-v2">
      <div className="preflight-copy">
        <p>Ready</p>
        <h2>Run the factor stack</h2>
        <span>{feature.description || "Configure the contract above, then run analysis to generate the selected output book."}</span>
        <div className="preflight-types">
          {top.map((section) => <i key={section.id}>{section.title}</i>)}
        </div>
        <button className="run-button" disabled={loading} onClick={onRun} type="button">{loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />} Run analysis</button>
      </div>
      <div className="preflight-placeholders">
        {top.map((section, index) => (
          <div className="preflight-mini" key={section.id}>
            <b>{String(index + 1).padStart(2, "0")}</b>
            <span>{section.title}</span>
            <em />
          </div>
        ))}
      </div>
    </section>
  );
}

function cardNumericSignature(data) {
  const numeric = rowsFrom(data).flatMap((row) => Object.values(row || {}).map(numberLike).filter((value) => value != null));
  if (!numeric.length) return null;
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length;
}

function DrawingLayer({ enabled, resetSignal, storageKey }) {
  const canvasRef = useRef(null);
  const drawingRef = useRef(false);
  const lastRef = useRef(null);

  const fitCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    const rect = parent?.getBoundingClientRect();
    if (!canvas || !rect?.width || !rect?.height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    canvas.height = Math.max(1, Math.floor(rect.height * ratio));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = TOKENS.amber;
  }, []);

  useEffect(() => {
    fitCanvas();
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(fitCanvas);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [fitCanvas]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !storageKey) return;
    const saved = window.localStorage.getItem(storageKey);
    if (!saved) return;
    const img = new Image();
    img.onload = () => {
      const rect = canvas.getBoundingClientRect();
      ctx.drawImage(img, 0, 0, rect.width, rect.height);
    };
    img.src = saved;
  }, [storageKey]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !resetSignal) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (storageKey) window.localStorage.removeItem(storageKey);
  }, [resetSignal, storageKey]);

  const point = (event) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const save = () => {
    const canvas = canvasRef.current;
    if (canvas && storageKey) window.localStorage.setItem(storageKey, canvas.toDataURL("image/png"));
  };

  return (
    <canvas
      ref={canvasRef}
      className={`drawing-canvas ${enabled ? "enabled" : ""}`}
      onPointerDown={(event) => {
        if (!enabled) return;
        drawingRef.current = true;
        lastRef.current = point(event);
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!enabled || !drawingRef.current) return;
        const ctx = canvasRef.current.getContext("2d");
        const next = point(event);
        const prev = lastRef.current || next;
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(next.x, next.y);
        ctx.stroke();
        lastRef.current = next;
      }}
      onPointerUp={(event) => {
        if (!enabled) return;
        drawingRef.current = false;
        lastRef.current = null;
        save();
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      }}
      onPointerLeave={() => {
        if (drawingRef.current) save();
        drawingRef.current = false;
        lastRef.current = null;
      }}
      aria-hidden="true"
    />
  );
}

const AnnotatedOutputCard = memo(function AnnotatedOutputCard({ annotationMode, cardData, children, fullScreenId, isActive, loading, onAddAnnotation, onDrill, onResolve, onToggleAnnotationMode, onToggleFullscreen, previousCardData, section, sectionAnnotations = [], sections = [], style }) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawMode, setDrawMode] = useState(false);
  const [drawReset, setDrawReset] = useState(0);
  const [draft, setDraft] = useState(null);
  const [text, setText] = useState("");
  const [category, setCategory] = useState("QUESTION");
  const active = annotationMode === section.id;
  const fullScreen = fullScreenId === section.id;
  const insight = useMemo(() => generateInsight(section, cardData), [cardData, section]);
  function startDraft(event) {
    if (event.target.closest("button, textarea, input, select, a")) return;
    if (drawMode) return;
    if (!active) {
      onDrill?.({ section, anchor: nearestDataAnchor(event, cardData), rows: rowsFrom(cardData).slice(0, 80) });
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    setDraft({
      x_pct: ((event.clientX - rect.left) / rect.width) * 100,
      y_pct: ((event.clientY - rect.top) / rect.height) * 100,
      data_anchor: nearestDataAnchor(event, cardData),
    });
    setText("");
    setCategory("QUESTION");
  }
  function submitDraft() {
    const clean = text.trim();
    if (!draft || !clean) return;
    onAddAnnotation({
      id: `${section.id}-${Date.now()}`,
      chart_id: section.id,
      position: draft,
      data_anchor: draft.data_anchor,
      text: clean,
      author: "Quant360",
      category,
      created_at: new Date().toISOString(),
      resolved: false,
      thread: [],
    });
    setDraft(null);
    setText("");
  }
  function downloadPanel() {
    const payload = JSON.stringify({ section: section.id, title: section.title }, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `quant360_${section.id}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
  const linked = (section.linkedSections || [])
    .map((id) => sections.find((item) => item.id === id))
    .filter(Boolean);
  return (
    <article className={`output-card rank-${section.rank || "supporting"} ${active ? "annotating" : ""} ${fullScreen ? "fullscreen-card" : ""} ${collapsed ? "is-collapsed" : ""} ${isActive ? "is-active" : ""} ${drawMode ? "drawing" : ""}`} id={section.id} onDoubleClick={() => onToggleFullscreen(section.id)} style={style}>
      <div className="output-head">
        <div><h3>{section.title}</h3></div>
        <div className="card-actions">
          <InfoTooltip text={section.description || insight} />
          <button aria-label={`Draw on ${section.title}`} className={drawMode ? "active" : ""} onClick={() => setDrawMode((current) => !current)} type="button"><Pencil size={16} /></button>
          {drawMode ? <button aria-label={`Clear ${section.title} drawing`} onClick={() => setDrawReset((current) => current + 1)} type="button"><X size={16} /></button> : null}
          <button aria-label={`Copy ${section.title} data as TSV`} onClick={() => copyRowsAsTsv(cardData)} type="button"><Copy size={16} /></button>
          <button aria-label={`Capture ${section.title} chart as PNG`} onClick={() => captureElementAsPng(section.id)} type="button"><Camera size={16} /></button>
          <button aria-label={`Download ${section.title} metadata`} onClick={downloadPanel} type="button"><Download size={16} /></button>
          <button aria-label={`${fullScreen ? "Exit" : "Open"} fullscreen ${section.title}`} onClick={() => onToggleFullscreen(section.id)} type="button">{fullScreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
          <button className={active ? "active" : ""} aria-label={`Pin note on ${section.title}`} onClick={() => onToggleAnnotationMode(section.id)} type="button"><MessageSquare size={16} /></button>
          <button className={`collapse-button ${collapsed ? "collapsed" : ""}`} aria-label={`${collapsed ? "Expand" : "Collapse"} ${section.title}`} onClick={() => setCollapsed((current) => !current)} type="button"><ChevronDown size={16} /></button>
        </div>
      </div>
      <div className="output-card-body" aria-hidden={collapsed}>
        <div>
          <div className="annotatable-surface" onClick={startDraft}>
            {loading ? <LoadingSection section={section} /> : children}
            <DrawingLayer enabled={drawMode} resetSignal={drawReset} storageKey={`quant360:factors-v2:drawing:${section.id}`} />
            {sectionAnnotations.map((annotation, index) => (
              <button
                className={`annotation-pin ${annotation.resolved ? "resolved" : ""}`}
                key={annotation.id}
                onClick={(event) => {
                  event.stopPropagation();
                  onResolve(annotation.id, section.id);
                }}
                style={{ left: `${annotation.position.x_pct}%`, top: `${annotation.position.y_pct}%` }}
                title={annotation.text}
                type="button"
              >
                <i style={{ background: categoryColor(annotation.category) }} />
                {index + 1}
                {annotation.thread?.length ? <b>{annotation.thread.length}</b> : null}
              </button>
            ))}
            {draft ? (
              <div className="annotation-popover" style={{ left: `${draft.x_pct}%`, top: `${draft.y_pct}%` }}>
                <select aria-label="Annotation category" value={category} onChange={(event) => setCategory(event.target.value)}>
                  {["QUESTION", "RISK", "SIGNAL", "ACTION"].map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <textarea autoFocus placeholder="Add chart annotation..." value={text} onChange={(event) => setText(event.target.value)} />
                <div>
                  <button onClick={() => setDraft(null)} type="button">Cancel</button>
                  <button onClick={submitDraft} type="button">Submit</button>
                </div>
              </div>
            ) : null}
          </div>
          {linked.length ? (
            <div className="linked-sections">
              <strong>Linked outputs</strong>
              {linked.map((item) => <a className="link-btn" href={`#${item.id}`} key={item.id}>{item.title} ↗</a>)}
            </div>
          ) : null}
          {insight ? <div className="insight-bar"><span>{insight}</span></div> : null}
        </div>
      </div>
    </article>
  );
}, (previous, next) => (
  previous.annotationMode === next.annotationMode
  && previous.cardData === next.cardData
  && previous.children === next.children
  && previous.fullScreenId === next.fullScreenId
  && previous.isActive === next.isActive
  && previous.loading === next.loading
  && previous.previousCardData === next.previousCardData
  && previous.section === next.section
  && previous.sectionAnnotations === next.sectionAnnotations
  && previous.style?.animationDelay === next.style?.animationDelay
));

const OutputNav = memo(function OutputNav({ activeOutputId, annotationsCount, onAnnotationOpen, selectedSections, setActiveOutputId }) {
  const observerRef = useRef(null);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target?.id) setActiveOutputId(visible.target.id);
      },
      { rootMargin: "-12% 0px -45% 0px", threshold: [0.15, 0.35, 0.65] },
    );
    return () => observerRef.current?.disconnect();
  }, [setActiveOutputId]);

  useEffect(() => {
    const observer = observerRef.current;
    if (!observer) return undefined;
    observer.disconnect();
    selectedSections.forEach((section) => {
      const node = document.getElementById(section.id);
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [selectedSections]);

  return (
    <aside className="output-nav">
      <strong>Output map</strong>
      <div className="output-nav-track">
        {selectedSections.map((section, index) => {
          const activeIndex = selectedSections.findIndex((item) => item.id === activeOutputId);
          const state = activeOutputId === section.id ? "active" : activeIndex >= index ? "visited" : "";
          return <i className={`nav-progress-dot ${state}`} key={section.id} style={{ top: `${selectedSections.length <= 1 ? 0 : (index / (selectedSections.length - 1)) * 100}%` }} />;
        })}
      </div>
      {selectedSections.map((section, index) => (
        <a className={activeOutputId === section.id ? "active" : ""} data-title={section.title} href={`#${section.id}`} key={section.id} title={section.title}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          {section.title}
          {index < 9 ? <kbd>{index + 1}</kbd> : null}
        </a>
      ))}
      <button className="annotation-open" onClick={onAnnotationOpen} title="Annotations" type="button"><MessageSquare size={15} /><span>{annotationsCount}</span></button>
    </aside>
  );
});

export function CustomFeaturePage({ featureId, sections }) {
  const feature = useMemo(() => getFactorsV2Feature(featureId), [featureId]);
  const profileStorageKey = `quant360:factors-v2:${featureId}:output-profiles`;
  const enrichedSections = useMemo(() => enrichSections(sections, feature), [sections, feature]);
  const outputManifest = useMemo(() => buildOutputManifest(enrichedSections), [enrichedSections]);
  const [form, setForm] = useState(() => initialForm(feature));
  const [debouncedForm] = useDebounce(form, 300);
  const [data, setData] = useState(null);
  const [previousData, setPreviousData] = useState(null);
  const [error, setError] = useState("");
  const [hasRun, setHasRun] = useState(false);
  const [selectedOutputIds, setSelectedOutputIds] = useState(() => outputManifest.filter((item) => item.defaultSelected).map((item) => item.id));
  const [profiles, setProfiles] = useState([]);
  const [profileName, setProfileName] = useState("");
  const annotationsByChart = useFactorsV2AnnotationStore((state) => state.annotationsByChart);
  const addAnnotation = useFactorsV2AnnotationStore((state) => state.addAnnotation);
  const replaceAnnotations = useFactorsV2AnnotationStore((state) => state.replaceAnnotations);
  const resolveAnnotationInStore = useFactorsV2AnnotationStore((state) => state.resolveAnnotation);
  const replyAnnotationInStore = useFactorsV2AnnotationStore((state) => state.replyAnnotation);
  const [annotationMode, setAnnotationMode] = useState(null);
  const [annotationDrawerOpen, setAnnotationDrawerOpen] = useState(false);
  const [fullScreenId, setFullScreenId] = useState(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [activeOutputId, setActiveOutputId] = useState(null);
  const [elapsed, setElapsed] = useState(null);
  const [researchMode, setResearchMode] = useState(feature.defaults?.compute_mode === "research");
  const [splitMode, setSplitMode] = useState(false);
  const [secondaryForm, setSecondaryForm] = useState(() => initialForm(feature));
  const [secondaryData, setSecondaryData] = useState(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [drillPoint, setDrillPoint] = useState(null);
  const outputRef = useRef(null);
  const startRef = useRef(null);
  const stateRef = useRef({});
  const selectedSections = useMemo(() => {
    const ordered = orderedSections(enrichedSections, selectedOutputIds);
    return ordered.map((section, index) => decorateSection(section, index, ordered));
  }, [enrichedSections, selectedOutputIds]);
  const annotations = useMemo(() => Object.values(annotationsByChart || {}).flat(), [annotationsByChart]);
  const payload = useMemo(() => ({ ...payloadFromForm(feature, debouncedForm), compute_mode: researchMode ? "research" : "realtime" }), [feature, debouncedForm, researchMode]);
  const runMutation = useMutation({
    mutationFn: (nextPayload) => runFactorsV2Feature(feature.id, nextPayload),
  });
  const secondaryMutation = useMutation({
    mutationFn: (nextPayload) => runFactorsV2Feature(feature.id, nextPayload),
    onSuccess: (result) => {
      setSecondaryData(result);
      toast.success(`F${feature.id} comparison complete`);
    },
    onError: (err) => toast.error(err?.message || "Comparison run failed"),
  });
  const loading = runMutation.isPending;
  const secondaryPayload = useMemo(() => ({ ...payloadFromForm(feature, secondaryForm), compute_mode: researchMode ? "research" : "realtime" }), [feature, researchMode, secondaryForm]);
  const quickFields = useMemo(() => {
    const priority = ["compute_mode", "factor", "benchmark", "window_days", "factor_model", "method", "report_type"];
    return (feature.fields || []).filter((field) => priority.includes(field.key)).slice(0, 4);
  }, [feature]);

  useEffect(() => {
    stateRef.current = {
      annotations,
      activeOutputId,
      data,
      exportWorkspace,
      feature,
      fullScreenId,
      payload,
      run,
      selectedOutputIds,
      selectedSections,
      toggleFullscreen,
    };
  });

  useEffect(() => {
    try {
      setProfiles(JSON.parse(window.localStorage.getItem(profileStorageKey) || "[]"));
    } catch {
      setProfiles([]);
    }
  }, [profileStorageKey]);

  useEffect(() => {
    document.title = `F${feature.id} ${feature.title} — ATLAS Factor Intelligence`;
    const description = feature.description || "Quant360 institutional Factors V2 analysis workspace.";
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", description);
    let ogTitle = document.querySelector('meta[property="og:title"]');
    if (!ogTitle) {
      ogTitle = document.createElement("meta");
      ogTitle.setAttribute("property", "og:title");
      document.head.appendChild(ogTitle);
    }
    ogTitle.setAttribute("content", `${feature.title} — Quant360`);
  }, [feature]);

  function saveProfile() {
    const name = profileName.trim();
    if (!name) return;
    const next = [...profiles.filter((profile) => profile.name !== name), { name, selected_outputs: selectedOutputIds, created_at: new Date().toISOString() }];
    setProfiles(next);
    window.localStorage.setItem(profileStorageKey, JSON.stringify(next));
    setProfileName("");
  }

  function loadProfile(name) {
    const profile = profiles.find((item) => item.name === name);
    if (profile?.selected_outputs?.length) setSelectedOutputIds(profile.selected_outputs);
  }

  function toggleAnnotationMode(sectionId) {
    setAnnotationMode((current) => current === sectionId ? null : sectionId);
  }

  function resolveAnnotation(annotationId, chartId) {
    resolveAnnotationInStore(annotationId, chartId);
  }

  function replyAnnotation(annotationId, text, chartId) {
    const annotation = annotations.find((item) => item.id === annotationId);
    replyAnnotationInStore(annotationId, chartId || annotation?.chart_id, text);
  }

  function jumpToAnnotation(annotation) {
    document.getElementById(annotation.chart_id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function toggleFullscreen(sectionId) {
    setFullScreenId((current) => current === sectionId ? null : sectionId);
  }

  function exportWorkspace() {
    const blob = new Blob([JSON.stringify({ feature_id: feature.id, payload, selected_outputs: selectedOutputIds, annotations, data }, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `quant360_factors_v2_${feature.id}_workspace.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function importWorkspace(workspace) {
    const nextForm = { ...initialForm(feature) };
    for (const [key, value] of Object.entries(workspace.payload || {})) {
      if (key === "selected_outputs" || key === "compute_mode") continue;
      nextForm[key] = Array.isArray(value) ? value.join(",") : String(value ?? "");
    }
    setForm(nextForm);
    if (workspace.selected_outputs?.length) setSelectedOutputIds(workspace.selected_outputs);
    if (workspace.annotations?.length) replaceAnnotations(workspace.annotations);
    if (workspace.results_cache || workspace.data) {
      setData(workspace.results_cache || workspace.data);
      setHasRun(true);
    }
    setResearchMode((workspace.payload || {}).compute_mode === "research");
  }

  useEffect(() => {
    const handler = (event) => {
      const current = stateRef.current;
      const key = event.key.toLowerCase();
      if ((event.metaKey || event.ctrlKey) && key === "r") {
        event.preventDefault();
        current.run?.();
      }
      if ((event.metaKey || event.ctrlKey) && key === "e") {
        event.preventDefault();
        current.exportWorkspace?.();
      }
      if ((event.metaKey || event.ctrlKey) && key === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
      if ((event.metaKey || event.ctrlKey) && key === "b") {
        event.preventDefault();
        setSplitMode((current) => !current);
      }
      if (key === "f" && !event.metaKey && !event.ctrlKey && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        const first = current.selectedSections?.[0]?.id;
        if (first) current.toggleFullscreen?.(current.fullScreenId || first);
      }
      const num = Number(event.key);
      if (num >= 1 && num <= 9 && current.selectedSections?.[num - 1]) {
        document.getElementById(current.selectedSections[num - 1].id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if ((key === "j" || event.key === "ArrowDown" || key === "k" || event.key === "ArrowUp") && !event.metaKey && !event.ctrlKey && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        event.preventDefault();
        const sectionsForNav = current.selectedSections || [];
        const currentIndex = Math.max(0, sectionsForNav.findIndex((section) => section.id === current.activeOutputId));
        const nextIndex = key === "j" || event.key === "ArrowDown"
          ? Math.min(sectionsForNav.length - 1, currentIndex + 1)
          : Math.max(0, currentIndex - 1);
        const next = sectionsForNav[nextIndex];
        if (next) document.getElementById(next.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  async function run() {
    startRef.current = performance.now();
    setElapsed(null);
    setHasRun(true);
    setError("");
    setConfigOpen(false);
    window.requestAnimationFrame(() => outputRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    try {
      const result = await runMutation.mutateAsync(payload);
      setPreviousData(data);
      setData(result);
      window.localStorage.setItem(`quant360:factors-v2:${feature.id}:last-run`, Date.now().toString());
      window.localStorage.setItem(`quant360:factors-v2:${feature.id}:latest-summary`, JSON.stringify(result?.summary_cards || []));
      toast.success(`F${feature.id} analysis complete`);
    } catch (err) {
      setError(err?.message || "Factors V2 request failed.");
      toast.error(err?.message || "Factors V2 API error");
    } finally {
      if (startRef.current != null) setElapsed(((performance.now() - startRef.current) / 1000).toFixed(1));
    }
  }

  const headlineMetric = data?.summary_cards?.[0];
  const commandItems = [
    { label: "Run analysis", hint: "Cmd+R", action: run },
    { label: "Export workspace", hint: "Cmd+E", action: exportWorkspace },
    { label: `${researchMode ? "Disable" : "Enable"} Research Mode`, hint: "R", action: () => setResearchMode((current) => !current) },
    ...["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14"].map((id) => ({ label: `Open Factor Feature F${id}`, hint: `F${id}`, action: () => { window.location.href = `/labs/factors-v2/feature-${id}`; } })),
  ];
  const visibleCommands = commandItems.filter((item) => item.label.toLowerCase().includes(commandQuery.toLowerCase())).slice(0, 12);
  const regimeStatus = useMemo(() => {
    const cards = rowsFrom(data?.summary_cards);
    const label = `${cards[0]?.label || cards[0]?.name || feature.title}`.toUpperCase();
    const value = numberLike(cards[0]?.value ?? cards[0]?.score ?? cards[0]?.percentile);
    if (!data) return { label: "IDLE", color: TOKENS.amber, state: "idle" };
    if (value != null && value >= 70) return { label: `${label}: ELEVATED`, color: TOKENS.red, state: "elevated" };
    if (value != null && value >= 45) return { label: `${label}: WATCH`, color: TOKENS.amber, state: "watch" };
    return { label: `${label}: NORMAL`, color: TOKENS.green, state: "normal" };
  }, [data, feature.title]);

  return (
    <main className="f2-page" style={{ "--regime-border": regimeStatus.color }}>
      <style jsx global>{styles}</style>
      <section className="f2-topbar">
        <div className="topbar-brand"><strong>ATLAS</strong><span>F{feature.id} · {feature.title}</span></div>
        <div className="topbar-spacer" />
        {data ? <div className="regime-pill" data-state={regimeStatus.state}><i />{regimeStatus.label}</div> : null}
        <button className={`topbar-btn ${researchMode ? "active" : ""}`} onClick={() => setResearchMode((current) => !current)} title="Research Mode" type="button">RM</button>
        <button className={`topbar-btn ${splitMode ? "active" : ""}`} onClick={() => setSplitMode((current) => !current)} title="Split comparison" type="button">⊟</button>
        <LiveClock live={Boolean(data && !error)} />
      </section>
      <PinnedSummaryStrip />

      <header className="f2-hero">
        <div>
          <p>Feature {feature.id}</p>
          <h1>{feature.title}</h1>
          <span>{feature.description}</span>
        </div>
        <div className="hero-meta">
          <b style={{ color: data ? TOKENS.green : TOKENS.amber }}>{data ? "COMPUTED" : payload.compute_mode || "realtime"}</b>
          <span>{data && headlineMetric ? `${headlineMetric.label || headlineMetric.name || "Primary metric"}: ${formatValue(headlineMetric.value ?? headlineMetric.score ?? headlineMetric.percentile)}` : "Realtime caps are enforced. Research Mode unlocks explicit expensive diagnostics and cached outputs."}</span>
        </div>
      </header>

      {hasRun ? (
        <section className="input-summary-strip">
          <strong>Input contract</strong>
          <span>F{feature.id} · {feature.title}</span>
          <button className="ghost-button" onClick={() => setConfigOpen(true)} type="button">Edit inputs</button>
          <button disabled={loading} onClick={run} type="button">{elapsed ? `Run again (${elapsed}s)` : "Run again"}</button>
        </section>
      ) : null}

      {!hasRun ? (
        <section className="config-card">
          <div className="section-head">
            <div><p>Configuration</p><h2>Input contract</h2></div>
            <div className="header-actions">
              <ImportWorkspaceButton onImport={importWorkspace} />
              <button className="ghost-button" onClick={exportWorkspace} type="button">Export</button>
              <button className="run-button" disabled={loading} onClick={run} type="button">{loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />} Run analysis</button>
            </div>
          </div>
          <GroupedInputForm feature={feature} form={form} onChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))} />
          {feature.constraints?.length ? <div className="constraint-row">{feature.constraints.map((item) => <ConstraintPill key={item} text={item} />)}</div> : null}
        </section>
      ) : null}

      {configOpen ? (
        <div className="input-curtain" onClick={() => setConfigOpen(false)}>
          <section className="config-card curtain-card" onClick={(event) => event.stopPropagation()}>
            <div className="section-head">
              <div><p>Configuration</p><h2>Input contract</h2></div>
              <div className="header-actions">
                <ImportWorkspaceButton onImport={importWorkspace} />
                <button className="ghost-button" onClick={exportWorkspace} type="button">Export</button>
                <button className="ghost-button" onClick={() => setConfigOpen(false)} type="button">Close</button>
                <button className="run-button" disabled={loading} onClick={run} type="button">{loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />} Run analysis</button>
              </div>
            </div>
            <GroupedInputForm feature={feature} form={form} onChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))} />
            {feature.constraints?.length ? <div className="constraint-row">{feature.constraints.map((item) => <ConstraintPill key={item} text={item} />)}</div> : null}
          </section>
        </div>
      ) : null}

      <OutputConfigurator
        loadProfile={loadProfile}
        manifest={outputManifest}
        profileName={profileName}
        profiles={profiles}
        saveProfile={saveProfile}
        selectedOutputIds={selectedOutputIds}
        setProfileName={setProfileName}
        setSelectedOutputIds={setSelectedOutputIds}
      />

      <StatusPanels data={data} error={error} />

      {!hasRun ? (
        <div ref={outputRef}><PreflightState feature={feature} loading={loading} onRun={run} selectedSections={selectedSections} /></div>
      ) : (
      <section className={`output-layout ${splitMode ? "split" : ""}`} ref={outputRef}>
        <OutputNav
          activeOutputId={activeOutputId}
          annotationsCount={annotations.length}
          onAnnotationOpen={() => setAnnotationDrawerOpen(true)}
          selectedSections={selectedSections}
          setActiveOutputId={setActiveOutputId}
        />
        <ChartSyncProvider>
        <div className="output-stack">
          {selectedSections.map((section, index) => (
            <AnnotatedOutputCard
              annotationMode={annotationMode}
              cardData={pickData(data, section)}
              fullScreenId={fullScreenId}
              isActive={activeOutputId === section.id}
              key={section.id}
              loading={loading && !data}
              onAddAnnotation={addAnnotation}
              onDrill={setDrillPoint}
              onResolve={resolveAnnotation}
              onToggleAnnotationMode={toggleAnnotationMode}
              onToggleFullscreen={toggleFullscreen}
              previousCardData={pickData(previousData, section)}
              section={section}
              sectionAnnotations={annotationsByChart[section.id] || []}
              sections={selectedSections}
              style={{ animationDelay: `${index * 60}ms` }}
            >
              <RenderFeatureSection response={data} section={section} />
            </AnnotatedOutputCard>
          ))}
        </div>
        </ChartSyncProvider>
        {splitMode ? (
          <div className="secondary-stack">
            <div className="secondary-controls">
              <b>Comparison inputs</b>
              {quickFields.map((field) => (
                <FieldControl compact field={field} key={field.key} value={secondaryForm[field.key]} onChange={(value) => setSecondaryForm((current) => ({ ...current, [field.key]: value }))} />
              ))}
              <button className="run-button small" disabled={secondaryMutation.isPending} onClick={() => secondaryMutation.mutate(secondaryPayload)} type="button">{secondaryMutation.isPending ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Run comparison</button>
            </div>
            {selectedSections.map((section, index) => (
              <AnnotatedOutputCard
                annotationMode={annotationMode}
                cardData={pickData(secondaryData, section)}
                fullScreenId={fullScreenId}
                isActive={activeOutputId === section.id}
                key={`secondary-${section.id}`}
                loading={secondaryMutation.isPending && !secondaryData}
                onAddAnnotation={addAnnotation}
                onDrill={setDrillPoint}
                onResolve={resolveAnnotation}
                onToggleAnnotationMode={toggleAnnotationMode}
                onToggleFullscreen={toggleFullscreen}
                previousCardData={pickData(data, section)}
                section={{ ...section, id: `secondary-${section.id}`, title: `${section.title} — comparison` }}
                sectionAnnotations={annotationsByChart[`secondary-${section.id}`] || []}
                sections={selectedSections}
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <RenderFeatureSection response={secondaryData} section={section} />
              </AnnotatedOutputCard>
            ))}
          </div>
        ) : null}
      </section>
      )}
      {annotationDrawerOpen ? <AnnotationDrawer annotations={annotations} onClose={() => setAnnotationDrawerOpen(false)} onJump={jumpToAnnotation} onReply={replyAnnotation} onResolve={resolveAnnotation} sections={enrichedSections} /> : null}
      {commandOpen ? (
        <Command.Dialog className="command-overlay" label="Factors V2 commands" onOpenChange={setCommandOpen} open={commandOpen}>
          <div className="command-palette">
            <Command.Input autoFocus placeholder="Search features, actions, exports..." value={commandQuery} onValueChange={setCommandQuery} />
            <Command.List>
              <Command.Empty>No matching commands.</Command.Empty>
              <Command.Group heading="Workspace">
                {visibleCommands.slice(0, 3).map((item) => (
                  <Command.Item key={item.label} onSelect={() => { item.action(); setCommandOpen(false); }}>
                    <span>{item.label}</span><kbd>{item.hint}</kbd>
                  </Command.Item>
                ))}
              </Command.Group>
              <Command.Group heading="Features">
                {visibleCommands.slice(3).map((item) => (
                  <Command.Item key={item.label} onSelect={() => { item.action(); setCommandOpen(false); }}>
                    <span>{item.label}</span><kbd>{item.hint}</kbd>
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </div>
        </Command.Dialog>
      ) : null}
      <DrillDownDrawer point={drillPoint} onClose={() => setDrillPoint(null)} />
    </main>
  );
}

const styles = `
  @font-face { font-family: "Quant360 Inter"; src: url("/fonts/inter-5.woff2") format("woff2"); font-weight: 400 800; font-style: normal; font-display: swap; }
  @font-face { font-family: "Quant360 Mono"; src: url("/fonts/jetbrains-5.woff2") format("woff2"); font-weight: 400 800; font-style: normal; font-display: swap; }
  body { background: ${TOKENS.page}; }
  .f2-page { min-height: 100dvh; background: ${TOKENS.page}; color: ${TOKENS.text}; font-family: "Quant360 Inter", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 24px clamp(16px, 3vw, 40px) 56px; }
  .mono, .f2-table td:not(:first-child), .metric-card strong, .progress-row b, .heatmap-cell { font-family: "Quant360 Mono", "JetBrains Mono", "Fira Code", Consolas, monospace; font-variant-numeric: tabular-nums slashed-zero; font-feature-settings: "tnum", "zero"; }
  .f2-topbar { height: 54px; display: flex; align-items: center; justify-content: space-between; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.panel}; border-radius: 10px; padding: 0 18px; position: sticky; top: 12px; z-index: 4; box-shadow: 0 8px 28px rgba(0,0,0,0.35); }
  .f2-topbar div:first-child { display: flex; gap: 10px; align-items: center; letter-spacing: .12em; font-size: 12px; }
  .f2-topbar strong { color: ${TOKENS.amber}; }
  .f2-topbar span, .f2-topbar nav { color: ${TOKENS.secondary}; }
  .f2-topbar nav { display: flex; gap: 26px; font-size: 11px; letter-spacing: .14em; }
  .live-dot { display: flex; gap: 8px; align-items: center; color: ${TOKENS.secondary}; font-size: 11px; letter-spacing: .1em; }
  .live-dot i { width: 7px; height: 7px; border-radius: 999px; background: ${TOKENS.amber}; display: inline-block; }
  .live-dot.live i { background: ${TOKENS.green}; box-shadow: 0 0 12px rgba(63,185,80,.5); }
  .live-dot b { color: ${TOKENS.text}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0; }
  .regime-indicator { min-height: 30px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; border-radius: 999px; padding: 0 12px; display: inline-flex; align-items: center; gap: 8px; font-size: 10px; font-weight: 800; letter-spacing: .12em; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--regime-border) 24%, transparent); }
  .regime-indicator i { width: 7px; height: 7px; border-radius: 999px; display: inline-block; box-shadow: 0 0 12px var(--regime-border); }
  .split-toggle { min-height: 30px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; border-radius: 999px; padding: 0 12px; font-size: 10px; font-weight: 800; letter-spacing: .12em; cursor: pointer; }
  .split-toggle.active { color: ${TOKENS.accent}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.1); }
  .pinned-summary-strip { position: sticky; top: 78px; z-index: 3; margin-top: 10px; display: flex; gap: 8px; overflow-x: auto; padding: 8px; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 10px; background: rgba(13,17,23,.82); backdrop-filter: blur(14px); }
  .pinned-summary-strip:empty { display: none; }
  .pinned-summary-strip a { min-width: 170px; text-decoration: none; color: ${TOKENS.text}; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 9px 11px; display: grid; grid-template-columns: auto 1fr; gap: 3px 8px; align-items: baseline; }
  .pinned-summary-strip span { color: ${TOKENS.accent}; font: 800 10px "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: .12em; }
  .pinned-summary-strip b { font: 800 16px "Quant360 Mono", "JetBrains Mono", monospace; text-align: right; }
  .pinned-summary-strip small { grid-column: 1 / -1; color: ${TOKENS.secondary}; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .f2-hero { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: end; padding: 52px 0 28px; border-bottom: 1px solid ${TOKENS.borderSubtle}; }
  .f2-hero p, .section-head p, .output-head p { color: ${TOKENS.amber}; text-transform: uppercase; letter-spacing: .16em; font-size: 11px; margin: 0 0 10px; font-weight: 700; }
  .f2-hero h1 { font-size: clamp(34px, 5vw, 64px); line-height: .95; letter-spacing: -0.02em; margin: 0 0 14px; max-width: 940px; }
  .f2-hero span { color: ${TOKENS.secondary}; font-size: 15px; max-width: 760px; display: block; line-height: 1.65; }
  .hero-meta { background: ${TOKENS.panel}; border: 1px solid ${TOKENS.border}; border-radius: 10px; padding: 18px; }
  .hero-meta b { color: ${TOKENS.green}; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; display: block; margin-bottom: 8px; }
  .hero-meta span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.5; }

  .input-summary-strip { position: sticky; top: 78px; z-index: 3; margin: 16px 0 0; min-height: 42px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; background: rgba(13,17,23,.92); backdrop-filter: blur(14px); border: 1px solid ${TOKENS.border}; border-radius: 9px; padding: 9px 12px; box-shadow: 0 12px 30px rgba(0,0,0,.28); }
  .input-summary-strip strong { color: ${TOKENS.amber}; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
  .input-summary-strip span { color: ${TOKENS.secondary}; font-size: 12px; }
  .input-summary-strip b { color: ${TOKENS.text}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .input-summary-strip button { margin-left: auto; min-height: 30px; border: 1px solid rgba(245,164,0,.45); background: ${TOKENS.accent}; color: white; border-radius: 7px; padding: 0 12px; font-weight: 700; cursor: pointer; }
  .fullscreen-card { position: fixed; inset: 22px; z-index: 30; overflow: auto; box-shadow: 0 24px 80px rgba(0,0,0,.68); }
  .fullscreen-card .annotatable-surface { min-height: calc(100dvh - 220px); }
  .insight-bar { margin-top: 18px; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 14px; display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 12px; align-items: start; color: ${TOKENS.secondary}; line-height: 1.55; font-size: 13px; }
  .insight-bar strong { color: ${TOKENS.amber}; font-size: 11px; letter-spacing: .12em; }

  .mfg-panel { display: grid; gap: 18px; }
  .mfg-extremes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .mfg-extreme-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 14px 16px; display: grid; gap: 4px; }
  .mfg-extreme-card.red { border-color: rgba(239,68,68,.36); background: rgba(239,68,68,.07); }
  .mfg-extreme-card.green { border-color: rgba(34,197,94,.36); background: rgba(34,197,94,.07); }
  .mfg-extreme-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .mfg-extreme-card strong { font-size: 18px; color: ${TOKENS.text}; }
  .mfg-extreme-card b { font-size: 13px; }
  .mfg-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
  .mfg-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px; display: grid; gap: 8px; position: relative; overflow: hidden; transition: border-color .15s ease; }
  .mfg-card.status-stretched { border-color: rgba(239,68,68,.32); }
  .mfg-card.status-cheap { border-color: rgba(34,197,94,.32); }
  .mfg-card:hover { border-color: rgba(245,164,0,.4); }
  .mfg-bar-track { height: 6px; background: ${TOKENS.active}; border-radius: 999px; position: relative; overflow: visible; }
  .mfg-bar-fill { height: 100%; border-radius: 999px; transition: width .6s cubic-bezier(.4,0,.2,1); }
  .mfg-threshold { position: absolute; top: -3px; width: 1px; height: 12px; background: ${TOKENS.borderSubtle}; }
  .mfg-card-body { display: grid; gap: 4px; }
  .mfg-factor-name { color: ${TOKENS.text}; font-size: 12px; font-weight: 700; padding-right: 70px; }
  .mfg-pct { font-size: 26px; font-weight: 800; line-height: 1; }
  .mfg-pct sup { font-size: 12px; vertical-align: super; }
  .mfg-implied { font-size: 11px; }
  .mfg-delta { display: flex; align-items: center; gap: 6px; }
  .mfg-delta small { color: ${TOKENS.muted}; font-size: 10px; }
  .mfg-badge { position: absolute; top: 8px; right: 8px; color: #050505; font-size: 8px; font-weight: 900; letter-spacing: .14em; border-radius: 3px; padding: 3px 5px; }

  .alert-feed { display: grid; gap: 10px; }
  .alert-feed-header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .alert-feed-count { color: ${TOKENS.amber}; font-family: "Quant360 Mono","JetBrains Mono",monospace; font-size: 11px; font-weight: 800; }
  .alert-feed-filters { display: flex; gap: 6px; }
  .alert-feed-filters button { height: 24px; padding: 0 8px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 4px; font-size: 9px; font-weight: 800; letter-spacing: .1em; cursor: pointer; }
  .alert-feed-filters button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .alert-list { display: grid; gap: 8px; }
  .alert-row { display: grid; grid-template-columns: 10px 1fr; gap: 10px; align-items: start; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 10px 12px; }
  .alert-row.resolved { opacity: .55; }
  .alert-dot { width: 8px; height: 8px; border-radius: 999px; margin-top: 4px; flex-shrink: 0; }
  .alert-content { display: grid; gap: 3px; }
  .alert-content strong { color: ${TOKENS.text}; font-size: 13px; }
  .alert-content span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.4; }
  .alert-meta { display: flex; align-items: center; gap: 10px; margin-top: 4px; flex-wrap: wrap; }
  .alert-meta small { color: ${TOKENS.muted}; font-size: 10px; }
  .resolved-badge { color: ${TOKENS.green}; font-size: 9px; font-weight: 800; letter-spacing: .1em; border: 1px solid rgba(34,197,94,.3); border-radius: 3px; padding: 1px 5px; font-style: normal; }
  .alert-empty { color: ${TOKENS.muted}; font-size: 12px; padding: 16px; border: 1px dashed ${TOKENS.border}; border-radius: 7px; }

  .annotated-ts { display: grid; gap: 14px; }
  .crisis-legend { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 8px; border-top: 1px solid ${TOKENS.borderSubtle}; }
  .crisis-chip { display: flex; align-items: center; gap: 6px; border: 1px solid rgba(245,164,0,.24); background: rgba(245,164,0,.06); border-radius: 5px; padding: 5px 9px; }
  .crisis-chip i { width: 6px; height: 6px; border-radius: 999px; background: ${TOKENS.amber}; flex-shrink: 0; }
  .crisis-chip span { color: ${TOKENS.secondary}; font-size: 10px; }
  .crisis-chip b { font-size: 10px; color: ${TOKENS.text}; }
  .crisis-chip em { color: ${TOKENS.amber}; font-size: 10px; font-style: normal; font-family: "Quant360 Mono","JetBrains Mono",monospace; }

  .rolling-heatmap { display: grid; gap: 10px; }
  .rolling-controls { display: flex; align-items: center; gap: 8px; padding: 8px; background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 7px; flex-wrap: wrap; }
  .rolling-controls button { min-width: 28px; height: 28px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 5px; cursor: pointer; font-size: 10px; font-weight: 800; display: grid; place-items: center; padding: 0 8px; }
  .rolling-controls button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .rolling-scrubber { flex: 1; min-width: 160px; }
  .rolling-scrubber input[type="range"] { width: 100%; accent-color: ${TOKENS.accent}; }
  .rolling-date { color: ${TOKENS.text}; font-size: 11px; white-space: nowrap; }
  .rolling-count { color: ${TOKENS.muted}; font-size: 10px; }

  .regime-trend-panel { display: grid; gap: 13px; }
  .regime-stack-label { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .14em; font-weight: 800; }
  .regime-stack { display: flex; height: 14px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; border: 1px solid ${TOKENS.borderSubtle}; }
  .regime-stack i { display: block; height: 100%; min-width: 1px; }
  .regime-trend-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
  .regime-trend-card { border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 11px; display: grid; gap: 5px; }
  .regime-trend-card span { color: ${TOKENS.secondary}; display: flex; align-items: center; gap: 7px; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; }
  .regime-trend-card span i { width: 8px; height: 8px; border-radius: 999px; }
  .regime-trend-card b { color: ${TOKENS.text}; font-size: 22px; }
  .regime-trend-card small { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; }

  .decile-return-panel { display: grid; gap: 10px; }
  .decile-ribbon { display: flex; flex-wrap: wrap; gap: 6px; }
  .decile-ribbon span { border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 999px; padding: 5px 8px; font-size: 10px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .hierarchical-heatmap { display: grid; gap: 9px; }
  .hierarchy-note { display: flex; align-items: center; justify-content: space-between; gap: 8px; border: 1px solid ${TOKENS.borderSubtle}; background: rgba(245,164,0,.05); border-radius: 7px; padding: 8px 10px; }
  .hierarchy-note span { color: ${TOKENS.secondary}; font-size: 11px; }
  .hierarchy-note b { color: ${TOKENS.amber}; font-size: 10px; letter-spacing: .12em; }

  .config-card, .output-configurator, .output-card { position: relative; background: ${TOKENS.panel}; border: 1px solid ${TOKENS.border}; border-radius: 12px; padding: 24px; overflow: hidden; }
  .config-card::before, .output-configurator::before, .output-card::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 1px; background: linear-gradient(90deg, transparent, rgba(245,164,0,.55), transparent); pointer-events: none; }
  .config-card { margin-top: 28px; }
  .output-configurator { margin-top: 18px; }
  .section-head, .output-head { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 22px; }
  .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
  .section-head h2, .output-head h3 { margin: 0; font-size: 22px; letter-spacing: -0.01em; }
  .output-head span { color: ${TOKENS.secondary}; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 999px; padding: 6px 10px; font-size: 11px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .run-button, .pdf-button { min-height: 44px; border: 1px solid rgba(245,164,0,.45); background: ${TOKENS.accent}; color: white; border-radius: 8px; padding: 0 18px; display: inline-flex; gap: 10px; align-items: center; justify-content: center; font-weight: 700; cursor: pointer; transition: transform .2s ease, background .2s ease; }
  .run-button.small { width: 100%; min-height: 38px; padding: 0 12px; font-size: 12px; }
  .ghost-button { min-height: 38px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; border-radius: 7px; padding: 0 12px; font-weight: 700; cursor: pointer; }
  .run-button:active, .pdf-button:active { transform: translateY(1px) scale(.99); }
  .run-button:disabled, .pdf-button:disabled { cursor: not-allowed; opacity: .65; background: ${TOKENS.active}; color: ${TOKENS.secondary}; border-color: ${TOKENS.border}; }
  .spin { animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 22px; }
  .grouped-input-form { display: grid; gap: 14px; }
  .input-group { border: 1px solid ${TOKENS.borderSubtle}; background: rgba(22,27,34,.55); border-radius: 10px; padding: 14px; display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 16px; align-items: start; }
  .input-group > div:first-child p { margin: 0 0 6px; color: ${TOKENS.amber}; font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
  .input-group > div:first-child span { color: ${TOKENS.secondary}; font-size: 11px; }
  .input-group-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px 16px; }
  .field { display: grid; grid-template-columns: 210px minmax(0, 1fr); gap: 12px 18px; align-items: center; }
  .field.wide { grid-column: 1 / -1; align-items: start; }
  .field.compact { display: grid; grid-template-columns: 1fr; gap: 6px; margin-bottom: 10px; }
  .field span { color: ${TOKENS.text}; font-size: 13px; font-weight: 700; }
  .field.compact span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .field input, .field select, .field textarea { width: 100%; min-height: 44px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; border-radius: 7px; padding: 10px 12px; outline: none; font-size: 13px; }
  .field.compact input, .field.compact select { min-height: 36px; padding: 7px 9px; font-size: 12px; }
  .field textarea { min-height: 96px; resize: vertical; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .field input:focus, .field select:focus, .field textarea:focus { border-color: ${TOKENS.accent}; box-shadow: 0 0 0 3px rgba(245,164,0,.14); }
  .field small { grid-column: 2; color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.45; }
  .smart-field { display: grid; gap: 8px; }
  .smart-field > span { color: ${TOKENS.text}; font-size: 12px; font-weight: 800; display: flex; justify-content: space-between; gap: 12px; }
  .smart-field > span b { color: ${TOKENS.accent}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .smart-field small { color: ${TOKENS.secondary}; line-height: 1.45; font-size: 11px; }
  .smart-field input[type="range"] { width: 100%; accent-color: ${TOKENS.accent}; }
  .range-meta { display: flex; justify-content: space-between; color: ${TOKENS.muted}; font-size: 10px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip-row button { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 999px; min-height: 32px; padding: 0 11px; font-size: 11px; font-weight: 800; cursor: pointer; }
  .chip-row button.active { color: white; border-color: rgba(245,164,0,.55); background: ${TOKENS.accent}; }
  .constraint-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 20px; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 16px; align-items: flex-start; }
  .constraint-item { max-width: 360px; }
  .constraint-pill { color: ${TOKENS.amber}; background: rgba(210,153,34,.08); border: 1px solid rgba(210,153,34,.24); border-radius: 999px; padding: 7px 10px; font-size: 11px; cursor: pointer; }
  .constraint-detail { margin-top: 7px; padding: 9px 11px; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 7px; background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.5; }
  .profile-tools { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
  .profile-tools select, .profile-tools input { min-height: 38px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; border-radius: 7px; padding: 8px 10px; font-size: 12px; }
  .config-actions { display: flex; gap: 8px; align-items: center; margin: -4px 0 16px; }
  .config-actions button { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; border-radius: 999px; padding: 7px 11px; cursor: pointer; font-size: 12px; }
  .config-actions span { margin-left: auto; color: ${TOKENS.secondary}; font-size: 12px; }
  .output-manifest { display: grid; gap: 10px; }
  .manifest-row { display: grid; grid-template-columns: 30px 20px minmax(0, 1fr) 76px; gap: 10px; align-items: center; background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; opacity: .64; transition: border-color .15s ease, opacity .15s ease, transform .15s ease; }
  .manifest-row.selected { opacity: 1; border-color: rgba(245,164,0,.36); }
  .manifest-row[draggable="true"] { cursor: grab; }
  .manifest-row[draggable="true"]:active { cursor: grabbing; transform: scale(.997); }
  .manifest-row strong { color: ${TOKENS.text}; display: block; font-size: 13px; margin-bottom: 4px; }
  .manifest-row p { color: ${TOKENS.secondary}; margin: 0 0 5px; line-height: 1.35; font-size: 12px; }
  .manifest-row small { color: ${TOKENS.muted}; font-size: 11px; }
  .check-toggle { width: 26px; height: 26px; border-radius: 6px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.green}; display: grid; place-items: center; cursor: pointer; }
  .drag-handle { color: ${TOKENS.muted}; }
  .cost { justify-self: end; color: ${TOKENS.secondary}; background: ${TOKENS.input}; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 999px; padding: 6px 8px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 10px; }
  .cost-4, .cost-5 { color: ${TOKENS.amber}; border-color: rgba(210,153,34,.32); }
  .status-panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin: 18px 0 28px; }
  .status-card { min-height: 48px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px 14px; display: flex; align-items: center; gap: 10px; color: ${TOKENS.secondary}; font-size: 13px; }
  .status-card svg { color: ${TOKENS.green}; flex: none; }
  .status-card b { margin-left: auto; color: ${TOKENS.text}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .status-card.warning svg { color: ${TOKENS.amber}; }
  .status-card.danger { border-color: rgba(248,81,73,.42); color: ${TOKENS.red}; }
  .status-card.danger svg { color: ${TOKENS.red}; }
  .output-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 24px; align-items: start; }
  .output-layout.split { grid-template-columns: 220px minmax(0, 1fr) minmax(0, 1fr); }
  .output-nav { position: sticky; top: 82px; background: ${TOKENS.panel}; border: 1px solid ${TOKENS.border}; border-radius: 12px; padding: 14px; max-height: calc(100dvh - 104px); overflow: auto; }
  .output-nav { position: sticky; }
  .output-nav-track { position: absolute; left: 13px; top: 58px; bottom: 178px; width: 2px; background: ${TOKENS.border}; pointer-events: none; }
  .nav-progress-dot { position: absolute; left: -3px; width: 8px; height: 8px; border-radius: 999px; border: 2px solid ${TOKENS.border}; background: ${TOKENS.panel}; transform: translateY(-50%); transition: background .2s ease, border-color .2s ease, box-shadow .2s ease; }
  .nav-progress-dot.visited { background: ${TOKENS.accent}; border-color: ${TOKENS.accent}; }
  .nav-progress-dot.active { background: ${TOKENS.accent}; border-color: ${TOKENS.accent}; box-shadow: 0 0 10px rgba(245,164,0,.5); animation: navPulse 2s ease-in-out infinite; }
  @keyframes navPulse { 0%,100% { transform: translateY(-50%) scale(1); opacity: .9; } 50% { transform: translateY(-50%) scale(1.35); opacity: 1; } }
  .output-nav strong { display: block; color: ${TOKENS.text}; font-size: 12px; letter-spacing: .14em; text-transform: uppercase; margin: 4px 4px 12px; }
  .output-nav a { display: grid; grid-template-columns: 34px 1fr auto; gap: 10px; align-items: center; min-height: 44px; color: ${TOKENS.secondary}; text-decoration: none; border-radius: 7px; padding: 6px 9px; font-size: 12px; line-height: 1.35; }
  .output-nav a:hover, .output-nav a.active { background: ${TOKENS.active}; color: ${TOKENS.text}; box-shadow: inset 2px 0 0 ${TOKENS.accent}; }
  .output-nav span { font-family: "Quant360 Mono", "JetBrains Mono", monospace; color: ${TOKENS.accent}; }
  .output-nav kbd { justify-self: end; min-width: 20px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.muted}; border-radius: 4px; padding: 1px 5px; text-align: center; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 9px; }
  .annotation-open { width: 100%; margin-top: 12px; min-height: 36px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; border-radius: 7px; padding: 0 10px; cursor: pointer; font-size: 12px; }
  .annotation-open span { color: ${TOKENS.amber}; margin-left: auto; }
  .output-stack { display: grid; gap: 24px; min-width: 0; }
  .secondary-stack { min-width: 0; border-left: 1px solid ${TOKENS.border}; padding-left: 20px; display: grid; gap: 18px; }
  .secondary-controls { background: ${TOKENS.panel}; border: 1px solid ${TOKENS.border}; border-radius: 10px; padding: 14px; display: grid; gap: 10px; }
  .secondary-controls b { color: ${TOKENS.amber}; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
  .output-card { opacity: 0; animation: outputReveal .3s ease both; }
  .output-card.rank-primary { border-color: rgba(245,164,0,.5); box-shadow: 0 0 0 1px rgba(245,164,0,.1), 0 18px 52px rgba(0,0,0,.3); }
  .output-card.rank-primary::before { height: 2px; background: linear-gradient(90deg, transparent, rgba(245,164,0,.9), transparent); }
  .output-card.rank-contextual { background: color-mix(in srgb, ${TOKENS.panel} 86%, ${TOKENS.page}); }
  .output-card.rank-contextual .annotatable-surface { opacity: .94; }
  .output-card:hover { border-color: rgba(245,164,0,.28); box-shadow: 0 0 0 1px rgba(245,164,0,.08), 0 14px 42px rgba(0,0,0,.28); }
  .output-card.is-active { border-left: 2px solid ${TOKENS.accent}; box-shadow: inset 2px 0 0 rgba(245,164,0,.38); }
  @keyframes outputReveal { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
  .card-actions { display: flex; align-items: center; gap: 8px; }
  .card-actions button { width: 32px; height: 32px; border-radius: 7px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; display: grid; place-items: center; cursor: pointer; }
  .card-actions button:has(+ *) { font-size: 8px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-weight: 800; }
  .card-actions button.active { color: ${TOKENS.amber}; border-color: rgba(210,153,34,.42); background: rgba(210,153,34,.1); }
  .collapse-button svg { transition: transform .2s ease; }
  .collapse-button.collapsed svg { transform: rotate(-90deg); }
  .output-card.is-collapsed { padding-bottom: 10px; }
  .output-card-body { display: grid; grid-template-rows: 1fr; transition: grid-template-rows .3s cubic-bezier(.4,0,.2,1), opacity .2s ease; }
  .output-card-body > div { min-height: 0; overflow: hidden; }
  .output-card.is-collapsed .output-card-body { grid-template-rows: 0fr; opacity: 0; }
  .output-card.is-collapsed .annotatable-surface { visibility: hidden; }
  .output-head { cursor: pointer; }
  .info-wrap { position: relative; }
  .info-popover { position: absolute; right: 0; top: calc(100% + 8px); width: 260px; z-index: 8; background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.border}; border-radius: 6px; padding: 10px 12px; color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.55; box-shadow: 0 8px 32px rgba(0,0,0,.6); text-align: left; }
  .annotatable-surface { position: relative; min-height: 120px; cursor: crosshair; }
  .annotatable-surface .recharts-wrapper, .annotatable-surface svg { cursor: crosshair; }
  .delta-panel { margin-top: 14px; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; background: ${TOKENS.elevated}; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  .delta-panel b { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 13px; }
  .delta-panel span { color: ${TOKENS.secondary}; font-size: 12px; }
  .linked-sections { margin-top: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .linked-sections strong { color: ${TOKENS.amber}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .link-btn { color: ${TOKENS.secondary}; text-decoration: none; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 999px; padding: 6px 10px; font-size: 11px; transition: color .15s ease, border-color .15s ease; }
  .link-btn:hover { color: ${TOKENS.accent}; border-color: rgba(245,164,0,.45); }
  .output-card.annotating .annotatable-surface { outline: 1px dashed rgba(210,153,34,.45); outline-offset: 8px; }
  .annotation-pin { position: absolute; transform: translate(-50%, -50%); width: 24px; height: 24px; border-radius: 999px; border: 1px solid rgba(210,153,34,.72); background: ${TOKENS.amber}; color: ${TOKENS.panel}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; font-weight: 800; display: grid; place-items: center; cursor: pointer; z-index: 2; box-shadow: 0 6px 18px rgba(0,0,0,.42); }
  .annotation-pin.resolved { background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; border-color: ${TOKENS.border}; }
  .annotation-popover { position: absolute; transform: translate(-8px, -8px); z-index: 3; width: min(300px, 84vw); background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.border}; border-radius: 8px; padding: 10px; box-shadow: 0 14px 40px rgba(0,0,0,.52); }
  .annotation-popover textarea { width: 100%; min-height: 84px; resize: vertical; background: ${TOKENS.input}; border: 1px solid ${TOKENS.border}; color: ${TOKENS.text}; border-radius: 6px; padding: 9px; font-size: 12px; }
  .annotation-popover div { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
  .annotation-popover button { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; border-radius: 6px; min-height: 30px; padding: 0 10px; cursor: pointer; }
  .annotation-popover button:last-child { background: ${TOKENS.accent}; border-color: ${TOKENS.accent}; color: white; }
  .annotation-drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(420px, 92vw); z-index: 20; background: ${TOKENS.panel}; border-left: 1px solid ${TOKENS.border}; box-shadow: -18px 0 44px rgba(0,0,0,.46); padding: 18px; overflow: auto; }
  .drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .drawer-head p { color: ${TOKENS.amber}; text-transform: uppercase; letter-spacing: .16em; font-size: 11px; margin: 0 0 8px; font-weight: 700; }
  .drawer-head h3 { margin: 0; font-size: 22px; }
  .drawer-head button { width: 34px; height: 34px; border-radius: 7px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; display: grid; place-items: center; cursor: pointer; }
  .annotation-list-item { width: 100%; display: grid; grid-template-columns: 34px minmax(0, 1fr) 30px; gap: 10px; text-align: left; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; border-radius: 8px; padding: 12px; margin-bottom: 10px; cursor: pointer; }
  .annotation-list-item.resolved { opacity: .55; }
  .annotation-list-item strong { display: block; font-size: 13px; margin-bottom: 4px; }
  .annotation-list-item p { margin: 0 0 5px; color: ${TOKENS.secondary}; line-height: 1.4; font-size: 12px; }
  .annotation-list-item small { color: ${TOKENS.muted}; font-size: 10px; }
  .annotation-list-item i { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 999px; border: 1px solid ${TOKENS.border}; color: ${TOKENS.green}; }
  .drawer-empty { border: 1px dashed ${TOKENS.border}; border-radius: 8px; color: ${TOKENS.secondary}; padding: 20px; line-height: 1.5; }
  .preflight-card { margin-top: 22px; background: linear-gradient(135deg, rgba(245,164,0,.11), rgba(13,17,23,.96) 42%, rgba(210,153,34,.08)); border: 1px solid ${TOKENS.border}; border-radius: 12px; min-height: 220px; padding: 28px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
  .preflight-card p { color: ${TOKENS.amber}; text-transform: uppercase; letter-spacing: .16em; font-size: 11px; margin: 0 0 10px; font-weight: 700; }
  .preflight-card h2 { font-size: clamp(24px, 3vw, 40px); line-height: 1; letter-spacing: -0.02em; margin: 0 0 12px; }
  .preflight-card span { color: ${TOKENS.secondary}; max-width: 720px; display: block; line-height: 1.6; }
  .preflight-illustration { width: min(220px, 40vw); flex: none; }
  .preflight-illustration circle { fill: none; stroke: rgba(245,164,0,.22); stroke-width: 1; stroke-dasharray: 5 7; }
  .preflight-illustration path { fill: none; stroke: ${TOKENS.border}; stroke-width: 8; stroke-linecap: round; }
  .preflight-illustration line { stroke: ${TOKENS.accent}; stroke-width: 3; stroke-linecap: round; filter: drop-shadow(0 0 8px rgba(245,164,0,.5)); }
  .preflight-illustration circle:last-of-type { fill: ${TOKENS.amber}; stroke: ${TOKENS.panel}; stroke-width: 3; stroke-dasharray: none; }
  .preflight-illustration text { fill: ${TOKENS.secondary}; font: 700 9px "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: .12em; }
  .preflight-v2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 460px); align-items: center; }
  .preflight-copy .run-button { margin-top: 18px; }
  .preflight-types { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
  .preflight-types i { color: ${TOKENS.secondary}; background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.border}; border-radius: 999px; padding: 6px 9px; font-size: 10px; font-style: normal; text-transform: uppercase; letter-spacing: .1em; }
  .preflight-placeholders { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .preflight-mini { min-height: 120px; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 10px; background: ${TOKENS.elevated}; padding: 12px; display: grid; align-content: space-between; position: relative; overflow: hidden; }
  .preflight-mini::before { content: ""; position: absolute; left: 12px; right: 12px; top: 52px; height: 42px; border-radius: 7px; background: linear-gradient(90deg, ${TOKENS.active}, ${TOKENS.input}, ${TOKENS.active}); background-size: 220% 100%; animation: shimmer 1.5s ease-in-out infinite; }
  .preflight-mini b { color: ${TOKENS.accent}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; }
  .preflight-mini span { color: ${TOKENS.text}; font-size: 12px; line-height: 1.25; max-width: none; }
  .preflight-mini em { height: 5px; width: 70%; background: ${TOKENS.border}; border-radius: 999px; }
  .skeleton-chart, .skeleton-table, .skeleton-gauge-grid, .skeleton-heatmap { min-height: 320px; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 24px; overflow: hidden; }
  .skeleton-chart { display: grid; align-content: end; gap: 14px; }
  .skeleton-chart i, .skeleton-table i, .skeleton-gauge-grid i, .skeleton-heatmap i { display: block; border-radius: 6px; background: linear-gradient(90deg, ${TOKENS.active}, ${TOKENS.input}, ${TOKENS.active}); background-size: 220% 100%; animation: shimmer 1.5s ease-in-out infinite; }
  .skeleton-chart i:nth-child(1) { height: 42px; width: 42%; }
  .skeleton-chart i:nth-child(2) { height: 180px; animation-delay: .08s; }
  .skeleton-chart i:nth-child(3) { height: 38px; width: 82%; animation-delay: .16s; }
  .skeleton-chart i:nth-child(4) { height: 22px; width: 54%; animation-delay: .24s; }
  .skeleton-table { min-height: 260px; display: grid; gap: 9px; align-content: start; }
  .skeleton-table div { display: grid; grid-template-columns: 1.3fr repeat(4, 1fr); gap: 8px; }
  .skeleton-table i { height: 24px; }
  .skeleton-gauge-grid { min-height: 280px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); place-items: center; gap: 18px; }
  .skeleton-gauge-grid i { width: 146px; height: 86px; border-radius: 146px 146px 10px 10px; }
  .skeleton-heatmap { min-height: 340px; display: grid; grid-template-columns: repeat(8, 1fr); gap: 6px; }
  .skeleton-heatmap i { min-height: 32px; }
  @keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
  .metric-deck { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
  .metric-card { background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.border}; border-radius: 8px; min-height: 124px; padding: 16px; display: flex; flex-direction: column; justify-content: center; }
  .metric-card span, .metric-card small { color: ${TOKENS.secondary}; font-size: 11px; text-transform: uppercase; letter-spacing: .11em; }
  .metric-card strong { color: ${TOKENS.text}; font-size: 27px; margin: 8px 0 4px; line-height: 1; }
  .metric-spark { margin-top: 10px; width: 88px; height: 32px; }
  .metric-spark polyline { fill: none; stroke: ${TOKENS.accent}; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 0 6px rgba(245,164,0,.3)); }
  .metric-card small { text-transform: none; letter-spacing: 0; line-height: 1.4; }
  .f2-empty { min-height: 230px; border: 1px dashed ${TOKENS.border}; border-radius: 8px; display: flex; gap: 12px; align-items: center; justify-content: center; color: ${TOKENS.secondary}; padding: 24px; text-align: left; }
  .f2-empty.idle { flex-direction: column; text-align: center; }
  .f2-empty.missing { border-color: rgba(210,153,34,.34); background: rgba(210,153,34,.04); }
  .empty-orb { font-size: 32px; opacity: .24; }
  .f2-empty strong { color: ${TOKENS.text}; display: block; margin-bottom: 5px; }
  .f2-empty p { margin: 0; max-width: 620px; line-height: 1.55; font-size: 12px; }
  .table-scroll, .heatmap-wrap { overflow: auto; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; }
  .table-scroll { max-height: 680px; }
  .f2-table { width: 100%; border-collapse: collapse; min-width: 760px; }
  .f2-table th { height: 44px; background: ${TOKENS.elevated}; color: ${TOKENS.text}; text-align: right; font-size: 12px; padding: 0 12px; border-bottom: 1px solid ${TOKENS.border}; white-space: nowrap; position: sticky; top: 0; z-index: 2; }
  .f2-table th button { width: 100%; height: 100%; border: 0; background: transparent; color: inherit; display: inline-flex; justify-content: flex-end; align-items: center; gap: 7px; font: inherit; text-transform: uppercase; letter-spacing: .08em; cursor: pointer; }
  .f2-table th button span { color: ${TOKENS.muted}; font-size: 10px; }
  .f2-table th[data-sorted="true"] { background: rgba(245,164,0,.12); color: ${TOKENS.accent}; border-bottom: 2px solid ${TOKENS.accent}; }
  .f2-table th:first-child, .f2-table td:first-child { text-align: left; position: sticky; left: 0; background: ${TOKENS.elevated}; z-index: 1; }
  .f2-table td { height: 40px; color: ${TOKENS.text}; text-align: right; font-size: 12px; padding: 0 12px; border-bottom: 1px solid ${TOKENS.grid}; white-space: nowrap; }
  .f2-table tr { border-left: 2px solid transparent; transition: border-color 80ms ease; }
  .f2-table tr:hover { border-left-color: ${TOKENS.accent}; }
  .f2-table tr:hover td { background: ${TOKENS.input}; }
  .positive { color: ${TOKENS.green} !important; }
  .negative { color: ${TOKENS.red} !important; }
  .warning { color: ${TOKENS.amber} !important; }
  .heatmap-grid { display: grid; min-width: 760px; }
  .heatmap-tools { display: flex; justify-content: flex-end; align-items: center; gap: 8px; padding: 8px; background: ${TOKENS.panel}; border-bottom: 1px solid ${TOKENS.borderSubtle}; position: sticky; left: 0; }
  .heatmap-tools span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .heatmap-tools select { min-height: 30px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.text}; border-radius: 6px; padding: 0 8px; font-size: 11px; }
  .heatmap-head, .heatmap-row-label, .heatmap-cell { min-height: 38px; display: flex; align-items: center; justify-content: flex-end; border-bottom: 1px solid ${TOKENS.grid}; border-right: 1px solid ${TOKENS.grid}; padding: 0 10px; font-size: 11px; }
  .heatmap-head { background: ${TOKENS.elevated}; color: ${TOKENS.text}; font-weight: 700; }
  .heatmap-row-label { justify-content: flex-start; color: ${TOKENS.text}; background: ${TOKENS.elevated}; font-weight: 700; position: sticky; left: 0; z-index: 1; }
  .heatmap-cell { color: ${TOKENS.text}; }
  .heatmap-cell.strong-cell { box-shadow: inset 0 0 0 2px rgba(210,153,34,.62); }

  .pro-gauge { width: min(390px, 86vw); height: 250px; overflow: visible; filter: drop-shadow(0 16px 28px rgba(0,0,0,.32)); }
  .pro-gauge.full { height: 300px; }
  .gauge-track, .gauge-green, .gauge-amber, .gauge-red { fill: none; stroke-width: 18; stroke-linecap: round; }
  .gauge-track { stroke: ${TOKENS.active}; }
  .gauge-green { stroke: ${TOKENS.green}; }
  .gauge-amber { stroke: ${TOKENS.amber}; }
  .gauge-red { stroke: ${TOKENS.red}; }
  .gauge-needle { stroke: ${TOKENS.text}; stroke-width: 3; stroke-linecap: round; }
  .gauge-pivot { fill: ${TOKENS.amber}; stroke: ${TOKENS.panel}; stroke-width: 3; }
  .gauge-value { fill: ${TOKENS.text}; font: 700 46px "Quant360 Mono", "JetBrains Mono", monospace; }
  .gauge-label { fill: ${TOKENS.secondary}; font: 700 11px Inter, sans-serif; letter-spacing: .12em; text-transform: uppercase; }
  .waterfall-svg-wrap { overflow: auto; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; background: radial-gradient(circle at 20% 10%, rgba(245,164,0,.07), transparent 34%), ${TOKENS.elevated}; }
  .waterfall-svg-wrap { position: relative; }
  .waterfall-tooltip { position: absolute; transform: translate(-50%, -10px); min-width: 210px; z-index: 3; background: ${TOKENS.panel}; border: 1px solid ${TOKENS.border}; border-radius: 8px; padding: 10px 12px; box-shadow: 0 14px 38px rgba(0,0,0,.52); pointer-events: none; display: grid; gap: 5px; }
  .waterfall-tooltip strong { color: ${TOKENS.text}; font-size: 12px; margin-bottom: 3px; }
  .waterfall-tooltip span { display: flex; justify-content: space-between; gap: 16px; color: ${TOKENS.secondary}; font-size: 11px; }
  .waterfall-tooltip b { font-family: "Quant360 Mono", "JetBrains Mono", monospace; color: ${TOKENS.text}; }
  .waterfall-svg { min-width: 860px; width: 100%; height: 390px; display: block; }
  .wf-grid { stroke: ${TOKENS.grid}; stroke-opacity: .45; }
  .wf-zero { stroke: ${TOKENS.secondary}; stroke-dasharray: 4 4; stroke-opacity: .72; }
  .wf-positive { fill: ${TOKENS.green}; }
  .wf-negative { fill: ${TOKENS.red}; }
  .wf-connector { stroke: ${TOKENS.secondary}; stroke-width: 1; stroke-dasharray: 3 4; opacity: .72; }
  .wf-dot { fill: ${TOKENS.text}; opacity: .82; }
  .wf-label { fill: ${TOKENS.secondary}; font: 500 10px "Quant360 Mono", "JetBrains Mono", monospace; }
  .wf-value { fill: ${TOKENS.text}; font: 700 10px "Quant360 Mono", "JetBrains Mono", monospace; }
  .split-backtest { display: grid; grid-template-rows: 7fr 3fr; gap: 10px; min-height: 650px; }
  .split-top, .split-bottom { min-height: 0; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; background: ${TOKENS.elevated}; padding: 10px; overflow: hidden; }
  .split-top .recharts-responsive-container { min-height: 410px; }
  .split-bottom .recharts-responsive-container { min-height: 190px; }
  .violates-monotone { filter: drop-shadow(0 0 8px rgba(210,153,34,.42)); }

  .gauge-layout { display: grid; place-items: center; gap: 24px; padding: 18px 0 8px; }
  .progress-stack { display: grid; gap: 14px; }
  .progress-row { display: grid; grid-template-columns: 180px 1fr 74px; gap: 12px; align-items: center; color: ${TOKENS.secondary}; font-size: 12px; }
  .progress-row div { height: 11px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; }
  .progress-row i { display: block; height: 100%; border-radius: 999px; }
  .progress-row b { color: ${TOKENS.text}; text-align: right; }
  .signal-health-table tr:has(.negative), .signal-row-degraded { animation: pulseRow 2s ease-in-out infinite; }
  @keyframes pulseRow { 0%,100% { background: rgba(248,81,73,.03); } 50% { background: rgba(248,81,73,.12); } }
  .custom-tooltip { background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.border}; border-radius: 6px; padding: 10px 14px; box-shadow: 0 8px 32px rgba(0,0,0,.6); transform: translate(8px, 8px); pointer-events: none; max-width: 280px; }
  .tooltip-label { color: ${TOKENS.secondary}; font-size: 11px; margin-bottom: 8px; }
  .tooltip-row { display: flex; justify-content: space-between; gap: 16px; color: ${TOKENS.secondary}; font-size: 12px; }
  .tooltip-row b { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 12px; }
  .text-block { border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 18px; color: ${TOKENS.secondary}; line-height: 1.65; }
  .text-block.alert { border-color: rgba(248,81,73,.38); background: rgba(248,81,73,.08); }
  .text-row + .text-row { border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 14px; margin-top: 14px; }
  .text-row strong { color: ${TOKENS.text}; display: block; margin-bottom: 5px; }
  .text-row p { margin: 0; }
  .classifier { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 18px; }
  .classifier span { color: ${TOKENS.secondary}; text-transform: uppercase; letter-spacing: .13em; font-size: 11px; }
  .classifier strong { display: block; font-size: 26px; margin: 8px 0 18px; }
  .classifier-bar { display: flex; height: 28px; overflow: hidden; border-radius: 999px; background: ${TOKENS.active}; }
  .classifier-bar i { display: block; height: 100%; }
  .triple-heatmap { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
  .triple-heatmap h4 { margin: 0 0 8px; color: ${TOKENS.secondary}; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
  .research-toggle { min-height: 30px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; color: ${TOKENS.secondary}; border-radius: 999px; padding: 0 12px; font-size: 10px; font-weight: 800; letter-spacing: .12em; cursor: pointer; }
  .research-toggle.active { color: ${TOKENS.amber}; border-color: rgba(210,153,34,.52); background: rgba(210,153,34,.1); box-shadow: 0 0 18px rgba(210,153,34,.12); }
  .annotation-pin > i { position: absolute; left: -2px; top: -2px; width: 8px; height: 8px; border-radius: 999px; border: 1px solid ${TOKENS.panel}; }
  .annotation-pin > b { position: absolute; right: -5px; top: -7px; min-width: 15px; height: 15px; border-radius: 999px; background: ${TOKENS.accent}; color: white; font-size: 9px; display: grid; place-items: center; border: 1px solid ${TOKENS.panel}; }
  .annotation-popover select { width: 100%; min-height: 34px; background: ${TOKENS.input}; border: 1px solid ${TOKENS.border}; color: ${TOKENS.text}; border-radius: 6px; padding: 8px; font-size: 12px; margin-bottom: 8px; }
  .annotation-filters { display: grid; grid-template-columns: 1fr 130px; gap: 8px; margin-bottom: 14px; }
  .annotation-filters label { display: flex; align-items: center; gap: 7px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; border-radius: 7px; padding: 0 9px; color: ${TOKENS.secondary}; }
  .annotation-filters input, .annotation-filters select, .reply-box input { width: 100%; min-height: 36px; border: 0; background: transparent; color: ${TOKENS.text}; outline: 0; font-size: 12px; }
  .annotation-filters select { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; border-radius: 7px; padding: 0 8px; }
  .annotation-list-item { display: grid; grid-template-columns: 1fr !important; cursor: default; }
  .annotation-jump { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; text-align: left; border: 0; background: transparent; color: inherit; cursor: pointer; padding: 0; }
  .annotation-list-item strong { display: flex !important; align-items: center; gap: 7px; }
  .annotation-list-item strong i { width: 8px; height: 8px; border-radius: 999px; display: inline-block; }
  .annotation-thread { border-left: 2px solid ${TOKENS.border}; margin-left: 16px; padding-left: 12px; display: grid; gap: 8px; }
  .annotation-thread p { background: ${TOKENS.input}; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 7px; padding: 9px; }
  .annotation-thread b { display: block; color: ${TOKENS.text}; margin-bottom: 4px; }
  .reply-box { display: grid; grid-template-columns: 1fr 32px 32px; gap: 6px; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 8px; }
  .reply-box input { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; border-radius: 7px; padding: 0 9px; }
  .reply-box button { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 7px; display: grid; place-items: center; cursor: pointer; }
  .drilldown-drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(460px, 92vw); z-index: 21; background: ${TOKENS.panel}; border-left: 1px solid ${TOKENS.border}; box-shadow: -18px 0 44px rgba(0,0,0,.46); padding: 18px; overflow: auto; }
  .drill-anchor { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px; margin-bottom: 14px; display: grid; gap: 5px; }
  .drill-anchor b { color: ${TOKENS.text}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .drill-anchor span { color: ${TOKENS.secondary}; font-size: 12px; }
  .insight-bar small { grid-column: 2; color: ${TOKENS.muted}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; }
  .metric-range { margin-top: 10px; height: 4px; background: ${TOKENS.active}; border-radius: 999px; }
  .metric-range i { display: block; height: 100%; border-radius: 999px; position: relative; }
  .metric-range b { position: absolute; right: -3px; top: -3px; width: 10px; height: 10px; border-radius: 999px; border: 2px solid ${TOKENS.panel}; }
  .pro-gauge[data-stress="high"] { filter: drop-shadow(0 0 24px rgba(248,81,73,.35)) drop-shadow(0 16px 28px rgba(0,0,0,.32)); }
  .heatmap-cell { animation: cellReveal 200ms ease both; }
  @keyframes cellReveal { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
  .command-overlay { position: fixed; inset: 0; z-index: 60; display: grid; place-items: start center; padding-top: 14vh; background: rgba(8,12,16,.62); backdrop-filter: blur(20px); }
  .command-palette { width: min(560px, calc(100vw - 28px)); border: 1px solid ${TOKENS.border}; background: rgba(13,17,23,.98); border-radius: 12px; box-shadow: 0 28px 80px rgba(0,0,0,.62); overflow: hidden; }
  .command-palette [cmdk-input] { width: 100%; height: 54px; border: 0; border-bottom: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; outline: 0; padding: 0 16px; font-size: 15px; }
  .command-palette [cmdk-list] { display: grid; padding: 8px; max-height: 420px; overflow: auto; }
  .command-palette [cmdk-group-heading] { color: ${TOKENS.amber}; font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; padding: 10px 10px 6px; }
  .command-palette [cmdk-item] { min-height: 42px; border: 0; background: transparent; color: ${TOKENS.text}; border-radius: 8px; padding: 0 10px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; font-size: 13px; }
  .command-palette [cmdk-item][aria-selected="true"] { background: ${TOKENS.elevated}; }
  .command-palette kbd { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 5px; padding: 2px 6px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 10px; }

  /* Bloomberg/Koyfin density pass */
  .f2-page { padding-top: 0; }
  .f2-topbar {
    height: 48px;
    justify-content: flex-start;
    gap: 8px;
    border: 0;
    border-bottom: 1px solid ${TOKENS.borderSubtle};
    background: ${TOKENS.panel};
    border-radius: 0;
    padding: 0 20px;
    top: 0;
    box-shadow: 0 1px 0 ${TOKENS.borderSubtle};
  }
  .f2-topbar div:first-child { letter-spacing: 0; }
  .topbar-brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .topbar-brand strong { color: ${TOKENS.amber}; font-size: 12px; letter-spacing: .14em; }
  .topbar-brand span { color: ${TOKENS.muted}; font-size: 11px; letter-spacing: .06em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .topbar-spacer { flex: 1; }
  .topbar-btn {
    height: 28px;
    padding: 0 10px;
    border: 1px solid ${TOKENS.border};
    background: transparent;
    color: ${TOKENS.muted};
    border-radius: 4px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .1em;
    cursor: pointer;
  }
  .topbar-btn.active { color: ${TOKENS.amber}; border-color: rgba(245,158,11,.35); background: rgba(245,158,11,.08); }
  .regime-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 28px;
    padding: 0 10px;
    border: 1px solid ${TOKENS.border};
    border-radius: 4px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .1em;
    color: ${TOKENS.secondary};
  }
  .regime-pill i { width: 6px; height: 6px; border-radius: 999px; background: ${TOKENS.secondary}; }
  .regime-pill[data-state="elevated"] { color: ${TOKENS.red}; border-color: rgba(239,68,68,.25); }
  .regime-pill[data-state="elevated"] i { background: ${TOKENS.red}; box-shadow: 0 0 8px ${TOKENS.red}; }
  .regime-pill[data-state="watch"] { color: ${TOKENS.amber}; border-color: rgba(245,158,11,.25); }
  .regime-pill[data-state="watch"] i { background: ${TOKENS.amber}; }
  .regime-pill[data-state="normal"] { color: ${TOKENS.green}; border-color: rgba(34,197,94,.25); }
  .regime-pill[data-state="normal"] i { background: ${TOKENS.green}; }
  .live-dot span { display: none; }

  .config-card, .output-card { padding: 16px; border-radius: 8px; }
  .config-card { margin-top: 18px; }
  .section-head, .output-head { margin-bottom: 12px; min-height: 36px; }
  .section-head h2 { font-size: 18px; }
  .output-head h3 { font-size: 13px !important; line-height: 1.2; }
  .output-card.rank-primary .output-head h3 { font-size: 15px !important; }
  .output-head p { display: none; }
  .output-head span { color: ${TOKENS.textDisabled}; border-color: ${TOKENS.borderSubtle}; background: transparent; padding: 4px 7px; font-size: 9px; opacity: .68; }
  .card-actions { gap: 5px; }
  .card-actions button { width: 26px; height: 26px; border-radius: 5px; }
  .card-actions svg { width: 13px; height: 13px; }
  .output-stack { gap: 10px; }
  .output-layout { gap: 18px; grid-template-columns: 270px minmax(0,1fr); }
  .output-nav { top: 58px; border-radius: 8px; padding: 10px; max-height: calc(100dvh - 70px); }
  .output-nav a { min-height: 32px; font-size: 11px; }
  .output-card.rank-primary { border-left: 3px solid ${TOKENS.accent}; padding-left: 13px; box-shadow: none; }
  .output-card.rank-primary::before { height: 1px; background: linear-gradient(90deg, ${TOKENS.accent}, transparent); opacity: .4; }
  .output-card.rank-supporting { border-left: 3px solid transparent; }
  .output-card.rank-contextual { border-left: 3px solid ${TOKENS.borderSubtle}; background: rgba(14,17,23,.6); opacity: .88; }
  .output-card.is-active { border-left-color: ${TOKENS.accent}; box-shadow: inset 2px 0 0 rgba(245,164,0,.26); }
  .annotatable-surface { min-height: 48px; }
  .linked-sections { margin-top: 8px; gap: 5px; }
  .linked-sections strong { color: ${TOKENS.textDisabled}; font-size: 8px; }
  .link-btn { padding: 4px 7px; font-size: 10px; color: ${TOKENS.muted}; }
  .insight-bar {
    margin-top: 10px;
    padding: 8px 10px 0 0;
    border-top: 1px solid ${TOKENS.borderSubtle};
    display: flex;
    align-items: center;
    gap: 8px;
    color: ${TOKENS.secondary};
    font-size: 11px;
    font-family: "Quant360 Mono", "JetBrains Mono", monospace;
    line-height: 1.4;
  }
  .insight-bar::before { content: ""; width: 6px; height: 6px; border-radius: 999px; background: ${TOKENS.amber}; box-shadow: 0 0 10px rgba(245,164,0,.35); flex-shrink: 0; }

  .f2-empty-minimal {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 4px;
    color: ${TOKENS.textDisabled};
    font-size: 11px;
    font-family: "Quant360 Mono", "JetBrains Mono", monospace;
  }
  .f2-empty-minimal.missing { flex-wrap: wrap; min-height: 56px; color: ${TOKENS.amber}; }
  .empty-status { color: ${TOKENS.muted}; font-size: 14px; flex-shrink: 0; }
  .empty-available { width: 100%; padding-left: 24px; color: ${TOKENS.textDisabled}; font-size: 10px; }

  .mini-legend, .preset-tabs, .event-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 12px;
  }
  .mini-legend span, .event-strip span, .preset-tabs button {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 24px;
    padding: 4px 9px;
    border: 1px solid ${TOKENS.borderSubtle};
    border-radius: 999px;
    background: rgba(21,18,11,.82);
    color: ${TOKENS.secondary};
    font: 700 10px/1 "Quant360 Mono", "JetBrains Mono", monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  .mini-legend i { width: 8px; height: 8px; border-radius: 999px; }
  .preset-tabs button { cursor: pointer; }
  .preset-tabs button.active { border-color: rgba(245,164,0,.5); color: ${TOKENS.amber}; background: rgba(245,164,0,.1); }
  .freshness-score { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 18px; align-items: start; }
  .freshness-dial {
    aspect-ratio: 1;
    border-radius: 999px;
    display: grid;
    place-items: center;
    align-content: center;
    background: conic-gradient(var(--score-color) var(--score), ${TOKENS.borderSubtle} 0);
    box-shadow: inset 0 0 0 18px ${TOKENS.panel}, 0 0 32px rgba(245,164,0,.08);
  }
  .freshness-dial b { color: ${TOKENS.text}; font: 800 44px/1 "Quant360 Mono", "JetBrains Mono", monospace; }
  .freshness-dial span { color: ${TOKENS.muted}; font-size: 10px; text-transform: uppercase; letter-spacing: .16em; }
  .portfolio-compare, .stacked-attribution, .sector-decay, .multi-radar, .crowding-overlay, .adv-capacity, .crisis-presets { cursor: crosshair; }

  .pro-form { display: grid; gap: 0; }
  .pro-form-group {
    display: grid;
    grid-template-columns: 160px 1fr;
    border-top: 1px solid ${TOKENS.borderSubtle};
    padding: 14px 0;
    gap: 0 20px;
    align-items: start;
  }
  .pro-form-group:first-child { border-top: 0; }
  .pro-form-label {
    color: ${TOKENS.muted};
    font-size: 9px;
    font-weight: 800;
    letter-spacing: .16em;
    text-transform: uppercase;
    padding-top: 3px;
    position: sticky;
    top: 54px;
  }
  .pro-form-fields { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px 16px; }
  .pro-field { display: grid; gap: 5px; }
  .pro-field-wide { grid-column: 1 / -1; }
  .pro-field-label { color: ${TOKENS.secondary}; font-size: 11px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
  .pro-range-value { color: ${TOKENS.accent}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; font-weight: 800; }
  .pro-input, .pro-select, .ticker-search input {
    height: 36px;
    background: ${TOKENS.input};
    border: 1px solid ${TOKENS.border};
    color: ${TOKENS.text};
    border-radius: 6px;
    padding: 0 10px;
    font-size: 12px;
    outline: none;
    width: 100%;
  }
  .pro-input:focus, .pro-select:focus, .ticker-search:focus-within { border-color: ${TOKENS.accent}; box-shadow: 0 0 0 2px rgba(245,164,0,.12); }
  .pro-textarea {
    min-height: 80px;
    background: ${TOKENS.input};
    border: 1px solid ${TOKENS.border};
    color: ${TOKENS.text};
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: "Quant360 Mono", "JetBrains Mono", monospace;
    resize: vertical;
    outline: none;
    width: 100%;
  }
  .pro-number-shell {
    display: grid;
    grid-template-columns: 1fr 30px;
    height: 36px;
    background: ${TOKENS.input};
    border: 1px solid ${TOKENS.border};
    border-radius: 6px;
    overflow: hidden;
  }
  .pro-number-shell:focus-within { border-color: ${TOKENS.accent}; box-shadow: 0 0 0 2px rgba(245,164,0,.12); }
  .pro-number-input {
    min-width: 0;
    height: 100%;
    border: 0;
    background: transparent;
    color: ${TOKENS.text};
    font-family: "Quant360 Mono", "JetBrains Mono", monospace;
    font-size: 12px;
    outline: none;
    padding: 0 10px;
    width: 100%;
  }
  .pro-number-input::-webkit-outer-spin-button,
  .pro-number-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
  .pro-stepper { display: grid; grid-template-rows: 1fr 1fr; border-left: 1px solid ${TOKENS.borderSubtle}; }
  .pro-stepper button {
    border: 0;
    background: ${TOKENS.elevated};
    color: ${TOKENS.secondary};
    font-size: 11px;
    line-height: 1;
    cursor: pointer;
  }
  .pro-stepper button + button { border-top: 1px solid ${TOKENS.borderSubtle}; }
  .pro-stepper button:hover { color: ${TOKENS.text}; background: ${TOKENS.active}; }
  .pro-chips { display: flex; flex-wrap: wrap; gap: 5px; }
  .pro-chips button {
    height: 28px;
    padding: 0 10px;
    border: 1px solid ${TOKENS.border};
    background: ${TOKENS.elevated};
    color: ${TOKENS.secondary};
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    transition: all 100ms ease;
  }
  .pro-chips button.active { background: rgba(245,164,0,.15); border-color: rgba(245,164,0,.4); color: ${TOKENS.accent}; }
  .pro-chips button:hover:not(.active) { background: ${TOKENS.active}; color: ${TOKENS.text}; }
  .pro-mini-chips { display: flex; flex-wrap: wrap; gap: 4px; }
  .pro-mini-chips button {
    height: 20px;
    padding: 0 7px;
    border: 1px solid ${TOKENS.borderSubtle};
    background: transparent;
    color: ${TOKENS.muted};
    border-radius: 999px;
    font-size: 9px;
    font-family: "Quant360 Mono", "JetBrains Mono", monospace;
    cursor: pointer;
  }
  .pro-mini-chips button:hover { color: ${TOKENS.accent}; border-color: rgba(245,164,0,.4); background: rgba(245,164,0,.08); }
  .pro-field-helper { color: ${TOKENS.textDisabled}; font-size: 10px; line-height: 1.4; }
  .ticker-search { position: relative; display: flex; align-items: center; gap: 7px; height: 36px; background: ${TOKENS.input}; border: 1px solid ${TOKENS.border}; border-radius: 6px; padding: 0 9px; }
  .ticker-search input { height: 34px; border: 0; background: transparent; padding: 0; }
  .ticker-search svg { color: ${TOKENS.muted}; flex: none; }
  .ticker-results { position: absolute; left: 0; right: 0; top: calc(100% + 5px); z-index: 40; border: 1px solid ${TOKENS.border}; background: ${TOKENS.panel}; border-radius: 6px; box-shadow: 0 14px 38px rgba(0,0,0,.46); overflow: hidden; min-width: 360px; }
  .ticker-results button { width: 100%; min-height: 40px; border: 0; background: transparent; color: ${TOKENS.text}; display: grid; grid-template-columns: 70px 1fr auto; gap: 9px; align-items: center; text-align: left; padding: 0 10px; cursor: pointer; }
  .ticker-results button:hover { background: ${TOKENS.elevated}; }
  .ticker-results b { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 12px; color: ${TOKENS.accent}; }
  .ticker-results span { color: ${TOKENS.secondary}; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ticker-results em { color: ${TOKENS.muted}; font-style: normal; font-size: 10px; white-space: nowrap; text-transform: uppercase; }
  .ticker-loading { height: 36px; display: flex; align-items: center; padding: 0 10px; color: ${TOKENS.muted}; font-size: 11px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .multi-ticker { border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; border-radius: 7px; padding: 6px; }
  .multi-ticker:focus-within { border-color: ${TOKENS.accent}; box-shadow: 0 0 0 2px rgba(245,164,0,.14); }
  .multi-ticker-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
  .multi-ticker-strip > button {
    height: 28px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid rgba(245,164,0,.38);
    background: rgba(245,164,0,.1);
    color: ${TOKENS.accent};
    border-radius: 4px;
    padding: 0 8px;
    cursor: pointer;
  }
  .multi-ticker-strip > button b { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 11px; letter-spacing: .04em; }
  .multi-ticker .ticker-search { flex: 1; min-width: 220px; border: 0; background: transparent; padding: 0; height: 30px; }
  .multi-ticker .ticker-search:focus-within { box-shadow: none; border-color: transparent; }
  .multi-ticker .ticker-results { min-width: 460px; }
  .token-field { display: grid; gap: 6px; }
  .token-list {
    min-height: 36px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 5px;
    background: ${TOKENS.input};
    border: 1px solid ${TOKENS.border};
    border-radius: 6px;
    padding: 5px;
  }
  .token-list:focus-within { border-color: ${TOKENS.accent}; box-shadow: 0 0 0 2px rgba(245,164,0,.12); }
  .token-list button {
    height: 24px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid rgba(245,164,0,.35);
    background: rgba(245,164,0,.1);
    color: ${TOKENS.accent};
    border-radius: 4px;
    padding: 0 7px;
    font-size: 10px;
    font-weight: 800;
    cursor: pointer;
  }
  .token-list input {
    flex: 1;
    min-width: 90px;
    height: 24px;
    border: 0;
    outline: none;
    background: transparent;
    color: ${TOKENS.text};
    font-size: 12px;
  }
  .portfolio-input {
    display: grid;
    gap: 6px;
    border: 1px solid ${TOKENS.borderSubtle};
    border-radius: 8px;
    background: rgba(14,17,23,.42);
    padding: 8px;
  }
  .portfolio-head,
  .portfolio-row {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) 120px 30px;
    gap: 8px;
    align-items: center;
  }
  .portfolio-head { color: ${TOKENS.muted}; font-size: 9px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; padding: 0 2px; }
  .portfolio-row > button {
    height: 30px;
    border: 1px solid ${TOKENS.border};
    background: ${TOKENS.elevated};
    color: ${TOKENS.muted};
    border-radius: 5px;
    cursor: pointer;
  }
  .portfolio-row > button:hover { color: ${TOKENS.red}; border-color: rgba(239,68,68,.35); }
  .portfolio-actions { display: flex; gap: 6px; justify-content: flex-end; }
  .portfolio-actions button {
    height: 24px;
    border: 1px solid ${TOKENS.border};
    background: transparent;
    color: ${TOKENS.secondary};
    border-radius: 4px;
    padding: 0 8px;
    font-size: 10px;
    cursor: pointer;
  }
  .portfolio-actions button:hover { color: ${TOKENS.text}; background: ${TOKENS.elevated}; }

  .output-config-v2 { margin-top: 12px; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; overflow: visible; background: ${TOKENS.panel}; }
  .output-config-header {
    width: 100%;
    height: 40px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
    background: ${TOKENS.panel};
    border: 0;
    cursor: pointer;
    color: ${TOKENS.secondary};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
  }
  .output-config-header:hover { background: ${TOKENS.elevated}; }
  .output-config-header span { color: ${TOKENS.amber}; }
  .output-config-header em { font-style: normal; margin-left: auto; color: ${TOKENS.muted}; font-size: 11px; font-family: "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: 0; font-weight: 400; }
  .config-profile-tools select { height: 24px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 4px; padding: 0 6px; font-size: 10px; }
  .output-config-body { border-top: 1px solid ${TOKENS.borderSubtle}; }
  .output-config-actions { display: flex; gap: 6px; padding: 8px 12px; border-bottom: 1px solid ${TOKENS.borderSubtle}; align-items: center; }
  .output-config-actions button { height: 26px; padding: 0 8px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.secondary}; border-radius: 4px; font-size: 10px; cursor: pointer; }
  .output-config-actions input { flex: 1; height: 26px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; border-radius: 4px; padding: 0 8px; font-size: 11px; outline: none; }
  .output-config-list { display: grid; }
  .config-row {
    display: grid;
    grid-template-columns: 22px 14px 1fr 26px;
    align-items: center;
    height: 36px;
    padding: 0 12px;
    gap: 8px;
    border-top: 1px solid ${TOKENS.borderSubtle};
    cursor: pointer;
    font-size: 12px;
    color: ${TOKENS.muted};
    transition: background 80ms ease;
  }
  .config-row:first-child { border-top: 0; }
  .config-row:hover { background: ${TOKENS.elevated}; }
  .config-row.on { color: ${TOKENS.text}; }
  .config-check { width: 16px; height: 16px; border: 1px solid ${TOKENS.border}; border-radius: 3px; background: transparent; display: grid; place-items: center; color: ${TOKENS.green}; }
  .config-check.on { background: rgba(34,197,94,.1); border-color: rgba(34,197,94,.4); }
  .config-name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .config-cost { justify-self: end; font-size: 9px; font-weight: 800; color: ${TOKENS.textDisabled}; font-family: "Quant360 Mono", "JetBrains Mono", monospace; }
  .config-cost.cost-4, .config-cost.cost-5 { color: ${TOKENS.amber}; }



  /* Bloomberg terminal interaction pass */
  .input-summary-strip { position: sticky; top: 54px; z-index: 5; margin: 0 0 14px; min-height: 46px; border: 1px solid rgba(245,158,11,.24); border-radius: 14px; background: rgba(5,6,8,.88); box-shadow: 0 18px 70px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.04); backdrop-filter: blur(18px); display: flex; align-items: center; gap: 12px; padding: 8px 12px; }
  .input-summary-strip strong { color: var(--amber); letter-spacing: .16em; text-transform: uppercase; font-size: 10px; }
  .input-summary-strip span { color: var(--text-muted); font-size: 12px; flex: 1; }
  .input-summary-strip button { height: 30px; border-radius: 8px; border: 1px solid rgba(245,158,11,.3); background: rgba(245,158,11,.08); color: var(--text); padding: 0 12px; font-size: 11px; font-weight: 800; cursor: pointer; }
  .input-curtain { position: fixed; inset: 0; z-index: 900; background: rgba(0,0,0,.62); backdrop-filter: blur(12px); display: flex; align-items: flex-start; justify-content: center; padding: 58px clamp(18px, 5vw, 80px) 24px; }
  .curtain-card { width: min(1400px, 100%); max-height: calc(100dvh - 86px); overflow: auto; animation: curtainDrop 340ms cubic-bezier(.2,.9,.2,1) both; box-shadow: 0 28px 120px rgba(0,0,0,.66), 0 0 0 1px rgba(245,158,11,.18); }
  @keyframes curtainDrop { from { opacity: 0; transform: translateY(-42px) scale(.985); } to { opacity: 1; transform: none; } }
  .output-layout { grid-template-columns: 86px minmax(0, 1fr); gap: 18px; align-items: flex-start; }
  .output-nav { position: sticky; top: 66px; width: 72px; min-width: 72px; padding: 10px 8px; border-radius: 28px; border: 1px solid rgba(245,158,11,.22); background: rgba(6,7,9,.78); box-shadow: 0 18px 70px rgba(0,0,0,.46), inset 0 1px 0 rgba(255,255,255,.04); backdrop-filter: blur(18px); display: flex; flex-direction: column; align-items: center; gap: 8px; overflow: visible; }
  .output-nav strong { font-size: 8px; letter-spacing: .18em; color: var(--amber); writing-mode: vertical-rl; transform: rotate(180deg); margin: 4px 0 8px; }
  .output-nav-track { display: none; }
  .output-nav a { width: 46px; height: 46px; min-height: 46px; padding: 0; border-radius: 16px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.07); background: rgba(21,25,34,.72); color: var(--text-muted); font-size: 0; position: relative; transition: transform 180ms cubic-bezier(.2,.9,.2,1), background 120ms ease, border-color 120ms ease, box-shadow 120ms ease; }
  .output-nav a span { font-size: 11px; font-family: var(--font-mono); font-weight: 900; color: inherit; }
  .output-nav a kbd { display: none; }
  .output-nav a:hover, .output-nav a.active { transform: translateX(10px) scale(1.18); color: #050505; background: var(--amber); border-color: var(--amber); box-shadow: 0 12px 34px rgba(245,158,11,.22); z-index: 3; }
  .output-nav a::after { content: attr(data-title); position: absolute; left: 58px; top: 50%; transform: translateY(-50%) translateX(-8px); min-width: 190px; max-width: 260px; padding: 8px 10px; border-radius: 10px; border: 1px solid rgba(245,158,11,.22); background: rgba(5,6,8,.94); box-shadow: 0 16px 40px rgba(0,0,0,.42); color: var(--text); font-size: 11px; line-height: 1.35; pointer-events: none; opacity: 0; transition: opacity 120ms ease, transform 120ms ease; }
  .output-nav a:hover::after { opacity: 1; transform: translateY(-50%) translateX(0); }
  .annotation-open { width: 46px; height: 46px; min-height: 46px; padding: 0; border-radius: 16px; display: grid; place-items: center; border: 1px solid rgba(245,158,11,.18); background: rgba(245,158,11,.08); color: var(--amber); font-size: 0; position: relative; }
  .annotation-open span { position: absolute; right: -4px; top: -5px; min-width: 18px; height: 18px; border-radius: 999px; display: grid; place-items: center; background: var(--amber); color: #050505; font: 900 10px/1 var(--font-mono); }
  .output-card { border-color: rgba(245,158,11,.16); background: radial-gradient(circle at 50% -20%, rgba(245,158,11,.08), transparent 42%), linear-gradient(180deg, #101114, #060708 82%); box-shadow: inset 0 1px 0 rgba(255,255,255,.04), 0 24px 80px rgba(0,0,0,.38); }
  .output-card:hover, .output-card.is-active { border-color: rgba(245,158,11,.32); box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 0 0 1px rgba(245,158,11,.09), 0 28px 90px rgba(0,0,0,.45); }
  .output-card.rank-primary { border-left-color: var(--amber); }
  .annotatable-surface { position: relative; overflow: hidden; border-radius: 12px; border: 1px solid rgba(255,255,255,.08); background: repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0, rgba(255,255,255,.025) 1px, transparent 1px, transparent 34px), repeating-linear-gradient(90deg, rgba(255,255,255,.018) 0, rgba(255,255,255,.018) 1px, transparent 1px, transparent 72px), linear-gradient(180deg, #08090b, #030405); box-shadow: inset 0 0 0 1px rgba(0,0,0,.7), inset 0 24px 80px rgba(255,255,255,.02); }
  .annotatable-surface .recharts-cartesian-grid line { stroke: rgba(255,255,255,.18); stroke-width: .7; }
  .annotatable-surface .recharts-text { fill: #a7a29a; font-family: var(--font-mono); }
  .drawing-canvas { position: absolute; inset: 0; z-index: 4; pointer-events: none; }
  .drawing-canvas.enabled { pointer-events: auto; cursor: crosshair; }
  .output-card.drawing .annotatable-surface { outline: 1px solid rgba(245,158,11,.48); outline-offset: -1px; }
  .card-actions button.active { color: #050505; background: var(--amber); border-color: var(--amber); }
  .fullscreen-card { position: fixed !important; inset: 14px 14px 78px 14px !important; z-index: 1000 !important; overflow: auto; margin: 0 !important; max-width: none !important; background: #050506; }
  .fullscreen-card .annotatable-surface { min-height: calc(100dvh - 210px); }
  .fullscreen-card .recharts-responsive-container { min-height: calc(100dvh - 260px); }
  .backtest-split, .split-panel, .two-panel-stack { gap: 6px !important; }
  .split-drawdown, .drawdown-panel { margin-top: 0 !important; }

  @media (max-width: 980px) { .f2-hero, .output-layout, .field-grid, .field, .preflight-card, .input-group, .preflight-v2 { grid-template-columns: 1fr; flex-direction: column; align-items: stretch; } .input-group-grid { grid-template-columns: 1fr; } .output-nav { position: static; max-height: none; } .field small { grid-column: auto; } .triple-heatmap { grid-template-columns: 1fr; } .f2-topbar nav { display: none; } .input-summary-strip { top: 72px; } .insight-bar { grid-template-columns: 1fr; } }
`;
