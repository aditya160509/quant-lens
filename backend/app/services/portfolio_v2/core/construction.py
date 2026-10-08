"""Constrained portfolio construction with explicit solver diagnostics."""

from __future__ import annotations
import math
import numpy as np
import pandas as pd
import cvxpy as cp
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from .common import fast_pinv
from .context import parse_weights
from .covariance import covariance_matrix, expected_returns
from .data_loader import annualization_factor
from .performance import cached_correlation_frame

OBJECTIVES = (
    "markowitz",
    "global_min_variance",
    "max_sharpe",
    "inverse_vol",
    "risk_parity",
    "max_diversification",
    "hrp",
    "growth_optimal",
    "black_litterman",
    "cvar_min",
)


class OptimizationError(ValueError):
    pass


def _portfolio_constraints(cols, payload, ctx_weights=None):
    structure = payload.get("position_structure", "long_only")
    if structure not in {"long_only", "130_30", "market_neutral", "unconstrained"}:
        raise ValueError("Unknown position_structure")
    net = 0.0 if structure == "market_neutral" else 1.0
    default_low = 0.0 if structure == "long_only" else -1.0

    def bound(raw, default):
        if isinstance(raw, dict):
            if set(raw) - set(cols):
                raise ValueError("Bounds contain unknown symbols")
            return np.array([float(raw.get(c, default)) for c in cols])
        return np.full(len(cols), default if raw is None else float(raw))

    lo = bound(payload.get("min_weights"), default_low)
    hi = bound(payload.get("max_weights", payload.get("max_weight")), 1.0)
    if not np.isfinite(lo).all() or not np.isfinite(hi).all() or (lo > hi).any():
        raise ValueError("Invalid weight bounds")
    gross = float(
        payload.get(
            "leverage_cap",
            1.0 if structure == "long_only" else 1.6 if structure == "130_30" else 2.0,
        )
    )
    checks = [
        {"type": "eq", "fun": lambda w: w.sum() - net, "name": "net_budget"},
        {"type": "ineq", "fun": lambda w: gross - np.abs(w).sum(), "name": "gross_cap"},
    ]
    if structure == "130_30":
        shorts = payload.get("short_symbols")
        if not shorts or set(shorts) - set(cols):
            raise ValueError("130_30 requires an explicit short_symbols subset")
        mask = np.array([c in shorts for c in cols])
        lo[~mask] = np.maximum(lo[~mask], 0)
        hi[mask] = np.minimum(hi[mask], 0)
        checks.append(
            {"type": "eq", "fun": lambda w: w[mask].sum() + 0.3, "name": "short_budget"}
        )
    sectors = payload.get("sector_map", {})
    for sector, cap in payload.get("sector_max_weights", {}).items():
        mask = np.array([sectors.get(c) == sector for c in cols])
        if not mask.any():
            raise ValueError(
                f"No observed sector classification for constraint: {sector}"
            )
        checks.append(
            {
                "type": "ineq",
                "fun": lambda w, m=mask, cap=float(cap): cap - np.abs(w[m]).sum(),
                "name": "sector:" + sector,
            }
        )
    current = (
        parse_weights({"weights": ctx_weights}, cols)
        if ctx_weights is not None
        else None
    )
    turnover = payload.get("max_turnover")
    if turnover is not None:
        if current is None:
            raise ValueError("max_turnover requires current weights")
        checks.append(
            {
                "type": "ineq",
                "fun": lambda w: (
                    float(turnover) - np.abs(w - current.to_numpy()).sum() / 2
                ),
                "name": "one_way_turnover",
            }
        )
    return (
        list(zip(lo, hi)),
        checks,
        {
            "position_structure": structure,
            "net_budget": net,
            "gross_cap": gross,
            "sector_caps": payload.get("sector_max_weights", {}),
            "max_turnover": turnover,
        },
    )


