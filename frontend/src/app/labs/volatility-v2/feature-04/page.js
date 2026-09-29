"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "timeline",
    "title": "Probabilistic Regime Timeline",
    "source": "charts",
    "dataKey": "probabilistic_regime_timeline",
    "chartType": "probabilityStack",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "dashboard",
    "title": "Current Regime Dashboard",
    "source": "charts",
    "dataKey": "current_regime_dashboard",
    "chartType": "regimeDashboard",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "conditional",
    "title": "Regime-Conditional Statistics",
    "source": "tables",
    "dataKey": "regime_conditional_stats",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "transition",
    "title": "Regime Transition Heatmap",
    "source": "charts",
    "dataKey": "transition_heatmap",
    "chartType": "heatmap",
    "rank": "supporting",
    "fallbackKeys": [
      "regime_transition_heatmap"
    ],
    "config": {
      "rowKey": "row",
      "colKey": "col",
      "valueKey": "value"
    }
  },
  {
    "id": "divergence",
    "title": "Method Divergence Indicator",
    "source": "charts",
    "dataKey": "method_divergence_indicator",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "alerts",
    "title": "Regime Transition Alert Log",
    "source": "tables",
    "dataKey": "transition_alert_log",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "adaptive",
    "title": "Adaptive EW-HMM Timeline",
    "source": "charts",
    "dataKey": "adaptive_hmm_timeline",
    "chartType": "probabilityStack",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "filtered",
    "title": "Smoothed vs Filtered Posterior",
    "source": "charts",
    "dataKey": "smoothed_vs_filtered_comparison",
    "chartType": "dualPosterior",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "duration",
    "title": "Regime Duration Survival",
    "source": "tables",
    "dataKey": "regime_duration_survival",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "sync",
    "title": "Global Vol Regime Sync Index",
    "source": "charts",
    "dataKey": "global_vol_regime_sync_index",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "hmm-bic",
    "title": "HMM BIC K Selection",
    "source": "tables",
    "dataKey": "hmm_bic_k_selection",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature04Page() {
  return <VolatilityV2Workbench featureId="04" sections={sections} />;
}
