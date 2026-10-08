"""Execution cost model with explicit assumptions and a genuine cost-risk frontier."""

from ..core.context import load_context, feature_meta, parse_weights
from ..core.common import response
from ..core.execution import execution_costs

from .inputs import inputs_for, output

FEATURE_ID = "11"
FEATURE_NAME = "Optimal Execution and Transaction Cost Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    if payload.get("target_weights") is None:
        raise ValueError(
            "target_weights is required; trading into the same portfolio is not implied"
        )
    target = parse_weights({"weights": payload["target_weights"]}, ctx["symbols"])
    costs = execution_costs(
        ctx["symbols"],
        ctx["weights"],
        target,
        float(payload.get("portfolio_nav", 1000000)),
        int(payload.get("time_horizon", 5)),
        float(payload.get("risk_aversion", 0.1)),
        ctx["returns"],
        payload.get("temporary_impact_coefficient"),
        payload.get("permanent_impact_coefficient", 0),
    )
    delay = payload.get("delay_returns", {})
    decomposition = []
    if set(delay) - set(ctx["symbols"]):
        raise ValueError("Delay returns contain unknown symbols")
    for row in costs["cost_table"]:
        ticker = row["ticker"]
        trade = row["trade_dollars"]
        delay_cost = trade * float(delay[ticker]) if ticker in delay else None
        decomposition.append(
            {
                "ticker": ticker,
                "temporary_impact_dollars": row["temporary_cost_dollars"],
                "permanent_impact_dollars": row["permanent_cost_dollars"],
                "delay_cost_dollars": delay_cost,
                "delay_status": "observed input"
                if delay_cost is not None
                else "not supplied",
                "opportunity_cost_bps_assumption": float(
                    payload.get("opportunity_cost_bps", 0)
                ),
            }
        )
    return response(
        FEATURE_ID,
        [
            {
                "label": "Expected Impact Cost $",
                "value": sum(r["expected_is_dollars"] for r in costs["cost_table"]),
            },
            {"label": "Shortfall Risk $", "value": costs["shortfall_std_dollars"]},
        ],
        {"execution_trajectory": costs["schedule"], "is_frontier": costs["frontier"]},
        {
            "cost_estimate": costs["cost_table"],
            "is_decomposition": decomposition,
            "joint_schedule": costs["schedule"],
        },
        meta=feature_meta(
            ctx,
            [
                "Covariance couples execution risk; permanent/temporary coefficients are explicit assumptions, not observed order-flow calibration. Intraday volume profiles and cross-impact coefficients cannot be inferred from daily OHLCV and are not fabricated."
            ],
        ),
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("execution_trajectory", "charts", "line", True),
    output("is_frontier", "charts", "line", False),
    output("cost_estimate"),
    output("is_decomposition"),
    output("joint_schedule"),
]
