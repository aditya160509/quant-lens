"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
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
  ReferenceArea,
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
  ArrowLeft,
  ArrowUpRight,
  Boxes,
  ChevronDown,
  CircleDollarSign,
  Copy,
  Crosshair,
  Download,
  Expand,
  FileJson,
  Gauge,
  Layers3,
  Network,
  PanelRightClose,
  PanelRightOpen,
  Play,
  RefreshCw,
  Search,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Target,
  X,
  Zap,
} from "lucide-react";
import { getPortfolioV2Feature, titleize } from "./registry";

const T = {
  void: "#030504",
  page: "#060907",
  panel: "#0A0E0B",
  raised: "#111813",
  screen: "#080C09",
  line: "#243128",
  soft: "#18221C",
  text: "#F1F8F2",
  secondary: "#9AA79E",
  muted: "#5F6F64",
  acid: "#B7FF3C",
  mint: "#4CE0A1",
  cyan: "#5AC8FA",
  amber: "#F5B942",
  red: "#FF625A",
  violet: "#A98BFF",
};
const COLORS = [
  T.acid,
  T.mint,
  T.cyan,
  T.amber,
  T.violet,
  T.red,
  "#E8F0C8",
  "#4F7EFF",
];
const tooltipStyle = {
  background: "#0A0E0B",
  border: `1px solid ${T.line}`,
  borderRadius: 8,
  color: T.text,
  boxShadow: "0 20px 60px rgba(0,0,0,.6)",
};
const axis = {
  stroke: T.muted,
  tick: { fill: T.secondary, fontSize: 10, fontFamily: "JetBrains Mono" },
  axisLine: false,
  tickLine: false,
};

export const PORTFOLIO_OUTPUT_BOOKS = {
  "01": sections(
    "efficient_frontier|weights|risk_contribution|dcc_average_correlation",
    "optimized_weights|black_litterman_weights|cvar_min_weights|constraint_report|stability_table|covariance_condition_numbers",
  ),
  "02": sections(
    "equity_curve|drawdown|monthly_heatmap|pbo_distribution|risk_methods",
    "performance_table|psr_dsr|walk_forward|bias_audit",
  ),
  "03": sections(
    "attribution_waterfall|active_return_series",
    "brinson_table|brinson_fachler|factor_attribution|drawdown_attribution|risk_attribution|linking_methods|skill_luck|skill_luck_null_distribution",
  ),
  "04": sections(
    "scenario_waterfall|monte_carlo",
    "scenario_table|correlation_stress|reverse_stress|stress_verdict|monte_carlo_summary",
  ),
  "05": sections(
    "macro_factor_returns|rolling_exposure",
    "macro_exposures|unintended_macro_bets|mcte_per_position|implied_alpha_required|factor_crowding_rank|factor_risk_budget",
  ),
  "06": sections(
    "regime_timeline|transition_matrix|regime_conditional_correlation",
    "regime_performance|regime_conditional_weights|survival_curves|nonhomogeneous_transition|factor_performance_by_regime|regime_alerts",
  ),
  "07": sections(
    "liquidation_schedule|liquidity_rank|liquidity_frontier",
    "liquidity_table|days_to_liquidate|liquidity_var|half_life|crisis_liquidation_cost|regulatory_compliance",
  ),
  "08": sections(
    "correlation_heatmap|crisis_delta|contagion_network|mantegna_mst|partial_correlation_network|eigenvalues|leading_eigenvalue_series|diversification_ratio_series|sector_block_analysis",
    "diversification_report|pair_redundancy|chow_breakpoints|hierarchy",
  ),
  "09": sections(
    "ic_decay_curve|decay_adjusted_weights",
    "half_life_table|decay_model_selection|crowding_proxy|optimal_rebalance_frequency|alpha_capacity|factor_zoo_comparison|publication_decay",
  ),
  10: sections(
    "growth_frontier|kelly_weights|ruin_probability_surface|turnover_optimal_curve|signal_decay_sizing|markowitz_weights",
    "position_sizing|ruin_probability|drawdown_leverage|effective_kelly_fraction|turnover_optimal_kelly|kelly_vs_markowitz",
  ),
  11: sections(
    "execution_trajectory|almgren_chriss_trajectory|is_frontier_aggregate|is_frontier_almgren_chriss",
    "cost_estimate|is_decomposition|joint_schedule|signal_decay_urgency|correlated_multiasset_is",
  ),
  12: sections(
    "overlap_heatmap|contagion_network|peer_data_requirement",
    "fire_sale_impact|debtrank|systemic_risk_contribution|overlap_centrality|spiral_probability|overlap_reducing_reallocation",
  ),
  13: sections(
    "strategy_correlation|dynamic_allocations|kelly_growth|all_reallocation_rules",
    "strategy_dashboard|risk_budget|kill_switch|kill_switch_pnl|kelly_strategy_weights|sharpe_momentum_weights|regime_conditional_strategy_weights|risk_attribution|capacity_constrained_reallocation|diversification_benefit|netting_savings",
  ),
};

function sections(charts, tables) {
  const make = (key, source, index) => ({
    id: key,
    dataKey: key,
    source,
    title: titleize(key),
    rank: index === 0 ? "primary" : "supporting",
  });
  return [
    ...charts
      .split("|")
      .filter(Boolean)
      .map((k, i) => make(k, "charts", i)),
    ...tables
      .split("|")
      .filter(Boolean)
      .map((k, i) => make(k, "tables", i + 20)),
  ];
}

const ENGINE_META = {
  "01": {
    code: "ALLOC",
    noun: "construction",
    accent: T.acid,
    primitive: ConstructionPrimitive,
  },
  "02": {
    code: "AUDIT",
    noun: "backtest",
    accent: T.mint,
    primitive: BacktestPrimitive,
  },
  "03": {
    code: "ATTR",
    noun: "attribution",
    accent: T.cyan,
    primitive: AttributionPrimitive,
  },
  "04": {
    code: "STRESS",
    noun: "scenario",
    accent: T.red,
    primitive: StressPrimitive,
  },
  "05": {
    code: "MACRO",
    noun: "factor",
    accent: T.amber,
    primitive: MacroPrimitive,
  },
  "06": {
    code: "REGIME",
    noun: "state",
    accent: T.violet,
    primitive: RegimePrimitive,
  },
  "07": {
    code: "LIQ",
    noun: "liquidity",
    accent: T.cyan,
    primitive: LiquidityPrimitive,
  },
  "08": {
    code: "NET",
    noun: "contagion",
    accent: T.red,
    primitive: ContagionPrimitive,
  },
  "09": {
    code: "DECAY",
    noun: "alpha",
    accent: T.amber,
    primitive: DecayPrimitive,
  },
  10: {
    code: "KELLY",
    noun: "growth",
    accent: T.acid,
    primitive: KellyPrimitive,
  },
  11: {
    code: "EXEC",
    noun: "execution",
    accent: T.mint,
    primitive: ExecutionPrimitive,
  },
  12: {
    code: "SYSTEM",
    noun: "systemic",
    accent: T.red,
    primitive: SystemicPrimitive,
  },
  13: {
    code: "MULTI",
    noun: "strategy",
    accent: T.violet,
    primitive: StrategyPrimitive,
  },
};

export function PortfolioV2Workbench({
  featureId,
  sections: suppliedSections,
}) {
  const feature = getPortfolioV2Feature(featureId);
  const meta = ENGINE_META[feature.id];
  const sectionBook = suppliedSections || PORTFOLIO_OUTPUT_BOOKS[feature.id];
  const [form, setForm] = useState(feature.defaults);
  const [data, setData] = useState(null);
  const [compareData, setCompareData] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [inputOpen, setInputOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeId, setActiveId] = useState(sectionBook[0]?.id);
  const [compact, setCompact] = useState(false);
  const [split, setSplit] = useState(false);
  const [fullscreen, setFullscreen] = useState(null);
  const [toast, setToast] = useState("");
  const [inspector, setInspector] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const filtered = useMemo(
    () =>
      sectionBook.filter(
        (s) => !search || s.title.toLowerCase().includes(search.toLowerCase()),
      ),
    [sectionBook, search],
  );
  const runEngine = useCallback(
    async (comparison = false) => {
      setRunning(true);
      setError("");
      try {
        const payload = normalizePayload(form);
        const response = await fetch(
          `/api/labs/portfolio/v2/feature/${feature.id}/run`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payload }),
          },
        );
        const json = await response.json();
        if (!response.ok)
          throw new Error(json.detail || "Portfolio computation failed");
        comparison ? setCompareData(json) : setData(json);
        setToast(
          comparison
            ? "Comparison snapshot captured"
            : "Portfolio engine completed",
        );
        window.setTimeout(() => setToast(""), 2600);
      } catch (exc) {
        setError(exc.message);
      } finally {
        setRunning(false);
      }
    },
    [feature.id, form],
  );

  useEffect(() => {
    const onKey = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((value) => !value);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setInspector(null);
        setFullscreen(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function exportJson() {
    const blob = new Blob([JSON.stringify(data || {}, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `portfolio-v2-${feature.id}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <main
      className={`portfolio-terminal ${compact ? "compact" : ""}`}
      style={{ "--engine": meta.accent }}
    >
      <style jsx global>
        {styles}
      </style>
      <TerminalTopbar
        feature={feature}
        meta={meta}
        running={running}
        search={search}
        setSearch={setSearch}
        onRun={() => runEngine(false)}
        onCompare={() => {
          setSplit(true);
          runEngine(true);
        }}
        onInputs={() => setInputOpen(true)}
        onExport={exportJson}
        compact={compact}
        setCompact={setCompact}
      />
      <div className={`run-rail ${running ? "active" : ""}`}>
        <i />
      </div>
      <Hero feature={feature} meta={meta} />
      <PresetBar
        feature={feature}
        form={form}
        setForm={setForm}
        onRun={() => runEngine(false)}
      />
      {error ? (
        <div className="terminal-error">
          <ShieldAlert size={18} />
          <b>ENGINE HALT</b>
          <span>{error}</span>
        </div>
      ) : null}
      <MetricTape cards={data?.summary_cards || []} meta={meta} />
      <DataQualityStrip response={data} feature={feature} />
      <section className="terminal-layout">
        <OutputRail
          sections={filtered}
          activeId={activeId}
          onSelect={setActiveId}
        />
        <div className={`terminal-lanes ${split ? "split" : ""}`}>
          <OutputLane
            label="LIVE BOOK"
            response={data}
            sections={filtered}
            meta={meta}
            activeId={activeId}
            setActiveId={setActiveId}
            fullscreen={fullscreen}
            setFullscreen={setFullscreen}
            onInspect={setInspector}
          />
          {split ? (
            <OutputLane
              label="COMPARISON"
              response={compareData || data}
              sections={filtered}
              meta={meta}
              activeId={null}
              setActiveId={() => {}}
              fullscreen={fullscreen}
              setFullscreen={setFullscreen}
              onInspect={setInspector}
              comparison
            />
          ) : null}
        </div>
        <RiskTelemetry response={data} meta={meta} />
      </section>
      <AnimatePresence>
        {inputOpen ? (
          <InputCurtain
            feature={feature}
            form={form}
            setForm={setForm}
            onClose={() => setInputOpen(false)}
            onRun={() => {
              setInputOpen(false);
              runEngine(false);
            }}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {inspector ? (
          <InspectorDrawer
            item={inspector}
            onClose={() => setInspector(null)}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {paletteOpen ? (
          <CommandPalette
            sections={sectionBook}
            onClose={() => setPaletteOpen(false)}
            onRun={() => {
              setPaletteOpen(false);
              runEngine(false);
            }}
            onInputs={() => {
              setPaletteOpen(false);
              setInputOpen(true);
            }}
            onJump={(id) => {
              setPaletteOpen(false);
              setActiveId(id);
              document
                .getElementById(`output-${id}`)
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {toast ? (
          <motion.div
            className="terminal-toast"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Zap size={15} />
            {toast}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </main>
  );
}

function TerminalTopbar({
  feature,
  meta,
  running,
  search,
  setSearch,
  onRun,
  onCompare,
  onInputs,
  onExport,
  compact,
  setCompact,
}) {
  return (
    <header className="terminal-topbar">
      <Link href="/labs/portfolio-v2" className="back">
        <ArrowLeft size={16} />
      </Link>
      <div className="terminal-mark">
        <b>P</b>
        <span>
          {meta.code}.{feature.id}
        </span>
      </div>
      <label className="terminal-search">
        <Search size={14} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search output book"
        />
        <kbd>⌘K</kbd>
      </label>
      <button onClick={() => setCompact(!compact)} title="Density">
        <Layers3 size={15} />
        {compact ? "Dense" : "Comfort"}
      </button>
      <button onClick={onCompare}>
        <Boxes size={15} />
        Compare
      </button>
      <button onClick={onExport}>
        <Download size={15} />
        Export
      </button>
      <button onClick={onInputs}>
        <SlidersHorizontal size={15} />
        Contract
      </button>
      <button className="execute" disabled={running} onClick={onRun}>
        {running ? (
          <RefreshCw className="spin" size={15} />
        ) : (
          <Play size={15} />
        )}{" "}
        {running ? "Computing" : "Execute"}
      </button>
    </header>
  );
}

function Hero({ feature, meta }) {
  return (
    <section className="terminal-hero">
      <div>
        <p>PORTFOLIO V2 / {meta.code} CONTROL SURFACE</p>
        <h1>{feature.title}</h1>
        <span>{feature.description}</span>
      </div>
      <div className="hero-orbit">
        <i />
        <i />
        <i />
        <b>{feature.id}</b>
        <small>{meta.noun.toUpperCase()}</small>
      </div>
    </section>
  );
}

function MetricTape({ cards, meta }) {
  const shown = cards.length
    ? cards
    : [
        { label: "Engine", value: meta.code },
        { label: "State", value: "READY" },
        { label: "Outputs", value: "AWAITING RUN" },
      ];
  return (
    <section className="metric-tape">
      <div className="tape-label">
        <Crosshair size={15} />
        <span>LIVE TELEMETRY</span>
      </div>
      {shown.map((card, index) => (
        <motion.div
          key={`${card.label}-${index}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: index * 0.05 }}
        >
          <small>{card.label}</small>
          <strong>{format(card.value)}</strong>
          <em>{card.format || "live"}</em>
          <svg viewBox="0 0 90 22">
            <polyline points={sparkPoints(Number(card.value) || index + 1)} />
          </svg>
        </motion.div>
      ))}
    </section>
  );
}

