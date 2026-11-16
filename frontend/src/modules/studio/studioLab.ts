import dynamic from "next/dynamic";
import { Blend, CandlestickChart, FlaskConical, PencilRuler, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { STUDIO_BASE } from "./base";
import { StudioContext, StrategiesPicker, StrategyPicker } from "./RunHeader";
import { isNum, pct } from "@/modules/research/format";
import type { HeroSpec } from "@/modules/research/Hero";
import { group, registerAlternates, registerViews } from "@/modules/research/outputs/registry";
import type { FeatureMeta, LabConfig, Page } from "@/modules/research/lab";
import type { FeatureResult, FeatureSpec, InputSpec, OutputSpec, RunRecord } from "@/modules/research/types";
import type { StudioMeta } from "./types";
import { lead } from "./leads";

const CATALOG: Record<string, FeatureMeta> = {
  st01: { name: "Backtest", slug: "backtest", icon: FlaskConical, question: "" },
  st02: { name: "Optimise", slug: "optimise", icon: SlidersHorizontal, question: "" },
  st03: { name: "Validate", slug: "validate", icon: ShieldCheck, question: "" },
  st04: { name: "Portfolio", slug: "portfolio", icon: Blend, question: "" },
};

const PAGES: Page[] = [
  { id: "build", label: "Build", icon: PencilRuler, question: "", features: [], slug: "build" },
  { id: "test", label: "Test", icon: FlaskConical, question: "", features: ["st01", "st02", "st03"] },
  { id: "portfolio", label: "Portfolio", icon: Blend, question: "", features: ["st04"] },
  { id: "chart", label: "Chart", icon: CandlestickChart, question: "", features: [], slug: "chart" },
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

/** Validate hero: the grade and its one reason. */
function validateHero(r: FeatureResult): HeroSpec | null {
  const g = (r.meta as { grade?: { grade: string; reason: string; cap: string | null } }).grade;
  if (!g) return null;
  return { figure: g.grade, tone: g.grade <= "B" ? "up" : g.grade === "C" ? "warn" : "down", versus: g.cap ? `capped at ${g.cap}` : undefined, line: g.reason };
}

/** Portfolio hero: the combined line against each member. */
function portfolioHero(r: FeatureResult): HeroSpec | null {
  const m = r.meta as { headline?: string; names?: string[]; total_return?: number };
  const rows = (r.charts.combined ?? []) as Record<string, number>[];
  if (rows.length < 2 || !m.names) return null;
  const step = Math.max(1, Math.floor(rows.length / 320));
  const thin = (k: string) => rows.filter((_, i) => i % step === 0 || i === rows.length - 1).map((x) => x[k]);
  return { figure: sign(m.total_return ?? 0), tone: (m.total_return ?? 0) >= 0 ? "up" : "down", line: m.headline,
    lines: [{ label: "Combined", values: thin("combined"), color: "var(--accent)" }, ...m.names.map((n, i) => ({ label: n, values: thin(n), color: `var(--c${(i % 6) + 2})` }))] };
}

/** Optimise hero: the plateau's score, not the best cell's. */
function optimiseHero(r: FeatureResult): HeroSpec | null {
  const m = r.meta as { headline?: string; plateau?: { status: string; centre_score?: number; best_score?: number }; objective_label?: string; cells?: number };
  if (!m.plateau) return null;
  const v = m.plateau.status === "plateau" ? m.plateau.centre_score : m.plateau.best_score;
  return { figure: isNum(v) ? v.toFixed(2) : "—", tone: m.plateau.status === "spike" ? "warn" : null, versus: m.plateau.status === "spike" ? "spike only" : `${m.objective_label} on the plateau`,
    line: `${m.cells} cells · ${m.headline ?? ""}` };
}

const BV = group(() => import("./views/BacktestViews") as Promise<Record<string, unknown>>);
const OV = group(() => import("./views/OptimiseViews") as Promise<Record<string, unknown>>);
registerViews({ stParamMap: OV.ParamMap, stImportance: OV.Importance, stPareto: OV.Pareto }, ["stParamMap", "stPareto"]);
const VV = group(() => import("./views/ValidateViews") as Promise<Record<string, unknown>>);
registerViews({ stTiles: VV.Tiles, stScorecard: VV.Scorecard, stStitched: VV.Stitched, stVsRandom: VV.VsRandom, stLottery: VV.Lottery, stHoldout: VV.Holdout, stCertificate: VV.Certificate }, ["stTiles", "stStitched"]);
const TS = group(() => import("@/modules/screener/test/TearSheet") as Promise<Record<string, unknown>>);
registerViews({ stEquity: BV.Equity, stStartDates: BV.StartDates, stSurvivorship: BV.Survivorship, stFillCheck: BV.FillCheck, stCarriedBy: BV.CarriedBy, stTradeShape: BV.TradeShape, stTradeReturns: BV.TradeReturns,
  stHoldTime: BV.HoldTime, stCrises: BV.Crises, stCosts: BV.Costs, stCapacity: BV.Capacity, stExposure: BV.Exposure, stDrawdowns: BV.Drawdowns, stStability: BV.Stability, stByRegime: BV.ByRegime, stSeasonality: BV.Seasonality, stPerName: BV.PerName, stContributors: BV.Contributors,
  stTradeFan: BV.TradeFan, stOnChart: BV.OnChart, stRuin: BV.Ruin, stStreaks: BV.Streaks,
  monthlyHeatmap: TS.MonthlyHeatmap, yearlyVsBenchmark: TS.YearlyVsBenchmark, underwater: TS.Underwater },
  ["stEquity", "stStartDates", "stSurvivorship", "stFillCheck", "stTradeShape", "stCrises", "stExposure", "stStability"]);
registerAlternates({ stTradeShape: [{ label: "Returns", view: "stTradeReturns" }, { label: "Hold time", view: "stHoldTime" }], stCarriedBy: [{ label: "Table", view: "dataTable" }], stCrises: [{ label: "Table", view: "dataTable" }],
  stStartDates: [{ label: "Table", view: "dataTable" }], stDrawdowns: [{ label: "Table", view: "dataTable" }] });

const TRADE_COLUMNS = ["symbol", "side", "entry_date", "exit_date", "entry", "exit", "shares", "pnl", "return", "bars", "mae", "mfe", "exit_reason", "costs", "signal_date"];
const BuildPage = dynamic<{ features: FeatureSpec[]; id?: string }>(() => import("./build/BuildPage"), { ssr: false });
const ChartPage = dynamic<{ features: FeatureSpec[]; id?: string }>(() => import("./chart/ChartPage"), { ssr: false });
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
          { keys: ["per_name"], span: 12, view: "stOnChart", title: "Trades on price" },
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
        { id: "when", label: "When", items: [
          { keys: ["by_regime"], span: 7, view: "stByRegime", title: "By regime" },
          { keys: ["seasonality"], span: 5, view: "stSeasonality", title: "Seasonality" },
          { keys: ["by_regime"], span: 12, view: "dataTable", title: "Regimes" },
        ] },
        { id: "names", label: "Names", items: [
          { keys: ["per_name"], span: 12, view: "stContributors", title: "Contributors" },
          { keys: ["per_name"], span: 12, view: "stPerName", title: "Per-name results" },
        ] },
        { id: "paths", label: "Paths", items: [
          { keys: ["trade_mc"], span: 12, view: "stTradeFan", title: "Trade Monte Carlo" },
          { keys: ["ruin"], span: 6, view: "stRuin", title: "Ruin" },
          { keys: ["streaks"], span: 6, view: "stStreaks", title: "Losing streaks" },
        ] },
      ],
      drop: ["cost_ladder", "my_limits", "limits", "statistics"],
    },
    st03: {
      hero: validateHero,
      sections: [
        { id: "verdict", label: "Verdict", items: [
          { keys: ["tiles"], span: 12, view: "stTiles", title: "Tests" },
          { keys: ["verdict"], span: 12, view: "stScorecard", title: "Scorecard" },
        ] },
        { id: "wf", label: "Walk-forward", items: [
          { keys: ["walk_forward"], span: 12, view: "stStitched", title: "Stitched out-of-sample" },
          { keys: ["windows"], span: 12, view: "dataTable", title: "Windows" },
        ] },
        { id: "robust", label: "Robustness", items: [
          { keys: ["vs_random"], span: 7, view: "stVsRandom", title: "Vs random entries" },
          { keys: ["execution"], span: 5, view: "dataTable", title: "Execution" },
          { keys: ["parameters"], span: 12, view: "dataTable", title: "Nearby settings" },
          { keys: ["noise"], span: 6, view: "dataTable", title: "Price noise" },
          { keys: ["mcpt"], span: 6, view: "dataTable", title: "Permutation" },
        ] },
        { id: "luck", label: "Luck", items: [
          { keys: ["lottery"], span: 7, view: "stLottery", title: "Luck lottery" },
          { keys: ["luck"], span: 5, view: "dataTable", title: "Luck measures" },
        ] },
        { id: "holdout", label: "Hold-out", items: [{ keys: ["tiles"], span: 12, view: "stHoldout", title: "Sealed hold-out" }] },
        { id: "certificate", label: "Certificate", items: [{ keys: ["tiles"], span: 12, view: "stCertificate", title: "Certificate" }] },
      ],
    },
    st04: {
      hero: portfolioHero,
      sections: [
        { id: "together", label: "Together", items: [
          { keys: ["combined"], span: 12, view: "lineChart", title: "Combined vs each" },
          { keys: ["methods"], span: 6, view: "dataTable", title: "Allocation methods" },
          { keys: ["weights"], span: 6, view: "dataTable", title: "Weights" },
        ] },
        { id: "relations", label: "Correlation", items: [
          { keys: ["correlation"], span: 7, view: "dataTable", title: "Correlation" },
          { keys: ["overlap"], span: 5, view: "dataTable", title: "Overlap" },
          { keys: ["marginal"], span: 6, view: "dataTable", title: "Marginal contribution" },
          { keys: ["members"], span: 6, view: "dataTable", title: "Members" },
        ] },
      ],
    },
    st02: {
      hero: optimiseHero,
      sections: [
        { id: "map", label: "Map", items: [
          { keys: ["heatmap"], span: 12, view: "stParamMap", title: "Parameter map" },
          { keys: ["importance"], span: 5, view: "stImportance", title: "What matters" },
          { keys: ["pareto"], span: 7, view: "stPareto", title: "Trade-offs" },
        ] },
        { id: "sets", label: "Top sets", items: [
          { keys: ["top_sets"], span: 12, view: "dataTable", title: "Top 10 sets" },
          { keys: ["cells"], span: 12, view: "dataTable", title: "All cells", opts: { max: 100000, maxHeight: 560 } },
        ] },
      ],
    },
  },
  manifest: (raw) => (raw as { features: RawFeature[] }).features.filter((f) => f.id in CATALOG).map(toSpec),
  submit: (featureId, payload) => {
    // A run with no strategy picked uses the last one used anywhere in Studio (the picker lives in the closed inspector).
    let sid = payload.strategy_id;
    if (!sid) { try { sid = localStorage.getItem("studio:strategy"); } catch { /* storage blocked */ } }
    return { path: `/feature/${featureId}/jobs`, body: { payload: { ...payload, strategy_id: sid || undefined } } };
  },
  signal: false,
  contextBar: StudioContext,
  widgets: { strategy_id: StrategyPicker, strategy_ids: StrategiesPicker, switch_off: StrategyPicker },
  takeaway: (_feature, key, view, result) => lead(view ?? key, result),
  runLabel: (f) => ({ st02: "Run sweep", st03: "Run validation", st04: "Combine" } as Record<string, string>)[f] ?? "Run backtest",
  defaultUniverse: "Top names by liquidity",
  specials: { build: BuildPage, chart: ChartPage },
  overview: { home: HomePage, intro: "", stages: [] },
};
