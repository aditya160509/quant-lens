"""Performance helpers for PCA V2.

These helpers keep feature code small while avoiding repeated conversions,
slow Python loops, and unstable matrix operations.
"""

from __future__ import annotations

from functools import lru_cache, wraps
from time import perf_counter
from typing import Any, Callable

import numpy as np
import pandas as pd


def timed(label: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = perf_counter()
            out = fn(*args, **kwargs)
            elapsed = perf_counter() - start
            if isinstance(out, dict):
                out.setdefault("performance", {})[label] = round(elapsed, 6)
            return out

        return wrapper

    return decorator


def contiguous_float_frame(frame: pd.DataFrame) -> np.ndarray:
    x = frame.to_numpy(dtype=np.float64)
    if not np.isfinite(x).all():
        raise ValueError("Finite observed returns required")
    return np.ascontiguousarray(x)


def fast_cov(frame: pd.DataFrame) -> np.ndarray:
    x = contiguous_float_frame(frame)
    if x.shape[0] < 2:
        return np.zeros((x.shape[1], x.shape[1]), dtype=float)
    x = x - x.mean(axis=0, keepdims=True)
    return (x.T @ x) / max(x.shape[0] - 1, 1)


def safe_pinv(matrix: np.ndarray, ridge: float = 1e-8) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    if arr.size == 0:
        return arr
    return np.linalg.pinv(arr + np.eye(arr.shape[0]) * ridge)


def batched_corr(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    std = x.std(ddof=1).replace(0, np.nan)
    z = ((x - x.mean()) / std)
    if not np.isfinite(z.to_numpy()).all():
        raise ValueError("Correlation requires finite returns and positive asset variance")
    corr = (z.to_numpy(dtype=float).T @ z.to_numpy(dtype=float)) / max(len(z) - 1, 1)
    return pd.DataFrame(corr, index=x.columns, columns=x.columns)


def downsample_records(frame: pd.DataFrame, limit: int = 1000) -> pd.DataFrame:
    if frame is None or len(frame) <= limit:
        return frame
    idx = np.unique(np.round(np.linspace(0, len(frame) - 1, limit)).astype(int))
    return frame.iloc[idx]


@lru_cache(maxsize=256)
def normalized_symbol_tuple(symbols: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(s).strip().upper().replace(".", "_").replace("-", "_") for s in symbols if str(s).strip()}))


def frame_fingerprint(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"rows": 0, "cols": 0}
    return {
        "rows": int(frame.shape[0]),
        "cols": int(frame.shape[1]),
        "start": str(frame.index.min())[:10],
        "end": str(frame.index.max())[:10],
    }
