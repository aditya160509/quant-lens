import dynamic from "next/dynamic";
import { Bell, Bookmark, FlaskConical, Layers, Scale, SlidersHorizontal, Sigma, Table2, Trophy } from "lucide-react";
import { createElement } from "react";
import { SCREENER_BASE } from "./base";
import { FormulaControl } from "./formula/FormulaControl";
import { FilterTree } from "./filters/FilterTree";
import { InFilter } from "./filters/InFilter";
import { WatchlistFilter } from "./filters/WatchlistFilter";
import { ComponentWeights } from "./rank/ComponentWeights";
import { TemplatePicker } from "./rank/TemplatePicker";
import { RowActions } from "./RowActions";
import { ScreenerHome } from "./home/ScreenerHome";
import { isNum } from "@/modules/research/format";
import { group, registerAlternates, registerViews } from "@/modules/research/outputs/registry";
import type { FeatureMeta, LabConfig, Page } from "@/modules/research/lab";
import type { FeatureResult, FeatureSpec, InputSpec, OutputSpec } from "@/modules/research/types";

/** Screener features carry an "sc" prefix so their runs and settings never collide with other labs. */
const ID = (raw: string) => `sc${raw}`;
const RAW = (id: string) => id.replace(/^sc/, "");

const CATALOG: Record<string, FeatureMeta> = {
  sc01: { name: "Screen", slug: "screen", icon: SlidersHorizontal, question: "Which names pass, and what removed the rest?" },
  sc02: { name: "Formula", slug: "formula", icon: Sigma, question: "Which names does my own expression rank highest?" },
  sc07: { name: "Valuation", slug: "valuation", icon: Scale, question: "How cheap is each name against its sector and its own history?" },
  sc03: { name: "Composite score", slug: "composite", icon: Trophy, question: "Who ranks highest once factors are combined?" },
  sc05: { name: "Backtest", slug: "backtest", icon: FlaskConical, question: "Would this screen have made money after costs?" },
  sc06: { name: "Alerts", slug: "alerts", icon: Bell, question: "What changed on my watchlist?" },
  sc08: { name: "Changes and export", slug: "export", icon: Table2, question: "What entered or left the screen since the last run?" },
};

const PAGES: Page[] = [
  { id: "screen", label: "Screen", icon: SlidersHorizontal, question: CATALOG.sc01.question, features: ["sc01", "sc02", "sc07"] },
  { id: "rank", label: "Rank", icon: Trophy, question: CATALOG.sc03.question, features: ["sc03"] },
  { id: "test", label: "Test", icon: FlaskConical, question: CATALOG.sc05.question, features: ["sc05"] },
  { id: "monitor", label: "Monitor", icon: Bell, question: CATALOG.sc06.question, features: ["sc06", "sc08"] },
  { id: "saved", label: "Saved", icon: Bookmark, question: "Screens you keep, when they re-run and who they alert.", features: [], slug: "saved" },
  { id: "more", label: "More", icon: Layers, question: "Other markets, hourly bars, formulas, sharing and API keys.", features: [], slug: "more" },
];

type RawFeature = { id: string; name: string; inputs: InputSpec[]; outputs: { key: string; title?: string; label?: string; render?: string }[] };

const VIEW: Record<string, string> = { table: "dataTable", metrics: "keyValue", lineChart: "lineChart", heatmap: "heatmap" };

function toSpec(f: RawFeature): FeatureSpec {
  const outputs: OutputSpec[] = f.outputs.filter((o) => o.render !== "download").map((o) => ({
    key: o.key, title: o.title ?? o.label ?? o.key, source: o.render === "table" ? "tables" : "charts", render: VIEW[o.render ?? ""] ?? "dataTable",
  }));
  return { id: ID(f.id), name: f.name, description: CATALOG[ID(f.id)]?.question ?? "", inputs: f.inputs.map((i) => ({ ...i, group: i.group || "Settings" })), outputs };
}

type Meta = FeatureResult["meta"] & { as_of_date?: string; universe_count?: number; data_version?: string; data_sources?: Record<string, { modified_ns?: number }> };

