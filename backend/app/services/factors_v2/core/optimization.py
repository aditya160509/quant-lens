"""Consistent constrained CVXPY solves and ellipsoidal mean uncertainty."""

import cvxpy as cp
import numpy as np
import statsmodels.api as sm


def solve(mu, sigma, payload, lam, robust, observations):
    n = len(mu)
    w = cp.Variable(n)
    eig, u = np.linalg.eigh(sigma * 252 / observations)
    root = np.diag(np.sqrt(np.maximum(eig, 0))) @ u.T
    objective = cp.Maximize(
        mu @ w
        - float(lam) * cp.quad_form(w, cp.psd_wrap(sigma))
        - float(robust) * cp.norm(root @ w, 2)
    )
    constraints = [cp.sum(w) == float(payload.get("net_exposure", 1))]
    bound = float(payload.get("position_limit", 1))
    constraints += [
        w <= bound,
        w >= (-bound if payload.get("long_short", False) else 0),
    ]
    if payload.get("gross_limit") is not None:
        constraints.append(cp.norm1(w) <= float(payload["gross_limit"]))
    current = np.asarray(payload.get("current_weights", [0] * n), float)
    if len(current) != n:
        raise ValueError("current_weights length must equal the factor count")
    if payload.get("turnover_limit") is not None:
        constraints.append(cp.norm1(w - current) <= float(payload["turnover_limit"]))
    if payload.get("tracking_error_limit") is not None:
        vals, vec = np.linalg.eigh(sigma)
        riskroot = np.diag(np.sqrt(np.maximum(vals, 0))) @ vec.T
        benchmark = np.asarray(payload.get("benchmark_weights", [0] * n), float)
        if len(benchmark) != n:
            raise ValueError("benchmark_weights length must equal the factor count")
        constraints.append(
            cp.norm(riskroot @ (w - benchmark), 2)
            <= float(payload["tracking_error_limit"])
        )
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.CLARABEL, verbose=False)
    if problem.status != "optimal" or w.value is None:
        raise ValueError(f"Optimizer did not solve: {problem.status}")
    values = np.asarray(w.value).reshape(-1)
    if any(
        c.violation() is not None and np.max(np.abs(c.violation())) > 1e-5
        for c in constraints
    ):
        raise ValueError("Optimizer constraint violation")
    dual = [
        {
            "constraint": str(c),
            "shadow_price": np.asarray(c.dual_value).tolist()
            if c.dual_value is not None
            else None,
        }
        for c in constraints
    ]
    return values, dual


def alignment(alpha, loadings):
    if alpha is None or loadings is None:
        return {
            "r_squared": None,
            "status": "unavailable",
            "reason": "Supply matched cross-sectional alpha_signal and risk_loadings rows",
        }
    y = np.asarray(alpha, float)
    x = np.asarray(loadings, float)
    if (
        x.ndim != 2
        or y.ndim != 1
        or len(y) != len(x)
        or len(y) <= x.shape[1] + 2
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError(
            "FAP needs finite matched alpha/loadings and more rows than risk regressors"
        )
    fit = sm.OLS(y, sm.add_constant(x)).fit()
    return {
        "r_squared": float(fit.rsquared),
        "unexplained_fraction": 1 - float(fit.rsquared),
        "sample_size": len(y),
        "method": "Cross-sectional OLS alpha on supplied risk loadings",
    }
