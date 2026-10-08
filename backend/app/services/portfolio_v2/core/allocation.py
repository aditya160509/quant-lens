"""Portfolio V2 allocation engine."""

from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from .common import fast_solve


def kelly_sizing(
    mu: pd.Series,
    cov: pd.DataFrame,
    current: pd.Series | None = None,
    fraction: float = 0.5,
    leverage_cap: float = 1.0,
    tc_bps: float = 10.0,
    rebalances_per_year: int = 12,
) -> dict[str, Any]:
    cols = list(mu.index)
    n = len(cols)
    mu_arr = mu.to_numpy(dtype=np.float64)
    sigma = (
        cov.reindex(index=cols, columns=cols).to_numpy(dtype=np.float64)
        + np.eye(n) * 1e-9
    )
    raw = fast_solve(sigma, mu_arr)
    if not np.isfinite(raw).all() or not 0 < fraction <= 1 or leverage_cap <= 0:
        raise ValueError("Invalid Kelly estimates or controls")
    w = raw * fraction
    wabs = float(np.abs(w).sum())
    if wabs > leverage_cap:
        w *= leverage_cap / wabs
    cur = (
        current.reindex(cols).fillna(0.0).to_numpy(dtype=np.float64)
        if current is not None
        else np.zeros(n)
    )
    rows = [
        {
            "ticker": s,
            "kelly_weight": float(r),
            "constrained_weight": float(wi),
            "current_weight": float(ci),
            "sizing_gap": float(wi - ci),
        }
        for s, r, wi, ci in zip(cols, raw, w, cur)
    ]
    fracs = np.linspace(0.05, 1.0, 40, dtype=np.float64)
    tc = float(tc_bps / 10000)
    grid = []
    for f in fracs:
        wf = raw * f
        if np.abs(wf).sum() > leverage_cap:
            wf *= leverage_cap / np.abs(wf).sum()
        growth = float(wf @ mu_arr) - 0.5 * float(wf @ sigma @ wf)
        cost = tc * float(np.abs(wf - cur).sum()) * rebalances_per_year
        grid.append(
            {
                "kelly_fraction": float(f),
                "gross_growth": growth,
                "cost_drag": cost,
                "net_growth": growth - cost,
            }
        )
    best = max(grid, key=lambda r: r["net_growth"]) if grid else {"kelly_fraction": 0.0}
    return {
        "table": rows,
        "growth_curve": grid,
        "turnover_optimal_fraction": best["kelly_fraction"],
    }


def geometric_growth_rate(
    weights: pd.Series | np.ndarray,
    mu: pd.Series | np.ndarray,
    cov: pd.DataFrame | np.ndarray,
) -> float:
    w = np.asarray(weights, dtype=float)
    m = np.asarray(mu, dtype=float)
    c = np.asarray(cov, dtype=float)
    return float(w @ m - 0.5 * w @ c @ w)


def turnover_optimal_kelly(
    mu: pd.Series, cov: pd.DataFrame, current: pd.Series, tc_bps: float = 10.0
) -> dict[str, Any]:
    base = kelly_sizing(mu, cov, current, 1.0, 1.0, tc_bps)
    best = (
        max(base["growth_curve"], key=lambda r: r["net_growth"])
        if base["growth_curve"]
        else {}
    )
    return {"best_fraction": best.get("kelly_fraction"), "curve": base["growth_curve"]}
