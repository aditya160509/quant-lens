"""Portfolio V2 decay engine."""

from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def decay_model_selection(ic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fit exponential, hyperbolic and stretched-exponential IC decay models."""
    if len(ic_rows) < 4:
        return []
    h = np.asarray([r["horizon"] for r in ic_rows], dtype=float)
    y = np.abs(np.asarray([r["ic"] for r in ic_rows], dtype=float))
    y = np.maximum(y, 1e-10)
    candidates = []
    models = {
        "linear": (
            lambda p: np.maximum(p[0] - p[1] * h, 0),
            [y[0], y[0] / max(h[-1], 1)],
        ),
        "exponential": (
            lambda p: p[0] * np.exp(-h / max(p[1], 1e-9)),
            [y[0], max(np.median(h), 1.0)],
        ),
        "hyperbolic": (
            lambda p: p[0] / (1.0 + h / max(p[1], 1e-9)),
            [y[0], max(np.median(h), 1.0)],
        ),
        "stretched_exponential": (
            lambda p: p[0] * np.exp(-np.power(h / max(p[1], 1e-9), max(p[2], 0.05))),
            [y[0], max(np.median(h), 1.0), 0.8],
        ),
    }
    for name, (func, init) in models.items():
        result = minimize(
            lambda p: float(np.square(y - func(p)).sum()),
            init,
            bounds=[(1e-12, None)] * len(init),
            method="L-BFGS-B",
        )
        if result.success:
            rss = max(float(result.fun), 1e-18)
            candidates.append(
                {
                    "model": name,
                    "parameters": [float(v) for v in result.x],
                    "aic": float(len(y) * math.log(rss / len(y)) + 2 * len(init)),
                    "rss": rss,
                }
            )
    return sorted(candidates, key=lambda row: row["aic"])


def empirical_ic(returns, signals, max_horizon=63, draws=200):
    from scipy.stats import spearmanr
    from arch.bootstrap import StationaryBootstrap
    from .stats import politis_romano_block

    if returns.shape[1] < 3:
        raise ValueError("Cross-sectional IC requires at least three assets")
    records = []
    for h in range(1, max_horizon + 1):
        future = np.expm1(np.log1p(returns).rolling(h).sum().shift(-h))
        scores = []
        dates = []
        for date in returns.index:
            joined = pd.concat([signals.loc[date], future.loc[date]], axis=1).dropna()
            if (
                len(joined) < 3
                or joined.iloc[:, 0].nunique() < 2
                or joined.iloc[:, 1].nunique() < 2
            ):
                continue
            scores.append(
                float(spearmanr(joined.iloc[:, 0], joined.iloc[:, 1]).statistic)
            )
            dates.append(date)
        if len(scores) < 30:
            records.append(
                {
                    "horizon": h,
                    "ic": None,
                    "observations": len(scores),
                    "reason": "Fewer than 30 observed formation dates with nonconstant scores and matured labels",
                }
            )
            continue
        sample = pd.Series(scores, index=dates)
        length = politis_romano_block(sample)
        bootstrap = StationaryBootstrap(length, np.array(scores), seed=17)
        means = [
            float(positional[0].mean()) for positional, _ in bootstrap.bootstrap(draws)
        ]
        low, high = np.quantile(means, [0.025, 0.975])
        records.append(
            {
                "horizon": h,
                "ic": float(sample.mean()),
                "lower": float(low),
                "upper": float(high),
                "observations": len(scores),
                "bootstrap_block_length": length,
                "latest_matured_origin": dates[-1],
            }
        )
    return records


def publication_mean_shift(returns, signals, publication_date):
    """HAC mean-shift test on actual one-interval ICs matured by the cutoff."""
    import statsmodels.api as sm
    from scipy.stats import spearmanr

    date = pd.Timestamp(publication_date)
    future = returns.shift(-1)
    rows = []
    for origin in returns.index[:-1]:
        joined = pd.concat([signals.loc[origin], future.loc[origin]], axis=1).dropna()
        if (
            len(joined) >= 3
            and joined.iloc[:, 0].nunique() > 1
            and joined.iloc[:, 1].nunique() > 1
        ):
            rows.append(
                (
                    origin,
                    float(spearmanr(joined.iloc[:, 0], joined.iloc[:, 1]).statistic),
                )
            )
    sample = pd.Series(dict(rows), dtype=float).sort_index()
    pre, post = sample.loc[sample.index < date], sample.loc[sample.index >= date]
    if min(len(pre), len(post)) < 30:
        return [
            {
                "status": "unavailable",
                "reason": "Publication mean-shift test needs at least 30 matured formation ICs on each side",
                "pre_observations": len(pre),
                "post_observations": len(post),
            }
        ]
    indicator = pd.Series(
        (sample.index >= date).astype(float), index=sample.index, name="post"
    )
    fit = sm.OLS(sample, sm.add_constant(indicator)).fit(
        cov_type="HAC", cov_kwds={"maxlags": 4}
    )
    return [
        {
            "status": "ok",
            "publication_date": date,
            "method": "OLS post-publication mean shift with Newey-West HAC(4); supplied publication date, not an inferred event",
            "pre_mean_ic": float(pre.mean()),
            "post_mean_ic": float(post.mean()),
            "mean_shift": float(fit.params.post),
            "t_statistic": float(fit.tvalues.post),
            "p_value": float(fit.pvalues.post),
            "pre_observations": len(pre),
            "post_observations": len(post),
        }
    ]
