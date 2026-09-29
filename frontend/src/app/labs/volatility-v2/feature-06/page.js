"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "index",
    "title": "Total Connectedness Index",
    "source": "charts",
    "dataKey": "connectedness_index",
    "chartType": "area",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "net-ranking",
    "title": "Net Spillover Ranking",
    "source": "tables",
    "dataKey": "net_spillover_ranking",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "network",
    "title": "Dynamic Connectedness Network",
    "source": "charts",
    "dataKey": "spillover_network_graph",
    "chartType": "network",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "fevd",
    "title": "Pairwise FEVD Heatmap",
    "source": "charts",
    "dataKey": "pairwise_fevd_heatmap",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {
      "rowKey": "row",
      "colKey": "col",
      "valueKey": "value"
    }
  },
  {
    "id": "to-from",
    "title": "Rolling To/From Decomposition",
    "source": "charts",
    "dataKey": "rolling_to_from_decomposition",
    "chartType": "bar",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "alert",
    "title": "Connectedness Regime Alert",
    "source": "tables",
    "dataKey": "connectedness_regime_alert",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "frequency",
    "title": "Frequency-Decomposed Connectedness",
    "source": "charts",
    "dataKey": "frequency_decomposed_connectedness",
    "chartType": "frequencyBands",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "car",
    "title": "Connectedness-at-Risk",
    "source": "tables",
    "dataKey": "connectedness_at_risk",
    "chartType": "metricDeck",
    "rank": "supporting",
    "fallbackKeys": [
      "connectedness_at_risk"
    ],
    "config": {}
  },
  {
    "id": "irf",
    "title": "VAR Impulse Response",
    "source": "charts",
    "dataKey": "var_impulse_response",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature06Page() {
  return <VolatilityV2Workbench featureId="06" sections={sections} />;
}