/** The result header: how many names passed, out of what, as of when, on which data. */
function headline(r: FeatureResult) {
  const meta = r.meta as Meta;
  const passed = r.summary_cards?.find((c) => c.label === "After filters")?.value;
  const mtimes = Object.values(meta.data_sources ?? {}).map((d) => d.modified_ns).filter(isNum);
  const known = r.summary_cards?.find((c) => c.label === "Data coverage")?.value;
  const parts = [
    isNum(passed) && isNum(meta.universe_count) ? `${passed.toLocaleString()} of ${meta.universe_count.toLocaleString()} names pass` : null,
    meta.as_of_date ? `as of ${meta.as_of_date}` : null,
    mtimes.length ? `updated ${new Date(Math.max(...mtimes) / 1e6).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}` : null,
    meta.data_version ? `data ${meta.data_version}` : null,
    isNum(known) ? `${known.toFixed(0)}% of key figures known` : null,
  ];
  return { headline: parts.filter(Boolean).join(" · ") || null, tone: isNum(known) && known < 60 ? ("warn" as const) : null };
}

/** The standing disclosure on a backtest: what the numbers cannot tell. */
function testBanner(r: FeatureResult) {
  const meta = r.meta as Meta;
  const parts = ["Today's names only: no delisted returns", "benchmark SPY", "fundamentals from 2021, 90-day lag", meta.as_of_date ? `prices to ${meta.as_of_date}` : null];
  return { headline: parts.filter(Boolean).join(" · "), tone: "warn" as const };
}

