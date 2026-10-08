"""Fraction-first Kelly sizing, leverage caps and explicit diffusion assumptions."""

import numpy as np
from ..core.context import load_context, feature_meta
from ..core.common import response
from ..core.covariance import covariance_matrix, expected_returns
from ..core.construction import solve_portfolio
from ..core.allocation import kelly_sizing

from .inputs import inputs_for, output

FEATURE_ID = "10"
FEATURE_NAME = "Growth-Optimal Position Sizing and Capital Allocation Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    r = ctx["returns"]
    ann = ctx["annualization_factor"]
    covariance, _ = covariance_matrix(
        r, payload.get("covariance_estimator", "ledoit_wolf")
    )
    covariance *= ann
    mu = expected_returns(r, payload.get("expected_return_estimator", "shrinkage"), ann)
    kelly = kelly_sizing(
        mu,
        covariance,
        ctx["weights"],
        float(payload.get("kelly_fraction", 0.5)),
        float(payload.get("leverage_cap", 1)),
        float(payload.get("transaction_cost_bps", 10)),
        int(payload.get("rebalances_per_year", 12)),
    )
    w = np.array([row["constrained_weight"] for row in kelly["table"]])
    full = np.array([row["kelly_weight"] for row in kelly["table"]])
    matrix = covariance.to_numpy()
    drift = float(w @ mu)
    variance = float(w @ matrix @ w)
    growth = drift - variance / 2
    unconstrained = float(full @ mu - full @ matrix @ full / 2)
    markowitz, _ = solve_portfolio(
        r, {"objective": "markowitz", "risk_aversion": 1}, "markowitz"
    )
    ruin = []
    for lev in [1, 1.25, 1.5, 2]:
        probability = (
            1.0
            if drift <= 0
            else float(np.exp(-2 * lev * drift / (lev**2 * variance)))
            if variance > 0
            else 0
        )
        ruin.append(
            {
                "leverage_multiplier": lev,
                "ruin_probability_model": probability,
                "model": "Infinite-horizon arithmetic Brownian wealth hitting zero, unit initial capital; not a drawdown guarantee",
            }
        )
    return response(
        FEATURE_ID,
        [
            {"label": "Annual Geometric Growth Approximation", "value": growth},
            {
                "label": "Turnover Optimal Fraction",
                "value": kelly["turnover_optimal_fraction"],
            },
        ],
        {"growth_frontier": kelly["growth_curve"], "kelly_weights": kelly["table"]},
        {
            "position_sizing": kelly["table"],
            "ruin_probability": ruin,
            "effective_kelly_fraction": [
                {"growth_ratio": growth / unconstrained if unconstrained > 0 else None}
            ],
            "kelly_vs_markowitz": [
                {
                    "ticker": row["ticker"],
                    "kelly_weight": row["constrained_weight"],
                    "markowitz_weight": float(markowitz[row["ticker"]]),
                }
                for row in kelly["table"]
            ],
            "turnover_optimal_kelly": [
                {
                    "fraction": kelly["turnover_optimal_fraction"],
                    "assumed_rebalances_per_year": int(
                        payload.get("rebalances_per_year", 12)
                    ),
                }
            ],
        },
        meta=feature_meta(
            ctx,
            [
                "No guaranteed drawdown-safe leverage is inferred from a drift/volatility approximation. Signal-decay sizing requires an actual supplied signal and is not fabricated for an arbitrary portfolio."
            ],
        ),
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("growth_frontier", "charts", "line", True),
    output("kelly_weights", "charts", "bar", False),
    output("position_sizing"),
    output("ruin_probability"),
    output("effective_kelly_fraction"),
    output("kelly_vs_markowitz"),
    output("turnover_optimal_kelly"),
]