def constraint_report(weights, bounds, constraints):
    w = np.asarray(weights)
    rows = []
    for c in constraints:
        slack = float(c["fun"](w))
        valid = abs(slack) <= 1e-5 if c["type"] == "eq" else slack >= -1e-5
        rows.append(
            {
                "constraint": c.get("name", "constraint"),
                "slack": slack,
                "status": "violated"
                if not valid
                else "binding"
                if abs(slack) <= 1e-5
                else "satisfied",
            }
        )
    for i, (lo, hi) in enumerate(bounds):
        for label, slack in (("lower", w[i] - lo), ("upper", hi - w[i])):
            rows.append(
                {
                    "constraint": f"weight_{i}_{label}",
                    "slack": float(slack),
                    "status": "violated"
                    if slack < -1e-5
                    else "binding"
                    if slack <= 1e-5
                    else "satisfied",
                }
            )
    return rows


def _validated(result, bounds, constraints, name):
    if (
        not result.success
        or not np.isfinite(result.x).all()
        or any(
            r["status"] == "violated"
            for r in constraint_report(result.x, bounds, constraints)
        )
    ):
        raise OptimizationError(
            f"{name}: {result.message}; feasible weights were not produced"
        )
    return result.x


def _convex_constraints(w, cols, payload, scale=1):
    bounds, checks, meta = _portfolio_constraints(
        cols, payload, payload.get("current_weights", payload.get("weights"))
    )
    lo, hi = np.array(bounds).T
    constraints = [
        w >= lo * scale,
        w <= hi * scale,
        cp.sum(w) == meta["net_budget"] * scale,
        cp.norm1(w) <= meta["gross_cap"] * scale,
    ]
    if meta["position_structure"] == "130_30":
        mask = [i for i, c in enumerate(cols) if c in payload["short_symbols"]]
        constraints.append(cp.sum(w[mask]) == -0.3 * scale)
    for sector, cap in meta["sector_caps"].items():
        ids = [i for i, c in enumerate(cols) if payload["sector_map"].get(c) == sector]
        constraints.append(cp.norm1(w[ids]) <= float(cap) * scale)
    if meta["max_turnover"] is not None:
        current = parse_weights(
            {"weights": payload.get("current_weights", payload.get("weights"))}, cols
        ).to_numpy()
        constraints.append(
            cp.norm1(w - current * scale) <= 2 * float(meta["max_turnover"]) * scale
        )
    return constraints, bounds, checks


