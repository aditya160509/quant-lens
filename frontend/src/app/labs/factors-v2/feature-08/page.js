"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "correlation-heatmap",
    "title": "Factor Correlation Heatmap",
    "source": "charts",
    "dataKey": "correlation_heatmap",
    "fallbackKeys": [
      "correlation_matrix"
    ],
    "chartType": "hierarchicalHeatmap",
    "config": {
      "palette": "diverging",
      "defaultSort": "cluster"
    }
  },
  {
    "id": "factor-volatility",
    "title": "Factor Volatility Forecast",
    "source": "charts",
    "dataKey": "factor_volatility",
    "chartType": "bar"
  },
  {
    "id": "normal-vs-crisis",
    "title": "Normal Versus Crisis Covariance",
    "source": "charts",
    "dataKey": "normal_vs_crisis",
    "chartType": "normalVsCrisis"
  },
  {
    "id": "crisis-preset-comparison",
    "title": "Crisis Preset Comparison",
    "source": "charts",
    "dataKey": "crisis_preset_comparison",
    "chartType": "crisisPresetComparison",
    "rank": "supporting"
  },
  {
    "id": "eigenvalue-decomposition",
    "title": "Eigenvalue Decomposition",
    "source": "charts",
    "dataKey": "eigenvalue_decomposition",
    "fallbackKeys": [
      "eigenvalues"
    ],
    "chartType": "bar",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#D29922"
      ]
    }
  },
  {
    "id": "rolling-correlation",
    "title": "Rolling Correlation",
    "source": "charts",
    "dataKey": "rolling_pair_correlation",
    "chartType": "line"
  },
  {
    "id": "portfolio-risk-decomposition",
    "title": "Portfolio Risk Decomposition",
    "source": "charts",
    "dataKey": "portfolio_risk_decomposition",
    "chartType": "heatmap"
  }
];

export default function Feature08Page() {
  return <CustomFeaturePage featureId="08" sections={sections} />;
}
