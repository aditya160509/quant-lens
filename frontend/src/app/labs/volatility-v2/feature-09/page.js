"use client";

import { VolatilityV2Workbench } from "@/components/volatility-v2/customPagePrimitives";

const sections = [
  {
    "id": "dashboard",
    "title": "Portfolio Vol Dashboard",
    "source": "charts",
    "dataKey": "portfolio_vol_dashboard",
    "chartType": "metricDeck",
    "rank": "primary",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "gap",
    "title": "Vol-to-Target Gap Gauge",
    "source": "charts",
    "dataKey": "vol_to_target_gap_gauge",
    "chartType": "volGauge",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "budget",
    "title": "Vol Budget Attribution Waterfall",
    "source": "charts",
    "dataKey": "vol_budget_attribution_waterfall",
    "chartType": "budgetWaterfall",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "scaling",
    "title": "Scaling Factor History",
    "source": "charts",
    "dataKey": "scaling_factor_history",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "target",
    "title": "Regime-Conditional Target Evolution",
    "source": "charts",
    "dataKey": "regime_conditional_target_evolution",
    "chartType": "line",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "recommendation",
    "title": "Rebalancing Recommendation",
    "source": "tables",
    "dataKey": "rebalancing_recommendation",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "backtest",
    "title": "Historical Vol-Targeting Backtest",
    "source": "charts",
    "dataKey": "historical_vol_targeting_backtest",
    "chartType": "area",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "budget-table",
    "title": "Portfolio Vol Budget Table",
    "source": "tables",
    "dataKey": "portfolio_vol_budget_table",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "two-step",
    "title": "Two-Step Rebalancing Detail",
    "source": "tables",
    "dataKey": "two_step_rebalancing_detail",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "costs",
    "title": "Almgren-Chriss Transaction Costs",
    "source": "tables",
    "dataKey": "almgren_chriss_transaction_costs",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "kelly",
    "title": "Kelly Vol Target",
    "source": "tables",
    "dataKey": "kelly_vol_target",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "breaches",
    "title": "Vol Budget Breach Log",
    "source": "tables",
    "dataKey": "vol_budget_breach_log",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  },
  {
    "id": "performance",
    "title": "Historical Backtest Performance",
    "source": "tables",
    "dataKey": "historical_backtest_performance",
    "chartType": "table",
    "rank": "supporting",
    "fallbackKeys": [],
    "config": {}
  }
];

export default function VolatilityFeature09Page() {
  return <VolatilityV2Workbench featureId="09" sections={sections} />;
}
