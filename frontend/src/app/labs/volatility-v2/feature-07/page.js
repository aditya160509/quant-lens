"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "corr",
    "title": "Correlation Matrix Heatmap",
    "source": "charts",
    "dataKey": "correlation_heatmap",
    "chartType": "heatmap",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {
      "diverging": true
    }
  },
  {
    "id": "corr-movie",
    "title": "Rolling Correlation Mini-Movie",
    "source": "charts",
    "dataKey": "rolling_corr_animation",
    "chartType": "corrAnimation",
    "rank": "supporting",
    "fallbackKeys": [
      "rolling_correlation_matrices"
    ],
    "config": {}
  },
  {
    "id": "normal-crisis",
    "title": "Normal vs Crisis Correlation",
    "source": "charts",
    "dataKey": "normal_vs_crisis_correlation",
    "chartType": "tripleHeatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "dcc-ts",
    "title": "DCC Time Series",
    "source": "charts",
    "dataKey": "dcc_time_series",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "eigen",
    "title": "Eigenvalue Decomposition",
    "source": "charts",
    "dataKey": "eigenvalue_decomposition",
    "chartType": "composedBarLine",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "condition",
    "title": "Condition Number History",
    "source": "charts",
    "dataKey": "condition_number_history",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "risk-attr",
    "title": "Portfolio Risk Attribution",
    "source": "tables",
    "dataKey": "portfolio_risk_attribution",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "min-var",
    "title": "Minimum Variance Portfolio",
    "source": "tables",
    "dataKey": "minimum_variance_portfolio",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "comparison",
    "title": "Sample/EWMA/LW/DCC Comparison",
    "source": "tables",
    "dataKey": "sample_ewma_lw_dcc_comparison",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "midas",
    "title": "DCC-MIDAS Long-Run Correlation",
    "source": "charts",
    "dataKey": "dcc_midas_long_run_correlation",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {
      "diverging": true
    }
  },
  {
    "id": "prob-crisis",
    "title": "Probability-Weighted Crisis Correlation",
    "source": "charts",
    "dataKey": "probability_weighted_crisis_correlation",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {
      "diverging": true
    }
  },
  {
    "id": "torsion",
    "title": "Minimum Torsion Attribution",
    "source": "tables",
    "dataKey": "minimum_torsion_risk_attribution",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "fisher",
    "title": "Fisher Z Crisis Amplification",
    "source": "tables",
    "dataKey": "fisher_z_crisis_amplification",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "pairwise-cov",
    "title": "Pairwise Covariance Contribution",
    "source": "charts",
    "dataKey": "pairwise_covariance_contribution",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature07Page() {
  return <VolatilityV2Workbench featureId="07" sections={sections} />;
}
