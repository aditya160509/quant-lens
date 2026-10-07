"""Factors V2 covariance helpers."""

from __future__ import annotations
import math
from typing import Any, Dict
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from .performance import fast_covariance_matrix, dcc_recursion_kernel


def covariance_payload(
    rets: pd.DataFrame, method: str = "sample", half_life: int = 63
) -> Dict[str, Any]:
    x = rets.dropna()
    if len(x) < 2:
        raise ValueError("Covariance requires at least two complete observations")
    if method not in {"sample", "ewma", "ledoit_wolf"}:
        raise ValueError(f"Unsupported covariance method: {method}")
    if method == "ewma":
        lam = math.exp(math.log(0.5) / max(half_life, 1))
        weights = np.array([(1 - lam) * lam**i for i in range(len(x) - 1, -1, -1)])
        weights = weights / weights.sum()
        xm = x - (x * weights[:, None]).sum(axis=0)
        cov = pd.DataFrame(
            (xm.values * weights[:, None]).T @ xm.values * 252,
            index=x.columns,
            columns=x.columns,
        )
    elif method == "ledoit_wolf":
        lw = LedoitWolf().fit(x.values.astype(np.float64, copy=False))
        cov = pd.DataFrame(lw.covariance_ * 252, index=x.columns, columns=x.columns)
    else:
        cov = pd.DataFrame(
            fast_covariance_matrix(x.values, annualize=252.0, dtype=np.float32),
            index=x.columns,
            columns=x.columns,
        )
    corr = x.corr()
    eig = np.linalg.eigvalsh(cov.values)
    return {
        "covariance": cov,
        "correlation": corr,
        "volatility": np.sqrt(np.diag(cov)).tolist(),
        "eigenvalues": sorted([float(v) for v in eig], reverse=True),
        "condition_number": float(
            np.nanmax(eig)
            / max(np.nanmin(eig[eig > 1e-12]) if (eig > 1e-12).any() else 1e-12, 1e-12)
        ),
    }


def dcc_garch_payload(
    rets: pd.DataFrame, a: float = 0.03, b: float = 0.94
) -> Dict[str, Any]:
    """DCC-style covariance using EWMA vol standardization and Engle recursion.

    This is a deterministic local implementation path when the full arch DCC
    class is unavailable or too expensive for an API call. It estimates dynamic
    conditional correlations from standardized residuals and returns the latest
    annualized covariance.
    """
    x = rets.dropna()
    if len(x) < 80:
        return {}
    if a < 0 or b < 0 or a + b >= 1:
        raise ValueError("Invalid DCC parameters")
    vol = x.ewm(span=63, min_periods=20).std().replace(0, np.nan)
    z = (x / vol).replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 60:
        return {}
    qbar = fast_covariance_matrix(z.values, annualize=1.0, dtype=np.float32)
    if qbar.size == 0:
        return {}
    q, corr_path_arr = dcc_recursion_kernel(
        z.values.astype(float), qbar.astype(float), a, b
    )
    diag = np.sqrt(np.clip(np.diag(q), 1e-12, None))
    r = q / np.outer(diag, diag)
    corr_path = corr_path_arr.tolist()
    latest_vol = vol.reindex(z.index).iloc[-1]
    cov = pd.DataFrame(
        np.diag(latest_vol) @ r @ np.diag(latest_vol) * 252,
        index=x.columns,
        columns=x.columns,
    )
    return {
        "covariance": cov,
        "correlation": pd.DataFrame(r, index=x.columns, columns=x.columns),
        "avg_correlation_path": pd.Series(corr_path, index=z.index),
        "a": a,
        "b": b,
    }
