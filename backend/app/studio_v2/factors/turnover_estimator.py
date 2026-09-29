"""Factor turnover, decay, and cost-aware rebalance recommendation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class TurnoverDecayEstimator:
    def estimate(self, scores: Any, forward_returns: Any | None = None,
                 cost_bps: float | None = None, horizons: list[int] | None = None,
                 asset_class: str = "equity") -> dict[str, Any]:
        realistic_costs = {"equity": 10.0, "em_equity": 20.0, "fx": 2.0,
                           "future": 3.0, "crypto": 25.0}
        resolved_cost_bps = float(
            realistic_costs.get(str(asset_class).lower(), 10.0)
            if cost_bps is None else cost_bps
        )
        frame = pd.DataFrame(scores, dtype=float)
        ranks = frame.rank(axis=1, pct=True)
        turnover = ranks.diff().abs().mean(axis=1).fillna(0.0)
        result = {
            "average_turnover": float(turnover.mean()),
            "annualized_turnover": float(turnover.mean() * 252),
            "estimated_annual_cost": float(turnover.mean() * 252 * resolved_cost_bps / 10_000),
            "realistic_cost_bps": resolved_cost_bps,
            "turnover_series": turnover,
        }
        if forward_returns is not None:
            future = pd.DataFrame(forward_returns, dtype=float).reindex_like(frame)
            decay = []
            resolved_horizons = [int(value) for value in (horizons or [1, 5, 10, 21, 63])
                                 if 0 < int(value) < len(frame)]
            for horizon in resolved_horizons:
                shifted = future.rolling(horizon).sum().shift(-horizon)
                daily = [frame.iloc[i].corr(shifted.iloc[i], method="spearman") for i in range(max(0, len(frame) - horizon))]
                finite_daily = np.asarray(daily, dtype=float)
                finite_daily = finite_daily[np.isfinite(finite_daily)]
                ic = float(finite_daily.mean()) if len(finite_daily) else 0.0
                annual_turnover = float(turnover.mean() * 252 / max(1, horizon))
                gross_signal = max(0.0, ic) * np.sqrt(252 / max(1, horizon))
                break_even_bps = (
                    float(gross_signal / annual_turnover * 10_000)
                    if annual_turnover > 0 else float("inf")
                )
                decay.append({
                    "horizon": horizon,
                    "half_life": horizon,
                    "ic": ic,
                    "turnover": float(turnover.mean()),
                    "turnover_annualized": annual_turnover,
                    "break_even_cost_bps": break_even_bps,
                    "realistic_cost_bps": resolved_cost_bps,
                    "implementable": bool(break_even_bps > resolved_cost_bps),
                    "region": "implementable" if break_even_bps > resolved_cost_bps else "cost_dominated",
                })
            result["ic_decay"] = decay
            net = [row["ic"] - result["estimated_annual_cost"] / np.sqrt(max(1, row["horizon"])) for row in decay]
            finite_net = np.asarray(net, dtype=float)
            result["recommended_horizon"] = decay[int(np.nanargmax(finite_net))]["horizon"] if decay and np.isfinite(finite_net).any() else None
            result["chart_data"] = decay
            result["regions"] = [
                {"id": "cost_dominated", "max_break_even_bps": resolved_cost_bps},
                {"id": "implementable", "min_break_even_bps": resolved_cost_bps},
            ]
        return result
