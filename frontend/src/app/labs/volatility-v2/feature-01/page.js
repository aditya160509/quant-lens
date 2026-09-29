"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "estimator-comparison",
    "title": "Five-Estimator Comparison",
    "source": "charts",
    "dataKey": "five_estimator_comparison",
    "chartType": "estimatorComparison",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "calendar",
    "title": "Volatility Calendar Heatmap",
    "source": "charts",
    "dataKey": "vol_calendar",
    "chartType": "calendarHeatmap",
    "rank": "supporting",
    "fallbackKeys": [
      "annualized_vol_panel",
      "five_estimator_comparison"
    ],
    "config": {}
  },
  {
    "id": "ridge",
    "title": "Rolling Vol Distribution Ridge",
    "source": "charts",
    "dataKey": "vol_ridge",
    "chartType": "ridgePlot",
    "rank": "supporting",
    "fallbackKeys": [
      "annualized_vol_panel",
      "five_estimator_comparison"
    ],
    "config": {}
  },
  {
    "id": "cone",
    "title": "Realized Volatility Cone",
    "source": "charts",
    "dataKey": "volatility_cone",
    "chartType": "volCone",
    "rank": "supporting",
    "fallbackKeys": [
      "multi_window_estimator_panel",
      "multi_window_estimator_table"
    ],
    "config": {}
  },
  {
    "id": "signature",
    "title": "Volatility Signature Plot",
    "source": "charts",
    "dataKey": "vol_signature",
    "chartType": "signaturePlot",
    "rank": "supporting",
    "fallbackKeys": [
      "multi_window_estimator_panel",
      "five_estimator_comparison"
    ],
    "config": {}
  },
  {
    "id": "agreement",
    "title": "Estimator Agreement Index",
    "source": "charts",
    "dataKey": "estimator_agreement_index",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "annualized-panel",
    "title": "Annualized Vol Panel",
    "source": "charts",
    "dataKey": "annualized_vol_panel",
    "chartType": "metricDeck",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "multi-window",
    "title": "Multi-Window Estimator Panel",
    "source": "charts",
    "dataKey": "multi_window_estimator_panel",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "dm-tournament",
    "title": "Diebold-Mariano Tournament",
    "source": "tables",
    "dataKey": "diebold_mariano_tournament",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {
      "rowKey": "row",
      "colKey": "col",
      "valueKey": "value",
      "diverging": true
    }
  },
  {
    "id": "ranked-panel",
    "title": "Cross-Asset Ranked Panel",
    "source": "tables",
    "dataKey": "cross_asset_ranked_panel",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "range-correlation",
    "title": "Range Correlation Matrix",
    "source": "charts",
    "dataKey": "range_correlation_matrix",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {
      "diverging": true
    }
  },
  {
    "id": "opening-gap",
    "title": "Opening Gap Fragility",
    "source": "charts",
    "dataKey": "opening_gap_fragility",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "br-proxy",
    "title": "Bandi-Russell Liquidity Proxy",
    "source": "charts",
    "dataKey": "bandi_russell_estimator",
    "chartType": "area",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "vol-momentum",
    "title": "Vol-Adjusted Momentum Panel",
    "source": "charts",
    "dataKey": "vol_adjusted_momentum_panel",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature01Page() {
  return <VolatilityV2Workbench featureId="01" sections={sections} />;
}
