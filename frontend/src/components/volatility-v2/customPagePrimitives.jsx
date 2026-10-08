"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { runVolatilityV2Feature } from "./api";
import { motion, AnimatePresence } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
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
  Activity,
  AlertTriangle,
  BarChart3,
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
import { getVolatilityV2Feature } from "./registry";

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
const FALLBACK_EPOCH_MS = Date.UTC(2026, 0, 1);

export const VOLATILITY_OUTPUT_BOOKS = {
  "01": [
    s("estimator-comparison", "Five-Estimator Comparison", "charts", "five_estimator_comparison", "estimatorComparison", { rank: "primary" }),
    s("calendar", "Volatility Calendar Heatmap", "charts", "vol_calendar", "calendarHeatmap", { fallbackKeys: ["annualized_vol_panel", "five_estimator_comparison"] }),
    s("ridge", "Rolling Vol Distribution Ridge", "charts", "vol_ridge", "ridgePlot", { fallbackKeys: ["annualized_vol_panel", "five_estimator_comparison"] }),
    s("cone", "Realized Volatility Cone", "charts", "volatility_cone", "volCone", { fallbackKeys: ["multi_window_estimator_panel", "multi_window_estimator_table"] }),
    s("signature", "Volatility Signature Plot", "charts", "vol_signature", "signaturePlot", { fallbackKeys: ["multi_window_estimator_panel", "five_estimator_comparison"] }),
    s("agreement", "Estimator Agreement Index", "charts", "estimator_agreement_index", "line"),
    s("annualized-panel", "Annualized Vol Panel", "charts", "annualized_vol_panel", "metricDeck"),
    s("multi-window", "Multi-Window Estimator Panel", "charts", "multi_window_estimator_panel", "table"),
    s("dm-tournament", "Diebold-Mariano Tournament", "tables", "diebold_mariano_tournament", "heatmap", { config: { rowKey: "row", colKey: "col", valueKey: "value", diverging: true } }),
    s("ranked-panel", "Cross-Asset Ranked Panel", "tables", "cross_asset_ranked_panel", "table"),
    s("range-correlation", "Range Correlation Matrix", "charts", "range_correlation_matrix", "heatmap", { config: { diverging: true } }),
    s("opening-gap", "Opening Gap Fragility", "charts", "opening_gap_fragility", "line"),
    s("br-proxy", "Bandi-Russell Liquidity Proxy", "charts", "bandi_russell_estimator", "area"),
    s("vol-momentum", "Vol-Adjusted Momentum Panel", "charts", "vol_adjusted_momentum_panel", "table"),
  ],
  "02": [
    s("scoreboard", "GARCH Model Scoreboard", "tables", "model_scoreboard", "garchScoreboard", { rank: "primary", fallbackKeys: ["garch_scoreboard"] }),
    s("qq-plot", "Residual Q-Q Adequacy Plot", "charts", "qq_plot", "qqPlot", { fallbackKeys: ["standardized_residual_qq", "garch_qq_plot"] }),
    s("term-structure", "GARCH-Implied Term Structure", "charts", "garch_term_structure", "termStructure"),
    s("news-impact", "News Impact Curve", "charts", "news_impact_curve", "line"),
    s("var-series", "Conditional VaR Time Series", "charts", "conditional_var_timeseries", "varChart", { fallbackKeys: ["conditional_var_time_series"] }),
    s("pit-test", "PIT Density Test", "charts", "pit_histogram", "bar"),
    s("vol-state", "Volatility State Gauge", "charts", "volatility_state_gauge", "volGauge", { fallbackKeys: ["summary_cards"], source: "summary" }),
    s("realized-garch", "Realized-GARCH Variance", "charts", "realized_garch_variance_series", "area"),
    s("nic-ribbon", "Regime-Conditional NIC Ribbon", "charts", "regime_conditional_nic_ribbon", "line"),
    s("nyblom", "Nyblom Parameter Stability", "tables", "nyblom_parameter_stability", "table"),
    s("aparch-delta", "APARCH Delta Benchmark", "tables", "aparch_delta_benchmark", "table"),
    s("var-backtests", "VaR Backtests", "tables", "var_backtests", "table"),
    s("surface", "Synthetic Vol Surface", "charts", "synthetic_vol_surface", "surfaceGrid"),
  ],
  "03": [
    s("parameter-table", "HAR Parameter Table", "tables", "har_parameter_table", "table", { rank: "primary" }),
    s("forecast-chart", "Multi-Horizon Forecast Chart", "charts", "multi_horizon_forecast_chart", "forecastBands"),
    s("accuracy", "Forecast Accuracy Table", "tables", "forecast_accuracy_table", "table"),
    s("mcs", "Model Confidence Set", "tables", "model_confidence_set", "table"),
    s("jump-proxy", "Jump Proxy Time Series", "charts", "jump_proxy_time_series", "area"),
    s("leverage", "Leverage Effect Chart", "charts", "leverage_effect_chart", "line"),
    s("acsv", "ACSV Predictive Contribution", "charts", "acsv_predictive_contribution", "area"),
    s("macro", "HAR-X Macro Contribution", "charts", "har_x_macro_contribution", "bar"),
    s("walk-forward", "Walk-Forward Forecast Check", "charts", "walk_forward_forecast_chart", "line"),
    s("bootstrap", "Bootstrap Forecast Bands", "charts", "forecast_confidence_bands", "forecastBands"),
    s("jump-disagreement", "Jump Estimator Disagreement", "tables", "jump_estimator_disagreement", "table"),
  ],
  "04": [
    s("timeline", "Probabilistic Regime Timeline", "charts", "probabilistic_regime_timeline", "probabilityStack", { rank: "primary" }),
    s("dashboard", "Current Regime Dashboard", "charts", "current_regime_dashboard", "regimeDashboard"),
    s("conditional", "Regime-Conditional Statistics", "tables", "regime_conditional_stats", "table"),
    s("transition", "Regime Transition Heatmap", "charts", "transition_heatmap", "heatmap", { fallbackKeys: ["regime_transition_heatmap"], config: { rowKey: "row", colKey: "col", valueKey: "value" } }),
    s("divergence", "Method Divergence Indicator", "charts", "method_divergence_indicator", "line"),
    s("alerts", "Regime Transition Alert Log", "tables", "transition_alert_log", "table"),
    s("adaptive", "Adaptive EW-HMM Timeline", "charts", "adaptive_hmm_timeline", "probabilityStack"),
    s("filtered", "Smoothed vs Filtered Posterior", "charts", "smoothed_vs_filtered_comparison", "dualPosterior"),
    s("duration", "Regime Duration Survival", "tables", "regime_duration_survival", "table"),
    s("sync", "Global Vol Regime Sync Index", "charts", "global_vol_regime_sync_index", "line"),
    s("hmm-bic", "HMM BIC K Selection", "tables", "hmm_bic_k_selection", "table"),
  ],
  "05": [
    s("vrp-series", "VRP Time Series", "charts", "vrp_time_series", "area", { rank: "primary" }),
    s("zscore", "VRP Z-Score Panel", "charts", "vrp_zscore_panel", "line"),
    s("cross-asset", "Cross-Asset VRP Comparison", "tables", "cross_asset_vrp_comparison", "table"),
    s("predictability", "Return Predictability Panel", "tables", "return_predictability_regression", "table"),
    s("mean-reversion", "VRP Mean Reversion Speed", "tables", "vrp_mean_reversion_speed", "table"),
    s("component", "VRP Component Attribution", "charts", "vrp_component_attribution", "bar"),
    s("term", "VRP Term Structure", "charts", "vrp_term_structure", "termStructure"),
    s("regime-btz", "Regime-Conditional BTZ", "tables", "regime_conditional_btz", "table"),
    s("lookbacks", "Z-Score Lookback Comparison", "tables", "vrp_zscore_lookback_comparison", "table"),
  ],
  "06": [
    s("index", "Total Connectedness Index", "charts", "connectedness_index", "area", { rank: "primary" }),
    s("net-ranking", "Net Spillover Ranking", "tables", "net_spillover_ranking", "table"),
    s("network", "Dynamic Connectedness Network", "charts", "spillover_network_graph", "network"),
    s("fevd", "Pairwise FEVD Heatmap", "charts", "pairwise_fevd_heatmap", "heatmap", { config: { rowKey: "row", colKey: "col", valueKey: "value" } }),
    s("to-from", "Rolling To/From Decomposition", "charts", "rolling_to_from_decomposition", "bar"),
    s("alert", "Connectedness Regime Alert", "tables", "connectedness_regime_alert", "table"),
    s("frequency", "Frequency-Decomposed Connectedness", "charts", "frequency_decomposed_connectedness", "frequencyBands"),
    s("car", "Connectedness-at-Risk", "charts", "connectedness_at_risk", "metricDeck", { fallbackKeys: ["connectedness_at_risk"], source: "tables" }),
    s("irf", "VAR Impulse Response", "charts", "var_impulse_response", "line"),
  ],
  "07": [
    s("corr", "Correlation Matrix Heatmap", "charts", "correlation_heatmap", "heatmap", { rank: "primary", config: { diverging: true } }),
    s("corr-movie", "Rolling Correlation Mini-Movie", "charts", "rolling_corr_animation", "corrAnimation", { fallbackKeys: ["rolling_correlation_matrices"] }),
    s("normal-crisis", "Normal vs Crisis Correlation", "charts", "normal_vs_crisis_correlation", "tripleHeatmap"),
    s("dcc-ts", "DCC Time Series", "charts", "dcc_time_series", "line"),
    s("eigen", "Eigenvalue Decomposition", "charts", "eigenvalue_decomposition", "composedBarLine"),
    s("condition", "Condition Number History", "charts", "condition_number_history", "line"),
    s("risk-attr", "Portfolio Risk Attribution", "tables", "portfolio_risk_attribution", "table"),
    s("min-var", "Minimum Variance Portfolio", "tables", "minimum_variance_portfolio", "table"),
    s("comparison", "Sample/EWMA/LW/DCC Comparison", "tables", "sample_ewma_lw_dcc_comparison", "table"),
    s("midas", "DCC-MIDAS Long-Run Correlation", "charts", "dcc_midas_long_run_correlation", "heatmap", { config: { diverging: true } }),
    s("prob-crisis", "Probability-Weighted Crisis Correlation", "charts", "probability_weighted_crisis_correlation", "heatmap", { config: { diverging: true } }),
    s("torsion", "Minimum Torsion Attribution", "tables", "minimum_torsion_risk_attribution", "table"),
    s("fisher", "Fisher Z Crisis Amplification", "tables", "fisher_z_crisis_amplification", "table"),
    s("pairwise-cov", "Pairwise Covariance Contribution", "charts", "pairwise_covariance_contribution", "heatmap"),
  ],
  "08": [
    s("vol-shock", "Vol Shock Bar Chart", "charts", "vol_shock_bar_chart", "bar", { rank: "primary" }),
    s("waterfall", "Portfolio P&L Attribution", "charts", "portfolio_pnl_attribution_waterfall", "waterfall"),
    s("reverse", "Reverse Stress Scenario", "tables", "reverse_stress_scenario", "table"),
    s("analog", "Historical Analog Comparison", "tables", "historical_analog_comparison", "table"),
    s("irf", "Contagion Impulse Response", "charts", "contagion_impulse_response", "line"),
    s("irf-bands", "IRF Confidence Bands", "charts", "contagion_impulse_response_bands", "forecastBands"),
    s("multi", "Multi-Scenario Comparison", "tables", "multi_scenario_comparison", "table"),
    s("var-cvar", "Stress VaR/CVaR", "tables", "stress_var_cvar", "table"),
    s("glasso", "Graphical LASSO Analog", "tables", "historical_analog_glasso", "table"),
    s("copula", "Reverse Stress Copula", "tables", "reverse_stress_copula", "table"),
    s("adversarial", "Adversarial Scenario", "tables", "adversarial_scenario", "table"),
    s("distribution", "Stress Distribution", "charts", "stress_distribution", "stressDistribution"),
  ],
  "09": [
    s("dashboard", "Portfolio Vol Dashboard", "charts", "portfolio_vol_dashboard", "metricDeck", { rank: "primary" }),
    s("gap", "Vol-to-Target Gap Gauge", "charts", "vol_to_target_gap_gauge", "volGauge"),
    s("budget", "Vol Budget Attribution Waterfall", "charts", "vol_budget_attribution_waterfall", "budgetWaterfall"),
    s("scaling", "Scaling Factor History", "charts", "scaling_factor_history", "line"),
    s("target", "Regime-Conditional Target Evolution", "charts", "regime_conditional_target_evolution", "line"),
    s("recommendation", "Rebalancing Recommendation", "tables", "rebalancing_recommendation", "table"),
    s("backtest", "Historical Vol-Targeting Backtest", "charts", "historical_vol_targeting_backtest", "area"),
    s("budget-table", "Portfolio Vol Budget Table", "tables", "portfolio_vol_budget_table", "table"),
    s("two-step", "Two-Step Rebalancing Detail", "tables", "two_step_rebalancing_detail", "table"),
    s("costs", "Almgren-Chriss Transaction Costs", "tables", "almgren_chriss_transaction_costs", "table"),
    s("kelly", "Kelly Vol Target", "tables", "kelly_vol_target", "table"),
    s("breaches", "Vol Budget Breach Log", "tables", "vol_budget_breach_log", "table"),
    s("performance", "Historical Backtest Performance", "tables", "historical_backtest_performance", "table"),
  ],
};

function s(id, title, source, dataKey, chartType, options = {}) {
  return { id, title, source: options.source || source, dataKey, chartType, rank: options.rank || "supporting", fallbackKeys: options.fallbackKeys || [], config: options.config || {} };
}

function rowsFrom(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map((item, index) => (item && typeof item === "object" ? item : { name: String(index + 1), value: item }));
  if (typeof value !== "object") return [{ name: "Value", value }];
  const recordKey = Object.keys(value).find((key) => Array.isArray(value[key]) && value[key].some((row) => row && typeof row === "object"));
  if (recordKey) return value[recordKey];
  const seriesKeys = Object.keys(value).filter((key) => Array.isArray(value[key]));
  if (seriesKeys.length) {
    const length = Math.max(...seriesKeys.map((key) => value[key].length));
    return Array.from({ length }, (_, index) => Object.fromEntries(seriesKeys.map((key) => [key, value[key][index]])));
  }
  return Object.entries(value).map(([key, item]) => (item && typeof item === "object" ? { name: titleize(key), ...item } : { name: titleize(key), value: item }));
}

