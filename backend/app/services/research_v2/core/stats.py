"""Inference primitives for Research V2.

Everything here is a standard, citable procedure:

* Newey-West (1987) HAC standard errors with Bartlett weights.
* Stationary bootstrap (Politis-Romano 1994) via ``arch``.
* Patton-Timmermann (2010) monotonic-relation (MR) test.
* Chow (1960) structural-difference test on regression coefficients.
* Andrews (1993) sup-F test with asymptotic p-values simulated from the
  limiting Brownian-bridge process, and a Bai (1997) break-date interval.
"""

from __future__ import annotations

from functools import lru_cache
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def nw_se(series: pd.Series | np.ndarray, lag: int = 4) -> float:
    """Newey-West standard error of the sample mean."""

    x = pd.Series(series).dropna().astype(float).to_numpy()
    n = len(x)
    if n < 3:
        return np.nan
    xc = x - x.mean()
    max_lag = max(0, min(int(lag), n - 1))
    var = float(xc @ xc) / n
    for lag_i in range(1, max_lag + 1):
        weight = 1 - lag_i / (max_lag + 1)
        var += 2 * weight * float(xc[lag_i:] @ xc[:-lag_i]) / n
    return math.sqrt(max(var, 0.0) / n)


def mean_test(series: pd.Series | np.ndarray, lag: int = 4) -> dict[str, float]:
    """Mean, NW SE, t and two-sided p for H0: mean = 0."""

    x = pd.Series(series).dropna().astype(float)
    n = len(x)
    mean = float(x.mean()) if n else np.nan
    se = nw_se(x, lag)
    t = mean / se if se and np.isfinite(se) and se > 0 else np.nan
    p = float(2 * stats.t.sf(abs(t), max(1, n - 1))) if np.isfinite(t) else np.nan
    return {"mean": mean, "se": se, "t": t, "p": p, "n": n}


def auto_nw_lag(n: int) -> int:
    """Newey-West (1994) plug-in lag floor(4 (n/100)^(2/9))."""

    return int(max(1, math.floor(4 * (max(n, 1) / 100) ** (2 / 9))))


