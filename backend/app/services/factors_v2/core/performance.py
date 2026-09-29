"""Performance kernels and runtime policy helpers for Factors V2.

The functions here keep the feature modules explicit about what is allowed in
realtime versus Research Mode, while providing fast vectorized/JIT kernels for
the hot loops that show up across the factor stack.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any, Dict, Iterable, Tuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


_ARRAY_CACHE: Dict[str, np.ndarray] = {}
_SCRATCH_CACHE: Dict[Tuple[str, Tuple[int, ...], int], np.ndarray] = {}
_MAX_CACHE_ENTRIES = 512

try:  # pragma: no cover - compile-time optional until requirements are synced.
    from numba import njit, prange
except Exception:  # pragma: no cover
    def njit(*args, **kwargs):
        def wrap(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return wrap
    def prange(*args):
        return range(*args)


try:  # pragma: no cover - used opportunistically for shape-stable arrays.
    import jax
    import jax.numpy as jnp
except Exception:  # pragma: no cover
    jax = None
    jnp = None


def compute_mode(payload: Dict[str, Any] | None) -> str:
    mode = str((payload or {}).get("compute_mode", "realtime")).lower()
    return "research" if mode in {"research", "async", "full"} else "realtime"


def is_research(payload: Dict[str, Any] | None) -> bool:
    return compute_mode(payload) == "research"


@lru_cache(maxsize=256)
def _cached_hash(material: str) -> str:
    """LRU-cached SHA-256 digest so identical payloads skip re-hashing."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def stable_cache_key(feature_id: str, payload: Dict[str, Any] | None, namespace: str) -> str:
    material = json.dumps(payload or {}, sort_keys=True, default=str)
    # blake2b is materially faster than sha256 for short API payloads while
    # remaining deterministic and collision-resistant enough for cache keys.
    digest = hashlib.blake2b(material.encode("utf-8"), digest_size=8).hexdigest()
    return f"factors_v2:{feature_id}:{namespace}:{digest}"


def cache_array(cache_key: str, arr: np.ndarray, dtype=np.float32) -> np.ndarray:
    """Keep contiguous arrays in-process for repeated feature calls.

    Bounded to _MAX_CACHE_ENTRIES with FIFO eviction to prevent unbounded
    growth in long-running server processes.
    """
    if len(_ARRAY_CACHE) >= _MAX_CACHE_ENTRIES:
        _ARRAY_CACHE.pop(next(iter(_ARRAY_CACHE)))  # evict oldest (FIFO)
    out = np.ascontiguousarray(arr, dtype=dtype)
    _ARRAY_CACHE[cache_key] = out
    return out


def get_cached_array(cache_key: str) -> np.ndarray | None:
    return _ARRAY_CACHE.get(cache_key)


def scratch_array(key: str, shape: Tuple[int, ...], dtype=np.float64) -> np.ndarray:
    # Use itemsize (an int) instead of dtype.str (string construction) — cheaper to hash.
    cache_key = (key, shape, np.dtype(dtype).itemsize)
    arr = _SCRATCH_CACHE.get(cache_key)
    if arr is None:
        arr = np.empty(shape, dtype=dtype)
        _SCRATCH_CACHE[cache_key] = arr
    return arr


def batch_covariance_upper(values: np.ndarray, window: int, step: int = 1) -> np.ndarray:
    """Batch rolling covariance upper triangles with stride windows.

    This replaces repeated Python-level covariance calls in regime GMM vector
    construction. It intentionally stays NumPy-only so it works before Numba/JAX
    warm-up and remains stable in worker processes.
    """
    arr = np.asarray(values, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] < window or arr.shape[1] == 0:
        return np.empty((0, 0), dtype=np.float32)
    windows = sliding_window_view(arr, window_shape=window, axis=0)[:: max(int(step), 1)]
    # sliding_window_view(axis=0) returns (n_windows, n_factors, window).
    # Keep that layout and contract on the window axis; this avoids the
    # np.moveaxis copy called out in AUDIT.md.
    centered = windows - np.nanmean(windows, axis=2, keepdims=True)
    cov = np.einsum("nfw,ngw->nfg", centered, centered, optimize=True) / max(window - 1, 1)
    tri = np.triu_indices(arr.shape[1])
    return cov[:, tri[0], tri[1]].astype(np.float32, copy=False)


def cap_realtime(value: int, default_cap: int, research_cap: int, payload: Dict[str, Any] | None) -> int:
    cap = research_cap if is_research(payload) else default_cap
    return min(int(value), cap)


