"""A shared, explicitly parameterized per-security square-root cost sweep."""

import numpy as np
from .panel import characteristic_panel


def cost_sweep(payload, aums):
    chars = characteristic_panel(payload)
    factor = payload.get("factor", "momentum_12_1")
    rank = chars[factor].rank(method="first", pct=True)
    top, bottom = rank >= 0.8, rank <= 0.2
    long_short = payload.get("long_short", True)
    book = chars.loc[top | bottom if long_short else top].copy()
    if book.empty:
        raise ValueError("No eligible observed characteristic book")
    invalid = book.loc[
        book.adv.isna() | book.adv.le(0) | book.realized_vol.isna(), "Ticker"
    ]
    if len(invalid):
        raise ValueError(
            "Missing observed USD ADV or volatility: " + ", ".join(invalid)
        )
    weights = np.zeros(len(chars))
    if top.sum():
        weights[top.to_numpy()] = 1 / top.sum()
    if long_short and bottom.sum():
        weights[bottom.to_numpy()] = 1 / bottom.sum()
    w = weights[(top | bottom if long_short else top).to_numpy()]
    adv = book.adv.to_numpy()
    sigma = book.realized_vol.to_numpy() / np.sqrt(252)
    turnover = float(payload.get("turnover", 0.35))
    cap = float(payload.get("participation_cap", 0.15))
    step = int(payload.get("rebalance_days", 21))
    eta = float(payload.get("impact_eta", 0.1))
    explicit = float(payload.get("explicit_bps", 8)) / 10000
    rows = []
    for aum in aums:
        trade = aum * turnover * w
        participation = trade / adv
        days = np.maximum(1, np.ceil(participation / cap))
        impact = eta * sigma * np.sqrt(participation / days)
        # Execution slicing changes per-dollar impact, not the total dollars traded.
        impact_drag = float((impact * turnover * w).sum() * 252 / step)
        explicit_drag = explicit * turnover * 252 / step
        rows.append(
            {
                "aum": float(aum),
                "impact_drag": impact_drag,
                "explicit_drag": explicit_drag,
                "annual_cost": impact_drag + explicit_drag,
                "time_to_liquidate_days": float(np.max(aum * w / (cap * adv))),
                "execution_days": float(days.max()),
                "participation_max": float(participation.max()),
            }
        )
    return rows
