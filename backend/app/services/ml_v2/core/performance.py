"""Shared numeric helpers for ML V2: rank IC, Sharpe, drawdown, payload normalisation, optional boosters."""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def _optional(module_name: str, attr: str) -> Any | None:
    try:
        return getattr(__import__(module_name, fromlist=[attr]), attr)
    except ImportError:
        return None


XGBOOST = _optional("xgboost", "XGBRegressor")
LGBM = _optional("lightgbm", "LGBMRegressor")
CATBOOST = _optional("catboost", "CatBoostRegressor")


def fast_spearman_ic(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman IC without scipy p-value overhead; NaN when fewer than 4 pairs or a constant side (undefined, not zero)."""
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 4:
        return float("nan")
    xv = x[valid]
    yv = y[valid]
    rx = rankdata(xv, method="average")
    ry = rankdata(yv, method="average")
    rx -= rx.mean()
    ry -= ry.mean()
    denom = float(np.sqrt(np.dot(rx, rx)) * np.sqrt(np.dot(ry, ry)))
    return float(np.dot(rx, ry) / denom) if denom > 1e-12 else float("nan")



def sharpe(series: np.ndarray | pd.Series | Iterable, ann: float = 252.0) -> float:
    arr = np.asarray(series, dtype=np.float64).ravel()
    finite = arr[np.isfinite(arr)]
    n = len(finite)
    if n < 2:
        return float("nan")  # undefined with fewer than two observations
    mu = finite.mean()
    sd = finite.std(ddof=1)
    return float(mu / sd * math.sqrt(ann)) if sd > 1e-12 else float("nan")



def max_drawdown(equity: np.ndarray | pd.Series | Iterable) -> float:
    arr = np.asarray(equity, dtype=np.float64).ravel()
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return 0.0
    running_max = np.maximum.accumulate(arr)
    dd = arr / np.where(running_max > 1e-12, running_max, 1.0) - 1.0
    return float(dd.min())


def equity_from_returns(returns: np.ndarray | pd.Series | Iterable) -> np.ndarray:
    arr = np.asarray(returns, dtype=np.float64).ravel()
    arr = np.where(np.isfinite(arr), arr, 0.0)
    return np.cumprod(1.0 + arr)


def normalize_payload(
    payload: dict[str, Any] | None,
    *,
    defaults: dict[str, Any],
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """P12 — One dict copy + one pass; no intermediate dicts."""
    out = defaults.copy()
    if not payload:
        return out
    al = aliases or {}
    for k, v in payload.items():
        if v is None:
            continue
        out[al.get(k, k)] = v
    return out