def solve_portfolio(
    returns, payload=None, objective="global_min_variance", target=None
):
    payload = payload or {}
    if objective not in OBJECTIVES:
        raise ValueError("Unknown objective: " + str(objective))
    r = returns.dropna()
    if len(r) < 2 or r.shape[1] < 1:
        raise ValueError("Complete observed returns required")
    cols = list(r.columns)
    ann = annualization_factor(payload.get("frequency", "daily"))
    cov, _ = covariance_matrix(r, payload.get("covariance_estimator", "ledoit_wolf"))
    sigma = cov.to_numpy() * ann
    mu = expected_returns(
        r, payload.get("expected_return_estimator", "shrinkage"), ann
    ).to_numpy()
    w = cp.Variable(len(cols))
    constraints, bounds, checks = _convex_constraints(w, cols, payload)
    if target is not None:
        constraints.append(mu @ w == target)
        checks = checks + [
            {"type": "eq", "fun": lambda x: x @ mu - target, "name": "target_return"}
        ]
    if objective == "black_litterman":
        prior = parse_weights(
            {
                "weights": payload.get(
                    "market_weights", {c: 1 / len(cols) for c in cols}
                )
            },
            cols,
        )
        if not np.isclose(prior.sum(), 1):
            raise ValueError("Black-Litterman market_weights must sum to one")
        bl = black_litterman(
            cov * ann,
            prior,
            payload.get("views"),
            tau=float(payload.get("bl_tau", 0.05)),
            risk_aversion=float(payload.get("risk_aversion", 2.5)),
        )
        mu = bl["posterior_mu"].to_numpy()
        sigma = bl["posterior_cov"].to_numpy()
    if objective in {"markowitz", "growth_optimal", "black_litterman"}:
        penalty = (
            1 / float(payload.get("kelly_fraction", 1))
            if objective == "growth_optimal"
            else float(payload.get("risk_aversion", 2.5))
        )
        goal = cp.Minimize(penalty / 2 * cp.quad_form(w, cp.psd_wrap(sigma)) - mu @ w)
    elif objective == "cvar_min":
        alpha = float(payload.get("var_confidence", 0.95))
        eta = cp.Variable()
        u = cp.Variable(len(r), nonneg=True)
        constraints.append(u >= -r.to_numpy() @ w - eta)
        goal = cp.Minimize(eta + cp.sum(u) / ((1 - alpha) * len(r)))
    else:
        goal = cp.Minimize(cp.quad_form(w, cp.psd_wrap(sigma)))
    problem = cp.Problem(goal, constraints)
    problem.solve(solver="CLARABEL")
    if problem.status != cp.OPTIMAL or w.value is None:
        raise OptimizationError(f"{objective}: cvxpy status {problem.status}")
    seed = w.value
    if (
        objective == "risk_parity"
        and payload.get("position_structure", "long_only") == "long_only"
    ):
        budgets = np.array(
            [float(payload.get("risk_shares", {}).get(c, 1 / len(cols))) for c in cols]
        )
        if (budgets <= 0).any() or not np.isclose(budgets.sum(), 1):
            raise ValueError(
                "Convex risk budgeting requires positive normalized risk_shares"
            )
        risk_weights = cp.Variable(len(cols), pos=True)
        risk_problem = cp.Problem(
            cp.Minimize(
                0.5 * cp.quad_form(risk_weights, cp.psd_wrap(sigma))
                - budgets @ cp.log(risk_weights)
            )
        )
        risk_problem.solve(solver="CLARABEL", tol_gap_abs=1e-10, tol_feas=1e-10)
        if risk_problem.status != cp.OPTIMAL:
            raise OptimizationError(
                "Risk-budget log-barrier solve failed: " + risk_problem.status
            )
        candidate = risk_weights.value / risk_weights.value.sum()
        if not any(
            row["status"] == "violated"
            for row in constraint_report(candidate, bounds, checks)
        ):
            seed = candidate
    tangency_solved = False
    if objective == "max_sharpe":
        excess = mu - float(payload.get("risk_free_rate", 0))
        best_return = cp.Problem(cp.Maximize(excess @ w), constraints)
        best_return.solve(solver="CLARABEL")
        if best_return.status != cp.OPTIMAL:
            raise OptimizationError(
                "Sharpe feasible-return solve failed: " + best_return.status
            )
        if best_return.value > 1e-9:
            y = cp.Variable(len(cols))
            scale = cp.Variable(nonneg=True)
            transformed, _, _ = _convex_constraints(y, cols, payload, scale)
            problem = cp.Problem(
                cp.Minimize(cp.quad_form(y, cp.psd_wrap(sigma))),
                transformed + [excess @ y == 1, scale >= 1e-9],
            )
            problem.solve(solver="CLARABEL", tol_gap_abs=1e-10, tol_feas=1e-10)
            if problem.status != cp.OPTIMAL or scale.value <= 0:
                raise OptimizationError(
                    "Sharpe tangency solve failed: " + problem.status
                )
            seed = y.value / scale.value
            tangency_solved = True
    if (
        objective in {"max_sharpe", "risk_parity", "max_diversification"}
        and not tangency_solved
    ):
        vols = np.sqrt(np.diag(sigma))

        def fun(x):
            variance = max(float(x @ sigma @ x), 1e-18)
            if objective == "max_sharpe":
                return -float(
                    x @ mu - x.sum() * float(payload.get("risk_free_rate", 0))
                ) / math.sqrt(variance)
            if objective == "max_diversification":
                return -float(np.abs(x) @ vols) / math.sqrt(variance)
            shares = x * (sigma @ x) / variance
            budgets = np.array(
                [
                    float(payload.get("risk_shares", {}).get(c, 1 / len(cols)))
                    for c in cols
                ]
            )
            if (budgets < 0).any() or not np.isclose(budgets.sum(), 1):
                raise ValueError("risk_shares must be nonnegative and sum to one")
            return float(np.square(shares - budgets).sum())

        result = minimize(
            fun,
            seed,
            method="SLSQP",
            bounds=bounds,
            constraints=[
                {k: v for k, v in c.items() if k in {"type", "fun"}}
                for c in checks
                if not (
                    c["name"] == "gross_cap"
                    and payload.get("position_structure", "long_only") == "long_only"
                    and float(payload.get("leverage_cap", 1)) >= 1
                )
            ],
            options={"maxiter": 1000, "ftol": 1e-11},
        )
        seed = _validated(result, bounds, checks, objective)
    elif objective in {"inverse_vol", "hrp"}:
        vols = np.sqrt(np.diag(sigma))
        seed = 1 / vols
        seed /= seed.sum()
        if objective == "hrp":
            seed = _hrp_weights(cached_correlation_frame(r), vols, cols, sigma)
        if any(
            row["status"] == "violated"
            for row in constraint_report(seed, bounds, checks)
        ):
            raise OptimizationError(
                f"{objective}: unconstrained allocation violates requested constraints; no projected substitute published"
            )
    if any(
        row["status"] == "violated" for row in constraint_report(seed, bounds, checks)
    ):
        raise OptimizationError(f"{objective}: solver residual violates constraints")
    return pd.Series(seed, index=cols), {
        "success": True,
        "solver": "CLARABEL tangency"
        if tangency_solved
        else "SLSQP"
        if objective in {"max_sharpe", "risk_parity", "max_diversification"}
        else "CLARABEL"
        if objective not in {"hrp", "inverse_vol"}
        else "analytic",
        "constraints": constraint_report(seed, bounds, checks),
    }


