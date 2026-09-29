"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, ChevronDown, Copy, Maximize2, Play, Search, SlidersHorizontal, TerminalSquare, X } from "lucide-react";
import { runScreenerV2Feature } from "@/lib/api";
import { getScreenerV2Feature, SCREENER_OUTPUT_BOOKS, SCREENER_V2_FEATURES } from "./registry";

const TOKENS = {
  page: "#050505",
  panel: "#090909",
  screen: "#0D0F11",
  raised: "#14110A",
  input: "#121212",
  border: "#302613",
  borderSubtle: "#1D1710",
  grid: "#2D2A24",
  accent: "#F5A400",
  accentSoft: "rgba(245,164,0,.14)",
  text: "#F5F2EA",
  secondary: "#A8A197",
  muted: "#6E665B",
  red: "#EF4444",
  green: "#22C55E",
  amber: "#F5A400",
  blue: "#60A5FA",
  teal: "#14B8A6",
  purple: "#8B5CF6",
};

const SERIES = ["#F5A400", "#22C55E", "#E8D18A", "#EF4444", "#14B8A6", "#8B5CF6", "#60A5FA", "#EC4899"];
const DEMO_TICKERS = ["NVDA", "MSFT", "AAPL", "META", "AMZN", "GOOGL", "JPM", "XOM", "LLY", "AVGO", "COST", "V", "MA", "ADBE"];

function rowsFrom(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (typeof data === "object") {
    if (Array.isArray(data.rows)) return data.rows;
    if (Array.isArray(data.data)) return data.data;
    return Object.entries(data).map(([name, value]) => (typeof value === "object" && value !== null ? { name, ...value } : { name, value }));
  }
  return [{ value: data }];
}

