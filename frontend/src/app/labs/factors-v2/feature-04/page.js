"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "regime-probabilities",
    "title": "Composite Regime Probabilities",
    "source": "charts",
    "dataKey": "regime_probabilities",
    "fallbackKeys": [
      "composite_probability"
    ],
    "chartType": "stackedArea",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#D29922",
        "#F85149",
        "#A371F7"
      ],
      "yDomain": [
        0,
        1
      ],
      "stacked": true
    }
  },
  {
    "id": "current-regime",
    "title": "Current Regime Probability Stack",
    "source": "charts",
    "dataKey": "current_regime_trend",
    "fallbackKeys": [
      "current_regime",
      "current_regime_probabilities"
    ],
    "chartType": "regimeTrend"
  },
  {
    "id": "conditional-factor-returns",
    "title": "Conditional Factor Returns",
    "source": "tables",
    "dataKey": "conditional_returns",
    "chartType": "heatmap"
  },
  {
    "id": "factor-sharpe-by-regime",
    "title": "Factor Sharpe By Regime",
    "source": "charts",
    "dataKey": "factor_sharpe_by_regime",
    "chartType": "bar",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#D29922",
        "#F85149",
        "#A371F7"
      ]
    }
  },
  {
    "id": "regime-sensitivity",
    "title": "Regime Sensitivity Table",
    "source": "tables",
    "dataKey": "regime_sensitivity",
    "chartType": "table",
    "rank": "supporting",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "transition-matrix",
    "title": "Regime Transition Matrix",
    "source": "tables",
    "dataKey": "transition_matrix",
    "chartType": "heatmap",
    "config": {
      "colorByIntensity": true
    }
  },
  {
    "id": "timing-regression",
    "title": "Timing Regression Diagnostics",
    "source": "tables",
    "dataKey": "timing_regression",
    "fallbackKeys": [
      "factor_timing_regression"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true,
      "flagAbsTstat2": true
    }
  }
];

export default function Feature04Page() {
  return <CustomFeaturePage featureId="04" sections={sections} />;
}