function PresetBar({ feature, form, setForm, onRun }) {
  const presets = [
    {
      label: "Balanced",
      patch: { objective: "max_sharpe", lookback_days: 1260 },
    },
    {
      label: "Defensive",
      patch: {
        objective: "min_variance",
        target_vol: 0.08,
        lookback_days: 2520,
      },
    },
    {
      label: "Crisis",
      patch: { scenario: "gfc_2008", loss_threshold: 0.2, regimes: 4 },
    },
    { label: "Fast", patch: { lookback_days: 504, simulations: 5000 } },
  ];
  return (
    <section className="preset-bar">
      <span>
        <Sparkles size={13} /> MODEL PRESETS
      </span>
      {presets.map((preset) => (
        <button
          key={preset.label}
          onClick={() =>
            setForm((current) => ({ ...current, ...preset.patch }))
          }
        >
          {preset.label}
        </button>
      ))}
      <em>{Object.keys(form).length} parameters armed</em>
      <button className="preset-run" onClick={onRun}>
        <Zap size={13} />
        Quick run
      </button>
    </section>
  );
}

function DataQualityStrip({ response, feature }) {
  const meta = response?.meta || {};
  const warnings = meta.notes || meta.warnings || [];
  const outputs =
    Object.keys(response?.charts || {}).length +
    Object.keys(response?.tables || {}).length;
  const items = [
    ["ENGINE", `F${feature.id}`],
    ["DATA POLICY", meta.data_policy || "LOCAL PARQUET"],
    ["OUTPUTS", outputs || "STANDBY"],
    ["WARNINGS", Array.isArray(warnings) ? warnings.length : warnings ? 1 : 0],
    ["LINEAGE", meta.engine || "PORTFOLIO_V2"],
  ];
  return (
    <section className="quality-strip">
      {items.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <b>{String(value)}</b>
          <i
            className={label === "WARNINGS" && Number(value) > 0 ? "warn" : ""}
          />
        </div>
      ))}
    </section>
  );
}

function InspectorDrawer({ item, onClose }) {
  const data = toRows(item.value);
  const numeric = numericKeys(data);
  const stats = numeric.map((key) => {
    const values = data.map((row) => Number(row[key])).filter(Number.isFinite);
    const mean = values.reduce((a, b) => a + b, 0) / Math.max(values.length, 1);
    return {
      key,
      count: values.length,
      min: Math.min(...values),
      max: Math.max(...values),
      mean,
    };
  });
  return (
    <motion.aside
      className="inspector"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", damping: 28, stiffness: 260 }}
    >
      <header>
        <div>
          <small>OUTPUT INSPECTOR</small>
          <h2>{item.section.title}</h2>
        </div>
        <button onClick={onClose}>
          <X size={16} />
        </button>
      </header>
      <section className="inspector-lineage">
        <span>PATH</span>
        <code>
          {item.section.source}.{item.section.dataKey}
        </code>
        <span>ROWS</span>
        <b>{data.length}</b>
        <span>ENGINE</span>
        <b>{item.meta.code}</b>
      </section>
      <h3>Numeric profile</h3>
      <div className="stat-grid">
        {stats.map((stat) => (
          <div key={stat.key}>
            <span>{titleize(stat.key)}</span>
            <strong>{format(stat.mean)}</strong>
            <small>
              {format(stat.min)} → {format(stat.max)} · n={stat.count}
            </small>
          </div>
        ))}
      </div>
      <h3>Raw evidence</h3>
      <pre>{JSON.stringify(item.value || {}, null, 2)}</pre>
      <footer>
        <button
          onClick={() =>
            navigator.clipboard?.writeText(
              JSON.stringify(item.value || {}, null, 2),
            )
          }
        >
          <Copy size={14} />
          Copy JSON
        </button>
        <button onClick={() => downloadCsv(item.section.dataKey, data)}>
          <Download size={14} />
          CSV
        </button>
      </footer>
    </motion.aside>
  );
}

function CommandPalette({ sections, onClose, onRun, onInputs, onJump }) {
  const [query, setQuery] = useState("");
  const commands = [
    {
      id: "run",
      label: "Execute portfolio engine",
      hint: "↵",
      action: onRun,
      icon: Play,
    },
    {
      id: "input",
      label: "Open input contract",
      hint: "I",
      action: onInputs,
      icon: Settings2,
    },
    ...sections.map((section) => ({
      id: section.id,
      label: `Jump to ${section.title}`,
      hint: section.source.toUpperCase(),
      action: () => onJump(section.id),
      icon: Crosshair,
    })),
  ].filter((command) =>
    command.label.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <motion.div
      className="palette-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.section
        initial={{ scale: 0.96, y: -12 }}
        animate={{ scale: 1, y: 0 }}
        onClick={(event) => event.stopPropagation()}
      >
        <label>
          <Search size={17} />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Type a command or output name"
          />
          <kbd>ESC</kbd>
        </label>
        <div>
          {commands.map((command) => {
            const Icon = command.icon;
            return (
              <button key={command.id} onClick={command.action}>
                <Icon size={15} />
                <span>{command.label}</span>
                <kbd>{command.hint}</kbd>
              </button>
            );
          })}
        </div>
        <footer>
          <span>⌘K command palette</span>
          <span>Portfolio V2 institutional console</span>
        </footer>
      </motion.section>
    </motion.div>
  );
}

function OutputRail({ sections, activeId, onSelect }) {
  return (
    <aside className="output-rail">
      <b>BOOK</b>
      {sections.map((section, index) => (
        <button
          key={section.id}
          className={activeId === section.id ? "active" : ""}
          onClick={() => {
            onSelect(section.id);
            document
              .getElementById(`output-${section.id}`)
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <i>
            {section.source === "charts" ? (
              <Gauge size={15} />
            ) : (
              <FileJson size={15} />
            )}
          </i>
          <em>{section.title}</em>
        </button>
      ))}
    </aside>
  );
}

function OutputLane({
  label,
  response,
  sections,
  meta,
  activeId,
  setActiveId,
  fullscreen,
  setFullscreen,
  onInspect,
  comparison = false,
}) {
  const Primitive = meta.primitive;
  return (
    <div className={`output-lane ${comparison ? "comparison" : ""}`}>
      <div className="lane-label">
        <span>{label}</span>
        <i>{response ? "SYNCHRONIZED" : "STANDBY"}</i>
      </div>
      {sections.map((section, index) => (
        <motion.article
          id={`output-${section.id}`}
          key={section.id}
          className={`terminal-card ${section.rank} ${activeId === section.id ? "active" : ""} ${fullscreen === section.id ? "fullscreen" : ""}`}
          onMouseEnter={() => setActiveId(section.id)}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: Math.min(index * 0.035, 0.3) }}
        >
          <header>
            <div>
              <small>
                {meta.code} / {section.source} /{" "}
                {String(index + 1).padStart(2, "0")}
              </small>
              <h2>{section.title}</h2>
            </div>
            <HeaderPulse data={pick(response, section)} />
            <button
              title="Copy output"
              onClick={() =>
                navigator.clipboard?.writeText(
                  JSON.stringify(pick(response, section) || {}, null, 2),
                )
              }
            >
              <Copy size={15} />
            </button>
            <button
              title="Inspect output"
              onClick={() =>
                onInspect({ section, value: pick(response, section), meta })
              }
            >
              <PanelRightOpen size={15} />
            </button>
            <button
              title="Download CSV"
              onClick={() =>
                downloadCsv(section.dataKey, toRows(pick(response, section)))
              }
            >
              <Download size={15} />
            </button>
            <button
              onClick={() =>
                setFullscreen(fullscreen === section.id ? null : section.id)
              }
            >
              {fullscreen === section.id ? (
                <X size={15} />
              ) : (
                <Expand size={15} />
              )}
            </button>
          </header>
          <div className="terminal-screen">
            <Primitive
              output={section.dataKey}
              value={pick(response, section)}
              response={response}
            />
          </div>
          <footer>
            <span>
              Source: {section.source}.{section.dataKey}
            </span>
            <b>{rowCount(pick(response, section))} observations</b>
          </footer>
        </motion.article>
      ))}
    </div>
  );
}

