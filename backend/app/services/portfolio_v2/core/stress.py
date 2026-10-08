"""Observed FF5 crisis replay, stationary-bootstrap tails and reverse stress."""

import math
import numpy as np
from scipy import stats
from arch.bootstrap import StationaryBootstrap
from .data_loader import load_factor_returns
from .stats import portfolio_return_series, politis_romano_block

CRISES = {
    "dot_com": ("2000-03-01", "2002-10-31"),
    "gfc": ("2008-09-01", "2009-03-31"),
    "lehman": ("2008-09-15", "2008-09-26"),
    "euro_debt": ("2010-04-01", "2012-07-31"),
    "china_devaluation": ("2015-08-10", "2015-08-31"),
    "q4_2018": ("2018-10-01", "2018-12-31"),
    "covid": ("2020-02-19", "2020-04-30"),
    "rates_2022": ("2022-01-01", "2022-10-31"),
    "svb": ("2023-03-08", "2023-03-17"),
    "tariffs_2025": ("2025-04-02", "2025-04-30"),
}


def historical_crisis_replay(returns, weights):
    factors = load_factor_returns().set_index("date")
    cols = ["mkt_rf", "smb", "hml", "rmw", "cma"]
    joint = returns.tail(252).join(factors[cols], how="inner").dropna()
    if len(joint) < 30:
        raise ValueError("Insufficient actual FF5 exposure history")
    design = np.c_[np.ones(len(joint)), joint[cols].to_numpy()]
    betas = np.linalg.lstsq(design, joint[returns.columns].to_numpy(), rcond=None)[0][
        1:
    ]
    exposure = betas @ weights.reindex(returns.columns).to_numpy()
    rows = []
    for name, (start, end) in CRISES.items():
        f = factors.loc[start:end, cols].dropna()
        if len(f) == 0:
            rows.append(
                {
                    "scenario": name,
                    "status": "unavailable",
                    "reason": "No matching observed factor window",
                }
            )
            continue
        daily = f.to_numpy() @ exposure
        equity = np.cumprod(1 + daily)
        rows.append(
            {
                "scenario": name,
                "status": "ok",
                "return": float(equity[-1] - 1),
                "worst_day": float(daily.min()),
                "observations": len(f),
                "method": "Current trailing-year asset FF5 exposures times observed crisis factor sequences; residual returns excluded",
                "daily_path": [
                    {"date": date, "portfolio_return": float(value)}
                    for date, value in zip(f.index, daily)
                ],
            }
        )
    return rows


def stress_scenarios(returns, weights):
    port = portfolio_return_series(returns, weights)
    rows = []
    for q in [0.01, 0.025, 0.05, 0.1]:
        tail = port[port <= port.quantile(q)]
        rows.append(
            {
                "scenario": f"observed_daily_tail_{q:g}",
                "portfolio_return": float(tail.mean()),
                "pl_bps": float(tail.mean() * 10000),
                "method": "Observed tail conditional mean, not a named crisis",
            }
        )
    date = port.idxmin()
    contribution = returns.loc[date] * weights
    return {
        "scenario_table": rows,
        "waterfall": [
            {"component": c, "value": float(v), "date": date}
            for c, v in contribution.items()
        ],
    }


def stationary_block_bootstrap_paths(series, paths, horizon, block_length=None, seed=7):
    values = series.dropna().to_numpy()
    if len(values) < 20:
        raise ValueError("Bootstrap needs at least 20 finite observations")
    length = int(block_length or politis_romano_block(series))
    if length < 1:
        raise ValueError("Positive bootstrap block length required")
    # Extend with repeated observed values only for sampling length; circular blocks
    # always originate from the observed sample. arch owns the stationary resampling.
    bootstrap = StationaryBootstrap(length, values, seed=seed)
    out = []
    for positional, _ in bootstrap.bootstrap(paths):
        draw = positional[0]
        if horizon > len(draw):
            extra = []
            while len(draw) + sum(len(x) for x in extra) < horizon:
                extra.append(next(bootstrap.bootstrap(1))[0][0])
            draw = np.concatenate([draw, *extra])
        out.append(draw[:horizon])
    return np.asarray(out)


def minimum_mahalanobis_reverse_stress(returns, weights, loss_threshold):
    mu = returns.mean().to_numpy()
    cov = returns.cov().to_numpy()
    w = weights.reindex(returns.columns).to_numpy()
    denominator = float(w @ cov @ w)
    target = -abs(loss_threshold)
    if denominator <= 1e-14:
        raise ValueError("Reverse stress is unidentified for a zero-risk portfolio")
    shock = mu + cov @ w * ((target - w @ mu) / denominator)
    d2 = float((shock - mu) @ np.linalg.pinv(cov) @ (shock - mu))
    return {
        "target_loss": target,
        "portfolio_loss": float(w @ shock),
        "mahalanobis_distance": math.sqrt(max(d2, 0)),
        "plausibility_percentile": float(
            stats.chi2.cdf(d2, np.linalg.matrix_rank(cov))
        ),
        "asset_shocks": [
            {"ticker": c, "return": float(v)} for c, v in zip(returns.columns, shock)
        ],
        "probability_interpretation": "Gaussian ellipsoid severity percentile, not an annual event probability",
    }


def reverse_stress_test(returns, weights, loss_threshold=0.15):
    return minimum_mahalanobis_reverse_stress(returns, weights, loss_threshold)


def correlation_breakdown_stress(returns, weights, crisis_corr=0.75):
    n = len(returns.columns)
    if not -1 / max(n - 1, 1) <= crisis_corr <= 1:
        raise ValueError("Flat correlation must define a PSD matrix")
    vols = returns.std().to_numpy()
    corr = np.full((n, n), crisis_corr)
    np.fill_diagonal(corr, 1)
    covariance = corr * np.outer(vols, vols)
    w = weights.reindex(returns.columns).to_numpy()
    base = float(w @ returns.cov() @ w)
    stressed = float(w @ covariance @ w)
    return {
        "current_daily_vol": math.sqrt(max(base, 0)),
        "stressed_daily_vol": math.sqrt(max(stressed, 0)),
        "variance_increase": stressed - base,
        "crisis_corr": crisis_corr,
        "assumption": "User-declared flat correlation scenario",
    }