function numberLike(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const n = Number(String(value).replace(/[$,%]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function fmt(value) {
  const n = numberLike(value);
  if (n == null) return value == null ? "-" : String(value);
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs < 1 && abs > 0) return n.toFixed(3);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function titleize(key) {
  return String(key || "").replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function pick(response, section) {
  const source = section.source === "summary" ? "summary_cards" : section.source;
  const root = source === "summary_cards" ? response?.summary_cards : response?.[source];
  if (!root) return null;
  if (Array.isArray(root)) return root;
  for (const key of [section.dataKey, ...(section.fallbackKeys || [])]) {
    if (root?.[key] != null) return root[key];
  }
  return null;
}

function demoRows(count = 16) {
  return DEMO_TICKERS.slice(0, count).map((ticker, i) => ({
    rank: i + 1,
    ticker,
    company_name: `${ticker} Corporation`,
    sector: ["Technology", "Consumer", "Financials", "Energy", "Healthcare"][i % 5],
    core_quant_score: 94 - i * 3.1,
    valuation_percentile: 35 + ((i * 17) % 61),
    quality_percentile: 55 + ((i * 11) % 42),
    momentum_percentile: 91 - ((i * 7) % 55),
    low_vol_percentile: 48 + ((i * 5) % 38),
    market_cap: 2.2e12 / (i + 1),
    return_6m: 0.31 - i * 0.025,
    beta_effective: 0.72 + i * 0.06,
  }));
}

function demoSeries(length = 96, key = "strategy", base = 1) {
  let v = base;
  return Array.from({ length }, (_, i) => {
    v *= 1 + Math.sin(i / 7) * 0.006 + 0.0017;
    return { date: `D${i + 1}`, [key]: Number(v.toFixed(4)), benchmark: Number((1 + i * 0.0012 + Math.sin(i / 11) * 0.018).toFixed(4)) };
  });
}

function demoHeatmap(labels = ["Value", "Quality", "Momentum", "Low Vol", "Liquidity"]) {
  return labels.flatMap((row, i) => labels.map((col, j) => ({ row, col, value: i === j ? 1 : Number((Math.cos((i + 1) * (j + 2)) * 0.55).toFixed(2)) })));
}

function makeDemoResponse(featureId, form = {}) {
  const ranked = demoRows(Number(form.top_n || 16));
  const base = {
    feature_id: featureId,
    status: "preview",
    summary_cards: [
      { label: "Universe", value: form.universe === "master" ? "4,000+" : String(form.universe || "master") },
      { label: "Returned", value: ranked.length },
      { label: "Top Score", value: ranked[0]?.core_quant_score },
      { label: "Mode", value: "Local preview" },
    ],
    charts: {},
    tables: {},
    meta: { access_issues: ["API route is not wired yet; rendering deterministic local preview data."] },
  };
  if (featureId === "01") {
    base.tables.ranked_screener_table = ranked;
    base.tables.saved_screens = [];
    base.charts.filter_funnel_waterfall = [
      { name: "Universe", value: 4200 },
      { name: "Liquidity", value: 2600 },
      { name: "Fundamental", value: 1300 },
      { name: "Score", value: 180 },
      { name: "Selected", value: ranked.length },
    ];
    base.charts.cross_sectional_percentile_context = ranked;
    base.charts.heatmap_view = ranked.map((r) => ({ row: r.sector, col: r.ticker, value: r.core_quant_score }));
    base.charts.quick_look_card = { ticker: form.focus_ticker || "AAPL", chart_full: demoSeries(120, "price", 180), metrics: ranked[0] };
    base.charts.market_cap_bucket_distribution = ["Mega", "Large", "Mid", "Small"].map((bucket, i) => ({ bucket, count: 1200 - i * 240, avg_score: 58 + i * 6 }));
  }
  if (featureId === "02") {
    base.tables.formula_result_table = ranked.map((r) => ({ ...r, formula_score: r.core_quant_score + 2 }));
    base.tables.formula_validation_panel = [{ status: "valid", formula: form.formula, diagnostics: "Parsed with local preview evaluator" }];
    base.charts.historical_formula_backtest = demoSeries(120, "formula");
    base.charts.factor_zoo_comparison = ["Value", "Momentum", "Quality", "Low Vol"].map((factor, i) => ({ factor, score: 64 + i * 7 }));
  }
  if (featureId === "03") {
    base.tables.composite_score_universe_ranking = ranked;
    base.tables.score_transparency_decomposition = ["Value", "Momentum", "Quality", "Low Vol"].map((component, i) => ({ component, weight: [0.3, 0.3, 0.25, 0.15][i], mean_score: 62 + i * 6 }));
    base.tables.per_stock_score_decomposition = base.tables.score_transparency_decomposition.map((r) => ({ ticker: "NVDA", ...r, contribution: r.weight * r.mean_score }));
    base.tables.component_ic_ir_leaderboard = ["valuation_percentile", "momentum_percentile", "quality_percentile"].map((component, i) => ({ component, mean_ic: 0.08 + i * 0.03, ic_ir: 0.4 + i * 0.25 }));
    base.charts.factor_correlation_heatmap = demoHeatmap();
    base.charts.composite_vs_factor_backtest = demoSeries(120, "composite");
    base.tables.regime_conditional_composite_breakdown = ["Low Vol", "Normal", "High Vol"].map((regime, i) => ({ regime, avg_return: 0.06 - i * 0.025, hit_rate: 0.62 - i * 0.05 }));
  }
  if (featureId === "04") {
    base.tables.strategy_leaderboard = ["magic_formula", "quality_minus_junk", "trending_value", "low_vol"].map((strategy, i) => ({ strategy, avg_score: 81 - i * 5, top_decile_count: 18 - i * 3, coverage: 0.9 - i * 0.04 }));
    base.tables.per_strategy_stock_list = ranked;
    base.tables.piotroski_breakdown = ranked.map((r, i) => ({ ticker: r.ticker, piotroski_f_score: 9 - (i % 4), f5_leverage_field_used: i % 2 ? "long_term_debt" : "total_debt_fallback" }));
    base.tables.altman_z_score_status = ranked.map((r, i) => ({ ticker: r.ticker, altman_z_score: 4.8 - i * 0.18, altman_status: i > 8 ? "Grey" : "Safe" }));
    base.charts.strategy_correlation_matrix = demoHeatmap(["Magic", "Piotroski", "Altman", "Momentum", "LowVol"]);
    base.charts.historical_strategy_performance = demoSeries(120, "strategy");
    base.tables.historical_strategy_performance_all = base.tables.strategy_leaderboard.map((r) => ({ strategy: r.strategy, sharpe: 0.9 + Math.random() * 0.4, annualized_return: 0.12, max_drawdown: -0.18 }));
    base.tables.historical_strategy_performance_metadata = [{ evaluated_strategy_count: 4, excluded_due_to_limit: "proxy/helper columns excluded" }];
  }
  if (featureId === "05") {
    base.charts.equity_curve = demoSeries(160, "strategy");
    base.tables.full_performance_statistics = [{ total_return: 0.84, annualized_return: 0.18, annualized_vol: 0.21, sharpe: 0.88, max_drawdown: -0.19 }];
    base.charts.rolling_performance = demoSeries(80, "rolling_sharpe", 0.8);
    base.tables.holding_period_sensitivity = [21, 42, 63, 126].map((hold) => ({ hold, sharpe: 0.7 + hold / 400, turnover: 0.35 - hold / 800 }));
    base.tables.rebalancing_date_sensitivity = Array.from({ length: 8 }, (_, i) => ({ rebalance_offset_days: i, sharpe: 0.71 + Math.sin(i) * 0.08 }));
    base.tables.rebalancing_date_sensitivity_by_weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].map((weekday, i) => ({ weekday, sharpe: 0.7 + i * 0.04, rebalance_count: 152 - i }));
    base.tables.turnover_report = demoSeries(16, "turnover", 0.22);
    base.tables.sector_attribution = ["Tech", "Healthcare", "Energy", "Financials"].map((sector, i) => ({ sector, contribution: 0.09 - i * 0.025 }));
    base.tables.regime_conditional_performance = ["Low Vol", "Normal", "High Vol"].map((regime, i) => ({ regime, return: 0.11 - i * 0.04, sharpe: 1.1 - i * 0.25 }));
    base.charts.monte_carlo_sharpe_distribution = Array.from({ length: 40 }, (_, i) => ({ bucket: (0.2 + i * 0.04).toFixed(2), count: Math.round(22 * Math.exp(-Math.pow(i - 18, 2) / 120)) }));
    base.tables.stock_level_attribution = ranked.map((r, i) => ({ ticker: r.ticker, contribution: 0.05 - i * 0.006 }));
  }
  if (featureId === "06") {
    base.charts.alert_feed = ranked.slice(0, 8).map((r, i) => ({ ticker: r.ticker, type: i % 2 ? "SCORE_BREAKOUT" : "VOLUME_SPIKE", severity: i < 3 ? "high" : "medium", value: r.core_quant_score }));
    base.tables.alert_performance_tracker = [{ alert_type: "SCORE_BREAKOUT", precision: 0.62, count: 42 }, { alert_type: "VOLUME_SPIKE", precision: 0.55, count: 31 }];
    base.tables.alert_performance_tracker_historical = [
      { alert_type: "GOLDEN_CROSS", hit_rates: { "1d": 0.51, "5d": 0.57, "21d": 0.62 }, sample_sizes: { "1d": 91, "5d": 87, "21d": 73 }, method: "same_session_historical_replay" },
      { alert_type: "RSI_EXTREME", hit_rates: { "1d": 0.48, "5d": 0.53, "21d": 0.56 }, sample_sizes: { "1d": 144, "5d": 139, "21d": 121 }, method: "same_session_historical_replay" },
    ];
    base.tables.screen_entry_exit_log = ranked.slice(0, 8).map((r, i) => ({ ticker: r.ticker, action: i % 2 ? "ENTER" : "EXIT", score: r.core_quant_score }));
  }
  if (featureId === "07") {
    base.charts.four_dimension_valuation_card = { ticker: form.focus_ticker || "AAPL", valuation: 72, sector: 61, own_history: 84, momentum: 58 };
    base.charts.sector_valuation_landscape_heatmap = ranked.map((r) => ({ row: r.sector, col: r.ticker, value: r.valuation_percentile }));
    base.charts.own_history_percentile_time_series = demoSeries(120, "percentile", 0.48).map((r, i) => ({ date: r.date, percentile: 50 + Math.sin(i / 8) * 24 }));
    base.tables.peer_comparison_table = ranked;
    base.tables.universe_percentile_table = ranked.map((r) => ({ ticker: r.ticker, trailing_pe_pct: r.valuation_percentile, pb_pct: 100 - r.valuation_percentile, ev_ebitda_pct: r.quality_percentile }));
  }
  if (featureId === "08") {
    base.tables.instant_download = [{ format: form.export_format || "tsv", rows: ranked.length, bytes: 48212, status: "ready" }];
    base.tables.screen_result_api_endpoint = [{ method: "POST", endpoint: "/api/labs/screener/v2/feature/08/run", wired: false }];
    base.charts.change_report = ranked.slice(0, 10).map((r, i) => ({ ticker: r.ticker, status: i % 3 === 0 ? "NEW" : i % 3 === 1 ? "UP" : "DOWN", rank_change: 14 - i * 3 }));
  }
  return base;
}

function Field({ field, value, onChange }) {
  const common = { value: value ?? "", onChange: (e) => onChange(field.key, e.target.value) };
  if (field.type === "select") {
    return <select className="sv2-input" {...common}>{(field.options || []).map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}</select>;
  }
  if (field.type === "formula" || field.type === "json") {
    return <textarea className="sv2-textarea" {...common} placeholder={field.type === "formula" ? "rank(value)+zscore(momentum)" : "[{\"name\":\"Value\",\"field\":\"valuation_percentile\",\"weight\":0.4}]"}/>;
  }
  if (field.type === "ticker_list" || field.inputType === "multiTicker") {
    return <TickerStrip value={value} onChange={(v) => onChange(field.key, v)} placeholder="MASTER or AAPL MSFT NVDA" />;
  }
  return <input className="sv2-input" type={field.type === "number" ? "number" : "text"} {...common} />;
}

function TickerStrip({ value, onChange, placeholder }) {
  const tokens = String(value || "").split(/[,\s]+/).filter(Boolean);
  const [draft, setDraft] = useState("");
  function addToken(next) {
    const clean = String(next || draft).trim().toUpperCase();
    if (!clean) return;
    const merged = Array.from(new Set([...tokens.filter((t) => t.toLowerCase() !== "master"), clean]));
    onChange(merged.join(" "));
    setDraft("");
  }
  function removeToken(token) {
    onChange(tokens.filter((t) => t !== token).join(" ") || "master");
  }
  return (
    <div className="sv2-tickerbox">
      {tokens.slice(0, 10).map((token) => <button type="button" key={token} onClick={() => removeToken(token)}>{token}<span>×</span></button>)}
      <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === "," || e.key === "Tab") { e.preventDefault(); addToken(); } }} placeholder={tokens.length ? "Add..." : placeholder} />
    </div>
  );
}

