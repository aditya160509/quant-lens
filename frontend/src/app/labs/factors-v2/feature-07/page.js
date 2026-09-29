"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "equity-curve",
    "title": "Gross Net Benchmark Equity Curve",
    "source": "charts",
    "dataKey": "equity_curve",
    "chartType": "backtestSplit",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#2F81F7",
        "#8B949E"
      ],
      "fillOpacity": 0.16
    }
  },
  {
    "id": "drawdown",
    "title": "Drawdown Surface",
    "source": "charts",
    "dataKey": "drawdown",
    "chartType": "area",
    "defaultSelected": false,
    "config": {
      "seriesColors": [
        "#F85149"
      ],
      "yDomain": [
        "auto",
        0
      ]
    }
  },
  {
    "id": "statistics-table",
    "title": "Backtest Statistics",
    "source": "tables",
    "dataKey": "statistics_table",
    "fallbackKeys": [
      "statistics"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "quintile-monotonicity",
    "title": "Decile / Quintile Monotonicity",
    "source": "charts",
    "dataKey": "decile_monotonicity",
    "fallbackKeys": [
      "quintile_monotonicity"
    ],
    "chartType": "decileReturn",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#8B949E",
        "#D29922",
        "#F85149"
      ]
    }
  },
  {
    "id": "transaction-cost-decomposition",
    "title": "Transaction Cost Decomposition",
    "source": "charts",
    "dataKey": "transaction_cost_decomposition",
    "fallbackKeys": [
      "transaction_costs"
    ],
    "chartType": "stackedBar",
    "config": {
      "seriesColors": [
        "#D29922",
        "#F85149",
        "#A371F7"
      ],
      "stacked": true
    }
  },
  {
    "id": "adv-capacity-curve",
    "title": "ADV Capacity Curve",
    "source": "charts",
    "dataKey": "adv_capacity_curve",
    "chartType": "advCapacityCurve",
    "rank": "supporting"
  },
  {
    "id": "monte-carlo-bands",
    "title": "Monte Carlo Confidence Bands",
    "source": "charts",
    "dataKey": "monte_carlo_bands",
    "chartType": "line",
    "config": {
      "seriesColors": [
        "#8B949E",
        "#2F81F7",
        "#8B949E"
      ]
    }
  }
];

export default function Feature07Page() {
  return <CustomFeaturePage featureId="07" sections={sections} />;
}
