"""Observed liquidity and participation-constrained exit schedules."""

from ..core.context import load_context, feature_meta
from ..core.common import response
from ..core.data_loader import ohlcv_for_symbols
from ..core.liquidity import (
    liquidity_table,
    liquidity_halflife,
    regulatory_classification,
    crisis_liquidation_cost,
    liquidity_frontier,
    liquidation_schedule,
)

from .inputs import inputs_for, output

FEATURE_ID = "07"
FEATURE_NAME = "Liquidity Analytics Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    participation = float(payload.get("participation_rate", 0.2))
    rows = liquidity_table(
        ctx["symbols"],
        ctx["lookback_days"],
        float(payload.get("portfolio_nav", 1000000)),
        ctx["weights"],
        int(payload.get("adv_window", 60)),
        participation,
    )
    raw = ohlcv_for_symbols(ctx["symbols"], ctx["lookback_days"])
    half = []
    for ticker, g in raw.groupby("Ticker"):
        x = ((g.Close / g.Open - 1).abs() / (g.Close * g.Volume)).replace(
            [float("inf"), float("-inf")], float("nan")
        )
        half.append(
            {
                "ticker": ticker,
                "liquidity_halflife_days": liquidity_halflife(x),
                "method": "Log open-to-close Amihud trend over up to 60 observed sessions; improving trends only",
            }
        )
    return response(
        FEATURE_ID,
        [{"label": "Max DTL", "value": max(r["days_to_liquidate"] for r in rows)}],
        {
            "liquidation_schedule": liquidation_schedule(
                rows, participation, payload.get("liquidation_urgency", "orderly")
            ),
            "liquidity_rank": sorted(
                rows, key=lambda r: r["days_to_liquidate"], reverse=True
            ),
            "dtl_eligibility": liquidity_frontier(rows),
        },
        {
            "liquidity_table": rows,
            "days_to_liquidate": [
                {"ticker": r["ticker"], "days": r["days_to_liquidate"]} for r in rows
            ],
            "half_life": half,
            "stress_liquidation_cost": crisis_liquidation_cost(
                rows, float(payload.get("stress_volume_multiplier", 0.3))
            ),
            "dtl_classification": [
                {
                    "ticker": r["ticker"],
                    "bucket": regulatory_classification(r["days_to_liquidate"]),
                    "interpretation": "DTL threshold classification only, not a SEC/UCITS compliance certification",
                }
                for r in rows
            ],
        },
        meta=feature_meta(
            ctx,
            [
                "Measured bid-ask spreads and signed order flow are absent: calibrated LVaR, permanent impact and regulatory compliance certification are not produced"
            ],
        ),
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("liquidation_schedule", "charts", "line", True),
    output("liquidity_rank", "charts", "bar", False),
    output("dtl_eligibility", "charts", "bar", False),
    output("liquidity_table"),
    output("days_to_liquidate"),
    output("half_life"),
    output("stress_liquidation_cost"),
    output("dtl_classification"),
]
