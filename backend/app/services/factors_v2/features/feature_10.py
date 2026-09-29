"""Feature 10: Factor-Based Portfolio Optimizer."""

from typing import Any, Dict, Optional

import cvxpy as cp
import numpy as np

from app.services.factors_v2.core.analytics import covariance_payload, factor_returns, response
from app.services.factors_v2.core.performance import compute_mode, runtime_meta

_OPTIMIZER_CACHE: Dict[tuple[str, ...], np.ndarray] = {}


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 756)))
    if rets.empty:
        return response("feature_10", "warning", meta={"warning": "No factor returns available"})
    cov = covariance_payload(rets, method=payload.get("covariance_method", "ledoit_wolf"))["covariance"]
    mu = rets.mean().values * 252
    names = list(rets.columns)
    manual_returns = payload.get("expected_returns") or {}
    if isinstance(manual_returns, dict) and manual_returns:
        mu = np.asarray([float(manual_returns.get(name, mu[i])) for i, name in enumerate(names)], dtype=float)
    bl_result = _black_litterman_factor(payload, names, cov.values, mu)
    if bl_result:
        mu = np.asarray(bl_result["posterior"], dtype=float)
    lam = float(payload.get("risk_aversion", 5.0))
    n = len(names)
    robust_requested = bool(payload.get("robust", True))
    robust_mode = "goldfarb_iyengar_socp"
    if robust_requested and mode == "realtime" and n > 100:
        confidence = float(payload.get("robust_confidence", 0.50))
        mu = mu * max(0.0, 1.0 - confidence)
        robust = 0.0
        robust_mode = "expected_return_shrinkage_approximation"
    else:
        robust = float(payload.get("robust_penalty", 0.25 if robust_requested else 0.0))
    cov_values = cov.values
    theta = cp.Variable(n)
    sigma_mu = cov_values / max(len(rets), 1)
    objective = cp.Maximize(
        mu @ theta
        - robust * cp.norm(cp.psd_wrap(sigma_mu) @ theta, 2)
        - lam * cp.quad_form(theta, cp.psd_wrap(cov_values))
    )
    constraints = [cp.sum(theta) == 1]
    if payload.get("long_short", True):
        constraints.extend([theta >= -1.0, theta <= 1.0])
    else:
        constraints.extend([theta >= 0.0, theta <= 1.0])
    if payload.get("gross_limit") is not None:
        constraints.append(cp.norm1(theta) <= float(payload["gross_limit"]))
    if payload.get("position_limit") is not None:
        limit = abs(float(payload["position_limit"]))
        constraints.extend([theta >= -limit if payload.get("long_short", True) else 0.0, theta <= limit])
    problem = cp.Problem(objective, constraints)
    cache_key = tuple(names)
    previous = _OPTIMIZER_CACHE.get(cache_key)
    if previous is not None and previous.shape[0] == n:
        theta.value = previous
    solver_used = "OSQP"
    try:
        problem.solve(solver=cp.OSQP, warm_start=True, eps_abs=1e-5, eps_rel=1e-5, verbose=False)
    except Exception:
        solver_used = "CLARABEL"
        problem.solve(solver=cp.CLARABEL, warm_start=True, verbose=False)
    success = theta.value is not None and problem.status in {"optimal", "optimal_inaccurate"}
    w = np.asarray(theta.value, dtype=float).reshape(-1) if success else np.ones(n) / n
    if success:
        _OPTIMIZER_CACHE[cache_key] = w.copy()
    cardinality = payload.get("cardinality")
    greedy_selected = None
    if cardinality:
        k = max(1, min(int(cardinality), n))
        keep = np.argsort(np.abs(w))[-k:]
        greedy = np.zeros_like(w)
        greedy[keep] = w[keep]
        gross = np.sum(np.abs(greedy))
        if gross > 0:
            greedy = greedy / gross if payload.get("long_short", True) else greedy / max(np.sum(greedy), 1e-12)
        greedy_selected = [names[i] for i in keep]
        w = greedy
    rows = [{"factor": name, "weight": float(weight), "expected_return_contribution": float(weight * mu[i]), "risk_contribution": float(weight * (cov.values @ w)[i])} for i, (name, weight) in enumerate(zip(names, w))]
    frontier = _efficient_frontier(mu, cov_values, payload, robust, sigma_mu)
    standard_weights = None
    if robust_requested:
        standard_weights = _solve_single(mu, cov_values, payload, lam, 0.0, sigma_mu)
    alpha = np.asarray(payload.get("alpha_signal", mu), dtype=float)
    fap_r2 = float(np.corrcoef(alpha[:n], mu[:n])[0, 1] ** 2) if len(alpha) >= n and np.std(alpha[:n]) and np.std(mu) else 0.0
    binding = [
        {"constraint": "budget_sum_1", "active": True, "shadow_price": float(constraints[0].dual_value) if constraints[0].dual_value is not None else None},
        {"constraint": "long_short_bounds" if payload.get("long_short", True) else "long_only_bounds", "active": bool(np.any(np.isclose(np.abs(w), 1.0)) or np.any(np.isclose(w, 0.0)))},
    ]
    return response(
        "feature_10",
        "ok" if success else "error",
        summary_cards=[{"label": "Expected Return", "value": float(w @ mu)}, {"label": "Projected Volatility", "value": float(np.sqrt(max(w @ cov.values @ w, 0)))}, {"label": "FAP R2", "value": fap_r2}],
        charts={
            "efficient_frontier": frontier,
            "optimal_weights": rows,
            "risk_budget": [{"factor": row["factor"], "value": row["risk_contribution"]} for row in rows],
            "robust_vs_standard": _robust_comparison(names, w, standard_weights, mu, cov_values),
        },
        tables={
            "optimal_factor_allocation": rows,
            "constraint_binding": binding,
            "fap_diagnostic": [{"r_squared": fap_r2, "flagged": fap_r2 > 0.7}],
            "cardinality_post_processing": [{"requested_cardinality": cardinality, "method": "continuous_relaxation_plus_greedy_top_abs_weight", "selected": greedy_selected}],
            "robust_vs_standard": _robust_comparison(names, w, standard_weights, mu, cov_values),
            "black_litterman_posterior": _black_litterman_rows(names, bl_result),
        },
        alerts=[{"level": "high", "message": "Factor Alignment Problem flagged", "r_squared": fap_r2}] if fap_r2 > 0.7 else [],
        meta={
            **runtime_meta("feature_10", payload, ["no integer programming live; continuous relaxation plus greedy post-processing"]),
            "optimizer": f"cvxpy {solver_used} factor-space program with warm_start",
            "robust_mode": robust_mode,
            "problem_status": problem.status,
            "objective_value": problem.value,
            "success": bool(success),
            "audit_closures": ["efficient frontier now re-solves across risk-aversion values", "robust-vs-standard comparison", "structured factor-level Black-Litterman posterior"],
        },
    )


