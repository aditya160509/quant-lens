"""Portfolio V2 performance primitives.

This module keeps speed improvements local and behavior-preserving:

* bounded in-process caches for deterministic numeric transforms
* vectorized pair/matrix operations for graph-style outputs
* bounded record serializers so large universes do not explode response size
* lightweight profiling helpers for feature smoke tests

No function here mutates parquet files or changes financial methodology.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Iterable
import hashlib
import math

import numpy as np
import numba as nb
import pandas as pd


MAX_CACHE_ITEMS = 64
MAX_MATRIX_CELLS = 20_000
MAX_NETWORK_EDGES = 2_000


@dataclass
class PerfCounter:
    calls: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0

    def add(self, elapsed: float) -> None:
        self.calls += 1
        self.total_seconds += float(elapsed)
        self.max_seconds = max(self.max_seconds, float(elapsed))

    def as_dict(self) -> dict[str, float | int]:
        avg = self.total_seconds / self.calls if self.calls else 0.0
        return {
            "calls": self.calls,
            "total_seconds": round(self.total_seconds, 6),
            "avg_seconds": round(avg, 6),
            "max_seconds": round(self.max_seconds, 6),
        }


@dataclass
class PerfRegistry:
    timings: dict[str, PerfCounter] = field(default_factory=dict)
    cache_hits: dict[str, int] = field(default_factory=dict)
    cache_misses: dict[str, int] = field(default_factory=dict)

    def record(self, name: str, elapsed: float) -> None:
        self.timings.setdefault(name, PerfCounter()).add(elapsed)

    def hit(self, name: str) -> None:
        self.cache_hits[name] = self.cache_hits.get(name, 0) + 1

    def miss(self, name: str) -> None:
        self.cache_misses[name] = self.cache_misses.get(name, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "timings": {k: v.as_dict() for k, v in sorted(self.timings.items())},
            "cache_hits": dict(sorted(self.cache_hits.items())),
            "cache_misses": dict(sorted(self.cache_misses.items())),
        }


PERF = PerfRegistry()


@contextmanager
def timed(name: str):
    start = perf_counter()
    try:
        yield
    finally:
        PERF.record(name, perf_counter() - start)


def instrument(name: str) -> Callable:
    def deco(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with timed(name):
                return fn(*args, **kwargs)

        wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        wrapper.__doc__ = getattr(fn, "__doc__", None)
        return wrapper

    return deco


class BoundedLRU:
    __slots__ = ("name", "max_items", "_store", "_lock")

    def __init__(self, name: str, max_items: int = MAX_CACHE_ITEMS):
        self._lock = RLock()
        self.name = name
        self.max_items = max_items
        self._store: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._store:
                PERF.miss(self.name)
                return None
            self._store.move_to_end(key)
            PERF.hit(self.name)
            return deepcopy(self._store[key])

    def set(self, key: str, value: Any) -> Any:
        with self._lock:
            self._store[key] = deepcopy(value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_items:
                self._store.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


COV_CACHE = BoundedLRU("covariance")
CORR_CACHE = BoundedLRU("correlation")
RESULT_CACHE = BoundedLRU("generic_result")


def performance_snapshot() -> dict[str, Any]:
    return PERF.snapshot()


def cached_result(name: str, key: str, builder: Callable[[], Any]) -> Any:
    full_key = f"{name}:{key}"
    cached = RESULT_CACHE.get(full_key)
    if cached is not None:
        return cached
    with timed(name):
        value = builder()
    RESULT_CACHE.set(full_key, value)
    return value


def normalize_numeric_frame(
    df: pd.DataFrame | None, *, fill: float = 0.0
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    arr = df.to_numpy(dtype=np.float64, copy=False)
    arr = (
        arr.copy()
        if arr.flags["C_CONTIGUOUS"]
        else np.ascontiguousarray(arr, dtype=np.float64)
    )
    if isinstance(fill, float) and math.isnan(fill):
        arr[~np.isfinite(arr)] = np.nan
    else:
        np.nan_to_num(arr, copy=False, nan=fill, posinf=fill, neginf=fill)
    return pd.DataFrame(arr, index=df.index, columns=df.columns, copy=False)


def float_array(df: pd.DataFrame | np.ndarray | Iterable[Any]) -> np.ndarray:
    if isinstance(df, pd.DataFrame):
        arr = df.to_numpy(dtype=np.float64, copy=False)
        arr = (
            arr.copy()
            if arr.flags["C_CONTIGUOUS"]
            else np.ascontiguousarray(arr, dtype=np.float64)
        )
    else:
        arr = np.ascontiguousarray(df, dtype=np.float64)
    if not np.isfinite(arr).all():
        raise ValueError("Numeric matrix contains missing or nonfinite observations")
    return arr


def dataframe_fingerprint(df, *, precision=8):
    if df is None:
        return "none"
    h = hashlib.blake2b(digest_size=16)
    h.update(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    h.update(repr(list(df.columns)).encode())
    return h.hexdigest()


def cached_covariance_frame(
    returns: pd.DataFrame,
    method: str,
    builder: Callable[[], tuple[pd.DataFrame, dict[str, Any]]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    key = f"{method}:{dataframe_fingerprint(returns)}"
    cached = COV_CACHE.get(key)
    if cached is not None:
        cov, meta = cached
        meta = dict(meta)
        meta["cache"] = "hit"
        return cov.copy(), meta
    with timed(f"covariance.{method}"):
        cov, meta = builder()
    meta = dict(meta)
    meta["cache"] = "miss"
    COV_CACHE.set(key, (cov.copy(), meta))
    return cov, meta


def cached_correlation_frame(
    returns: pd.DataFrame, method: str = "pearson"
) -> pd.DataFrame:
    method = str(method or "pearson").lower()
    key = f"{method}:{dataframe_fingerprint(returns)}"
    cached = CORR_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    with timed("correlation.frame"):
        # Preserve missing observations for pairwise correlation. Filling them
        # with zero biases sparse assets toward artificial co-movement.
        corr = (
            normalize_numeric_frame(returns, fill=float("nan"))
            .corr(method=method)
            .replace([np.inf, -np.inf], np.nan)
        )
    if not np.isfinite(corr.to_numpy()).all():
        raise ValueError(
            "Correlation is undefined for constant or insufficient observations"
        )
    CORR_CACHE.set(key, corr.copy())
    return corr


def nearest_psd(matrix: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    a = np.asarray(matrix, dtype=np.float64)
    arr = np.empty_like(a)
    np.add(a, a.T, out=arr)
    arr *= 0.5
    if not np.isfinite(arr).all():
        raise ValueError("PSD projection requires finite covariance")
    try:
        vals, vecs = np.linalg.eigh(arr)
        np.maximum(vals, eps, out=vals)
        return (vecs * vals) @ vecs.T
    except np.linalg.LinAlgError as exc:
        raise ValueError("Covariance eigendecomposition failed") from exc


def safe_inverse(matrix: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    arr = nearest_psd(arr, ridge)
    scale = float(np.trace(arr) / max(arr.shape[0], 1)) if arr.size else 1.0
    reg = max(ridge, abs(scale) * ridge)
    try:
        return np.linalg.inv(arr + np.eye(arr.shape[0]) * reg)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(arr + np.eye(arr.shape[0]) * reg)


def covariance_to_correlation(
    cov: pd.DataFrame | np.ndarray, labels: Iterable[str] | None = None
) -> pd.DataFrame:
    if isinstance(cov, pd.DataFrame):
        arr = float_array(cov)
        cols = list(cov.columns)
    else:
        arr = float_array(cov)
        cols = list(labels or [f"A{i + 1}" for i in range(arr.shape[0])])
    diag = np.sqrt(np.maximum(np.diag(arr), 1e-18))
    corr = arr / np.outer(diag, diag)
    corr = np.clip(np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    return pd.DataFrame(corr, index=cols, columns=cols)


def fast_matrix_records(
    matrix: pd.DataFrame | np.ndarray,
    labels: Iterable[str] | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    if isinstance(matrix, pd.DataFrame):
        rows_l = np.asarray(matrix.index, dtype=object)
        cols_l = np.asarray(matrix.columns, dtype=object)
        arr = (
            matrix.to_numpy(dtype=float)
            if isinstance(matrix, pd.DataFrame)
            else np.asarray(matrix, dtype=float)
        )
    else:
        arr = (
            matrix.to_numpy(dtype=float)
            if isinstance(matrix, pd.DataFrame)
            else np.asarray(matrix, dtype=float)
        )
        base = np.asarray(
            list(labels or [f"A{i + 1}" for i in range(arr.shape[0])]), dtype=object
        )
        rows_l = base[: arr.shape[0]]
        cols_l = base[: arr.shape[1]]
    n, m = arr.shape[:2]
    if n * m > MAX_MATRIX_CELLS:
        side = max(1, int(math.isqrt(MAX_MATRIX_CELLS)))
        n = min(n, side, limit)
        m = min(m, side, limit)
    else:
        n = min(n, limit)
        m = min(m, limit)
    sub = arr[:n, :m].ravel()
    row_labels = np.repeat(rows_l[:n].astype(str), m)
    col_labels = np.tile(cols_l[:m].astype(str), n)
    finite_mask = np.isfinite(sub)
    return [
        {"row": r, "col": c, "value": float(v) if f else None}
        for r, c, v, f in zip(row_labels, col_labels, sub, finite_mask)
    ]


def fast_network_edges_from_corr(
    corr: pd.DataFrame, threshold: float = 0.45, max_edges: int = MAX_NETWORK_EDGES
) -> list[dict[str, Any]]:
    if corr is None or corr.empty or len(corr.columns) < 2:
        return []
    labels = np.asarray([str(c) for c in corr.columns])
    arr = np.ascontiguousarray(float_array(corr))
    iu = np.triu_indices_from(arr, k=1)
    vals = arr[iu]
    abs_vals = np.abs(vals)
    mask = abs_vals >= float(threshold)
    if mask.any():
        selected = np.flatnonzero(mask)
        if len(selected) > max_edges:
            top_idx = np.argpartition(abs_vals[selected], -max_edges)[-max_edges:]
            selected = selected[top_idx]
        top = selected[np.argsort(abs_vals[selected])[::-1]]
    else:
        return []
    src = labels[iu[0][top]]
    tgt = labels[iu[1][top]]
    v = vals[top]
    w = np.abs(v)
    return [
        {"source": s, "target": t, "correlation": float(cv), "weight": float(wv)}
        for s, t, cv, wv in zip(src, tgt, v, w)
    ]


def rolling_leading_eigenvalue(
    returns: pd.DataFrame, window: int = 126, step: int = 5
) -> list[dict[str, Any]]:
    x = normalize_numeric_frame(returns)
    n_rows, n_cols = x.shape
    if n_rows < max(20, window // 2) or n_cols < 2:
        return []
    arr = float_array(x)
    rows: list[dict[str, Any]] = []
    start = max(window, 20)

    def _eigen_share(sub: np.ndarray) -> float:
        sub_c = sub - sub.mean(axis=0)
        norms = np.einsum("ij,ij->j", sub_c, sub_c)
        np.sqrt(norms, out=norms)
        norms[norms < 1e-12] = 1.0
        sub_c /= norms
        corr_a = sub_c.T @ sub_c
        np.clip(corr_a, -1.0, 1.0, out=corr_a)
        np.fill_diagonal(corr_a, 1.0)
        vals = np.linalg.eigvalsh(np.ascontiguousarray(corr_a))
        return float(vals[-1] / max(n_cols, 1))

    for end in range(start, n_rows + 1, max(1, step)):
        sub = arr[max(0, end - window) : end]
        rows.append(
            {
                "date": x.index[end - 1],
                "leading_eigenvalue_share": _eigen_share(sub.copy()),
            }
        )
    if rows and rows[-1]["date"] != x.index[-1]:
        rows.append(
            {
                "date": x.index[-1],
                "leading_eigenvalue_share": _eigen_share(arr[-window:].copy()),
            }
        )
    return rows


def rolling_diversification_ratio(
    returns: pd.DataFrame, weights: pd.Series, window: int = 126, step: int = 5
) -> list[dict[str, Any]]:
    x = normalize_numeric_frame(returns)
    n_rows, n_cols = x.shape
    if n_rows < max(20, window // 2) or n_cols < 2:
        return []
    w = weights.reindex(x.columns).fillna(0.0).to_numpy(dtype=np.float64)
    wabs = np.abs(w)
    if wabs.sum() <= 1e-12:
        w = np.full(n_cols, 1.0 / n_cols)
        wabs = w
    arr = float_array(x)
    rows: list[dict[str, Any]] = []
    start = max(window, 20)

    def _dr(sub: np.ndarray) -> float:
        sub_c = sub - sub.mean(axis=0)
        cov = (sub_c.T @ sub_c) / max(sub.shape[0] - 1, 1)
        vols = np.sqrt(np.maximum(np.einsum("ii->i", cov), 0.0))
        port = math.sqrt(max(float(w @ cov @ w), 1e-18))
        return float((wabs @ vols) / port)

    for end in range(start, n_rows + 1, max(1, step)):
        rows.append(
            {
                "date": x.index[end - 1],
                "diversification_ratio": _dr(arr[max(0, end - window) : end]),
            }
        )
    if rows and rows[-1]["date"] != x.index[-1]:
        rows.append({"date": x.index[-1], "diversification_ratio": _dr(arr[-window:])})
    return rows


def compact_table(df: pd.DataFrame, limit: int = 600) -> pd.DataFrame:
    if df is None or df.empty or len(df) <= limit:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    idx = np.unique(np.linspace(0, len(df) - 1, limit, dtype=np.intp))
    return df.iloc[idx].copy()


def fast_corr(df: pd.DataFrame) -> pd.DataFrame:
    arr = float_array(df)
    arr -= arr.mean(axis=0)
    norms = np.einsum("ij,ij->j", arr, arr)
    np.sqrt(norms, out=norms)
    norms[norms < 1e-12] = 1.0
    arr /= norms
    corr = arr.T @ arr
    np.clip(corr, -1.0, 1.0, out=corr)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=df.columns, columns=df.columns)


def safe_eigh(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    arr = np.ascontiguousarray(mat, dtype=np.float64)
    np.nan_to_num(arr, copy=False)
    return np.linalg.eigh(arr)


def dates_to_str(index: pd.Index) -> list[str]:
    return pd.Series(index).dt.strftime("%Y-%m-%d").tolist()


@nb.njit(cache=True, fastmath=False)
def _jit_rank_ic(s_arr: np.ndarray, y_arr: np.ndarray, finite: np.ndarray) -> float:
    """Per-horizon cross-sectional Spearman IC in a single compiled pass."""
    T = s_arr.shape[0]
    N = s_arr.shape[1]
    total_ic = 0.0
    valid_rows = 0
    for t in range(T):
        count = 0
        for j in range(N):
            if finite[t, j]:
                count += 1
        if count <= 5:
            continue
        s_mean = 0.0
        y_mean = 0.0
        for j in range(N):
            if finite[t, j]:
                s_mean += s_arr[t, j]
                y_mean += y_arr[t, j]
        s_mean /= count
        y_mean /= count
        ss = 0.0
        yy = 0.0
        sy = 0.0
        for j in range(N):
            if finite[t, j]:
                sc = s_arr[t, j] - s_mean
                yc = y_arr[t, j] - y_mean
                ss += sc * sc
                yy += yc * yc
                sy += sc * yc
        denom = math.sqrt(ss * yy)
        if denom > 1e-12:
            total_ic += sy / denom
            valid_rows += 1
    return total_ic / max(valid_rows, 1) if valid_rows > 0 else 0.0


def rank_ic_curve(
    returns: pd.DataFrame, max_horizon: int = 63, signal_window: int = 21
) -> list[dict[str, float | int]]:
    """Vectorized cross-sectional Spearman IC by horizon."""
    x = normalize_numeric_frame(returns, fill=np.nan)
    if x.empty:
        return []
    signal = x.rolling(signal_window).mean().shift(1).rank(axis=1, pct=True)
    s_arr = np.ascontiguousarray(signal.to_numpy(dtype=np.float64))
    rows: list[dict[str, float | int]] = []
    for h in range(1, int(max_horizon) + 1):
        fwd = ((1 + x).rolling(h).apply(np.prod, raw=True).shift(-h) - 1).rank(
            axis=1, pct=True
        )
        y_arr = np.ascontiguousarray(fwd.to_numpy(dtype=np.float64))
        finite = np.ascontiguousarray(np.isfinite(s_arr) & np.isfinite(y_arr))
        ic = _jit_rank_ic(s_arr, y_arr, finite)
        rows.append({"horizon": h, "ic": float(ic)})
    return rows
