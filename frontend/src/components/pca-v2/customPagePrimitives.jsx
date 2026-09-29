"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
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
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Boxes, ChevronDown, CircleDot, Copy, Download, Network, Play, Search, Settings2 } from "lucide-react";
import { getPcaV2Feature, PCA_V2_FEATURES } from "./registry";

const TOKENS = {
  page: "#050505",
  panel: "#0A0A0A",
  screen: "#101113",
  raised: "#15130E",
  input: "#121212",
  border: "#312610",
  borderSoft: "#20190E",
  grid: "#2E2A20",
  accent: "#F5A400",
  accentSoft: "rgba(245,164,0,.14)",
  text: "#F7F1E6",
  secondary: "#AAA194",
  muted: "#6F6658",
  green: "#22C55E",
  red: "#EF4444",
  blue: "#60A5FA",
  teal: "#14B8A6",
  purple: "#8B5CF6",
};

const SERIES = ["#F5A400", "#22C55E", "#60A5FA", "#EF4444", "#14B8A6", "#8B5CF6", "#E8D18A", "#EC4899"];

function section(id, title, source, dataKey, chartType, options = {}) {
  return { id, title, source, dataKey, chartType, rank: options.rank || "supporting", fallbackKeys: options.fallbackKeys || [], config: options.config || {} };
}