def _solve_single(mu: np.ndarray, cov_values: np.ndarray, payload: Dict[str, Any], lam: float, robust: float, sigma_mu: np.ndarray) -> np.ndarray:
    n = len(mu)
    theta = cp.Variable(n)
    objective = cp.Maximize(mu @ theta - robust * cp.norm(cp.psd_wrap(sigma_mu) @ theta, 2) - float(lam) * cp.quad_form(theta, cp.psd_wrap(cov_values)))
    constraints = [cp.sum(theta) == 1]
    if payload.get("long_short", True):
        constraints.extend([theta >= -1.0, theta <= 1.0])
    else:
        constraints.extend([theta >= 0.0, theta <= 1.0])
    problem = cp.Problem(objective, constraints)
    try:
        problem.solve(solver=cp.OSQP, warm_start=True, eps_abs=1e-5, eps_rel=1e-5, verbose=False)
    except Exception:
        try:
            problem.solve(solver=cp.CLARABEL, warm_start=True, verbose=False)
        except Exception:
            return np.ones(n) / n
    if theta.value is None or problem.status not in {"optimal", "optimal_inaccurate"}:
        return np.ones(n) / n
    return np.asarray(theta.value, dtype=float).reshape(-1)


def _efficient_frontier(mu: np.ndarray, cov_values: np.ndarray, payload: Dict[str, Any], robust: float, sigma_mu: np.ndarray) -> list[dict[str, float]]:
    frontier = []
    for l in np.linspace(1, 20, 25):
        w = _solve_single(mu, cov_values, payload, float(l), robust, sigma_mu)
        frontier.append({"risk_aversion": float(l), "expected_return": float(w @ mu), "volatility": float(np.sqrt(max(w @ cov_values @ w, 0)))})
    return frontier


def _robust_comparison(names, robust_w, standard_w, mu, cov_values):
    if standard_w is None:
        return []
    return [
        {
            "factor": name,
            "robust_weight": float(robust_w[i]),
            "standard_weight": float(standard_w[i]),
            "weight_delta": float(robust_w[i] - standard_w[i]),
            "robust_return_contribution": float(robust_w[i] * mu[i]),
            "standard_return_contribution": float(standard_w[i] * mu[i]),
            "risk_marginal_delta": float((cov_values @ robust_w)[i] - (cov_values @ standard_w)[i]),
        }
        for i, name in enumerate(names)
    ]


def _black_litterman_factor(payload: Dict[str, Any], names, sigma: np.ndarray, prior: np.ndarray) -> Optional[Dict[str, Any]]:
    views = payload.get("bl_views") or payload.get("black_litterman_views") or []
    if not isinstance(views, list) or not views:
        return None
    tau = float(payload.get("bl_tau", 0.05))
    P, q, omega_diag = [], [], []
    name_to_idx = {name: i for i, name in enumerate(names)}
    for view in views[:20]:
        if not isinstance(view, dict):
            continue
        long_name = view.get("long")
        short_name = view.get("short")
        if long_name not in name_to_idx and short_name not in name_to_idx:
            continue
        row = np.zeros(len(names), dtype=float)
        if long_name in name_to_idx:
            row[name_to_idx[long_name]] = 1.0
        if short_name in name_to_idx:
            row[name_to_idx[short_name]] -= 1.0
        confidence = min(max(float(view.get("confidence", 0.5)), 1e-3), 0.999)
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
    except Exception:
        return None
    return {"prior": prior.tolist(), "posterior": posterior.tolist(), "posterior_covariance": posterior_cov.tolist(), "adjustment": (posterior - prior).tolist(), "views_used": int(len(P)), "method": "factor_level_black_litterman_structured_views"}


def _black_litterman_rows(names, result):
    if not result:
        return [{"status": "not_requested", "input_contract": "Use structured bl_views: [{long, short, excess_return, confidence}], not natural-language strings."}]
    return [{"factor": name, "prior_return": float(result["prior"][i]), "posterior_return": float(result["posterior"][i]), "adjustment": float(result["adjustment"][i]), "method": result["method"], "views_used": result["views_used"]} for i, name in enumerate(names)]
