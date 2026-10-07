"""Meucci's exact minimum-torsion factors and additive variance attribution.

Algorithm reference: Meucci (2013), doi:10.2139/ssrn.2276632, alternating
orthogonal Procrustes and diagonal scale minimization in correlation space.
The review's TT'=Sigma constraint describes a factor square root, rather than
this return transformation, whose transformed covariance is diagonal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.linalg import eigh, polar


def minimum_torsion(covariance, weights, tolerance=1e-10, max_iterations=10000):
    sigma = covariance.to_numpy(dtype=float)
    if not np.isfinite(sigma).all() or not np.allclose(sigma, sigma.T):
        raise ValueError("Minimum torsion requires finite symmetric covariance")
    if tolerance <= 0 or max_iterations < 2:
        raise ValueError("Invalid minimum-torsion convergence controls")
    standard_deviation = np.sqrt(np.diag(sigma))
    correlation = sigma / np.outer(standard_deviation, standard_deviation)
    eigenvalues, eigenvectors = eigh(correlation)
    if eigenvalues.min() <= 0:
        raise ValueError("Minimum torsion requires positive definite covariance")
    root = (eigenvectors * np.sqrt(eigenvalues)) @ eigenvectors.T
    diagonal = np.ones(len(sigma))
    previous = None
    for iteration in range(max_iterations):
        # polar(D C^1/2) gives the nearest orthogonal matrix in Frobenius norm.
        orthogonal, _ = polar(diagonal[:, None] * root)
        diagonal = np.diag(orthogonal @ root)
        perturbation = diagonal[:, None] * orthogonal
        objective = float(np.linalg.norm(root - perturbation, "fro"))
        if objective <= tolerance or (
            previous is not None
            and abs(previous - objective)
            <= tolerance * max(objective, tolerance) * len(sigma)
        ):
            break
        previous = objective
    else:
        raise ValueError("Minimum-torsion iteration did not converge")
    standardized_transform = np.linalg.solve(root.T, perturbation.T).T
    transform = (
        standardized_transform
        * standard_deviation[:, None]
        / standard_deviation[None, :]
    )
    factor_covariance = transform @ sigma @ transform.T
    if not np.allclose(
        factor_covariance, np.diag(np.diag(factor_covariance)), atol=1e-10, rtol=1e-7
    ):
        raise ValueError("Minimum-torsion factors did not decorrelate")
    vector = weights.reindex(covariance.columns).to_numpy(dtype=float)
    if not np.isfinite(vector).all():
        raise ValueError("Minimum-torsion weights must be finite")
    exposure = np.linalg.solve(transform.T, vector)
    contributions = exposure**2 * np.diag(factor_covariance)
    total = float(vector @ sigma @ vector)
    if total <= 0 or not np.isclose(contributions.sum(), total, rtol=1e-7):
        raise ValueError("Minimum-torsion risk contributions did not conserve variance")
    fractions = contributions / total
    positive = fractions[fractions > 0]
    return {
        "transformation": pd.DataFrame(
            transform, index=covariance.index, columns=covariance.columns
        ),
        "factor_covariance": pd.DataFrame(
            factor_covariance, index=covariance.index, columns=covariance.columns
        ),
        "attribution": [
            {
                "factor": name,
                "exposure": float(exposure[i]),
                "factor_variance": float(factor_covariance[i, i]),
                "variance_contribution": float(contributions[i]),
                "fraction_total_variance": float(fractions[i]),
            }
            for i, name in enumerate(covariance.columns)
        ],
        "effective_number_of_bets": float(np.exp(-np.sum(positive * np.log(positive)))),
        "iterations": iteration + 1,
        "objective": objective,
    }