export const PCA_OUTPUT_BOOKS = {
  "01": [
    section("spectrum", "Eigenvalue Spectrum vs Marchenko-Pastur", "charts", "eigenvalue_spectrum_mp", "scree", { rank: "primary" }),
    section("scree-cutoff", "Scree Multi-Cutoff", "charts", "scree_multi_cutoff", "composed"),
    section("raw-cov", "Raw Covariance Heatmap", "charts", "raw_covariance_heatmap", "heatmap"),
    section("cleaned-cov", "RMT-Cleaned Covariance Heatmap", "charts", "cleaned_covariance_heatmap", "heatmap"),
    section("blended-cov", "Blended Covariance Heatmap", "charts", "blended_covariance_heatmap", "heatmap"),
    section("diff-cov", "Covariance Difference Heatmap", "charts", "covariance_difference_heatmap", "heatmap"),
    section("condition-panel", "Condition Number Panel", "charts", "condition_number_panel", "metricDeck"),
    section("signal-table", "Signal vs Noise Eigenvalue Table", "tables", "signal_vs_noise_eigenvalue_table", "table"),
    section("lw-diagnostic", "Ledoit-Wolf Shrinkage Diagnostic", "tables", "ledoit_wolf_shrinkage_diagnostic", "table"),
  ],
  "02": [
    section("loading-heatmap", "Loading Matrix Heatmap", "charts", "loading_matrix_heatmap", "heatmap", { rank: "primary" }),
    section("factor-returns", "Factor Return Time Series", "charts", "factor_return_time_series", "line"),
    section("explained-variance", "Explained Variance Bar", "charts", "explained_variance_bar", "bar"),
    section("rotated-loadings", "Rotated Loading Matrix", "charts", "rotated_loading_matrix", "heatmap"),
    section("cluster-map", "Hierarchical PCA Cluster Map", "charts", "hierarchical_pca_cluster_map", "clusterMap"),
    section("hpca-returns", "HPCA Cross-Factor Returns", "charts", "hpca_cross_factor_returns", "line"),
    section("hoyer", "Hoyer Sparsity by PC", "charts", "hoyer_sparsity_by_pc", "bar"),
    section("top-loadings", "Top-N Loading Table", "tables", "top_n_loading_table", "table"),
    section("factor-stats", "Factor Return Statistics", "tables", "factor_return_statistics", "table"),
    section("interpretation", "PC Interpretation Panel", "tables", "pc_interpretation_panel", "table"),
    section("asset-r2", "Asset R2 Table", "tables", "asset_r2_table", "table"),
  ],
  "03": [
    section("risk-stack", "Risk Attribution Stacked Bar", "charts", "risk_attribution_stacked_bar", "bar", { rank: "primary" }),
    section("var-waterfall", "Factor VaR Waterfall", "charts", "factor_var_waterfall", "waterfall"),
    section("cvar-waterfall", "CVaR Decomposition", "charts", "cvar_decomposition", "waterfall"),
    section("systematic-pie", "Systematic vs Idiosyncratic", "charts", "systematic_vs_idiosyncratic_pie", "pie"),
    section("rolling-risk", "Rolling Risk Decomposition", "charts", "rolling_risk_decomposition", "area"),
    section("benchmark-corr", "Benchmark Correlation by PC", "charts", "benchmark_correlation_by_pc", "bar"),
    section("tracking-error", "Tracking Error by Factor", "charts", "tracking_error_by_factor", "bar"),
    section("marginal-risk", "Marginal Risk Contribution", "tables", "marginal_risk_contribution", "table"),
    section("active-risk", "Active Risk Attribution", "tables", "active_risk_attribution_table", "table"),
    section("var-cvar", "VaR / CVaR Table", "tables", "var_cvar_table", "table"),
  ],
  "04": [
    section("zscore-dist", "Residual Z-Score Distribution", "charts", "residual_zscore_distribution", "bar", { rank: "primary" }),
    section("spread-ts", "Residual Spread Time Series", "charts", "residual_spread_timeseries", "line"),
    section("half-life", "Half-Life vs Z-Score", "charts", "half_life_vs_zscore", "scatter"),
    section("sector-balance", "Sector Signal Balance", "charts", "sector_signal_balance", "bar"),
    section("decay", "Signal Decay Curve", "charts", "signal_decay_curve", "line"),
    section("ou-backtest", "Residual OU Backtest Equity", "charts", "residual_ou_backtest_equity", "area"),
    section("ranked-signals", "Ranked Signal Table", "tables", "ranked_signal_table", "table"),
    section("ou-params", "OU Parameter Table", "tables", "ou_parameter_table", "table"),
    section("mle-params", "MLE Parameter Table", "tables", "mle_parameter_table", "table"),
    section("trade-list", "Trade List", "tables", "trade_list", "table"),
    section("backtest-stats", "Residual OU Backtest Stats", "tables", "residual_ou_backtest_stats", "table"),
  ],
  "05": [
    section("pc1-share", "Rolling PC1 Share", "charts", "rolling_pc1_share", "line", { rank: "primary" }),
    section("eigen-drift", "Eigenvector Drift", "charts", "eigenvector_drift", "line"),
    section("cusum", "CUSUM Structural Break", "charts", "cusum_structural_break", "line"),
    section("eigen-ratio", "Eigenvalue Ratio Time Series", "charts", "eigenvalue_ratio_time_series", "line"),
    section("loading-evo", "PC1 Loading Evolution Heatmap", "charts", "pc1_loading_evolution_heatmap", "heatmap"),
    section("principal-angle", "Principal Angle Time Series", "charts", "principal_angle_time_series", "line"),
    section("tensor-core", "Multi-Frequency Regime Tensor", "charts", "multi_frequency_regime_tensor", "tensor"),
    section("tensor-factor", "Tensor Factor Singular Values", "charts", "tensor_factor_singular_values", "bar"),
    section("current-readout", "Current Regime Readout", "tables", "current_regime_readout", "table"),
    section("breakpoints", "Bai-Perron Breakpoint Table", "tables", "bai_perron_breakpoint_table", "table"),
    section("pc1-percentile", "PC1 Percentile Rank Table", "tables", "pc1_percentile_rank_table", "table"),
  ],
  "06": [
    section("frontier", "Efficient Frontier", "charts", "efficient_frontier", "frontier", { rank: "primary" }),
    section("weights-chart", "Optimal Weights", "charts", "optimal_weights", "bar"),
    section("pc-rp", "PC Factor Risk Parity", "charts", "pc_factor_risk_parity", "bar"),
    section("pc-rp-weights", "PC Factor Risk Parity Weights", "charts", "pc_factor_risk_parity_weights", "bar"),
    section("robust-frontier", "Robust vs Standard Frontier", "charts", "robust_vs_standard_frontier", "frontier"),
    section("k-sensitivity", "K Sensitivity OOS Sharpe", "charts", "k_sensitivity_oos_sharpe", "line"),
    section("weights-table", "Optimal Portfolio Weights", "tables", "optimal_portfolio_weights", "table"),
    section("risk-contrib", "Risk Contribution Table", "tables", "risk_contribution_table", "table"),
    section("shadow-prices", "Constraint Shadow Prices", "tables", "constraint_shadow_prices", "table"),
    section("black-litterman", "Black-Litterman Posterior", "tables", "black_litterman_posterior", "table"),
  ],
  "07": [
    section("bootstrap-scree", "Bootstrap Scree Plot", "charts", "bootstrap_scree_plot", "scree", { rank: "primary" }),
    section("cosine", "Eigenvector Cosine Distribution", "charts", "eigenvector_cosine_distribution", "bar"),
    section("subsampling", "Subsampling Stability Heatmap", "charts", "subsampling_stability_heatmap", "heatmap"),
    section("bai-ng", "Bai-Ng Criteria Sweep", "charts", "bai_ng_criteria_sweep", "line"),
    section("principal-angle", "Principal Angle Analysis", "charts", "principal_angle_analysis", "line"),
    section("scorecard", "Factor Genuineness Scorecard", "tables", "factor_genuineness_scorecard", "table"),
    section("bands", "Bootstrap Eigenvalue Bands", "tables", "bootstrap_eigenvalue_bands", "table"),
    section("bai-ng-table", "Bai-Ng IC Table", "tables", "bai_ng_ic_table", "table"),
    section("angle-table", "Principal Angle Table", "tables", "principal_angle_table", "table"),
  ],
  "08": [
    section("rolling-group", "Rolling Group Residual Correlation", "charts", "rolling_group_residual_corr_time_series", "line", { rank: "primary" }),
    section("resid-matrix", "Residual Correlation Matrix", "charts", "residual_correlation_matrix", "heatmap"),
    section("lambda-k", "Residual Lambda1 by K", "charts", "residual_lambda1_by_k", "line"),
    section("under-spec", "Under-Specification Diagnostic", "charts", "under_specification_diagnostic", "bar"),
    section("by-group", "Residual Correlation by Group", "charts", "residual_correlation_by_group", "bar"),
    section("crisis-dates", "Crisis Overlay Dates", "charts", "crisis_overlay_dates", "timeline"),
    section("tensor", "Residual Frequency Tensor", "charts", "residual_frequency_tensor", "tensor"),
    section("contagion", "Contagion Spike Detector", "tables", "contagion_spike_detector", "table"),
    section("regime-alert", "Residual Correlation Regime Alert", "tables", "residual_correlation_regime_alert", "table"),
    section("tensor-summary", "Residual Tensor Summary", "tables", "residual_tensor_summary", "table"),
  ],
  "09": [
    section("pc-heatmap", "PC Scenario P&L Heatmap", "charts", "pc_scenario_pnl_heatmap", "heatmap", { rank: "primary" }),
    section("sensitivity", "Scenario Sensitivity Table Chart", "charts", "scenario_sensitivity_table_chart", "bar"),
    section("max-loss", "Maximum Loss Scenario Identifier", "charts", "maximum_loss_scenario_identifier", "metricDeck"),
    section("analog", "Mahalanobis Historical Analog", "charts", "mahalanobis_historical_analog", "table"),
    section("worst-days", "Historical Worst-Day Scenarios", "charts", "historical_worst_day_scenarios_chart", "bar"),
    section("joint", "Joint Scenario P&L Chart", "charts", "joint_scenario_pnl_chart", "waterfall"),
    section("scenario-table", "Scenario Sensitivity Table", "tables", "scenario_sensitivity_table", "table"),
    section("pnl-waterfall", "Position-Level P&L Waterfall", "tables", "position_level_pnl_waterfall", "table"),
    section("stress-var", "Stress VaR / CVaR", "tables", "stress_var_cvar", "table"),
    section("pdf-export", "PDF Export Payload", "tables", "pdf_export", "table"),
  ],
  "10": [
    section("block-cov", "Asset-Class Specific Covariance Estimators", "charts", "asset_class_covariance_estimators", "heatmap", { rank: "primary", fallbackKeys: ["block_covariance_heatmap", "block_correlation_heatmap"] }),
    section("dcc-block", "DCC Cross-Block Conditional Correlation", "charts", "dcc_cross_block_conditional_correlation", "line"),
    section("rolling-block", "Rolling Block Correlation Monitor", "charts", "rolling_block_correlation_monitor", "line"),
    section("casci", "Cross-Asset Systemic Concentration Index", "charts", "casci_index", "area"),
    section("stress-overlay", "Stress-Date Block Correlation Overlay", "charts", "stress_date_block_correlation_overlay", "heatmap"),
    section("fx-hedge", "FX Minimum Variance Hedge Ratios", "tables", "fx_minimum_variance_hedge_ratios", "table"),
    section("crypto-filter", "Crypto Volume Filter", "tables", "crypto_volume_filter", "table"),
    section("calendar-audit", "Calendar Alignment Audit", "tables", "calendar_alignment_audit", "table"),
    section("hourly-inventory", "Hourly Parquet Inventory", "tables", "hourly_parquet_inventory", "table"),
    section("coverage", "Cross-Asset Coverage", "tables", "coverage", "table"),
  ],
  "11": [
    section("surface", "Illiquidity Surface Heatmap", "charts", "illiquidity_surface_heatmap", "heatmap", { rank: "primary" }),
    section("latent", "Latent Liquidity Factor", "charts", "latent_liquidity_factor", "area"),
    section("beta-ranking", "Liquidity Beta Ranking", "charts", "liquidity_beta_ranking", "bar"),
    section("sizing", "Position Sizing Liquidity Overlay", "charts", "position_sizing_liquidity_overlay", "bar"),
    section("lavar", "LaVaR Decomposition", "charts", "lavar_decomposition", "metricDeck"),
    section("scorecard", "Liquidity Risk Scorecard", "tables", "liquidity_risk_scorecard", "table"),
    section("liquidation", "Liquidation Cost Table", "tables", "liquidation_cost_table", "table"),
    section("unwind", "Quant Unwind Monitor", "tables", "quant_unwind_monitor", "table"),
    section("metadata", "Illiquidity Measure Metadata", "tables", "illiquidity_measure_metadata", "table"),
  ],
};

