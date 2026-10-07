"""Observed-return covariance estimates and Euler portfolio attribution."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf, OAS


def covariance_estimates(returns, half_life=63, annualization=252):
    """Missing returns are an error: callers must explicitly align observations."""
    values = returns.to_numpy(dtype=float)
    if values.ndim != 2 or values.shape[0] < 30 or values.shape[1] < 2:
        raise ValueError(
            "Covariance estimation requires 30 aligned observations and two assets"
        )
    if not np.isfinite(values).all():
        raise ValueError("Covariance estimation requires finite observed returns")
    if half_life <= 0 or annualization <= 0:
        raise ValueError("Half-life and annualization must be positive")
    decay = np.exp2(-np.arange(len(values) - 1, -1, -1) / half_life)
    decay /= decay.sum()
    centered = values - decay @ values
    effective_correction = 1 - decay @ decay
    matrices = {
        "sample": np.cov(values, rowvar=False, ddof=1),
        "ewma": (centered * decay[:, None]).T @ centered / effective_correction,
        "ledoit_wolf": LedoitWolf().fit(values).covariance_,
        "oas": OAS().fit(values).covariance_,
    }
    return {
        name: pd.DataFrame(
            matrix * annualization, index=returns.columns, columns=returns.columns
        )
        for name, matrix in matrices.items()
    }


def portfolio_attribution(covariance, weights):
    """Euler contributions sum to volatility; ordered pair contributions to variance."""
    matrix = covariance.to_numpy(dtype=float)
    vector = weights.reindex(covariance.columns).to_numpy(dtype=float)
    if not np.isfinite(matrix).all() or not np.isfinite(vector).all():
        raise ValueError("Portfolio covariance and weights must be finite")
    if not np.allclose(matrix, matrix.T, atol=1e-12):
        raise ValueError("Portfolio covariance must be symmetric")
    if np.linalg.eigvalsh(matrix).min() <= 0:
        raise ValueError("Portfolio covariance must be positive definite")
    variance = float(vector @ matrix @ vector)
    if variance <= 0:
        raise ValueError("Portfolio risk attribution requires positive variance")
    volatility = float(np.sqrt(variance))
    marginal = matrix @ vector / volatility
    component = vector * marginal
    rows = [
        {
            "asset": asset,
            "weight": float(vector[i]),
            "marginal_volatility": float(marginal[i]),
            "component_volatility": float(component[i]),
            "fraction_total_risk": float(component[i] / volatility),
        }
        for i, asset in enumerate(covariance.columns)
    ]
    pairwise = covariance * np.outer(vector, vector)
    minimum = np.linalg.solve(matrix, np.ones(len(vector)))
    minimum /= minimum.sum()
    return {
        "volatility": volatility,
        "variance": variance,
        "assets": rows,
        "pairwise_variance": pairwise,
        "minimum_variance_weights": minimum,
    }
