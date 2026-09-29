"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "scenario-waterfall",
    "title": "Scenario PnL Waterfall",
    "source": "charts",
    "dataKey": "scenario_waterfall",
    "chartType": "waterfall",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "factor-returns-under-scenario",
    "title": "Factor Returns Under Scenario",
    "source": "tables",
    "dataKey": "factor_shocks",
    "chartType": "bar",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "historical-analog",
    "title": "Historical Analog",
    "source": "tables",
    "dataKey": "historical_analog",
    "chartType": "table"
  },
  {
    "id": "reverse-stress",
    "title": "Reverse Stress Closed Form",
    "source": "tables",
    "dataKey": "reverse_stress",
    "chartType": "table",
    "config": {
      "alert": true
    }
  },
  {
    "id": "contagion-irf",
    "title": "VAR Contagion Impulse Response",
    "source": "charts",
    "dataKey": "contagion_irf",
    "chartType": "bar"
  },
  {
    "id": "multi-scenario-comparison",
    "title": "Multi Scenario Comparison",
    "source": "tables",
    "dataKey": "multi_scenario_comparison",
    "fallbackKeys": [
      "multi_scenario"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  }
];

export default function Feature11Page() {
  return <CustomFeaturePage featureId="11" sections={sections} />;
}