def ols(y: pd.Series, x: pd.DataFrame, cov: str = "nonrobust", lags: int | None = None, groups: Any = None, add_const: bool = True) -> dict[str, Any]:
    """statsmodels OLS with a chosen covariance. Returns plain arrays keyed by name."""

    frame = pd.concat([pd.Series(y, name="__y"), pd.DataFrame(x)], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    names = [c for c in frame.columns if c != "__y"]
    import statsmodels.api as sm

    exog = sm.add_constant(frame[names], has_constant="add") if add_const else frame[names]
    if len(frame) <= exog.shape[1] + 2:
        empty = pd.Series(np.nan, index=exog.columns)
        return {"params": empty, "bse": empty, "tvalues": empty, "pvalues": empty, "rsquared": np.nan, "rsquared_adj": np.nan, "nobs": len(frame), "resid": pd.Series(dtype=float), "fitted": pd.Series(dtype=float), "ssr": np.nan, "model": None}
    model = sm.OLS(frame["__y"], exog)
    if cov == "hac":
        fit = model.fit(cov_type="HAC", cov_kwds={"maxlags": int(lags if lags is not None else auto_nw_lag(len(frame)))})
    elif cov == "cluster" and groups is not None:
        # ``groups`` is a Series (or DataFrame for two-way) aligned to ``y``'s index.
        fit = model.fit(cov_type="cluster", cov_kwds={"groups": pd.DataFrame(groups).reindex(frame.index).apply(lambda c: pd.factorize(c)[0]).to_numpy().squeeze()})
    elif cov == "hc1":
        fit = model.fit(cov_type="HC1")
    else:
        fit = model.fit()
    return {"params": fit.params, "bse": fit.bse, "tvalues": fit.tvalues, "pvalues": fit.pvalues, "rsquared": float(fit.rsquared), "rsquared_adj": float(fit.rsquared_adj), "nobs": int(fit.nobs), "resid": fit.resid, "fitted": fit.fittedvalues, "ssr": float(fit.ssr), "model": fit}


def default_block_length(n: int) -> float:
    return float(max(2, round(n ** (1 / 3))))


def stationary_bootstrap_means(data: np.ndarray, reps: int, block: float | None = None, seed: int = 0) -> np.ndarray:
    """Bootstrap distribution of column means under the stationary bootstrap."""

    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    arr = arr[np.isfinite(arr).all(axis=1)]
    if len(arr) < 8:
        return np.empty((0, arr.shape[1]))
    from arch.bootstrap import StationaryBootstrap

    bs = StationaryBootstrap(block or default_block_length(len(arr)), arr, seed=seed)
    return np.asarray([pos[0].mean(axis=0) for pos, _ in bs.bootstrap(int(reps))])


def bootstrap_mean_pvalue(series: pd.Series, reps: int = 1000, block: float | None = None, seed: int = 0) -> float:
    """Two-sided stationary-bootstrap p-value for H0: mean = 0 (recentred)."""

    x = pd.Series(series).dropna().to_numpy(dtype=float)
    if len(x) < 8:
        return np.nan
    boot = stationary_bootstrap_means(x, reps, block, seed)[:, 0]
    centered = boot - x.mean()
    return float(np.mean(np.abs(centered) >= abs(x.mean())))


def monotonic_relation_test(port_rets: pd.DataFrame, reps: int = 1000, block: float | None = None, seed: int = 0) -> dict[str, Any]:
    """Patton-Timmermann (2010) MR test.

    H0: expected returns are not monotonically increasing (min_i delta_i <= 0).
    H1: delta_i = mu_{i+1} - mu_i > 0 for all i. The direction is chosen from the
    sign of the top-minus-bottom spread and tested on the correspondingly
    ordered portfolios. Bootstrap statistics are recentred at the sample
    deltas so the null distribution is correct under the least favourable
    configuration.
    """

    cols = [c for c in port_rets.columns if str(c).startswith("Q")]
    data = port_rets[cols].dropna()
    if len(cols) < 3 or len(data) < 24:
        return {"available": False, "reason": "needs >= 3 portfolios and >= 24 periods"}
    values = data.to_numpy(dtype=float)
    mu = values.mean(axis=0)
    direction = "increasing" if mu[-1] >= mu[0] else "decreasing"
    if direction == "decreasing":
        values = values[:, ::-1]
        mu = mu[::-1]
    delta = np.diff(mu)
    stat = float(delta.min())
    boot_means = stationary_bootstrap_means(values, reps, block, seed)
    boot_delta = np.diff(boot_means, axis=1) - delta
    boot_stat = boot_delta.min(axis=1)
    p = float(np.mean(boot_stat >= stat))
    ls = port_rets["long_short"] if "long_short" in port_rets else data[cols[-1]] - data[cols[0]]
    tmb = mean_test(ls, auto_nw_lag(len(ls.dropna())))
    return {
        "available": True,
        "direction_tested": direction,
        "mr_statistic": stat,
        "bootstrap_p_value": p,
        "adjacent_pairs_ordered": float((delta > 0).mean()),
        "adjacent_pairs": int(len(delta)),
        "top_minus_bottom_t": tmb["t"],
        "top_minus_bottom_p": tmb["p"],
        "replications": int(len(boot_stat)),
        "block_length": float(block or default_block_length(len(values))),
        "verdict": "monotonic" if p < 0.05 else "not monotonic at 5%",
    }


def chow_test(y: pd.Series, x: pd.DataFrame, split: pd.Series) -> dict[str, Any]:
    """Chow F-test that the regression coefficients differ between two groups."""

    frame = pd.concat([pd.Series(y, name="__y"), pd.DataFrame(x), pd.Series(split, name="__g").astype(float)], axis=1).dropna()
    xcols = [c for c in frame.columns if c not in {"__y", "__g"}]
    k = len(xcols) + 1
    g1 = frame[frame["__g"] > 0.5]
    g0 = frame[frame["__g"] <= 0.5]
    if len(g1) <= k + 2 or len(g0) <= k + 2:
        return {"f_stat": np.nan, "p_value": np.nan, "df1": k, "df2": np.nan, "n1": len(g1), "n0": len(g0)}
    rss_p = ols(frame["__y"], frame[xcols])["ssr"]
    rss_1 = ols(g1["__y"], g1[xcols])["ssr"]
    rss_0 = ols(g0["__y"], g0[xcols])["ssr"]
    df2 = len(frame) - 2 * k
    f = ((rss_p - rss_1 - rss_0) / k) / ((rss_1 + rss_0) / df2)
    return {"f_stat": float(f), "p_value": float(stats.f.sf(f, k, df2)), "df1": k, "df2": int(df2), "n1": int(len(g1)), "n0": int(len(g0))}


@lru_cache(maxsize=16)
def _supf_null(k: int, trim: float, reps: int = 4000, grid: int = 1000, seed: int = 11) -> np.ndarray:
    """Draws from Andrews' (1993) limiting distribution of sup-Wald / k."""

    rng = np.random.default_rng(seed)
    steps = rng.standard_normal((reps, grid, k)) / math.sqrt(grid)
    w = np.cumsum(steps, axis=1)
    pi = np.arange(1, grid + 1) / grid
    lo, hi = int(trim * grid), int((1 - trim) * grid)
    bridge = w[:, lo:hi, :] - pi[lo:hi, None] * w[:, -1:, :]
    q = (bridge ** 2).sum(axis=2) / (pi[lo:hi] * (1 - pi[lo:hi]))
    return q.max(axis=1) / k


def andrews_sup_f(y: pd.Series, x: pd.DataFrame | None = None, trim: float = 0.15) -> dict[str, Any]:
    """Andrews (1993) sup-F test for one unknown break in a linear regression.

    Without ``x`` the model is a mean-shift model. Returns the F path, the
    supremum, its asymptotic p-value and 5% critical value, and a Bai (1997)
    90% confidence interval for the break date (mean-shift approximation).
    """

    yy = pd.Series(y).dropna().astype(float)
    xx = pd.DataFrame(index=yy.index) if x is None else pd.DataFrame(x).reindex(yy.index)
    frame = pd.concat([yy.rename("__y"), xx], axis=1).dropna()
    n = len(frame)
    xcols = [c for c in frame.columns if c != "__y"]
    k = len(xcols) + 1
    if n < max(24, 4 * k):
        return {"path": pd.DataFrame(), "sup_f": np.nan, "p_value": np.nan, "break_date": None}
    xm = np.column_stack([np.ones(n), frame[xcols].to_numpy(dtype=float)]) if xcols else np.ones((n, 1))
    yv = frame["__y"].to_numpy(dtype=float)

    def rss(a: np.ndarray, b: np.ndarray) -> float:
        beta, *_ = np.linalg.lstsq(a, b, rcond=None)
        r = b - a @ beta
        return float(r @ r)

    rss_full = rss(xm, yv)
    rows = []
    for i in range(max(k + 1, int(n * trim)), min(n - k - 1, int(n * (1 - trim))) + 1):
        rss_split = rss(xm[:i], yv[:i]) + rss(xm[i:], yv[i:])
        f = ((rss_full - rss_split) / k) / (rss_split / (n - 2 * k))
        rows.append({"date": frame.index[i], "f_stat": f})
    path = pd.DataFrame(rows)
    if path.empty:
        return {"path": path, "sup_f": np.nan, "p_value": np.nan, "break_date": None}
    null = _supf_null(k, trim)
    crit5 = float(np.quantile(null, 0.95))
    best = path.loc[path["f_stat"].idxmax()]
    sup_f = float(best["f_stat"])
    pos = int(frame.index.get_loc(best["date"]))
    pre, post = yv[:pos], yv[pos:]
    delta = post.mean() - pre.mean()
    sigma2 = float(np.concatenate([pre - pre.mean(), post - post.mean()]).var())
    half = int(math.ceil(7.69 * sigma2 / delta ** 2)) if delta else n
    lo_i, hi_i = max(0, pos - half), min(n - 1, pos + half)
    path["critical_5pct"] = crit5
    return {
        "path": path,
        "sup_f": sup_f,
        "p_value": float(np.mean(null >= sup_f)),
        "critical_5pct": crit5,
        "break_date": best["date"],
        "break_ci90_low": frame.index[lo_i],
        "break_ci90_high": frame.index[hi_i],
        "pre_mean": float(pre.mean()),
        "post_mean": float(post.mean()),
        "parameters": k,
        "trim": trim,
    }


def fisher_stouffer(p_values: list[float]) -> dict[str, Any]:
    vals = np.array([p for p in p_values if np.isfinite(p)], dtype=float).clip(1e-300, 1 - 1e-16)
    if len(vals) == 0:
        return {"fisher_p_value": np.nan, "stouffer_p_value": np.nan, "tests": 0}
    fisher = -2 * np.log(vals).sum()
    z = stats.norm.isf(vals).sum() / math.sqrt(len(vals))
    return {"fisher_stat": float(fisher), "fisher_p_value": float(stats.chi2.sf(fisher, 2 * len(vals))), "stouffer_z": float(z), "stouffer_p_value": float(stats.norm.sf(z)), "tests": int(len(vals))}


def two_sided_power(effect_t: float, alpha: float = 0.05) -> float:
    """Power of a two-sided z-test when the true standardized effect is ``effect_t``."""

    if not np.isfinite(effect_t):
        return np.nan
    z = stats.norm.isf(alpha / 2)
    return float(stats.norm.sf(z - abs(effect_t)) + stats.norm.cdf(-z - abs(effect_t)))


# Harvey, Liu and Zhu (2016, RFS) Table/Figure benchmarks for the 5% level as of
# 2012 (316 published factors): the t-stat a new factor must clear.
HLZ_2016_BENCHMARKS = {"bonferroni": 3.78, "holm": 3.64, "bhy": 3.39}


def bonferroni_t(tests: int, alpha: float = 0.05) -> float:
    return float(stats.norm.isf(alpha / (2 * max(1, tests))))