function titleize(value) {
  return String(value ?? "").replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function numberLike(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const n = Number(value.replace(/[$,%x]/g, "").trim());
  return Number.isFinite(n) ? n : null;
}

function formatValue(value) {
  const n = numberLike(value);
  if (n == null) return String(value ?? "-");
  const abs = Math.abs(n);
  if (abs > 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (abs > 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (abs < 1 && abs !== 0) return n.toFixed(4);
  return n.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function previewRows(sectionDef) {
  const key = `${sectionDef.id}:${sectionDef.dataKey}`;
  const seed = Array.from(key).reduce((s, c) => s + c.charCodeAt(0), 0);
  if (sectionDef.chartType === "heatmap") {
    const labels = ["PC1", "PC2", "PC3", "PC4", "PC5", "IDIO"];
    return labels.flatMap((row, i) => labels.map((col, j) => ({ row, col, value: i === j ? 1 : Math.sin((i + 1) * (j + 2) + seed) * 0.72 })));
  }
  if (sectionDef.chartType === "table") {
    return Array.from({ length: 8 }, (_, i) => ({
      rank: i + 1,
      item: `${sectionDef.dataKey}_${i + 1}`,
      component: `PC${(i % 5) + 1}`,
      value: Math.sin(seed + i) * 0.42 + i / 20,
      status: i % 3 === 0 ? "watch" : "ok",
    }));
  }
  if (sectionDef.chartType === "metricDeck") {
    return ["Signal PCs", "Lambda Max", "Condition", "Coverage"].map((name, i) => ({ name, value: Math.abs(Math.sin(seed + i) * 100), unit: i === 0 ? "count" : "score" }));
  }
  if (sectionDef.chartType === "waterfall") {
    return ["PC1", "PC2", "PC3", "PC4", "IDIO"].map((name, i) => ({ name, value: Math.sin(seed / 10 + i) * 0.08 }));
  }
  if (sectionDef.chartType === "pie") {
    return [{ name: "Systematic", value: 72 }, { name: "Idiosyncratic", value: 28 }];
  }
  if (sectionDef.chartType === "frontier" || sectionDef.chartType === "scatter") {
    return Array.from({ length: 28 }, (_, i) => ({ risk: 6 + i * 0.45, return: 4 + Math.sqrt(i + 1) * 1.45, value: Math.sin(seed + i) }));
  }
  return Array.from({ length: 72 }, (_, i) => ({
    date: `T${i + 1}`,
    value: 0.2 + Math.sin(i / 6 + seed) * 0.08 + i * 0.002,
    PC1: 0.18 + Math.sin(i / 7 + seed) * 0.09,
    PC2: 0.12 + Math.cos(i / 8 + seed) * 0.06,
    PC3: 0.08 + Math.sin(i / 5 + seed) * 0.04,
  }));
}

const axis = {
  tick: { fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, IBM Plex Mono, Consolas, monospace" },
  axisLine: false,
  tickLine: false,
};

function PcaTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="pca-tooltip">
      <b>{label}</b>
      {payload.map((entry) => (
        <span key={entry.dataKey || entry.name}>
          {entry.name}: <em style={{ color: entry.color }}>{formatValue(entry.value)}</em>
        </span>
      ))}
    </div>
  );
}

function ChartFrame({ children }) {
  return <div className="pca-chart-frame">{children}</div>;
}

function StandardChart({ section: sectionDef }) {
  const rows = previewRows(sectionDef);
  if (sectionDef.chartType === "area") {
    return (
      <ChartFrame>
        <ResponsiveContainer width="100%" height={330}>
          <AreaChart data={rows}>
            <defs><linearGradient id={`pca-grad-${sectionDef.id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={TOKENS.accent} stopOpacity={0.35} /><stop offset="95%" stopColor={TOKENS.accent} stopOpacity={0.02} /></linearGradient></defs>
            <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false} />
            <XAxis dataKey="date" {...axis} />
            <YAxis {...axis} />
            <Tooltip content={<PcaTooltip />} />
            <Area type="monotone" dataKey="value" stroke={TOKENS.accent} fill={`url(#pca-grad-${sectionDef.id})`} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
    );
  }
  if (sectionDef.chartType === "bar" || sectionDef.chartType === "scree") {
    const barRows = rows.slice(0, 24).map((r, i) => ({ ...r, rank: r.rank || i + 1, eigenvalue: Math.max(0.02, 2.7 / (i + 1) + Math.sin(i) * 0.05), mp: 0.42 }));
    return (
      <ChartFrame>
        <ResponsiveContainer width="100%" height={330}>
          <ComposedChart data={barRows}>
            <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false} />
            <XAxis dataKey="rank" {...axis} />
            <YAxis {...axis} />
            <Tooltip content={<PcaTooltip />} />
            <Bar dataKey={sectionDef.chartType === "scree" ? "eigenvalue" : "value"} fill={TOKENS.accent} radius={[4, 4, 0, 0]} />
            {sectionDef.chartType === "scree" ? <Line dataKey="mp" dot={false} stroke={TOKENS.red} strokeDasharray="5 5" /> : null}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
    );
  }
  if (sectionDef.chartType === "scatter" || sectionDef.chartType === "frontier") {
    return (
      <ChartFrame>
        <ResponsiveContainer width="100%" height={330}>
          <ScatterChart>
            <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} />
            <XAxis type="number" dataKey="risk" name="Risk" {...axis} />
            <YAxis type="number" dataKey="return" name="Return" {...axis} />
            <Tooltip content={<PcaTooltip />} />
            <Scatter data={rows} fill={TOKENS.accent} />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartFrame>
    );
  }
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height={330}>
        <LineChart data={rows}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false} />
          <XAxis dataKey="date" {...axis} />
          <YAxis {...axis} />
          <Tooltip content={<PcaTooltip />} />
          <Line dataKey="PC1" dot={false} stroke={SERIES[0]} strokeWidth={2} />
          <Line dataKey="PC2" dot={false} stroke={SERIES[1]} strokeWidth={2} />
          <Line dataKey="PC3" dot={false} stroke={SERIES[2]} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function Heatmap({ section: sectionDef }) {
  const rows = previewRows(sectionDef);
  const rowLabels = [...new Set(rows.map((r) => r.row || r.ticker || r.component || "Row"))];
  const colLabels = [...new Set(rows.map((r) => r.col || r.component || "Value"))];
  const map = new Map(rows.map((r) => [`${r.row || r.ticker || r.component || "Row"}:${r.col || r.component || "Value"}`, numberLike(r.value) ?? 0]));
  return (
    <ChartFrame>
      <div className="pca-heatmap" style={{ gridTemplateColumns: `90px repeat(${colLabels.length}, minmax(48px, 1fr))` }}>
        <span />
        {colLabels.map((col) => <b key={col}>{col}</b>)}
        {rowLabels.map((row) => (
          <>
            <strong key={`${row}-label`}>{row}</strong>
            {colLabels.map((col) => {
              const v = map.get(`${row}:${col}`) ?? 0;
              const pos = v >= 0;
              const alpha = Math.min(0.82, Math.abs(v));
              return <i key={`${row}-${col}`} title={`${row} ${col}: ${formatValue(v)}`} style={{ background: pos ? `rgba(34,197,94,${alpha})` : `rgba(239,68,68,${alpha})` }}>{formatValue(v)}</i>;
            })}
          </>
        ))}
      </div>
    </ChartFrame>
  );
}

function DataTable({ section: sectionDef }) {
  const rows = previewRows(sectionDef);
  const cols = Object.keys(rows[0] || {});
  return (
    <ChartFrame>
      <div className="pca-table-wrap">
        <table className="pca-table">
          <thead><tr>{cols.map((col) => <th key={col}>{titleize(col)}</th>)}</tr></thead>
          <tbody>{rows.map((row, idx) => <tr key={idx}>{cols.map((col) => <td key={col}>{formatValue(row[col])}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </ChartFrame>
  );
}

function MetricDeck({ section: sectionDef }) {
  return (
    <div className="pca-metric-grid">
      {previewRows(sectionDef).map((row) => (
        <div className="pca-metric-card" key={row.name}>
          <span>{row.name}</span>
          <strong>{formatValue(row.value)}</strong>
          <small>{row.unit || "live output"}</small>
        </div>
      ))}
    </div>
  );
}

function Waterfall({ section: sectionDef }) {
  const rows = previewRows(sectionDef);
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height={310}>
        <BarChart data={rows}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.55} vertical={false} />
          <XAxis dataKey="name" {...axis} />
          <YAxis {...axis} />
          <Tooltip content={<PcaTooltip />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {rows.map((row, i) => <Cell key={i} fill={(numberLike(row.value) ?? 0) >= 0 ? TOKENS.green : TOKENS.red} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function PieVisual({ section: sectionDef }) {
  const rows = previewRows(sectionDef);
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height={310}>
        <PieChart>
          <Tooltip content={<PcaTooltip />} />
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius={70} outerRadius={116} paddingAngle={2}>
            {rows.map((_, i) => <Cell key={i} fill={SERIES[i % SERIES.length]} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function TensorVisual({ section: sectionDef }) {
  return (
    <ChartFrame>
      <div className="pca-tensor">
        {Array.from({ length: 36 }, (_, i) => <i key={i} style={{ opacity: 0.25 + ((i * 17) % 70) / 100 }} />)}
      </div>
    </ChartFrame>
  );
}

function RenderOutput({ section: sectionDef }) {
  if (sectionDef.chartType === "heatmap") return <Heatmap section={sectionDef} />;
  if (sectionDef.chartType === "table" || sectionDef.chartType === "timeline" || sectionDef.chartType === "clusterMap") return <DataTable section={sectionDef} />;
  if (sectionDef.chartType === "metricDeck") return <MetricDeck section={sectionDef} />;
  if (sectionDef.chartType === "waterfall") return <Waterfall section={sectionDef} />;
  if (sectionDef.chartType === "pie") return <PieVisual section={sectionDef} />;
  if (sectionDef.chartType === "tensor") return <TensorVisual section={sectionDef} />;
  return <StandardChart section={sectionDef} />;
}

function FieldControl({ field, value, onChange }) {
  if (field.type === "select") {
    return (
      <label className="pca-field">
        <span>{field.label}</span>
        <select value={String(value ?? "")} onChange={(e) => onChange(field.key, e.target.value)}>
          {(field.options || []).map((opt) => <option key={String(opt)} value={String(opt)}>{String(opt)}</option>)}
        </select>
      </label>
    );
  }
  if (field.type === "tokens") {
    const selected = new Set(String(value ?? "").split(",").map((v) => v.trim()).filter(Boolean));
    return (
      <label className="pca-field pca-wide">
        <span>{field.label}</span>
        <div className="pca-token-row">
          {(field.options || []).map((opt) => {
            const on = selected.has(String(opt));
            return <button key={String(opt)} type="button" className={on ? "on" : ""} onClick={() => {
              const next = new Set(selected);
              if (on) next.delete(String(opt)); else next.add(String(opt));
              onChange(field.key, [...next].join(","));
            }}>{String(opt)}</button>;
          })}
        </div>
      </label>
    );
  }
  if (field.type === "textarea") {
    return (
      <label className="pca-field pca-wide">
        <span>{field.label}</span>
        <textarea value={value ?? ""} placeholder={field.placeholder || ""} onChange={(e) => onChange(field.key, e.target.value)} />
      </label>
    );
  }
  const isTicker = /ticker|symbol|asset|universe/i.test(`${field.key} ${field.inputType || ""}`);
  return (
    <label className={`pca-field ${isTicker ? "pca-wide" : ""}`}>
      <span>{field.label}</span>
      <div className={isTicker ? "pca-terminal-input" : ""}>
        {isTicker ? <Search size={15} /> : null}
        <input type={field.type === "number" ? "number" : "text"} value={value ?? ""} placeholder={field.placeholder || ""} onChange={(e) => onChange(field.key, e.target.value)} />
      </div>
      {field.presets?.length ? <div className="pca-presets">{field.presets.map((p) => <button key={String(p)} type="button" onClick={() => onChange(field.key, p)}>{String(p)}</button>)}</div> : null}
    </label>
  );
}

function InputDeck({ feature, form, setForm }) {
  const groups = useMemo(() => {
    const map = new Map();
    feature.fields.forEach((field) => {
      const key = field.group || "Parameters";
      map.set(key, [...(map.get(key) || []), field]);
    });
    return [...map.entries()];
  }, [feature]);
  return (
    <div className="pca-input-deck">
      {groups.map(([group, fields]) => (
        <section key={group} className="pca-input-group">
          <h3>{group}</h3>
          <div className="pca-input-grid">
            {fields.map((field) => <FieldControl key={field.key} field={field} value={form[field.key]} onChange={(key, next) => setForm((old) => ({ ...old, [key]: next }))} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

export function PcaV2Workbench({ featureId, sections }) {
  const feature = getPcaV2Feature(featureId);
  const outputBook = sections || PCA_OUTPUT_BOOKS[feature.id] || [];
  const [form, setForm] = useState(feature.defaults);
  const [inputsOpen, setInputsOpen] = useState(true);
  return (
    <main className="pca-page">
      <section className="pca-hero">
        <div>
          <p>PCA V2 // FEATURE {feature.id}</p>
          <h1>{feature.title}</h1>
          <span>{feature.description}</span>
        </div>
        <div className="pca-hero-actions">
          <button type="button" onClick={() => setInputsOpen((open) => !open)}><Settings2 size={16} /> Inputs <ChevronDown size={14} className={inputsOpen ? "up" : ""} /></button>
          <button type="button" className="primary"><Play size={16} /> API pending</button>
        </div>
      </section>

      {inputsOpen ? <InputDeck feature={feature} form={form} setForm={setForm} /> : null}

      <section className="pca-workspace">
        <aside className="pca-output-nav">
          <b>OUTPUT BOOK</b>
          {outputBook.map((item, index) => (
            <a key={item.id} href={`#${item.id}`}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {item.title}
            </a>
          ))}
        </aside>
        <div className="pca-output-stack">
          {outputBook.map((item) => (
            <article id={item.id} key={item.id} className={`pca-output-card rank-${item.rank}`}>
              <header>
                <div>
                  <small>{item.source}.{item.dataKey}</small>
                  <h2>{item.title}</h2>
                </div>
                <div className="pca-card-tools">
                  <button type="button" title="Copy key"><Copy size={14} /></button>
                  <button type="button" title="Export shell"><Download size={14} /></button>
                </div>
              </header>
              <RenderOutput section={item} />
              <footer><CircleDot size={11} /> Ready for API key <code>{item.dataKey}</code></footer>
            </article>
          ))}
        </div>
      </section>

      <style jsx global>{`
        .pca-page {
          min-height: 100dvh;
          padding: 34px clamp(18px, 3vw, 52px) 110px;
          background:
            radial-gradient(ellipse 70% 38% at 50% -10%, rgba(245,164,0,.10), transparent 60%),
            linear-gradient(180deg, #090909, ${TOKENS.page} 34%);
          color: ${TOKENS.text};
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        .pca-hero {
          display: flex;
          justify-content: space-between;
          gap: 24px;
          align-items: end;
          margin: 0 auto 22px;
          max-width: 1720px;
          border-bottom: 1px solid ${TOKENS.borderSoft};
          padding-bottom: 22px;
        }
        .pca-hero p, .pca-output-nav b {
          color: ${TOKENS.accent};
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .18em;
          margin: 0 0 12px;
        }
        .pca-hero h1 {
          margin: 0;
          max-width: 940px;
          color: ${TOKENS.text};
          font-family: Georgia, "Times New Roman", serif;
          font-size: clamp(38px, 5vw, 76px);
          line-height: .93;
          letter-spacing: -.045em;
        }
        .pca-hero span {
          display: block;
          max-width: 820px;
          margin-top: 18px;
          color: ${TOKENS.secondary};
          font-size: 16px;
          line-height: 1.65;
        }
        .pca-hero-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
        .pca-hero-actions button {
          height: 42px;
          display: inline-flex;
          align-items: center;
          gap: 9px;
          border: 1px solid ${TOKENS.border};
          border-radius: 8px;
          background: ${TOKENS.raised};
          color: ${TOKENS.text};
          padding: 0 16px;
          font-weight: 800;
          cursor: pointer;
        }
        .pca-hero-actions .primary { background: ${TOKENS.accent}; color: #050505; }
        .pca-hero-actions .up { transform: rotate(180deg); }
        .pca-input-deck {
          max-width: 1720px;
          margin: 0 auto 24px;
          border: 1px solid ${TOKENS.border};
          border-radius: 14px;
          background: rgba(11,11,11,.84);
          box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 30px 90px rgba(0,0,0,.32);
          overflow: hidden;
        }
        .pca-input-group {
          display: grid;
          grid-template-columns: 180px 1fr;
          gap: 20px;
          padding: 18px 22px;
          border-top: 1px solid ${TOKENS.borderSoft};
        }
        .pca-input-group:first-child { border-top: 0; }
        .pca-input-group h3 {
          margin: 5px 0 0;
          color: ${TOKENS.muted};
          font-size: 10px;
          font-weight: 950;
          letter-spacing: .18em;
          text-transform: uppercase;
        }
        .pca-input-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
          gap: 14px;
        }
        .pca-field { display: grid; gap: 7px; color: ${TOKENS.secondary}; font-size: 12px; font-weight: 750; }
        .pca-field span { color: ${TOKENS.secondary}; }
        .pca-wide { grid-column: span 2; }
        .pca-field input, .pca-field select, .pca-field textarea {
          width: 100%;
          min-height: 38px;
          border: 1px solid ${TOKENS.border};
          border-radius: 7px;
          background: ${TOKENS.input};
          color: ${TOKENS.text};
          padding: 0 11px;
          outline: none;
          font: 700 12px "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
        }
        .pca-field textarea { min-height: 78px; padding: 10px 11px; resize: vertical; }
        .pca-field input:focus, .pca-field select:focus, .pca-field textarea:focus {
          border-color: rgba(245,164,0,.62);
          box-shadow: 0 0 0 3px rgba(245,164,0,.12);
        }
        .pca-terminal-input {
          display: flex;
          align-items: center;
          gap: 8px;
          border: 1px solid ${TOKENS.border};
          border-radius: 7px;
          background: #090909;
          padding-left: 10px;
        }
        .pca-terminal-input svg { color: ${TOKENS.accent}; }
        .pca-terminal-input input { border: 0; background: transparent; box-shadow: none !important; }
        .pca-token-row, .pca-presets { display: flex; gap: 6px; flex-wrap: wrap; }
        .pca-token-row button, .pca-presets button {
          min-height: 26px;
          border: 1px solid ${TOKENS.border};
          border-radius: 6px;
          background: ${TOKENS.raised};
          color: ${TOKENS.secondary};
          font-size: 11px;
          font-weight: 800;
          cursor: pointer;
          padding: 0 9px;
        }
        .pca-token-row button.on { color: #050505; background: ${TOKENS.accent}; }
        .pca-workspace {
          max-width: 1720px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: 270px minmax(0, 1fr);
          gap: 18px;
        }
        .pca-output-nav {
          position: sticky;
          top: 16px;
          align-self: start;
          border: 1px solid ${TOKENS.border};
          border-radius: 14px;
          background: rgba(10,10,10,.88);
          padding: 16px 12px;
          max-height: calc(100dvh - 120px);
          overflow: auto;
        }
        .pca-output-nav a {
          display: grid;
          grid-template-columns: 34px 1fr;
          align-items: center;
          gap: 8px;
          min-height: 42px;
          padding: 7px 10px;
          border-radius: 10px;
          color: ${TOKENS.secondary};
          text-decoration: none;
          font-size: 12px;
          line-height: 1.35;
        }
        .pca-output-nav a:hover { background: ${TOKENS.raised}; color: ${TOKENS.text}; transform: translateX(4px); }
        .pca-output-nav a span { color: ${TOKENS.accent}; font-family: "JetBrains Mono", monospace; font-size: 11px; }
        .pca-output-stack { display: grid; gap: 14px; min-width: 0; }
        .pca-output-card {
          border: 1px solid ${TOKENS.border};
          border-left: 3px solid transparent;
          border-radius: 14px;
          background:
            linear-gradient(180deg, rgba(255,255,255,.035), transparent 22%),
            repeating-linear-gradient(0deg, rgba(255,255,255,.018) 0 1px, transparent 1px 5px),
            ${TOKENS.screen};
          padding: 18px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,.055), 0 24px 70px rgba(0,0,0,.24);
        }
        .pca-output-card.rank-primary { border-left-color: ${TOKENS.accent}; }
        .pca-output-card header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 16px;
          margin-bottom: 14px;
        }
        .pca-output-card h2 { margin: 3px 0 0; font-size: 18px; letter-spacing: -.02em; }
        .pca-output-card small, .pca-output-card footer {
          color: ${TOKENS.muted};
          font: 800 10px "JetBrains Mono", monospace;
          letter-spacing: .08em;
        }
        .pca-output-card footer {
          margin-top: 12px;
          padding-top: 10px;
          border-top: 1px solid ${TOKENS.borderSoft};
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .pca-output-card code { color: ${TOKENS.accent}; }
        .pca-card-tools { display: flex; gap: 6px; }
        .pca-card-tools button {
          width: 32px;
          height: 32px;
          border: 1px solid ${TOKENS.border};
          border-radius: 7px;
          background: ${TOKENS.raised};
          color: ${TOKENS.secondary};
          display: grid;
          place-items: center;
        }
        .pca-chart-frame {
          min-height: 250px;
          border: 1px solid ${TOKENS.borderSoft};
          border-radius: 11px;
          background: radial-gradient(ellipse 70% 50% at 50% 0%, rgba(245,164,0,.05), transparent 65%), #080808;
          padding: 14px;
          overflow: auto;
          cursor: crosshair;
        }
        .pca-tooltip {
          display: grid;
          gap: 5px;
          min-width: 160px;
          padding: 10px 12px;
          border: 1px solid ${TOKENS.border};
          border-radius: 8px;
          background: ${TOKENS.raised};
          color: ${TOKENS.text};
          box-shadow: 0 16px 42px rgba(0,0,0,.55);
        }
        .pca-tooltip b { color: ${TOKENS.accent}; font-size: 11px; }
        .pca-tooltip span { display: flex; justify-content: space-between; gap: 14px; color: ${TOKENS.secondary}; font-size: 11px; }
        .pca-tooltip em { font-style: normal; font-family: "JetBrains Mono", monospace; }
        .pca-heatmap {
          min-width: 520px;
          display: grid;
          gap: 4px;
          align-items: stretch;
        }
        .pca-heatmap b, .pca-heatmap strong {
          color: ${TOKENS.secondary};
          font: 800 10px "JetBrains Mono", monospace;
          text-align: center;
          align-self: center;
        }
        .pca-heatmap strong { text-align: right; padding-right: 8px; }
        .pca-heatmap i {
          min-height: 42px;
          display: grid;
          place-items: center;
          border-radius: 6px;
          color: ${TOKENS.text};
          font: 800 10px "JetBrains Mono", monospace;
          font-style: normal;
        }
        .pca-table-wrap { overflow: auto; max-height: 420px; }
        .pca-table { width: 100%; border-collapse: collapse; min-width: 620px; }
        .pca-table th, .pca-table td {
          border-bottom: 1px solid ${TOKENS.borderSoft};
          padding: 10px 12px;
          text-align: left;
          color: ${TOKENS.secondary};
          font-size: 12px;
        }
        .pca-table th {
          position: sticky;
          top: 0;
          z-index: 1;
          background: #111;
          color: ${TOKENS.accent};
          font: 900 10px "JetBrains Mono", monospace;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .pca-table td { font-family: "JetBrains Mono", monospace; }
        .pca-metric-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px;
        }
        .pca-metric-card {
          min-height: 118px;
          border: 1px solid ${TOKENS.borderSoft};
          border-radius: 11px;
          background: #080808;
          padding: 16px;
          display: grid;
          align-content: center;
          gap: 7px;
        }
        .pca-metric-card span { color: ${TOKENS.muted}; font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
        .pca-metric-card strong { color: ${TOKENS.text}; font: 900 30px "JetBrains Mono", monospace; }
        .pca-metric-card small { color: ${TOKENS.secondary}; }
        .pca-tensor {
          min-height: 300px;
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 8px;
          perspective: 900px;
        }
        .pca-tensor i {
          border: 1px solid rgba(245,164,0,.25);
          border-radius: 8px;
          background: linear-gradient(135deg, rgba(245,164,0,.5), rgba(20,184,166,.18));
          transform: rotateX(18deg) rotateY(-22deg);
          box-shadow: 0 18px 36px rgba(0,0,0,.32);
        }
        @media (max-width: 980px) {
          .pca-hero { display: grid; align-items: start; }
          .pca-workspace { grid-template-columns: 1fr; }
          .pca-output-nav { position: static; max-height: none; }
          .pca-input-group { grid-template-columns: 1fr; }
          .pca-wide { grid-column: span 1; }
        }
      `}</style>
    </main>
  );
}

export function PcaV2HomePage() {
  return (
    <main className="pca-home">
      <section className="pca-home-hero">
        <p>ATLAS // PCA INTELLIGENCE</p>
        <h1>Principal component risk infrastructure.</h1>
        <span>Eleven PCA modules for RMT covariance cleaning, residual stat-arb, cross-asset covariance, stress, liquidity, and validation.</span>
      </section>
      <section className="pca-home-grid">
        {PCA_V2_FEATURES.map((feature) => (
          <Link key={feature.id} href={`/labs/pca-v2/${feature.slug}`} className="pca-home-card">
            <i>P{feature.id}</i>
            <h2>{feature.shortTitle}</h2>
            <p>{feature.description}</p>
          </Link>
        ))}
      </section>
      <style jsx global>{`
        .pca-home {
          min-height: 100dvh;
          padding: 80px clamp(18px, 4vw, 70px) 120px;
          background: radial-gradient(ellipse 80% 46% at 50% -12%, rgba(245,164,0,.13), transparent 60%), #050505;
          color: #f7f1e6;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        .pca-home-hero { max-width: 980px; margin: 0 auto 42px; text-align: center; }
        .pca-home-hero p { color: #f5a400; font-size: 11px; font-weight: 950; letter-spacing: .2em; }
        .pca-home-hero h1 { margin: 0; font: 800 clamp(48px, 7vw, 96px)/.9 Georgia, serif; letter-spacing: -.05em; }
        .pca-home-hero span { display: block; margin: 22px auto 0; max-width: 720px; color: #aaa194; font-size: 18px; line-height: 1.65; }
        .pca-home-grid { max-width: 1440px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
        .pca-home-card { min-height: 220px; border: 1px solid #312610; border-radius: 14px; background: linear-gradient(180deg, rgba(255,255,255,.035), transparent), #0a0a0a; padding: 22px; text-decoration: none; color: #f7f1e6; transition: transform 150ms ease, border-color 150ms ease; }
        .pca-home-card:hover { transform: translateY(-5px); border-color: rgba(245,164,0,.55); }
        .pca-home-card i { color: #f5a400; font: normal 900 11px "JetBrains Mono", monospace; letter-spacing: .16em; }
        .pca-home-card h2 { margin: 18px 0 10px; font-size: 22px; }
        .pca-home-card p { margin: 0; color: #aaa194; font-size: 14px; line-height: 1.6; }
      `}</style>
    </main>
  );
}