const rowActions = (row: Record<string, unknown>) => (typeof row.ticker === "string" ? createElement(RowActions, { ticker: row.ticker }) : null);
const RESULT_COLUMNS = ["rank", "ticker", "company_name", "sector", "exchange", "country", "quote_currency", "data_coverage", "statement_age_days", "price", "trend_3m", "market_cap", "core_quant_score", "sector_relative_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "trailing_pe", "pb_ratio", "roe", "revenue_growth_yoy", "return_1d", "return_1m", "return_6m", "qtr_sales_yoy", "qtr_profit_yoy", "realized_vol_63d", "max_drawdown_252d", "piotroski_passed", "altman_z_score"];
/** Percentiles drawn as bars on a 0 to 100 scale. */
const RESULT_BARS = ["data_coverage", "sector_relative_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"];
/** Provenance and always-empty fields, kept out of the columns. */
const RESULT_HIDDEN = ["currency_units_unavailable_reason", "financial_currency", "market_value_currency", "market_cap_statement_currency", "market_cap_observation_date", "market_cap_basis", "price_observation_date", "valuation_score_definition", "fundamental_basis", "enterprise_value_basis", "beta_effective_source", "beta_252_unavailable_reason", "float_percent", "forward_pe"];

const SavedPage = dynamic<{ features: FeatureSpec[]; id?: string }>(() => import("./saved/SavedPage"), { ssr: false });
const MorePage = dynamic<{ features: FeatureSpec[]; id?: string }>(() => import("./extras/MorePage"), { ssr: false });
const SV = group(() => import("./views") as Promise<Record<string, unknown>>);
const ST = group(() => import("./test/ProofViews") as Promise<Record<string, unknown>>);
const RV = group(() => import("./rank/RankViews") as Promise<Record<string, unknown>>);
registerViews({ screenTreemap: SV.ScreenTreemap, screenTable: SV.ScreenTable, nearMisses: SV.NearMissView, screenScatter: SV.ScatterView, sensitivity: SV.SensitivityView, runInfo: SV.RunView, screenDiff: SV.DiffView, proofPanel: ST.ProofPanel, scoreWaterfall: RV.ScoreWaterfall, rankVsMl: RV.RankVsMl }, []);
registerAlternates({ rankedTable: [{ label: "Sector treemap", view: "screenTreemap" }], screenTable: [{ label: "Sector treemap", view: "screenTreemap" }] });

export const SCREENER_LAB: LabConfig = {
  id: "screener",
  title: "Screener",
  root: "/screener",
  base: SCREENER_BASE,
  catalog: CATALOG,
  pages: PAGES,
  layouts: {
    sc01: {
      verdict: headline,
      sections: [
        { id: "results", label: "Results", items: [{ keys: ["ranked_screener_table"], span: 12, view: "screenTable", opts: { max: 5000, maxHeight: 640, columns: RESULT_COLUMNS, bars: RESULT_BARS, hide: RESULT_HIDDEN, hatch: true, rowActions } }] },
        { id: "trust", label: "Trust", items: [
          { keys: ["ranked_screener_table"], span: 12, view: "nearMisses", title: "Near misses" },
          { keys: ["ranked_screener_table"], span: 12, view: "sensitivity", title: "Sensitivity" },
          { keys: ["ranked_screener_table"], span: 12, view: "screenScatter", title: "Scatter" },
          { keys: ["ranked_screener_table"], span: 6, view: "screenDiff", title: "Compare runs" },
          { keys: ["ranked_screener_table"], span: 6, view: "runInfo", title: "Run" },
        ] },
        { id: "funnel", label: "Funnel", items: [{ keys: ["filter_funnel_waterfall"], span: 6 }, { keys: ["market_cap_bucket_distribution"], span: 6 }] },
        { id: "coverage", label: "Coverage", items: [{ keys: ["metric_coverage"], span: 12, view: "dataTable", opts: { max: 500, maxHeight: 640 } }] },
      ],
    },
    sc03: {
      sections: [
        { id: "ranking", label: "Ranking", items: [
          { keys: ["composite_score_universe_ranking"], span: 8, view: "rankedTable", opts: { max: 5000, maxHeight: 640, hatch: true, rowActions } },
          { keys: ["per_stock_score_decomposition"], span: 4, view: "scoreWaterfall", title: "Why the top name ranks here" },
        ] },
        { id: "weights", label: "Weights", items: [{ keys: ["score_transparency_decomposition"], span: 6, view: "dataTable" }, { keys: ["factor_correlation_heatmap"], span: 6 }] },
        { id: "ml", label: "Rules and ML", items: [{ keys: ["composite_score_universe_ranking"], span: 12, view: "rankVsMl", opts: { max: 5000, maxHeight: 480 } }] },
        { id: "backtest", label: "Backtest", items: [{ keys: ["composite_vs_spy_backtest"], span: 12 }] },
      ],
    },
    sc05: {
      verdict: testBanner,
      sections: [
        { id: "proof", label: "Proof", items: [{ keys: ["equity_curve", "cscv_pbo"], span: 12, view: "proofPanel" }] },
        { id: "performance", label: "Performance", items: [{ keys: ["equity_curve"], span: 8 }, { keys: ["full_performance_statistics"], span: 4 }, { keys: ["rolling_performance"], span: 12 }] },
        { id: "rebalancing", label: "Rebalancing", items: [{ keys: ["rebalancing_date_sensitivity"], span: 6 }, { keys: ["holding_period_sensitivity"], span: 6 }, { keys: ["turnover_report"], span: 12 }] },
      ],
    },
  },
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => ID(f.id) in CATALOG).map(toSpec),
  submit: (featureId, payload) => ({ path: `/feature/${RAW(featureId)}/jobs`, body: { payload } }),
  signal: false,
  specials: { saved: SavedPage, more: MorePage },
  widgets: { formula: FormulaControl, sector: InFilter, industry: InFilter, exchange: InFilter, country: InFilter, currency: InFilter, ticker_in: WatchlistFilter, filter_tree: FilterTree, screen_template: TemplatePicker, components: ComponentWeights },
  funnel: (result) => Object.fromEntries(((result?.charts?.filter_funnel_waterfall ?? []) as { key?: string; removed: number; remaining: number; bottleneck?: string | null }[]).filter((s) => s.key).map((s) => [s.key as string, { removed: s.removed, remaining: s.remaining, bottleneck: Boolean(s.bottleneck) }])),
  defaultUniverse: "All names we hold",
  overview: {
    home: ScreenerHome,
    intro: "Screen, rank, test and monitor, with every limit printed on the result.",
    stages: PAGES.filter((p) => p.features.length).map((p) => ({ id: p.id, label: p.label, intro: p.question, ids: p.features })),
  },
};
