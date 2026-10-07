"""Rotated Clayton downside-return/upside-volatility dependence."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import rankdata
from statsmodels.distributions.copula.api import ClaytonCopula


def rotated_clayton(
    returns,
    volatility_changes,
    loss_threshold=0.15,
    tail_probability=0.20,
    horizon_sessions=1,
):
    """Condition on upper-tail volatility via V=F(-delta_vol), a lower-tail variable.

    Fit the full copula density. Fitting only selected tails without the tail
    selection normalization would not be maximum likelihood for this model.
    Empirical marginals limit inference to the observed support.
    """
    frame = pd.concat(
        [returns.rename("return"), volatility_changes.rename("vol_change")], axis=1
    ).dropna()
    if len(frame) < 120 or not 0 < tail_probability < 0.5 or not 0 < loss_threshold < 1:
        raise ValueError(
            "Clayton analysis requires 120 observations and valid loss/tail controls"
        )
    if not np.isfinite(frame.to_numpy()).all() or (frame.std() <= 0).any():
        raise ValueError("Clayton inputs must have finite nonzero observed variance")
    u = rankdata(frame["return"], method="average") / (len(frame) + 1)
    v = rankdata(-frame.vol_change, method="average") / (len(frame) + 1)
    uniforms = np.column_stack([u, v])

    def objective(theta):
        value = ClaytonCopula(theta=theta).logpdf(uniforms)
        return float(-value.sum()) if np.isfinite(value).all() else np.inf

    fit = minimize_scalar(
        objective, bounds=(0.001, 50), method="bounded", options={"xatol": 1e-7}
    )
    if not fit.success or not np.isfinite(fit.fun):
        raise ValueError("Clayton maximum-likelihood optimization failed")
    theta = float(fit.x)
    copula = ClaytonCopula(theta=theta)
    sorted_returns = np.sort(frame["return"].to_numpy())
    probabilities = np.array([0.01, 0.05, 0.5, 0.95])
    # P(U<=u | V<=v) = C(u,v)/v, inverted analytically.
    log_a = -theta * np.log(probabilities * tail_probability)
    log_b = -theta * np.log(tail_probability)
    log_inside = log_a + np.log1p(-np.exp(log_b - log_a) + np.exp(-log_a))
    conditional_u = np.exp(-log_inside / theta)
    conditional_returns = np.quantile(sorted_returns, conditional_u)
    frontier = []
    empirical_u = (np.arange(len(sorted_returns)) + 1) / (len(sorted_returns) + 1)
    loss_u = float(np.interp(-loss_threshold, sorted_returns, empirical_u))
    supported_loss = sorted_returns[0] <= -loss_threshold <= sorted_returns[-1]
    grid = np.linspace(0.02, 0.5, 49)
    for probability in grid:
        vthreshold = float(np.quantile(frame.vol_change, 1 - probability))
        loss_probability = (
            float(copula.cdf(np.array([[loss_u, probability]]))[0] / probability)
            if supported_loss
            else None
        )
        frontier.append(
            {
                "volatility_change_threshold": vthreshold,
                "volatility_upper_tail_probability": float(probability),
                "conditional_loss_probability": loss_probability,
                "loss_threshold": loss_threshold,
            }
        )
    # Least-extreme observed-support shock giving at least a 50% modeled loss probability.
    qualifying = [
        row
        for row in frontier
        if row["conditional_loss_probability"] is not None
        and row["conditional_loss_probability"] >= 0.5
    ]
    required = (
        max(qualifying, key=lambda row: row["volatility_upper_tail_probability"])
        if qualifying
        else None
    )
    return {
        "theta": theta,
        "lower_tail_dependence": float(2 ** (-1 / theta)),
        "observations": len(frame),
        "log_likelihood": float(-fit.fun),
        "rotation": f"({horizon_sessions}-session portfolio return, negative change in trailing portfolio volatility)",
        "horizon_sessions": horizon_sessions,
        "overlapping_window_limitation": "Overlapping horizons imply serial dependence; no IID parameter standard errors are claimed",
        "estimation": "Full-sample rank pseudo-likelihood with empirical marginals",
        "conditioning_event": f"Volatility change above its observed {1 - tail_probability:.0%} quantile",
        "volatility_change_threshold": float(
            np.quantile(frame.vol_change, 1 - tail_probability)
        ),
        "conditional_return_quantiles": [
            {
                "quantile": float(p),
                "return": float(value),
                "unconditional_return_cdf": float(u_value),
            }
            for p, value, u_value in zip(
                probabilities, conditional_returns, conditional_u
            )
        ],
        "reverse_stress": required,
        "reverse_stress_status": "ok" if required else "unavailable",
        "reverse_stress_reason": None
        if required
        else (
            "Requested loss lies outside observed empirical return support"
            if not supported_loss
            else "No observed-support shock attains a 50% conditional loss probability"
        ),
        "frontier": frontier,
        "near_independence_boundary": theta < 0.005,
        "limitation": "Conditional distribution is a fitted model, not a causal return-volatility mapping; empirical marginal support cannot extrapolate unseen losses",
    }
