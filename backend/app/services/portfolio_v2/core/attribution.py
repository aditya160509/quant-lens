"""Portfolio V2 attribution engine."""

from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from .common import clean_json


def brinson_fachler(
    returns: pd.DataFrame,
    portfolio_weights: pd.Series,
    benchmark_weights: pd.Series,
    groups: dict[str, str],
    method: str = "fachler",
) -> list[dict[str, Any]]:
    if method not in {"fachler", "bhb"}:
        raise ValueError("Unknown Brinson allocation method")
    rows = []
    mean_ret = returns.mean()
    for group in sorted(set(groups.values())):
        names = [c for c in returns.columns if groups.get(c, "Unknown") == group]
        if not names:
            continue
        wp = portfolio_weights.reindex(names).fillna(0.0)
        wb = benchmark_weights.reindex(names).fillna(0.0)
        rp = float((wp * mean_ret.reindex(names)).sum() / max(wp.sum(), 1e-12))
        rb = float((wb * mean_ret.reindex(names)).sum() / max(wb.sum(), 1e-12))
        total_bench = float(
            (benchmark_weights.reindex(returns.columns).fillna(0.0) * mean_ret).sum()
        )
        rows.append(
            {
                "group": group,
                "allocation": float(
                    (wp.sum() - wb.sum())
                    * (rb - total_bench if method == "fachler" else rb)
                ),
                "selection": float(wb.sum() * (rp - rb)),
                "interaction": float((wp.sum() - wb.sum()) * (rp - rb)),
            }
        )
    return clean_json(rows)


def risk_attribution_xsr(
    active_returns: pd.DataFrame, active_weights: pd.Series
) -> list[dict[str, Any]]:
    cov = active_returns.cov()
    w = active_weights.reindex(active_returns.columns).fillna(0.0)
    variance = float(w @ cov @ w)
    if variance <= 0:
        return [
            {
                "ticker": c,
                "mcte": None,
                "component_te": None,
                "reason": "Marginal risk is undefined at zero portfolio variance",
            }
            for c in active_returns.columns
        ]
    te = math.sqrt(variance)
    mcte = cov @ w / te
    return [
        {
            "ticker": c,
            "mcte": float(mcte.get(c, 0.0)),
            "component_te": float(w.get(c, 0.0) * mcte.get(c, 0.0)),
        }
        for c in active_returns.columns
    ]


def linked_effects(effects, portfolio, benchmark, method="carino"):
    """Exact geometric active-return reconciliation for Carino, Menchero and GRAP."""
    joined = pd.concat(
        [portfolio.rename("p"), benchmark.rename("b"), effects], axis=1
    ).dropna()
    p, b = joined.p, joined.b
    if (p <= -1).any() or (b <= -1).any():
        raise ValueError("Linking requires positive wealth")
    active = p - b
    P = float((1 + p).prod() - 1)
    B = float((1 + b).prod() - 1)
    if not np.allclose(joined[effects.columns].sum(axis=1), active, atol=1e-10):
        raise ValueError("Period effects do not reconcile to active returns")
    if method == "carino":
        k = np.where(
            np.abs(active) > 1e-12, (np.log1p(p) - np.log1p(b)) / active, 1 / (1 + p)
        )
        K = (np.log1p(P) - np.log1p(B)) / (P - B) if abs(P - B) > 1e-12 else 1 / (1 + P)
        factors = k / K
    elif method == "menchero":
        n = len(p)
        difference = (1 + P) ** (1 / n) - (1 + B) ** (1 / n)
        A = (
            (P - B) / n / difference
            if abs(difference) > 1e-12
            else (1 + P) ** ((n - 1) / n)
        )
        denominator = float(active.pow(2).sum())
        adjustment = (
            (P - B - A * active.sum()) / denominator if denominator > 1e-20 else 0
        )
        factors = A + adjustment * active
    elif method == "grap":
        preceding = (1 + p).cumprod().shift(1, fill_value=1)
        following = (1 + b).iloc[::-1].cumprod().iloc[::-1] / (1 + b)
        factors = preceding * following
    else:
        raise ValueError("Unknown linking method")
    linked = joined[effects.columns].mul(np.asarray(factors), axis=0)
    if not np.isclose(linked.sum().sum(), P - B, atol=1e-9):
        raise ValueError("Linked effects do not reconcile")
    return linked


def factor_attribution(active, factors):
    from .stats import newey_west_regression

    fit = newey_west_regression(active, factors)
    beta = {r["factor"]: r["beta"] for r in fit["coefficients"]}
    joined = factors.join(active.rename("active"), how="inner").dropna()
    rows = [
        {
            "component": c,
            "loading": beta[c],
            "mean_factor_return": float(joined[c].mean()),
            "contribution": float(beta[c] * joined[c].mean()),
        }
        for c in factors
    ]
    residual = float(joined.active.mean() - sum(r["contribution"] for r in rows))
    rows.append(
        {"component": "residual_alpha", "loading": None, "contribution": residual}
    )
    return rows, fit


def sector_selection_null(returns, weights, benchmark, sectors, draws=1000):
    """Within-sector permutation of observed holdings weights, not an iid time bootstrap."""
    rng = np.random.default_rng(17)
    w = weights.reindex(returns.columns).to_numpy()
    means = returns.mean().to_numpy()
    observed = float(w @ means - benchmark.mean())
    null = []
    groups = [
        np.array(
            [i for i, c in enumerate(returns) if sectors.get(c, "Unknown") == sector]
        )
        for sector in set(sectors.values())
    ]
    for _ in range(draws):
        perm = w.copy()
        for ids in groups:
            perm[ids] = rng.permutation(w[ids])
        null.append(float(perm @ means - benchmark.mean()))
    return {
        "observed_active_mean": observed,
        "p_value": float((1 + np.sum(np.asarray(null) >= observed)) / (draws + 1)),
        "draws": draws,
        "null_distribution": [
            {"sample": i, "active_mean": float(value)}
            for i, value in enumerate(null[:500])
        ],
        "null": "Permute holding weights within static sectors of the explicitly selected observed universe",
    }
