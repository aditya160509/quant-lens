"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "capacity-curve",
    "title": "Net Alpha Capacity Curve",
    "source": "charts",
    "dataKey": "capacity_curve",
    "chartType": "area",
    "config": {
      "colorBySign": true,
      "logX": true,
      "referenceLines": [
        {
          "value": 0,
          "stroke": "#8B949E"
        }
      ]
    }
  },
  {
    "id": "slippage-table",
    "title": "AUM Slippage Sweep",
    "source": "tables",
    "dataKey": "slippage_table",
    "fallbackKeys": [
      "slippage_by_aum"
    ],
    "chartType": "table",
    "config": {
      "viableColumn": true
    }
  },
  {
    "id": "time-to-liquidate",
    "title": "Time To Liquidate",
    "source": "tables",
    "dataKey": "slippage_by_aum",
    "chartType": "table"
  },
  {
    "id": "sensitivity-analysis",
    "title": "Capacity Sensitivity Analysis",
    "source": "tables",
    "dataKey": "sensitivity_analysis",
    "fallbackKeys": [
      "sensitivity"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "allocator-memo",
    "title": "Allocator Capacity Memo",
    "source": "meta",
    "dataKey": "allocator_memo",
    "fallbackKeys": [
      "memo"
    ],
    "chartType": "textBlock"
  }
];

export default function Feature09Page() {
  return <CustomFeaturePage featureId="09" sections={sections} />;
}
