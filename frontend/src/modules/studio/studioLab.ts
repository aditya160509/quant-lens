import dynamic from "next/dynamic";
import { FlaskConical, PencilRuler } from "lucide-react";
import { STUDIO_BASE } from "./base";
import { StudioContext, StrategyPicker } from "./RunHeader";
import { isNum, pct } from "@/modules/research/format";
import type { HeroSpec } from "@/modules/research/Hero";
import { group, registerAlternates, registerViews } from "@/modules/research/outputs/registry";
import type { FeatureMeta, LabConfig, Page } from "@/modules/research/lab";
import type { FeatureResult, FeatureSpec, InputSpec, OutputSpec, RunRecord } from "@/modules/research/types";
import type { StudioMeta } from "./types";
import { lead } from "./leads";

const CATALOG: Record<string, FeatureMeta> = {
  st01: { name: "Backtest", slug: "backtest", icon: FlaskConical, question: "" },
};

const PAGES: Page[] = [
  { id: "build", label: "Build", icon: PencilRuler, question: "", features: [], slug: "build" },
  { id: "test", label: "Test", icon: FlaskConical, question: "", features: ["st01"] },
];

type RawFeature = { id: string; name: string; inputs: InputSpec[]; outputs: { key: string; label: string; source: "tables" | "charts"; render: string }[] };
const VIEW: Record<string, string> = { table: "dataTable", lineChart: "lineChart" };
/** The open draft and the version travel with the strategy picker, not as form fields. */
const HIDDEN = new Set(["spec", "version"]);

function toSpec(f: RawFeature): FeatureSpec {
  const outputs: OutputSpec[] = f.outputs.map((o) => ({ key: o.key, title: o.label, source: o.source, render: VIEW[o.render] ?? "dataTable" }));
  return { id: f.id, name: f.name, description: "", inputs: f.inputs.filter((i) => !HIDDEN.has(i.key)), outputs };
}

const sign = (v: number, d = 0) => `${v > 0 ? "+" : ""}${pct(v, d)}`;

/** Backtest hero: net return against the benchmark, both curves full width, ending at the hold-out boundary. */
function backtestHero(r: FeatureResult): HeroSpec | null {
  const m = r.meta as StudioMeta;
  const rows = (r.charts.equity_curve ?? []) as { strategy: number; benchmark: number | null }[];
  if (rows.length < 2 || !isNum(m.total_return)) return null;
  const step = Math.max(1, Math.floor(rows.length / 320));
  const thin = <T,>(v: T[]) => v.filter((_, i) => i % step === 0 || i === v.length - 1);
  const bench = rows.map((x) => x.benchmark).filter(isNum);
  const br = m.metrics.benchmark_total_return;
  return {
    figure: sign(m.total_return), tone: isNum(br) ? (m.total_return >= br ? "up" : "down") : m.total_return >= 0 ? "up" : "down",
    versus: isNum(br) && m.benchmark ? `${m.benchmark} ${sign(br)}` : undefined,
    line: [`${m.years.toFixed(1)} years`, isNum(m.metrics.sharpe) ? `Sharpe ${m.metrics.sharpe.toFixed(2)}` : null, isNum(m.metrics.max_drawdown) ? `worst drawdown ${pct(m.metrics.max_drawdown, 0)}` : null,
      `${m.metrics.trades} trades${m.few_trades ? " (few)" : ""}`].filter(Boolean).join(" · "),
    lines: [{ label: "Net", values: thin(rows.map((x) => x.strategy)), color: "var(--accent)" }, ...(bench.length > 1 ? [{ label: m.benchmark ?? "Benchmark", values: thin(bench), color: "var(--text-3)" }] : [])],
  };
}

const BV = group(() => import("./views/BacktestViews") as Promise<Record<string, unknown>>);
const TS = group(() => import("@/modules/screener/test/TearSheet") as Promise<Record<string, unknown>>);
registerViews({ stEquity: BV.Equity, stStartDates: BV.StartDates, stSurvivorship: BV.Survivorship, stFillCheck: BV.FillCheck, stCarriedBy: BV.CarriedBy, stTradeShape: BV.TradeShape, stTradeReturns: BV.TradeReturns,
  stHoldTime: BV.HoldTime, stCrises: BV.Crises, stCosts: BV.Costs, stCapacity: BV.Capacity, stExposure: BV.Exposure, stDrawdowns: BV.Drawdowns, stStability: BV.Stability,
  monthlyHeatmap: TS.MonthlyHeatmap, yearlyVsBenchmark: TS.YearlyVsBenchmark, underwater: TS.Underwater },
  ["stEquity", "stStartDates", "stSurvivorship", "stFillCheck", "stTradeShape", "stCrises", "stExposure", "stStability"]);
