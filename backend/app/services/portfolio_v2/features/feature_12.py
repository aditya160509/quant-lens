"""Real peer books and optional measured counterparty exposure stress."""

import pandas as pd
from ..core.context import load_context, feature_meta, parse_weights
from ..core.common import response, matrix_records
from ..core.systemic import (
    portfolio_overlap_index,
    overlap_centrality,
    debtrank_propagate,
    fire_sale_impact,
    overlap_reducing_trades,
)
from ..core.liquidity import liquidity_table

from .inputs import inputs_for, output

FEATURE_ID = "12"
FEATURE_NAME = "Systemic Risk and Fire-Sale Contagion Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    supplied = payload.get("peer_portfolios")
    if not supplied:
        return response(
            FEATURE_ID,
            [{"label": "Peer Books", "value": 0}],
            {},
            {
                "peer_data_requirement": [
                    {
                        "field": "peer_portfolios",
                        "status": "required",
                        "reason": "Named real peer books are required; shuffled holdings are not used",
                    }
                ]
            },
            meta=feature_meta(ctx, ["Actual peer portfolios are required"]),
        )
    if "portfolio" in supplied:
        raise ValueError("Peer name portfolio is reserved")
    peers = {
        name: parse_weights({"weights": weights}, ctx["symbols"])
        for name, weights in supplied.items()
    }
    books = {"portfolio": ctx["weights"], **peers}
    overlap = portfolio_overlap_index(books)
    issues = []
    impacts = []
    debt = []
    navs = payload.get("peer_navs", {})
    gamma = payload.get("market_depth_coefficient")
    if gamma is not None and set(navs) == set(peers):
        rows = liquidity_table(
            ctx["symbols"],
            ctx["lookback_days"],
            float(payload.get("portfolio_nav", 1000000)),
            ctx["weights"],
        )
        adv = pd.Series({r["ticker"]: r["adv_dollars"] for r in rows})
        for name, w in peers.items():
            contributions = fire_sale_impact(
                w,
                ctx["weights"],
                adv,
                float(payload.get("liquidation_fraction", 0.2)),
                float(navs[name]),
                float(gamma),
            )
            impacts.append(
                {
                    "peer": name,
                    "portfolio_loss": float(contributions.sum()),
                    "portfolio_loss_dollars": float(
                        contributions.sum() * payload.get("portfolio_nav", 1000000)
                    ),
                    "loss_bps": float(contributions.sum() * 10000),
                    "peer_nav": float(navs[name]),
                    "market_depth_coefficient_assumption": float(gamma),
                }
            )
    else:
        issues.append(
            "Fire-sale stress requires real peer_navs and an explicit market_depth_coefficient; own NAV is not substituted for peers"
        )
    if payload.get("counterparty_exposures") is not None:
        exposure = pd.DataFrame(payload["counterparty_exposures"]).reindex(
            index=list(books), columns=list(books)
        )
        if exposure.isna().any().any():
            raise ValueError(
                "Complete directional exposure matrix required, including explicit zero entries"
            )
        initial = payload.get("initial_distress")
        if initial is None or set(initial) - set(books):
            raise ValueError("Actual named initial_distress required")
        result = debtrank_propagate(exposure, pd.Series(initial, dtype=float))
        debt = [{"node": c, "distress": float(v)} for c, v in result.items()]
    else:
        issues.append(
            "DebtRank requires directional counterparty exposures as fractions of equity; overlap is not an exposure substitute"
        )
    edges = [
        {"source": a, "target": b, "weight": float(overlap.loc[a, b])}
        for i, a in enumerate(overlap)
        for b in list(overlap)[i + 1 :]
        if overlap.loc[a, b] > 0
    ]
    return response(
        FEATURE_ID,
        [{"label": "Peer Books", "value": len(peers)}],
        {"overlap_heatmap": matrix_records(overlap), "contagion_network": edges},
        {
            "fire_sale_impact": impacts,
            "debtrank": debt,
            "overlap_centrality": overlap_centrality(overlap),
            "shared_holding_ranking": overlap_reducing_trades(
                ctx["weights"], pd.DataFrame(peers).mean(axis=1)
            ),
        },
        meta=feature_meta(
            ctx,
            issues
            + [
                "Cascade and liquidation-spiral probabilities require capital buffers, leverage, liquidation rules and calibrated shock distributions; no uniform-random or exponential probability proxy is published"
            ],
        ),
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("overlap_heatmap", "charts", "heatmap", True),
    output("contagion_network", "charts", "network", False),
    output("fire_sale_impact"),
    output("debtrank"),
    output("overlap_centrality"),
    output("shared_holding_ranking"),
    output("peer_data_requirement"),
]
