"""Past-only two-stage DCC-GARCH estimation, without optimizer fallbacks."""

from __future__ import annotations

import numpy as np
import pandas as pd
from arch import arch_model
from scipy.optimize import minimize
from app.services.volatility_v2.core.performance import dcc_neg_ll_jit


def correlation(q):
    scale = np.sqrt(np.diag(q))
    if not np.isfinite(scale).all() or (scale <= 0).any():
        raise ValueError("DCC covariance diagonal must be positive and finite")
    result = q / np.outer(scale, scale)
    if np.linalg.eigvalsh(result).min() <= 0:
        raise ValueError("DCC correlation is not positive definite")
    return result


def fit_dcc(z):
    z = np.ascontiguousarray(z, dtype=float)
    if z.ndim != 2 or len(z) < 120 or z.shape[1] < 2 or not np.isfinite(z).all():
        raise ValueError(
            "DCC requires 120 finite standardized residuals and two assets"
        )
    qbar = z.T @ z / len(z)
    correlation(qbar)
    fits = []
    for initial in ((0.03, 0.94), (0.05, 0.8), (0.01, 0.6)):
        fit = minimize(
            lambda p: dcc_neg_ll_jit(z, qbar, p[0], p[1]),
            initial,
            method="SLSQP",
            bounds=((0, 0.999), (0, 0.999)),
            constraints={"type": "ineq", "fun": lambda p: 0.99999 - p.sum()},
            options={"maxiter": 500, "ftol": 1e-9},
        )
        if fit.success and np.isfinite(fit.fun) and fit.x.sum() < 1:
            fits.append(fit)
    if not fits:
        raise ValueError("DCC optimizer failed for all starting points")
    best = min(fits, key=lambda fit: fit.fun)
    a, b = best.x
    q = qbar.copy()
    for previous in z[:-1]:
        q = (1 - a - b) * qbar + a * np.outer(previous, previous) + b * q
    return float(a), float(b), qbar, q


def expanding_dcc(returns, min_train=252, refit_interval=63, annualization=252):
    """Covariance for date t uses data through t-1; latest forecast uses all observed data."""
    data = returns.to_numpy(dtype=float)
    if not np.isfinite(data).all() or returns.index.has_duplicates:
        raise ValueError("DCC requires finite aligned returns with unique dates")
    if (
        min_train < 120
        or len(data) <= min_train
        or refit_interval < 1
        or annualization <= 0
    ):
        raise ValueError("Invalid DCC training controls or insufficient observations")
    rows, parameters, covariances = [], [], []
    latest = None
    for start in range(min_train, len(data), refit_interval):
        stop = min(start + refit_interval, len(data))
        residuals, variances, means = [], [], []
        for asset in returns.columns:
            model = arch_model(
                returns[asset].iloc[:stop] * 100,
                mean="Constant",
                vol="GARCH",
                p=1,
                q=1,
                dist="t",
                rescale=False,
            )
            fitted = model.fit(
                last_obs=start, disp="off", show_warning=False, options={"maxiter": 500}
            )
            if fitted.convergence_flag != 0:
                raise ValueError(
                    f"GARCH marginal failed for {asset} at {returns.index[start]}"
                )
            residuals.append(
                (fitted.resid / fitted.conditional_volatility).iloc[:start].to_numpy()
            )
            means.append(float(fitted.params["mu"]) / 100)
            forecast = fitted.forecast(start=start - 1, horizon=1, reindex=False)
            variances.append(forecast.residual_variance.iloc[:, 0].to_numpy() / 10000)
        training_z = np.column_stack(residuals)
        a, b, qbar, q = fit_dcc(training_z)
        previous = training_z[-1]
        variance_path = np.column_stack(variances)
        parameters.append(
            {
                "training_observed_through": returns.index[start - 1],
                "a": a,
                "b": b,
                "training_size": start,
            }
        )
        for offset, position in enumerate(range(start, stop)):
            q = (1 - a - b) * qbar + a * np.outer(previous, previous) + b * q
            corr = correlation(q)
            variance = variance_path[offset]
            if not np.isfinite(variance).all() or (variance <= 0).any():
                raise ValueError("Invalid marginal variance forecast")
            covariance = corr * np.sqrt(np.outer(variance, variance)) * annualization
            covariances.append(covariance)
            rows.append(
                {
                    "date": returns.index[position],
                    "training_observed_through": returns.index[start - 1],
                    "forecast_observed_through": returns.index[position - 1],
                    "condition_number": float(np.linalg.cond(covariance)),
                    "correlation": corr.tolist(),
                }
            )
            previous = (data[position] - means) / np.sqrt(variance)
        q_next = (1 - a - b) * qbar + a * np.outer(previous, previous) + b * q
        next_variance = variance_path[stop - start]
        latest = (
            correlation(q_next)
            * np.sqrt(np.outer(next_variance, next_variance))
            * annualization
        )
    return {
        "timeline": rows,
        "parameters": parameters,
        "covariances": covariances,
        "forecast_covariance": pd.DataFrame(
            latest, index=returns.columns, columns=returns.columns
        ),
        "forecast_observed_through": returns.index[-1],
    }