function InputContract({ feature, form, setForm, onRun, loading }) {
  const [open, setOpen] = useState(true);
  const groups = useMemo(() => {
    const out = new Map();
    (feature.fields || []).forEach((field) => out.set(field.group || "Inputs", [...(out.get(field.group || "Inputs") || []), field]));
    return Array.from(out.entries());
  }, [feature]);
  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  return (
    <section className={`sv2-contract ${open ? "open" : "closed"}`}>
      <div className="sv2-contract-head">
        <div><span>INPUT CONTRACT</span><h2>{feature.title}</h2></div>
        <div className="sv2-contract-actions">
          <button className="sv2-ghost" type="button" onClick={() => setOpen((v) => !v)}><SlidersHorizontal size={15} />{open ? "Hide inputs" : "Edit inputs"}<ChevronDown size={14} /></button>
          <button className="sv2-run" onClick={onRun} disabled={loading}><Play size={15} />{loading ? "Running" : "Run screen"}</button>
        </div>
      </div>
      <motion.div className="sv2-groups" initial={false} animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }} transition={{ duration: 0.24, ease: "easeOut" }}>
        {groups.map(([group, fields]) => (
          <div className="sv2-group" key={group}>
            <div className="sv2-group-label">{group}</div>
            <div className="sv2-fields">
              {fields.map((field) => (
                <label className={`sv2-field ${field.type === "formula" || field.type === "json" ? "wide" : ""}`} key={field.key}>
                  <span>{field.label}</span>
                  <Field field={field} value={form[field.key]} onChange={update} />
                  {field.presets ? <div className="sv2-presets">{field.presets.map((p) => <button type="button" key={String(p)} onClick={() => update(field.key, p)}>{String(p)}</button>)}</div> : null}
                </label>
              ))}
            </div>
          </div>
        ))}
      </motion.div>
    </section>
  );
}

function SummaryTape({ cards, status }) {
  return <div className="sv2-summary">{(cards || []).map((c) => <div key={c.label}><span>{c.label}</span><b>{fmt(c.value)}</b></div>)}<em>{status}</em></div>;
}

function OutputNav({ sections, active, setActive }) {
  return (
    <aside className="sv2-output-nav">
      <p>OUTPUT BOOK</p>
      <div className="sv2-nav-rail">
        {sections.map((section, i) => <a key={section.id} href={`#${section.id}`} className={active === section.id ? "active" : ""} onMouseEnter={() => setActive(section.id)} title={section.title}><span>{String(i + 1).padStart(2, "0")}</span><b>{section.title}</b></a>)}
      </div>
    </aside>
  );
}

