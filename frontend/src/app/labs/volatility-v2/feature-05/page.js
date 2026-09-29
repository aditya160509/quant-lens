"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "vrp-series",
    "title": "VRP Time Series",
    "source": "charts",
    "dataKey": "vrp_time_series",
    "chartType": "area",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "zscore",
    "title": "VRP Z-Score Panel",
    "source": "charts",
    "dataKey": "vrp_zscore_panel",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "cross-asset",
    "title": "Cross-Asset VRP Comparison",
    "source": "tables",
    "dataKey": "cross_asset_vrp_comparison",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "predictability",
    "title": "Return Predictability Panel",
    "source": "tables",
    "dataKey": "return_predictability_regression",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "mean-reversion",
    "title": "VRP Mean Reversion Speed",
    "source": "tables",
    "dataKey": "vrp_mean_reversion_speed",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "component",
    "title": "VRP Component Attribution",
    "source": "charts",
    "dataKey": "vrp_component_attribution",
    "chartType": "bar",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "term",
    "title": "VRP Term Structure",
    "source": "charts",
    "dataKey": "vrp_term_structure",
    "chartType": "termStructure",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "regime-btz",
    "title": "Regime-Conditional BTZ",
    "source": "tables",
    "dataKey": "regime_conditional_btz",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "lookbacks",
    "title": "Z-Score Lookback Comparison",
    "source": "tables",
    "dataKey": "vrp_zscore_lookback_comparison",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature05Page() {
  return <VolatilityV2Workbench featureId="05" sections={sections} />;
}
