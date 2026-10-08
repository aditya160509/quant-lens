"""Discrete Almgren-Chriss schedules with actual covariance and explicit impact assumptions."""

import numpy as np
import cvxpy as cp
from .liquidity import liquidity_table


def optimal_schedule(trades, covariance, eta, horizon, risk_aversion=0):
    trades = np.asarray(trades, float)
    eta = np.asarray(eta, float)
    n = len(trades)
    if horizon < 1 or (eta <= 0).any() or risk_aversion < 0:
        raise ValueError("Positive horizon and temporary impact coefficient required")
    if not np.isfinite(trades).all() or not np.isfinite(eta).all():
        raise ValueError("Execution inputs must be finite")
    scale = max(float(np.max(np.abs(trades))), 1.0)
    normalized_trades = trades / scale
    inventory = cp.Variable((horizon + 1, n))
    v = inventory[:-1] - inventory[1:]
    constraints = [inventory[0] == normalized_trades, inventory[-1] == 0]
    for i, value in enumerate(trades):
        constraints.append(v[:, i] >= 0 if value >= 0 else v[:, i] <= 0)
    impact = cp.sum(cp.multiply(eta, cp.square(v)))
    variance = sum(
        cp.quad_form(inventory[t], cp.psd_wrap(covariance))
        for t in range(1, horizon + 1)
    )
    problem = cp.Problem(
        cp.Minimize(
            (impact + risk_aversion * variance) / max(float(np.mean(eta)), 1e-18)
        ),
        constraints,
    )
    problem.solve(solver="CLARABEL", canon_backend=cp.SCIPY_CANON_BACKEND)
    if problem.status != cp.OPTIMAL:
        raise ValueError("Execution schedule infeasible: " + problem.status)
    x = inventory.value * scale
    rates = x[:-1] - x[1:]
    cost = float(np.sum(eta * rates**2))
    risk = float(sum(x[t] @ covariance @ x[t] for t in range(1, horizon + 1)))
    return rates, x, cost, np.sqrt(max(risk, 0))


def execution_costs(
    symbols,
    weights_current,
    weights_target,
    nav=1000000,
    horizon_days=5,
    risk_aversion=0.1,
    returns=None,
    temporary_coefficient=None,
    permanent_coefficient=0,
):
    delta = weights_target - weights_current
    rows = liquidity_table(symbols, 252, nav, delta)
    liq = {r["ticker"]: r for r in rows}
    trades = delta.reindex(symbols).to_numpy() * nav
    if returns is None:
        raise ValueError("Observed return covariance required")
    covariance = returns.reindex(columns=symbols).cov().to_numpy()

    def coefficients(value, default):
        if isinstance(value, dict):
            return np.array(
                [float(value.get(c, default[i])) for i, c in enumerate(symbols)]
            )
        return default if value is None else np.full(len(symbols), float(value))

    default_eta = np.array(
        [liq[c]["daily_return_volatility"] / liq[c]["adv_dollars"] for c in symbols]
    )
    eta = coefficients(temporary_coefficient, default_eta)
    gamma = coefficients(permanent_coefficient, np.zeros(len(symbols)))
    if (gamma < 0).any():
        raise ValueError("Permanent impact coefficient must be nonnegative")
    rates, inventory, temp, risk = optimal_schedule(
        trades, covariance, eta, horizon_days, risk_aversion
    )
    schedule = []
    table = []
    for i, c in enumerate(symbols):
        temporary = float(eta[i] * np.square(rates[:, i]).sum())
        permanent = float(gamma[i] * trades[i] ** 2 / 2)
        table.append(
            {
                "ticker": c,
                "trade_dollars": float(trades[i]),
                "adv_dollars": liq[c]["adv_dollars"],
                "daily_return_volatility": liq[c]["daily_return_volatility"],
                "temporary_cost_dollars": temporary,
                "permanent_cost_dollars": permanent,
                "expected_is_dollars": temporary + permanent,
                "expected_is_bps": (temporary + permanent) / abs(trades[i]) * 10000
                if trades[i]
                else 0,
                "temporary_coefficient": float(eta[i]),
                "permanent_coefficient": float(gamma[i]),
                "coefficient_source": "Explicit user assumption"
                if temporary_coefficient is not None
                else "Declared linear-impact approximation sigma/ADV, not order-flow calibration",
            }
        )
        for t in range(horizon_days):
            schedule.append(
                {
                    "ticker": c,
                    "day": t + 1,
                    "trade_dollars": float(rates[t, i]),
                    "remaining_dollars": float(inventory[t + 1, i]),
                    "temporary_cost_dollars": float(eta[i] * rates[t, i] ** 2),
                }
            )
    frontier = []
    for lam in np.r_[0, np.geomspace(1e-10, 1, 20)]:
        _, _, cost, sd = optimal_schedule(
            trades, covariance, eta, horizon_days, float(lam)
        )
        frontier.append(
            {
                "risk_aversion": float(lam),
                "expected_cost_dollars": cost + float(np.sum(gamma * trades**2 / 2)),
                "shortfall_std_dollars": sd,
            }
        )
    return {
        "schedule": schedule,
        "cost_table": table,
        "frontier": frontier,
        "shortfall_std_dollars": risk,
        "temporary_cost_dollars": temp,
    }


def almgren_chriss_trajectory(x0, sigma, eta, risk_aversion, horizon):
    rates, x, _, _ = optimal_schedule(
        [x0], np.array([[sigma**2]]), [eta], horizon, risk_aversion
    )
    return [
        {"day": t + 1, "remaining": float(x[t + 1, 0]), "trade": float(rates[t, 0])}
        for t in range(horizon)
    ]