function OutputCard({ section, data, index, active, setActive }) {
  const [collapsed, setCollapsed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setActive(section.id);
    }, { threshold: 0.35, rootMargin: "-15% 0px -55% 0px" });
    obs.observe(node);
    return () => obs.disconnect();
  }, [section.id, setActive]);
  function renderArticle({ modal = false } = {}) {
    return (
    <motion.article
      ref={modal ? null : ref}
      id={modal ? undefined : section.id}
      className={`sv2-card ${section.rank === "primary" ? "primary" : ""} ${active === section.id ? "is-active" : ""} ${modal ? "expanded" : ""}`}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: modal ? 0 : index * 0.045 }}
    >
      <div className="sv2-card-head">
        <div><h3>{section.title}</h3><code>{section.source}.{section.dataKey}</code></div>
        <div className="sv2-card-actions">
          <button type="button" onClick={() => navigator.clipboard?.writeText(JSON.stringify(data ?? [], null, 2))} title="Copy output"><Copy size={14} /></button>
          {!modal ? <button type="button" onClick={() => setExpanded(true)} title="Expand"><Maximize2 size={14} /></button> : null}
          {!modal ? <button type="button" onClick={() => setCollapsed((v) => !v)} title="Collapse"><ChevronDown size={14} /></button> : null}
        </div>
      </div>
      {modal || !collapsed ? <div className="sv2-screen"><Renderer section={section} data={data} /></div> : null}
    </motion.article>
    );
  }

  return (
    <>
      {renderArticle()}
      {expanded ? <div className="sv2-modal"><button className="sv2-modal-close" type="button" onClick={() => setExpanded(false)}><X size={18} /></button>{renderArticle({ modal: true })}</div> : null}
    </>
  );
}

function Renderer({ section, data }) {
  if (!data || (Array.isArray(data) && !data.length)) return <div className="sv2-empty"><AlertTriangle size={15} /> Awaiting output</div>;
  const type = section.chartType;
  if (["table", "screenerTable", "strategyLeaderboard"].includes(type)) return <DataTable data={data} dense={type === "screenerTable"} />;
  if (type === "weekday") return <WeekdaySensitivity data={data} />;
  if (type === "alertPrecision") return <AlertPrecision data={data} />;
  if (type === "metricDeck") return <MetricDeck data={data} />;
  if (type === "diagnostic") return <Diagnostic data={data} />;
  if (type === "quickLook") return <QuickLook data={data} />;
  if (type === "heatmap") return <Heatmap data={data} />;
  if (type === "waterfall") return <BarVisual data={data} layout="vertical" />;
  if (type === "bar" || type === "histogram" || type === "factorBars") return <BarVisual data={data} />;
  if (type === "equityCurve" || type === "line") return <LineVisual data={data} />;
  if (type === "weights") return <Weights data={data} />;
  if (type === "alertTape") return <AlertTape data={data} />;
  if (type === "valuationCard") return <ValuationCard data={data} />;
  if (type === "exportPayload") return <ExportPayload data={data} />;
  if (type === "changeReport") return <ChangeReport data={data} />;
  return <DataTable data={data} />;
}

function DataTable({ data, dense = false }) {
  const rows = rowsFrom(data);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ key: null, dir: -1 });
  const cols = Object.keys(rows[0] || {}).slice(0, dense ? 12 : 8);
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    let out = text ? rows.filter((row) => cols.some((c) => String(row[c] ?? "").toLowerCase().includes(text))) : rows;
    if (sort.key) {
      out = [...out].sort((a, b) => {
        const av = numberLike(a[sort.key]);
        const bv = numberLike(b[sort.key]);
        if (av != null && bv != null) return (av - bv) * sort.dir;
        return String(a[sort.key] ?? "").localeCompare(String(b[sort.key] ?? "")) * sort.dir;
      });
    }
    return out;
  }, [rows, cols, query, sort]);
  function toggle(col) {
    setSort((prev) => ({ key: col, dir: prev.key === col ? prev.dir * -1 : -1 }));
  }
  return <div className="sv2-table-shell"><div className="sv2-table-tools"><Search size={14} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search rows..." /><span>{filtered.length} rows</span></div><div className="sv2-table-wrap"><table className="sv2-table"><thead><tr>{cols.map((c) => <th key={c} onClick={() => toggle(c)}>{titleize(c)} {sort.key === c ? (sort.dir < 0 ? "↓" : "↑") : ""}</th>)}</tr></thead><tbody>{filtered.slice(0, 160).map((row, i) => <tr key={i}>{cols.map((c) => <td key={c} className={numberLike(row[c]) != null ? "num" : ""}>{fmt(row[c])}</td>)}</tr>)}</tbody></table></div></div>;
}

function MetricDeck({ data }) {
  const row = rowsFrom(data)[0] || {};
  return <div className="sv2-metrics">{Object.entries(row).slice(0, 10).map(([k, v]) => <div key={k}><span>{titleize(k)}</span><b>{fmt(v)}</b></div>)}</div>;
}

function Diagnostic({ data }) {
  return <pre className="sv2-pre">{JSON.stringify(data, null, 2)}</pre>;
}

function xKey(rows) {
  return ["date", "t", "name", "ticker", "factor", "strategy", "bucket"].find((k) => rows.some((r) => r[k] != null)) || Object.keys(rows[0] || {})[0] || "name";
}

function yKeys(rows) {
  const x = xKey(rows);
  return Object.keys(rows[0] || {}).filter((k) => k !== x && rows.some((r) => numberLike(r[k]) != null)).slice(0, 4);
}

function LineVisual({ data }) {
  const rows = rowsFrom(data);
  const x = xKey(rows);
  const ys = yKeys(rows);
  return <ResponsiveContainer width="100%" height={360}><LineChart data={rows} margin={{ top: 12, right: 20, left: 0, bottom: 8 }}><CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false}/><XAxis dataKey={x} tick={axisTick} axisLine={false} tickLine={false}/><YAxis tick={axisTick} axisLine={false} tickLine={false}/><Tooltip content={<Tip />}/>{ys.map((k, i) => <Line key={k} dataKey={k} type="monotone" stroke={SERIES[i]} strokeWidth={2} dot={false} />)}</LineChart></ResponsiveContainer>;
}