function numberLike(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const n = Number(value.replace(/[$,%x]/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

function titleize(value) {
  return String(value ?? "").replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function formatValue(value) {
  if (value == null || value === "") return "-";
  if (typeof value === "boolean") return value ? "YES" : "NO";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "-";
    const abs = Math.abs(value);
    if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (abs >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (abs > 0 && abs < 0.01) return value.toFixed(4);
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function pickData(response, section) {
  if (!response) return null;
  if (section.source === "summary") return response.summary_cards || [];
  if (section.source === "alerts") return response.alerts || [];
  const bucket = response[section.source] || {};
  const keys = [section.dataKey];
  for (const key of keys) {
    if (bucket?.[key] != null) return bucket[key];
    if (response?.[key] != null) return response[key];
  }
  return null;
}

function inferKeys(rows, config = {}) {
  const sample = rows.find(Boolean) || {};
  const keys = Object.keys(sample);
  const xKey = config.xKey || keys.find((key) => /date|time|horizon|bucket|rank|asset|model|name|metric|component|scenario|regime/i.test(key)) || keys[0] || "name";
  const yKeys = config.yKeys || keys.filter((key) => key !== xKey && numberLike(sample[key]) != null).slice(0, 8);
  return { xKey, yKeys: yKeys.length ? yKeys : ["value"] };
}

function isoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
}

function variance(values) {
  if (!values.length) return 0;
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
}

function copyData(value) {
  const rows = rowsFrom(value);
  if (!rows.length || typeof navigator === "undefined") return;
  const cols = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  navigator.clipboard?.writeText([cols.join("\t"), ...rows.map((row) => cols.map((col) => row[col] ?? "").join("\t"))].join("\n"));
}

function workspacePayload(feature, form, sections, response) {
  return {
    module: "volatility-v2",
    feature: { id: feature.id, title: feature.title },
    form,
    sections: sections.map(({ id, title, source, dataKey, chartType }) => ({ id, title, source, dataKey, chartType })),
    response,
    exported_at: new Date().toISOString(),
  };
}

function downloadText(filename, text, type = "text/plain") {
  if (typeof document === "undefined") return;
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportWorkspace(feature, form, sections, response) {
  downloadText(`atlas-vol-f${feature.id}-workspace.json`, JSON.stringify(workspacePayload(feature, form, sections, response), null, 2), "application/json");
}

function sectionTsv(section, response) {
  const rows = rowsFrom(pickData(response, section));
  if (!rows.length) return "";
  const cols = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  return [`# ${section.title}`, cols.join("\t"), ...rows.map((row) => cols.map((col) => row[col] ?? "").join("\t"))].join("\n");
}

function exportAllTsv(sections, response) {
  return sections.map((section) => sectionTsv(section, response)).filter(Boolean).join("\n\n");
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

function VolTooltip({ active, payload, label, rows = [], xKey = "date" }) {
  if (!active || !payload?.length) return null;
  const index = rows.findIndex((row) => String(row[xKey]) === String(label));
  const prev = index > 0 ? rows[index - 1] : null;
  return (
    <div className="vol-tooltip xhair-tooltip">
      <b>{label}</b>
      {payload.map((entry, index) => (
        <span key={`${entry.dataKey}-${index}`}>
          <i style={{ background: entry.color }} />
          {entry.name || entry.dataKey}
          <strong>{formatValue(entry.value)}</strong>
          {prev && numberLike(entry.value) != null && numberLike(prev[entry.dataKey]) != null ? (
            <em className={numberLike(entry.value) >= numberLike(prev[entry.dataKey]) ? "up" : "dn"}>
              {numberLike(entry.value) >= numberLike(prev[entry.dataKey]) ? "▲" : "▼"} {formatValue(Math.abs(numberLike(entry.value) - numberLike(prev[entry.dataKey])))}
            </em>
          ) : null}
        </span>
      ))}
    </div>
  );
}

function TerminalAssetInput({ value, onChange, multi = false, placeholder = "Search ticker..." }) {
  const [query, setQuery] = useState("");
  const tokens = String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
  const suggestions = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO", "BTC_USD", "ETH_USD", "AAPL", "MSFT", "NVDA"].filter((item) => item.toLowerCase().includes(query.toLowerCase()) && !tokens.includes(item));
  function add(symbol) {
    const next = multi ? [...tokens, symbol] : [symbol];
    onChange(next.join(","));
    setQuery("");
  }
  return (
    <div className="bbg-symbol-box">
      <Search size={15} />
      <div className="bbg-symbol-tokens">
        {tokens.map((token) => <button key={token} onClick={() => onChange(tokens.filter((item) => item !== token).join(","))} type="button">{token}<X size={11} /></button>)}
        <input value={query} onChange={(event) => setQuery(event.target.value.toUpperCase())} onKeyDown={(event) => {
          if (event.key === "Enter" && query.trim()) add(query.trim().replace("-", "_"));
          if (event.key === "Backspace" && !query && tokens.length) onChange(tokens.slice(0, -1).join(","));
        }} placeholder={tokens.length ? "" : placeholder} />
      </div>
      {query ? (
        <div className="bbg-symbol-menu">
          {suggestions.slice(0, 8).map((symbol) => <button key={symbol} onClick={() => add(symbol)} type="button"><strong>{symbol}</strong><span>LOCAL UNIVERSE</span><em>Equity / ETF</em></button>)}
          <button onClick={() => add(query.trim().replace("-", "_"))} type="button"><strong>{query}</strong><span>CUSTOM SYMBOL</span><em>Use as typed</em></button>
        </div>
      ) : null}
    </div>
  );
}

function VolInputForm({ feature, form, onChange }) {
  const groups = useMemo(() => {
    const map = new Map();
    for (const field of feature.fields || []) {
      const group = field.group || "Parameters";
      map.set(group, [...(map.get(group) || []), field]);
    }
    return [...map.entries()];
  }, [feature]);
  return (
    <div className="vol-input-grid">
      {groups.map(([group, fields]) => (
        <section className="vol-input-group" key={group}>
          <h3>{group}</h3>
          <div>
            {fields.map((field) => <VolField field={field} key={field.key} onChange={(value) => onChange(field.key, value)} value={form[field.key]} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

function VolField({ field, value, onChange }) {
  const isTicker = field.inputType === "ticker" || /asset|symbol|ticker/i.test(field.key);
  const isMultiTicker = field.inputType === "multiTicker" || /assets|universe/i.test(field.key);
  if (isMultiTicker || isTicker) {
    return <label className="vol-field"><span>{field.label}</span><TerminalAssetInput multi={isMultiTicker} onChange={onChange} value={value} placeholder={field.label} />{field.helper ? <small>{field.helper}</small> : null}</label>;
  }
  if (field.type === "select") {
    return (
      <label className="vol-field">
        <span>{field.label}</span>
        <div className="vol-chip-row">
          {(field.options || []).map((option) => <button className={String(value) === String(option) ? "active" : ""} key={String(option)} onClick={() => onChange(String(option))} type="button">{String(option)}</button>)}
        </div>
      </label>
    );
  }
  if (field.type === "tokens") {
    const selected = String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
    return (
      <label className="vol-field vol-wide">
        <span>{field.label}</span>
        <div className="vol-chip-row">
          {(field.options || []).map((option) => {
            const active = selected.includes(String(option));
            return <button className={active ? "active" : ""} key={String(option)} onClick={() => onChange((active ? selected.filter((x) => x !== String(option)) : [...selected, String(option)]).join(","))} type="button">{String(option)}</button>;
          })}
        </div>
      </label>
    );
  }
  if (field.type === "textarea") {
    return <label className="vol-field vol-wide"><span>{field.label}</span><textarea value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder={field.placeholder || "{}"} /></label>;
  }
  return (
    <label className="vol-field">
      <span>{field.label}<b>{formatValue(numberLike(value) ?? value)}</b></span>
      <input value={value ?? ""} onChange={(event) => onChange(event.target.value)} />
      {field.presets ? <div className="vol-presets">{field.presets.map((preset) => <button key={String(preset)} onClick={() => onChange(String(preset))} type="button">{formatValue(preset)}</button>)}</div> : null}
    </label>
  );
}

function OutputDock({ sections, activeId, onJump, onReorder }) {
  const [dragging, setDragging] = useState(null);
  return (
    <nav className="vol-dock" aria-label="Volatility outputs">
      <strong>OUTPUTS</strong>
      {sections.map((section, index) => (
        <button
          className={`${activeId === section.id ? "active" : ""} ${dragging === section.id ? "dragging" : ""}`}
          draggable
          key={section.id}
          onClick={() => onJump(section.id)}
          onDragEnd={() => setDragging(null)}
          onDragOver={(event) => event.preventDefault()}
          onDragStart={() => setDragging(section.id)}
          onDrop={() => {
            onReorder?.(dragging, section.id);
            setDragging(null);
          }}
          title={`${section.title} · drag to reorder`}
          type="button"
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <BarChart3 size={16} />
          <em>{section.title}</em>
        </button>
      ))}
    </nav>
  );
}

function OutputMinimap({ sections, activeId, onJump }) {
  if (sections.length < 6) return null;
  return (
    <aside className="vol-minimap" aria-label="Output minimap">
      <span>MAP</span>
      {sections.map((section, index) => (
        <button className={activeId === section.id ? "active" : ""} key={section.id} onClick={() => onJump(section.id)} title={section.title} type="button">
          <i data-type={section.chartType} />
          <em>{String(index + 1).padStart(2, "0")}</em>
        </button>
      ))}
    </aside>
  );
}

function DensityToggle({ value, onChange }) {
  const options = [
    ["compact", "—"],
    ["comfortable", "≡"],
    ["spacious", "☰"],
  ];
  return (
    <div className="density-toggle" role="group" aria-label="Table density">
      {options.map(([key, label]) => <button className={value === key ? "active" : ""} key={key} onClick={() => onChange(key)} title={key} type="button">{label}</button>)}
    </div>
  );
}

function ToastRack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-rack" role="region" aria-live="polite">
      {toasts.map((toast) => (
        <div className={`toast toast-${toast.type}`} key={toast.id}>
          <span className="toast-dot" />
          <span className="toast-msg">{toast.message}</span>
          <button onClick={() => onDismiss(toast.id)} type="button">×</button>
        </div>
      ))}
    </div>
  );
}

function RunProgressBar({ running, progress }) {
  if (!running && progress === 0) return null;
  return (
    <div className="vol-run-progress" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${Math.max(3, progress * 100)}%` }} />
      {running ? <b>COMPUTING {Math.round(progress * 100)}%</b> : <b>RUN COMPLETE</b>}
    </div>
  );
}

function HeaderSparkline({ data }) {
  const rows = rowsFrom(data);
  const values = rows.flatMap((row) => Object.values(row).map(numberLike).filter((value) => value != null)).slice(-28);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${24 - ((value - min) / range) * 22}`).join(" ");
  return <svg className="header-spark" viewBox="0 0 100 28" aria-hidden="true"><polyline points={points} /></svg>;
}

function StickySummaryBar({ sections, activeId, response }) {
  const section = sections.find((item) => item.id === activeId) || sections[0];
  const data = section ? pickData(response, section) : null;
  const rows = rowsFrom(data);
  const nums = rows.flatMap((row) => Object.entries(row).map(([key, value]) => ({ key, value: numberLike(value) })).filter((item) => item.value != null)).slice(0, 4);
  if (!response || !nums.length) return null;
  return (
    <div className="sticky-summary">
      <span>{section.title}</span>
      {nums.map((item) => <b key={item.key}>{titleize(item.key)} <em>{formatValue(item.value)}</em></b>)}
    </div>
  );
}

function WorkspaceSearch({ query, setQuery, matches, onJump, hitCount = 0 }) {
  return (
    <div className="workspace-search">
      <Search size={14} />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search outputs or cells..." />
      {query ? (
        <div>
          <p>{hitCount} table/data hits</p>
          {matches.length ? matches.map((section) => <button key={section.id} onClick={() => onJump(section.id)} type="button">{section.title}<span>{section.chartType}</span></button>) : <p>No output match</p>}
        </div>
      ) : null}
    </div>
  );
}

function DrawingCanvas({ enabled, resetKey }) {
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const resize = () => {
      const rect = parent.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.strokeStyle = TOKENS.accent;
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [resetKey]);
  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
  }, [resetKey]);
  if (!enabled) return null;
  return <canvas className="vol-drawing" ref={canvasRef} onPointerDown={(event) => { drawing.current = true; const ctx = event.currentTarget.getContext("2d"); ctx.beginPath(); ctx.moveTo(event.nativeEvent.offsetX, event.nativeEvent.offsetY); }} onPointerMove={(event) => { if (!drawing.current) return; const ctx = event.currentTarget.getContext("2d"); ctx.lineTo(event.nativeEvent.offsetX, event.nativeEvent.offsetY); ctx.stroke(); }} onPointerUp={() => { drawing.current = false; }} onPointerLeave={() => { drawing.current = false; }} />;
}

function VolOutputCard({ section, response, active, onActive, cinemaId, onCinema, staggerIndex = 0, searchQuery = "", compare = false, draggable = false, onDragStart, onDrop }) {
  const [full, setFull] = useState(false);
  const [draw, setDraw] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const data = pickData(response, section);
  const focused = cinemaId === section.id;
  const dimmed = cinemaId && !focused;
  return (
    <motion.article
      draggable={draggable}
      id={compare ? `compare-${section.id}` : section.id}
      className={`vol-output-card ${section.rank === "primary" ? "primary" : ""} ${active ? "active" : ""} ${full ? "fullscreen" : ""} ${focused ? "cinema-focused" : ""} ${dimmed ? "cinema-dimmed" : ""} ${compare ? "compare-card" : ""}`}
      initial={{ opacity: 0, y: 24, filter: "blur(3px)" }}
      animate={{ opacity: dimmed ? 0.08 : 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.36, delay: staggerIndex * 0.045, ease: [0.2, 0.9, 0.2, 1] }}
      onDragOver={(event) => event.preventDefault()}
      onDragStart={() => onDragStart?.(section.id)}
      onDrop={() => onDrop?.(section.id)}
      onMouseEnter={() => onActive(section.id)}
    >
      <header>
        <div><p>{compare ? "comparison" : `${section.source}.${section.dataKey}`}</p><h2>{section.title}</h2></div>
        <HeaderSparkline data={data} />
        <div className="vol-card-actions">
          <button onClick={() => setDraw((v) => !v)} className={draw ? "active" : ""} title="Draw" type="button"><Pencil size={15} /></button>
          <button onClick={() => setResetKey((v) => v + 1)} title="Clear drawing" type="button"><Eraser size={15} /></button>
          <button onClick={() => copyData(data)} title="Copy data" type="button"><Copy size={15} /></button>
          <button onClick={() => onCinema(focused ? null : section.id)} className={focused ? "active" : ""} title="Cinema mode" type="button"><Film size={15} /></button>
          <button onClick={() => setFull((v) => !v)} title="Fullscreen" type="button"><Maximize2 size={15} /></button>
        </div>
      </header>
      <div className="vol-screen">
        <VolRenderer section={section} data={data} response={response} searchQuery={searchQuery} />
        <DrawingCanvas enabled={draw} resetKey={resetKey} />
      </div>
    </motion.article>
  );
}

function VolRenderer({ section, data, response, searchQuery = "" }) {
  if (!data) return <VolEmpty section={section} response={response} />;
  if (section.chartType === "calendarHeatmap") return <VolCalendarHeatmap data={data} />;
  if (section.chartType === "ridgePlot") return <VolRidgePlot data={data} />;
  if (section.chartType === "volCone") return <VolatilityCone data={data} />;
  if (section.chartType === "qqPlot") return <QQPlot data={data} />;
  if (section.chartType === "signaturePlot") return <VolSignaturePlot data={data} />;
  if (section.chartType === "corrAnimation") return <CorrelationMiniMovies data={data} />;
  if (section.chartType === "metricDeck") return <MetricDeck data={data} />;
  if (section.chartType === "estimatorComparison") return <EstimatorComparison data={data} />;
  if (section.chartType === "garchScoreboard") return <GarchScoreboard data={data} />;
  if (section.chartType === "termStructure") return <VolChart data={data} type="line" config={{ xKey: "horizon", yKeys: ["p05", "p25", "p50", "p75", "p95", "vol", "value"] }} />;
  if (section.chartType === "probabilityStack") return <ProbabilityStack data={data} />;
  if (section.chartType === "regimeDashboard") return <RegimeDashboard data={data} />;
  if (section.chartType === "heatmap") return <Heatmap data={data} config={section.config} />;
  if (section.chartType === "tripleHeatmap") return <TripleHeatmap data={data} />;
  if (section.chartType === "network") return <NetworkGraph data={data} />;
  if (section.chartType === "waterfall") return <Waterfall data={data} />;
  if (section.chartType === "budgetWaterfall") return <Waterfall data={data} valueKey="budget_deviation" nameKey="asset" />;
  if (section.chartType === "stressDistribution") return <VolChart data={data} type="area" config={{ xKey: "bucket", yKeys: ["loss"] }} />;
  if (section.chartType === "volGauge") return <VolGauge data={data} />;
  if (section.chartType === "forecastBands") return <ForecastBands data={data} />;
  if (section.chartType === "surfaceGrid") return <SurfaceGrid data={data} />;
  if (section.chartType === "frequencyBands") return <FrequencyBands data={data} />;
  if (section.chartType === "dualPosterior") return <DualPosterior data={data} />;
  if (section.chartType === "composedBarLine") return <ComposedBars data={data} />;
  if (section.chartType === "varChart") return <VolChart data={data} type="area" config={{ yKeys: ["returns", "var_95", "var_99", "var_975", "expected_shortfall", "breach"] }} />;
  if (section.chartType === "table") return <VolTable data={data} searchQuery={searchQuery} />;
  return <VolChart data={data} type={section.chartType} config={section.config} />;
}

function VolEmpty({ section, response }) {
  const available = response ? Object.entries(response).flatMap(([bucket, value]) => value && typeof value === "object" ? Object.keys(value).map((key) => `${bucket}.${key}`) : []).slice(0, 8) : [];
  return <div className="vol-empty"><Activity size={18} /><span>{response ? `${section.source}.${section.dataKey} not returned` : "Awaiting run"}</span>{available.length ? <small>{available.join(" · ")}</small> : null}</div>;
}

function MetricDeck({ data }) {
  const rows = rowsFrom(data).slice(0, 8);
  return (
    <div className="metric-deck">
      {rows.map((row, index) => {
        const value = row.value ?? row.score ?? row.percentile ?? row.vol ?? Object.values(row).find((v) => typeof v === "number");
        const n = numberLike(value);
        const pct = Math.max(0, Math.min(100, numberLike(row.percentile ?? row.pct ?? n) ?? 0));
        const delta = numberLike(row.delta ?? row.change);
        const trend = delta == null ? pct < 50 : delta >= 0;
        return <div className={`vol-metric ${trend ? "up" : "dn"}`} key={index}><span>{row.label || row.metric || row.name || row.asset || `Metric ${index + 1}`}</span><strong>{formatValue(value)}{row.unit ? <em>{row.unit}</em> : null}</strong>{delta != null ? <small className={delta >= 0 ? "pos" : "neg"}>{delta >= 0 ? "▲" : "▼"} {formatValue(Math.abs(delta))}</small> : null}<PercentileArc value={pct} /><Spark value={n ?? index} /></div>;
      })}
    </div>
  );
}

function PercentileArc({ value }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct > 80 ? TOKENS.red : pct > 60 ? TOKENS.amber : TOKENS.green;
  const dash = pct / 100 * 88;
  return (
    <svg className="pct-arc" viewBox="0 0 72 40" aria-label={`${pct.toFixed(0)} percentile`}>
      <path d="M 8 34 A 28 28 0 0 1 64 34" fill="none" stroke="#1d1710" strokeWidth="5" strokeLinecap="round" />
      <path d="M 8 34 A 28 28 0 0 1 64 34" fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${dash} 88`} />
      <text x="36" y="33" textAnchor="middle" fill={color} fontSize="10" fontWeight="900" fontFamily="JetBrains Mono, monospace">{pct.toFixed(0)}p</text>
    </svg>
  );
}

function Spark() {
  return null;
}

function EstimatorComparison({ data }) {
  return <VolChart data={data} type="area" config={{ yKeys: ["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"], fillOpacity: 0.16 }} />;
}

function VolCalendarHeatmap({ data }) {
  const sourceRows = rowsFrom(data);
  const cells = sourceRows.map((row, index) => {
    const date = new Date(row.date || row.timestamp || FALLBACK_EPOCH_MS - (sourceRows.length - index) * 86400000);
    return { date, label: row.date || date.toISOString().slice(0, 10), week: isoWeek(date), dow: date.getDay(), val: numberLike(row.yang_zhang ?? row.yz ?? row.vol ?? row.value ?? row.close_to_close) ?? 0 };
  }).filter((row) => row.dow >= 1 && row.dow <= 5);
  if (!cells.length) return <VolEmpty section={{ source: "charts", dataKey: "vol_calendar" }} response={{}} />;
  const weeks = [...new Set(cells.map((cell) => cell.week))].sort((a, b) => a - b).slice(-52);
  const map = new Map(cells.map((cell) => [`${cell.week}-${cell.dow}`, cell]));
  const min = Math.min(...cells.map((cell) => cell.val));
  const max = Math.max(...cells.map((cell) => cell.val));
  const color = (value) => {
    const t = (value - min) / (max - min || 1);
    if (t < 0.33) return `rgba(20,184,166,${0.18 + t * 1.3})`;
    if (t < 0.66) return `rgba(245,164,0,${0.16 + t})`;
    return `rgba(239,68,68,${0.2 + t * 0.72})`;
  };
  return (
    <div className="vcal-wrap">
      <div className="vcal-legend"><span>LOW</span><i /><span>HIGH</span></div>
      <div className="vcal-days">{["M", "T", "W", "T", "F"].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}</div>
      <div className="vcal-grid" style={{ "--cols": weeks.length }}>
        {weeks.map((week) => [1, 2, 3, 4, 5].map((dow) => {
          const cell = map.get(`${week}-${dow}`);
          return <b key={`${week}-${dow}`} style={{ background: cell ? color(cell.val) : "transparent" }} title={cell ? `${cell.label}: ${formatValue(cell.val)}` : "No data"} />;
        }))}
      </div>
    </div>
  );
}

function VolRidgePlot({ data, groupBy = "quarter" }) {
  const sourceRows = rowsFrom(data);
  const rows = sourceRows.map((row, index) => ({ date: new Date(row.date || FALLBACK_EPOCH_MS - (sourceRows.length - index) * 86400000), value: numberLike(row.yang_zhang ?? row.vol ?? row.value ?? row.close_to_close) ?? 0 })).filter((row) => Number.isFinite(row.value));
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "vol_ridge" }} response={{}} />;
  const groups = {};
  for (const row of rows) {
    const label = groupBy === "quarter" ? `${row.date.getFullYear()} Q${Math.ceil((row.date.getMonth() + 1) / 3)}` : `${row.date.getFullYear()}-${String(row.date.getMonth() + 1).padStart(2, "0")}`;
    (groups[label] ||= []).push(row.value);
  }
  const labels = Object.keys(groups).sort().slice(-12);
  const all = labels.flatMap((label) => groups[label]);
  const xMin = Math.max(0, Math.min(...all) - 2);
  const xMax = Math.max(...all) + 2;
  const width = 560;
  const band = 42;
  const total = labels.length * 24 + 52;
  const xs = Array.from({ length: 70 }, (_, i) => xMin + (i / 69) * (xMax - xMin));
  const toX = (x) => ((x - xMin) / (xMax - xMin || 1)) * (width - 70) + 52;
  const kde = (values, x) => {
    const h = Math.max(0.8, 1.06 * Math.sqrt(variance(values) || 1) * values.length ** -0.2);
    return values.reduce((sum, value) => sum + Math.exp(-0.5 * ((x - value) / h) ** 2) / (h * Math.sqrt(2 * Math.PI)), 0) / values.length;
  };
  return (
    <div className="ridge-wrap">
      <svg viewBox={`0 0 ${width} ${total}`} className="ridge-svg">
        {labels.map((label, index) => {
          const values = groups[label];
          const density = xs.map((x) => kde(values, x));
          const maxD = Math.max(...density) || 1;
          const yBase = total - 28 - index * 24;
          const color = SERIES[index % SERIES.length];
          const d = density.map((v, i) => `${i ? "L" : "M"}${toX(xs[i]).toFixed(1)},${(yBase - (v / maxD) * band).toFixed(1)}`).join(" ") + ` L${toX(xs.at(-1)).toFixed(1)},${yBase} L${toX(xs[0]).toFixed(1)},${yBase} Z`;
          return <g key={label}><path d={d} fill={color} fillOpacity=".18" stroke={color} strokeWidth="1.4" /><text x="44" y={yBase - 7} fill={color} fontSize="9" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontWeight="800">{label}</text></g>;
        })}
        {[xMin, (xMin + xMax) / 2, xMax].map((x) => <text key={x} x={toX(x)} y={total - 8} fill={TOKENS.muted} fontSize="9" textAnchor="middle">{x.toFixed(0)}%</text>)}
      </svg>
    </div>
  );
}

function VolatilityCone({ data }) {
  const raw = data?.cone || data;
  const rows = rowsFrom(raw).map((row, index) => ({
    window: numberLike(row.window ?? row.window_days ?? row.horizon ?? row.name) ?? (index + 1) * 21,
    p10: numberLike(row.p10 ?? row.q10) ?? numberLike(row.value) * 0.7,
    p25: numberLike(row.p25 ?? row.q25) ?? numberLike(row.value) * 0.85,
    p50: numberLike(row.p50 ?? row.median ?? row.value) ?? 0,
    p75: numberLike(row.p75 ?? row.q75) ?? numberLike(row.value) * 1.15,
    p90: numberLike(row.p90 ?? row.q90) ?? numberLike(row.value) * 1.3,
    current: numberLike(row.current ?? row.latest ?? row.value) ?? 0,
  })).filter((row) => row.p50 || row.current);
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "volatility_cone" }} response={{}} />;
  return (
    <div className="cone-wrap">
      <ResponsiveContainer height={380} width="100%">
        <ComposedChart data={rows} margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="window" tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} tickFormatter={(value) => `${value}d`} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} />
          <Tooltip content={<VolTooltip />} />
          <Area dataKey="p90" stroke="transparent" fill="rgba(245,164,0,.05)" />
          <Area dataKey="p75" stroke="transparent" fill="rgba(245,164,0,.12)" />
          <Line dataKey="p50" stroke={TOKENS.accent} strokeWidth={2} dot={false} type="monotone" />
          <Line dataKey="current" stroke={TOKENS.green} strokeWidth={0} dot={{ r: 5, fill: TOKENS.green, stroke: TOKENS.page, strokeWidth: 2 }} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="cone-interp">{rows.map((row) => <span key={row.window}>{row.window}D <b>{row.current > row.p75 ? "HIGH" : row.current < row.p25 ? "LOW" : "NORMAL"}</b></span>)}</div>
    </div>
  );
}

function QQPlot({ data }) {
  const rows = rowsFrom(data).map((row, index) => ({ theoretical: numberLike(row.theoretical ?? row.q_theoretical ?? row.x) ?? index, empirical: numberLike(row.empirical ?? row.q_empirical ?? row.y ?? row.value) ?? 0 })).filter((row) => Number.isFinite(row.theoretical) && Number.isFinite(row.empirical));
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "qq_plot" }} response={{}} />;
  const min = Math.min(...rows.flatMap((row) => [row.theoretical, row.empirical]));
  const max = Math.max(...rows.flatMap((row) => [row.theoretical, row.empirical]));
  return (
    <ResponsiveContainer height={380} width="100%">
      <ScatterChart margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
        <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} />
        <XAxis dataKey="theoretical" type="number" domain={[min, max]} tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} />
        <YAxis dataKey="empirical" type="number" domain={[min, max]} tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} />
        <Tooltip content={<VolTooltip />} />
        <ReferenceLine segment={[{ x: min, y: min }, { x: max, y: max }]} stroke={TOKENS.muted} strokeDasharray="4 4" />
        <Scatter data={rows}>{rows.map((row, index) => <Cell key={index} fill={Math.abs(row.empirical - row.theoretical) > 0.5 ? TOKENS.red : TOKENS.accent} fillOpacity={0.72} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function VolSignaturePlot({ data }) {
  const rows = rowsFrom(data).map((row, index) => ({ lag_days: numberLike(row.lag_days ?? row.window ?? row.horizon) ?? index + 1, rv: numberLike(row.rv ?? row.realized_variance ?? row.vol ?? row.value) ?? 0 })).sort((a, b) => a.lag_days - b.lag_days);
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "vol_signature" }} response={{}} />;
  const first = rows[0].rv || 1;
  const last = rows.at(-1).rv;
  const label = Math.abs(last - first) / Math.abs(first) < 0.05 ? "FLAT DIFFUSION SIGNATURE" : last > first ? "UPWARD LONG-MEMORY SLOPE" : "DOWNWARD MICROSTRUCTURE SLOPE";
  return <div className="sig-wrap"><VolChart data={rows} type="line" config={{ xKey: "lag_days", yKeys: ["rv"] }} /><div className="sig-interp">{label}</div></div>;
}

function CorrelationMiniMovies({ data }) {
  const frames = Array.isArray(data) ? data : rowsFrom(data);
  const [frame, setFrame] = useState(0);
  const current = frames[frame] || {};
  const assets = current.assets || current.labels || Object.keys(current.matrix?.[0] || {}).filter(Boolean);
  const matrix = current.matrix || [];
  if (!frames.length || !assets.length) return <VolEmpty section={{ source: "charts", dataKey: "rolling_corr_animation" }} response={{}} />;
  const cellValue = (ri, ci) => Array.isArray(matrix[ri]) ? matrix[ri][ci] : numberLike(matrix[ri]?.[assets[ci]]) ?? 0;
  return (
    <div className="cmm-wrap">
      <div className="cmm-controls"><button onClick={() => setFrame(Math.max(0, frame - 1))} type="button">‹</button><button onClick={() => setFrame((frame + 1) % frames.length)} type="button">▶</button><input type="range" min="0" max={frames.length - 1} value={frame} onChange={(e) => setFrame(Number(e.target.value))} /><span>{current.date || current.period || `${frame + 1}/${frames.length}`}</span></div>
      <div className="cmm-matrix" style={{ "--cols": assets.length + 1 }} key={frame}>
        <i />
        {assets.map((asset) => <b key={asset}>{asset}</b>)}
        {assets.map((asset, ri) => [<b className="cmm-row-label" key={`${asset}-label`}>{asset}</b>, ...assets.map((col, ci) => { const v = cellValue(ri, ci); const alpha = 0.12 + Math.abs(v) * 0.75; return <em key={`${asset}-${col}`} style={{ background: ri === ci ? "rgba(245,164,0,.15)" : v >= 0 ? `rgba(239,68,68,${alpha})` : `rgba(96,165,250,${alpha})` }}>{ri === ci ? "" : Number(v).toFixed(2)}</em>; })])}
      </div>
    </div>
  );
}

function GarchScoreboard({ data }) {
  const rows = rowsFrom(data).map((row) => ({
    ...row,
    score: numberLike(row.rank_score ?? row.score),
    aic: numberLike(row.aic),
    bic: numberLike(row.bic),
    qlike: numberLike(row.qlike),
    llf: numberLike(row.log_likelihood ?? row.llf),
  })).sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999) || (a.aic ?? Infinity) - (b.aic ?? Infinity));
  const mcsRows = rows.filter((row) => row.mcs_member || row.mcs || row.mcs_inclusion).slice(0, 8);
  return (
    <div className="garch-shell">
      {mcsRows.length ? (
        <div className="garch-mcs-strip">
          <span>MCS SURVIVORS</span>
          {mcsRows.map((row, index) => <b key={`${row.model || index}-${row.distribution || "dist"}`}>{row.model || row.spec || "GARCH"} · {row.distribution || row.error_dist || "normal"}</b>)}
        </div>
      ) : null}
      <div className="garch-board">
        {rows.slice(0, 24).map((row, index) => (
          <div className={index === 0 || row.winner ? "winner" : ""} key={`${row.model || index}-${row.distribution || "dist"}`}>
            <strong>{String(index + 1).padStart(2, "0")}</strong>
            <b>{row.model || row.spec || "GARCH"}</b>
            <span>{row.distribution || row.error_dist || "normal"}</span>
            <em>AIC {formatValue(row.aic)}</em>
            <em>BIC {formatValue(row.bic)}</em>
            <em>QLIKE {formatValue(row.qlike)}</em>
            <em>LL {formatValue(row.llf)}</em>
            {row.mcs_member || row.mcs || row.mcs_inclusion ? <i>MCS</i> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function VolChart({ data, type = "line", config = {} }) {
  const rows = rowsFrom(data);
  const { xKey, yKeys } = inferKeys(rows, config);
  if (!rows.length) return <VolEmpty section={{ source: "data", dataKey: "chart" }} response={{}} />;
  const axis = { tick: { fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }, axisLine: false, tickLine: false };
  if (type === "bar" || type === "horizontalBar") {
    const vertical = type === "horizontalBar";
    return (
      <ResponsiveContainer height={Math.max(320, vertical ? rows.length * 34 : 340)} width="100%">
        <BarChart data={rows} layout={vertical ? "vertical" : undefined} margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
          <defs>
            {SERIES.map((color, index) => (
              <linearGradient id={`bar-pos-${index}`} key={color} x1="0" x2={vertical ? "1" : "0"} y1="0" y2={vertical ? "0" : "1"}>
                <stop offset="0%" stopColor={color} stopOpacity=".94" />
                <stop offset="100%" stopColor={color} stopOpacity=".42" />
              </linearGradient>
            ))}
            <linearGradient id="bar-neg" x1="0" x2={vertical ? "1" : "0"} y1="0" y2={vertical ? "0" : "1"}>
              <stop offset="0%" stopColor={TOKENS.red} stopOpacity=".92" />
              <stop offset="100%" stopColor={TOKENS.red} stopOpacity=".34" />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={!vertical} horizontal={vertical} />
          {vertical ? <XAxis type="number" {...axis} /> : <XAxis dataKey={xKey} {...axis} />}
          {vertical ? <YAxis dataKey={xKey} type="category" width={150} {...axis} /> : <YAxis {...axis} />}
          <Tooltip content={<VolTooltip rows={rows} xKey={xKey} />} cursor={{ fill: "rgba(245,164,0,.05)" }} />
          {yKeys.map((key, index) => <Bar dataKey={key} fill={`url(#bar-pos-${index % SERIES.length})`} key={key} radius={vertical ? [0, 5, 5, 0] : [5, 5, 0, 0]}>{rows.map((row, cell) => <Cell key={cell} fill={(numberLike(row[key]) ?? 0) < 0 ? "url(#bar-neg)" : `url(#bar-pos-${index % SERIES.length})`} />)}<LabelList dataKey={key} position={vertical ? "right" : "top"} formatter={(value) => formatValue(value)} fill={TOKENS.muted} fontSize={9} fontFamily="JetBrains Mono, monospace" /></Bar>)}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  if (type === "scatter") {
    return (
      <ResponsiveContainer height={360} width="100%">
        <ScatterChart margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} />
          <XAxis dataKey={config.xKey || yKeys[0] || xKey} type="number" {...axis} />
          <YAxis dataKey={config.yKey || yKeys[1] || "value"} type="number" {...axis} />
          <Tooltip content={<VolTooltip rows={rows} xKey={config.xKey || yKeys[0] || xKey} />} cursor={{ stroke: "rgba(245,164,0,.25)", strokeDasharray: "4 3" }} />
          <Scatter data={rows} fill={TOKENS.accent} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }
  const Chart = type === "area" || type === "stackedArea" ? AreaChart : LineChart;
  return (
    <div className="asc-wrap">
      <ResponsiveContainer height={400} width="100%">
        <Chart data={rows} margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
          <defs>{yKeys.map((key, index) => <linearGradient id={`vol-grad-${key}-${index}`} key={key} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={SERIES[index % SERIES.length]} stopOpacity={config.fillOpacity ?? .28} /><stop offset="100%" stopColor={SERIES[index % SERIES.length]} stopOpacity={.02} /></linearGradient>)}</defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey={xKey} {...axis} />
          <YAxis {...axis} />
          <Tooltip content={<VolTooltip rows={rows} xKey={xKey} />} cursor={{ stroke: "rgba(245,164,0,.25)", strokeDasharray: "4 3" }} />
          <ReferenceLine y={0} stroke={TOKENS.muted} strokeDasharray="3 5" />
          {yKeys.map((key, index) => type === "area" || type === "stackedArea" ? <Area activeDot={{ r: 5, fill: TOKENS.panel, stroke: SERIES[index % SERIES.length], strokeWidth: 2 }} dataKey={key} fill={`url(#vol-grad-${key}-${index})`} key={key} stackId={type === "stackedArea" ? "stack" : undefined} stroke={SERIES[index % SERIES.length]} strokeWidth={2} type="monotone" /> : <Line activeDot={{ r: 5, fill: TOKENS.panel, stroke: SERIES[index % SERIES.length], strokeWidth: 2 }} dataKey={key} dot={false} key={key} stroke={SERIES[index % SERIES.length]} strokeWidth={2} type="monotone" />)}
          {rows.length > 252 ? <Brush dataKey={xKey} height={26} travellerWidth={7} stroke={TOKENS.border} fill={TOKENS.panel} tickFormatter={() => ""} /> : null}
        </Chart>
      </ResponsiveContainer>
      <div className="asc-legend">{yKeys.map((key, index) => <span key={key} style={{ "--c": SERIES[index % SERIES.length] }}><i />{titleize(key)}<b>{formatValue(rows.at(-1)?.[key])}</b></span>)}</div>
    </div>
  );
}

function Heatmap({ data, config = {} }) {
  const rows = rowsFrom(data);
  const rowKey = config.rowKey || "row";
  const colKey = config.colKey || "col";
  const valueKey = config.valueKey || "value";
  const [hovered, setHovered] = useState(null);
  const rowLabels = [...new Set(rows.map((r) => String(r[rowKey] ?? r.asset ?? r.name ?? "")))].filter(Boolean);
  const colLabels = [...new Set(rows.map((r) => String(r[colKey] ?? r.factor ?? r.name ?? "")))].filter(Boolean);
  const maxAbs = Math.max(1e-9, ...rows.map((r) => Math.abs(numberLike(r[valueKey]) ?? 0)));
  const valueAt = (row, col) => {
    const cell = rows.find((r) => String(r[rowKey] ?? r.asset ?? r.name ?? "") === row && String(r[colKey] ?? r.factor ?? r.name ?? "") === col);
    return numberLike(cell?.[valueKey]) ?? 0;
  };
  return (
    <div className="heatmap-shell">
      <div className="vol-heatmap" style={{ "--cols": colLabels.length || 1 }}>
        <div className="hm-corner" />
        {colLabels.map((col) => <b className={hovered?.col === col ? "hm-active" : ""} key={col}>{col}</b>)}
        {rowLabels.map((row) => [
          <b className={`row-label ${hovered?.row === row ? "hm-active" : ""}`} key={`${row}-label`}>{row}</b>,
          ...colLabels.map((col) => {
            const v = valueAt(row, col);
            const diagonal = row === col;
            const alpha = Math.min(.86, Math.abs(v) / maxAbs * .78 + .08);
            const color = diagonal ? "linear-gradient(135deg,rgba(245,164,0,.2),rgba(245,164,0,.06))" : config.diverging && v < 0 ? `rgba(96,165,250,${alpha})` : v < 0 ? `rgba(239,68,68,${alpha})` : `rgba(245,164,0,${alpha})`;
            const dim = hovered && hovered.row !== row && hovered.col !== col;
            return <i className={`${diagonal ? "diag" : ""} ${dim ? "dim" : ""}`} key={`${row}-${col}`} onMouseEnter={() => setHovered({ row, col, v })} onMouseLeave={() => setHovered(null)} style={{ background: color, boxShadow: Math.abs(v) / maxAbs > .7 ? `0 0 18px ${v < 0 ? "rgba(96,165,250,.28)" : "rgba(245,164,0,.25)"}` : "none" }}>{diagonal ? "—" : Math.abs(v) > .3 || maxAbs > 10 ? formatValue(v) : ""}</i>;
          }),
        ])}
      </div>
      {hovered ? <div className="heatmap-hover"><strong>{hovered.row} × {hovered.col}</strong><b>{formatValue(hovered.v)}</b><span>|value| {(Math.abs(hovered.v) / maxAbs * 100).toFixed(0)}% of max</span></div> : null}
      <div className="heatmap-scale"><span>{config.diverging ? `-${formatValue(maxAbs)}` : "0"}</span><i className={config.diverging ? "diverging" : ""} /><span>{formatValue(maxAbs)}</span></div>
    </div>
  );
}

function TripleHeatmap({ data }) {
  const payload = data && typeof data === "object" ? data : {};
  return <div className="triple-vol-heat"><section><h4>Normal</h4><Heatmap data={payload.normal || payload.normal_correlation || []} config={{ diverging: true }} /></section><section><h4>Crisis</h4><Heatmap data={payload.crisis || payload.crisis_correlation || []} config={{ diverging: true }} /></section><section><h4>Delta</h4><Heatmap data={payload.delta || payload.difference || []} config={{ diverging: true }} /></section></div>;
}

function ProbabilityStack({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "probability_stack" }} response={{}} />;
  const sample = rows[0] || {};
  const xKey = Object.keys(sample).find((key) => /date|time|period|horizon|window/i.test(key)) || "date";
  const stateKeys = Object.keys(sample).filter((key) => key !== xKey && numberLike(sample[key]) != null).slice(0, 7);
  const last = rows.at(-1) || {};
  const dominant = stateKeys.reduce((best, key) => (numberLike(last[key]) ?? 0) > (numberLike(last[best]) ?? 0) ? key : best, stateKeys[0]);
  if (!stateKeys.length) return <VolChart data={rows} type="area" />;
  return (
    <div className="prob-stack">
      <VolChart data={rows} type="stackedArea" config={{ xKey, yKeys: stateKeys, fillOpacity: 0.34 }} />
      <div className="prob-current">
        <strong>{dominant ? titleize(dominant) : "Dominant State"}<span>{formatValue((numberLike(last[dominant]) ?? 0) * ((numberLike(last[dominant]) ?? 0) <= 1 ? 100 : 1))}%</span></strong>
        <div>
          {stateKeys.map((key, index) => {
            const raw = numberLike(last[key]) ?? 0;
            const pct = Math.max(0, Math.min(100, raw <= 1 ? raw * 100 : raw));
            return <i key={key} style={{ width: `${pct}%`, background: SERIES[index % SERIES.length] }} title={`${titleize(key)} ${pct.toFixed(1)}%`} />;
          })}
        </div>
      </div>
      <div className="prob-legend">
        {stateKeys.map((key, index) => <span key={key} style={{ "--c": SERIES[index % SERIES.length] }}><i />{titleize(key)}<b>{formatValue(numberLike(last[key]) ?? 0)}</b></span>)}
      </div>
    </div>
  );
}

function NetworkGraph({ data }) {
  const nodes = useMemo(() => data?.nodes || [], [data]);
  const edges = useMemo(() => data?.edges || [], [data]);
  const n = Math.max(nodes.length, 1);
  const basePositions = useMemo(() => Object.fromEntries(nodes.map((node, i) => {
    const id = node.id || node.name || node.asset || `node-${i}`;
    return [id, { x: 260 + Math.cos((i / n) * Math.PI * 2) * 190, y: 210 + Math.sin((i / n) * Math.PI * 2) * 150 }];
  })), [nodes, n]);
  const [positions, setPositions] = useState({});
  const [dragId, setDragId] = useState(null);
  const positioned = nodes.map((node, i) => {
    const id = node.id || node.name || node.asset || `node-${i}`;
    return { ...node, id, ...(positions[id] || basePositions[id]) };
  });
  const byId = new Map(positioned.map((node) => [node.id || node.name || node.asset, node]));
  function moveNode(event) {
    if (!dragId) return;
    const svg = event.currentTarget;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const cursor = point.matrixTransform(svg.getScreenCTM().inverse());
    setPositions((current) => ({ ...current, [dragId]: { x: cursor.x, y: cursor.y } }));
  }
  return (
    <svg className="vol-network" viewBox="0 0 540 420" onPointerMove={moveNode} onPointerUp={() => setDragId(null)} onPointerLeave={() => setDragId(null)}>
      <defs>
        <filter id="nodeGlow"><feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        <marker id="arrowPos" markerHeight="8" markerWidth="8" orient="auto" refX="8" refY="4"><path d="M0,0 L8,4 L0,8 Z" fill={TOKENS.accent} opacity=".75" /></marker>
        <marker id="arrowNeg" markerHeight="8" markerWidth="8" orient="auto" refX="8" refY="4"><path d="M0,0 L8,4 L0,8 Z" fill={TOKENS.blue} opacity=".75" /></marker>
      </defs>
      {edges.slice(0, 80).map((edge, index) => {
        const a = byId.get(edge.source || edge.from);
        const b = byId.get(edge.target || edge.to);
        if (!a || !b) return null;
        const v = numberLike(edge.value ?? edge.weight ?? edge.correlation) ?? 0;
        return <line key={index} markerEnd={v >= 0 ? "url(#arrowPos)" : "url(#arrowNeg)"} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={v >= 0 ? TOKENS.accent : TOKENS.blue} strokeOpacity={0.25 + Math.min(.45, Math.abs(v))} strokeWidth={1 + Math.abs(v) * 5} />;
      })}
      {positioned.map((node) => {
        const net = numberLike(node.net ?? node.value ?? node.size ?? node.centrality) ?? 0;
        const nodeColor = net < 0 ? TOKENS.blue : net > 0 ? TOKENS.accent : TOKENS.secondary;
        const radius = 11 + Math.min(22, Math.abs(net) * 16 || Math.abs(numberLike(node.size) ?? 0) * 8);
        return (
          <g className="network-node" key={node.id || node.name || node.asset} filter="url(#nodeGlow)" onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); setDragId(node.id); }}>
            <circle cx={node.x} cy={node.y} r={radius} fill={dragId === node.id ? nodeColor : TOKENS.panel} fillOpacity={dragId === node.id ? ".95" : ".72"} stroke={nodeColor} strokeWidth="2.4" />
            <circle cx={node.x} cy={node.y} r={Math.max(3, radius * .22)} fill={nodeColor} opacity=".82" />
            <text x={node.x} y={node.y + radius + 17} fill={TOKENS.secondary} fontSize="12" textAnchor="middle">{node.label || node.id || node.name || node.asset}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Waterfall({ data, valueKey = "value", nameKey = "name" }) {
  const rows = rowsFrom(data).map((row) => ({ name: row[nameKey] || row.component || row.asset || row.factor || row.name, value: numberLike(row[valueKey] ?? row.pnl ?? row.contribution ?? row.return) ?? 0 }));
  const chartRows = rows.reduce((acc, row) => {
    const start = acc.length ? acc[acc.length - 1].end : 0;
    const end = start + row.value;
    acc.push({ ...row, start, end, base: Math.min(start, end), height: Math.abs(row.value), positive: row.value >= 0 });
    return acc;
  }, []);
  const total = chartRows.at(-1)?.end ?? 0;
  if (chartRows.length) chartRows.push({ name: "TOTAL", value: total, start: 0, end: total, base: Math.min(0, total), height: Math.abs(total), total: true, positive: total >= 0 });
  if (!chartRows.length) return <VolEmpty section={{ source: "charts", dataKey: "waterfall" }} response={{}} />;
  const axis = { tick: { fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }, axisLine: false, tickLine: false };
  return (
    <ResponsiveContainer height={390} width="100%">
      <ComposedChart data={chartRows} margin={{ top: 20, right: 24, left: 8, bottom: 16 }}>
        <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
        <XAxis dataKey="name" {...axis} interval={0} tick={{ ...axis.tick, fontSize: 10 }} />
        <YAxis {...axis} tickFormatter={(value) => formatValue(value)} />
        <Tooltip content={<VolTooltip rows={chartRows} xKey="name" />} cursor={{ fill: "rgba(245,164,0,.05)" }} />
        <ReferenceLine y={0} stroke={TOKENS.muted} strokeDasharray="3 5" />
        <Bar dataKey="base" stackId="waterfall" fill="transparent" />
        <Bar dataKey="height" stackId="waterfall" radius={[5, 5, 0, 0]}>
          {chartRows.map((row, index) => <Cell key={index} fill={row.total ? TOKENS.accent : row.positive ? TOKENS.green : TOKENS.red} fillOpacity={row.total ? .95 : .78} />)}
          <LabelList dataKey="value" formatter={(value) => formatValue(value)} position="top" fill={TOKENS.secondary} fontSize={9} fontFamily="JetBrains Mono, monospace" />
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function VolGauge({ data }) {
  const row = rowsFrom(data)[0] || {};
  const value = Math.max(0, Math.min(100, numberLike(row.value ?? row.score ?? row.percentile) ?? 50));
  const angle = -180 + value * 1.8;
  const needle = { x: 150 + Math.cos((angle * Math.PI) / 180) * 104, y: 148 + Math.sin((angle * Math.PI) / 180) * 104 };
  const zones = [
    { start: 0, end: 20, label: "SERENE", color: TOKENS.teal },
    { start: 20, end: 40, label: "CALM", color: TOKENS.green },
    { start: 40, end: 60, label: "NERVOUS", color: TOKENS.blue },
    { start: 60, end: 80, label: "STRESSED", color: TOKENS.amber },
    { start: 80, end: 100, label: "CRISIS", color: TOKENS.red },
  ];
  const arc = (start, end, color) => {
    const a0 = (-180 + start * 1.8) * Math.PI / 180;
    const a1 = (-180 + end * 1.8) * Math.PI / 180;
    const p0 = { x: 150 + Math.cos(a0) * 112, y: 148 + Math.sin(a0) * 112 };
    const p1 = { x: 150 + Math.cos(a1) * 112, y: 148 + Math.sin(a1) * 112 };
    return <path d={`M ${p0.x} ${p0.y} A 112 112 0 0 1 ${p1.x} ${p1.y}`} fill="none" stroke={color} strokeLinecap="round" strokeWidth="18" />;
  };
  const zone = zones.find((item) => value <= item.end)?.label || "CRISIS";
  return (
    <div className="vol-gauge-pro" data-zone={zone.toLowerCase()}>
      <svg viewBox="0 0 300 188">
        <defs><filter id="gaugeGlow"><feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
        {zones.map((item) => <g key={item.label}>{arc(item.start + .8, item.end - .8, item.color)}</g>)}
        <line x1="150" y1="148" x2={needle.x} y2={needle.y} stroke={TOKENS.text} strokeWidth="3" strokeLinecap="round" filter="url(#gaugeGlow)" />
        <circle cx="150" cy="148" r="9" fill={TOKENS.accent} stroke="#050505" strokeWidth="4" />
        <text x="150" y="118" textAnchor="middle" fill={TOKENS.text} fontSize="34" fontWeight="900" fontFamily="JetBrains Mono, monospace">{formatValue(value)}%</text>
        <text x="150" y="137" textAnchor="middle" fill={TOKENS.accent} fontSize="10" fontWeight="900" letterSpacing="2">{zone}</text>
      </svg>
      <span>{row.label || row.name || "Current State"}</span>
      <div className="gauge-zone-strip">{zones.map((item) => <i className={zone === item.label ? "active" : ""} key={item.label} style={{ "--c": item.color }}>{item.label}</i>)}</div>
    </div>
  );
}

function RegimeDashboard({ data }) {
  const rows = rowsFrom(data).map((row, index) => {
    const v = Math.max(0, Math.min(1, numberLike(row.probability ?? row.value ?? row.weight) ?? 0));
    return { ...row, label: row.regime || row.state || row.name || `Regime ${index + 1}`, value: v };
  }).sort((a, b) => b.value - a.value);
  return (
    <div className="regime-dial-grid">
      {rows.map((row, index) => {
        const pct = row.value * 100;
        const color = index === 0 ? TOKENS.accent : pct > 35 ? TOKENS.amber : TOKENS.secondary;
        return (
          <div className={index === 0 ? "primary" : ""} key={row.label}>
            <svg viewBox="0 0 92 92">
              <circle cx="46" cy="46" r="35" fill="none" stroke="#211b10" strokeWidth="9" />
              <circle cx="46" cy="46" r="35" fill="none" stroke={color} strokeLinecap="round" strokeWidth="9" strokeDasharray={`${pct * 2.2} 220`} transform="rotate(-90 46 46)" />
              <text x="46" y="50" textAnchor="middle" fill={TOKENS.text} fontSize="17" fontWeight="900" fontFamily="JetBrains Mono, monospace">{pct.toFixed(0)}%</text>
            </svg>
            <b>{row.label}</b>
            <span>{index === 0 ? "dominant state" : "posterior probability"}</span>
          </div>
        );
      })}
    </div>
  );
}

function ForecastBands({ data }) {
  const rows = rowsFrom(data).map((row, index) => ({
    date: row.date || row.horizon || row.t || index + 1,
    actual: numberLike(row.actual ?? row.realized),
    forecast: numberLike(row.forecast ?? row.p50 ?? row.median),
    p05: numberLike(row.p05 ?? row.lower_95 ?? row.lower),
    p25: numberLike(row.p25 ?? row.lower_50),
    p75: numberLike(row.p75 ?? row.upper_50),
    p95: numberLike(row.p95 ?? row.upper_95 ?? row.upper),
  })).map((row) => ({
    ...row,
    band90Base: row.p05,
    band90: row.p95 != null && row.p05 != null ? row.p95 - row.p05 : null,
    band50Base: row.p25,
    band50: row.p75 != null && row.p25 != null ? row.p75 - row.p25 : null,
  }));
  if (!rows.length) return <VolEmpty section={{ source: "charts", dataKey: "forecast_bands" }} response={{}} />;
  return (
    <div className="forecast-fan">
      <ResponsiveContainer height={420} width="100%">
        <ComposedChart data={rows} margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="date" tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }} axisLine={false} tickLine={false} />
          <Tooltip content={<VolTooltip rows={rows} xKey="date" />} cursor={{ stroke: "rgba(245,164,0,.25)", strokeDasharray: "4 3" }} />
          <Area dataKey="band90Base" stackId="band90" stroke="transparent" fill="transparent" />
          <Area dataKey="band90" stackId="band90" stroke="transparent" fill="rgba(245,164,0,.08)" />
          <Area dataKey="band50Base" stackId="band50" stroke="transparent" fill="transparent" />
          <Area dataKey="band50" stackId="band50" stroke="transparent" fill="rgba(245,164,0,.18)" />
          <Line dataKey="actual" stroke={TOKENS.text} strokeWidth={1.7} dot={false} type="monotone" />
          <Line dataKey="forecast" stroke={TOKENS.accent} strokeWidth={2.2} dot={false} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="fan-legend"><span><i />90% interval</span><span><i />50% interval</span><b>Forecast median</b></div>
    </div>
  );
}

function SurfaceGrid({ data }) {
  return <Heatmap data={rowsFrom(data).map((r) => ({ row: r.horizon_days, col: r.moneyness_quantile, value: r.synthetic_vol }))} />;
}

function FrequencyBands({ data }) {
  const rows = Object.entries(data || {}).map(([band, value]) => ({ band, connectedness: value?.connectedness }));
  return <VolChart data={rows} type="bar" config={{ xKey: "band", yKeys: ["connectedness"] }} />;
}

function DualPosterior({ data }) {
  const payload = data && typeof data === "object" ? data : {};
  return <div className="dual-posterior"><section><h4>Smoothed</h4><ProbabilityStack data={payload.smoothed || []} /></section><section><h4>Filtered</h4><ProbabilityStack data={payload.filtered || []} /></section></div>;
}

function ComposedBars({ data }) {
  const rows = rowsFrom(data);
  return (
    <ResponsiveContainer height={380} width="100%">
      <ComposedChart data={rows} margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
        <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
        <XAxis dataKey="rank" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
        <YAxis tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
        <Tooltip content={<VolTooltip />} />
        <Bar dataKey="eigenvalue" fill={TOKENS.accent} radius={[4, 4, 0, 0]} />
        <Line dataKey="cumulative_variance" stroke={TOKENS.green} strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function VolTable({ data, searchQuery = "" }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const cols = useMemo(() => [...new Set(rows.slice(0, 100).flatMap((row) => Object.keys(row)))].slice(0, 14), [rows]);
  const [sort, setSort] = useState({ key: cols[0], dir: "asc" });
  const stats = useMemo(() => Object.fromEntries(cols.map((col) => {
    const nums = rows.map((row) => numberLike(row[col])).filter((value) => value != null);
    return [col, { max: Math.max(1e-9, ...nums.map((value) => Math.abs(value))) }];
  })), [cols, rows]);
  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = numberLike(a[sort.key]) ?? String(a[sort.key] ?? "");
      const bv = numberLike(b[sort.key]) ?? String(b[sort.key] ?? "");
      const result = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? result : -result;
    });
    return copy;
  }, [rows, sort]);
  const q = searchQuery.trim().toLowerCase();
  return (
    <div className="vol-table-wrap">
      <table className="vol-table">
        <thead><tr>{cols.map((col) => <th className={sort.key === col ? "sorted" : ""} key={col} onClick={() => setSort((current) => ({ key: col, dir: current.key === col && current.dir === "asc" ? "desc" : "asc" }))}>{titleize(col)} <em>{sort.key === col ? sort.dir === "asc" ? "↑" : "↓" : "↕"}</em></th>)}</tr></thead>
        <tbody>{sorted.slice(0, 300).map((row, i) => <tr key={i}>{cols.map((col, ci) => {
          const n = numberLike(row[col]);
          const alpha = n == null || ci === 0 ? 0 : Math.min(0.42, Math.abs(n) / stats[col].max * 0.34 + 0.04);
          const bg = n == null ? undefined : n < 0 ? `rgba(239,68,68,${alpha})` : `rgba(34,197,94,${alpha * 0.75})`;
          const text = formatValue(row[col]);
          const hit = q && String(row[col] ?? "").toLowerCase().includes(q);
          const barWidth = n == null || ci === 0 ? 0 : Math.min(100, Math.abs(n) / stats[col].max * 100);
          return (
            <td className={`${n != null ? n < 0 ? "neg num" : "pos num" : ""} ${hit ? "cell-hit" : ""}`} key={col} style={{ background: bg }}>
              <span className="vol-cell-inner">{text}</span>
              {barWidth ? <span className="vol-microbar" style={{ width: `${barWidth}%`, background: n < 0 ? TOKENS.red : TOKENS.green }} /> : null}
            </td>
          );
        })}</tr>)}</tbody>
      </table>
      <div className="vol-table-footer">{sorted.length} rows · {cols.length} visible columns{sorted.length > 300 ? " · showing first 300" : ""}</div>
    </div>
  );
}

function ExportModal({ feature, form, sections, response, onClose }) {
  const jsonText = JSON.stringify(workspacePayload(feature, form, sections, response), null, 2);
  const tsvText = exportAllTsv(sections, response);
  const [copied, setCopied] = useState("");
  async function copy(text, label) {
    await navigator.clipboard?.writeText(text);
    setCopied(label);
    window.setTimeout(() => setCopied(""), 1400);
  }
  return (
    <motion.div className="export-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.section className="export-modal" initial={{ y: 28, opacity: 0, scale: .98 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 28, opacity: 0, scale: .98 }} onClick={(event) => event.stopPropagation()}>
        <header><div><p>EXPORT SURFACE</p><h2>F{feature.id} · {feature.title}</h2></div><button onClick={onClose} type="button"><X size={17} /></button></header>
        <div className="export-grid">
          <button onClick={() => downloadText(`atlas-vol-f${feature.id}-workspace.json`, jsonText, "application/json")} type="button"><Download size={18} /><b>Workspace JSON</b><span>Inputs, output manifest and response payload.</span></button>
          <button onClick={() => downloadText(`atlas-vol-f${feature.id}-outputs.tsv`, tsvText || "No tabular outputs", "text/tab-separated-values")} type="button"><Download size={18} /><b>Excel TSV Book</b><span>All resolved output tables in one paste-ready file.</span></button>
          <button onClick={() => copy(jsonText, "json")} type="button"><Copy size={18} /><b>Copy JSON</b><span>{copied === "json" ? "Copied." : "Copy workspace config to clipboard."}</span></button>
          <button onClick={() => copy(tsvText || "No tabular outputs", "tsv")} type="button"><Copy size={18} /><b>Copy TSV</b><span>{copied === "tsv" ? "Copied." : "Copy all table outputs for Excel."}</span></button>
        </div>
        <textarea readOnly value={tsvText || jsonText} />
      </motion.section>
    </motion.div>
  );
}

export function VolatilityV2Workbench({ featureId, sections, response = null, onRun }) {
  const feature = useMemo(() => getVolatilityV2Feature(featureId), [featureId]);
  const execute = onRun || ((payload) => runVolatilityV2Feature(featureId, payload));
  const outputSections = useMemo(() => sections || VOLATILITY_OUTPUT_BOOKS[feature.id] || [], [sections, feature.id]);
  const storageKey = `atlas-vol-v2:f${feature.id}:workspace`;
  const [form, setForm] = useState(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = JSON.parse(window.localStorage.getItem(storageKey) || "null");
        if (saved?.form) return saved.form;
      } catch {}
    }
    return Object.fromEntries(Object.entries(feature.defaults || {}).map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : String(v)]));
  });
  const [data, setData] = useState(response);
  const [error, setError] = useState("");
  const [inputOpen, setInputOpen] = useState(!response);
  const [activeId, setActiveId] = useState(outputSections[0]?.id);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [density, setDensity] = useState("comfortable");
  const [cinemaId, setCinemaId] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [query, setQuery] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [compareData, setCompareData] = useState(null);
  const [draggingSection, setDraggingSection] = useState(null);
  const [sectionOrder, setSectionOrder] = useState(() => outputSections.map((section) => section.id));
  const toastId = useRef(0);
  useEffect(() => {
    setSectionOrder((current) => {
      const available = new Set(outputSections.map((section) => section.id));
      const kept = current.filter((id) => available.has(id));
      const added = outputSections.map((section) => section.id).filter((id) => !kept.includes(id));
      return [...kept, ...added];
    });
  }, [outputSections]);
  const orderedSections = useMemo(() => {
    const byId = new Map(outputSections.map((section) => [section.id, section]));
    return sectionOrder.map((id) => byId.get(id)).filter(Boolean);
  }, [outputSections, sectionOrder]);
  const matches = useMemo(() => orderedSections.filter((section) => `${section.title} ${section.chartType} ${section.dataKey}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8), [orderedSections, query]);
  const dataHitCount = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !data) return 0;
    return orderedSections.reduce((count, section) => count + rowsFrom(pickData(data, section)).reduce((inner, row) => inner + Object.values(row).filter((value) => String(value ?? "").toLowerCase().includes(q)).length, 0), 0);
  }, [query, data, orderedSections]);
  const pushToast = (message, type = "info") => {
    const id = ++toastId.current;
    setToasts((current) => [...current.slice(-3), { id, message, type }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4200);
  };
  const jumpTo = (id) => {
    setActiveId(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  useEffect(() => {
    setData(response);
  }, [response]);
  useEffect(() => {
    setActiveId(outputSections[0]?.id);
  }, [outputSections]);
  useEffect(() => {
    document.documentElement.style.setProperty("--vol-row-h", density === "compact" ? "28px" : density === "spacious" ? "52px" : "40px");
    document.documentElement.style.setProperty("--vol-table-fs", density === "compact" ? "10px" : density === "spacious" ? "14px" : "12px");
  }, [density]);
  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({ form, activeId, density, sectionOrder, ts: Date.now() }));
      if (activeId) window.history.replaceState(null, "", `#f${feature.id}-${activeId}`);
    } catch {}
  }, [storageKey, form, activeId, density, feature.id, sectionOrder]);
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") {
        setCinemaId(null);
        setInputOpen(false);
      }
      if (event.key.toLowerCase() === "f" && activeId && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        event.preventDefault();
        setCinemaId((current) => current === activeId ? null : activeId);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeId]);
  async function run() {
    setRunning(true);
    setProgress(0);
    setError("");
    try {
      const result = await execute(form);
      setData(result);
      setInputOpen(false);
      setProgress(1);
      pushToast(`Run complete — ${outputSections.length} outputs ready`, "success");
    } catch (err) {
      setError(err?.message || "Volatility run failed");
      pushToast(err?.message || "Volatility run failed", "error");
    } finally {
      setRunning(false);
      window.setTimeout(() => setProgress(0), 800);
    }
  }
  async function runComparison() {
    setRunning(true);
    setProgress(0);
    try {
      setCompareData(await execute(form));
      setSplitMode(true);
      setProgress(1);
      pushToast("Comparison lane refreshed", "success");
    } catch (err) {
      pushToast(err?.message || "Comparison run failed", "error");
    } finally {
      setRunning(false);
      window.setTimeout(() => setProgress(0), 800);
    }
  }
  return (
    <main className={`vol-v2-page ${cinemaId ? "cinema-active" : ""}`}>
      <style jsx global>{volStyles}</style>
      <header className="vol-topbar"><div><strong>VOL</strong><span>F{feature.id} · {feature.title}</span></div><WorkspaceSearch query={query} setQuery={setQuery} matches={matches} onJump={jumpTo} hitCount={dataHitCount} /><DensityToggle value={density} onChange={setDensity} /><button className={splitMode ? "active" : ""} onClick={() => setSplitMode((value) => !value)} type="button">Split</button><button onClick={runComparison} type="button">Compare</button><button onClick={() => setExportOpen(true)} type="button"><Download size={16} /> Export</button><button onClick={() => setInputOpen(true)} type="button"><SlidersHorizontal size={16} /> Input Contract</button><button className="run" disabled={running} onClick={run} type="button"><Play size={16} /> {running ? "Running" : "Run"}</button></header>
      <RunProgressBar running={running} progress={progress} />
      <section className="vol-hero"><p>ATLAS // VOLATILITY INTELLIGENCE</p><h1>{feature.title}</h1><span>{feature.description}</span></section>
      {error ? <div className="vol-status"><AlertTriangle size={17} />{error}</div> : null}
      <StickySummaryBar sections={orderedSections} activeId={activeId} response={data} />
      <AnimatePresence>{inputOpen ? <motion.div className="vol-curtain" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setInputOpen(false)}><motion.section initial={{ y: -42, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -42, opacity: 0 }} onClick={(e) => e.stopPropagation()}><header><div><p>Input Contract</p><h2>{feature.shortTitle}</h2></div><button onClick={() => setInputOpen(false)} type="button"><X size={17} /></button></header><VolInputForm feature={feature} form={form} onChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))} /><footer><button onClick={() => setInputOpen(false)} type="button">Close</button><button className="run" disabled={running} onClick={run} type="button"><Play size={16} /> Run volatility stack</button></footer></motion.section></motion.div> : null}</AnimatePresence>
      <section className="vol-workspace">
        <OutputDock activeId={activeId} sections={orderedSections} onJump={jumpTo} onReorder={(from, to) => setSectionOrder((current) => moveById(current, from, to))} />
        <div className={`vol-stack ${splitMode ? "split-stack" : ""}`}>
          <div className="split-lane"><b className="split-label">Primary</b>{orderedSections.map((section, index) => <VolOutputCard active={activeId === section.id} cinemaId={cinemaId} draggable key={section.id} onActive={setActiveId} onCinema={setCinemaId} onDragStart={setDraggingSection} onDrop={(target) => setSectionOrder((current) => moveById(current, draggingSection, target))} response={data} searchQuery={query} section={section} staggerIndex={index} />)}</div>
          {splitMode ? <div className="split-lane compare-lane"><b className="split-label">Comparison</b>{orderedSections.map((section, index) => <VolOutputCard active={false} cinemaId={cinemaId} compare key={`compare-${section.id}`} onActive={() => {}} onCinema={setCinemaId} response={compareData || data} searchQuery={query} section={section} staggerIndex={index} />)}</div> : null}
        </div>
        <OutputMinimap activeId={activeId} sections={orderedSections} onJump={jumpTo} />
      </section>
      <AnimatePresence>{exportOpen ? <ExportModal feature={feature} form={form} sections={orderedSections} response={data} onClose={() => setExportOpen(false)} /> : null}</AnimatePresence>
      <ToastRack toasts={toasts} onDismiss={(id) => setToasts((current) => current.filter((toast) => toast.id !== id))} />
    </main>
  );
}

