"""Shared library-backed Volatility statistical comparisons."""

from __future__ import annotations
import numpy as np
import pandas as pd
from .performance import newey_west_lrv_jit


def newey_west_lrv(values: np.ndarray, bandwidth: int | None = None) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return 0.0
    n = len(x)
    bandwidth = int(bandwidth if bandwidth is not None else max(1, n ** (1 / 3)))
    return float(newey_west_lrv_jit(x, bandwidth))


def model_confidence_set(
    losses: dict[str, pd.Series], alpha: float = 0.10, reps: int = 200
) -> list[str]:
    from arch.bootstrap import MCS

    aligned = pd.concat(losses, axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if aligned.empty:
        return []
    if len(aligned.columns) == 1:
        return list(aligned.columns)
    if len(aligned) < 30:
        raise ValueError("MCS requires at least 30 aligned held-out losses")
    mcs = MCS(
        aligned,
        size=alpha,
        reps=reps,
        block_size=max(2, int(len(aligned) ** (1 / 3))),
        method="R",
        bootstrap="stationary",
        seed=17,
    )
    mcs.compute()
    return list(mcs.included)