const axisTick = { fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" };

function BarVisual({ data, layout }) {
  const rows = rowsFrom(data);
  const x = xKey(rows);
  const ys = yKeys(rows);
  const y = ys[0] || "value";
  if (layout === "vertical") {
    return <ResponsiveContainer width="100%" height={340}><BarChart data={rows} layout="vertical" margin={{ top: 12, right: 28, left: 24, bottom: 8 }}><CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} horizontal={false}/><XAxis type="number" tick={axisTick} axisLine={false} tickLine={false}/><YAxis type="category" dataKey={x} tick={axisTick} axisLine={false} tickLine={false}/><Tooltip content={<Tip />}/><Bar dataKey={y}>{rows.map((r, i) => <Cell key={i} fill={(numberLike(r[y]) || 0) < 0 ? TOKENS.red : TOKENS.accent}/>)}</Bar></BarChart></ResponsiveContainer>;
  }
  return <ResponsiveContainer width="100%" height={340}><BarChart data={rows} margin={{ top: 12, right: 18, left: 0, bottom: 8 }}><CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false}/><XAxis dataKey={x} tick={axisTick} axisLine={false} tickLine={false}/><YAxis tick={axisTick} axisLine={false} tickLine={false}/><Tooltip content={<Tip />}/><Bar dataKey={y} radius={[4, 4, 0, 0]} fill={TOKENS.accent}/></BarChart></ResponsiveContainer>;
}

function Heatmap({ data }) {
  const rows = rowsFrom(data);
  const rowLabels = Array.from(new Set(rows.map((r) => String(r.row ?? r.sector ?? r.name ?? "")))).filter(Boolean).slice(0, 18);
  const colLabels = Array.from(new Set(rows.map((r) => String(r.col ?? r.ticker ?? r.factor ?? "")))).filter(Boolean).slice(0, 24);
  const map = new Map(rows.map((r) => [`${r.row ?? r.sector ?? r.name}|${r.col ?? r.ticker ?? r.factor}`, numberLike(r.value ?? r.core_quant_score ?? r.valuation_percentile) ?? 0]));
  return <div className="sv2-heat" style={{ gridTemplateColumns: `110px repeat(${colLabels.length}, minmax(38px, 1fr))` }}><i />{colLabels.map((c) => <b key={c}>{c}</b>)}{rowLabels.map((r) => [<strong key={`${r}-h`}>{r}</strong>, ...colLabels.map((c) => { const v = map.get(`${r}|${c}`) ?? 0; const alpha = Math.min(0.85, Math.abs(v) / 100 || Math.abs(v)); return <span key={`${r}-${c}`} style={{ background: v < 0 ? `rgba(239,68,68,${alpha})` : `rgba(245,164,0,${alpha})` }}>{fmt(v)}</span>; })])}</div>;
}

function QuickLook({ data }) {
  const chart = data.chart_full || data.price || [];
  return <div className="sv2-quick"><div><span>FOCUS</span><b>{data.ticker || "AAPL"}</b><small>Price history and factor context</small></div><LineVisual data={chart} /></div>;
}

function Weights({ data }) {
  return <div className="sv2-weights">{rowsFrom(data).map((r, i) => <div key={i}><span>{r.component || r.name || r.field}</span><b>{fmt(r.weight ?? r.contribution ?? r.mean_score)}</b><i style={{ width: `${Math.min(100, Math.abs(numberLike(r.contribution ?? r.mean_score ?? r.weight) || 0))}%` }} /></div>)}</div>;
}

function AlertTape({ data }) {
  return <div className="sv2-alerts">{rowsFrom(data).map((r, i) => <div key={i} data-sev={r.severity}><b>{r.ticker}</b><span>{r.type}</span><em>{fmt(r.value)}</em></div>)}</div>;
}

function AlertPrecision({ data }) {
  return <div className="sv2-precision">{rowsFrom(data).map((row, i) => {
    const rates = row.hit_rates || {};
    const sizes = row.sample_sizes || {};
    return <div key={i}><header><b>{row.alert_type}</b><span>{row.method}</span></header>{Object.keys(rates).map((h) => <section key={h}><span>{h}</span><i><em style={{ width: `${Math.round((numberLike(rates[h]) || 0) * 100)}%` }} /></i><strong>{fmt((numberLike(rates[h]) || 0) * 100)}%</strong><small>n={sizes[h] ?? "-"}</small></section>)}</div>;
  })}</div>;
}

function WeekdaySensitivity({ data }) {
  const rows = rowsFrom(data);
  const best = Math.max(...rows.map((r) => numberLike(r.sharpe) ?? 0), 0.01);
  return <div className="sv2-weekdays">{rows.map((r) => <div key={r.weekday || r.name}><span>{r.weekday || r.name}</span><b>{fmt(r.sharpe)}</b><i><em style={{ width: `${Math.max(2, ((numberLike(r.sharpe) || 0) / best) * 100)}%` }} /></i><small>{fmt(r.rebalance_count)} rebalances</small></div>)}</div>;
}

function ValuationCard({ data }) {
  const row = Array.isArray(data) ? data[0] : data;
  const items = Object.entries(row || {}).filter(([, v]) => numberLike(v) != null);
  return <div className="sv2-valuation"><h4>{row?.ticker || "FOCUS"}</h4>{items.slice(0, 6).map(([k, v]) => <div key={k}><span>{titleize(k)}</span><b>{fmt(v)}</b><i style={{ width: `${Math.min(100, Math.abs(numberLike(v) || 0))}%` }} /></div>)}</div>;
}

function ExportPayload({ data }) {
  const text = JSON.stringify(data, null, 2);
  return <div className="sv2-export"><TerminalSquare size={30}/><h4>Export payload ready</h4><p>{rowsFrom(data).length} row envelope. TSV/JSON surfaces map directly to backend output keys.</p><button onClick={() => navigator.clipboard?.writeText(text)}><Copy size={14}/> Copy payload</button></div>;
}

