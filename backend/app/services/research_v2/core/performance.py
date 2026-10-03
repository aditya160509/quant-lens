"""Performance helpers for Research V2.

These utilities keep hot-path vectorization and small memoized formatting out
of the feature logic. They are intentionally dependency-light and deterministic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

def _fm_kernel_py(y: np.ndarray, x: np.ndarray, min_obs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


_FM_JIT: Callable | None = None


def _fm_kernel(y: np.ndarray, x: np.ndarray, min_obs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compile the kernel on first use so importing this module does not load numba (no fastmath: it breaks np.isfinite)."""

    global _FM_JIT
    if _FM_JIT is None:
        try:
            from numba import njit

            _FM_JIT = njit(cache=True)(_fm_kernel_py)
        except Exception:  # pragma: no cover
            _FM_JIT = _fm_kernel_py
    return _FM_JIT(y, x, min_obs)


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

    s_v = sig.to_numpy(dtype=np.float64)
    r_v = fwd.to_numpy(dtype=np.float64)
    w_v = weights.to_numpy(dtype=np.float64)
    valid = ~(np.isnan(s_v) | np.isnan(r_v) | np.isnan(w_v))
    n = valid.sum(axis=1)
    keep = n >= buckets * 5
    if not keep.any():
        return pd.DataFrame()
    # Rank within each date (ties broken by column order), then cut the ranks at the
    # same linearly interpolated quantile edges that pd.qcut uses.
    ranks = pd.DataFrame(np.where(valid, s_v, np.nan)).rank(axis=1, method="first").to_numpy()
    bucket = np.zeros(ranks.shape, dtype=np.int64)
    for k in range(1, buckets):
        edge = 1.0 + (n - 1) * k / buckets
        bucket += ranks > edge[:, None]
    wgt = np.where(valid, np.maximum(w_v, 0.0), 0.0)
    wret = np.where(valid, r_v, 0.0) * wgt
    labels = [f"Q{i + 1}" for i in range(buckets)]
    cols_out = sorted(range(buckets), key=lambda i: labels[i])
    data = np.full((int(keep.sum()), buckets), np.nan)
    for j, i in enumerate(cols_out):
        m = (bucket == i) & valid
        num, den = (wret * m).sum(axis=1)[keep], (wgt * m).sum(axis=1)[keep]
        present = m.any(axis=1)[keep]
        with np.errstate(invalid="ignore", divide="ignore"):
            data[:, j] = np.where(present & (den != 0), num / np.where(den == 0, 1.0, den), np.nan)
    out = pd.DataFrame(data, columns=pd.Index([labels[i] for i in cols_out], name="bucket"))
    out.insert(0, "date", common_index[keep])
    return out.sort_values("date")


