"""Monthly-correlation DCC-MIDAS targets with jointly estimated Beta decay.

Colacito, Engle and Ghysels (2011), doi:10.1016/j.jeconom.2011.02.013.
Convex matrix weights preserve positive definiteness, unlike unconstrained
pairwise intercept/slope regressions. Only completed prior months are used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from .dcc import correlation
from .performance import _jit


def beta_weights(lags, theta):
    if lags < 2 or not 1 <= theta <= 100:
        raise ValueError("MIDAS requires at least two lags and Beta theta in [1,100]")
    # Interior grid avoids the Beta endpoint singularity and a forced zero oldest weight.
    grid = np.arange(1, lags + 1) / (lags + 1)
    log_weights = (theta - 1) * np.log1p(-grid)
    weights = np.exp(log_weights - log_weights.max())
    return weights / weights.sum()


def monthly_correlations(z, index):
    frame = pd.DataFrame(z, index=pd.DatetimeIndex(index))
    result = {}
    for month, observed in frame.groupby(frame.index.to_period("M")):
        if len(observed) < max(10, frame.shape[1] + 1):
            continue
        values = observed.to_numpy(dtype=float)
        covariance = values.T @ values / len(values)
        result[month] = correlation(covariance)
    return result


def lag_matrices(monthly, date, lags):
    current = pd.Timestamp(date).to_period("M")
    required = [current - lag for lag in range(1, lags + 1)]
    if any(month not in monthly for month in required):
        raise ValueError(
            f"MIDAS requires {lags} consecutive observed completed months before {current}"
        )
    return np.stack([monthly[month] for month in required])


@_jit
def _likelihood(z, targets, a, b):
    q = targets[0].copy()
    loss = 0.0
    for pos in range(1, len(z)):
        q = (1 - a - b) * targets[pos] + a * np.outer(z[pos - 1], z[pos - 1]) + b * q
        scale = np.sqrt(np.diag(q))
        r = q / np.outer(scale, scale)
        sign, logdet = np.linalg.slogdet(r)
        if sign <= 0:
            return np.inf
        loss += 0.5 * (logdet + z[pos] @ np.linalg.solve(r, z[pos]))
    return loss


def fit_midas(z, index, lags=36):
    monthly = monthly_correlations(z, index)
    cubes, positions = [], []
    for position, date in enumerate(index):
        try:
            cubes.append(lag_matrices(monthly, date, lags))
            positions.append(position)
        except ValueError:
            continue
    if len(positions) < 120:
        raise ValueError(
            "DCC-MIDAS requires 120 training observations after the completed-month lag warmup"
        )
    if not np.array_equal(np.diff(positions), np.ones(len(positions) - 1)):
        raise ValueError(
            "Missing completed-month coverage inside DCC-MIDAS training period"
        )
    cube = np.stack(cubes)
    data = np.ascontiguousarray(z[positions])

    def objective(parameters):
        weights = beta_weights(lags, parameters[2])
        targets = np.ascontiguousarray(np.einsum("tkij,k->tij", cube, weights))
        return _likelihood(data, targets, parameters[0], parameters[1])

    fits = []
    for initial in ((0.03, 0.94, 2), (0.05, 0.8, 5), (0.01, 0.6, 1)):
        result = minimize(
            objective,
            initial,
            method="SLSQP",
            bounds=((0, 0.999), (0, 0.999), (1, 100)),
            constraints={"type": "ineq", "fun": lambda p: 0.99999 - p[:2].sum()},
            options={"maxiter": 500, "ftol": 1e-8},
        )
        if result.success and np.isfinite(result.fun) and result.x[:2].sum() < 1:
            fits.append(result)
    if not fits:
        raise ValueError("DCC-MIDAS optimizer failed for all starting points")
    fit = min(fits, key=lambda candidate: candidate.fun)
    a, b, theta = fit.x
    targets = np.einsum("tkij,k->tij", cube, beta_weights(lags, theta))
    q = targets[0].copy()
    for pos in range(1, len(data)):
        q = (
            (1 - a - b) * targets[pos]
            + a * np.outer(data[pos - 1], data[pos - 1])
            + b * q
        )
    return float(a), float(b), float(theta), q, monthly