function ChangeReport({ data }) {
  return <div className="sv2-change">{rowsFrom(data).map((r, i) => <div key={i}><b>{r.ticker}</b><span>{r.status}</span><em>{fmt(r.rank_change)}</em></div>)}</div>;
}

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="sv2-tip"><b>{label}</b>{payload.map((p) => <div key={p.dataKey}><span>{p.name}</span><em style={{ color: p.color }}>{fmt(p.value)}</em></div>)}</div>;
}

export function ScreenerV2Workbench({ featureId, sections: explicitSections, pageSpec = {} }) {
  const feature = getScreenerV2Feature(featureId);
  const sections = explicitSections || SCREENER_OUTPUT_BOOKS[feature.id] || [];
  const [form, setForm] = useState(feature.defaults || {});
  const [response, setResponse] = useState(() => makeDemoResponse(feature.id, feature.defaults));
  const [status, setStatus] = useState("LOCAL PREVIEW");
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(sections[0]?.id);
  async function run() {
    setLoading(true);
    try {
      const result = await runScreenerV2Feature(feature.id, form);
      setResponse(result);
      setStatus("API LIVE");
    } catch {
      setResponse(makeDemoResponse(feature.id, form));
      setStatus("LOCAL PREVIEW");
    } finally {
      setLoading(false);
    }
  }
  return (
    <main className="sv2-shell">
      <section className="sv2-hero">
        <div>
          <span>{pageSpec.eyebrow || "ATLAS // SCREENER V2"}</span>
          <h1>{pageSpec.headline || feature.title}</h1>
          <p>{pageSpec.description || feature.description}</p>
          <div className="sv2-hero-tags">
            <i>{sections.length} outputs</i>
            <i>{pageSpec.intent || "screening workflow"}</i>
            <i>{status}</i>
          </div>
        </div>
        <div className="sv2-hero-terminal"><Search size={18}/><code>{feature.shortTitle.toUpperCase()} &lt;GO&gt;</code></div>
      </section>
      <InputContract feature={feature} form={form} setForm={setForm} onRun={run} loading={loading} />
      <SummaryTape cards={response?.summary_cards} status={status} />
      <section className="sv2-workspace">
        <OutputNav sections={sections} active={active} setActive={setActive} />
        <div className="sv2-stack">
          {sections.map((section, index) => <OutputCard key={section.id} section={section} data={pick(response, section)} index={index} active={active} setActive={setActive} />)}
        </div>
      </section>
      <ScreenerStyles />
    </main>
  );
}

export function ScreenerV2Home() {
  return (
    <main className="sv2-home">
      <section className="sv2-home-hero">
        <span>ATLAS // SCREENING COMMAND CENTER</span>
        <h1>Institutional equity screening without dashboard noise.</h1>
        <p>Eight modules for factor ranking, formula screens, composite scores, academic strategies, backtests, alerts, relative valuation and export workflows.</p>
        <div>{SCREENER_V2_FEATURES.slice(0, 4).map((f) => <Link key={f.id} href={`/labs/screener-v2/${f.slug}`}>S{f.id} {f.shortTitle}</Link>)}</div>
      </section>
      <section className="sv2-home-grid">
        {SCREENER_V2_FEATURES.map((f) => <Link key={f.id} href={`/labs/screener-v2/${f.slug}`} className="sv2-home-card"><span>S{f.id}</span><h2>{f.shortTitle}</h2><p>{f.description}</p><em>{(SCREENER_OUTPUT_BOOKS[f.id] || []).length} outputs</em></Link>)}
      </section>
      <ScreenerStyles />
    </main>
  );
}

