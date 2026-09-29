"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "efficient-frontier",
    "title": "Efficient Frontier",
    "source": "charts",
    "dataKey": "efficient_frontier",
    "chartType": "scatter",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#3FB950",
        "#D29922"
      ]
    }
  },
  {
    "id": "factor-allocation",
    "title": "Optimized Factor Allocation",
    "source": "charts",
    "dataKey": "factor_allocation",
    "fallbackKeys": [
      "optimal_weights",
      "weights"
    ],
    "chartType": "horizontalBar",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "risk-budget",
    "title": "Risk Budget",
    "source": "charts",
    "dataKey": "risk_budget",
    "chartType": "pie"
  },
  {
    "id": "constraint-binding",
    "title": "Constraint Binding Table",
    "source": "tables",
    "dataKey": "constraint_binding",
    "chartType": "table"
  },
  {
    "id": "robust-vs-standard",
    "title": "Robust Versus Standard Weights",
    "source": "charts",
    "dataKey": "robust_vs_standard",
    "chartType": "groupedHorizontalBar",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#D29922"
      ]
    }
  },
  {
    "id": "fap-diagnostic",
    "title": "Factor Alignment Problem Diagnostic",
    "source": "tables",
    "dataKey": "fap_diagnostic",
    "chartType": "table",
    "config": {
      "alert": true
    }
  }
];

export default function Feature10Page() {
  return <CustomFeaturePage featureId="10" sections={sections} />;
}
