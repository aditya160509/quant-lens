"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "vol-shock",
    "title": "Vol Shock Bar Chart",
    "source": "charts",
    "dataKey": "vol_shock_bar_chart",
    "chartType": "bar",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "waterfall",
    "title": "Portfolio P&L Attribution",
    "source": "charts",
    "dataKey": "portfolio_pnl_attribution_waterfall",
    "chartType": "waterfall",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "reverse",
    "title": "Reverse Stress Scenario",
    "source": "tables",
    "dataKey": "reverse_stress_scenario",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "analog",
    "title": "Historical Analog Comparison",
    "source": "tables",
    "dataKey": "historical_analog_comparison",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "irf",
    "title": "Contagion Impulse Response",
    "source": "charts",
    "dataKey": "contagion_impulse_response",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "irf-bands",
    "title": "IRF Confidence Bands",
    "source": "charts",
    "dataKey": "contagion_impulse_response_bands",
    "chartType": "forecastBands",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "multi",
    "title": "Multi-Scenario Comparison",
    "source": "tables",
    "dataKey": "multi_scenario_comparison",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "var-cvar",
    "title": "Stress VaR/CVaR",
    "source": "tables",
    "dataKey": "stress_var_cvar",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "glasso",
    "title": "Graphical LASSO Analog",
    "source": "tables",
    "dataKey": "historical_analog_glasso",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "copula",
    "title": "Reverse Stress Copula",
    "source": "tables",
    "dataKey": "reverse_stress_copula",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "adversarial",
    "title": "Adversarial Scenario",
    "source": "tables",
    "dataKey": "adversarial_scenario",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "distribution",
    "title": "Stress Distribution",
    "source": "charts",
    "dataKey": "stress_distribution",
    "chartType": "stressDistribution",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature08Page() {
  return <VolatilityV2Workbench featureId="08" sections={sections} />;
}