@njit(cache=True, fastmath=True)
def rolling_autocorr_1(x: np.ndarray, window: int) -> np.ndarray:
    out = np.empty(x.shape[0], dtype=np.float64)
    out[:] = np.nan
    for i in range(window, x.shape[0] + 1):
        a = x[i - window : i - 1]
        b = x[i - window + 1 : i]
        ma = np.mean(a)
        mb = np.mean(b)
        va = np.sum((a - ma) ** 2)
        vb = np.sum((b - mb) ** 2)
        den = np.sqrt(va * vb)
        if den > 0:
            out[i - 1] = np.sum((a - ma) * (b - mb)) / den
    return out


@njit(cache=True, fastmath=True)
def drawdown_curve(equity: np.ndarray) -> np.ndarray:
    out = np.empty(equity.shape[0], dtype=np.float64)
    peak = equity[0] if equity.shape[0] else 1.0
    for i in range(equity.shape[0]):
        if equity[i] > peak:
            peak = equity[i]
        out[i] = equity[i] / peak - 1.0 if peak != 0 else 0.0
    return out


@njit(cache=True, fastmath=True, parallel=True)
def implementation_shortfall_kernel(
    weights: np.ndarray,
    adv: np.ndarray,
    realized_vol: np.ndarray,
    aum: float,
    turnover: float,
    explicit_bps: float,
    linear_bps: float,
    impact_eta: float,
    timing_bps: float,
    participation_cap: float,
    include_timing: bool,
) -> np.ndarray:
    out = np.zeros((weights.shape[0], 6), dtype=np.float64)
    for i in prange(weights.shape[0]):
        trade = aum * turnover * weights[i]
        participation = trade / max(adv[i], 1.0)
        execution_days = np.ceil(participation / max(participation_cap, 1e-8))
        if execution_days < 1:
            execution_days = 1
        capped_part = participation / execution_days
        explicit = explicit_bps / 10000.0 * turnover * weights[i]
        linear = linear_bps / 10000.0 * capped_part * turnover * weights[i] * execution_days
        impact = impact_eta * max(realized_vol[i], 0.01) * np.sqrt(max(capped_part, 0.0)) * turnover * weights[i] * execution_days
        timing = timing_bps / 10000.0 * turnover * weights[i] * np.sqrt(execution_days) if include_timing else 0.0
        out[i, 0] = participation
        out[i, 1] = execution_days
        out[i, 2] = explicit
        out[i, 3] = linear
        out[i, 4] = impact
        out[i, 5] = timing
    return out


@njit(cache=True, fastmath=True)
def cusum_statistic(x: np.ndarray) -> np.ndarray:
    out = np.empty(x.shape[0], dtype=np.float64)
    out[:] = np.nan
    mean = np.nanmean(x)
    std = np.nanstd(x)
    if not np.isfinite(std) or std == 0:
        return out
    running = 0.0
    for i in range(x.shape[0]):
        running += (x[i] - mean) / std
        out[i] = abs(running) / np.sqrt(i + 1)
    return out


@njit(cache=True, fastmath=True)
def dcc_recursion_kernel(z: np.ndarray, qbar: np.ndarray, a: float, b: float) -> Tuple[np.ndarray, np.ndarray]:
    n, k = z.shape
    q = qbar.copy()
    corr_path = np.empty(n, dtype=np.float64)
    for i in range(n):
        eps = z[i]
        # Engle (2002) DCC recursion without reshape for numba-contiguous safety.
        for r in range(k):
            for c in range(k):
                q[r, c] = (1.0 - a - b) * qbar[r, c] + a * eps[r] * eps[c] + b * q[r, c]
        # Normalization to Correlation Matrix and Path Statistics
        d = np.sqrt(np.diag(q))
        sum_abs_r = 0.0
        count = 0
        for r in range(k):
            for c in range(r + 1, k):
                val = q[r, c] / (d[r] * d[c])
                sum_abs_r += abs(val)
                count += 1
        corr_path[i] = sum_abs_r / count if count > 0 else 0.0
    return q, corr_path