function ScreenerStyles() {
  return <style jsx global>{`
    .sv2-shell,.sv2-home{min-height:100dvh;background:#050505;color:#f5f2ea;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:0 clamp(18px,3vw,52px) 118px}
    .sv2-hero{display:flex;justify-content:space-between;gap:24px;padding:54px 0 26px;border-bottom:1px solid #1d1710}
    .sv2-hero span,.sv2-home-hero span{color:#f5a400;font-size:11px;font-weight:900;letter-spacing:.22em}
    .sv2-hero h1,.sv2-home-hero h1{max-width:920px;margin:12px 0 10px;font-size:clamp(38px,6vw,82px);line-height:.95;letter-spacing:-.04em}
    .sv2-hero p,.sv2-home-hero p{max-width:760px;color:#a8a197;font-size:17px;line-height:1.7}
    .sv2-hero-tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.sv2-hero-tags i{height:28px;display:inline-flex;align-items:center;border:1px solid #302613;border-radius:999px;background:#090909;color:#a8a197;padding:0 10px;font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;font-style:normal}
    .sv2-hero-terminal{height:48px;display:flex;align-items:center;gap:10px;padding:0 16px;border:1px solid #302613;background:#090909;border-radius:999px;color:#f5a400;white-space:nowrap}
    .sv2-contract{margin:22px 0;border:1px solid #302613;border-radius:14px;background:linear-gradient(180deg,#0d0f11,#090909);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
    .sv2-contract-head{height:64px;padding:0 18px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1d1710}
    .sv2-contract-head span,.sv2-group-label{color:#6e665b;font-size:10px;font-weight:900;letter-spacing:.18em}
    .sv2-contract-head h2{font-size:18px;margin:4px 0 0}
    .sv2-contract-actions{display:flex;align-items:center;gap:8px}.sv2-ghost{height:38px;border:1px solid #302613;background:#0d0f11;color:#a8a197;border-radius:8px;padding:0 12px;display:flex;align-items:center;gap:8px;font-weight:900;cursor:pointer}.sv2-ghost:hover{border-color:#f5a400;color:#f5a400}
    .sv2-run{height:38px;border:1px solid rgba(245,164,0,.45);background:#f5a400;color:#050505;border-radius:8px;padding:0 16px;display:flex;align-items:center;gap:8px;font-weight:900;cursor:pointer}
    .sv2-groups{display:grid;overflow:hidden}.sv2-group{display:grid;grid-template-columns:170px 1fr;gap:18px;padding:18px;border-top:1px solid #1d1710}.sv2-group:first-child{border-top:0}.sv2-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.sv2-field{display:grid;gap:7px}.sv2-field.wide{grid-column:1/-1}.sv2-field>span{color:#a8a197;font-size:12px;font-weight:800}
    .sv2-input,.sv2-textarea{width:100%;background:#121212;border:1px solid #302613;border-radius:7px;color:#f5f2ea;padding:0 11px;height:36px;outline:none}.sv2-textarea{height:78px;padding:10px;font-family:"JetBrains Mono",monospace}.sv2-input:focus,.sv2-textarea:focus{border-color:#f5a400;box-shadow:0 0 0 2px rgba(245,164,0,.12)}
    .sv2-tickerbox{min-height:38px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:#121212;border:1px solid #302613;border-radius:7px;padding:5px}.sv2-tickerbox button{height:26px;border:1px solid rgba(245,164,0,.28);background:rgba(245,164,0,.1);color:#f5a400;border-radius:5px;font-size:11px;font-weight:900}.sv2-tickerbox button span{margin-left:5px;color:#a8a197}.sv2-tickerbox input{flex:1;min-width:130px;background:transparent;border:0;color:#f5f2ea;outline:0}
    .sv2-presets{display:flex;gap:5px;flex-wrap:wrap}.sv2-presets button{height:22px;border:1px solid #1d1710;background:#090909;color:#6e665b;border-radius:999px;font-size:10px}
    .sv2-summary{height:auto;min-height:54px;display:flex;gap:8px;align-items:center;overflow-x:auto;border:1px solid #1d1710;border-radius:12px;background:#090909;padding:8px}.sv2-summary div{min-width:150px;padding:8px 12px;border:1px solid #1d1710;border-radius:8px;background:#0d0f11}.sv2-summary span{display:block;color:#6e665b;font-size:10px;letter-spacing:.14em;text-transform:uppercase}.sv2-summary b{font-family:"JetBrains Mono",monospace;font-size:18px}.sv2-summary em{margin-left:auto;color:#f5a400;font-style:normal;font-size:11px;font-weight:900;letter-spacing:.16em;white-space:nowrap}
    .sv2-workspace{display:grid;grid-template-columns:270px 1fr;gap:18px;margin-top:18px}.sv2-output-nav{position:sticky;top:18px;align-self:start;border:1px solid #302613;border-radius:14px;background:rgba(9,9,9,.94);padding:12px}.sv2-output-nav p{margin:0 0 10px;color:#f5a400;font-size:11px;font-weight:900;letter-spacing:.18em}.sv2-nav-rail{display:grid;gap:3px}.sv2-output-nav a{display:flex;gap:10px;padding:10px;border-radius:8px;color:#a8a197;text-decoration:none;font-size:12px;line-height:1.3;transition:transform 160ms ease,background 160ms ease,color 160ms ease}.sv2-output-nav a b{font-weight:800}.sv2-output-nav a span{font-family:"JetBrains Mono",monospace;color:#f5a400}.sv2-output-nav a.active,.sv2-output-nav a:hover{background:rgba(245,164,0,.1);color:#f5f2ea;transform:translateX(5px)}
    .sv2-stack{display:grid;gap:12px}.sv2-card{border:1px solid #302613;border-radius:14px;background:linear-gradient(180deg,#101114,#090909);padding:16px;box-shadow:0 18px 60px rgba(0,0,0,.35);transition:border-color 160ms ease,box-shadow 160ms ease,transform 160ms ease}.sv2-card.primary{border-left:3px solid #f5a400}.sv2-card.is-active{border-color:rgba(245,164,0,.65);box-shadow:0 0 0 1px rgba(245,164,0,.18),0 24px 80px rgba(0,0,0,.45)}.sv2-card:hover{transform:translateY(-1px);border-color:rgba(245,164,0,.5)}.sv2-card-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.sv2-card h3{margin:0;font-size:16px}.sv2-card code{color:#6e665b;background:#0d0f11;border:1px solid #1d1710;border-radius:999px;padding:5px 9px;font-size:10px}.sv2-card-actions{display:flex;gap:6px}.sv2-card-actions button,.sv2-modal-close{width:30px;height:30px;border:1px solid #302613;background:#0d0f11;color:#a8a197;border-radius:8px;display:grid;place-items:center;cursor:pointer}.sv2-card-actions button:hover,.sv2-modal-close:hover{color:#f5a400;border-color:#f5a400}.sv2-screen{min-height:170px;border:1px solid #1d1710;border-radius:10px;background:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px),radial-gradient(circle at 50% 0,rgba(245,164,0,.08),transparent 46%),#0d0f11;background-size:36px 36px,36px 36px,auto,auto;padding:14px;overflow:auto;cursor:crosshair}
    .sv2-modal{position:fixed;inset:20px;z-index:90;background:rgba(5,5,5,.9);backdrop-filter:blur(18px);border:1px solid #302613;border-radius:18px;padding:46px 18px 18px;display:grid}.sv2-modal-close{position:absolute;right:14px;top:12px}.sv2-card.expanded{height:100%;overflow:auto}.sv2-card.expanded .sv2-screen{min-height:calc(100dvh - 190px)}
    .sv2-table-shell{display:grid;gap:10px}.sv2-table-tools{height:34px;display:flex;align-items:center;gap:8px;border:1px solid #1d1710;background:#090909;border-radius:8px;padding:0 10px}.sv2-table-tools input{flex:1;background:transparent;border:0;outline:0;color:#f5f2ea}.sv2-table-tools span{color:#6e665b;font-family:"JetBrains Mono",monospace;font-size:11px}.sv2-table-wrap{overflow:auto;max-height:520px}.sv2-table{width:100%;border-collapse:collapse;font-size:12px}.sv2-table th{position:sticky;top:0;background:#14110a;color:#f5a400;text-align:left;font-size:10px;letter-spacing:.12em;text-transform:uppercase;cursor:pointer}.sv2-table th,.sv2-table td{border-bottom:1px solid #1d1710;padding:9px 10px;white-space:nowrap}.sv2-table td{color:#d8d0c3}.sv2-table td.num{font-family:"JetBrains Mono",monospace;color:#f5f2ea;text-align:right}.sv2-table tr:hover td{background:rgba(245,164,0,.05)}
    .sv2-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.sv2-metrics div{border:1px solid #302613;border-radius:9px;padding:12px;background:#090909}.sv2-metrics span,.sv2-valuation span{color:#6e665b;font-size:10px;text-transform:uppercase;letter-spacing:.14em}.sv2-metrics b,.sv2-valuation b{display:block;font-family:"JetBrains Mono",monospace;font-size:24px;margin-top:6px}
    .sv2-heat{display:grid;gap:3px;min-width:700px}.sv2-heat b,.sv2-heat strong{font-size:10px;color:#a8a197;display:grid;place-items:center}.sv2-heat strong{justify-content:start}.sv2-heat span{min-height:34px;display:grid;place-items:center;border:1px solid rgba(255,255,255,.04);font-family:"JetBrains Mono",monospace;font-size:10px;color:#f5f2ea}
    .sv2-tip{background:#14110a;border:1px solid #302613;border-radius:7px;padding:10px;color:#f5f2ea;box-shadow:0 18px 44px rgba(0,0,0,.5)}.sv2-tip div{display:flex;justify-content:space-between;gap:18px;color:#a8a197}.sv2-tip em{font-style:normal;font-family:"JetBrains Mono",monospace}.sv2-empty{height:130px;display:grid;place-items:center;color:#6e665b;font-family:"JetBrains Mono",monospace}
    .sv2-pre{margin:0;color:#a8a197;font-size:12px;white-space:pre-wrap}.sv2-quick{display:grid;grid-template-columns:200px 1fr;gap:12px}.sv2-quick>div:first-child{border:1px solid #302613;border-radius:10px;padding:14px;background:#090909}.sv2-quick b{display:block;font-size:32px}.sv2-weights{display:grid;gap:10px}.sv2-weights div,.sv2-valuation div{position:relative;border:1px solid #1d1710;border-radius:8px;padding:10px;background:#090909;overflow:hidden}.sv2-weights i,.sv2-valuation i{position:absolute;left:0;bottom:0;height:2px;background:#f5a400}.sv2-alerts,.sv2-change{display:grid;gap:8px}.sv2-alerts div,.sv2-change div{display:grid;grid-template-columns:90px 1fr 90px;gap:10px;padding:10px;border:1px solid #302613;border-radius:8px;background:#090909}.sv2-alerts div[data-sev=high]{border-color:rgba(239,68,68,.45)}.sv2-alerts em,.sv2-change em{font-style:normal;text-align:right;font-family:"JetBrains Mono",monospace;color:#f5a400}.sv2-valuation h4{font-size:32px;margin:0 0 12px}.sv2-export{text-align:center;padding:34px}.sv2-export svg{color:#f5a400}.sv2-export button{height:36px;border:1px solid #302613;background:#14110a;color:#f5a400;border-radius:8px;padding:0 14px;display:inline-flex;align-items:center;gap:8px}
    .sv2-precision{display:grid;gap:10px}.sv2-precision>div{border:1px solid #302613;border-radius:10px;background:#090909;padding:12px}.sv2-precision header{display:flex;justify-content:space-between;gap:12px;margin-bottom:10px}.sv2-precision header b{color:#f5f2ea}.sv2-precision header span,.sv2-precision small{color:#6e665b;font-size:10px}.sv2-precision section{display:grid;grid-template-columns:44px 1fr 70px 56px;gap:10px;align-items:center;margin-top:8px}.sv2-precision section span,.sv2-precision strong{font-family:"JetBrains Mono",monospace}.sv2-precision i{height:6px;border-radius:999px;background:#1d1710;overflow:hidden}.sv2-precision em{display:block;height:100%;background:#f5a400;border-radius:999px}.sv2-weekdays{display:grid;gap:8px}.sv2-weekdays div{display:grid;grid-template-columns:110px 70px 1fr 100px;gap:10px;align-items:center;border:1px solid #1d1710;border-radius:8px;background:#090909;padding:10px}.sv2-weekdays span{color:#a8a197;font-weight:800}.sv2-weekdays b{font-family:"JetBrains Mono",monospace;color:#f5a400}.sv2-weekdays i{height:6px;border-radius:999px;background:#1d1710;overflow:hidden}.sv2-weekdays em{display:block;height:100%;background:#f5a400;border-radius:999px}.sv2-weekdays small{color:#6e665b}
    .sv2-home-hero{min-height:76vh;display:grid;place-content:center;text-align:center}.sv2-home-hero h1{margin-left:auto;margin-right:auto}.sv2-home-hero p{margin-left:auto;margin-right:auto}.sv2-home-hero div{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:24px}.sv2-home-hero a{color:#f5a400;border:1px solid #302613;border-radius:999px;padding:10px 14px;text-decoration:none;background:#090909}.sv2-home-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.sv2-home-card{min-height:230px;border:1px solid #302613;border-radius:16px;background:linear-gradient(180deg,#101114,#090909);padding:18px;text-decoration:none;color:#f5f2ea}.sv2-home-card span{color:#f5a400;font-family:"JetBrains Mono",monospace}.sv2-home-card h2{font-size:28px}.sv2-home-card p{color:#a8a197;line-height:1.55}.sv2-home-card em{color:#6e665b;font-style:normal}
    @media(max-width:900px){.sv2-workspace,.sv2-group,.sv2-quick,.sv2-weekdays div{grid-template-columns:1fr}.sv2-output-nav{position:relative;top:0}.sv2-hero{display:block}.sv2-hero-terminal{margin-top:18px}.sv2-card-head{align-items:flex-start;flex-direction:column}.sv2-contract-head{height:auto;gap:12px;padding:14px;align-items:flex-start;flex-direction:column}.sv2-contract-actions{width:100%;justify-content:space-between}}
  `}</style>;
}
