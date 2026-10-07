"""Live Factors numerical kernels and reproducible runtime metadata."""

from __future__ import annotations
import hashlib
import json
from functools import lru_cache
from typing import Any, Dict, Iterable, Tuple
import numpy as np
from numba import njit


def compute_mode(payload: Dict[str, Any] | None) -> str:
    mode = str((payload or {}).get("compute_mode", "realtime")).lower()
    return "research" if mode in {"research", "async", "full"} else "realtime"


@lru_cache(maxsize=256)
def _cached_hash(material: str) -> str:
    """LRU-cached SHA-256 digest so identical payloads skip re-hashing."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def stable_cache_key(
    feature_id: str, payload: Dict[str, Any] | None, namespace: str
) -> str:
    material = json.dumps(payload or {}, sort_keys=True, default=str)
    # blake2b is materially faster than sha256 for short API payloads while
    # remaining deterministic and collision-resistant enough for cache keys.
    digest = hashlib.blake2b(material.encode("utf-8"), digest_size=8).hexdigest()
    return f"factors_v2:{feature_id}:{namespace}:{digest}"


@njit(cache=True, fastmath=False)
def dcc_recursion_kernel(
    z: np.ndarray, qbar: np.ndarray, a: float, b: float
) -> Tuple[np.ndarray, np.ndarray]:
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


def runtime_meta(
    feature_id: str,
    payload: Dict[str, Any] | None,
    constraints: Iterable[str] | None = None,
) -> Dict[str, Any]:
    return {
        "compute_mode": compute_mode(payload),
        "contract_status": "implemented_with_realtime_constraints",
        "real_time_constraints": list(constraints or []),
        "missing_data_policy": "use complete local observations; surface reduced universe and unavailable institutional data explicitly",
        "cache_key": stable_cache_key(feature_id, payload, "runtime"),
    }


@njit(cache=True, fastmath=False)
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


def fast_covariance_matrix(
    matrix: np.ndarray, annualize: float = 1.0, dtype=np.float32
) -> np.ndarray:
    R = np.asarray(matrix, dtype=dtype)
    R = R[np.isfinite(R).all(axis=1)] if R.ndim == 2 else R
    if R.ndim != 2 or R.shape[0] < 2:
        return np.empty((0, 0), dtype=np.float64)
    centered = R - R.mean(axis=0, keepdims=True)
    cov = np.dot(centered.T, centered) / max(R.shape[0] - 1, 1)
    return np.asarray(cov * annualize, dtype=np.float64)
