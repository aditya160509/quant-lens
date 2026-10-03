"""Performance helpers for Research V2.

These utilities keep hot-path vectorization and small memoized formatting out
of the feature logic. They are intentionally dependency-light and deterministic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

try:
    from numba import njit
except Exception:  # pragma: no cover
    njit = None


def _identity_jit(*args: Any, **kwargs: Any) -> Callable:
    def wrap(fn: Callable) -> Callable:
        return fn
    return wrap


# No fastmath: it assumes no NaN, which silently breaks np.isfinite in the kernel.
_jit = njit(cache=True) if njit is not None else _identity_jit()


@_jit
def _fm_kernel(y: np.ndarray, x: np.ndarray, min_obs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t_count = y.shape[0]
    n_assets = y.shape[1]
    k = x.shape[2]
    coefs = np.empty((t_count, k))
    r2 = np.empty(t_count)
    nobs = np.empty(t_count)
    for t in range(t_count):
        for j in range(k):
            coefs[t, j] = np.nan
        r2[t] = np.nan
        nobs[t] = 0.0
        valid_count = 0
        for i in range(n_assets):
            ok = np.isfinite(y[t, i])
            if ok:
                for j in range(k):
                    if not np.isfinite(x[t, i, j]):
                        ok = False
                        break
            if ok:
                valid_count += 1
        if valid_count < min_obs or valid_count <= k + 2:
            continue
        xx = np.empty((valid_count, k))
        yy = np.empty(valid_count)
        pos = 0
        for i in range(n_assets):
            ok = np.isfinite(y[t, i])
            if ok:
                for j in range(k):
                    if not np.isfinite(x[t, i, j]):
                        ok = False
                        break
            if ok:
                yy[pos] = y[t, i]
                for j in range(k):
                    xx[pos, j] = x[t, i, j]
                pos += 1
        # Rank-deficient cross-sections (collinear regressors) have no unique slope; leave the month missing
        beta, _, rank, _ = np.linalg.lstsq(xx, yy, 1e-10)
        if rank < k:
            continue
        pred = xx @ beta
        resid = yy - pred
        rss = 0.0
        ybar = 0.0
        for i in range(valid_count):
            rss += resid[i] * resid[i]
            ybar += yy[i]
        ybar = ybar / valid_count
        tss = 0.0
        for i in range(valid_count):
            diff = yy[i] - ybar
            tss += diff * diff
        for j in range(k):
            coefs[t, j] = beta[j]
        r2[t] = 1.0 - rss / tss if tss > 0 else np.nan
        nobs[t] = float(valid_count)
    return coefs, r2, nobs


@lru_cache(maxsize=1)
def cached_data_inventory(loader_token: str = "default") -> dict[str, Any]:
    """Session-level inventory cache.

    The token argument is present so callers can intentionally invalidate from
    tests or fetcher flows without changing the public analytics response shape.
    """

    from .data_loader import data_inventory

    return data_inventory()


def acf_frame(series: pd.Series, max_lag: int = 21) -> pd.DataFrame:
    x = pd.Series(series).dropna().astype(float).to_numpy()
    if len(x) < 4:
        return pd.DataFrame({"lag": list(range(1, max_lag + 1)), "acf": [np.nan] * max_lag})
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    if denom <= 0:
        vals = [np.nan] * max_lag
    else:
        acov = np.correlate(xc, xc, mode="full")[len(x) - 1:] / denom
        vals = [float(acov[lag]) if lag < len(acov) and len(x) > lag + 2 else np.nan for lag in range(1, max_lag + 1)]
    return pd.DataFrame({"lag": list(range(1, max_lag + 1)), "acf": vals})


def vectorized_portfolio_returns(sig: pd.DataFrame, fwd: pd.DataFrame, weights: pd.DataFrame | None, buckets: int) -> pd.DataFrame:
    """Build bucket returns with one stacked panel instead of one DataFrame per date."""

    common_index = sig.index.intersection(fwd.index)
    common_cols = sig.columns.intersection(fwd.columns)
    if len(common_index) == 0 or len(common_cols) == 0:
        return pd.DataFrame()
    sig = sig.reindex(index=common_index, columns=common_cols)
    fwd = fwd.reindex(index=common_index, columns=common_cols)
    if weights is None or weights.empty:
        weights = pd.DataFrame(1.0, index=common_index, columns=common_cols)
    else:
        weights = weights.reindex(index=common_index, columns=common_cols)

    def stack_frame(frame: pd.DataFrame, name: str) -> pd.Series:
        try:
            return frame.stack(future_stack=True).rename(name)
        except TypeError:
            return frame.stack(dropna=False).rename(name)

    stacked = pd.concat(
        [
            stack_frame(sig, "signal"),
            stack_frame(fwd, "ret"),
            stack_frame(weights, "weight"),
        ],
        axis=1,
    ).dropna(subset=["signal", "ret", "weight"])
    if stacked.empty:
        return pd.DataFrame()
    date_level = stacked.index.names[0]

    def assign_bucket(values: pd.Series) -> pd.Series:
        if values.notna().sum() < buckets * 5:
            return pd.Series(pd.NA, index=values.index, dtype="object")
        ranked = values.rank(method="first")
        try:
            return pd.qcut(ranked, q=buckets, labels=[f"Q{i + 1}" for i in range(buckets)]).astype("object")
        except ValueError:
            return pd.Series(pd.NA, index=values.index, dtype="object")

    stacked["bucket"] = stacked.groupby(level=0, observed=True)["signal"].transform(assign_bucket)
    stacked = stacked.dropna(subset=["bucket"])
    if stacked.empty:
        return pd.DataFrame()
    stacked["weight"] = stacked["weight"].clip(lower=0)
    stacked["weighted_ret"] = stacked["ret"] * stacked["weight"]
    grouped = stacked.groupby([stacked.index.get_level_values(0), "bucket"], observed=True)
    sums = grouped[["weighted_ret", "weight"]].sum()
    bucket_rets = (sums["weighted_ret"] / sums["weight"].replace(0, np.nan)).unstack("bucket")
    bucket_rets.index.name = date_level or "date"
    out = bucket_rets.reset_index().rename(columns={bucket_rets.index.name or "index": "date"})
    if "date" not in out.columns:
        out = out.rename(columns={out.columns[0]: "date"})
    return out.sort_values("date")


