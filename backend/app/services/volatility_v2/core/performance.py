"""Performance primitives for Volatility V2.

The module is intentionally dependency-light. If numba is unavailable, the
public wrappers still work with NumPy fallbacks so feature execution does not
break in constrained environments.
"""

from __future__ import annotations

import math
import os

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_vol_v2")

import numpy as np

try:
    from scipy.linalg import solve_triangular
except Exception:  # pragma: no cover
    solve_triangular = None

try:  # pragma: no cover - exercised only when numba is installed.
    from numba import njit, prange
except Exception:  # pragma: no cover
    njit = None
    prange = range


def _identity_decorator(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


_jit = njit(cache=True, fastmath=False) if njit else _identity_decorator()
_jit_parallel = njit(cache=True, parallel=True, fastmath=False) if njit else _identity_decorator()


@_jit
def newey_west_lrv_jit(x: np.ndarray, bandwidth: int) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mu = 0.0
    for i in range(n):
        mu += x[i]
    mu /= n
    gamma0 = 0.0
    for i in range(n):
        v = x[i] - mu
        gamma0 += v * v
    gamma0 /= n
    lrv = gamma0
    max_lag = min(bandwidth, n - 1)
    for lag in range(1, max_lag + 1):
        cov = 0.0
        for t in range(lag, n):
            cov += (x[t] - mu) * (x[t - lag] - mu)
        cov /= n
        weight = 1.0 - lag / (bandwidth + 1.0)
        lrv += 2.0 * weight * cov
    return max(lrv, 0.0)


@_jit
def sjm_viterbi(dist: np.ndarray, jump_penalty: float) -> np.ndarray:
    t_len, k_len = dist.shape
    cost = np.empty((t_len, k_len), dtype=np.float64)
    back = np.zeros((t_len, k_len), dtype=np.int64)
    for k in range(k_len):
        cost[0, k] = dist[0, k]
    for t in range(1, t_len):
        for k in range(k_len):
            best_cost = 1e300
            best_prev = 0
            for j in range(k_len):
                pen = jump_penalty * np.float64(j != k)
                val = cost[t - 1, j] + pen
                if val < best_cost:
                    best_cost = val
                    best_prev = j
            cost[t, k] = dist[t, k] + best_cost
            back[t, k] = best_prev
    path = np.empty(t_len, dtype=np.int64)
    best = 0
    best_cost = cost[t_len - 1, 0]
    for k in range(1, k_len):
        if cost[t_len - 1, k] < best_cost:
            best_cost = cost[t_len - 1, k]
            best = k
    path[t_len - 1] = best
    for t in range(t_len - 2, -1, -1):
        path[t] = back[t + 1, path[t + 1]]
    return path


@_jit
def autocorr_raw_jit(x: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return np.nan
    count = 0
    mean = 0.0
    for i in range(n):
        v = x[i]
        if not math.isnan(v) and not math.isinf(v):
            mean += v
            count += 1
    if count < 3:
        return np.nan
    mean /= count
    c0 = 0.0
    c1 = 0.0
    prev = 0.0
    have_prev = False
    for i in range(n):
        v = x[i]
        if math.isnan(v) or math.isinf(v):
            have_prev = False
            continue
        dv = v - mean
        c0 += dv * dv
        if have_prev:
            c1 += dv * prev
        prev = dv
        have_prev = True
    return c1 / c0 if c0 > 1e-12 else np.nan


@_jit
def rolling_rank_pct_last_jit(arr: np.ndarray, window: int) -> np.ndarray:
    n = len(arr)
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = np.nan
    for i in range(window - 1, n):
        last = arr[i]
        if math.isnan(last) or math.isinf(last):
            continue
        count = 0
        rank = 0
        for j in range(i - window + 1, i + 1):
            v = arr[j]
            if math.isnan(v) or math.isinf(v):
                continue
            count += 1
            if v <= last:
                rank += 1
        if count > 0:
            out[i] = rank / count * 100.0
    return out


@_jit
def garch_loop(vals: np.ndarray, omega: float, alpha: float, beta: float, gamma: float, unconditional: float, model_id: int) -> np.ndarray:
    n = len(vals)
    out = np.empty(n, dtype=np.float64)
    out[0] = max(unconditional, 1e-10)
    for i in range(1, n):
        e = vals[i - 1]
        e2 = e * e
        prev = out[i - 1]
        if model_id == 4:
            denom = math.sqrt(max(prev, 1e-12))
            out[i] = math.exp((1.0 - beta) * math.log(max(unconditional, 1e-10)) + beta * math.log(max(prev, 1e-10)) + alpha * (math.fabs(e) / denom - 0.798) - math.fabs(gamma) * e / denom)
        elif model_id == 1 or model_id == 2:
            indicator = 1.0 if e < 0.0 else 0.0
            out[i] = max(omega + (alpha + gamma * indicator) * e2 + beta * prev, 1e-10)
        elif model_id == 3:
            shock = 0.55 * e2 + 0.45 * prev
            out[i] = max(omega + alpha * shock + beta * prev, 1e-10)
        else:
            out[i] = max(omega + alpha * e2 + beta * prev, 1e-10)
    return out


@_jit
def realized_garch_nll(
    r_np: np.ndarray,
    log_x: np.ndarray,
    omega: float,
    beta: float,
    gamma: float,
    xi: float,
    phi: float,
    tau1: float,
    tau2: float,
    sigma_u: float,
) -> float:
    n = len(r_np)
    log_var = math.log(max(r_np[0] * r_np[0] + 1e-10, 1e-10))
    ll = 0.0
    for t in range(1, n):
        log_var = omega + beta * log_var + gamma * log_x[t - 1]
        sig2 = math.exp(log_var)
        if sig2 < 1e-12:
            sig2 = 1e-12
        z = r_np[t] / math.sqrt(sig2)
        u = log_x[t] - (xi + phi * log_var + tau1 * z + tau2 * (z * z - 1.0))
        ll += -0.5 * (log_var + z * z) - 0.5 * ((u / sigma_u) ** 2 + 2.0 * math.log(sigma_u))
    return -ll


@_jit
def dcc_neg_ll_jit(z: np.ndarray, qbar: np.ndarray, a: float, b: float) -> float:
    n_t, n = z.shape
    q = qbar.copy()
    ll = 0.0
    one_minus = 1.0 - a - b
    for t in range(1, n_t):
        for i in range(n):
            for j in range(n):
                q[i, j] = one_minus * qbar[i, j] + a * z[t - 1, i] * z[t - 1, j] + b * q[i, j]
        d = np.empty(n, dtype=np.float64)
        for i in range(n):
            d[i] = math.sqrt(max(q[i, i], 1e-12))
        rmat = np.empty((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                rmat[i, j] = q[i, j] / (d[i] * d[j])
        sign, logdet = np.linalg.slogdet(rmat)
        if sign <= 0:
            return 1e9
        inv = np.linalg.inv(rmat)
        quad = 0.0
        for i in range(n):
            tmp = 0.0
            for j in range(n):
                tmp += inv[i, j] * z[t, j]
            quad += z[t, i] * tmp
        ll += logdet + quad
    return 0.5 * ll


@_jit_parallel
def stationary_bootstrap_jit(n: int, reps: int, p: float, seed: int = 17) -> np.ndarray:
    np.random.seed(seed)
    out = np.empty((reps, n), dtype=np.int64)
    for r in prange(reps):
        idx = np.random.randint(0, n)
        for t in range(n):
            if t == 0 or np.random.random() < p:
                idx = np.random.randint(0, n)
            else:
                idx = (idx + 1) % n
            out[r, t] = idx
    return out


@_jit
def dcc_correlation_path(z: np.ndarray, qbar: np.ndarray, a: float, b: float) -> np.ndarray:
    t_len, n = z.shape
    q = qbar.copy()
    out = np.zeros((t_len, n, n), dtype=np.float64)
    one_minus = 1.0 - a - b
    for i in range(n):
        out[0, i, i] = 1.0
    for t in range(1, t_len):
        for i in range(n):
            for j in range(n):
                q[i, j] = one_minus * qbar[i, j] + a * z[t - 1, i] * z[t - 1, j] + b * q[i, j]
        for i in range(n):
            for j in range(n):
                denom = math.sqrt(max(q[i, i], 1e-12)) * math.sqrt(max(q[j, j], 1e-12))
                val = q[i, j] / max(denom, 1e-12)
                out[t, i, j] = min(0.999, max(-0.999, val))
    return out


def var_ma_matrices_fast(coefs: list[np.ndarray], horizon: int) -> np.ndarray:
    n = coefs[0].shape[0]
    phi = np.zeros((horizon, n, n), dtype=float)
    phi[0] = np.eye(n)
    for h in range(1, horizon):
        for lag, a in enumerate(coefs, start=1):
            if h - lag >= 0:
                phi[h] += phi[h - lag] @ a
    return phi


def generalized_fevd_fast(coefs: list[np.ndarray], sigma: np.ndarray, horizon: int = 10) -> np.ndarray:
    phi = var_ma_matrices_fast(coefs, horizon)
    n = sigma.shape[0]
    phi_sigma = phi @ sigma
    numerator = np.einsum("hij,hij->ij", phi_sigma, phi_sigma, optimize=True)
    numerator = numerator / np.maximum(np.diag(sigma), 1e-12)[None, :]
    denom = np.einsum("hij,hkj->hik", phi_sigma, phi, optimize=True)[:, np.arange(n), np.arange(n)].sum(axis=0)
    theta = numerator / np.maximum(denom[:, None], 1e-12)
    return theta / np.maximum(theta.sum(axis=1, keepdims=True), 1e-12)


def build_var_design_matrix(arr: np.ndarray, p: int) -> tuple[np.ndarray, np.ndarray]:
    arr = np.ascontiguousarray(arr, dtype=float)
    idx = np.arange(p, len(arr))
    lag_stack = np.hstack([arr[idx - lag] for lag in range(1, p + 1)])
    return np.column_stack([np.ones(len(idx)), lag_stack]), arr[p:]


def ols_hac_fast(x: np.ndarray, y: np.ndarray, bandwidth: int) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    try:
        q, r = np.linalg.qr(x)
        beta = solve_triangular(r, q.T @ y, check_finite=False) if solve_triangular else np.linalg.solve(r, q.T @ y)
    except Exception:
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
    resid = y - x @ beta
    xtx = x.T @ x
    try:
        xtx_inv = np.linalg.inv(xtx)
    except np.linalg.LinAlgError:
        xtx_inv = np.linalg.pinv(xtx)
    xe = x * resid[:, None]
    meat = xe.T @ xe
    for lag in range(1, min(bandwidth, len(y) - 1) + 1):
        w = 1.0 - lag / (bandwidth + 1.0)
        gamma = xe[lag:].T @ xe[:-lag]
        meat += w * (gamma + gamma.T)
    cov = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    r2 = 1.0 - float(np.sum(resid**2) / max(np.sum((y - y.mean()) ** 2), 1e-12))
    return beta, se, r2, resid
