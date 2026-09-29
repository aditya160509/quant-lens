"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "gauges",
    "title": "Valuation Dial Gauges",
    "source": "charts",
    "dataKey": "gauge_panel",
    "fallbackKeys": [
      "summary_cards"
    ],
    "chartType": "multiFactorGaugePanel"
  },
  {
    "id": "percentile-series",
    "title": "Historical Percentile Series",
    "source": "charts",
    "dataKey": "percentile_series",
    "fallbackKeys": [
      "spread_percentile_timeseries",
      "spread_history",
      "valuation_spread",
      "valuation_series"
    ],
    "chartType": "annotatedTimeSeries",
    "config": {
      "crisisDataKey": "crisis_anchors",
      "referenceLines": [
        {
          "value": 70,
          "stroke": "#F85149",
          "strokeDasharray": "4 4",
          "label": "70th"
        },
        {
          "value": 30,
          "stroke": "#3FB950",
          "strokeDasharray": "4 4",
          "label": "30th"
        }
      ],
      "stacked": true,
      "fillOpacity": 0.55
    }
  },
  {
    "id": "valuation-correlation",
    "title": "Valuation Correlation Matrix",
    "source": "charts",
    "dataKey": "valuation_correlation",
    "fallbackKeys": [
      "valuation_correlation_matrix",
      "correlation_matrix"
    ],
    "chartType": "heatmap",
    "config": {
      "palette": "diverging"
    }
  },
  {
    "id": "sector-contributors",
    "title": "Sector Spread Contributors",
    "source": "tables",
    "dataKey": "sector_contributors",
    "fallbackKeys": [
      "sector_contribution",
      "sector_spread_table"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "expected-return-regression",
    "title": "Expected Return Regression",
    "source": "charts",
    "dataKey": "expected_return_regression",
    "fallbackKeys": [
      "regression_scatter"
    ],
    "chartType": "scatter"
  },
  {
    "id": "alert-feed",
    "title": "Live Valuation Alert Feed",
    "source": "alerts",
    "dataKey": "alert_feed",
    "chartType": "alertFeed",
    "rank": "supporting"
  }
];

export default function Feature01Page() {
  return <CustomFeaturePage featureId="01" sections={sections} />;
}