def optimize_portfolios(returns, payload=None):
    payload = payload or {}
    requested = payload.get("objective", "max_sharpe")
    if requested not in OBJECTIVES:
        raise ValueError("Unknown objective: " + str(requested))
    weights = {}
    diagnostics = []
    for name in OBJECTIVES:
        try:
            weights[name], detail = solve_portfolio(returns, payload, name)
            diagnostics.append({"objective": name, **detail})
        except OptimizationError as exc:
            diagnostics.append(
                {"objective": name, "success": False, "message": str(exc)}
            )
    if requested not in weights:
        raise OptimizationError(
            next(d["message"] for d in diagnostics if d["objective"] == requested)
        )
    cov, cov_meta = covariance_matrix(
        returns, payload.get("covariance_estimator", "ledoit_wolf")
    )
    ann = annualization_factor(payload.get("frequency", "daily"))
    mu = expected_returns(
        returns, payload.get("expected_return_estimator", "shrinkage"), ann
    )
    frontier = []
    trace = []
    if "global_min_variance" in weights:
        start = float(weights["global_min_variance"] @ mu)
        # Solve maximal feasible return under exactly the same constraints.
        w = cp.Variable(len(mu))
        cs, _, _ = _convex_constraints(w, list(mu.index), payload)
        problem = cp.Problem(cp.Maximize(mu.to_numpy() @ w), cs)
        problem.solve(solver="CLARABEL")
        if problem.status == cp.OPTIMAL:
            for target in np.linspace(
                start, float(problem.value), int(payload.get("frontier_points", 100))
            ):
                try:
                    point, _ = solve_portfolio(
                        returns, payload, "global_min_variance", float(target)
                    )
                    vol = math.sqrt(max(float(point @ (cov * ann) @ point), 0))
                    frontier.append(
                        {
                            "target_return": float(target),
                            "return": float(point @ mu),
                            "vol": vol,
                            "success": True,
                        }
                    )
                except OptimizationError as exc:
                    frontier.append(
                        {
                            "target_return": float(target),
                            "success": False,
                            "message": str(exc),
                        }
                    )
        for risk in np.geomspace(0.01, 1000, int(payload.get("frontier_points", 100))):
            try:
                point, _ = solve_portfolio(
                    returns, {**payload, "risk_aversion": float(risk)}, "markowitz"
                )
                trace.append(
                    {
                        "lambda": float(risk),
                        "return": float(point @ mu),
                        "vol": math.sqrt(max(float(point @ (cov * ann) @ point), 0)),
                        "success": True,
                    }
                )
            except OptimizationError as exc:
                trace.append(
                    {"lambda": float(risk), "success": False, "message": str(exc)}
                )
    return {
        "weights": weights,
        "weight_table": [
            {"portfolio": name, "ticker": c, "weight": float(v), "success": True}
            for name, w in weights.items()
            for c, v in w.items()
        ],
        "frontier": frontier,
        "markowitz_trace": trace,
        "covariance": cov,
        "mu": mu,
        "diagnostics": diagnostics,
        "meta": cov_meta,
    }


