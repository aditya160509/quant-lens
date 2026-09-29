"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "characteristic-exposures",
    "title": "Characteristic Exposure Snapshot",
    "source": "tables",
    "dataKey": "characteristic_exposures",
    "chartType": "horizontalBar",
    "config": {
      "colorBySign": true,
      "errorBars": true,
      "positiveColor": "#3FB950",
      "negativeColor": "#F85149",
      "referenceLines": [
        {
          "value": 0,
          "stroke": "#8B949E"
        },
        {
          "value": 0.4,
          "stroke": "#D29922",
          "strokeDasharray": "4 4"
        },
        {
          "value": -0.4,
          "stroke": "#D29922",
          "strokeDasharray": "4 4"
        }
      ]
    }
  },
  {
    "id": "exposure-divergence",
    "title": "Active Exposure Divergence",
    "source": "tables",
    "dataKey": "divergence",
    "chartType": "groupedHorizontalBar",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#D29922"
      ]
    }
  },
  {
    "id": "holdings-heatmap",
    "title": "Holdings Contribution Heatmap",
    "source": "charts",
    "dataKey": "static_exposure_heatmap",
    "chartType": "heatmap"
  },
  {
    "id": "rolling-exposure-heatmap",
    "title": "Animated Rolling Exposure Heatmap",
    "source": "charts",
    "dataKey": "rolling_exposure_snapshots",
    "fallbackKeys": [
      "static_exposure_heatmap"
    ],
    "chartType": "rollingHeatmap",
    "rank": "supporting",
    "config": {
      "defaultSort": "magnitude"
    }
  },
  {
    "id": "multi-portfolio-comparison",
    "title": "Multi-Portfolio Side-By-Side",
    "source": "charts",
    "dataKey": "multi_portfolio_comparison",
    "chartType": "multiPortfolioCompare",
    "rank": "supporting"
  },
  {
    "id": "unintended-exposures",
    "title": "Unintended Exposure Flags",
    "source": "tables",
    "dataKey": "unintended_exposures",
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "tilt-summary",
    "title": "Tilt Summary",
    "source": "tables",
    "dataKey": "tilt_summary",
    "chartType": "textBlock"
  }
];

export default function Feature02Page() {
  return <CustomFeaturePage featureId="02" sections={sections} />;
}