const volStyles = `
  :root{--vol-row-h:40px;--vol-table-fs:12px;--vol-void:#000;--vol-page:${TOKENS.page};--vol-panel:${TOKENS.panel};--vol-screen:${TOKENS.screen};--vol-raised:${TOKENS.raised};--vol-input:${TOKENS.input};--vol-border:${TOKENS.border};--vol-border-subtle:${TOKENS.borderSubtle};--vol-accent:${TOKENS.accent};--vol-text:${TOKENS.text};--vol-secondary:${TOKENS.secondary};--vol-muted:${TOKENS.muted};--vol-red:${TOKENS.red};--vol-green:${TOKENS.green};--vol-teal:${TOKENS.teal};--vol-ease-out:cubic-bezier(.16,1,.3,1)}
  .vol-v2-page{min-height:100dvh;background:#050505;color:${TOKENS.text};font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:0 28px 120px}
  .vol-topbar{position:sticky;top:0;z-index:40;height:54px;margin:0 -28px;padding:0 28px;display:flex;align-items:center;gap:12px;background:rgba(5,5,5,.9);border-bottom:1px solid ${TOKENS.borderSubtle};backdrop-filter:blur(18px)}
  .vol-topbar div{display:flex;align-items:center;gap:12px}.vol-topbar strong{color:${TOKENS.accent};font-weight:950;letter-spacing:.18em}.vol-topbar span{color:${TOKENS.secondary};font-size:12px;letter-spacing:.08em}.vol-topbar button{height:34px;border:1px solid ${TOKENS.border};background:${TOKENS.raised};color:${TOKENS.secondary};border-radius:8px;padding:0 12px;display:inline-flex;align-items:center;gap:8px;font-weight:800;cursor:pointer}.vol-topbar button:first-of-type{margin-left:auto}.vol-topbar .run{background:${TOKENS.accent};color:#050505;border-color:${TOKENS.accent}}
  .vol-run-progress{position:sticky;top:54px;z-index:38;height:3px;margin:0 -28px;background:${TOKENS.borderSubtle}}.vol-run-progress i{height:100%;display:block;background:linear-gradient(90deg,${TOKENS.accent},${TOKENS.green});transition:width .28s var(--vol-ease-out)}.vol-run-progress b{position:absolute;right:28px;top:7px;color:${TOKENS.accent};font:900 9px JetBrains Mono,monospace;letter-spacing:.12em}
  .workspace-search{position:relative;margin-left:auto;width:min(320px,24vw);height:34px;border:1px solid ${TOKENS.border};background:${TOKENS.input};border-radius:9px;display:flex;align-items:center;gap:8px;padding:0 10px;color:${TOKENS.muted}}.workspace-search input{min-width:0;flex:1;border:0;background:transparent;color:${TOKENS.text};outline:0;font-size:12px}.workspace-search>div{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:80;background:#080808;border:1px solid ${TOKENS.border};border-radius:10px;box-shadow:0 22px 80px rgba(0,0,0,.62);overflow:hidden}.workspace-search button{width:100%;height:38px!important;margin:0!important;border:0!important;border-bottom:1px solid ${TOKENS.borderSubtle}!important;border-radius:0!important;background:transparent!important;justify-content:space-between;color:${TOKENS.text}!important}.workspace-search button:hover{background:${TOKENS.accentSoft}!important}.workspace-search p{margin:0;padding:12px;color:${TOKENS.muted};font-size:12px}
  .density-toggle{height:34px;display:flex;border:1px solid ${TOKENS.border};border-radius:9px;overflow:hidden;background:${TOKENS.input}}.density-toggle button{width:30px!important;height:32px!important;margin:0!important;border:0!important;border-right:1px solid ${TOKENS.borderSubtle}!important;border-radius:0!important;background:transparent!important;color:${TOKENS.muted}!important;padding:0!important}.density-toggle button.active{background:${TOKENS.accent}!important;color:#050505!important}
  .vol-hero{padding:52px 0 34px}.vol-hero p{color:${TOKENS.accent};font-size:11px;font-weight:900;letter-spacing:.22em}.vol-hero h1{margin:10px 0 8px;font-size:clamp(34px,5vw,70px);line-height:.95;letter-spacing:-.04em}.vol-hero span{color:${TOKENS.secondary};font-size:18px;max-width:820px;display:block;line-height:1.6}
  .vol-status{height:44px;border:1px solid rgba(239,68,68,.28);background:rgba(239,68,68,.08);color:${TOKENS.red};border-radius:10px;display:flex;align-items:center;gap:10px;padding:0 14px;margin-bottom:18px}
  .sticky-summary{position:sticky;top:62px;z-index:30;margin:0 0 16px;padding:9px 12px;border:1px solid ${TOKENS.border};border-radius:12px;background:rgba(5,5,5,.78);backdrop-filter:blur(14px);display:flex;gap:14px;align-items:center;overflow:auto}.sticky-summary span{color:${TOKENS.accent};font:900 10px JetBrains Mono,monospace;letter-spacing:.14em;text-transform:uppercase}.sticky-summary b{color:${TOKENS.secondary};font:800 11px JetBrains Mono,monospace;white-space:nowrap}.sticky-summary em{color:${TOKENS.text};font-style:normal;margin-left:4px}
  .vol-workspace{display:grid;grid-template-columns:96px 1fr 64px;gap:20px;align-items:start}.vol-stack{display:grid;gap:16px}
  .vol-dock{position:sticky;top:74px;min-height:420px;padding:10px;border:1px solid ${TOKENS.border};background:rgba(9,9,9,.76);border-radius:24px;display:flex;flex-direction:column;align-items:center;gap:8px;box-shadow:0 24px 80px rgba(0,0,0,.4)}.vol-dock strong{writing-mode:vertical-rl;color:${TOKENS.accent};font-size:10px;letter-spacing:.22em;margin:8px 0}.vol-dock button{width:54px;height:48px;border:1px solid ${TOKENS.borderSubtle};border-radius:16px;background:${TOKENS.input};color:${TOKENS.muted};display:grid;place-items:center;position:relative;cursor:pointer;transition:transform .16s ease,background .16s ease,color .16s ease}.vol-dock button:hover,.vol-dock button.active{transform:translateX(10px) scale(1.12);background:${TOKENS.accent};color:#050505;border-color:${TOKENS.accent}}.vol-dock button span{position:absolute;top:4px;left:6px;font:800 9px JetBrains Mono,monospace}.vol-dock button em{position:absolute;left:68px;white-space:nowrap;opacity:0;pointer-events:none;background:${TOKENS.raised};border:1px solid ${TOKENS.border};border-radius:8px;padding:7px 10px;color:${TOKENS.text};font-style:normal;font-size:12px}.vol-dock button:hover em{opacity:1}
  .vol-minimap{position:sticky;top:74px;display:flex;flex-direction:column;gap:8px;align-items:center}.vol-minimap span{color:${TOKENS.accent};font:900 9px JetBrains Mono,monospace;letter-spacing:.2em}.vol-minimap button{width:46px;height:32px;border:1px solid ${TOKENS.border};border-radius:8px;background:#080808;position:relative;padding:4px;cursor:pointer;transition:transform .15s ease,border-color .15s ease}.vol-minimap button.active,.vol-minimap button:hover{border-color:${TOKENS.accent};transform:translateX(-5px)}.vol-minimap i{display:block;width:100%;height:100%;border-radius:5px;background:linear-gradient(135deg,rgba(245,164,0,.25),rgba(255,255,255,.03))}.vol-minimap em{position:absolute;right:3px;bottom:2px;color:${TOKENS.muted};font:800 8px JetBrains Mono,monospace;font-style:normal}
  .vol-output-card{position:relative;border:1px solid ${TOKENS.border};border-radius:18px;background:linear-gradient(180deg,rgba(20,17,10,.96),rgba(8,8,8,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 22px 80px rgba(0,0,0,.28);overflow:hidden;transition:opacity .25s ease,box-shadow .25s ease,border-color .25s ease}.vol-output-card:before{content:"";position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(245,164,0,.6),transparent)}.vol-output-card.active{border-color:rgba(245,164,0,.7);box-shadow:0 0 0 1px rgba(245,164,0,.14),0 0 60px rgba(245,164,0,.08),0 26px 90px rgba(0,0,0,.38)}.vol-output-card.primary{border-left:3px solid ${TOKENS.accent}}.vol-output-card.fullscreen{position:fixed;z-index:100;inset:18px;border-radius:20px}.vol-output-card.cinema-focused{z-index:20;box-shadow:0 0 0 1px rgba(245,164,0,.42),0 40px 140px rgba(0,0,0,.72)}.vol-output-card.cinema-dimmed{pointer-events:none;user-select:none}.cinema-active .vol-dock,.cinema-active .vol-minimap{opacity:.28}
  .vol-output-card>header{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid ${TOKENS.borderSubtle}}.vol-output-card h2{margin:0;font-size:16px;letter-spacing:-.01em}.vol-output-card p{margin:0 0 4px;color:${TOKENS.muted};font:800 10px JetBrains Mono,monospace;letter-spacing:.12em;text-transform:uppercase}.vol-card-actions{display:flex;gap:7px}.vol-card-actions button{width:32px;height:32px;border:1px solid ${TOKENS.border};border-radius:8px;background:${TOKENS.input};color:${TOKENS.secondary};display:grid;place-items:center;cursor:pointer}.vol-card-actions button.active{color:#050505;background:${TOKENS.accent};border-color:${TOKENS.accent}}
  .header-spark{width:120px;height:30px;margin-left:auto;margin-right:12px}.header-spark polyline{fill:none;stroke:${TOKENS.accent};stroke-width:2}
  .vol-screen{position:relative;min-height:420px;padding:18px;background:radial-gradient(circle at 50% 0,rgba(245,164,0,.08),transparent 40%),linear-gradient(180deg,#101113,#070707);cursor:crosshair}.vol-screen:after{content:"";pointer-events:none;position:absolute;inset:0;background:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.8),transparent)}
  .vol-drawing{position:absolute;inset:0;z-index:5;touch-action:none}.vol-tooltip{background:#111;border:1px solid ${TOKENS.border};border-radius:8px;padding:10px 12px;box-shadow:0 18px 50px rgba(0,0,0,.6);color:${TOKENS.secondary};font-size:12px;min-width:190px}.vol-tooltip b{display:block;color:${TOKENS.text};margin-bottom:8px}.vol-tooltip span{display:flex;gap:8px;align-items:center;justify-content:space-between}.vol-tooltip i{width:9px;height:9px;border-radius:50%}.vol-tooltip strong{margin-left:auto;color:${TOKENS.text};font-family:JetBrains Mono,monospace}
  .metric-deck{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.vol-metric{min-height:132px;border:1px solid ${TOKENS.border};background:rgba(5,5,5,.5);border-radius:12px;padding:14px;display:grid;align-content:space-between}.vol-metric span{color:${TOKENS.secondary};font-size:11px;text-transform:uppercase;letter-spacing:.12em}.vol-metric strong{font:900 30px JetBrains Mono,monospace}.vol-metric svg{width:100%;height:36px}.vol-metric polyline{fill:none;stroke:${TOKENS.accent};stroke-width:2}
  .garch-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px}.garch-board div{border:1px solid ${TOKENS.borderSubtle};border-radius:10px;padding:10px;background:#080808;display:grid;grid-template-columns:1fr auto;gap:4px 10px}.garch-board .winner{border-color:${TOKENS.green};box-shadow:0 0 0 1px rgba(34,197,94,.12)}.garch-board b{color:${TOKENS.text}}.garch-board span,.garch-board em{color:${TOKENS.secondary};font-style:normal;font-size:11px}.garch-board strong{color:${TOKENS.green};font-size:10px}
  .vol-table-wrap{max-height:520px;overflow:auto;border:1px solid ${TOKENS.borderSubtle};border-radius:10px}.vol-table{width:100%;border-collapse:collapse;font-size:var(--vol-table-fs)}.vol-table th{position:sticky;top:0;background:#111;color:${TOKENS.accent};text-align:left;padding:10px;border-bottom:1px solid ${TOKENS.border};font-size:calc(var(--vol-table-fs) - 2px);letter-spacing:.12em;text-transform:uppercase;cursor:pointer;user-select:none}.vol-table th.sorted{color:${TOKENS.text};background:${TOKENS.raised}}.vol-table th em{font-style:normal;color:${TOKENS.muted};margin-left:5px}.vol-table td{height:var(--vol-row-h);padding:0 10px;border-bottom:1px solid ${TOKENS.borderSubtle};color:${TOKENS.secondary};font-family:JetBrains Mono,monospace}.vol-table td.pos{color:${TOKENS.green}}.vol-table td.neg{color:${TOKENS.red}}.vol-table tr:hover td{background:rgba(245,164,0,.06)!important;color:${TOKENS.text}}.vol-table-footer{padding:7px 10px;background:#090909;border-top:1px solid ${TOKENS.borderSubtle};color:${TOKENS.muted};font:800 10px JetBrains Mono,monospace}
  .vol-heatmap{display:grid;grid-template-columns:120px repeat(var(--cols),minmax(72px,1fr));gap:2px;overflow:auto}.vol-heatmap b{min-height:34px;display:grid;place-items:center;color:${TOKENS.secondary};font-size:10px;text-transform:uppercase}.vol-heatmap .row-label{justify-content:start;padding-left:8px}.vol-heatmap i{min-height:42px;border-radius:5px;display:grid;place-items:center;color:#fff;font:800 11px JetBrains Mono,monospace;font-style:normal}
  .triple-vol-heat,.dual-posterior{display:grid;grid-template-columns:repeat(3,minmax(280px,1fr));gap:10px;overflow:auto}.dual-posterior{grid-template-columns:repeat(2,minmax(300px,1fr))}.triple-vol-heat h4,.dual-posterior h4{margin:0 0 8px;color:${TOKENS.accent};font-size:11px;letter-spacing:.14em;text-transform:uppercase}
  .vol-network{width:100%;height:430px}.vol-gauge{height:360px;display:grid;place-items:center;align-content:center;gap:10px}.vol-gauge>div{width:220px;height:110px;border-radius:220px 220px 0 0;position:relative;overflow:hidden}.vol-gauge>div:after{content:"";position:absolute;inset:18px 18px 0;border-radius:200px 200px 0 0;background:#090909}.vol-gauge i{position:absolute;left:50%;bottom:0;width:2px;height:98px;background:${TOKENS.text};transform-origin:bottom center;z-index:2}.vol-gauge strong{font:900 42px JetBrains Mono,monospace}.vol-gauge span{color:${TOKENS.secondary}}
  .regime-bars{display:grid;gap:12px}.regime-bars div{display:grid;grid-template-columns:190px 80px 1fr;gap:12px;align-items:center}.regime-bars span{color:${TOKENS.secondary}}.regime-bars b{font-family:JetBrains Mono,monospace}.regime-bars i{height:12px;background:#171717;border-radius:999px;overflow:hidden}.regime-bars em{height:100%;display:block;background:${TOKENS.accent};border-radius:999px}
  .vcal-wrap,.ridge-wrap,.cone-wrap,.sig-wrap,.cmm-wrap{display:grid;gap:12px}.vcal-legend{display:flex;align-items:center;gap:8px;color:${TOKENS.muted};font:900 10px JetBrains Mono,monospace}.vcal-legend i{height:8px;width:160px;border-radius:999px;background:linear-gradient(90deg,rgba(20,184,166,.55),rgba(245,164,0,.75),rgba(239,68,68,.9))}.vcal-days{display:grid;grid-template-columns:repeat(5,16px);gap:2px;color:${TOKENS.muted};font:900 9px JetBrains Mono,monospace}.vcal-days span{text-align:center}.vcal-grid{display:grid;grid-template-columns:repeat(var(--cols),16px);grid-auto-rows:16px;gap:2px;overflow:auto}.vcal-grid b{border-radius:3px;transition:transform 80ms ease,filter 80ms ease}.vcal-grid b:hover{transform:scale(1.6);filter:brightness(1.3);z-index:2}.ridge-wrap{overflow:auto}.ridge-svg{width:100%;min-width:620px;height:auto;display:block}.cone-interp{display:flex;flex-wrap:wrap;gap:6px}.cone-interp span{height:24px;padding:0 8px;border:1px solid ${TOKENS.border};border-radius:6px;display:inline-flex;align-items:center;gap:6px;color:${TOKENS.secondary};font:900 10px JetBrains Mono,monospace}.cone-interp b{color:${TOKENS.accent}}.sig-interp{font:900 11px JetBrains Mono,monospace;padding:9px 12px;border-left:3px solid ${TOKENS.accent};background:rgba(255,255,255,.025);border-radius:0 6px 6px 0;color:${TOKENS.accent};letter-spacing:.06em}.cmm-controls{display:flex;align-items:center;gap:8px}.cmm-controls button{width:28px;height:28px;border:1px solid ${TOKENS.border};background:${TOKENS.input};color:${TOKENS.secondary};border-radius:6px}.cmm-controls input{flex:1;accent-color:${TOKENS.accent}}.cmm-controls span{color:${TOKENS.secondary};font:900 10px JetBrains Mono,monospace}.cmm-matrix{display:grid;grid-template-columns:80px repeat(calc(var(--cols) - 1),1fr);gap:3px;animation:matrixFade .25s ease both}.cmm-matrix b{min-height:28px;display:grid;place-items:center;color:${TOKENS.secondary};font:900 9px JetBrains Mono,monospace}.cmm-row-label{justify-content:start!important;padding-left:4px}.cmm-matrix em{min-height:40px;border-radius:5px;display:grid;place-items:center;color:rgba(255,255,255,.9);font:800 10px JetBrains Mono,monospace;font-style:normal}@keyframes matrixFade{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:scale(1)}}
  .toast-rack{position:fixed;right:24px;bottom:24px;z-index:500;display:flex;flex-direction:column-reverse;gap:8px;max-width:390px}.toast{min-height:42px;padding:0 10px 0 14px;border:1px solid ${TOKENS.border};border-radius:10px;background:rgba(8,8,8,.94);backdrop-filter:blur(16px);display:flex;align-items:center;gap:10px;color:${TOKENS.text};font-size:12px;animation:toastIn .22s var(--vol-ease-out) both}.toast-success{border-color:rgba(34,197,94,.4)}.toast-warning{border-color:rgba(245,164,0,.45)}.toast-error{border-color:rgba(239,68,68,.45)}.toast-dot{width:7px;height:7px;border-radius:50%;background:${TOKENS.muted}}.toast-success .toast-dot{background:${TOKENS.green}}.toast-warning .toast-dot{background:${TOKENS.accent}}.toast-error .toast-dot{background:${TOKENS.red}}.toast-msg{flex:1}.toast button{border:0;background:transparent;color:${TOKENS.muted};font-size:17px;cursor:pointer}@keyframes toastIn{from{opacity:0;transform:translateX(24px) scale(.97)}to{opacity:1;transform:none}}
  .vol-empty{min-height:210px;display:grid;place-items:center;text-align:center;color:${TOKENS.muted};gap:10px;border:1px dashed ${TOKENS.border};border-radius:12px}.vol-empty small{display:block;max-width:720px;line-height:1.7}
  .vol-curtain{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.72);backdrop-filter:blur(16px);padding:68px 34px;overflow:auto}.vol-curtain section{max-width:1280px;margin:0 auto;border:1px solid ${TOKENS.border};border-radius:20px;background:linear-gradient(180deg,#101010,#070707);box-shadow:0 40px 120px rgba(0,0,0,.66)}.vol-curtain header,.vol-curtain footer{height:62px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid ${TOKENS.borderSubtle}}.vol-curtain footer{border-top:1px solid ${TOKENS.borderSubtle};border-bottom:0}.vol-curtain h2{margin:0}.vol-curtain p{margin:0;color:${TOKENS.accent};font-size:10px;letter-spacing:.18em;text-transform:uppercase}.vol-curtain button,.vol-curtain .run{height:36px;border:1px solid ${TOKENS.border};background:${TOKENS.input};color:${TOKENS.secondary};border-radius:8px;padding:0 12px;display:inline-flex;align-items:center;gap:8px;font-weight:800;cursor:pointer}.vol-curtain .run{background:${TOKENS.accent};color:#050505;border-color:${TOKENS.accent}}
  .vol-input-grid{padding:18px 20px;display:grid;gap:0}.vol-input-group{display:grid;grid-template-columns:180px 1fr;gap:18px;border-top:1px solid ${TOKENS.borderSubtle};padding:16px 0}.vol-input-group:first-child{border-top:0}.vol-input-group h3{margin:0;color:${TOKENS.muted};font-size:10px;letter-spacing:.18em;text-transform:uppercase}.vol-input-group>div{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}.vol-field{display:grid;gap:7px}.vol-field.vol-wide{grid-column:1/-1}.vol-field span{display:flex;justify-content:space-between;color:${TOKENS.secondary};font-size:12px;font-weight:800}.vol-field span b{color:${TOKENS.accent};font-family:JetBrains Mono,monospace}.vol-field input,.vol-field textarea{width:100%;background:${TOKENS.input};border:1px solid ${TOKENS.border};border-radius:8px;color:${TOKENS.text};height:38px;padding:0 11px}.vol-field textarea{min-height:84px;padding:10px;resize:vertical}.vol-field small{color:${TOKENS.muted};font-size:11px}.vol-chip-row,.vol-presets{display:flex;flex-wrap:wrap;gap:6px}.vol-chip-row button,.vol-presets button{height:32px;border:1px solid ${TOKENS.border};background:${TOKENS.input};color:${TOKENS.secondary};border-radius:7px;padding:0 10px;font-size:11px;font-weight:800;cursor:pointer}.vol-chip-row button.active{background:${TOKENS.accent};border-color:${TOKENS.accent};color:#050505}
  .bbg-symbol-box{position:relative;min-height:40px;border:1px solid ${TOKENS.border};background:${TOKENS.input};border-radius:8px;display:flex;align-items:flex-start;gap:8px;padding:8px;color:${TOKENS.secondary}}.bbg-symbol-tokens{display:flex;flex-wrap:wrap;gap:5px;flex:1}.bbg-symbol-tokens button{height:24px;border:1px solid rgba(245,164,0,.35);background:${TOKENS.accentSoft};color:${TOKENS.accent};border-radius:5px;padding:0 6px;display:inline-flex;align-items:center;gap:4px;font:800 11px JetBrains Mono,monospace}.bbg-symbol-tokens input{height:24px;min-width:100px;flex:1;border:0;background:transparent;color:${TOKENS.text};outline:0;padding:0}.bbg-symbol-menu{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:8;background:#080808;border:1px solid ${TOKENS.border};border-radius:10px;box-shadow:0 24px 80px rgba(0,0,0,.62);overflow:hidden}.bbg-symbol-menu button{width:100%;height:42px;display:grid;grid-template-columns:90px 1fr auto;align-items:center;border:0;border-bottom:1px solid ${TOKENS.borderSubtle};background:transparent;color:${TOKENS.secondary};padding:0 12px;text-align:left}.bbg-symbol-menu button:hover{background:${TOKENS.accentSoft}}.bbg-symbol-menu strong{color:${TOKENS.text};font-family:JetBrains Mono,monospace}.bbg-symbol-menu em{font-style:normal;color:${TOKENS.muted};font-size:11px}
  .vol-topbar button.active{background:${TOKENS.accentSoft};color:${TOKENS.accent};border-color:rgba(245,164,0,.45)}
  .vol-dock button.dragging{opacity:.45;transform:translateX(12px) scale(.96)}
  .split-stack{grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:start}.split-lane{display:grid;gap:16px;min-width:0}.split-label{position:sticky;top:60px;z-index:4;height:30px;border:1px solid ${TOKENS.border};border-radius:999px;background:rgba(5,5,5,.82);backdrop-filter:blur(14px);display:inline-flex;align-items:center;width:max-content;padding:0 12px;color:${TOKENS.accent};font:900 10px JetBrains Mono,monospace;letter-spacing:.16em;text-transform:uppercase}.compare-card{border-color:rgba(20,184,166,.28)}.compare-card:before{background:linear-gradient(90deg,transparent,rgba(20,184,166,.55),transparent)}
  .vol-table td.cell-hit{outline:1px solid ${TOKENS.accent};box-shadow:inset 0 0 0 999px rgba(245,164,0,.13);color:${TOKENS.text}!important}
  .network-node{cursor:grab}.network-node:active{cursor:grabbing}.vol-network line{transition:stroke-opacity .15s ease,stroke-width .15s ease}.vol-network text{pointer-events:none;font-family:JetBrains Mono,monospace;font-weight:800}
  .export-overlay{position:fixed;inset:0;z-index:180;background:rgba(0,0,0,.72);backdrop-filter:blur(18px);display:grid;place-items:center;padding:24px}.export-modal{width:min(920px,calc(100vw - 48px));max-height:calc(100dvh - 48px);overflow:auto;border:1px solid ${TOKENS.border};border-radius:18px;background:linear-gradient(180deg,#11100c,#060606);box-shadow:0 40px 140px rgba(0,0,0,.76)}.export-modal header{height:62px;padding:0 18px;border-bottom:1px solid ${TOKENS.borderSubtle};display:flex;align-items:center;justify-content:space-between}.export-modal header p{margin:0;color:${TOKENS.accent};font:900 10px JetBrains Mono,monospace;letter-spacing:.18em}.export-modal header h2{margin:3px 0 0;font-size:18px}.export-modal header button{width:34px;height:34px;border:1px solid ${TOKENS.border};border-radius:8px;background:${TOKENS.input};color:${TOKENS.secondary}}.export-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:16px}.export-grid button{min-height:116px;text-align:left;border:1px solid ${TOKENS.border};border-radius:13px;background:${TOKENS.input};color:${TOKENS.secondary};padding:14px;display:grid;gap:7px;align-content:start;cursor:pointer}.export-grid button:hover{border-color:rgba(245,164,0,.5);background:${TOKENS.accentSoft}}.export-grid b{color:${TOKENS.text};font-size:13px}.export-grid span{font-size:11px;line-height:1.45}.export-modal textarea{display:block;width:calc(100% - 32px);height:190px;margin:0 16px 16px;border:1px solid ${TOKENS.border};border-radius:12px;background:#050505;color:${TOKENS.secondary};padding:12px;font:11px JetBrains Mono,monospace;resize:vertical}
  .vol-tooltip em.up{color:${TOKENS.green};font-style:normal}.vol-tooltip em.dn{color:${TOKENS.red};font-style:normal}
  .asc-wrap{display:grid;gap:6px}.asc-legend{display:flex;flex-wrap:wrap;gap:7px 12px;padding:8px 2px 0;border-top:1px solid ${TOKENS.borderSubtle}}.asc-legend span{display:inline-flex;align-items:center;gap:7px;color:${TOKENS.secondary};font:800 10px JetBrains Mono,monospace;text-transform:uppercase;letter-spacing:.08em}.asc-legend i{width:16px;height:2px;border-radius:999px;background:var(--c)}.asc-legend b{color:${TOKENS.text};font-weight:900}
  .metric-deck{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}.vol-metric{min-height:164px;background:radial-gradient(circle at 85% 0,rgba(245,164,0,.08),transparent 38%),rgba(5,5,5,.5);display:grid;grid-template-columns:1fr 72px;gap:6px 10px;align-items:start;align-content:initial;transition:border-color .15s ease,transform .15s ease}.vol-metric:hover{transform:translateY(-2px);border-color:rgba(245,164,0,.38)}.vol-metric.up{box-shadow:inset 3px 0 0 rgba(34,197,94,.62)}.vol-metric.dn{box-shadow:inset 3px 0 0 rgba(239,68,68,.62)}.vol-metric span{grid-column:1/-1;font-size:10px;letter-spacing:.14em;font-weight:900}.vol-metric strong{font-size:28px;letter-spacing:-.04em}.vol-metric strong em{font-size:11px;color:${TOKENS.muted};font-style:normal;margin-left:5px}.vol-metric small{justify-self:start;font:900 10px JetBrains Mono,monospace}.vol-metric small.pos{color:${TOKENS.green}}.vol-metric small.neg{color:${TOKENS.red}}.vol-metric .pct-arc{grid-row:2/4;grid-column:2;width:72px;height:44px}
  .garch-board{grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:9px}.garch-board div{position:relative;border-radius:12px;padding:12px;background:linear-gradient(135deg,#080808,#11100c);display:grid;grid-template-columns:34px 1fr auto;gap:5px 10px;align-items:center;overflow:hidden}.garch-board div:before{content:"";position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(245,164,0,.45),transparent)}.garch-board .winner{box-shadow:0 0 0 1px rgba(34,197,94,.12),0 0 34px rgba(34,197,94,.08)}.garch-board strong{grid-row:1/4;color:${TOKENS.accent};font:900 18px JetBrains Mono,monospace}.garch-board b{font-size:13px}.garch-board span{font-size:11px;text-transform:uppercase;letter-spacing:.1em}.garch-board em{font:800 10px JetBrains Mono,monospace}.garch-board i{justify-self:end;border:1px solid rgba(34,197,94,.35);background:rgba(34,197,94,.1);color:${TOKENS.green};border-radius:999px;padding:2px 7px;font-style:normal;font:900 9px JetBrains Mono,monospace}
  .heatmap-shell{display:grid;gap:9px}.vol-heatmap b.hm-active{color:${TOKENS.accent}}.vol-heatmap i{transition:opacity .12s ease,transform .12s ease,filter .12s ease}.vol-heatmap i:hover{transform:scale(1.04);filter:brightness(1.18);z-index:1}.vol-heatmap i.dim{opacity:.22}.vol-heatmap i.diag{color:${TOKENS.accent};font-size:13px;border:1px solid rgba(245,164,0,.18)}.heatmap-hover{display:flex;align-items:center;gap:10px;min-height:30px;padding:0 10px;border-left:3px solid ${TOKENS.accent};background:rgba(245,164,0,.06);border-radius:0 8px 8px 0;color:${TOKENS.secondary};font:800 11px JetBrains Mono,monospace}.heatmap-hover strong{color:${TOKENS.text}}.heatmap-hover b{color:${TOKENS.accent}}.heatmap-scale{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;color:${TOKENS.muted};font:900 9px JetBrains Mono,monospace}.heatmap-scale i{height:8px;border-radius:999px;background:linear-gradient(90deg,rgba(245,164,0,.05),rgba(245,164,0,.85))}.heatmap-scale i.diverging{background:linear-gradient(90deg,rgba(96,165,250,.8),rgba(255,255,255,.08),rgba(239,68,68,.8))}
  .vol-gauge-pro{min-height:360px;display:grid;place-items:center;align-content:center;gap:6px}.vol-gauge-pro svg{width:min(420px,100%);filter:drop-shadow(0 22px 48px rgba(0,0,0,.42))}.vol-gauge-pro[data-zone="extreme"] svg{filter:drop-shadow(0 0 28px rgba(239,68,68,.24)) drop-shadow(0 22px 48px rgba(0,0,0,.42))}.vol-gauge-pro span{color:${TOKENS.secondary};font:900 11px JetBrains Mono,monospace;letter-spacing:.14em;text-transform:uppercase}
  .regime-dial-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.regime-dial-grid div{min-height:170px;border:1px solid ${TOKENS.borderSubtle};border-radius:14px;background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(0,0,0,.1));display:grid;place-items:center;padding:12px;text-align:center}.regime-dial-grid div.primary{border-color:rgba(245,164,0,.4);box-shadow:0 0 38px rgba(245,164,0,.08)}.regime-dial-grid svg{width:98px;height:98px}.regime-dial-grid b{color:${TOKENS.text};font-size:13px}.regime-dial-grid span{color:${TOKENS.muted};font:800 10px JetBrains Mono,monospace;text-transform:uppercase;letter-spacing:.1em}
  .forecast-fan{display:grid;gap:8px}.fan-legend{display:flex;gap:12px;align-items:center;color:${TOKENS.secondary};font:900 10px JetBrains Mono,monospace;text-transform:uppercase;letter-spacing:.08em}.fan-legend span{display:inline-flex;align-items:center;gap:6px}.fan-legend i{width:20px;height:8px;border-radius:999px;background:rgba(245,164,0,.1)}.fan-legend span:nth-child(2) i{background:rgba(245,164,0,.2)}.fan-legend b{color:${TOKENS.accent}}
  .garch-shell{display:grid;gap:10px}.garch-mcs-strip{min-height:34px;border:1px solid rgba(34,197,94,.25);border-radius:10px;background:rgba(34,197,94,.055);display:flex;align-items:center;gap:8px;padding:6px 10px;overflow:auto}.garch-mcs-strip span{color:${TOKENS.green};font:900 9px JetBrains Mono,monospace;letter-spacing:.16em;white-space:nowrap}.garch-mcs-strip b{border:1px solid rgba(34,197,94,.25);border-radius:999px;padding:4px 8px;color:${TOKENS.text};font:900 10px JetBrains Mono,monospace;white-space:nowrap}
  .prob-stack{display:grid;gap:10px}.prob-current{border:1px solid ${TOKENS.borderSubtle};border-radius:10px;background:rgba(255,255,255,.025);padding:10px;display:grid;gap:8px}.prob-current strong{display:flex;justify-content:space-between;align-items:center;color:${TOKENS.text};font-size:12px;text-transform:uppercase;letter-spacing:.12em}.prob-current strong span{color:${TOKENS.accent};font:900 13px JetBrains Mono,monospace}.prob-current div{height:12px;border-radius:999px;overflow:hidden;background:#050505;display:flex}.prob-current i{height:100%;display:block;min-width:2px}.prob-legend{display:flex;flex-wrap:wrap;gap:7px 12px}.prob-legend span{display:inline-flex;align-items:center;gap:7px;color:${TOKENS.secondary};font:800 10px JetBrains Mono,monospace;text-transform:uppercase;letter-spacing:.08em}.prob-legend i{width:10px;height:10px;border-radius:2px;background:var(--c)}.prob-legend b{color:${TOKENS.text}}
  .vol-table th:first-child,.vol-table td:first-child{position:sticky;left:0;z-index:2;background:#090909}.vol-table th:first-child{z-index:4;background:#111}.vol-table td{position:relative}.vol-cell-inner{position:relative;z-index:1}.vol-microbar{position:absolute;right:8px;bottom:4px;height:2px;border-radius:999px;opacity:.64;max-width:calc(100% - 16px)}
  .vol-gauge-pro[data-zone="crisis"] svg{filter:drop-shadow(0 0 30px rgba(239,68,68,.28)) drop-shadow(0 22px 48px rgba(0,0,0,.42))}.gauge-zone-strip{display:flex;flex-wrap:wrap;gap:5px;justify-content:center}.gauge-zone-strip i{border:1px solid var(--c);border-radius:999px;padding:4px 7px;color:var(--c);font:900 9px JetBrains Mono,monospace;font-style:normal;letter-spacing:.1em;opacity:.5;background:rgba(255,255,255,.02)}.gauge-zone-strip i.active{opacity:1;box-shadow:0 0 18px rgba(245,164,0,.18)}
  @media(max-width:900px){.vol-workspace{grid-template-columns:1fr}.vol-minimap{display:none}.workspace-search{display:none}.vol-dock{position:fixed;left:12px;right:12px;bottom:12px;top:auto;z-index:60;min-height:0;flex-direction:row;overflow:auto}.vol-dock strong{writing-mode:initial}.vol-dock button:hover,.vol-dock button.active{transform:translateY(-8px) scale(1.08)}.vol-input-group{grid-template-columns:1fr}.triple-vol-heat,.dual-posterior,.split-stack{grid-template-columns:1fr}.export-grid{grid-template-columns:1fr 1fr}}
`;
