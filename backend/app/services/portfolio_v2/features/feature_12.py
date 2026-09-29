"""F12 Systemic Risk and Fire-Sale Contagion Engine."""

from __future__ import annotations

import pandas as pd

from ..core.analytics import cascade_probability, debtrank_propagate, feature_meta, fire_sale_impact, liquidation_spiral_prob, liquidity_table, load_context, matrix_records, network_edges, overlap_centrality, overlap_reducing_trades, portfolio_overlap_index, response, systemic_risk_contribution

FEATURE_ID = "12"
FEATURE_NAME = "Systemic Risk and Fire-Sale Contagion Engine"
INPUTS = ["tickers", "weights", "peer_count", "liquidation_fraction", "portfolio_nav"]
OUTPUTS = ["overlap_heatmap", "fire_sale_impact", "contagion_network", "debtrank", "spiral_probability"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    w = ctx["weights"].sort_values(ascending=False)
    peer_count = int(payload.get("peer_count") or 10)
    peers = {}
    supplied = payload.get("peer_portfolios") or {}
    if isinstance(supplied, dict):
        for name, weights in supplied.items():
            if isinstance(weights, dict):
                candidate = pd.Series(weights, dtype=float).reindex(w.index).fillna(0.0).clip(lower=0)
                if candidate.sum() > 0:
                    peers[str(name)] = candidate / candidate.sum()
    if not peers:
        return response(
            FEATURE_ID,
            [{"label": "Peer Books", "value": 0}],
            {},
            {"peer_data_requirement": [{"status": "required", "field": "peer_portfolios", "detail": "Provide named peer weight maps to compute overlap, fire-sale contagion, and DebtRank."}]},
            meta=feature_meta(ctx, ["Peer portfolios are required. Synthetic shuffled holdings are intentionally not used."]),
        )
    names = ["portfolio", *peers.keys()]
    portfolios = {"portfolio": w, **peers}
    overlap = portfolio_overlap_index(portfolios)
    liq = pd.DataFrame(liquidity_table(ctx["symbols"], ctx["lookback_days"], float(payload.get("portfolio_nav") or 1_000_000), w))
    theta = float(payload.get("liquidation_fraction") or 0.20)
    impacts = []
    for peer, pw in peers.items():
        loss = 0.0
        adv = liq.set_index("ticker")["adv_dollars"] if not liq.empty else pd.Series(1.0, index=w.index)
        impact_series = fire_sale_impact(pw, w, adv, theta, float(payload.get("portfolio_nav") or 1_000_000))
        loss = float(impact_series.sum())
        impacts.append({"peer": peer, "liquidation_fraction": theta, "portfolio_loss": loss, "loss_bps": loss * 10000})
    exposure_proxy = overlap.div(overlap.sum(axis=1).replace(0, 1), axis=0)
    debt_series = debtrank_propagate(exposure_proxy, pd.Series({"portfolio": theta}))
    debt = [{"node": n, "debtrank": float(v)} for n, v in debt_series.items()]
    losses = pd.Series({r["peer"]: abs(r["portfolio_loss"]) for r in impacts})
    peer_avg = pd.DataFrame(peers).mean(axis=1)
    leverage = float(payload.get("leverage") or 1.0)
    connectivity = float((overlap.drop(index="portfolio", columns="portfolio", errors="ignore") > 0.05).sum().mean())
    mean_overlap = float(overlap.loc["portfolio"].drop("portfolio").mean())
    tables = {"fire_sale_impact": impacts, "debtrank": debt, "systemic_risk_contribution": systemic_risk_contribution(overlap, losses), "overlap_centrality": overlap_centrality(overlap), "spiral_probability": [{"probability": liquidation_spiral_prob(mean_overlap, leverage, theta), "cascade_probability": cascade_probability(connectivity / max(peer_count, 1), leverage, theta), "connectivity": connectivity, "leverage": leverage}], "overlap_reducing_reallocation": overlap_reducing_trades(w, peer_avg)}
    charts = {"overlap_heatmap": matrix_records(overlap), "contagion_network": network_edges(ctx["returns"], 0.35)}
    notes = ["DebtRank exposure matrix uses normalized overlap as a proxy until directional counterparty exposures are supplied."]
    return response(FEATURE_ID, [{"label": "Max Fire-Sale Loss", "value": min([i["loss_bps"] for i in impacts] or [0.0])}, {"label": "Avg Overlap", "value": mean_overlap}], charts, tables, meta=feature_meta(ctx, notes))