registerAlternates({ stTradeShape: [{ label: "Returns", view: "stTradeReturns" }, { label: "Hold time", view: "stHoldTime" }], stCarriedBy: [{ label: "Table", view: "dataTable" }], stCrises: [{ label: "Table", view: "dataTable" }],
  stStartDates: [{ label: "Table", view: "dataTable" }], stDrawdowns: [{ label: "Table", view: "dataTable" }] });

const TRADE_COLUMNS = ["symbol", "side", "entry_date", "exit_date", "entry", "exit", "shares", "pnl", "return", "bars", "mae", "mfe", "exit_reason", "costs", "signal_date"];
const BuildPage = dynamic<{ features: FeatureSpec[]; id?: string }>(() => import("./build/BuildPage"), { ssr: false });
const HomePage = dynamic<{ features: FeatureSpec[]; runs: RunRecord[] }>(() => import("./home/StudioHome"), { ssr: false });

export const STUDIO_LAB: LabConfig = {
  id: "studio",
  title: "Studio",
  homeLabel: "Home",
  root: "/studio",
  base: STUDIO_BASE,
  catalog: CATALOG,
  pages: PAGES,
  layouts: {
    st01: {
      hero: backtestHero,
      sections: [
        { id: "overview", label: "Overview", items: [
          { keys: ["equity_curve"], span: 12, view: "stEquity", title: "Equity and drawdown" },
          { keys: ["start_dates"], span: 6, view: "stStartDates", title: "Start dates" },
          { keys: ["equity_curve"], span: 6, view: "stSurvivorship", title: "Survivorship" },
          { keys: ["equity_curve"], span: 12, view: "stFillCheck", title: "Fill check" },
        ] },
        { id: "trades", label: "Trades", items: [
          { keys: ["carried_by"], span: 5, view: "stCarriedBy", title: "Carried by" },
          { keys: ["trades"], span: 7, view: "stTradeShape", title: "Trade shape", toggle: "Excursion" },
          { keys: ["trades"], span: 12, view: "dataTable", title: "Trades", opts: { max: 100000, maxHeight: 560, columns: TRADE_COLUMNS, viewKey: "studio-trades" } },
        ] },
        { id: "returns", label: "Returns", items: [
          { keys: ["equity_curve"], span: 8, view: "monthlyHeatmap", title: "Calendar" },
          { keys: ["equity_curve"], span: 4, view: "yearlyVsBenchmark", title: "Each year" },
          { keys: ["crises"], span: 12, view: "stCrises", title: "Crisis periods" },
        ] },
        { id: "risk", label: "Risk", items: [
          { keys: ["drawdowns"], span: 7, view: "stDrawdowns", title: "Drawdowns" },
          { keys: ["rolling"], span: 5, view: "stStability", title: "Stability" },
          { keys: ["equity_curve"], span: 4, view: "stCosts", title: "Costs" },
          { keys: ["trades"], span: 4, view: "stCapacity", title: "Capacity" },
          { keys: ["exposure"], span: 4, view: "stExposure", title: "Exposure" },
        ] },
      ],
      drop: ["cost_ladder", "my_limits", "limits", "statistics", "per_name"],
    },
  },
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => f.id in CATALOG).map(toSpec),
  submit: (featureId, payload) => ({ path: `/feature/${featureId}/jobs`, body: { payload } }),
  signal: false,
  contextBar: StudioContext,
  widgets: { strategy_id: StrategyPicker },
  takeaway: (_feature, key, view, result) => lead(view ?? key, result),
  runLabel: () => "Run backtest",
  defaultUniverse: "Top names by liquidity",
  specials: { build: BuildPage },
  overview: { home: HomePage, intro: "", stages: [] },
};
