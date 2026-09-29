"""F11 Optimal Execution and Transaction Cost Engine."""

from __future__ import annotations

import pandas as pd

from ..core.analytics import almgren_chriss_trajectory, correlated_multiasset_is, execution_costs, feature_meta, impact_calibration, is_decomposition, is_efficient_frontier, load_context, response, signal_decay_urgency, volume_profile_trajectory
from ..core.performance import cached_correlation_frame

FEATURE_ID = "11"
FEATURE_NAME = "Optimal Execution and Transaction Cost Engine"
INPUTS = ["tickers", "weights", "target_weights", "portfolio_nav", "time_horizon", "risk_aversion"]
OUTPUTS = ["execution_trajectory", "is_frontier", "cost_estimate", "is_decomposition", "joint_schedule"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    current = ctx["weights"]
    target = ctx["weights"].copy()
    if payload.get("target_weights"):
        from ..core.analytics import parse_weights
        parsed = parse_weights({"weights": payload.get("target_weights")}, ctx["symbols"])
        if parsed is not None:
            target = parsed
    costs = execution_costs(ctx["symbols"], current, target, float(payload.get("portfolio_nav") or 1_000_000), int(payload.get("time_horizon") or payload.get("horizon_days") or 5), float(payload.get("risk_aversion") or 0.1))
    total = sum(r["expected_is_dollars"] for r in costs["cost_table"])
    ac = []
    decomp = []
    sigma_daily = float(ctx["returns"].std().mean())
    for row in costs["cost_table"]:
        calib = impact_calibration(row["adv_dollars"], row["market_impact_bps"] / 10000)
        traj = almgren_chriss_trajectory(row["trade_dollars"], sigma_daily, calib["eta"], float(payload.get("risk_aversion") or 0.1), int(payload.get("time_horizon") or payload.get("horizon_days") or 5))
        ac += [{**x, "ticker": row["ticker"]} for x in volume_profile_trajectory(traj)]
        decomp.append({"ticker": row["ticker"], **is_decomposition(row["trade_dollars"], row["market_impact_bps"], row["timing_risk_bps"])})
    trades = pd.Series({r["ticker"]: r["trade_dollars"] for r in costs["cost_table"]})
    corr = cached_correlation_frame(ctx["returns"])
    tables = {"cost_estimate": costs["cost_table"], "is_decomposition": decomp, "joint_schedule": costs["schedule"], "signal_decay_urgency": signal_decay_urgency(0.05, 63, int(payload.get("time_horizon") or 5)), "correlated_multiasset_is": [{"cross_impact_cost": correlated_multiasset_is(trades, corr)}]}
    charts = {"execution_trajectory": costs["schedule"], "almgren_chriss_trajectory": ac, "is_frontier_aggregate": costs["frontier"], "is_frontier_almgren_chriss": is_efficient_frontier(float(trades.abs().sum()), sigma_daily, 1e-9)}
    return response(FEATURE_ID, [{"label": "Expected IS $", "value": total, "format": "currency"}, {"label": "Trade Count", "value": len(costs["cost_table"])}], charts, tables, meta=feature_meta(ctx))