function RiskTelemetry({ response, meta }) {
  const alerts = response?.alerts || [];
  const metrics = response?.summary_cards || [];
  return (
    <aside className="risk-telemetry">
      <header>
        <Target size={15} />
        <b>RISK TAPE</b>
      </header>
      <div className="risk-dial">
        <svg viewBox="0 0 120 70">
          <path
            d="M12 62 A48 48 0 0 1 108 62"
            fill="none"
            stroke={T.soft}
            strokeWidth="10"
          />
          <path
            d="M12 62 A48 48 0 0 1 83 20"
            fill="none"
            stroke={meta.accent}
            strokeWidth="10"
          />
          <line
            x1="60"
            y1="62"
            x2="86"
            y2="29"
            stroke={T.text}
            strokeWidth="2"
          />
        </svg>
        <strong>{alerts.length ? "WATCH" : "CLEAR"}</strong>
        <span>CONTROL STATUS</span>
      </div>
      <div className="telemetry-list">
        {metrics.slice(0, 5).map((m, i) => (
          <div key={i}>
            <span>{m.label}</span>
            <b>{format(m.value)}</b>
          </div>
        ))}
      </div>
      {alerts.map((a, i) => (
        <div className="risk-alert" key={i}>
          <AlertTriangle size={13} />
          {a.message}
        </div>
      ))}
    </aside>
  );
}

function InputCurtain({ feature, form, setForm, onClose, onRun }) {
  return (
    <motion.div
      className="input-curtain"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.section
        initial={{ y: -40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <small>INPUT CONTRACT / FEATURE {feature.id}</small>
            <h2>{feature.title}</h2>
          </div>
          <button onClick={onClose}>
            <X size={17} />
          </button>
        </header>
        <div className="contract-grid">
          <div className="contract-intro">
            <Settings2 size={25} />
            <b>Model parameters</b>
            <span>
              Inputs are normalized before dispatch. Asset strings become ticker
              arrays.
            </span>
          </div>
          {feature.fields.map((field) => (
            <label key={field.key}>
              <span>
                {field.label}
                <em>{field.key}</em>
              </span>
              {field.type === "number" ? (
                <input
                  type="number"
                  value={form[field.key] ?? ""}
                  onChange={(e) =>
                    setForm((x) => ({
                      ...x,
                      [field.key]: Number(e.target.value),
                    }))
                  }
                />
              ) : (
                <textarea
                  rows={field.key.includes("weights") ? 4 : 2}
                  value={form[field.key] ?? ""}
                  onChange={(e) =>
                    setForm((x) => ({ ...x, [field.key]: e.target.value }))
                  }
                />
              )}
            </label>
          ))}
        </div>
        <footer>
          <button onClick={onClose}>Cancel</button>
          <button className="execute" onClick={onRun}>
            <Play size={15} />
            Run contract
          </button>
        </footer>
      </motion.section>
    </motion.div>
  );
}

// Feature 01: portfolio construction, frontier geometry and allocation diagnostics.
function ConstructionPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="allocation" />;
  if (output === "efficient_frontier") return <Frontier data={data} />;
  if (/weights/.test(output))
    return (
      <AllocationStack
        data={data}
        compare={output.includes("black") || output.includes("cvar")}
      />
    );
  if (output === "risk_contribution") return <RiskContribution data={data} />;
  if (output === "dcc_average_correlation")
    return <TimeSeries data={data} bands />;
  if (output === "constraint_report") return <ConstraintBoard data={data} />;
  if (output === "covariance_condition_numbers")
    return <ConditionBoard data={data} />;
  return <EvidenceTable data={data} />;
}

function BacktestPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="backtest" />;
  if (output === "equity_curve") return <EquityAudit data={data} />;
  if (output === "drawdown") return <DrawdownOcean data={data} />;
  if (output === "monthly_heatmap") return <CalendarMatrix data={data} />;
  if (output === "pbo_distribution")
    return <Distribution data={data} marker={0.5} />;
  if (output === "walk_forward") return <FoldTournament data={data} />;
  if (output === "bias_audit") return <AuditLedger data={data} />;
  return <EvidenceTable data={data} />;
}

function AttributionPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="attribution" />;
  if (output === "attribution_waterfall" || output === "factor_attribution")
    return <ContributionWaterfall data={data} />;
  if (output === "active_return_series") return <TimeSeries data={data} zero />;
  if (output === "skill_luck_null_distribution")
    return <Distribution data={data} />;
  if (output === "skill_luck") return <SkillVerdict data={data} />;
  return <EvidenceTable data={data} />;
}

function StressPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="stress scenario" />;
  if (output === "scenario_waterfall")
    return <ContributionWaterfall data={data} stress />;
  if (output === "monte_carlo") return <StressFan data={data} />;
  if (output === "scenario_table") return <ScenarioDeck data={data} />;
  if (output === "stress_verdict") return <VerdictPanel data={data} />;
  return <EvidenceTable data={data} />;
}

function MacroPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="macro factor" />;
  if (output === "macro_factor_returns") return <TimeSeries data={data} zero />;
  if (output === "rolling_exposure") return <ExposureRiver data={data} />;
  if (output === "macro_exposures") return <BetaConstellation data={data} />;
  if (output === "unintended_macro_bets")
    return <AuditLedger data={data} danger />;
  return <EvidenceTable data={data} />;
}

function RegimePrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="regime" />;
  if (output === "regime_timeline") return <RegimeRibbon data={data} />;
  if (/transition_matrix|correlation/.test(output))
    return <Matrix data={data} diverging={output.includes("correlation")} />;
  if (output === "regime_performance") return <RegimeScorecards data={data} />;
  if (output === "survival_curves") return <TimeSeries data={data} />;
  if (output === "regime_alerts") return <AuditLedger data={data} danger />;
  return <EvidenceTable data={data} />;
}

function LiquidityPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="liquidity" />;
  if (output === "liquidation_schedule") return <LiquidationTape data={data} />;
  if (output === "liquidity_rank") return <LiquidityLadder data={data} />;
  if (output === "liquidity_frontier") return <Frontier data={data} />;
  if (output === "days_to_liquidate") return <DaysToLiquidate data={data} />;
  if (output === "regulatory_compliance") return <ComplianceGrid data={data} />;
  return <EvidenceTable data={data} />;
}

function ContagionPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="correlation" />;
  if (/heatmap|crisis_delta|sector_block/.test(output))
    return <Matrix data={data} diverging />;
  if (/network|mst/.test(output))
    return <PortfolioNetwork data={data} mode={output} />;
  if (output === "eigenvalues") return <EigenSpectrum data={data} />;
  if (/series/.test(output)) return <TimeSeries data={data} />;
  return <EvidenceTable data={data} />;
}

function DecayPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="alpha decay" />;
  if (output === "ic_decay_curve") return <DecayCurve data={data} />;
  if (output === "decay_adjusted_weights") return <TimeSeries data={data} />;
  if (output === "half_life_table") return <HalfLifeClock data={data} />;
  if (output === "crowding_proxy") return <CrowdingRadar data={data} />;
  return <EvidenceTable data={data} />;
}

function KellyPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="growth allocation" />;
  if (output === "growth_frontier") return <GrowthFrontier data={data} />;
  if (/weights|position_sizing/.test(output))
    return <AllocationStack data={data} compare />;
  if (output === "ruin_probability_surface")
    return <Matrix data={data} danger />;
  if (output === "ruin_probability") return <RuinCurve data={data} />;
  if (output === "turnover_optimal_curve") return <TimeSeries data={data} />;
  return <EvidenceTable data={data} />;
}

function ExecutionPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="execution" />;
  if (/trajectory|schedule/.test(output))
    return <ExecutionTrajectory data={data} />;
  if (/frontier/.test(output)) return <Frontier data={data} />;
  if (output === "cost_estimate") return <CostTape data={data} />;
  if (output === "is_decomposition")
    return <ContributionWaterfall data={data} stress />;
  return <EvidenceTable data={data} />;
}

function SystemicPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="systemic risk" />;
  if (output === "overlap_heatmap") return <Matrix data={data} />;
  if (output === "contagion_network")
    return <PortfolioNetwork data={data} mode="systemic" />;
  if (output === "debtrank") return <DebtRank data={data} />;
  if (output === "fire_sale_impact") return <FireSaleCascade data={data} />;
  if (output === "spiral_probability")
    return <VerdictPanel data={data} danger />;
  return <EvidenceTable data={data} />;
}

function StrategyPrimitive({ output, value }) {
  const data = toRows(value);
  if (!data.length) return <Empty noun="strategy allocation" />;
  if (output === "strategy_correlation")
    return <Matrix data={data} diverging />;
  if (output === "dynamic_allocations") return <AllocationRiver data={data} />;
  if (output === "kelly_growth") return <GrowthFrontier data={data} />;
  if (output === "all_reallocation_rules")
    return <AllocationStack data={data} compare />;
  if (output === "strategy_dashboard") return <StrategyDashboard data={data} />;
  if (output === "kill_switch") return <KillSwitchBoard data={data} />;
  return <EvidenceTable data={data} />;
}

