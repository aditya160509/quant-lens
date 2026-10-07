"""Observed historical stress replay and explicitly assumed Gaussian risk scenarios."""

from __future__ import annotations

import numpy as np
import pandas as pd
from .dcc import correlation

PRESETS = {
    "gfc": ("2008-09-01", "2008-12-31"),
    "covid": ("2020-02-15", "2020-03-31"),
    "covid_recovery": ("2020-04-01", "2020-06-30"),
    "taper_tantrum": ("2013-06-01", "2013-06-30"),
    "em_crisis": ("2015-08-01", "2015-08-31"),
    "rate_shock_2022": ("2022-10-01", "2022-10-31"),
    "liberation_day_2025": ("2025-04-01", "2025-05-31"),
}


def replay(returns, weights, start, end, annualization=252):
    """Constant weights, rebalanced each observed day; exact cumulative contributions."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start > end or annualization <= 0:
        raise ValueError("Invalid stress dates or annualization")
    if returns.index.min() > start or returns.index.max() < end:
        raise ValueError(
            f"Historical episode {start.date()} to {end.date()} is not covered by aligned observed returns"
        )
    episode = returns.loc[start:end]
    if len(episode) < 10 or not np.isfinite(episode.to_numpy()).all():
        raise ValueError(
            "Historical stress requires at least 10 finite aligned observed returns"
        )
    vector = weights.reindex(returns.columns).to_numpy(dtype=float)
    if not np.isfinite(vector).all():
        raise ValueError("Stress weights must match the portfolio assets")
    daily = episode.to_numpy() @ vector
    if (daily <= -1).any():
        raise ValueError("Historical portfolio NAV became nonpositive")
    nav = np.cumprod(1 + daily)
    before = np.r_[1.0, nav[:-1]]
    contribution = (episode.to_numpy() * vector * before[:, None]).sum(axis=0)
    drawdown = nav / np.maximum.accumulate(np.r_[1.0, nav])[1:] - 1
    trough = int(np.argmin(drawdown))
    peak = float(np.max(np.r_[1.0, nav[: trough + 1]]))
    # Continue the same weighted historical portfolio after the episode, rather
    # than invent a recovery duration from a volatility multiplier.
    continuation = returns.loc[episode.index[trough] :].iloc[1:].to_numpy() @ vector
    if (continuation <= -1).any():
        recovery = None
        recovery_reason = "Portfolio NAV became nonpositive after the trough"
    else:
        future_nav = nav[trough] * np.cumprod(1 + continuation)
        crossings = np.flatnonzero(future_nav >= peak)
        recovery = int(crossings[0] + 1) if len(crossings) else None
        recovery_reason = (
            None
            if recovery is not None
            else "Right-censored at the last observed return"
        )
    if drawdown.min() >= -1e-12:
        recovery, recovery_reason = 0, None
    covariance = episode.cov() * annualization
    baseline = (
        returns.iloc[
            max(0, returns.index.searchsorted(start) - 21) : returns.index.searchsorted(
                start
            )
        ]
        @ weights
    )
    trailing = (returns @ weights).rolling(21, min_periods=21).std(ddof=1) * np.sqrt(
        annualization
    )
    post = trailing.loc[episode.index[-1] :].iloc[1:]
    baseline_vol = (
        float(baseline.std(ddof=1) * np.sqrt(annualization))
        if len(baseline) == 21
        else None
    )
    vol_crossings = (
        np.flatnonzero(post.to_numpy() <= baseline_vol)
        if baseline_vol is not None
        else []
    )
    return {
        "start": episode.index[0],
        "end": episode.index[-1],
        "observations": len(episode),
        "portfolio_return": float(nav[-1] - 1),
        "maximum_drawdown": float(drawdown.min()),
        "worst_cumulative_return": float(nav.min() - 1),
        "portfolio_volatility": float(np.std(daily, ddof=1) * np.sqrt(annualization)),
        "asset_returns": (1 + episode).prod() - 1,
        "covariance": covariance,
        "daily_mean": episode.mean(),
        "asset_volatility": episode.std(ddof=1) * np.sqrt(annualization),
        "attribution": [
            {"asset": asset, "cumulative_return_contribution": float(contribution[i])}
            for i, asset in enumerate(returns.columns)
        ],
        "path": [
            {
                "date": date,
                "portfolio_return": float(daily[i]),
                "nav": float(nav[i]),
                "drawdown": float(drawdown[i]),
            }
            for i, date in enumerate(episode.index)
        ],
        "nav_recovery_days": recovery,
        "nav_recovery_reason": recovery_reason,
        "volatility_recovery_days": int(vol_crossings[0] + 1)
        if len(vol_crossings)
        else None,
        "volatility_recovery_reason": None
        if len(vol_crossings)
        else "No observed post-episode recovery to the 21-session pre-episode volatility baseline",
        "replay_policy": "USD simple returns, constant weights rebalanced each observed date, no transaction costs",
    }


def gaussian_stress(
    covariance,
    weights,
    daily_mean=None,
    horizon=1,
    paths=20000,
    aum=1e8,
    annualization=252,
    seed=7,
):
    """Scenario risk is a declared model assumption, not a historical return replay."""
    if (
        not 1 <= horizon <= 252
        or not 1000 <= paths <= 200000
        or aum <= 0
        or annualization <= 0
    ):
        raise ValueError(
            "Invalid stress simulation horizon, path count, AUM or annualization"
        )
    matrix = covariance.to_numpy(dtype=float)
    correlation(matrix)
    vector = weights.reindex(covariance.columns).to_numpy(dtype=float)
    mean = (
        np.zeros(len(vector))
        if daily_mean is None
        else daily_mean.reindex(covariance.columns).to_numpy(dtype=float)
    )
    if not np.isfinite(mean).all() or not np.isfinite(vector).all():
        raise ValueError("Simulation mean and weights must be finite")
    sigma = np.sqrt(vector @ matrix @ vector / annualization)
    drift = float(vector @ mean)
    rng = np.random.default_rng(seed)
    wealth = np.ones(paths)
    for _ in range(horizon):
        wealth *= 1 + rng.normal(drift, sigma, paths)
    terminal = wealth - 1
    quantiles = np.quantile(terminal, [0.01, 0.05])
    row = {
        "var_99": float(quantiles[0]),
        "var_95": float(quantiles[1]),
        "cvar_99": float(terminal[terminal <= quantiles[0]].mean()),
        "cvar_95": float(terminal[terminal <= quantiles[1]].mean()),
        "paths": paths,
        "horizon_sessions": horizon,
        "aum_usd": aum,
        "scenario_annualized_volatility": float(sigma * np.sqrt(annualization)),
        "daily_portfolio_mean": drift,
        "distribution": "IID Gaussian daily simple portfolio returns, compounded over the selected horizon",
        "sign_convention": "Signed return quantiles; negative numbers are losses",
    }
    for key in ("var_99", "var_95", "cvar_99", "cvar_95"):
        row[f"{key}_usd"] = row[key] * aum
    return row, [
        {"quantile": float(p), "portfolio_return": float(value)}
        for p, value in zip(
            np.linspace(0.01, 0.99, 99),
            np.quantile(terminal, np.linspace(0.01, 0.99, 99)),
        )
    ]
