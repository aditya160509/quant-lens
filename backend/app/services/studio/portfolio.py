"""Deterministic constrained portfolio construction for the canonical Studio."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
from scipy.optimize import minimize


ENGINE_VERSION = "studio-portfolio-1.0"


class PortfolioOptimizationError(ValueError):
    """Raised when portfolio inputs or constraints cannot produce a valid artifact."""


def _finite_vector(values: list[float], size: int, label: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise PortfolioOptimizationError(f"{label} must contain {size} finite values")
    return vector


def optimize_portfolio(payload: dict[str, Any]) -> dict[str, Any]:
    assets = [str(value).strip().upper() for value in payload["assets"]]
    size = len(assets)
    if len(set(assets)) != size:
        raise PortfolioOptimizationError("assets must be unique")
    observations = payload.get("return_observations")
    return_matrix = None
    if observations is not None:
        return_matrix = np.asarray(observations, dtype=float)
        if return_matrix.ndim != 2 or return_matrix.shape[1] != size or return_matrix.shape[0] < 3:
            raise PortfolioOptimizationError("return_observations must have at least 3 rows and one column per asset")
        if not np.isfinite(return_matrix).all():
            raise PortfolioOptimizationError("return_observations must contain only finite values")
    periods = int(payload.get("periods_per_year", 252))
    expected_model = payload.get("expected_return_model", "supplied")
    covariance_model = payload.get("covariance_model", "supplied")
    if expected_model == "historical_mean":
        if return_matrix is None:
            raise PortfolioOptimizationError("historical_mean requires return_observations")
        expected = return_matrix.mean(axis=0) * periods
    elif expected_model == "zero":
        expected = np.zeros(size)
    else:
        expected = _finite_vector(payload.get("expected_returns", []), size, "expected_returns")
    if covariance_model in {"sample", "diagonal_shrinkage"}:
        if return_matrix is None:
            raise PortfolioOptimizationError(f"{covariance_model} requires return_observations")
        sample = np.cov(return_matrix, rowvar=False, ddof=1) * periods
        if covariance_model == "diagonal_shrinkage":
            shrinkage = float(payload.get("shrinkage", 0.2))
            if not 0 <= shrinkage <= 1:
                raise PortfolioOptimizationError("shrinkage must be between 0 and 1")
            covariance = (1 - shrinkage) * sample + shrinkage * np.diag(np.diag(sample))
        else:
            covariance = sample
    else:
        covariance = np.asarray(payload.get("covariance", []), dtype=float)
    if covariance.shape != (size, size) or not np.isfinite(covariance).all():
        raise PortfolioOptimizationError(f"covariance must be a finite {size} x {size} matrix")
    if not np.allclose(covariance, covariance.T, atol=1e-10):
        raise PortfolioOptimizationError("covariance must be symmetric")
    eigenvalues = np.linalg.eigvalsh(covariance)
    if float(eigenvalues.min()) < -1e-10:
        raise PortfolioOptimizationError("covariance must be positive semidefinite")

    lower = float(payload["min_weight"])
    upper = float(payload["max_weight"])
    gross_limit = float(payload["gross_leverage"])
    if lower > upper or size * lower > 1 + 1e-10 or size * upper < 1 - 1e-10:
        raise PortfolioOptimizationError("position bounds cannot satisfy the required net weight of 1")
    if gross_limit < 1:
        raise PortfolioOptimizationError("gross leverage must be at least 1")
    current = _finite_vector(payload.get("current_weights", [0.0] * size), size, "current_weights")
    objective = payload["objective"]
    risk_free = float(payload.get("risk_free_rate", 0.0))
    turnover_penalty = float(payload.get("turnover_penalty", 0.0))
    benchmark_values = payload.get("benchmark_weights")
    benchmark = _finite_vector(benchmark_values, size, "benchmark_weights") if benchmark_values is not None else None
    risk_aversion = float(payload.get("risk_aversion", 0.5))
    if not 0 <= risk_aversion <= 1:
        raise PortfolioOptimizationError("risk_aversion must be between 0 and 1")

    def variance(weights: np.ndarray) -> float:
        return float(weights @ covariance @ weights)

    def score(weights: np.ndarray) -> float:
        risk = max(variance(weights), 1e-16) ** 0.5
        turnover = float(np.abs(weights - current).sum())
        if objective == "max_sharpe":
            base = -(float(weights @ expected) - risk_free) / risk
        elif objective == "max_return":
            base = -float(weights @ expected)
        elif objective == "diversification":
            base = float(np.square(weights).sum())
        elif objective == "tracking_error":
            if benchmark is None:
                raise PortfolioOptimizationError("tracking_error requires benchmark_weights")
            active = weights - benchmark
            base = float(active @ covariance @ active)
        elif objective == "multi_objective":
            base = risk_aversion * variance(weights) - (1 - risk_aversion) * float(weights @ expected)
        else:
            base = variance(weights)
        return base + turnover_penalty * turnover

    constraints = [
        {"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)},
        {"type": "ineq", "fun": lambda weights: float(gross_limit - np.abs(weights).sum())},
    ]
    target_return = payload.get("target_return")
    if target_return is not None:
        constraints.append({"type": "ineq", "fun": lambda weights: float(weights @ expected - float(target_return))})
    max_turnover = payload.get("max_turnover")
    if max_turnover is not None:
        constraints.append({"type": "ineq", "fun": lambda weights: float(float(max_turnover) - np.abs(weights - current).sum())})
    linear_constraints = payload.get("linear_constraints") or []
    normalized_linear = []
    for item in linear_constraints:
        name = str(item.get("name") or "unnamed constraint").strip()
        coefficients = _finite_vector(item.get("coefficients", []), size, f"constraint {name!r} coefficients")
        minimum = item.get("min")
        maximum = item.get("max")
        if minimum is None and maximum is None:
            raise PortfolioOptimizationError(f"constraint {name!r} requires min or max")
        if minimum is not None:
            minimum = float(minimum)
            constraints.append({"type": "ineq", "fun": lambda weights, coefficients=coefficients, minimum=minimum: float(weights @ coefficients - minimum)})
        if maximum is not None:
            maximum = float(maximum)
            constraints.append({"type": "ineq", "fun": lambda weights, coefficients=coefficients, maximum=maximum: float(maximum - weights @ coefficients)})
        normalized_linear.append({"name": name, "coefficients": coefficients, "min": minimum, "max": maximum})
    scenarios = []
    for item in payload.get("scenarios") or []:
        name = str(item.get("name") or "unnamed scenario").strip()
        shocks = _finite_vector(item.get("shocks", []), size, f"scenario {name!r} shocks")
        scenarios.append({"name": name, "shocks": shocks})
    initial = np.full(size, 1.0 / size)
    result = minimize(
        score,
        initial,
        method="SLSQP",
        bounds=[(lower, upper)] * size,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not result.success:
        raise PortfolioOptimizationError(f"constraints are infeasible or optimization failed: {result.message}")
    weights = np.asarray(result.x, dtype=float)
    portfolio_variance = variance(weights)
    portfolio_volatility = max(portfolio_variance, 0.0) ** 0.5
    portfolio_return = float(weights @ expected)
    marginal = covariance @ weights
    risk_contribution = (
        weights * marginal / portfolio_variance if portfolio_variance > 1e-16 else np.zeros(size)
    )
    trades = weights - current
    turnover = float(np.abs(trades).sum())
    cost_bps = float(payload.get("cost_bps", 0.0))
    estimated_cost = turnover * cost_bps / 10_000
    tracking_error = None
    if benchmark is not None:
        active = weights - benchmark
        tracking_error = max(float(active @ covariance @ active), 0.0) ** 0.5
    observed_portfolio_returns = (
        (return_matrix @ weights).tolist() if return_matrix is not None else None
    )

    frontier = []
    feasible_returns = np.linspace(float(expected.min()), float(expected.max()), 21)
    for target in feasible_returns:
        candidate = minimize(
            variance,
            initial,
            method="SLSQP",
            bounds=[(lower, upper)] * size,
            constraints=[*constraints, {"type": "eq", "fun": lambda value, target=target: float(value @ expected - target)}],
            options={"ftol": 1e-10, "maxiter": 500},
        )
        if candidate.success:
            frontier.append({"return": float(candidate.x @ expected), "volatility": variance(candidate.x) ** 0.5})

    identity_payload = {
        "assets": assets,
        "expected_returns": expected.tolist(),
        "covariance": covariance.tolist(),
        "current_weights": current.tolist(),
        "objective": objective,
        "expected_return_model": expected_model,
        "covariance_model": covariance_model,
        "periods_per_year": periods,
        "shrinkage": float(payload.get("shrinkage", 0.2)),
        "min_weight": lower,
        "max_weight": upper,
        "gross_leverage": gross_limit,
        "risk_free_rate": risk_free,
        "turnover_penalty": turnover_penalty,
        "max_turnover": max_turnover,
        "target_return": target_return,
        "benchmark_weights": benchmark.tolist() if benchmark is not None else None,
        "risk_aversion": risk_aversion,
        "linear_constraints": [
            {"name": item["name"], "coefficients": item["coefficients"].tolist(), "min": item["min"], "max": item["max"]}
            for item in normalized_linear
        ],
        "scenarios": [{"name": item["name"], "shocks": item["shocks"].tolist()} for item in scenarios],
        "cost_bps": cost_bps,
        "source": payload.get("source") or {"kind": "manual"},
        "return_observations_sha256": (
            hashlib.sha256(return_matrix.tobytes(order="C")).hexdigest()
            if return_matrix is not None else None
        ),
    }
    normalized_input = json.dumps(identity_payload, sort_keys=True, separators=(",", ":"))
    artifact_id = f"portfolio_{hashlib.sha256(normalized_input.encode()).hexdigest()[:16]}"
    warnings = ["Tax-lot optimization and market-capacity estimates are unavailable because tax lots and liquidity data were not supplied."]
    if not normalized_linear:
        warnings.append("No sector, factor, liquidity, or custom exposure coefficients were supplied.")
    if not scenarios:
        warnings.append("No user-defined shock scenarios were supplied.")
    return {
        "artifact_id": artifact_id,
        "engine_version": ENGINE_VERSION,
        "objective": objective,
        "source": payload.get("source") or {"kind": "manual"},
        "assets": assets,
        "weights": dict(zip(assets, weights.tolist())),
        "current_weights": dict(zip(assets, current.tolist())),
        "trades": dict(zip(assets, trades.tolist())),
        "risk_contribution": dict(zip(assets, risk_contribution.tolist())),
        "metrics": {
            "expected_return": portfolio_return,
            "volatility": portfolio_volatility,
            "sharpe": (portfolio_return - risk_free) / portfolio_volatility if portfolio_volatility > 1e-16 else None,
            "gross_leverage": float(np.abs(weights).sum()),
            "net_weight": float(weights.sum()),
            "turnover": turnover,
            "estimated_cost_fraction": estimated_cost,
            "concentration_hhi": float(np.square(weights).sum()),
            "tracking_error": tracking_error,
        },
        "frontier": frontier,
        "observed_portfolio_returns": observed_portfolio_returns,
        "constraints": {"min_weight": lower, "max_weight": upper, "gross_leverage": gross_limit},
        "constraint_exposures": [
            {
                "name": item["name"],
                "value": float(weights @ item["coefficients"]),
                "min": item["min"],
                "max": item["max"],
            }
            for item in normalized_linear
        ],
        "scenario_results": [
            {
                "name": item["name"],
                "portfolio_return": float(weights @ item["shocks"]),
                "asset_contribution": dict(zip(assets, (weights * item["shocks"]).tolist())),
            }
            for item in scenarios
        ],
        "model": {
            "expected_returns": expected_model,
            "covariance": covariance_model,
            "periods_per_year": periods,
            "observations": int(return_matrix.shape[0]) if return_matrix is not None else None,
            "condition_number": float(np.linalg.cond(covariance)),
            "minimum_eigenvalue": float(eigenvalues.min()),
            "shrinkage": float(payload.get("shrinkage", 0.2)) if covariance_model == "diagonal_shrinkage" else None,
        },
        "warnings": warnings,
    }
