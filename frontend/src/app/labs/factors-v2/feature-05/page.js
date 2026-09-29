"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "ic-decay",
    "title": "IC Decay With Confidence Bands",
    "source": "charts",
    "dataKey": "ic_decay",
    "fallbackKeys": [
      "ic_decay_curve"
    ],
    "chartType": "line",
    "config": {
      "seriesColors": [
        "#2F81F7",
        "#58A6FF",
        "#8B949E"
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
    "id": "decay-model-fits",
    "title": "Decay Model Fits",
    "source": "charts",
    "dataKey": "decay_model_fits",
    "chartType": "line",
    "config": {
      "dashed": true,
      "seriesColors": [
        "#2F81F7",
        "#D29922",
        "#A371F7"
      ]
    }
  },
  {
    "id": "half-life-table",
    "title": "Half-Life Diagnostics",
    "source": "tables",
    "dataKey": "half_life_table",
    "fallbackKeys": [
      "decay_models",
      "half_life"
    ],
    "chartType": "table",
    "config": {
      "colorBySign": true
    }
  },
  {
    "id": "rebalancing-cost-curve",
    "title": "Rebalancing Cost Curve",
    "source": "charts",
    "dataKey": "rebalancing_cost_curve",
    "chartType": "area",
    "config": {
      "referenceLines": [
        {
          "value": 0,
          "stroke": "#D29922",
          "strokeDasharray": "4 4",
          "label": "Peak zone"
        }
      ]
    }
  },
  {
    "id": "rolling-half-life",
    "title": "Rolling Half-Life",
    "source": "charts",
    "dataKey": "rolling_half_life",
    "chartType": "line"
  },
  {
    "id": "icir-by-horizon",
    "title": "ICIR By Horizon",
    "source": "charts",
    "dataKey": "icir_by_horizon",
    "chartType": "line"
  },
  {
    "id": "signal-power-radar",
    "title": "Signal Power Radar",
    "source": "charts",
    "dataKey": "factor_signal_power_radar",
    "chartType": "radar",
    "rank": "supporting"
  },
  {
    "id": "cross-sector-decay",
    "title": "Cross-Sector Decay Matrix",
    "source": "charts",
    "dataKey": "cross_sector_decay",
    "chartType": "crossSectorDecay",
    "rank": "supporting"
  },
  {
    "id": "multi-factor-radar-overlay",
    "title": "Multi-Factor Power Overlay",
    "source": "charts",
    "dataKey": "multi_factor_power_radar",
    "chartType": "multiFactorRadar",
    "rank": "supporting"
  }
];

export default function Feature05Page() {
  return <CustomFeaturePage featureId="05" sections={sections} />;
}
