export const SCREENER_V2_FEATURES = [
  {
    id: "01",
    slug: "feature-01",
    title: "Core Multi-Factor Screener Engine",
    shortTitle: "Core Screen",
    description: "Master-universe factor ranking, liquidity filters, sector-relative context, quick-look price panels and saved-screen-ready output.",
    defaults: { universe: "master", max_symbols: 500, lookback_days: 756, sector: "all", market_cap_min: "", dollar_volume_min: "", score_min: "", top_n: 50, focus_ticker: "AAPL" },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "max_symbols", label: "Max Symbols", type: "number", group: "Universe", presets: [100, 250, 500, 1000, 2500] },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Window", presets: [252, 504, 756, 1260] },
      { key: "sector", label: "Sector", type: "text", group: "Filters" },
      { key: "market_cap_min", label: "Min Market Cap", type: "number", group: "Filters" },
      { key: "dollar_volume_min", label: "Min Dollar Vol", type: "number", group: "Filters" },
      { key: "score_min", label: "Min Score", type: "number", group: "Filters", presets: [50, 60, 70, 80, 90] },
      { key: "focus_ticker", label: "Focus Ticker", type: "ticker", group: "Quick Look", inputType: "ticker" },
    ],
  },
  {
    id: "02",
    slug: "feature-02",
    title: "Formula Builder and Custom Expression Screener",
    shortTitle: "Formula",
    description: "Terminal-style custom expression engine with validation diagnostics, formula result ranks and historical proxy backtest.",
    defaults: { universe: "master", formula: "0.4*rank(earnings_yield)+0.3*rank(momentum_jt)+0.3*rank(roe)", lookback_days: 756, top_n: 50 },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "formula", label: "Formula", type: "formula", group: "Expression" },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Backtest", presets: [252, 504, 756, 1260] },
      { key: "top_n", label: "Top N", type: "number", group: "Backtest", presets: [25, 50, 100, 250] },
    ],
  },
  {
    id: "03",
    slug: "feature-03",
    title: "Composite Quant Score Engine",
    shortTitle: "Composite",
    description: "Weighted factor composites, score transparency, component IC, redundancy heatmaps and regime-conditional breakdowns.",
    defaults: { universe: "master", components: "", weighting_mode: "manual", ic_target_field: "return_1m", ridge_lambda: 1, lookback_days: 756, top_n: 50, winsorize: true, sector_neutral: false, beta_neutral: false },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "components", label: "Components JSON", type: "json", group: "Composite" },
      { key: "weighting_mode", label: "Weighting Mode", type: "select", options: ["manual", "ic_ir", "ridge"], group: "Composite" },
      { key: "ic_target_field", label: "IC Target", type: "select", options: ["return_1m", "return_3m", "return_6m"], group: "Composite" },
      { key: "ridge_lambda", label: "Ridge λ", type: "number", group: "Composite", presets: [0.1, 0.5, 1, 2, 5] },
      { key: "winsorize", label: "Winsorize", type: "select", options: [true, false], group: "Composite" },
      { key: "sector_neutral", label: "Sector Neutral", type: "select", options: [false, true], group: "Composite" },
      { key: "beta_neutral", label: "Beta Neutral", type: "select", options: [false, true], group: "Composite" },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Backtest", presets: [252, 504, 756, 1260] },
      { key: "top_n", label: "Top N", type: "number", group: "Backtest", presets: [25, 50, 100] },
    ],
  },
  {
    id: "04",
    slug: "feature-04",
    title: "Academic Strategy Screener Library",
    shortTitle: "Academic",
    description: "Magic Formula, Piotroski, Altman, value composites, quality, low-vol and momentum screens in one strategy book.",
    defaults: { universe: "master", strategy: "magic_formula", lookback_days: 756, top_n: 50, strategy_perf_limit: 12 },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "strategy", label: "Strategy", type: "select", group: "Strategy", options: ["magic_formula", "acquirers_multiple", "value_composite_two", "momentum_jt", "low_vol", "conservative_formula", "trending_value", "piotroski_f_score"] },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Backtest", presets: [252, 504, 756, 1260] },
      { key: "top_n", label: "Top N", type: "number", group: "Backtest", presets: [25, 50, 100] },
      { key: "strategy_perf_limit", label: "Perf Limit", type: "number", group: "Backtest", presets: [6, 12, 18, 24] },
    ],
  },
  {
    id: "05",
    slug: "feature-05",
    title: "Screener Backtester with Point-in-Time Validation",
    shortTitle: "Backtester",
    description: "Equity curve, holding-period sensitivity, rebalancing-date sensitivity, PBO proxy, turnover and stock-level attribution.",
    defaults: { universe: "master", score_field: "core_quant_score", lookback_days: 756, top_n: 50, transaction_cost_bps: 10, run_full_pbo: false, pbo_trials: 20 },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "score_field", label: "Score Field", type: "select", group: "Signal", options: ["core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"] },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Backtest", presets: [252, 504, 756, 1260] },
      { key: "top_n", label: "Top N", type: "number", group: "Backtest", presets: [25, 50, 100] },
      { key: "transaction_cost_bps", label: "Cost bps", type: "number", group: "Execution", presets: [0, 5, 10, 25, 50] },
      { key: "run_full_pbo", label: "Run PBO", type: "select", options: [false, true], group: "Research" },
      { key: "pbo_trials", label: "PBO Trials", type: "number", group: "Research", presets: [5, 20, 60] },
    ],
  },
  {
    id: "06",
    slug: "feature-06",
    title: "Alert Engine and Watchlist Monitor",
    shortTitle: "Alerts",
    description: "Watchlist live dashboard, score/return/technical alerts, entry-exit logs and alert performance tracking shell.",
    defaults: { watchlist: "AAPL MSFT NVDA AMZN META GOOGL", alert_score_min: 80, alert_return_1d_abs: 0.05 },
    fields: [
      { key: "watchlist", label: "Watchlist", type: "ticker_list", group: "Watchlist", inputType: "multiTicker" },
      { key: "alert_score_min", label: "Score Alert", type: "number", group: "Thresholds", presets: [60, 70, 80, 90] },
      { key: "alert_return_1d_abs", label: "1D Move Alert", type: "number", group: "Thresholds", presets: [0.02, 0.03, 0.05, 0.08] },
    ],
  },
  {
    id: "07",
    slug: "feature-07",
    title: "Comparative Relative Valuation Screener",
    shortTitle: "Relative Value",
    description: "Four-dimensional valuation cards, sector valuation heatmap, own-history percentiles and peer comparison tables.",
    defaults: { universe: "master", focus_ticker: "AAPL", lookback_days: 756 },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "focus_ticker", label: "Focus Ticker", type: "ticker", group: "Focus", inputType: "ticker" },
      { key: "lookback_days", label: "Lookback", type: "number", group: "Window", presets: [252, 504, 756, 1260] },
    ],
  },
  {
    id: "08",
    slug: "feature-08",
    title: "Screener Result Export and Integration Layer",
    shortTitle: "Export",
    description: "Instant TSV/JSON export payload, API endpoint metadata, current-run change report and integration-ready response envelope.",
    defaults: { universe: "master", export_format: "tsv", top_n: 100 },
    fields: [
      { key: "universe", label: "Universe", type: "ticker_list", group: "Universe", inputType: "multiTicker" },
      { key: "export_format", label: "Export Format", type: "select", group: "Export", options: ["tsv", "json"] },
      { key: "top_n", label: "Top N", type: "number", group: "Export", presets: [50, 100, 250, 500] },
    ],
  },
];

