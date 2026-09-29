"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "attribution-waterfall",
    "title": "Attribution Waterfall",
    "source": "charts",
    "dataKey": "attribution_waterfall",
    "fallbackKeys": [
      "waterfall"
    ],
    "chartType": "waterfall",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "cumulative-contributions",
    "title": "Cumulative Factor Contributions",
    "source": "charts",
    "dataKey": "cumulative_contributions",
    "fallbackKeys": [
      "cumulative_contribution"
    ],
    "chartType": "stackedArea",
    "config": {
      "fillOpacity": 0.75
    }
  },
  {
    "id": "stacked-active-return-waterfall",
    "title": "Stacked Active-Return Waterfall",
    "source": "charts",
    "dataKey": "stacked_active_return_waterfall",
    "chartType": "stackedAttributionWaterfall",
    "rank": "supporting"
  },
  {
    "id": "decision-freshness-score",
    "title": "Decision Freshness Score",
    "source": "charts",
    "dataKey": "decision_freshness_score",
    "chartType": "freshnessScore",
    "rank": "supporting"
  },
  {
    "id": "factor-contributions",
    "title": "Factor Contribution Table",
    "source": "tables",
    "dataKey": "factor_contributions",
    "fallbackKeys": [
      "factor_contribution"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "ir-by-component",
    "title": "Information Ratio By Component",
    "source": "charts",
    "dataKey": "ir_by_component",
    "chartType": "bar",
    "config": {
      "referenceLines": [
        {
          "value": 0.5,
          "stroke": "#D29922",
          "strokeDasharray": "4 4",
          "label": "0.5 IR"
        }
      ]
    }
  },
  {
    "id": "brinson-fachler",
    "title": "Dynamic Brinson-Fachler Attribution",
    "source": "tables",
    "dataKey": "brinson_fachler",
    "fallbackKeys": [
      "sector_attribution"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "rolling-ir",
    "title": "Rolling Attribution IR",
    "source": "charts",
    "dataKey": "rolling_ir",
    "fallbackKeys": [
      "rolling_information_ratio"
    ],
    "chartType": "line",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#D29922"
      ]
    }
  }
];

export default function Feature03Page() {
  return <CustomFeaturePage featureId="03" sections={sections} />;
}
