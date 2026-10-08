"""Validated signed-cone risk budgets and constrained within-portfolio alignment."""

from __future__ import annotations

import numpy as np
from scipy.linalg import null_space
from scipy.optimize import minimize


def _validate(covariance, weights, budgets, target, gross_cap):
    covariance = np.asarray(covariance, dtype=float)
    weights, budgets = (
        np.asarray(weights, dtype=float),
        np.asarray(budgets, dtype=float),
    )
    if covariance.shape != (len(weights), len(weights)) or len(budgets) != len(weights):
        raise ValueError("Risk-budget dimensions must match")
    if (
        not np.isfinite(covariance).all()
        or not np.isfinite(weights).all()
        or not np.isfinite(budgets).all()
    ):
        raise ValueError("Risk-budget inputs must be finite")
    if (
        not np.allclose(covariance, covariance.T)
        or np.linalg.eigvalsh(covariance).min() <= 0
    ):
        raise ValueError(
            "Risk budgeting requires positive definite symmetric covariance"
        )
    if (
        (budgets <= 0).any()
        or not np.isclose(budgets.sum(), 1)
        or target <= 0
        or gross_cap <= 0
        or np.abs(weights).sum() <= 0
    ):
        raise ValueError(
            "Budgets must be positive and sum to one; target, gross cap and exposure must be positive"
        )
    return covariance, weights, budgets


def fractions(weights, covariance):
    variance = float(weights @ covariance @ weights)
    if variance <= 0:
        raise ValueError("Risk fractions require positive portfolio variance")
    return weights * (covariance @ weights) / variance


def risk_budget_weights(covariance, weights, budgets, target=0.1, gross_cap=3):
    """Convex log-barrier risk-budget solution in the declared current sign cone."""
    covariance, weights, budgets = _validate(
        covariance, weights, budgets, target, gross_cap
    )
    signs = np.where(weights < 0, -1.0, 1.0)
    signed = covariance * np.outer(signs, signs)
    initial = np.sqrt(budgets / np.diag(signed))
    result = minimize(
        lambda x: 0.5 * x @ signed @ x - budgets @ np.log(x),
        initial,
        jac=lambda x: signed @ x - budgets / x,
        method="L-BFGS-B",
        bounds=[(1e-12, None)] * len(weights),
        options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-10},
    )
    if not result.success:
        raise ValueError(f"Convex risk-budget optimization failed: {result.message}")
    proposed = signs * result.x
    actual = fractions(proposed, covariance)
    if np.max(np.abs(actual - budgets)) > 1e-6:
        raise ValueError("Risk-budget solver did not meet the assigned risk fractions")
    proposed *= min(
        target / np.sqrt(proposed @ covariance @ proposed),
        gross_cap / np.abs(proposed).sum(),
    )
    return proposed, {
        "solver": "Convex quadratic minus weighted log barrier in the current sign cone",
        "risk_fraction_error": float(np.max(np.abs(actual - budgets))),
        "achieved_volatility": float(np.sqrt(proposed @ covariance @ proposed)),
        "gross_cap_binding": bool(np.isclose(np.abs(proposed).sum(), gross_cap)),
    }


def two_step_alignment(covariance, weights, budgets, target=0.1, gross_cap=3):
    """Preserve scaled net exposure and volatility while minimizing budget deviation.

    The review's minimum-change objective has zero change as a feasible optimum.
    This replacement minimizes actual risk-budget deviation. Net exposure and
    variance are parameterized exactly; SLSQP searches the remaining sphere.
    """
    covariance, weights, budgets = _validate(
        covariance, weights, budgets, target, gross_cap
    )
    scale = min(
        target / np.sqrt(weights @ covariance @ weights),
        gross_cap / np.abs(weights).sum(),
    )
    scaled = weights * scale
    variance = float(scaled @ covariance @ scaled)
    net = float(scaled.sum())
    ones = np.ones(len(weights))
    inverse_ones = np.linalg.solve(covariance, ones)
    center = inverse_ones * net / (ones @ inverse_ones)
    remaining = variance - float(center @ covariance @ center)
    signs = np.where(weights < 0, -1.0, 1.0)

    def objective(vector):
        return float(np.sum((fractions(vector, covariance) - budgets) ** 2))

    if len(weights) == 1 or remaining <= 1e-12 * variance:
        return (
            scaled,
            scaled.copy(),
            {
                "solver": "Unique feasible net/variance allocation",
                "budget_deviation_squared": objective(scaled),
                "exact_budget_alignment": bool(
                    np.max(np.abs(fractions(scaled, covariance) - budgets)) < 1e-6
                ),
            },
        )
    basis = null_space(ones[None, :])
    lower = np.linalg.cholesky(basis.T @ covariance @ basis)
    transform = (
        basis @ np.linalg.solve(lower.T, np.eye(len(lower))) * np.sqrt(remaining)
    )
    initial = lower.T @ basis.T @ (scaled - center) / np.sqrt(remaining)
    initial /= np.linalg.norm(initial)
    starts = [initial, -initial]
    if len(initial) > 1:
        starts.extend(np.eye(len(initial)))
        starts.extend(-np.eye(len(initial)))
    successes, failures = [], []
    for start in starts:
        if len(initial) == 1:
            candidate = center + transform @ start
            if (
                np.abs(candidate).sum() <= gross_cap + 1e-8
                and (candidate * signs >= -1e-8).all()
            ):
                successes.append(candidate)
            continue
        result = minimize(
            lambda u: objective(center + transform @ u),
            start,
            method="SLSQP",
            constraints=[
                {"type": "eq", "fun": lambda u: float(u @ u - 1)},
                {"type": "ineq", "fun": lambda u: signs * (center + transform @ u)},
                {
                    "type": "ineq",
                    "fun": lambda u: gross_cap - np.abs(center + transform @ u).sum(),
                },
            ],
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        candidate = center + transform @ result.x
        valid = (
            result.success
            and np.isclose(candidate.sum(), net, atol=1e-8)
            and np.isclose(
                candidate @ covariance @ candidate, variance, rtol=1e-6, atol=1e-10
            )
            and np.abs(candidate).sum() <= gross_cap + 1e-8
            and (candidate * signs >= -1e-8).all()
        )
        if valid:
            successes.append(candidate)
        else:
            failures.append(str(result.message))
    if not successes:
        raise ValueError(
            "Constrained budget-alignment optimization failed for all starts"
        )
    best = min(successes, key=objective)
    if objective(best) > objective(scaled) + 1e-8:
        raise ValueError(
            "Constrained budget alignment worsened the initial budget deviation"
        )
    return (
        scaled,
        best,
        {
            "solver": "Multistart constrained risk-budget deviation optimization; exact net/variance parameterization",
            "budget_deviation_squared": objective(best),
            "before_deviation_squared": objective(scaled),
            "exact_budget_alignment": bool(
                np.max(np.abs(fractions(best, covariance) - budgets)) < 1e-6
            ),
            "net_exposure_preserved": net,
            "volatility_preserved": float(np.sqrt(variance)),
            "successful_starts": len(successes),
            "failed_starts": failures,
            "global_optimality": "Exact two-point search for two assets; no global-optimum guarantee for higher dimensions",
        },
    )
