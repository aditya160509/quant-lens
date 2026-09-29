"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "parameter-table",
    "title": "HAR Parameter Table",
    "source": "tables",
    "dataKey": "har_parameter_table",
    "chartType": "table",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "forecast-chart",
    "title": "Multi-Horizon Forecast Chart",
    "source": "charts",
    "dataKey": "multi_horizon_forecast_chart",
    "chartType": "forecastBands",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "accuracy",
    "title": "Forecast Accuracy Table",
    "source": "tables",
    "dataKey": "forecast_accuracy_table",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "mcs",
    "title": "Model Confidence Set",
    "source": "tables",
    "dataKey": "model_confidence_set",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "jump-proxy",
    "title": "Jump Proxy Time Series",
    "source": "charts",
    "dataKey": "jump_proxy_time_series",
    "chartType": "area",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "leverage",
    "title": "Leverage Effect Chart",
    "source": "charts",
    "dataKey": "leverage_effect_chart",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "acsv",
    "title": "ACSV Predictive Contribution",
    "source": "charts",
    "dataKey": "acsv_predictive_contribution",
    "chartType": "area",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "macro",
    "title": "HAR-X Macro Contribution",
    "source": "charts",
    "dataKey": "har_x_macro_contribution",
    "chartType": "bar",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "walk-forward",
    "title": "Walk-Forward Forecast Check",
    "source": "charts",
    "dataKey": "walk_forward_forecast_chart",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "bootstrap",
    "title": "Bootstrap Forecast Bands",
    "source": "charts",
    "dataKey": "forecast_confidence_bands",
    "chartType": "forecastBands",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "jump-disagreement",
    "title": "Jump Estimator Disagreement",
    "source": "tables",
    "dataKey": "jump_estimator_disagreement",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature03Page() {
  return <VolatilityV2Workbench featureId="03" sections={sections} />;
}
