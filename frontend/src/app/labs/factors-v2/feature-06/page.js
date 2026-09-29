"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "crowding-gauge",
    "title": "Crowding Score And Density",
    "source": "summary",
    "dataKey": "summary_cards",
    "chartType": "gauge"
  },
  {
    "id": "crowding-timeseries",
    "title": "Crowding Time Series With Stress Bands",
    "source": "charts",
    "dataKey": "crowding_timeseries",
    "chartType": "area",
    "config": {
      "seriesColors": [
        "#2F81F7"
      ],
      "referenceAreas": [
        {
          "y1": 0,
          "y2": 40,
          "fill": "#3FB950"
        },
        {
          "y1": 40,
          "y2": 70,
          "fill": "#D29922"
        },
        {
          "y1": 70,
          "y2": 100,
          "fill": "#F85149"
        }
      ]
    }
  },
  {
    "id": "crowding-metrics-radar",
    "title": "Crowding Metric Radar",
    "source": "charts",
    "dataKey": "crowding_metrics_radar",
    "fallbackKeys": [
      "metric_breakdown"
    ],
    "chartType": "radar",
    "config": {
      "stroke": "#A371F7",
      "fill": "#A371F7",
      "fillOpacity": 0.2
    }
  },
  {
    "id": "crowding-return-overlay",
    "title": "Crowding Return Overlay",
    "source": "charts",
    "dataKey": "crowding_return_overlay",
    "chartType": "crowdingOverlay",
    "rank": "supporting"
  },
  {
    "id": "crash-annotations",
    "title": "Crash Annotation Log",
    "source": "tables",
    "dataKey": "crash_annotations",
    "chartType": "table",
    "rank": "contextual"
  },
  {
    "id": "crash-probability",
    "title": "Crash Probability Credible Intervals",
    "source": "tables",
    "dataKey": "crash_probability",
    "chartType": "table",
    "config": {
      "colorByThreshold": true
    }
  },
  {
    "id": "crowding-league",
    "title": "Crowding League Table",
    "source": "tables",
    "dataKey": "crowding_league",
    "chartType": "table",
    "config": {
      "colorByThreshold": true
    }
  },
  {
    "id": "deleveraging-risk",
    "title": "Deleveraging Risk Diagnostics",
    "source": "tables",
    "dataKey": "deleveraging_risk",
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  }
];

export default function Feature06Page() {
  return <CustomFeaturePage featureId="06" sections={sections} />;
}