function Frontier({ data }) {
  const { x, ys } = infer(
    data,
    ["vol", "risk", "sigma"],
    ["return", "sharpe", "growth"],
  );
  const y = ys[0];
  return (
    <div className="primitive-shell">
      <div className="primitive-legend">
        <span>
          <i style={{ background: T.acid }} />
          FEASIBLE SET
        </span>
        <b>{data.length} portfolios</b>
      </div>
      <ResponsiveContainer width="100%" height={390}>
        <ScatterChart margin={{ left: 8, right: 22, top: 18, bottom: 8 }}>
          <CartesianGrid stroke={T.soft} />
          <XAxis {...axis} dataKey={x} name={titleize(x)} />
          <YAxis {...axis} dataKey={y} />
          <Tooltip contentStyle={tooltipStyle} />
          <Scatter data={data} fill={T.acid}>
            {data.map((_, i) => (
              <Cell
                key={i}
                fill={COLORS[i % COLORS.length]}
                opacity={0.35 + (0.65 * i) / data.length}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <Interpretation text="Upper-left portfolios dominate: higher expected reward for less risk. Isolated points often signal binding constraints or unstable covariance." />
    </div>
  );
}

function GrowthFrontier({ data }) {
  return (
    <div className="primitive-shell">
      <TimeSeries data={data} area />
      <Interpretation text="Growth peaks before unconstrained leverage. The right side of the curve trades a small expected-growth gain for rapidly increasing ruin sensitivity." />
    </div>
  );
}

function AllocationStack({ data, compare = false }) {
  const label =
    findKey(data, /ticker|asset|strategy|name/i) || Object.keys(data[0])[0];
  const numeric = numericKeys(data).slice(0, compare ? 4 : 2);
  return (
    <div className="allocation-layout">
      <div className="allocation-bars">
        {data.slice(0, 30).map((row, i) => (
          <div key={i}>
            <span>{row[label]}</span>
            <div>
              {numeric.map((key, j) => (
                <i
                  key={key}
                  style={{
                    width: `${Math.min(100, Math.abs(Number(row[key]) || 0) * 100)}%`,
                    background: COLORS[j],
                  }}
                  title={`${key}: ${format(row[key])}`}
                />
              ))}
            </div>
            <b>{format(row[numeric[0]])}</b>
          </div>
        ))}
      </div>
      <div className="allocation-donut">
        <svg viewBox="0 0 160 160">
          {donutSegments(data, numeric[0]).map((s, i) => (
            <circle
              key={i}
              cx="80"
              cy="80"
              r="54"
              fill="none"
              stroke={COLORS[i % COLORS.length]}
              strokeWidth="18"
              strokeDasharray={`${s.len} 339.3`}
              strokeDashoffset={-s.offset}
              transform="rotate(-90 80 80)"
            />
          ))}
        </svg>
        <strong>{data.length}</strong>
        <span>ALLOCATIONS</span>
      </div>
    </div>
  );
}

function RiskContribution({ data }) {
  const label = findKey(data, /ticker|asset/i),
    value = findKey(data, /risk_contribution|contribution/i);
  return (
    <div className="risk-bars">
      {data
        .sort((a, b) => (b[value] || 0) - (a[value] || 0))
        .map((r, i) => (
          <div key={i}>
            <span>{r[label]}</span>
            <i>
              <em
                style={{
                  width: `${Math.min(100, Math.abs(r[value] || 0) * 100)}%`,
                }}
              />
            </i>
            <b>{format(r[value])}</b>
            <small>
              {r[value] > 1 / data.length ? "OVER BUDGET" : "IN RANGE"}
            </small>
          </div>
        ))}
    </div>
  );
}
function EquityAudit({ data }) {
  return (
    <div className="primitive-shell">
      <TimeSeries data={data} area />
      <div className="audit-strip">
        <b>GROSS</b>
        <ArrowUpRight />
        <b>NET COSTS</b>
        <ArrowUpRight />
        <b>REALIZED EQUITY</b>
      </div>
    </div>
  );
}
function DrawdownOcean({ data }) {
  return (
    <ResponsiveContainer width="100%" height={390}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="dd" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={T.red} stopOpacity=".08" />
            <stop offset="1" stopColor={T.red} stopOpacity=".65" />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={T.soft} />
        <XAxis {...axis} dataKey={findKey(data, /date|time/i)} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        <ReferenceLine y={0} stroke={T.secondary} />
        <Area
          dataKey={findKey(data, /drawdown/i)}
          stroke={T.red}
          fill="url(#dd)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
function ContributionWaterfall({ data, stress = false }) {
  const label = findKey(data, /component|ticker|asset|factor|name/i),
    val = findKey(data, /value|contribution|return|pl_bps/i);
  const waterfall = [];
  let running = 0;
  for (const [index, row] of data.entries()) {
    const value = Number(row[val]) || 0;
    waterfall.push({ index, row, start: running, value });
    running += value;
  }
  return (
    <div className="waterfall">
      {waterfall.map(({ index, row, start, value }) => (
          <div key={index}>
            <span>{row[label]}</span>
            <i
              style={{
                marginLeft: `${Math.min(70, Math.abs(start) * 10)}%`,
                width: `${Math.max(3, Math.min(85, Math.abs(value) * 10))}%`,
                background: value < 0 ? T.red : stress ? T.amber : T.mint,
              }}
            />
            <b className={value < 0 ? "negative" : "positive"}>{format(value)}</b>
          </div>
      ))}
      <footer>
        <span>TOTAL</span>
        <b>{format(running)}</b>
      </footer>
    </div>
  );
}
function Matrix({ data, diverging = false, danger = false }) {
  const matrix = matrixShape(data);
  return (
    <div className="matrix-shell">
      <div
        className="matrix"
        style={{
          gridTemplateColumns: `110px repeat(${matrix.cols.length},minmax(52px,1fr))`,
        }}
      >
        <b></b>
        {matrix.cols.map((c) => (
          <b key={c}>{c}</b>
        ))}
        {matrix.rows.flatMap((r) => [
          <b key={`${r}-label`}>{r}</b>,
          ...matrix.cols.map((c) => {
            const v = matrix.map.get(`${r}|${c}`) || 0;
            return (
              <i
                key={`${r}-${c}`}
                style={{
                  background: heatColor(v, matrix.max, diverging, danger),
                }}
              >
                {format(v)}
              </i>
            );
          }),
        ])}
      </div>
      <div className="matrix-scale">
        <span>{diverging ? "−1" : "0"}</span>
        <i className={diverging ? "diverging" : ""} />
        <span>{diverging ? "+1" : "MAX"}</span>
      </div>
    </div>
  );
}

function PortfolioNetwork({ data, mode }) {
  const edges = data.filter((x) => x.source && x.target);
  const nodes = [...new Set(edges.flatMap((e) => [e.source, e.target]))];
  return (
    <div className="network-shell">
      <svg viewBox="0 0 700 420">
        {edges.slice(0, 80).map((e, i) => {
          const a = nodePoint(nodes.indexOf(e.source), nodes.length),
            b = nodePoint(nodes.indexOf(e.target), nodes.length);
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={mode === "systemic" ? T.red : T.mint}
              strokeOpacity={
                0.12 + Math.min(0.7, Math.abs(Number(e.weight) || 0.2))
              }
              strokeWidth={1 + Math.abs(Number(e.weight) || 0) * 3}
            />
          );
        })}
        {nodes.map((n, i) => {
          const p = nodePoint(i, nodes.length);
          return (
            <g key={n}>
              <circle
                cx={p.x}
                cy={p.y}
                r={20 + (i % 4) * 2}
                fill={T.raised}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth="2"
              />
              <text
                x={p.x}
                y={p.y + 4}
                fill={T.text}
                textAnchor="middle"
                fontSize="10"
              >
                {n}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="network-stats">
        <span>
          {nodes.length}
          <b>NODES</b>
        </span>
        <span>
          {edges.length}
          <b>EDGES</b>
        </span>
        <span>
          {mode.toUpperCase()}
          <b>TOPOLOGY</b>
        </span>
      </div>
    </div>
  );
}

function RegimeRibbon({ data }) {
  const x = findKey(data, /date|time/i),
    numeric = numericKeys(data).filter((k) => k !== x);
  return (
    <div className="regime-ribbon">
      <ResponsiveContainer width="100%" height={340}>
        <AreaChart data={data}>
          <CartesianGrid stroke={T.soft} />
          <XAxis {...axis} dataKey={x} />
          <YAxis {...axis} />
          <Tooltip contentStyle={tooltipStyle} />
          {numeric.slice(0, 5).map((k, i) => (
            <Area
              stackId="regime"
              key={k}
              dataKey={k}
              stroke={COLORS[i]}
              fill={COLORS[i]}
              fillOpacity={0.48}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      <div>
        {numeric.slice(0, 5).map((k, i) => (
          <span key={k}>
            <i style={{ background: COLORS[i] }} />
            {titleize(k)}
          </span>
        ))}
      </div>
    </div>
  );
}
function LiquidityLadder({ data }) {
  const label = findKey(data, /ticker|asset/i),
    val = numericKeys(data)[0];
  return (
    <div className="liquidity-ladder">
      {data
        .sort((a, b) => (b[val] || 0) - (a[val] || 0))
        .map((r, i) => (
          <div key={i}>
            <b>{String(i + 1).padStart(2, "0")}</b>
            <span>{r[label]}</span>
            <i>
              <em
                style={{
                  width: `${Math.min(100, (Math.abs(r[val] || 0) / Math.max(...data.map((x) => Math.abs(x[val] || 0)), 1)) * 100)}%`,
                }}
              />
            </i>
            <strong>{format(r[val])}</strong>
          </div>
        ))}
    </div>
  );
}
function LiquidationTape({ data }) {
  return (
    <div className="primitive-shell">
      <TimeSeries data={data} />
      <Interpretation text="Steeper early trajectories reduce exposure faster but consume more market capacity. Flat tails often indicate participation-rate or ADV constraints." />
    </div>
  );
}
function DecayCurve({ data }) {
  const x = findKey(data, /lag|day|age|horizon/i),
    y = findKey(data, /ic|value|weight/i);
  return (
    <div className="primitive-shell">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data}>
          <CartesianGrid stroke={T.soft} />
          <XAxis {...axis} dataKey={x} />
          <YAxis {...axis} />
          <Tooltip contentStyle={tooltipStyle} />
          <ReferenceLine y={0} stroke={T.red} />
          <Area
            dataKey={y}
            stroke={T.amber}
            fill={T.amber}
            fillOpacity={0.12}
          />
          <Line dataKey={y} stroke={T.amber} dot={false} strokeWidth={3} />
        </ComposedChart>
      </ResponsiveContainer>
      <Interpretation text="The economic half-life is where signal strength falls through half its initial value. Rebalance faster than decay, but slower than transaction-cost break-even." />
    </div>
  );
}
function ExecutionTrajectory({ data }) {
  const x = findKey(data, /time|day|step|date/i),
    numeric = numericKeys(data);
  return (
    <div className="execution-grid">
      <TimeSeries data={data} />
      <div className="execution-tape">
        {data.slice(0, 14).map((r, i) => (
          <div key={i}>
            <span>T+{r[x] ?? i}</span>
            <i
              style={{
                height: `${10 + Math.min(80, Math.abs(Number(r[numeric[0]]) || 0) * 80)}px`,
              }}
            />
            <b>{format(r[numeric[0]])}</b>
          </div>
        ))}
      </div>
    </div>
  );
}
function FireSaleCascade({ data }) {
  return (
    <div className="cascade">
      {data.map((r, i) => (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: i * 0.08 }}
          key={i}
        >
          <span>{r.peer || r.node || `Peer ${i + 1}`}</span>
          <i
            style={{
              width: `${Math.min(100, Math.abs(Number(r.portfolio_loss || r.loss_bps || 0)) * 100)}%`,
            }}
          />
          <b>{format(r.portfolio_loss ?? r.loss_bps)}</b>
          <em>CASCADE {i + 1}</em>
        </motion.div>
      ))}
    </div>
  );
}
function AllocationRiver({ data }) {
  const x = findKey(data, /date|time/i),
    numeric = numericKeys(data).filter((k) => k !== x);
  return (
    <ResponsiveContainer width="100%" height={390}>
      <AreaChart data={data}>
        <CartesianGrid stroke={T.soft} />
        <XAxis {...axis} dataKey={x} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        {numeric.slice(0, 8).map((k, i) => (
          <Area
            stackId="alloc"
            key={k}
            dataKey={k}
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={0.62}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

function TimeSeries({ data, area = false, zero = false, bands = false }) {
  const { x, ys } = infer(data);
  const Chart = area ? AreaChart : LineChart;
  return (
    <ResponsiveContainer width="100%" height={380}>
      <Chart data={data}>
        <CartesianGrid stroke={T.soft} vertical={false} />
        <XAxis {...axis} dataKey={x} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        {zero ? <ReferenceLine y={0} stroke={T.secondary} /> : null}
        {bands ? (
          <ReferenceArea y1={-0.2} y2={0.2} fill={T.acid} fillOpacity={0.035} />
        ) : null}
        {ys
          .slice(0, 7)
          .map((key, i) =>
            area ? (
              <Area
                key={key}
                dataKey={key}
                stroke={COLORS[i]}
                fill={COLORS[i]}
                fillOpacity={0.1}
                dot={false}
              />
            ) : (
              <Line
                key={key}
                dataKey={key}
                stroke={COLORS[i]}
                dot={false}
                strokeWidth={i === 0 ? 2.5 : 1.5}
              />
            ),
          )}
      </Chart>
    </ResponsiveContainer>
  );
}
function Distribution({ data, marker }) {
  const { x, ys } = infer(data);
  return (
    <ResponsiveContainer width="100%" height={370}>
      <BarChart data={data}>
        <CartesianGrid stroke={T.soft} />
        <XAxis {...axis} dataKey={x} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        {marker != null ? <ReferenceLine x={marker} stroke={T.red} /> : null}
        <Bar dataKey={ys[0]} fill={T.violet}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
function StressFan({ data }) {
  return (
    <div className="primitive-shell">
      <Distribution data={data} />
      <div className="stress-zones">
        <span>TAIL LOSS</span>
        <span>EXPECTED RANGE</span>
        <span>UPSIDE</span>
      </div>
    </div>
  );
}
function ExposureRiver({ data }) {
  return <TimeSeries data={data} zero />;
}
function EigenSpectrum({ data }) {
  return <Distribution data={data} />;
}
function RuinCurve({ data }) {
  return (
    <div className="primitive-shell">
      <TimeSeries data={data} />
      <Interpretation text="Ruin probability is nonlinear in leverage. The safe operating region ends before the visual elbow, not at the maximum-growth point." />
    </div>
  );
}
function CalendarMatrix({ data }) {
  return <Matrix data={normalizeCalendar(data)} diverging />;
}
function FoldTournament({ data }) {
  return <EvidenceTable data={data} highlight="test_sharpe" />;
}
function ConstraintBoard({ data }) {
  return (
    <div className="constraint-board">
      {data.map((r, i) => (
        <div
          className={String(r.status).includes("satisfied") ? "ok" : "watch"}
          key={i}
        >
          <ShieldAlert />
          <span>{r.constraint}</span>
          <b>{String(r.status || "CHECK").toUpperCase()}</b>
          <small>{format(r.value)}</small>
        </div>
      ))}
    </div>
  );
}
function ConditionBoard({ data }) {
  return (
    <div className="primitive-shell">
      <Distribution data={data} />
      <Interpretation text="Large condition numbers imply unstable inversion and fragile optimized weights. Prefer shrinkage or stronger constraints when the spectrum deteriorates." />
    </div>
  );
}
function AuditLedger({ data, danger = false }) {
  return (
    <div className="audit-ledger">
      {data.map((r, i) => (
        <div key={i}>
          <span className={danger ? "danger" : ""}>
            {danger ? <AlertTriangle /> : <ShieldAlert />}
          </span>
          <b>{r.test || r.factor || r.status || `Check ${i + 1}`}</b>
          <em>{r.status || r.interpretation || "observed"}</em>
          <small>{r.detail || format(Object.values(r).at(-1))}</small>
        </div>
      ))}
    </div>
  );
}
function ScenarioDeck({ data }) {
  return (
    <div className="scenario-deck">
      {data.map((r, i) => (
        <div key={i}>
          <span>SCN {String(i + 1).padStart(2, "0")}</span>
          <b>{r.scenario || r.name}</b>
          <strong
            className={
              (r.portfolio_return || r.return || 0) < 0
                ? "negative"
                : "positive"
            }
          >
            {format(r.portfolio_return ?? r.return ?? r.pl_bps)}
          </strong>
          <i
            style={{
              width: `${Math.min(100, Math.abs(Number(r.portfolio_return || r.return || 0)) * 300)}%`,
            }}
          />
        </div>
      ))}
    </div>
  );
}
function VerdictPanel({ data, danger = false }) {
  const row = data[0] || {};
  return (
    <div className={`verdict ${danger ? "danger" : ""}`}>
      <Crosshair />
      <small>MODEL VERDICT</small>
      <strong>
        {String(
          row.verdict || row.status || row.action || "CALCULATED",
        ).toUpperCase()}
      </strong>
      <p>
        {Object.entries(row)
          .map(([k, v]) => `${titleize(k)}: ${format(v)}`)
          .join(" · ")}
      </p>
    </div>
  );
}
function BetaConstellation({ data }) {
  return (
    <div className="beta-grid">
      {data.map((r, i) => {
        const beta = Number(r.beta) || 0;
        return (
          <div key={i}>
            <span>{r.factor}</span>
            <i
              style={{
                transform: `rotate(${beta * 35}deg)`,
                background: beta < 0 ? T.red : T.mint,
              }}
            />
            <strong>{format(beta)}</strong>
            <small>t {format(r.newey_west_t)}</small>
          </div>
        );
      })}
    </div>
  );
}
function RegimeScorecards({ data }) {
  return (
    <div className="regime-cards">
      {data.map((r, i) => (
        <div key={i} style={{ "--c": COLORS[i % COLORS.length] }}>
          <small>REGIME</small>
          <strong>{r.regime}</strong>
          {Object.entries(r)
            .filter(([, v]) => typeof v === "number")
            .slice(0, 4)
            .map(([k, v]) => (
              <span key={k}>
                {titleize(k)}
                <b>{format(v)}</b>
              </span>
            ))}
        </div>
      ))}
    </div>
  );
}
function DaysToLiquidate({ data }) {
  return <LiquidityLadder data={data} />;
}
function ComplianceGrid({ data }) {
  return (
    <div className="compliance-grid">
      {data.map((r, i) => (
        <div key={i}>
          <ShieldAlert />
          <b>{r.ticker}</b>
          <span>{r.bucket}</span>
        </div>
      ))}
    </div>
  );
}
function HalfLifeClock({ data }) {
  const row = data[0] || {},
    days = row.half_life_days || row.half_life || 0;
  return (
    <div className="half-life">
      <svg viewBox="0 0 200 200">
        <circle
          cx="100"
          cy="100"
          r="78"
          fill="none"
          stroke={T.soft}
          strokeWidth="18"
        />
        <circle
          cx="100"
          cy="100"
          r="78"
          fill="none"
          stroke={T.amber}
          strokeWidth="18"
          strokeDasharray={`${Math.min(490, Number(days) * 3)} 490`}
          transform="rotate(-90 100 100)"
        />
      </svg>
      <strong>{format(days)}</strong>
      <span>DAYS TO 50% SIGNAL</span>
      <small>{row.selected_model || row.taxonomy}</small>
    </div>
  );
}
function CrowdingRadar({ data }) {
  return <LiquidityLadder data={data} />;
}
function CostTape({ data }) {
  const total = data.reduce(
    (s, r) => s + Number(r.expected_cost || r.cost || r.total_cost || 0),
    0,
  );
  return (
    <div className="cost-tape">
      <div>
        <CircleDollarSign />
        <small>EXPECTED IMPLEMENTATION SHORTFALL</small>
        <strong>{format(total)}</strong>
      </div>
      <EvidenceTable data={data} />
    </div>
  );
}
function DebtRank({ data }) {
  return (
    <div className="debtrank">
      {data
        .sort((a, b) => (b.debtrank || 0) - (a.debtrank || 0))
        .map((r, i) => (
          <div key={i}>
            <b>{i + 1}</b>
            <span>{r.node}</span>
            <i
              style={{
                background: `conic-gradient(${T.red} ${(r.debtrank || 0) * 100}%,${T.soft} 0)`,
              }}
            />
            <strong>{format(r.debtrank)}</strong>
          </div>
        ))}
    </div>
  );
}
function StrategyDashboard({ data }) {
  return (
    <div className="strategy-grid">
      {data.map((r, i) => (
        <div key={i}>
          <header>
            <span>{r.strategy}</span>
            <i className={(r.sharpe || 0) > 0 ? "positive" : "negative"}>
              {format(r.sharpe)}
            </i>
          </header>
          <strong>{format(r.annual_return || r.return)}</strong>
          <small>RETURN</small>
          <footer>
            <span>VOL {format(r.annual_vol)}</span>
            <span>DD {format(r.max_drawdown)}</span>
          </footer>
        </div>
      ))}
    </div>
  );
}
function KillSwitchBoard({ data }) {
  return (
    <div className="kill-grid">
      {data.map((r, i) => (
        <div className={r.action || "hold"} key={i}>
          <span>{r.strategy}</span>
          <b>{String(r.action || "hold").toUpperCase()}</b>
          <i>
            <em
              style={{ width: `${Math.min(100, (r.proximity || 0) * 100)}%` }}
            />
          </i>
          <small>{format(r.proximity)}</small>
        </div>
      ))}
    </div>
  );
}
function SkillVerdict({ data }) {
  return <VerdictPanel data={data} />;
}
function CompliancePill({ value }) {
  return (
    <span className={`pill ${String(value).includes("satisfied") ? "ok" : ""}`}>
      {String(value)}
    </span>
  );
}

function EvidenceTable({ data, highlight }) {
  const [sort, setSort] = useState(null);
  const [desc, setDesc] = useState(true);
  const cols = Object.keys(data[0] || {}).slice(0, 14);
  const sorted = sort
    ? [...data].sort((a, b) => {
      const av = a[sort],
        bv = b[sort];
      return (
        (typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv))) * (desc ? -1 : 1)
      );
    })
    : data;
  return (
    <div className="evidence-table">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th
                key={c}
                onClick={() => {
                  if (sort === c) setDesc(!desc);
                  else {
                    setSort(c);
                    setDesc(true);
                  }
                }}
              >
                {titleize(c)} {sort === c ? (desc ? "↓" : "↑") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 300).map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td
                  className={`${highlight === c ? "highlight" : ""} ${Number(r[c]) < 0 ? "negative" : Number(r[c]) > 0 ? "positive" : ""}`}
                  key={c}
                >
                  {c === "status" ? (
                    <CompliancePill value={r[c]} />
                  ) : (
                    format(r[c])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <footer>{sorted.length} rows · click headers to sort</footer>
    </div>
  );
}

function HeaderPulse({ data }) {
  const count = rowCount(data);
  return (
    <div className="header-pulse">
      <svg viewBox="0 0 100 24">
        <polyline points={sparkPoints(count || 1)} />
      </svg>
      <b>{count}</b>
    </div>
  );
}
function Interpretation({ text }) {
  return (
    <div className="interpretation">
      <Sparkles size={14} />
      <span>{text}</span>
    </div>
  );
}
function Empty({ noun }) {
  return (
    <div className="terminal-empty">
      <Crosshair size={32} />
      <b>{noun.toUpperCase()} OUTPUT STANDBY</b>
      <span>Execute the engine to populate this purpose-built surface.</span>
    </div>
  );
}

function pick(response, section) {
  return (
    response?.[section.source]?.[section.dataKey] ??
    response?.charts?.[section.dataKey] ??
    response?.tables?.[section.dataKey]
  );
}
function toRows(value) {
  if (!value) return [];
  if (Array.isArray(value))
    return value.map((x, i) =>
      x && typeof x === "object" ? x : { index: i, value: x },
    );
  if (typeof value === "object") {
    const nested = Object.values(value).find(Array.isArray);
    if (nested) return nested;
    return Object.entries(value).map(([name, v]) =>
      v && typeof v === "object" ? { name, ...v } : { name, value: v },
    );
  }
  return [{ value }];
}
function format(value) {
  if (value == null || value === "") return "—";
  if (typeof value === "boolean") return value ? "YES" : "NO";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    const a = Math.abs(value);
    if (a >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (a >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (a > 0 && a < 0.01) return value.toFixed(4);
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
function numericKeys(data) {
  const sample = data.find(Boolean) || {};
  return Object.keys(sample).filter((k) => Number.isFinite(Number(sample[k])));
}
function findKey(data, re) {
  return Object.keys(data[0] || {}).find((k) => re.test(k));
}
function infer(
  data,
  xHints = [
    "date",
    "time",
    "horizon",
    "risk",
    "vol",
    "ticker",
    "asset",
    "name",
  ],
  yHints = [],
) {
  const ks = Object.keys(data[0] || {}),
    x =
      ks.find((k) => xHints.some((h) => k.toLowerCase().includes(h))) ||
      ks.find((k) => !Number.isFinite(Number(data[0][k]))) ||
      ks[0],
    nums = numericKeys(data).filter((k) => k !== x),
    preferred = yHints.flatMap((h) =>
      nums.filter((k) => k.toLowerCase().includes(h)),
    );
  return { x, ys: [...new Set([...preferred, ...nums])] };
}
function rowCount(value) {
  return toRows(value).length;
}
function normalizePayload(form) {
  return Object.fromEntries(
    Object.entries(form).map(([k, v]) => [
      k,
      k === "assets" && typeof v === "string"
        ? v
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : v,
    ]),
  );
}
function sparkPoints(seed) {
  return Array.from(
    { length: 10 },
    (_, i) => `${i * 10},${18 - (Math.sin(i * 0.9 + seed) * 6 + 7)}`,
  ).join(" ");
}
function donutSegments(data, key) {
  const vals = data.map((r) => Math.abs(Number(r[key]) || 0)),
    sum = vals.reduce((a, b) => a + b, 0) || 1;
  let offset = 0;
  return vals.map((v) => {
    const len = (v / sum) * 339.3,
      out = { len, offset };
    offset += len;
    return out;
  });
}
function matrixShape(data) {
  const rk =
      findKey(data, /^row$|source|ticker_a|asset_a/i) ||
      Object.keys(data[0] || {})[0],
    ck =
      findKey(data, /^col$|target|ticker_b|asset_b/i) ||
      Object.keys(data[0] || {})[1],
    vk =
      findKey(data, /value|weight|correlation|overlap|delta/i) ||
      numericKeys(data)[0],
    rows = [...new Set(data.map((r) => String(r[rk])))],
    cols = [...new Set(data.map((r) => String(r[ck])))],
    map = new Map(data.map((r) => [`${r[rk]}|${r[ck]}`, Number(r[vk]) || 0])),
    max = Math.max(...[...map.values()].map(Math.abs), 1e-9);
  return { rows, cols, map, max };
}
function heatColor(v, max, diverging, danger) {
  const a = 0.08 + (0.78 * Math.abs(v)) / max;
  if (danger) return `rgba(255,98,90,${a})`;
  if (diverging)
    return v < 0 ? `rgba(90,200,250,${a})` : `rgba(255,98,90,${a})`;
  return `rgba(183,255,60,${a})`;
}
function nodePoint(i, n) {
  const angle = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2,
    r = 145 + (i % 3) * 18;
  return { x: 350 + Math.cos(angle) * r, y: 210 + Math.sin(angle) * r };
}
function normalizeCalendar(data) {
  const first = data[0] || {};
  if (first.row != null) return data;
  const r = findKey(data, /year|date/i),
    cols = Object.keys(first).filter((k) => k !== r);
  return data.flatMap((row) =>
    cols.map((c) => ({ row: row[r], col: c, value: Number(row[c]) || 0 })),
  );
}

function downloadCsv(name, data) {
  if (!data.length) return;
  const columns = [...new Set(data.flatMap((row) => Object.keys(row || {})))];
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [
    columns.map(escape).join(","),
    ...data.map((row) =>
      columns
        .map((key) =>
          escape(
            typeof row[key] === "object" ? JSON.stringify(row[key]) : row[key],
          ),
        )
        .join(","),
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${name}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

const styles = `
  :root{--portfolio-row:40px;--portfolio-ease:cubic-bezier(.16,1,.3,1)}*{box-sizing:border-box}
  .portfolio-terminal{min-height:100dvh;background:radial-gradient(circle at 78% -15%,color-mix(in srgb,var(--engine) 12%,transparent),transparent 38%),${T.page};color:${T.text};padding:0 26px 120px;font-family:"IBM Plex Sans",sans-serif}
  .terminal-topbar{position:sticky;top:0;z-index:70;height:56px;margin:0 -26px;padding:0 26px;display:flex;align-items:center;gap:9px;background:rgba(3,5,4,.9);border-bottom:1px solid ${T.line};backdrop-filter:blur(20px)}
  .terminal-topbar button,.terminal-topbar .back{height:34px;border:1px solid ${T.line};background:${T.raised};color:${T.secondary};border-radius:7px;padding:0 11px;display:flex;align-items:center;gap:7px;text-decoration:none;cursor:pointer;font-weight:800}.terminal-topbar button:hover{color:${T.text};border-color:var(--engine)}.terminal-topbar .execute,.input-curtain .execute{background:var(--engine);border-color:var(--engine);color:#071006}
  .terminal-mark{display:flex;align-items:center;gap:10px}.terminal-mark b{width:29px;height:29px;border:1px solid var(--engine);color:var(--engine);display:grid;place-items:center;font:950 15px "JetBrains Mono",monospace}.terminal-mark span{color:${T.secondary};font:900 10px "JetBrains Mono",monospace;letter-spacing:.17em}.terminal-search{margin-left:auto;width:min(330px,26vw);height:34px;border:1px solid ${T.line};background:${T.screen};border-radius:7px;display:flex;align-items:center;gap:8px;padding:0 9px}.terminal-search input{min-width:0;flex:1;background:transparent;border:0;outline:0;color:${T.text}}.terminal-search kbd{color:${T.muted};font-size:9px}
  .run-rail{height:2px;position:sticky;top:56px;z-index:65;margin:0 -26px;background:${T.soft};overflow:hidden}.run-rail i{display:block;width:0;height:100%;background:var(--engine)}.run-rail.active i{animation:runRail 1.3s infinite}@keyframes runRail{0%{width:0;transform:translateX(0)}50%{width:55%}100%{width:25%;transform:translateX(400%)}}
  .terminal-hero{min-height:390px;padding:72px 2vw 48px;display:grid;grid-template-columns:1fr 300px;align-items:center;border-bottom:1px solid ${T.line}}.terminal-hero p{color:var(--engine);font:900 10px "JetBrains Mono",monospace;letter-spacing:.22em}.terminal-hero h1{max-width:980px;font-family:"Archivo Black",sans-serif;font-size:clamp(42px,5.6vw,82px);line-height:.92;letter-spacing:-.05em;margin:14px 0 18px}.terminal-hero span{display:block;max-width:820px;color:${T.secondary};font-size:17px;line-height:1.65}.hero-orbit{width:220px;height:220px;justify-self:end;border:1px solid ${T.line};border-radius:50%;position:relative;display:grid;place-items:center}.hero-orbit:before,.hero-orbit:after{content:"";position:absolute;border:1px solid color-mix(in srgb,var(--engine) 35%,transparent);border-radius:50%}.hero-orbit:before{inset:30px}.hero-orbit:after{inset:62px}.hero-orbit i{position:absolute;width:8px;height:8px;border-radius:50%;background:var(--engine);box-shadow:0 0 18px var(--engine)}.hero-orbit i:nth-child(1){left:20px;top:70px}.hero-orbit i:nth-child(2){right:35px;bottom:35px}.hero-orbit i:nth-child(3){top:10px}.hero-orbit b{font:950 48px "JetBrains Mono",monospace}.hero-orbit small{position:absolute;bottom:43px;color:var(--engine);font:900 8px "JetBrains Mono",monospace;letter-spacing:.18em}
  .metric-tape{display:flex;min-height:106px;margin:18px 0;border:1px solid ${T.line};background:${T.line};gap:1px;overflow:auto}.metric-tape>div{min-width:190px;flex:1;background:${T.panel};padding:13px;position:relative;display:grid;grid-template-columns:1fr 78px;gap:4px}.metric-tape .tape-label{min-width:64px;max-width:64px;display:flex;align-items:center;justify-content:center;color:var(--engine)}.tape-label span{writing-mode:vertical-rl;font:900 8px "JetBrains Mono",monospace;letter-spacing:.16em}.metric-tape small{color:${T.muted};font:900 9px "JetBrains Mono",monospace;text-transform:uppercase}.metric-tape strong{font:900 22px "JetBrains Mono",monospace}.metric-tape em{color:var(--engine);font:800 9px "JetBrains Mono",monospace;font-style:normal}.metric-tape svg{grid-column:2;grid-row:1/4;width:78px}.metric-tape polyline,.header-pulse polyline{fill:none;stroke:var(--engine);stroke-width:2}
  .preset-bar{min-height:44px;border:1px solid ${T.line};border-top:0;display:flex;align-items:center;gap:7px;padding:6px 10px;background:${T.panel};overflow:auto}.preset-bar>span{display:flex;align-items:center;gap:6px;color:var(--engine);font:900 8px "JetBrains Mono",monospace;letter-spacing:.14em;margin-right:8px}.preset-bar button{height:28px;border:1px solid ${T.line};background:${T.screen};color:${T.secondary};padding:0 9px;font:800 9px "JetBrains Mono",monospace;cursor:pointer}.preset-bar button:hover{border-color:var(--engine);color:var(--engine)}.preset-bar em{margin-left:auto;color:${T.muted};font:800 8px "JetBrains Mono",monospace;font-style:normal;white-space:nowrap}.preset-bar .preset-run{display:flex;align-items:center;gap:5px;background:color-mix(in srgb,var(--engine) 12%,${T.screen});color:var(--engine)}
  .quality-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:${T.line};border:1px solid ${T.line};margin:-8px 0 18px}.quality-strip>div{min-height:42px;background:${T.screen};padding:7px 10px;position:relative;display:grid;gap:3px}.quality-strip span{color:${T.muted};font:800 7px "JetBrains Mono",monospace;letter-spacing:.14em}.quality-strip b{color:${T.secondary};font:800 9px "JetBrains Mono",monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.quality-strip i{position:absolute;right:7px;top:7px;width:5px;height:5px;border-radius:50%;background:${T.mint};box-shadow:0 0 8px ${T.mint}}.quality-strip i.warn{background:${T.amber};box-shadow:0 0 8px ${T.amber}}
  .terminal-layout{display:grid;grid-template-columns:76px minmax(0,1fr) 210px;gap:16px;align-items:start}.output-rail{position:sticky;top:72px;max-height:calc(100dvh - 90px);overflow:auto;border:1px solid ${T.line};background:${T.panel};padding:8px;display:grid;gap:6px}.output-rail>b{color:var(--engine);font:900 8px "JetBrains Mono",monospace;letter-spacing:.2em;text-align:center;padding:7px}.output-rail button{width:58px;height:48px;border:1px solid ${T.soft};background:${T.screen};color:${T.muted};position:relative;display:grid;place-items:center;cursor:pointer}.output-rail button span{position:absolute;left:4px;top:3px;font:800 8px "JetBrains Mono",monospace}.output-rail button em{display:none}.output-rail button.active,.output-rail button:hover{border-color:var(--engine);color:var(--engine);transform:translateX(5px)}
  .terminal-lanes{display:grid;gap:14px}.terminal-lanes.split{grid-template-columns:1fr 1fr}.output-lane{min-width:0;display:grid;gap:14px}.lane-label{height:32px;position:sticky;top:66px;z-index:20;border:1px solid ${T.line};background:rgba(6,9,7,.9);backdrop-filter:blur(14px);display:flex;align-items:center;justify-content:space-between;padding:0 10px}.lane-label span{color:var(--engine);font:900 9px "JetBrains Mono",monospace;letter-spacing:.16em}.lane-label i{color:${T.muted};font:800 8px "JetBrains Mono",monospace;font-style:normal}.comparison{--engine:${T.cyan}}
  .terminal-card{border:1px solid ${T.line};background:linear-gradient(180deg,${T.panel},#060906);overflow:hidden;transition:border-color .2s,box-shadow .2s}.terminal-card.primary{border-left:3px solid var(--engine)}.terminal-card.active{border-color:color-mix(in srgb,var(--engine) 62%,${T.line});box-shadow:0 0 0 1px color-mix(in srgb,var(--engine) 10%,transparent),0 24px 80px rgba(0,0,0,.32)}.terminal-card.fullscreen{position:fixed;z-index:200;inset:16px;background:${T.page};overflow:auto}.terminal-card>header{height:58px;padding:0 14px;border-bottom:1px solid ${T.soft};display:flex;align-items:center;gap:12px}.terminal-card h2{font-size:15px;margin:2px 0 0}.terminal-card header small{color:${T.muted};font:800 8px "JetBrains Mono",monospace;letter-spacing:.13em}.terminal-card header button{width:31px;height:31px;border:1px solid ${T.line};background:${T.raised};color:${T.secondary};display:grid;place-items:center}.header-pulse{margin-left:auto;width:88px;height:28px;display:flex;align-items:center;gap:5px}.header-pulse svg{width:62px}.header-pulse b{color:var(--engine);font:900 9px "JetBrains Mono",monospace}.terminal-card>footer{height:28px;border-top:1px solid ${T.soft};padding:0 12px;display:flex;align-items:center;justify-content:space-between;color:${T.muted};font:800 8px "JetBrains Mono",monospace}.terminal-screen{min-height:430px;padding:16px;background:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px),radial-gradient(circle at 50% 0,color-mix(in srgb,var(--engine) 5%,transparent),transparent 45%);background-size:30px 30px,30px 30px,auto}
  .risk-telemetry{position:sticky;top:72px;border:1px solid ${T.line};background:${T.panel};padding:12px}.risk-telemetry>header{display:flex;align-items:center;gap:8px;color:var(--engine);font:900 9px "JetBrains Mono",monospace;letter-spacing:.15em}.risk-dial{display:grid;place-items:center;text-align:center;margin:20px 0}.risk-dial svg{width:150px}.risk-dial strong{font:950 21px "JetBrains Mono",monospace}.risk-dial span{color:${T.muted};font:800 8px "JetBrains Mono",monospace}.telemetry-list{display:grid}.telemetry-list div{padding:9px 0;border-top:1px solid ${T.soft};display:grid;gap:3px}.telemetry-list span{color:${T.muted};font-size:9px;text-transform:uppercase}.telemetry-list b{font:800 12px "JetBrains Mono",monospace}.risk-alert{margin-top:8px;padding:8px;background:rgba(255,98,90,.08);border:1px solid rgba(255,98,90,.3);color:${T.red};font-size:10px;display:flex;gap:6px}
  .primitive-shell{display:grid;gap:10px}.primitive-legend{display:flex;gap:12px;align-items:center;color:${T.secondary};font:800 9px "JetBrains Mono",monospace}.primitive-legend span{display:flex;align-items:center;gap:6px}.primitive-legend i{width:16px;height:2px}.primitive-legend b{margin-left:auto;color:var(--engine)}.interpretation{min-height:38px;border-left:3px solid var(--engine);background:color-mix(in srgb,var(--engine) 5%,transparent);padding:8px 10px;color:${T.secondary};font-size:10px;line-height:1.5;display:flex;gap:8px;align-items:center}.interpretation svg{color:var(--engine);flex:none}
  .allocation-layout{display:grid;grid-template-columns:1fr 190px;gap:20px}.allocation-bars{display:grid;gap:9px}.allocation-bars>div{display:grid;grid-template-columns:90px 1fr 65px;gap:8px;align-items:center}.allocation-bars span,.allocation-bars b{font:800 10px "JetBrains Mono",monospace}.allocation-bars span{color:${T.secondary}}.allocation-bars>div>div{height:15px;background:${T.soft};display:flex;align-items:center;gap:1px}.allocation-bars i{height:100%;display:block}.allocation-donut{display:grid;place-items:center;position:relative}.allocation-donut svg{width:170px}.allocation-donut strong{position:absolute;top:44%;font:950 28px "JetBrains Mono",monospace}.allocation-donut span{position:absolute;top:59%;color:${T.muted};font:800 8px "JetBrains Mono",monospace}
  .risk-bars{display:grid;gap:8px}.risk-bars>div{display:grid;grid-template-columns:80px 1fr 65px 82px;gap:8px;align-items:center}.risk-bars span,.risk-bars b,.risk-bars small{font:800 9px "JetBrains Mono",monospace}.risk-bars>div>i{height:9px;background:${T.soft}}.risk-bars em{display:block;height:100%;background:var(--engine);box-shadow:0 0 12px color-mix(in srgb,var(--engine) 35%,transparent)}.risk-bars small{color:${T.muted}}
  .matrix-shell{display:grid;gap:10px}.matrix{display:grid;gap:2px;overflow:auto}.matrix b,.matrix i{min-height:35px;display:grid;place-items:center;font:800 8px "JetBrains Mono",monospace}.matrix b{color:${T.muted}}.matrix i{font-style:normal;color:${T.text};transition:transform .12s}.matrix i:hover{transform:scale(1.08);z-index:2}.matrix-scale{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;color:${T.muted};font:800 8px "JetBrains Mono",monospace}.matrix-scale i{height:6px;background:linear-gradient(90deg,transparent,var(--engine))}.matrix-scale i.diverging{background:linear-gradient(90deg,${T.cyan},${T.screen},${T.red})}
  .network-shell{position:relative}.network-shell svg{width:100%;height:420px}.network-stats{position:absolute;left:8px;bottom:8px;display:flex;border:1px solid ${T.line};background:rgba(5,8,6,.8)}.network-stats span{min-width:90px;padding:8px;font:900 13px "JetBrains Mono",monospace;border-right:1px solid ${T.line}}.network-stats b{display:block;color:${T.muted};font-size:7px;margin-top:3px}
  .waterfall{display:grid;gap:7px}.waterfall>div{display:grid;grid-template-columns:120px 1fr 75px;gap:8px;align-items:center}.waterfall span,.waterfall b{font:800 9px "JetBrains Mono",monospace}.waterfall>div>i{height:17px;display:block}.waterfall footer{border-top:1px solid ${T.line};padding-top:10px;display:flex;justify-content:space-between}.positive{color:${T.mint}!important}.negative{color:${T.red}!important}
  .evidence-table{max-height:470px;overflow:auto;border:1px solid ${T.soft}}.evidence-table table{width:100%;border-collapse:collapse}.evidence-table th{position:sticky;top:0;z-index:2;background:${T.raised};color:var(--engine);padding:10px;text-align:left;font:900 8px "JetBrains Mono",monospace;letter-spacing:.1em;text-transform:uppercase;cursor:pointer}.evidence-table td{height:var(--portfolio-row);padding:0 10px;border-top:1px solid ${T.soft};color:${T.secondary};font:800 10px "JetBrains Mono",monospace;white-space:nowrap}.evidence-table tr:hover td{background:color-mix(in srgb,var(--engine) 5%,transparent);color:${T.text}}.evidence-table td.highlight{box-shadow:inset 2px 0 0 var(--engine)}.evidence-table>footer{position:sticky;bottom:0;background:${T.raised};padding:7px;color:${T.muted};font:800 8px "JetBrains Mono",monospace}.pill{padding:3px 6px;border:1px solid ${T.line};color:${T.amber}}.pill.ok{color:${T.mint};border-color:rgba(76,224,161,.3)}
  .constraint-board,.audit-ledger,.scenario-deck,.regime-cards,.strategy-grid,.kill-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:9px}.constraint-board>div,.audit-ledger>div,.scenario-deck>div,.regime-cards>div,.strategy-grid>div,.kill-grid>div{border:1px solid ${T.line};background:${T.screen};padding:12px}.constraint-board svg{width:18px}.constraint-board .ok svg{color:${T.mint}}.constraint-board .watch svg{color:${T.amber}}.constraint-board span,.constraint-board b,.constraint-board small{display:block;margin-top:6px}.constraint-board b{font:900 9px "JetBrains Mono",monospace;color:${T.mint}}
  .audit-ledger>div{display:grid;grid-template-columns:28px 1fr;gap:4px 8px}.audit-ledger span{grid-row:1/4;color:${T.mint}}.audit-ledger span.danger{color:${T.red}}.audit-ledger b{font-size:12px}.audit-ledger em,.audit-ledger small{color:${T.muted};font-size:10px;font-style:normal}.scenario-deck>div{position:relative;overflow:hidden}.scenario-deck span{color:${T.muted};font:800 8px "JetBrains Mono",monospace}.scenario-deck b,.scenario-deck strong{display:block;margin-top:9px}.scenario-deck i{position:absolute;bottom:0;left:0;height:3px;background:${T.red}}
  .verdict{min-height:350px;display:grid;place-items:center;align-content:center;text-align:center;border:1px solid color-mix(in srgb,var(--engine) 40%,${T.line});background:radial-gradient(circle,color-mix(in srgb,var(--engine) 10%,transparent),transparent 58%)}.verdict>svg{width:48px;height:48px;color:var(--engine)}.verdict small{color:${T.muted};font:900 9px "JetBrains Mono",monospace;letter-spacing:.2em;margin-top:16px}.verdict strong{font:950 36px "Archivo Black",sans-serif;margin:8px}.verdict p{max-width:650px;color:${T.secondary};font:10px "JetBrains Mono",monospace;line-height:1.6}.verdict.danger{--engine:${T.red}}
  .regime-cards>div{border-top:3px solid var(--c)}.regime-cards small{color:var(--c);font:900 8px "JetBrains Mono",monospace}.regime-cards strong{display:block;font-size:28px;margin:8px 0}.regime-cards span{display:flex;justify-content:space-between;border-top:1px solid ${T.soft};padding:6px 0;color:${T.muted};font-size:9px}.regime-cards b{color:${T.text}}
  .liquidity-ladder{display:grid;gap:7px}.liquidity-ladder>div{display:grid;grid-template-columns:30px 70px 1fr 80px;gap:8px;align-items:center}.liquidity-ladder b{color:var(--engine);font:900 9px "JetBrains Mono",monospace}.liquidity-ladder span,.liquidity-ladder strong{font:800 10px "JetBrains Mono",monospace}.liquidity-ladder>div>i{height:12px;background:${T.soft}}.liquidity-ladder em{height:100%;display:block;background:linear-gradient(90deg,var(--engine),${T.red})}
  .execution-grid{display:grid;gap:12px}.execution-tape{height:120px;display:flex;align-items:end;gap:5px;border-bottom:1px solid ${T.line};padding:0 8px}.execution-tape>div{flex:1;height:100%;display:flex;flex-direction:column;justify-content:end;align-items:center;gap:4px}.execution-tape i{width:70%;background:var(--engine)}.execution-tape span,.execution-tape b{font:700 7px "JetBrains Mono",monospace;color:${T.muted}}
  .half-life{min-height:360px;display:grid;place-items:center;align-content:center;position:relative}.half-life svg{width:220px}.half-life strong{position:absolute;top:42%;font:950 42px "JetBrains Mono",monospace}.half-life span{color:${T.amber};font:900 9px "JetBrains Mono",monospace}.half-life small{color:${T.muted};margin-top:6px}.cascade{display:grid;gap:10px}.cascade>div{border:1px solid ${T.line};padding:12px;display:grid;grid-template-columns:110px 1fr 80px 75px;gap:8px;align-items:center}.cascade i{height:9px;background:${T.red};box-shadow:0 0 15px rgba(255,98,90,.4)}.cascade span,.cascade b,.cascade em{font:800 9px "JetBrains Mono",monospace}.cascade em{color:${T.red};font-style:normal}
  .strategy-grid>div header,.strategy-grid>div footer{display:flex;justify-content:space-between}.strategy-grid>div>strong{display:block;font:950 28px "JetBrains Mono",monospace;margin-top:20px}.strategy-grid>div>small{color:${T.muted};font:800 8px "JetBrains Mono",monospace}.strategy-grid footer{border-top:1px solid ${T.soft};padding-top:8px;margin-top:16px;color:${T.secondary};font:800 8px "JetBrains Mono",monospace}.kill-grid>div{border-left:3px solid ${T.mint}}.kill-grid>div.watch{border-color:${T.amber}}.kill-grid>div.cut{border-color:${T.red};background:rgba(255,98,90,.06)}.kill-grid span,.kill-grid b{display:flex;justify-content:space-between}.kill-grid b{margin:8px 0;color:${T.mint}}.kill-grid .cut b{color:${T.red}}.kill-grid i{display:block;height:6px;background:${T.soft}}.kill-grid em{display:block;height:100%;background:currentColor}
  .stress-zones,.audit-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:2px}.stress-zones span,.audit-strip b{padding:8px;text-align:center;background:${T.screen};color:${T.muted};font:800 8px "JetBrains Mono",monospace}.stress-zones span:first-child{color:${T.red}}.audit-strip{display:flex;align-items:center;justify-content:center}.beta-grid,.compliance-grid,.debtrank{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.beta-grid>div,.compliance-grid>div,.debtrank>div{min-height:140px;border:1px solid ${T.line};background:${T.screen};padding:12px;display:grid;place-items:center}.beta-grid i{width:70px;height:2px;display:block}.beta-grid strong{font:900 22px "JetBrains Mono",monospace}.compliance-grid svg{color:${T.mint}}.debtrank i{width:48px;height:48px;border-radius:50%}.cost-tape>div:first-child{min-height:130px;display:grid;place-items:center;align-content:center;border:1px solid ${T.line};margin-bottom:10px}.cost-tape svg{color:var(--engine)}.cost-tape strong{font:950 30px "JetBrains Mono",monospace}.terminal-empty{min-height:390px;border:1px dashed ${T.line};display:grid;place-items:center;align-content:center;gap:10px;color:${T.muted};text-align:center}.terminal-empty svg{color:var(--engine)}.terminal-empty b{font:900 10px "JetBrains Mono",monospace;letter-spacing:.14em}
  .input-curtain{position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.78);backdrop-filter:blur(18px);padding:40px;overflow:auto}.input-curtain>section{max-width:1200px;margin:0 auto;border:1px solid ${T.line};background:${T.panel};box-shadow:0 50px 160px rgba(0,0,0,.8)}.input-curtain header,.input-curtain footer{min-height:66px;padding:0 18px;border-bottom:1px solid ${T.line};display:flex;align-items:center;justify-content:space-between}.input-curtain footer{border-top:1px solid ${T.line};border-bottom:0;justify-content:flex-end;gap:8px}.input-curtain button{height:34px;border:1px solid ${T.line};background:${T.raised};color:${T.secondary};padding:0 12px;display:flex;align-items:center;gap:7px}.input-curtain small{color:var(--engine);font:900 9px "JetBrains Mono",monospace;letter-spacing:.16em}.input-curtain h2{margin:4px 0 0}.contract-grid{padding:18px;display:grid;grid-template-columns:240px repeat(2,minmax(0,1fr));gap:12px}.contract-intro{grid-row:span 3;border:1px solid ${T.line};padding:18px;display:grid;align-content:start;gap:10px;color:var(--engine)}.contract-intro span{color:${T.muted};line-height:1.6}.contract-grid label{display:grid;gap:6px}.contract-grid label>span{display:flex;justify-content:space-between;color:${T.secondary};font-size:11px}.contract-grid em{color:${T.muted};font:800 8px "JetBrains Mono",monospace;font-style:normal}.contract-grid textarea,.contract-grid input{width:100%;border:1px solid ${T.line};background:${T.screen};color:${T.text};padding:10px;resize:vertical}.terminal-error{margin:14px 0;border:1px solid rgba(255,98,90,.35);background:rgba(255,98,90,.06);color:${T.red};padding:11px;display:flex;gap:8px;align-items:center}.terminal-error span{color:${T.secondary}}.terminal-toast{position:fixed;right:22px;bottom:22px;z-index:400;border:1px solid color-mix(in srgb,var(--engine) 45%,${T.line});background:${T.panel};padding:12px 16px;display:flex;gap:8px;color:var(--engine);font-weight:800}.spin{animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
  .inspector{position:fixed;right:0;top:0;bottom:0;z-index:350;width:min(560px,92vw);background:${T.panel};border-left:1px solid ${T.line};box-shadow:-40px 0 120px rgba(0,0,0,.65);padding:0 18px 80px;overflow:auto}.inspector>header{position:sticky;top:0;z-index:2;height:68px;margin:0 -18px;padding:0 18px;background:rgba(10,14,11,.94);backdrop-filter:blur(16px);border-bottom:1px solid ${T.line};display:flex;align-items:center;justify-content:space-between}.inspector small{color:var(--engine);font:900 8px "JetBrains Mono",monospace;letter-spacing:.15em}.inspector h2{margin:4px 0 0}.inspector button{height:32px;border:1px solid ${T.line};background:${T.raised};color:${T.secondary};display:flex;align-items:center;gap:6px;padding:0 9px}.inspector-lineage{display:grid;grid-template-columns:90px 1fr;gap:1px;background:${T.line};border:1px solid ${T.line};margin:16px 0}.inspector-lineage>*{background:${T.screen};padding:9px}.inspector-lineage span{color:${T.muted};font:800 8px "JetBrains Mono",monospace}.inspector-lineage code,.inspector-lineage b{color:${T.secondary};font:800 10px "JetBrains Mono",monospace}.inspector h3{margin:24px 0 10px;color:var(--engine);font:900 9px "JetBrains Mono",monospace;letter-spacing:.14em}.stat-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.stat-grid>div{border:1px solid ${T.line};background:${T.screen};padding:10px;display:grid;gap:5px}.stat-grid span,.stat-grid small{color:${T.muted};font:800 8px "JetBrains Mono",monospace}.stat-grid strong{font:900 19px "JetBrains Mono",monospace}.inspector pre{max-height:420px;overflow:auto;border:1px solid ${T.line};background:#030504;padding:12px;color:${T.secondary};font:10px/1.6 "JetBrains Mono",monospace}.inspector>footer{display:flex;gap:7px}
  .palette-overlay{position:fixed;inset:0;z-index:500;background:rgba(0,0,0,.72);backdrop-filter:blur(14px);display:grid;place-items:start center;padding-top:12vh}.palette-overlay>section{width:min(680px,calc(100vw - 28px));max-height:70vh;border:1px solid ${T.line};background:${T.panel};box-shadow:0 50px 150px rgba(0,0,0,.8);overflow:hidden}.palette-overlay label{height:58px;padding:0 14px;border-bottom:1px solid ${T.line};display:flex;align-items:center;gap:10px}.palette-overlay input{flex:1;background:transparent;border:0;outline:0;color:${T.text};font-size:15px}.palette-overlay kbd{color:${T.muted};font:800 8px "JetBrains Mono",monospace;border:1px solid ${T.line};padding:3px 5px}.palette-overlay>section>div{max-height:48vh;overflow:auto;padding:7px}.palette-overlay button{width:100%;height:42px;border:0;border-bottom:1px solid ${T.soft};background:transparent;color:${T.secondary};display:flex;align-items:center;gap:10px;padding:0 9px;text-align:left}.palette-overlay button:hover{background:color-mix(in srgb,var(--engine) 7%,transparent);color:${T.text}}.palette-overlay button span{flex:1}.palette-overlay footer{height:34px;border-top:1px solid ${T.line};padding:0 10px;display:flex;align-items:center;justify-content:space-between;color:${T.muted};font:800 8px "JetBrains Mono",monospace}
  .compact{--portfolio-row:30px}.compact .terminal-screen{min-height:350px}.compact .terminal-card>header{height:48px}
  @media(max-width:1200px){.terminal-layout{grid-template-columns:66px 1fr}.risk-telemetry{display:none}.terminal-lanes.split{grid-template-columns:1fr}.terminal-hero{grid-template-columns:1fr}.hero-orbit{display:none}}
  @media(max-width:760px){.portfolio-terminal{padding-left:12px;padding-right:12px}.terminal-topbar{margin:0 -12px;padding:0 12px}.terminal-search,.terminal-topbar button:not(.execute){display:none}.terminal-layout{grid-template-columns:1fr}.output-rail{position:fixed;left:8px;right:8px;bottom:8px;top:auto;z-index:100;display:flex;overflow:auto}.output-rail button{flex:none}.metric-tape{overflow:auto}.contract-grid{grid-template-columns:1fr}.contract-intro{grid-row:auto}.allocation-layout{grid-template-columns:1fr}.terminal-hero h1{font-size:42px}.terminal-screen{padding:9px}.terminal-card.fullscreen{inset:6px}}
`;