def _hrp_weights(
    corr: pd.DataFrame, vols: np.ndarray, cols: list[str], cov: np.ndarray | None = None
) -> np.ndarray:
    """Lopez de Prado hierarchical risk parity with recursive bisection."""
    if len(cols) <= 2:
        w = 1 / np.maximum(vols**2, 1e-12)
        return w / w.sum()
    corr_arr = corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float)
    corr_arr = np.clip((corr_arr + corr_arr.T) / 2, -1, 1)
    np.fill_diagonal(corr_arr, 1.0)
    link = linkage(
        squareform(np.sqrt(np.maximum((1.0 - corr_arr) / 2.0, 0.0)), checks=False),
        method="single",
    )
    order: list[int] = []

    def leaves(node: int):
        if node < len(cols):
            order.append(node)
            return
        left, right = link[node - len(cols), :2].astype(int)
        leaves(left)
        leaves(right)

    leaves(2 * len(cols) - 2)
    cov_arr = cov if cov is not None else np.outer(vols, vols) * corr_arr
    w = np.ones(len(cols), dtype=float)
    clusters = [order]
    while clusters:
        next_clusters = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            split = len(cluster) // 2
            left, right = cluster[:split], cluster[split:]

            def cluster_var(index):
                sub = cov_arr[np.ix_(index, index)]
                iv = 1.0 / np.maximum(np.diag(sub), 1e-12)
                iv /= iv.sum()
                return float(iv @ sub @ iv)

            lv, rv = cluster_var(left), cluster_var(right)
            alpha = 1.0 - lv / max(lv + rv, 1e-12)
            w[left] *= alpha
            w[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters
    return w / max(w.sum(), 1e-12)


def black_litterman(cov, market_weights, views=None, tau=0.05, risk_aversion=2.5):
    cols = list(cov.columns)
    sigma = cov.to_numpy()
    w = market_weights.reindex(cols).to_numpy()
    if not np.isfinite(w).all() or not np.isclose(w.sum(), 1) or tau <= 0:
        raise ValueError("Valid normalized prior weights and positive tau required")
    pi = risk_aversion * sigma @ w
    if not views:
        return {
            "posterior_mu": pd.Series(pi, index=cols),
            "posterior_cov": cov,
            "view_count": 0,
        }
    if "P" in views:
        P = np.array(views["P"], dtype=float)
        Q = np.array(views["Q"], dtype=float)
        omega = (
            np.array(views["Omega"], dtype=float)
            if "Omega" in views
            else np.diag(np.diag(P @ (tau * sigma) @ P.T))
        )
    else:
        if set(views) - set(cols):
            raise ValueError("Views contain unknown assets")
        P = np.eye(len(cols))[[cols.index(c) for c in views]]
        Q = np.array(list(views.values()), dtype=float)
        omega = np.diag(np.diag(P @ (tau * sigma) @ P.T))
    if (
        P.ndim != 2
        or P.shape[1] != len(cols)
        or Q.shape != (P.shape[0],)
        or omega.shape != (len(Q), len(Q))
        or len(Q) > 10
        or not all(np.isfinite(x).all() for x in (P, Q, omega))
        or np.linalg.eigvalsh(omega).min() <= 0
    ):
        raise ValueError("Invalid Black-Litterman P/Q/Omega views")
    prior = tau * sigma
    middle = fast_pinv(fast_pinv(prior) + P.T @ fast_pinv(omega) @ P)
    post = middle @ (fast_pinv(prior) @ pi + P.T @ fast_pinv(omega) @ Q)
    return {
        "posterior_mu": pd.Series(post, index=cols),
        "posterior_cov": pd.DataFrame(sigma + middle, index=cols, columns=cols),
        "view_count": len(Q),
    }


def cvar_minimize(returns, alpha=0.95, target_return=None):
    return solve_portfolio(
        returns, {"var_confidence": alpha}, "cvar_min", target_return
    )[0]


def min_cvar_target(returns, target):
    return cvar_minimize(returns, target_return=target)


def black_litterman_weights(returns, market_weights, views=None):
    return solve_portfolio(
        returns,
        {"market_weights": market_weights.to_dict(), "views": views},
        "black_litterman",
    )[0]


def weight_stability_index(weight_history):
    return float(weight_history.std().mean()) if not weight_history.empty else None
