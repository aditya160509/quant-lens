"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "health-table",
    "title": "Live Signal Health Table",
    "source": "tables",
    "dataKey": "health_table",
    "fallbackKeys": [
      "signal_health"
    ],
    "chartType": "table",
    "config": {
      "colorByThreshold": true
    }
  },
  {
    "id": "ic-drift",
    "title": "IC Drift And Alert Zone",
    "source": "charts",
    "dataKey": "ic_drift",
    "chartType": "line",
    "config": {
      "seriesColors": [
        "#2F81F7"
      ],
      "referenceLines": [
        {
          "value": 0,
          "stroke": "#D29922",
          "strokeDasharray": "4 4",
          "label": "Long-run mean"
        }
      ],
      "referenceAreas": [
        {
          "y1": -10,
          "y2": -1,
          "fill": "#F85149"
        }
      ]
    }
  },
  {
    "id": "structural-break",
    "title": "CUSUM Structural Break Diagnostic",
    "source": "charts",
    "dataKey": "structural_break",
    "fallbackKeys": [
      "cusum_structural_break"
    ],
    "chartType": "bar",
    "config": {
      "colorByThreshold": true
    }
  },
  {
    "id": "crowding-velocity",
    "title": "Crowding Velocity",
    "source": "charts",
    "dataKey": "crowding_velocity",
    "chartType": "bar",
    "config": {
      "seriesColors": [
        "#A371F7"
      ],
      "referenceLines": [
        {
          "value": 0,
          "stroke": "#8B949E"
        }
      ]
    }
  },
  {
    "id": "alert-log",
    "title": "Timestamped Alert Log",
    "source": "tables",
    "dataKey": "alert_log",
    "chartType": "table"
  }
];

export default function Feature13Page() {
  return <CustomFeaturePage featureId="13" sections={sections} />;
}
