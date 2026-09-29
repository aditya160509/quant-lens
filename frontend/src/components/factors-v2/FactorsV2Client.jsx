"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUpRight, BarChart3, CheckCircle2, Database, Download, FileText, Gauge, Layers3, Loader2, Play, RadarIcon, Route, Table2, Zap } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { runFactorsV2Feature } from "@/lib/api";
import { FACTORS_V2_FEATURES, getFactorsV2Feature } from "./registry";

const SERIES = ["#2F81F7", "#3FB950", "#F85149", "#D29922", "#A371F7", "#58A6FF", "#8B949E", "#E3B341"];
const SURFACE = "border border-[#30363D] bg-[#0D1117] shadow-[0_8px_32px_rgba(0,0,0,0.6)]";
const PANEL = "rounded-xl border border-[#30363D] bg-[#0D1117]";

function parseValue(field, value) {
  if (field.type === "number") return Number(value);
  if (field.type === "select" && (value === "true" || value === true)) return true;
  if (field.type === "select" && (value === "false" || value === false)) return false;
  if (field.type === "textarea") {
    if (!value) return undefined;
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  if (field.key === "horizons") return String(value).split(",").map((x) => Number(x.trim())).filter(Boolean);
  if (Array.isArray(field.options) && Array.isArray(field.default)) return String(value).split(",").map((x) => x.trim()).filter(Boolean);
  return value;
}

function formatValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (typeof value === "number") {
    const abs = Math.abs(value);
    if (abs >= 1_000_000) return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
    if (abs > 0 && abs < 0.01) return value.toExponential(2);
    return Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(value);
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function titleize(value) {
  return String(value).replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function initialForm(feature) {
  return Object.fromEntries(feature.fields.map((field) => {
    const value = feature.defaults[field.key];
    return [field.key, Array.isArray(value) ? value.join(",") : typeof value === "object" && value !== null ? JSON.stringify(value, null, 2) : value ?? ""];
  }));
}

export function FactorsV2Hub() {
  return (
    <main className="min-h-[100dvh] bg-[#080C10] text-[#E6EDF3] selection:bg-[#2F81F7]/30">
      <KernelTopBar />
      <section className="mx-auto max-w-[1700px] px-5 py-8 md:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <div className="pt-6">
            <div className="mb-5 inline-flex items-center gap-2 rounded border border-[#30363D] bg-[#2F81F7]/12 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#58A6FF]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#3FB950]" />
              dormant compute kernel
            </div>
            <h1 className="text-4xl font-black tracking-tight md:text-6xl">
              Factors <span className="text-[#58A6FF]">V2</span>
            </h1>
            <p className="mt-6 max-w-[68ch] text-base leading-7 text-[#8B949E]">
              Fourteen factor research workstations. Each page starts with a full computation form, then renders allocator-grade output sections from the backend schema.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {FACTORS_V2_FEATURES.map((feature, index) => (
              <Link
                key={feature.id}
                href={`/labs/factors-v2/${feature.slug}`}
                className={`${SURFACE} group relative overflow-hidden rounded-xl p-5 transition duration-200 hover:-translate-y-0.5 hover:border-[#2F81F7]`}
                style={{ animationDelay: `${index * 24}ms` }}
              >
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#2F81F7]/80 to-transparent" />
                <div className="flex items-start justify-between gap-4">
                  <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#58A6FF]">F{feature.id}</div>
                  <ArrowUpRight className="text-[#484F58] transition group-hover:text-[#58A6FF]" size={18} />
                </div>
                <h2 className="mt-5 text-xl font-semibold tracking-normal text-[#E6EDF3]">{feature.shortTitle}</h2>
                <p className="mt-3 text-sm leading-6 text-[#8B949E]">{feature.description}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

export function FactorsV2FeaturePage({ featureId }) {
  const feature = getFactorsV2Feature(featureId);
  const [form, setForm] = useState(() => initialForm(feature));
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const payload = useMemo(() => {
    const next = {};
    for (const field of feature.fields) {
      const parsed = parseValue(field, form[field.key]);
      if (parsed !== undefined && parsed !== "") next[field.key] = parsed;
    }
    return { ...feature.defaults, ...next };
  }, [feature, form]);

  async function run() {
    setLoading(true);
    setError("");
    try {
      setData(await runFactorsV2Feature(feature.id, payload));
    } catch (err) {
      setError(err.message || "Failed to run Factors V2 feature. The dormant backend router may not be wired yet.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <FeatureShell feature={feature} payload={payload}>
      <section className="mt-8 grid gap-8 xl:grid-cols-[500px_minmax(0,1fr)]">
        <ConfigurationPanel feature={feature} form={form} setForm={setForm} loading={loading} onRun={run} />
        <div>
          {error && <div className="mb-6 rounded-xl border border-red-400/30 bg-red-500/10 px-5 py-4 text-sm text-red-200">{error}</div>}
          {loading && <LoadingBlock />}
          {!data && !loading && <EmptyOutput feature={feature} />}
          {data && !loading && <FactorOutput feature={feature} data={data} />}
        </div>
      </section>
    </FeatureShell>
  );
}

function FeatureShell({ feature, payload, children }) {
  return (
    <main className="min-h-[100dvh] bg-[#080C10] text-[#E6EDF3] selection:bg-[#2F81F7]/30">
      <KernelTopBar />
      <section className="mx-auto max-w-[1760px] px-5 py-7 md:px-8">
        <div className="grid gap-6 border-b border-white/10 pb-8 lg:grid-cols-[1fr_420px]">
          <div>
            <Link href="/labs/factors-v2" className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#58A6FF]">Factors V2 / F{feature.id}</Link>
            <h1 className="mt-4 max-w-5xl text-3xl font-black tracking-tight md:text-5xl">{feature.title}</h1>
            <p className="mt-5 max-w-5xl text-base leading-7 text-[#8B949E]">{feature.description}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              {(feature.constraints || []).slice(0, 4).map((item) => (
                <span key={item} className="rounded-full border border-[#30363D] bg-[#2F81F7]/12 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.05em] text-[#8AB4F8]">{item}</span>
              ))}
            </div>
          </div>
          <div className={`${SURFACE} rounded-2xl p-5`}>
            <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E]">schema contract</div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <Badge label="inputs" value={feature.fields.length} />
              <Badge label="mode" value={payload.compute_mode || "realtime"} />
              <Badge label="sections" value={feature.outputLayout.length} />
              <Badge label="api" value="dormant" />
            </div>
          </div>
        </div>
        {children}
      </section>
    </main>
  );
}

function KernelTopBar() {
  return (
    <div className="border-b border-[#21262D] bg-[#0D1117]/95 px-5 py-3 md:px-8">
      <div className="mx-auto flex max-w-[1760px] items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className="flex h-9 w-9 items-center justify-center rounded bg-[#2F81F7] text-[#0D1117]"><Zap size={18} fill="currentColor" /></div>
          <div>
            <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-[#58A6FF]">ATLAS</div>
            <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-[#484F58]">factor intelligence kernel</div>
          </div>
        </div>
        <div className="hidden items-center gap-3 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E] md:flex">
          <span className="h-2 w-2 rounded-full bg-[#3FB950] shadow-[0_0_12px_rgba(63,185,80,0.5)]" />
          local data only
        </div>
      </div>
    </div>
  );
}

function Badge({ label, value }) {
  return (
    <div className="rounded-lg border border-[#30363D] bg-[#161B22] p-3">
      <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-[#8B949E]">{label}</div>
      <div className="mt-1 font-mono text-lg font-bold text-[#E6EDF3]">{value}</div>
    </div>
  );
}

function ConfigurationPanel({ feature, form, setForm, loading, onRun }) {
  return (
    <div className={`${SURFACE} sticky top-5 h-fit rounded-xl p-5`}>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-normal">Configuration</h2>
          <p className="mt-1 text-xs text-[#8B949E]">Inputs map to the computation document contract.</p>
        </div>
        <Database className="text-[#58A6FF]" size={20} />
      </div>
      <div className="space-y-3">
        {feature.fields.map((field) => (
          <div key={field.key} className="grid gap-2 rounded-lg border border-[#21262D] bg-[#161B22] p-3 md:grid-cols-[170px_minmax(0,1fr)] md:items-start">
            <div>
              <label htmlFor={field.key} className="block font-mono text-[10px] font-semibold uppercase tracking-[0.05em] text-[#8B949E]">{field.label}</label>
              {field.helper && <p className="mt-1 text-[11px] leading-4 text-[#484F58]">{field.helper}</p>}
            </div>
            {field.type === "select" ? (
              <select id={field.key} value={String(form[field.key])} onChange={(e) => setForm((prev) => ({ ...prev, [field.key]: e.target.value }))} className="h-11 w-full rounded-md border border-[#30363D] bg-[#1C2128] px-3 font-mono text-sm text-[#E6EDF3] outline-none transition focus:border-[#2F81F7] focus:ring-2 focus:ring-[#2F81F7]/20">
                {field.options.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
              </select>
            ) : field.type === "textarea" ? (
              <textarea id={field.key} value={form[field.key]} placeholder={field.placeholder} onChange={(e) => setForm((prev) => ({ ...prev, [field.key]: e.target.value }))} className="min-h-[118px] w-full rounded-md border border-[#30363D] bg-[#1C2128] px-3 py-3 font-mono text-xs text-[#E6EDF3] outline-none transition placeholder:text-[#484F58] focus:border-[#2F81F7] focus:ring-2 focus:ring-[#2F81F7]/20" />
            ) : (
              <input id={field.key} type={field.type || "text"} value={form[field.key]} placeholder={field.placeholder} onChange={(e) => setForm((prev) => ({ ...prev, [field.key]: e.target.value }))} className="h-11 w-full rounded-md border border-[#30363D] bg-[#1C2128] px-3 font-mono text-sm text-[#E6EDF3] outline-none transition placeholder:text-[#484F58] focus:border-[#2F81F7] focus:ring-2 focus:ring-[#2F81F7]/20" />
            )}
          </div>
        ))}
      </div>
      <button onClick={onRun} disabled={loading} className="mt-6 inline-flex h-12 w-full items-center justify-center gap-3 rounded-md bg-[#2F81F7] px-6 font-mono text-[11px] font-bold uppercase tracking-[0.12em] text-[#0D1117] transition hover:bg-[#388BFD] active:translate-y-px disabled:opacity-50">
        {loading ? <Loader2 size={17} className="animate-spin" /> : <Play size={17} fill="currentColor" />}
        {loading ? "running" : "run feature"}
      </button>
    </div>
  );
}

function LoadingBlock() {
  return (
    <div className={`${SURFACE} rounded-2xl p-8`}>
      <div className="h-3 w-56 animate-pulse rounded bg-[#2F81F7]/40" />
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-lg border border-[#30363D] bg-[#161B22]" />)}
      </div>
      <div className="mt-5 h-[360px] animate-pulse rounded-lg border border-[#30363D] bg-[#161B22]" />
    </div>
  );
}

function EmptyOutput({ feature }) {
  return (
    <div className={`${SURFACE} rounded-xl p-10`}>
      <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#58A6FF]">ready</div>
      <h2 className="mt-4 text-3xl font-bold tracking-normal">{feature.shortTitle} output deck</h2>
      <p className="mt-4 max-w-2xl text-sm leading-6 text-[#8B949E]">Run the feature to generate summary cards, feature-specific charts, institutional tables, alerts, and audit metadata from local factor, AQR, macro, price, and fundamentals data.</p>
    </div>
  );
}

function FactorOutput({ feature, data }) {
  const nav = buildOutputNav(feature);
  return (
    <section className="grid gap-6 lg:grid-cols-[190px_minmax(0,1fr)]">
      <OutputNav data={data} nav={nav} />
      <div className="space-y-6">
        {nav.map(([id, label]) => <FeatureOutputSection key={id} id={id} title={label} data={data} feature={feature} />)}
      </div>
    </section>
  );
}

function OutputNav({ data, nav }) {
  return (
      <aside className={`${SURFACE} sticky top-5 h-fit rounded-xl p-3`}>
        <div className="mb-2 flex items-center gap-2 rounded-md border border-[#3FB950]/25 bg-[#3FB950]/8 px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#56D364]">
          <CheckCircle2 size={15} /> {data.status}
        </div>
        {nav.map(([id, label, Icon]) => (
          <a key={id} href={`#${id}`} className="mt-2 flex min-h-11 items-center gap-3 rounded-md border border-[#21262D] bg-[#161B22] px-3 text-sm text-[#8B949E] transition hover:border-[#2F81F7] hover:bg-[#2F81F7]/12 hover:text-[#E6EDF3]">
            <Icon size={17} /> {label}
          </a>
        ))}
      </aside>
  );
}

function buildOutputNav(feature) {
  const iconMap = { summary: Gauge, alerts: AlertTriangle, audit: FileText, tables: Table2, report_preview: FileText, dna_radar: RadarIcon, correlation_heatmap: Layers3, covariance: Layers3, efficient_frontier: Route, equity_curve: BarChart3, drawdown: ArrowDown };
  return (feature.outputLayout || ["summary", "charts", "tables", "alerts", "audit"]).map((id) => [id, titleize(id), iconMap[id] || BarChart3]);
}

function FeatureOutputSection({ id, title, data }) {
  if (id === "summary") {
    return <OutputCard id={id} title={title}><MetricDeck cards={data.summary_cards || []} /></OutputCard>;
  }
  if (id === "alerts" || id === "alerts_log") {
    return <OutputCard id={id} title={title}><AlertPanel alerts={data.alerts || data.tables?.alert_log || []} /></OutputCard>;
  }
  if (id === "audit") {
    return <OutputCard id={id} title={title}><AuditPanel meta={data.meta || {}} /></OutputCard>;
  }
  if (id === "report_preview") {
    return <OutputCard id={id} title={title}><ReportPreview html={data.meta?.html} pdf={data.meta?.pdf_export} /></OutputCard>;
  }
  if (id === "tables") {
    return <OutputCard id={id} title={title}><div className="space-y-7">{Object.entries(data.tables || {}).map(([name, value]) => <DataTable key={name} name={name} rows={Array.isArray(value) ? value : [value]} />)}</div></OutputCard>;
  }
  const pickedCharts = pickNamed(data.charts || {}, id);
  const pickedTables = pickNamed(data.tables || {}, id);
  return (
    <OutputCard id={id} title={title}>
      {pickedCharts.length > 0 && <div className="grid gap-5 2xl:grid-cols-2">{pickedCharts.map(([name, value]) => <ChartBlock key={name} name={name} value={value} />)}</div>}
      {pickedTables.length > 0 && <div className="mt-5 space-y-7">{pickedTables.map(([name, value]) => <DataTable key={name} name={name} rows={Array.isArray(value) ? value : [value]} />)}</div>}
      {pickedCharts.length === 0 && pickedTables.length === 0 && <div className="text-sm text-[#8B949E]">This section will populate when the backend returns `{id}` outputs.</div>}
    </OutputCard>
  );
}

function MetricDeck({ cards }) {
  return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{cards.map((card, idx) => <MetricCard key={idx} card={card} />)}</div>;
}

function AlertPanel({ alerts }) {
  return alerts.length ? alerts.map((alert, idx) => <div key={idx} className="mb-3 rounded-lg border border-[#F85149]/25 bg-[#F85149]/8 p-4 text-sm text-[#FF7B72]">{formatValue(alert.message || alert.type || alert)}</div>) : <div className="text-sm text-[#8B949E]">No active alerts.</div>;
}

function AuditPanel({ meta }) {
  return <pre className="max-h-[420px] overflow-auto rounded-lg border border-[#30363D] bg-[#080C10] p-4 font-mono text-[11px] text-[#8B949E]">{JSON.stringify(meta, null, 2)}</pre>;
}

function ReportPreview({ html, pdf }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_220px]">
      <iframe title="Allocator report preview" srcDoc={html || "<p>Report preview unavailable until run completes.</p>"} className="h-[520px] w-full rounded-lg border border-[#30363D] bg-white" />
      <div className="rounded-lg border border-[#30363D] bg-[#161B22] p-4">
        <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E]">PDF Export</div>
        <div className="mt-3 text-2xl font-bold text-[#58A6FF]">{pdf || "pending"}</div>
        <button className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-[#2F81F7]/30 bg-[#2F81F7]/12 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-[#58A6FF]"><Download size={15} /> export ready</button>
      </div>
    </div>
  );
}

function pickNamed(source, section) {
  const keys = Object.keys(source);
  const aliases = SECTION_MATCHERS[section] || [section];
  const matched = keys.filter((key) => aliases.some((alias) => key.toLowerCase().includes(alias)));
  if (matched.length) return matched.map((key) => [key, source[key]]);
  if (section === "tables") return [];
  return [];
}

const SECTION_MATCHERS = {
  valuation_gauges: ["gauge", "valuation", "spread"],
  spread_history: ["spread", "timeseries", "series"],
  sector_tables: ["sector"],
  exposure_snapshot: ["exposure_bar"],
  static_heatmap: ["heatmap"],
  time_series: ["time_series", "series"],
  waterfall: ["waterfall"],
  cumulative: ["cumulative"],
  brinson: ["brinson"],
  regime_probabilities: ["probability"],
  transition_matrix: ["transition"],
  conditional_returns: ["conditional"],
  decay_curve: ["decay"],
  half_life: ["half_life"],
  rebalancing: ["rebalancing"],
  crowding_gauge: ["crowding", "metric"],
  metric_breakdown: ["metric"],
  crash_probability: ["crash"],
  equity_curve: ["equity"],
  drawdown: ["drawdown"],
  costs: ["cost", "capacity_constraints", "realtime_compute_policy"],
  statistics: ["statistics"],
  correlation_heatmap: ["correlation_heatmap"],
  covariance: ["covariance"],
  eigenvalues: ["eigen"],
  validation: ["validation"],
  capacity_curve: ["capacity"],
  slippage: ["slippage"],
  memo: ["memo", "sensitivity"],
  efficient_frontier: ["frontier"],
  weights: ["weight", "allocation"],
  constraints: ["constraint", "cardinality"],
  fap: ["fap"],
  scenario_waterfall: ["scenario"],
  reverse_stress: ["reverse"],
  var_irf: ["irf", "contagion"],
  dna_radar: ["dna"],
  classifier: ["classifier"],
  anatomy: ["anatomy"],
  purity: ["purity"],
  health: ["health"],
  cusum: ["cusum"],
  policy: ["policy", "resolution"],
  sections: ["sections"],
  pdf: ["customization", "ddq"],
};

function OutputCard({ id, title, children }) {
  return (
    <section id={id} className={`${SURFACE} rounded-xl p-5 md:p-7`}>
      <div className="mb-6 flex min-h-14 items-center justify-between border-b border-[#21262D] bg-[#161B22]/60 px-1 pb-4">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-[#E6EDF3]">{title}</h2>
        <div className="h-px w-24 bg-gradient-to-r from-[#2F81F7]/80 to-transparent" />
      </div>
      {children}
    </section>
  );
}

function MetricCard({ card }) {
  return (
    <div className="relative min-h-20 overflow-hidden rounded-lg border border-[#30363D] bg-[#161B22] p-5">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#2F81F7]/70 to-transparent" />
      <div className="font-mono text-[10px] font-medium uppercase tracking-[0.05em] text-[#8B949E]">{card.label}</div>
      <div className="mt-4 font-mono text-3xl font-bold tracking-tight text-[#E6EDF3]">{formatValue(card.value)}</div>
      {card.unit && <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.05em] text-[#58A6FF]">{card.unit}</div>}
    </div>
  );
}

function ChartBlock({ name, value }) {
  const rows = normalizeChartRows(value);
  return (
    <div className="min-h-[390px] rounded-lg border border-[#30363D] bg-[#080C10] p-4">
      <h3 className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E]">{name.replaceAll("_", " ")}</h3>
      <div className="h-[330px]">{renderChart(name, value, rows)}</div>
    </div>
  );
}

function normalizeChartRows(value) {
  if (Array.isArray(value)) return value.filter((row) => row && typeof row === "object");
  if (value && typeof value === "object" && Object.values(value).every((rows) => Array.isArray(rows))) {
    const merged = [];
    Object.entries(value).forEach(([series, rows]) => rows.forEach((row, idx) => {
      merged[idx] = { ...(merged[idx] || {}), date: row.date ?? merged[idx]?.date ?? idx, [series]: row.value };
    }));
    return merged;
  }
  return [];
}

function renderChart(name, value, rows) {
  if (rows.length && rows[0].row !== undefined && rows[0].column !== undefined) return <Heatmap rows={rows} />;
  if (name.includes("dna") && rows.length) return <DnaRadar rows={rows} />;
  if ((name.includes("gauge") || name.includes("crowding")) && rows.length) return <GaugeVisual rows={rows} />;
  if (name.includes("waterfall") && rows.length) return <WaterfallChart rows={rows} />;
  if (name.includes("classifier") && rows.length) return <GenericChart rows={rows} forceBar />;
  if (rows.length) return <GenericChart rows={rows} />;
  return <pre className="h-full overflow-auto rounded-md border border-[#30363D] bg-[#080C10] p-3 font-mono text-[11px] text-[#8B949E]">{JSON.stringify(value, null, 2)}</pre>;
}

function GaugeVisual({ rows }) {
  const row = rows.find((item) => typeof item.score === "number" || typeof item.value === "number") || rows[0] || {};
  const value = Math.max(0, Math.min(100, Number(row.score ?? row.value ?? 0)));
  return (
    <div className="flex h-full items-center justify-center">
      <div className="relative h-64 w-64">
        <div className="absolute inset-0 rounded-full border border-[#30363D] bg-[conic-gradient(from_225deg,#3FB950_0deg,#D29922_120deg,#F85149_240deg,rgba(255,255,255,0.08)_240deg)] shadow-[0_0_60px_rgba(47,129,247,0.18)]" />
        <div className="absolute inset-8 rounded-full bg-[#080C10] shadow-inner" />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="font-mono text-5xl font-bold text-[#E6EDF3]">{formatValue(value)}</div>
          <div className="mt-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E]">{row.metric || row.label || "score"}</div>
        </div>
      </div>
    </div>
  );
}

function WaterfallChart({ rows }) {
  const xKey = rows[0].factor ? "factor" : rows[0].component ? "component" : "scenario";
  const yKey = Object.keys(rows[0]).find((key) => typeof rows[0][key] === "number" && key !== "rank") || "value";
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} margin={{ top: 10, right: 20, bottom: 40, left: 0 }}>
        <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: "#8B949E", fontSize: 11 }} angle={-25} textAnchor="end" height={68} />
        <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#161B22", border: "1px solid #30363D", borderRadius: 6, color: "#E6EDF3" }} />
        <Bar dataKey={yKey} radius={[3, 3, 0, 0]}>
          {rows.map((row, idx) => <Cell key={idx} fill={Number(row[yKey]) >= 0 ? "#3FB950" : "#F85149"} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function GenericChart({ rows, forceBar = false }) {
  const xKey = "date" in rows[0] ? "date" : "factor" in rows[0] ? "factor" : "metric" in rows[0] ? "metric" : "class" in rows[0] ? "class" : "label" in rows[0] ? "label" : "rank";
  const keys = Object.keys(rows[0] || {}).filter((key) => key !== xKey && key !== "date" && key !== "row" && key !== "column" && rows.some((row) => typeof row[key] === "number"));
  if (!keys.length) return <pre className="h-full overflow-auto rounded-md border border-[#30363D] bg-[#080C10] p-3 font-mono text-[11px] text-[#8B949E]">{JSON.stringify(rows.slice(0, 40), null, 2)}</pre>;
  const barLike = forceBar || (rows.length <= 48 && !("date" in rows[0]));
  const Chart = barLike ? BarChart : keys.length > 2 ? AreaChart : LineChart;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <Chart data={rows} margin={{ top: 10, right: 20, bottom: 16, left: 0 }}>
        <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: "#8B949E", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={{ background: "#161B22", border: "1px solid #30363D", borderRadius: 6, color: "#E6EDF3" }} />
        <Legend wrapperStyle={{ color: "#8B949E", fontSize: 12 }} />
        {keys.slice(0, 7).map((key, idx) => barLike ? (
          <Bar key={key} dataKey={key} fill={SERIES[idx % SERIES.length]} radius={[2, 2, 0, 0]}>
            {rows.map((_, cellIdx) => <Cell key={cellIdx} fill={SERIES[(idx + cellIdx) % SERIES.length]} />)}
          </Bar>
        ) : Chart === AreaChart ? (
          <Area key={key} type="monotone" dataKey={key} stroke={SERIES[idx % SERIES.length]} fill={SERIES[idx % SERIES.length]} fillOpacity={0.18} dot={false} strokeWidth={2} />
        ) : (
          <Line key={key} type="monotone" dataKey={key} stroke={SERIES[idx % SERIES.length]} strokeWidth={2.2} dot={false} />
        ))}
      </Chart>
    </ResponsiveContainer>
  );
}

function DnaRadar({ rows }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={rows} outerRadius="72%">
        <PolarGrid stroke="#373E47" />
        <PolarAngleAxis dataKey="axis" tick={{ fill: "#E6EDF3", fontSize: 11 }} />
        <Radar dataKey="score" stroke="#2F81F7" fill="#2F81F7" fillOpacity={0.18} strokeWidth={2} />
        <Tooltip contentStyle={{ background: "#161B22", border: "1px solid #30363D", borderRadius: 6, color: "#E6EDF3" }} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function Heatmap({ rows }) {
  const r = Array.from(new Set(rows.map((x) => x.row)));
  const c = Array.from(new Set(rows.map((x) => x.column)));
  const map = new Map(rows.map((x) => [`${x.row}__${x.column}`, Number(x.value) || 0]));
  return (
    <div className="h-full overflow-auto">
      <div className="grid min-w-[560px]" style={{ gridTemplateColumns: `120px repeat(${c.length}, minmax(62px, 1fr))` }}>
        <div />
        {c.map((col) => <div key={col} className="truncate border-b border-[#30363D] p-2 text-center font-mono text-[10px] text-[#8B949E]">{col}</div>)}
        {r.map((row) => [
          <div key={`${row}-label`} className="truncate border-b border-[#30363D] p-2 font-mono text-[10px] text-[#8B949E]">{row}</div>,
          ...c.map((col) => {
            const v = map.get(`${row}__${col}`) || 0;
            const alpha = Math.min(0.92, Math.abs(v));
            const bg = v >= 0 ? `rgba(63,185,80,${0.08 + alpha * 0.5})` : `rgba(248,81,73,${0.08 + alpha * 0.5})`;
            return <div key={`${row}-${col}`} className="border-b border-l border-[#21262D] p-2 text-right font-mono text-[11px] text-[#E6EDF3]" style={{ background: bg }}>{formatValue(v)}</div>;
          }),
        ])}
      </div>
    </div>
  );
}

function DataTable({ name, rows }) {
  const normalized = rows.filter((row) => row && typeof row === "object").slice(0, 120);
  const columns = Array.from(new Set(normalized.flatMap((row) => Object.keys(row)))).slice(0, 10);
  return (
    <div>
      <h3 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8B949E]">{name.replaceAll("_", " ")}</h3>
      <div className="overflow-auto rounded-lg border border-[#30363D]">
        <table className="w-full min-w-[860px] border-collapse font-mono text-[12px]">
          <thead className="bg-[#161B22] text-[#8B949E]">
            <tr>{columns.map((col) => <th key={col} className="border-b border-[#30363D] px-3 py-3 text-left font-semibold uppercase tracking-[0.05em]">{col}</th>)}</tr>
          </thead>
          <tbody>
            {normalized.map((row, idx) => (
              <tr key={idx} className={idx % 2 ? "bg-[#161B22]/55" : "bg-[#0D1117]"}>
            {columns.map((col, colIdx) => <td key={col} className={`border-b border-[#21262D] px-3 py-3 align-top ${colIdx === 0 ? "sticky left-0 bg-[#0D1117] text-[#E6EDF3]" : ""} ${typeof row[col] === "number" ? "text-right text-[#E6EDF3]" : "text-[#8B949E]"}`}>{formatValue(row[col])}</td>)}
          </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
