"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "scoreboard",
    "title": "GARCH Model Scoreboard",
    "source": "tables",
    "dataKey": "model_scoreboard",
    "chartType": "garchScoreboard",
    "rank": "primary",
    "fallbackKeys": [
      "garch_scoreboard"
    ],
    "config": {}
  },
  {
    "id": "qq-plot",
    "title": "Residual Q-Q Adequacy Plot",
    "source": "charts",
    "dataKey": "qq_plot",
    "chartType": "qqPlot",
    "rank": "supporting",
    "fallbackKeys": [
      "standardized_residual_qq",
      "garch_qq_plot"
    ],
    "config": {}
  },
  {
    "id": "term-structure",
    "title": "GARCH-Implied Term Structure",
    "source": "charts",
    "dataKey": "garch_term_structure",
    "chartType": "termStructure",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "news-impact",
    "title": "News Impact Curve",
    "source": "charts",
    "dataKey": "news_impact_curve",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "var-series",
    "title": "Conditional VaR Time Series",
    "source": "charts",
    "dataKey": "conditional_var_timeseries",
    "chartType": "varChart",
    "rank": "supporting",
    "fallbackKeys": [
      "conditional_var_time_series"
    ],
    "config": {}
  },
  {
    "id": "pit-test",
    "title": "PIT Density Test",
    "source": "charts",
    "dataKey": "pit_histogram",
    "chartType": "bar",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "vol-state",
    "title": "Volatility State Gauge",
    "source": "summary",
    "dataKey": "volatility_state_gauge",
    "chartType": "volGauge",
    "rank": "supporting",
    "fallbackKeys": [
      "summary_cards"
    ],
    "config": {}
  },
  {
    "id": "realized-garch",
    "title": "Realized-GARCH Variance",
    "source": "charts",
    "dataKey": "realized_garch_variance_series",
    "chartType": "area",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "nic-ribbon",
    "title": "Regime-Conditional NIC Ribbon",
    "source": "charts",
    "dataKey": "regime_conditional_nic_ribbon",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "nyblom",
    "title": "Nyblom Parameter Stability",
    "source": "tables",
    "dataKey": "nyblom_parameter_stability",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "aparch-delta",
    "title": "APARCH Delta Benchmark",
    "source": "tables",
    "dataKey": "aparch_delta_benchmark",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "var-backtests",
    "title": "VaR Backtests",
    "source": "tables",
    "dataKey": "var_backtests",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "surface",
    "title": "Synthetic Vol Surface",
    "source": "charts",
    "dataKey": "synthetic_vol_surface",
    "chartType": "surfaceGrid",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature02Page() {
  return <VolatilityV2Workbench featureId="02" sections={sections} />;
}