function s(id, title, source, dataKey, chartType, extra = {}) {
  return { id, title, source, dataKey, chartType, rank: extra.rank || "supporting", fallbackKeys: extra.fallbackKeys || [], config: extra.config || {} };
}

export const SCREENER_OUTPUT_BOOKS = {
  "01": [
    s("ranked", "Ranked Screener Table", "tables", "ranked_screener_table", "screenerTable", { rank: "primary" }),
    s("funnel", "Filter Funnel", "charts", "filter_funnel_waterfall", "waterfall"),
    s("percentiles", "Cross-Sectional Percentile Context", "charts", "cross_sectional_percentile_context", "factorBars"),
    s("heatmap", "Sector Heatmap View", "charts", "heatmap_view", "heatmap"),
    s("quick", "Quick-Look Card", "charts", "quick_look_card", "quickLook"),
    s("buckets", "Market Cap Bucket Distribution", "charts", "market_cap_bucket_distribution", "bar"),
    s("saved", "Saved Screens", "tables", "saved_screens", "table"),
  ],
  "02": [
    s("results", "Formula Result Table", "tables", "formula_result_table", "screenerTable", { rank: "primary" }),
    s("validation", "Formula Validation Panel", "tables", "formula_validation_panel", "diagnostic"),
    s("backtest", "Historical Formula Backtest", "charts", "historical_formula_backtest", "equityCurve"),
    s("factor-zoo", "Factor Zoo Comparison", "charts", "factor_zoo_comparison", "bar"),
  ],
  "03": [
    s("ranking", "Composite Score Universe Ranking", "tables", "composite_score_universe_ranking", "screenerTable", { rank: "primary" }),
    s("decomp", "Score Transparency Decomposition", "tables", "score_transparency_decomposition", "weights"),
    s("stock-decomp", "Per-Stock Score Decomposition", "tables", "per_stock_score_decomposition", "weights"),
    s("ic", "Component IC/IR Leaderboard", "tables", "component_ic_ir_leaderboard", "table"),
    s("corr", "Factor Correlation Heatmap", "charts", "factor_correlation_heatmap", "heatmap"),
    s("bt", "Composite vs Factor Backtest", "charts", "composite_vs_factor_backtest", "equityCurve"),
    s("regime", "Regime Conditional Composite Breakdown", "tables", "regime_conditional_composite_breakdown", "table"),
  ],
  "04": [
    s("leader", "Strategy Leaderboard", "tables", "strategy_leaderboard", "strategyLeaderboard", { rank: "primary" }),
    s("stocks", "Per-Strategy Stock List", "tables", "per_strategy_stock_list", "screenerTable"),
    s("piotroski", "Piotroski Breakdown", "tables", "piotroski_breakdown", "table"),
    s("altman", "Altman Z-Score Status", "tables", "altman_z_score_status", "table"),
    s("corr", "Strategy Correlation Matrix", "charts", "strategy_correlation_matrix", "heatmap"),
    s("perf", "Historical Strategy Performance", "charts", "historical_strategy_performance", "equityCurve"),
    s("perf-all", "Historical Strategy Performance All", "tables", "historical_strategy_performance_all", "table"),
    s("perf-meta", "Performance Metadata", "tables", "historical_strategy_performance_metadata", "diagnostic"),
  ],
  "05": [
    s("equity", "Equity Curve", "charts", "equity_curve", "equityCurve", { rank: "primary" }),
    s("stats", "Full Performance Statistics", "tables", "full_performance_statistics", "metricDeck"),
    s("rolling", "Rolling Performance", "charts", "rolling_performance", "line"),
    s("holding", "Holding-Period Sensitivity", "tables", "holding_period_sensitivity", "table"),
    s("rebalance", "Rebalancing-Date Sensitivity", "tables", "rebalancing_date_sensitivity", "table"),
    s("weekday", "Weekday Rebalance Sensitivity", "tables", "rebalancing_date_sensitivity_by_weekday", "weekday"),
    s("turnover", "Turnover Report", "tables", "turnover_report", "table"),
    s("sector", "Sector Attribution", "tables", "sector_attribution", "table"),
    s("regime", "Regime Conditional Performance", "tables", "regime_conditional_performance", "table"),
    s("mc", "Monte Carlo Sharpe Distribution", "charts", "monte_carlo_sharpe_distribution", "histogram"),
    s("stock", "Stock-Level Attribution", "tables", "stock_level_attribution", "table"),
  ],
  "06": [
    s("feed", "Alert Feed", "charts", "alert_feed", "alertTape", { rank: "primary" }),
    s("tracker", "Alert Performance Tracker", "tables", "alert_performance_tracker", "table"),
    s("tracker-hist", "Historical Alert Precision Replay", "tables", "alert_performance_tracker_historical", "alertPrecision"),
    s("entry-exit", "Screen Entry/Exit Log", "tables", "screen_entry_exit_log", "table"),
  ],
  "07": [
    s("card", "Four-Dimension Valuation Card", "charts", "four_dimension_valuation_card", "valuationCard", { rank: "primary" }),
    s("landscape", "Sector Valuation Landscape Heatmap", "charts", "sector_valuation_landscape_heatmap", "heatmap"),
    s("history", "Own-History Percentile Time Series", "charts", "own_history_percentile_time_series", "line"),
    s("peers", "Peer Comparison Table", "tables", "peer_comparison_table", "screenerTable"),
    s("universe", "Universe Percentile Table", "tables", "universe_percentile_table", "table"),
  ],
  "08": [
    s("download", "Instant Download", "tables", "instant_download", "exportPayload", { rank: "primary" }),
    s("endpoint", "Screen Result API Endpoint", "tables", "screen_result_api_endpoint", "diagnostic"),
    s("change", "Change Report", "charts", "change_report", "changeReport"),
  ],
};

export function getScreenerV2Feature(featureId) {
  const normalized = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
  const feature = SCREENER_V2_FEATURES.find((item) => item.id === normalized);
  if (!feature) throw new Error(`Unknown Screener V2 feature: ${featureId}`);
  return feature;
}
