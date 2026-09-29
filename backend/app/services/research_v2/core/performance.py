"""Performance helpers for Research V2.

These utilities keep hot-path vectorization and small memoized formatting out
of the feature logic. They are intentionally dependency-light and deterministic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable
import hashlib
import math

import numpy as np
import pandas as pd

try:
    from numba import njit
except Exception:  # pragma: no cover
    njit = None


NUMBA_AVAILABLE = njit is not None


def _identity_jit(*args: Any, **kwargs: Any) -> Callable:
    def wrap(fn: Callable) -> Callable:
        return fn
    return wrap


_jit = njit(cache=True, fastmath=True) if njit is not None else _identity_jit()


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
        xtx = xx.T @ xx
        xty = xx.T @ yy
        try:
            beta = np.linalg.solve(xtx, xty)
        except Exception:
            beta = np.linalg.pinv(xtx) @ xty
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


def jit_fama_macbeth_frame(panel: dict[str, Any], min_obs: int = 20) -> pd.DataFrame:
    """Run cross-sectional FM regressions through a Numba kernel when possible."""

    sig = panel["signals"]
    fwd = panel["forward"]
    common_index = sig.index.intersection(fwd.index)
    common_cols = sig.columns.intersection(fwd.columns)
    if len(common_index) == 0 or len(common_cols) == 0:
        return pd.DataFrame()
    design_mats = [sig.reindex(index=common_index, columns=common_cols)]
    names = ["signal"]
    for name, mat in panel.get("controls", {}).items():
        if isinstance(mat, pd.DataFrame):
            aligned = mat.reindex(index=common_index, columns=common_cols)
            if np.isfinite(aligned.to_numpy(dtype=float)).sum() < min_obs:
                continue
            design_mats.append(aligned)
            names.append(str(name))
    y = fwd.reindex(index=common_index, columns=common_cols).to_numpy(dtype=np.float64)
    x = np.empty((len(common_index), len(common_cols), len(design_mats) + 1), dtype=np.float64)
    x[:, :, 0] = 1.0
    for idx, mat in enumerate(design_mats, start=1):
        x[:, :, idx] = mat.to_numpy(dtype=np.float64)
    coef, r2, nobs = _fm_kernel(y, x, int(min_obs))
    rows: list[dict[str, Any]] = []
    for i, date in enumerate(common_index):
        if not np.isfinite(nobs[i]) or nobs[i] < min_obs:
            continue
        row: dict[str, Any] = {"date": date, "r2": float(r2[i]) if np.isfinite(r2[i]) else np.nan, "n_assets": int(nobs[i])}
        for j, name in enumerate(names, start=1):
            row[f"{name}_lambda"] = float(coef[i, j]) if j < coef.shape[1] and np.isfinite(coef[i, j]) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def cached_data_inventory(loader_token: str = "default") -> dict[str, Any]:
    """Session-level inventory cache.

    The token argument is present so callers can intentionally invalidate from
    tests or fetcher flows without changing the public analytics response shape.
    """

    from .data_loader import data_inventory

    return data_inventory()


def frame_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    sample = df.head(250).tail(250)
    payload = pd.util.hash_pandas_object(sample, index=True).to_numpy(dtype=np.uint64).tobytes()
    return hashlib.blake2b(payload, digest_size=12).hexdigest()


@lru_cache(maxsize=64)
def cached_latex_from_csv(name: str, csv_payload: str) -> str:
    if not csv_payload:
        return f"% {name}: no rows"
    from io import StringIO

    df = pd.read_csv(StringIO(csv_payload))
    try:
        return df.to_latex(index=False, float_format=lambda x: f"{x:.4f}")
    except Exception:
        return csv_payload


def cached_latex_table(name: str, df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return f"% {name}: no rows"
    # CSV is a stable, compact cache key for the small tables emitted here.
    return cached_latex_from_csv(name, df.to_csv(index=False))


def broadcast_static(values: pd.Series, index: pd.Index, columns: pd.Index) -> pd.DataFrame:
    vals = values.reindex(columns).to_numpy(dtype=float)
    return pd.DataFrame(np.tile(vals, (len(index), 1)), index=index, columns=columns)


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
        weights = weights.reindex(index=common_index, columns=common_cols).fillna(1.0)

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
    ).dropna(subset=["signal", "ret"])
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
    stacked["weighted_ret"] = stacked["ret"] * stacked["weight"].clip(lower=0).fillna(0)
    grouped = stacked.groupby([stacked.index.get_level_values(0), "bucket"], observed=True)
    sums = grouped[["weighted_ret", "weight"]].sum()
    bucket_rets = (sums["weighted_ret"] / sums["weight"].replace(0, np.nan)).unstack("bucket")
    bucket_rets.index.name = date_level or "date"
    out = bucket_rets.reset_index().rename(columns={bucket_rets.index.name or "index": "date"})
    if "date" not in out.columns:
        out = out.rename(columns={out.columns[0]: "date"})
    return out.sort_values("date")


def offdiag_corr_mean(frame: pd.DataFrame, max_cols: int = 120) -> float:
    if frame is None or frame.empty or frame.shape[1] < 2:
        return 0.0
    sample = frame.iloc[:, : min(max_cols, frame.shape[1])].dropna(how="all")
    if sample.shape[1] < 2:
        return 0.0
    corr = sample.corr().replace([np.inf, -np.inf], np.nan)
    mask = ~np.eye(len(corr), dtype=bool)
    return float(corr.where(mask).stack().mean())


def positional_event_rows(df: pd.DataFrame, date: pd.Timestamp, start_k: int, end_k: int, value_col: str, baseline_window: int = 6) -> list[dict[str, Any]]:
    if df.empty:
        return []
    base_idx = int(df.index.get_indexer([date], method="nearest")[0])
    baseline = df.iloc[max(0, base_idx - baseline_window):base_idx][value_col].mean()
    rows = []
    for k in range(start_k, end_k + 1):
        pos = max(0, min(len(df) - 1, base_idx + k))
        rows.append({"cohort": str(date.date()), "event_time": k, "att_gt": df.iloc[pos][value_col] - baseline, "n": 1})
    return rows


def scm_objective_arrays(y: pd.Series, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    yy = y.to_numpy(dtype=float)
    xx = x.to_numpy(dtype=float)
    mask = np.isfinite(yy) & np.isfinite(xx).all(axis=1)
    return yy[mask], xx[mask]
