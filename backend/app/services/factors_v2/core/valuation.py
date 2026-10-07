"""Factors V2 valuation helpers."""

from __future__ import annotations
import numpy as np
import pandas as pd
from .panel import characteristic_panel
from .common import normalize_factor_name
from .stats import empirical_percentile, predictive_regression


def valuation_spread(payload=None):
    from .panel import historical_snapshots

    payload = payload or {}
    factors = [
        normalize_factor_name(f)
        for f in (payload.get("factors") or [payload.get("factor", "momentum_12_1")])
    ]
    chars = characteristic_panel(payload)
    snapshots = list(
        historical_snapshots(payload, int(payload.get("snapshot_step", 21)))
    )
    series, spreads, rows = {}, {}, []

    def spread(frame, factor):
        v = frame[factor].dropna()
        if len(v) < 10 or v.std() == 0:
            return np.nan
        rank = v.rank(method="first", pct=True)
        return float(v[rank >= 0.8].mean() - v[rank <= 0.2].mean())

    for factor in factors:
        if factor not in chars:
            raise ValueError(f"Unsupported factor: {factor}")
        history = pd.Series(
            {date: spread(frame, factor) for date, frame in snapshots}, dtype=float
        ).dropna()
        current = spread(chars, factor)
        spreads[factor] = history
        series[factor] = pd.Series(
            {d: empirical_percentile(history.loc[:d], v) for d, v in history.items()}
        )
        regression = {}
        regression_status = "unavailable: supply instrument metadata and sufficient matured strategy history"
        if payload.get("instrument_metadata"):
            from .backtest import portfolio_backtest

            strategy = portfolio_backtest(
                {**payload, "factor": factor, "factors": [factor]}, include_bins=False
            )
            regression = predictive_regression(
                history.reindex(strategy["gross"].index).ffill(), strategy["gross"], 252
            )
            regression_status = (
                "available"
                if regression.get("beta") is not None
                else "insufficient_matured_history"
            )
        values = chars.set_index("Ticker")[factor].dropna()
        ranks = values.rank(method="first", pct=True)
        sectors = chars.set_index("Ticker").sector
        contributions = []
        for sector in sectors.dropna().unique():
            names = sectors[sectors.eq(sector)].index
            top = values.loc[
                values.index.intersection(names).intersection(ranks[ranks >= 0.8].index)
            ]
            bottom = values.loc[
                values.index.intersection(names).intersection(ranks[ranks <= 0.2].index)
            ]
            contributions.append(
                {
                    "sector": sector,
                    "contribution": float(
                        top.sum() / max(1, (ranks >= 0.8).sum())
                        - bottom.sum() / max(1, (ranks <= 0.2).sum())
                    ),
                    "top_count": len(top),
                    "bottom_count": len(bottom),
                }
            )
        rows.append(
            {
                "factor": factor,
                "current_cross_section_spread": current,
                "historical_spread": float(history.iloc[-1]) if len(history) else None,
                "percentile": empirical_percentile(history, current),
                "expected_12m_return": regression.get("predicted_return"),
                "regression_beta": regression.get("beta"),
                "r_squared": regression.get("r_squared"),
                "ci_90_low": regression.get("ci_90_low"),
                "ci_90_high": regression.get("ci_90_high"),
                "sector_contributors": contributions,
                "top_count": int(chars[factor].notna().sum() * 0.2),
                "regression_status": regression_status,
            }
        )
    return {
        "rows": rows,
        "series": pd.DataFrame(series),
        "spread_series": pd.DataFrame(spreads),
        "chars": chars,
    }
