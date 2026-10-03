import type { ComponentType } from "react";
import * as P from "./plots";
import "./views.css";
import { AttributionBars, ByChoice, DivergingView, RobustnessMatrix, withSwitch, SpecificationCurveView, StabilityView } from "./robustness";
import * as T from "./tables";
import type { ViewProps } from "./types";

/**
 * Every view by name. Layout items pick a view explicitly; otherwise the backend render hint
 * selects one, and anything unknown falls back to the sortable table so no output is ever hidden.
 */
export const VIEWS: Record<string, ComponentType<ViewProps>> = {
  // tables
  dataTable: T.DataTable, keyValue: T.Facts, facts: T.Facts, testCard: T.TestsTable, tests: T.TestsTable, regressionTable: T.RegressionTable,
  tstats: T.TStatTable, reportCard: T.ReportCard, scorecard: T.Scorecard, publicationTable: T.PublicationTable, latex: T.Latex, csv: T.CsvExport,
  pdf: T.PdfExport, summaryLine: T.Prose, verdict: T.Prose, explanation: T.Prose, prose: T.Prose,
  // robustness
  specificationCurve: SpecificationCurveView, decisionLedger: T.DataTable, barList: withSwitch(DivergingView, "Diverging", "Bars", AttributionBars), diverging: DivergingView, byChoice: ByChoice, robustnessMatrix: RobustnessMatrix, boxSummary: StabilityView, stability: StabilityView,
  // time series
  lineChart: P.LineView, coefficientPath: P.CoefficientPath, growth: P.GrowthView, cumulative: P.CumulativeView, regimeRibbon: P.RegimeTimeline,
  breakScan: P.BreakScan, decayCurve: P.DecayCurve, sharpeDecay: P.SharpeDecay, syntheticPath: P.SyntheticPath, gapPlot: P.GapWithPlacebos,
  placeboPaths: P.GapWithPlacebos, conformalBand: P.ConformalBand,
  // bars and distributions
  portfolioLadder: P.PortfolioLadder, bars: P.BarsView, barCompare: P.OosCompare, correlogram: P.Correlogram, placeboRanking: P.PlaceboRanking,
  density: P.DensityView, donorWeights: P.DonorWeights, nullDistribution: P.NullDistributionView, distribution: P.HistogramView, power: P.PowerBars,
  // scatter
  scatter: P.ScatterView, qqPlot: P.QQView, partialResiduals: P.PartialResiduals, baconScatter: P.BaconScatter, rdPlot: P.RdPlot, zooScatter: P.ZooScatter, arCurve: P.ArCurve,
  // estimates with intervals
  eventStudy: P.EventStudy, placeboCutoffs: P.SensitivityView, quantile: P.QuantileView, forestPlot: P.ForestView, lovePlot: P.LovePlot, spanning: P.SpanningBetas,
  // matrices and gauges
  heatmap: P.DoubleSort, correlationMatrix: P.CorrelationMap, vitalityGauge: P.VitalityGauge, hlzRuler: P.HlzRuler, firstStage: P.FirstStage,
};

/** Views that draw an SVG chart, so their card offers SVG and PNG export. */
export const CHART_VIEWS = new Set([
  "specificationCurve", "byChoice", "diverging", "barList", "lineChart", "coefficientPath", "growth", "cumulative", "regimeRibbon", "breakScan", "decayCurve", "sharpeDecay",
  "syntheticPath", "gapPlot", "placeboPaths", "conformalBand", "portfolioLadder", "bars", "barCompare", "correlogram", "placeboRanking", "density",
  "donorWeights", "nullDistribution", "distribution", "power", "scatter", "qqPlot", "partialResiduals", "baconScatter", "rdPlot", "zooScatter", "arCurve",
  "eventStudy", "placeboCutoffs", "quantile", "forestPlot", "lovePlot", "spanning",
]);

export function viewFor(name: string): ComponentType<ViewProps> {
  return VIEWS[name] ?? T.DataTable;
}
