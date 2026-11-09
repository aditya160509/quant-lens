"""Portfolio V2 stats engine."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def portfolio_return_series(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=np.float64)
    arr = returns.to_numpy(dtype=np.float64)
    if not np.isfinite(arr[:, w != 0]).all():
        raise ValueError("Missing returns for held positions")
    return pd.Series(arr[:, w != 0] @ w[w != 0], index=returns.index)


def performance_metrics(series, ann=252):
    r = pd.Series(series).dropna().astype(float)
    if len(r) < 2 or not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError("At least two finite simple returns above -100% are required")
    mu = float(r.mean())
    sigma = float(r.std(ddof=1))
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax().clip(lower=1) - 1
    downside = float(np.sqrt(np.minimum(r, 0).pow(2).mean()))
    q = float(r.quantile(0.05))
    cvar = float(r[r <= q].mean())
    cagr = float(eq.iloc[-1] ** (ann / len(r)) - 1)
    positive = r[r > 0]
    negative = r[r < 0]
    losses = float(-negative.sum())
    q01 = float(r.quantile(0.01))
    q95 = float(r.quantile(0.95))
    underwater = dd < 0
    runs = underwater.groupby((~underwater).cumsum()).sum()
    return {
        "cumulative_return": float(eq.iloc[-1] - 1),
        "mean_period_return": mu,
        "median_period_return": float(r.median()),
        "period_volatility": sigma,
        "annual_downside_deviation": downside * np.sqrt(ann),
        "worst_period_return": float(r.min()),
        "best_period_return": float(r.max()),
        "positive_period_fraction": float((r > 0).mean()),
        "negative_period_fraction": float((r < 0).mean()),
        "zero_period_fraction": float((r == 0).mean()),
        "mean_positive_return": float(positive.mean()) if len(positive) else None,
        "mean_negative_return": float(negative.mean()) if len(negative) else None,
        "payoff_ratio": float(positive.mean() / abs(negative.mean()))
        if len(positive) and len(negative)
        else None,
        "profit_factor": float(positive.sum() / losses) if losses > 0 else None,
        "gain_to_pain_ratio": float(r.sum() / losses) if losses > 0 else None,
        "tail_ratio_95_05": q95 / abs(q) if q < 0 else None,
        "var_99": q01,
        "cvar_99": float(r[r <= q01].mean()),
        "average_underwater_drawdown": float(dd[underwater].mean())
        if underwater.any()
        else None,
        "longest_drawdown_observations": int(runs.max()) if len(runs) else 0,
        "ending_wealth_per_unit": float(eq.iloc[-1]),
        "annual_return": mu * ann,
        "cagr": cagr,
        "annual_vol": sigma * np.sqrt(ann),
        "sharpe": mu / sigma * np.sqrt(ann) if sigma > 0 else None,
        "sortino": mu / downside * np.sqrt(ann) if downside > 0 else None,
        "max_drawdown": float(dd.min()),
        "var_95": q,
        "cvar_95": cvar,
        "skew": float(stats.skew(r, bias=False)) if sigma > 1e-12 else None,
        "kurtosis": float(stats.kurtosis(r, bias=False)) if sigma > 1e-12 else None,
        "observations": len(r),
    }


def pbo_cscv(
    strategy_returns: pd.DataFrame, n_splits: int = 8, max_combinations: int = 5_000
) -> dict[str, Any]:
    """Combinatorially symmetric cross-validation with bounded enumeration.

    Every admissible half-sample is evaluated when feasible.  For larger
    partitions a deterministic sample prevents an exponential request from
    blocking a realtime feature run.
    """
    if strategy_returns.empty or strategy_returns.shape[1] < 2:
        return {"pbo": None, "distribution": []}
    from itertools import combinations

    if (
        n_splits < 2
        or n_splits % 2
        or n_splits > 16
        or len(strategy_returns) < 2 * n_splits
    ):
        raise ValueError(
            "CSCV requires 2-16 even partitions and at least two observations per partition"
        )
    if strategy_returns.isna().any().any():
        raise ValueError("CSCV needs aligned complete strategy returns")
    chunks = [
        strategy_returns.iloc[idx]
        for idx in np.array_split(np.arange(len(strategy_returns)), n_splits)
    ]
    half = len(chunks) // 2
    combinations_all = list(combinations(range(len(chunks)), half))
    if len(combinations_all) > max_combinations:
        rng = np.random.default_rng(7)
        selected = rng.choice(
            len(combinations_all), size=max_combinations, replace=False
        )
        combinations_all = [combinations_all[int(i)] for i in np.sort(selected)]
    rows, logits = [], []
    for i, train_idx in enumerate(combinations_all):
        train_set = set(train_idx)
        train = pd.concat([chunks[j] for j in train_idx])
        test = pd.concat([chunks[j] for j in range(len(chunks)) if j not in train_set])
        tr = train.mean() / train.std().replace(0, np.nan)
        te = test.mean() / test.std().replace(0, np.nan)
        if tr.isna().any() or te.isna().any():
            raise ValueError("CSCV Sharpe is undefined for constant strategy returns")
        winner = tr.idxmax()
        rank = te.rank(method="average").get(winner) / (len(te) + 1)
        logit = math.log(max(rank, 1e-6) / max(1 - rank, 1e-6))
        logits.append(logit)
        rows.append(
            {
                "combination": i + 1,
                "train_blocks": list(train_idx),
                "train_winner": winner,
                "test_percentile": float(rank),
                "logit": float(logit),
            }
        )
    return {
        "pbo": float(np.mean(np.asarray(logits) <= 0)),
        "distribution": rows,
        "combination_count": len(rows),
        "partition_count": len(chunks),
        "total_combinations": math.comb(n_splits, n_splits // 2),
        "sampled": len(rows) < math.comb(n_splits, n_splits // 2),
    }


def value_at_risk_methods(
    series: pd.Series, confidence: float = 0.95, simulations: int = 10_000
) -> list[dict[str, float | str]]:
    r = series.dropna().to_numpy(dtype=float)
    if not len(r):
        return []
    alpha = 1.0 - float(confidence)
    historical = float(np.quantile(r, alpha))
    hs_tail = r[r <= historical]
    mu, sigma = float(r.mean()), float(r.std(ddof=1))
    parametric = float(stats.norm.ppf(alpha, loc=mu, scale=max(sigma, 1e-12)))
    rng = np.random.default_rng(19)
    simulated = rng.normal(mu, sigma, min(max(int(simulations), 1000), 50_000))
    mc = float(np.quantile(simulated, alpha))
    z = float(stats.norm.ppf(alpha))
    skew = float(stats.skew(r, bias=False))
    kurtosis = float(stats.kurtosis(r, bias=False))

    def cf(x):
        return (
            x
            + (x * x - 1) * skew / 6
            + (x**3 - 3 * x) * kurtosis / 24
            - (2 * x**3 - 5 * x) * skew**2 / 36
        )

    grid = np.linspace(stats.norm.ppf(0.0001), stats.norm.ppf(0.9999), 1000)
    identified = (
        len(r) >= 30
        and np.isfinite([skew, kurtosis]).all()
        and (np.diff(cf(grid)) >= 0).all()
    )
    cornish_fisher = {
        "method": "cornish_fisher",
        "var": float(mu + sigma * cf(z)) if identified else None,
        "cvar": None,
        "status": "ok" if identified else "unavailable",
        "reason": "Moment expansion VaR only; no CVaR approximation reported"
        if identified
        else "Insufficient moments or nonmonotonic Cornish-Fisher quantile expansion",
    }
    return [
        cornish_fisher,
        {
            "method": "historical",
            "var": historical,
            "cvar": float(hs_tail.mean()) if len(hs_tail) else historical,
        },
        {
            "method": "parametric_normal",
            "var": parametric,
            "cvar": float(mu - sigma * stats.norm.pdf(stats.norm.ppf(alpha)) / alpha),
        },
        {
            "method": "monte_carlo_normal",
            "var": mc,
            "cvar": float(simulated[simulated <= mc].mean()),
        },
    ]


def probabilistic_sharpe(sharpe, n_obs, benchmark=0, skew=0, excess_kurtosis=0):
    if n_obs < 2:
        raise ValueError("Sharpe inference requires at least two observations")
    variance = (1 - skew * sharpe + (excess_kurtosis + 2) * sharpe**2 / 4) / (n_obs - 1)
    if n_obs < 2 or variance <= 0:
        raise ValueError("Sharpe inference variance is not identified")
    return float(stats.norm.cdf((sharpe - benchmark) / math.sqrt(variance)))


def deflated_sharpe_ratio(
    sharpe, n_obs, trials, skew=0, excess_kurtosis=0, trial_variance=None
):
    if trials < 1:
        raise ValueError("At least one actual strategy trial required")
    variance = 1 / (n_obs - 1) if trial_variance is None else float(trial_variance)
    if variance < 0:
        raise ValueError("Trial Sharpe variance cannot be negative")
    gamma = 0.5772156649015329
    null = (
        math.sqrt(variance)
        * (
            (1 - gamma) * stats.norm.ppf(1 - 1 / trials)
            + gamma * stats.norm.ppf(1 - 1 / (trials * math.e))
        )
        if trials > 1
        else 0
    )
    return probabilistic_sharpe(sharpe, n_obs, null, skew, excess_kurtosis)


def min_track_record_length(sharpe, benchmark_sr=0, alpha=0.05, skew=0, kurtosis=3):
    if sharpe <= benchmark_sr:
        return None
    return float(
        1
        + (1 - skew * sharpe + (kurtosis - 1) * sharpe**2 / 4)
        * (stats.norm.ppf(1 - alpha) / (sharpe - benchmark_sr)) ** 2
    )


def harvey_liu_correction(
    sharpe, trials=1, alpha=0.05, n_obs=252, skew=0, excess_kurtosis=0
):
    # Bonferroni family-wise Sharpe test, explicitly named, not a mislabeled HLZ estimator.
    adjusted_alpha = alpha / trials
    se = math.sqrt(
        (1 - skew * sharpe + (excess_kurtosis + 2) * sharpe**2 / 4) / (n_obs - 1)
    )
    threshold = float(stats.norm.ppf(1 - adjusted_alpha) * se)
    return {
        "method": "Bonferroni one-sided Sharpe test",
        "adjusted_alpha": adjusted_alpha,
        "period_sharpe_threshold": threshold,
        "passes": bool(sharpe > threshold),
    }


def omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
    r = returns.dropna() - threshold
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return float(gains / losses) if losses > 0 else None


def ulcer_index(returns: pd.Series) -> float:
    eq = (1 + returns.dropna()).cumprod()
    dd = eq / eq.cummax().clip(lower=1) - 1
    return float(np.sqrt(np.mean(np.square(dd))))


def calmar_ratio(returns: pd.Series, ann: float = 252.0) -> float:
    m = performance_metrics(returns, ann)
    return float(m["cagr"] / abs(m["max_drawdown"])) if m["max_drawdown"] < 0 else None


def up_down_capture(portfolio: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    joined = pd.concat([portfolio.rename("p"), benchmark.rename("b")], axis=1).dropna()
    up = joined[joined["b"] > 0]
    down = joined[joined["b"] < 0]
    return {
        "up_capture": float(up["p"].mean() / max(up["b"].mean(), 1e-12))
        if not up.empty
        else None,
        "down_capture": float(down["p"].mean() / min(down["b"].mean(), -1e-12))
        if not down.empty
        else None,
    }


def politis_romano_block(returns):
    from arch.bootstrap import optimal_block_length

    r = returns.dropna()
    if len(r) < 20:
        raise ValueError("Block-length selection requires at least 20 observations")
    value = float(optimal_block_length(r).stationary.iloc[0])
    return max(1, int(np.ceil(value)))


def newey_west_regression(y, x, lags=4):
    import statsmodels.api as sm

    joined = (
        pd.concat([y.rename("y"), x], axis=1, sort=False)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(joined) <= x.shape[1] + 2:
        raise ValueError("Insufficient complete observations for regression")
    design = sm.add_constant(joined[x.columns], has_constant="add")
    if np.linalg.matrix_rank(design.to_numpy()) < design.shape[1]:
        raise ValueError("Regression design is rank-deficient")
    fit = sm.OLS(joined.y, design).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "coefficients": [
            {
                "factor": "intercept" if c == "const" else c,
                "beta": float(fit.params[c]),
                "se": float(fit.bse[c]),
                "t": float(fit.tvalues[c]),
                "p_value": float(fit.pvalues[c]),
            }
            for c in design
        ],
        "r2": float(fit.rsquared),
        "observations": len(joined),
    }
