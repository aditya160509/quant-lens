import { Bell, FlaskConical, Scale, SlidersHorizontal, Sigma, Table2, Trophy } from "lucide-react";
import { API_BASE_URL } from "@/lib/apiBase";
import { isNum } from "@/modules/research/format";
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
  const parts = [
    isNum(passed) && isNum(meta.universe_count) ? `${passed.toLocaleString()} of ${meta.universe_count.toLocaleString()} names pass` : null,
    meta.as_of_date ? `as of ${meta.as_of_date}` : null,
    mtimes.length ? `updated ${new Date(Math.max(...mtimes) / 1e6).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}` : null,
    meta.data_version ? `data ${meta.data_version}` : null,
  ];
  return { headline: parts.filter(Boolean).join(" · ") || null, tone: null };
}

const RESULT_COLUMNS = ["rank", "ticker", "company_name", "sector", "exchange", "price", "market_cap", "core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "trailing_pe", "pb_ratio", "roe", "revenue_growth_yoy", "return_6m", "realized_vol_63d"];
/** Provenance and always-empty fields, kept out of the columns. */
const RESULT_HIDDEN = ["currency_units_unavailable_reason", "quote_currency", "financial_currency", "market_value_currency", "market_cap_statement_currency", "market_cap_observation_date", "market_cap_basis", "price_observation_date", "valuation_score_definition", "fundamental_basis", "enterprise_value_basis", "beta_effective_source", "beta_252_unavailable_reason", "float_percent", "forward_pe"];

export const SCREENER_LAB: LabConfig = {
  id: "screener",
  title: "Screener",
  root: "/screener",
  base: `${API_BASE_URL}/screener-v2`,
  catalog: CATALOG,
  pages: PAGES,
  layouts: {
    sc01: {
      verdict: headline,
      sections: [
        { id: "results", label: "Results", items: [{ keys: ["ranked_screener_table"], span: 12, view: "dataTable", opts: { max: 5000, maxHeight: 640, columns: RESULT_COLUMNS, hide: RESULT_HIDDEN } }] },
        { id: "funnel", label: "Funnel", items: [{ keys: ["filter_funnel_waterfall"], span: 6 }, { keys: ["market_cap_bucket_distribution"], span: 6 }] },
      ],
    },
  },
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => ID(f.id) in CATALOG).map(toSpec),
  submit: (featureId, payload) => ({ path: `/feature/${RAW(featureId)}/jobs`, body: { payload } }),
  signal: false,
  defaultUniverse: "All names we hold",
  overview: {
    intro: "Screen, rank, test and monitor, with every limit printed on the result.",
    stages: PAGES.map((p) => ({ id: p.id, label: p.label, intro: p.question, ids: p.features })),
  },
};
