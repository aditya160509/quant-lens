"""Feature 10: Factor-Based Portfolio Optimizer."""

from typing import Any, Dict, Optional

import numpy as np

from app.services.factors_v2.core.analytics import (
    covariance_payload,
    factor_returns,
    response,
)


def run(payload):
    from app.services.factors_v2.core.optimization import solve, alignment

    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 756)))
    if len(rets) < 30:
        raise ValueError("Insufficient factor return observations")
    cov = covariance_payload(rets, payload.get("covariance_method", "ledoit_wolf"))[
        "covariance"
    ]
    names = list(rets)
    mu = rets.mean().to_numpy() * 252
    manual = payload.get("expected_returns")
    if manual is not None:
        if set(manual) != set(names):
            raise ValueError(
                "Expected returns must specify every selected factor exactly"
            )
        mu = np.array([manual[n] for n in names], float)
    bl = _black_litterman_factor(payload, names, cov.to_numpy(), mu)
    if bl:
        mu = np.array(bl["posterior"])
    robust = (
        float(payload.get("robust_penalty", 0.25)) if payload.get("robust", True) else 0
    )
    w, dual = solve(
        mu,
        cov.to_numpy(),
        payload,
        float(payload.get("risk_aversion", 5)),
        robust,
        len(rets),
    )
    rows = [
        {
            "factor": n,
            "weight": w[i],
            "expected_return_contribution": w[i] * mu[i],
            "variance_contribution": w[i] * (cov.to_numpy() @ w)[i],
        }
        for i, n in enumerate(names)
    ]
    frontier = []
    for lam in np.geomspace(0.1, 100, 50):
        weights, _ = solve(mu, cov.to_numpy(), payload, lam, robust, len(rets))
        frontier.append(
            {
                "risk_aversion": lam,
                "expected_return": float(weights @ mu),
                "volatility": float(np.sqrt(weights @ cov.to_numpy() @ weights)),
            }
        )
    fap = alignment(payload.get("alpha_signal"), payload.get("risk_loadings"))
    standard, _ = solve(
        mu,
        cov.to_numpy(),
        payload,
        float(payload.get("risk_aversion", 5)),
        0,
        len(rets),
    )
    return response(
        "feature_10",
        summary_cards=[
            {"label": "Expected Return", "value": float(w @ mu)},
            {
                "label": "Projected Volatility",
                "value": float(np.sqrt(w @ cov.to_numpy() @ w)),
            },
        ],
        charts={"efficient_frontier": frontier, "optimal_weights": rows},
        tables={
            "optimal_factor_allocation": rows,
            "constraint_binding": dual,
            "fap_diagnostic": [fap],
            "robust_vs_standard": [
                {"factor": n, "robust_weight": w[i], "standard_weight": standard[i]}
                for i, n in enumerate(names)
            ],
            "black_litterman_posterior": _black_litterman_rows(names, bl),
        },
        meta={
            "optimizer": "CVXPY CLARABEL",
            "robust_mode": "ellipsoidal_mean_uncertainty_covariance_square_root",
            "missing_output_reasons": {
                "cardinality": "No mixed integer solver; greedy rescaling would violate constraints",
                "sector_bounds": "Factor-space optimization has no stock sector mapping",
            },
        },
    )


def _black_litterman_factor(
    payload: Dict[str, Any], names, sigma: np.ndarray, prior: np.ndarray
) -> Optional[Dict[str, Any]]:
    views = payload.get("bl_views") or payload.get("black_litterman_views") or []
    if not isinstance(views, list) or not views:
        return None
    tau = float(payload.get("bl_tau", 0.05))
    P, q, omega_diag = [], [], []
    name_to_idx = {name: i for i, name in enumerate(names)}
    for view in views:
        if not isinstance(view, dict):
            raise ValueError("Black-Litterman views must be structured objects")
        long_name = view.get("long")
        short_name = view.get("short")
        if long_name not in name_to_idx or (
            short_name and short_name not in name_to_idx
        ):
            raise ValueError("Unknown Black-Litterman view factor")
        row = np.zeros(len(names), dtype=float)
        if long_name in name_to_idx:
            row[name_to_idx[long_name]] = 1.0
        if short_name in name_to_idx:
            row[name_to_idx[short_name]] -= 1.0
        confidence = float(view.get("confidence", 0.5))
        if not np.isfinite(confidence) or not 0 < confidence < 1:
            raise ValueError("View confidence must be between zero and one")
        view_ret = float(view.get("excess_return", view.get("return", 0.0)))
        view_var = float(row @ sigma @ row.T)
        omega = max((1 - confidence) / confidence * max(view_var, 1e-8), 1e-8)
        P.append(row)
        q.append(view_ret)
        omega_diag.append(omega)
    if not P:
        return None
    P = np.vstack(P)
    q = np.asarray(q, dtype=float)
    omega = np.diag(np.asarray(omega_diag, dtype=float))
    tau_sigma = tau * sigma
    try:
        tau_inv = np.linalg.pinv(tau_sigma)
        omega_inv = np.linalg.pinv(omega)
        M = np.linalg.pinv(tau_inv + P.T @ omega_inv @ P)
        posterior = M @ (tau_inv @ prior + P.T @ omega_inv @ q)
        posterior_cov = sigma + M
    except np.linalg.LinAlgError as exc:
        raise ValueError("Black-Litterman matrix failure") from exc
    return {
        "prior": prior.tolist(),
        "posterior": posterior.tolist(),
        "posterior_covariance": posterior_cov.tolist(),
        "adjustment": (posterior - prior).tolist(),
        "views_used": int(len(P)),
        "method": "factor_level_black_litterman_structured_views",
    }


def _black_litterman_rows(names, result):
    if not result:
        return [
            {
                "status": "not_requested",
                "input_contract": "Use structured bl_views: [{long, short, excess_return, confidence}], not natural-language strings.",
            }
        ]
    return [
        {
            "factor": name,
            "prior_return": float(result["prior"][i]),
            "posterior_return": float(result["posterior"][i]),
            "adjustment": float(result["adjustment"][i]),
            "method": result["method"],
            "views_used": result["views_used"],
        }
        for i, name in enumerate(names)
    ]


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("10")
OUTPUTS = _outputs("10")