@njit(cache=True, fastmath=True)
def rolling_ols_kernel(x: np.ndarray, y: np.ndarray, window: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = x.shape[0]
    betas = np.empty(n, dtype=np.float64)
    alphas = np.empty(n, dtype=np.float64)
    r2s = np.empty(n, dtype=np.float64)
    betas[:] = np.nan
    alphas[:] = np.nan
    r2s[:] = np.nan
    for i in range(window, n + 1):
        sx = x[i - window : i]
        sy = y[i - window : i]
        mx, my = np.mean(sx), np.mean(sy)
        dx, dy = sx - mx, sy - my
        cov = np.sum(dx * dy)
        var_x = np.sum(dx * dx)
        if var_x > 0:
            b = cov / var_x
            a = my - b * mx
            betas[i - 1] = b
            alphas[i - 1] = a
            # R-Squared
            ss_res = np.sum((sy - (a + b * sx)) ** 2)
            ss_tot = np.sum(dy * dy)
            r2s[i - 1] = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return betas, alphas, r2s


def jax_covariance_batch(panel: np.ndarray) -> np.ndarray:
    """Return batched covariance using JAX when available, NumPy otherwise."""
    arr = np.asarray(panel, dtype=float)
    if jax is None or jnp is None or arr.ndim != 3:
        return np.asarray([np.cov(block, rowvar=False) for block in arr])

    @jax.jit
    def _batched_cov(x):
        x = x - jnp.nanmean(x, axis=1, keepdims=True)
        return jnp.einsum("bti,btj->bij", x, x) / jnp.maximum(x.shape[1] - 1, 1)

    return np.asarray(_batched_cov(jnp.asarray(arr)))


@njit(cache=True, fastmath=True)
def welford_rolling(arr: np.ndarray, window: int) -> Tuple[np.ndarray, np.ndarray]:
    n = arr.shape[0]
    means = np.empty(n, dtype=np.float64)
    variances = np.empty(n, dtype=np.float64)
    means[:] = np.nan
    variances[:] = np.nan
    for i in range(n):
        start = max(0, i - window + 1)
        count = 0
        mean = 0.0
        m2 = 0.0
        for j in range(start, i + 1):
            x = arr[j]
            if not np.isfinite(x):
                continue
            count += 1
            delta = x - mean
            mean += delta / count
            m2 += delta * (x - mean)
        if count > 1:
            means[i] = mean
            variances[i] = m2 / (count - 1)
    return means, variances


@njit(cache=True, fastmath=True)
def rolling_corr_kernel(x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
    n = min(x.shape[0], y.shape[0])
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        sx = x[i - window + 1 : i + 1]
        sy = y[i - window + 1 : i + 1]
        mx = np.mean(sx)
        my = np.mean(sy)
        dx = sx - mx
        dy = sy - my
        den = np.sqrt(np.sum(dx * dx) * np.sum(dy * dy))
        if den > 0:
            out[i] = np.sum(dx * dy) / den
    return out


@njit(cache=True, fastmath=True, parallel=True)
def batched_forward_sums(x: np.ndarray, horizons: np.ndarray) -> np.ndarray:
    n = x.shape[0]
    hcount = horizons.shape[0]
    out = np.empty((hcount, n), dtype=np.float64)
    out[:, :] = np.nan
    prefix = np.empty(n + 1, dtype=np.float64)
    prefix[0] = 0.0
    for i in range(n):
        prefix[i + 1] = prefix[i] + x[i]
    for hidx in prange(hcount):
        h = int(horizons[hidx])
        for i in range(0, n - h):
            out[hidx, i] = prefix[i + h + 1] - prefix[i + 1]
    return out


@njit(cache=True, fastmath=True, parallel=True)
def vectorized_rolling_ic_matrix(x: np.ndarray, forward: np.ndarray, window: int) -> np.ndarray:
    hcount, n = forward.shape
    out = np.empty((hcount, n), dtype=np.float64)
    out[:, :] = np.nan
    for hidx in prange(hcount):
        for i in range(window - 1, n):
            y = forward[hidx, i - window + 1 : i + 1]
            sx = x[i - window + 1 : i + 1]
            if not np.isfinite(y).all():
                continue
            mx = np.mean(sx)
            my = np.mean(y)
            dx = sx - mx
            dy = y - my
            den = np.sqrt(np.sum(dx * dx) * np.sum(dy * dy))
            if den > 0:
                out[hidx, i] = np.sum(dx * dy) / den
    return out


@njit(cache=True, fastmath=True)
def rolling_std_percentile_kernel(x: np.ndarray, window: int) -> np.ndarray:
    n = x.shape[0]
    vol = np.empty(n, dtype=np.float64)
    vol[:] = np.nan
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        chunk = x[i - window + 1 : i + 1]
        vol[i] = np.std(chunk)
        valid = vol[: i + 1][np.isfinite(vol[: i + 1])]
        if valid.shape[0] > 1:
            sorted_v = np.sort(valid)
            out[i] = np.searchsorted(sorted_v, vol[i]) / valid.shape[0] * 100.0
    return out


@njit(cache=True, fastmath=True, parallel=True)
def vectorized_mc_equity(returns: np.ndarray, simulations: int, seed_offsets: np.ndarray) -> np.ndarray:
    n = returns.shape[0]
    out = np.empty((simulations, n), dtype=np.float64)
    for s in prange(simulations):
        equity = 1.0
        offset = seed_offsets[s] if seed_offsets.shape[0] > s else 0
        for i in range(n):
            j = i + offset
            if j < 0:
                j = 0
            if j >= n:
                j = n - 1
            equity *= 1.0 + returns[j]
            out[s, i] = equity
    return out


@njit(cache=True, fastmath=True)
def elastic_net_coordinate_descent(X: np.ndarray, y: np.ndarray, alpha: float, l1_ratio: float, max_iter: int = 200) -> np.ndarray:
    n, p = X.shape
    beta = np.zeros(p, dtype=np.float64)
    l1 = alpha * l1_ratio
    l2 = alpha * (1.0 - l1_ratio)
    residual = y.copy()
    for _ in range(max_iter):
        for j in range(p):
            residual += X[:, j] * beta[j]
            rho = np.dot(X[:, j], residual) / n
            z = np.dot(X[:, j], X[:, j]) / n + l2
            if rho < -l1:
                beta[j] = (rho + l1) / z
            elif rho > l1:
                beta[j] = (rho - l1) / z
            else:
                beta[j] = 0.0
            residual -= X[:, j] * beta[j]
    return beta


@njit(cache=True, fastmath=True, parallel=True)
def tiled_dot_kernel(A: np.ndarray, B: np.ndarray, block_size: int = 64) -> np.ndarray:
    n, k = A.shape
    k2, m = B.shape
    C = np.zeros((n, m), dtype=np.float64)
    if k != k2:
        return C
    n_blocks = (n + block_size - 1) // block_size
    for bi in prange(n_blocks):
        ii = bi * block_size
        i_end = min(ii + block_size, n)
        for jj in range(0, m, block_size):
            j_end = min(jj + block_size, m)
            for kk in range(0, k, block_size):
                k_end = min(kk + block_size, k)
                for i in range(ii, i_end):
                    for j in range(jj, j_end):
                        acc = 0.0
                        for q in range(kk, k_end):
                            acc += A[i, q] * B[q, j]
                        C[i, j] += acc
    return C


def runtime_meta(feature_id: str, payload: Dict[str, Any] | None, constraints: Iterable[str] | None = None) -> Dict[str, Any]:
    return {
        "compute_mode": compute_mode(payload),
        "contract_status": "implemented_with_realtime_constraints",
        "real_time_constraints": list(constraints or []),
        "missing_data_policy": "use complete local observations; surface reduced universe and unavailable institutional data explicitly",
        "cache_key": stable_cache_key(feature_id, payload, "runtime"),
    }


@lru_cache(maxsize=64)
def cached_research_marker(cache_key: str) -> Dict[str, Any]:
    return {"cache_key": cache_key, "cache_policy": "nightly_or_research_mode_precompute"}


@njit(cache=True, fastmath=True)
def rolling_percentile_numba(arr: np.ndarray, window: int) -> np.ndarray:
    """Insertion-sort replaces np.sort for small windows — O(W^2) beats O(W log W)
    overhead for Numba's small-array sort path, and avoids temporary allocations."""
    out = np.empty(arr.shape[0], dtype=np.float64)
    out[:] = np.nan
    if window <= 1:
        return out
    for i in range(window - 1, arr.shape[0]):
        current = arr[i]
        if not np.isfinite(current):
            continue
        segment = arr[i - window + 1 : i + 1]
        sorted_w = segment.copy()
        # Insertion sort — faster than np.sort for small windows in Numba
        for j in range(1, len(sorted_w)):
            key = sorted_w[j]
            k = j - 1
            while k >= 0 and sorted_w[k] > key:
                sorted_w[k + 1] = sorted_w[k]
                k -= 1
            sorted_w[k + 1] = key
        pos = 0
        for j in range(len(sorted_w)):
            if sorted_w[j] < current:
                pos += 1
        out[i] = pos / len(sorted_w) * 100.0
    return out


def fast_covariance_matrix(matrix: np.ndarray, annualize: float = 1.0, dtype=np.float32) -> np.ndarray:
    R = np.asarray(matrix, dtype=dtype)
    R = R[np.isfinite(R).all(axis=1)] if R.ndim == 2 else R
    if R.ndim != 2 or R.shape[0] < 2:
        return np.empty((0, 0), dtype=np.float64)
    centered = R - R.mean(axis=0, keepdims=True)
    cov = np.dot(centered.T, centered) / max(R.shape[0] - 1, 1)
    return np.asarray(cov * annualize, dtype=np.float64)


def fast_spearman_ic(factor_scores: np.ndarray, forward_returns: np.ndarray) -> float:
    f = np.asarray(factor_scores, dtype=float)
    r = np.asarray(forward_returns, dtype=float)
    mask = np.isfinite(f) & np.isfinite(r)
    f = f[mask]
    r = r[mask]
    if f.size < 3:
        return np.nan
    rf = np.argsort(np.argsort(f)).astype(float)
    rr = np.argsort(np.argsort(r)).astype(float)
    rf -= rf.mean()
    rr -= rr.mean()
    denom = np.linalg.norm(rf) * np.linalg.norm(rr)
    return float(np.dot(rf, rr) / (denom + 1e-12))


def vectorized_bootstrap_ic(factor_scores: np.ndarray, returns: np.ndarray, n_boot: int = 1000, seed: int = 1729) -> np.ndarray:
    f = np.asarray(factor_scores, dtype=float)
    r = np.asarray(returns, dtype=float)
    mask = np.isfinite(f) & np.isfinite(r)
    f = f[mask]
    r = r[mask]
    if f.size < 3:
        return np.empty(0, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, f.size, size=(int(n_boot), f.size))
    f_boot = f[idx]
    r_boot = r[idx]
    f_ranked = np.argsort(np.argsort(f_boot, axis=1), axis=1).astype(float)
    r_ranked = np.argsort(np.argsort(r_boot, axis=1), axis=1).astype(float)
    f_ranked -= f_ranked.mean(axis=1, keepdims=True)
    r_ranked -= r_ranked.mean(axis=1, keepdims=True)
    num = (f_ranked * r_ranked).sum(axis=1)
    denom = np.linalg.norm(f_ranked, axis=1) * np.linalg.norm(r_ranked, axis=1)
    return num / (denom + 1e-12)


def hhi_fast(weights_array: np.ndarray) -> float:
    w = np.asarray(weights_array, dtype=np.float32)
    w = np.abs(w[np.isfinite(w)])
    total = float(w.sum())
    if total <= 0:
        return 0.0
    w = w / total
    return float(np.dot(w, w))


def participation_cap_filter(tickers: Iterable[Any], advs: Iterable[float], weights: Iterable[float], portfolio_value: float, participation_cap: float):
    ticker_arr = np.asarray(list(tickers), dtype=object)
    adv_arr = np.asarray(list(advs), dtype=np.float64)
    weight_arr = np.asarray(list(weights), dtype=np.float64)
    required_trades = float(portfolio_value) * np.abs(weight_arr)
    eligible_mask = (required_trades / np.maximum(adv_arr, 1.0)) <= float(participation_cap)
    return ticker_arr[eligible_mask].tolist()


def update_cusum_state(state: Dict[str, float], new_ic: float, long_run_mean: float) -> float:
    value = max(0.0, float(state.get("value", 0.0)) + float(new_ic) - float(long_run_mean))
    state["value"] = value
    state["target"] = float(long_run_mean)
    return value


def bitwise_alignment_score(ic_series: np.ndarray, characteristic_z: np.ndarray) -> float:
    ic_bits = (np.asarray(ic_series) > 0).astype(np.int8)
    char_bits = (np.asarray(characteristic_z) > 0).astype(np.int8)
    n = min(ic_bits.size, char_bits.size)
    if n == 0:
        return np.nan
    aligned = np.bitwise_not(np.bitwise_xor(ic_bits[:n], char_bits[:n])).astype(bool)
    return float(np.mean(aligned))


# ---------------------------------------------------------------------------
# Kernel Pre-Warming — eliminates the JIT compilation stall on first API call.
# All @njit kernels are compiled at import time with tiny dummy arrays.
# ---------------------------------------------------------------------------
def _prewarm_kernels() -> None:
    _x = np.random.randn(64).astype(np.float64)
    _R = np.random.randn(30, 5).astype(np.float64)
    try:
        rolling_autocorr_1(_x, 10)
        drawdown_curve(np.abs(_x) + 0.01)
        cusum_statistic(_x)
        welford_rolling(_x, 10)
        rolling_corr_kernel(_x, _x + 0.1, 10)
        rolling_percentile_numba(_x, 10)
        rolling_ols_kernel(_x, _x + 0.1, 10)
        elastic_net_coordinate_descent(_R, _x[:30], 0.01, 0.5, 10)
        batched_forward_sums(_x, np.array([5, 10], dtype=np.int64))
    except Exception:
        pass  # never block the server from starting


_prewarm_kernels()
