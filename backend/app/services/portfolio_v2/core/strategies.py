"""Causal strategy allocation with capacity, risk and correlation constraints."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize, milp, Bounds, LinearConstraint


def constrained_allocation(training, payload, current=None):
    cols = list(training)
    ann = {"daily": 252, "weekly": 52, "monthly": 12}[payload.get("frequency", "daily")]
    regime_detail = {}
    covariance = training.cov().to_numpy() * ann
    sigma = np.sqrt(np.diag(covariance))
    mean = training.mean().to_numpy() * ann
    if (sigma <= 0).any():
        raise ValueError("Strategy volatility must be positive")
    rule = payload.get("allocation_rule", "inverse_vol")
    if rule == "regime_conditional":
        from hmmlearn.hmm import GaussianHMM
        from sklearn.preprocessing import StandardScaler

        if len(training) < 100:
            raise ValueError(
                "Regime-conditional strategy allocation requires at least 100 prior observations"
            )
        scaler = StandardScaler().fit(training)
        X = scaler.transform(training)
        fits = []
        for seed in [7, 17, 27]:
            model = GaussianHMM(
                n_components=2,
                covariance_type="full",
                n_iter=300,
                tol=0.01,
                min_covar=1e-5,
                random_state=seed,
            ).fit(X)
            history = list(model.monitor_.history)
            if (
                len(history) >= 2
                and abs(history[-1] - history[-2]) < model.tol
                and np.isfinite(model.score(X))
            ):
                fits.append(model)
        if not fits:
            raise ValueError(
                "Strategy regime HMM did not converge; no allocation surrogate"
            )
        model = max(fits, key=lambda m: m.score(X))
        probability = model.predict_proba(X)[-1] @ model.transmat_
        means = scaler.inverse_transform(model.means_)
        covariances = model.covars_ * np.outer(scaler.scale_, scaler.scale_)
        mean_daily = probability @ means
        deviations = means - mean_daily
        covariance = (
            sum(
                probability[k]
                * (covariances[k] + np.outer(deviations[k], deviations[k]))
                for k in range(2)
            )
            * ann
        )
        mean = mean_daily * ann
        sigma = np.sqrt(np.diag(covariance))
        score = 1 / sigma
        regime_detail = {
            "regime_model": "Two-state full-covariance Gaussian HMM on actual strategy returns, fitted strictly before holding date",
            "next_regime_probabilities": probability.tolist(),
        }
    elif rule == "inverse_vol":
        score = 1 / sigma
    elif rule == "sharpe_momentum":
        ranks = pd.Series(mean / sigma).rank(pct=True).to_numpy()
        score = np.where(ranks >= 2 / 3, 1.5, np.where(ranks <= 1 / 3, 0.5, 1.0))
    elif rule == "kelly":
        score = np.maximum(mean, 1e-8)
    elif rule == "fixed":
        score = np.ones(len(cols))
    else:
        raise ValueError("Unknown allocation_rule")
    correlation = training.corr().to_numpy()
    cap = float(payload.get("correlation_constraint", 0.8))
    pairs = np.argwhere(np.triu(correlation > cap, 1))
    selected = np.ones(len(cols), bool)
    if len(pairs):
        matrix = np.zeros((len(pairs), len(cols)))
        for row, (i, j) in enumerate(pairs):
            matrix[row, [i, j]] = 1
        result = milp(
            -score,
            integrality=np.ones(len(cols)),
            bounds=Bounds(0, 1),
            constraints=LinearConstraint(matrix, -np.inf, 1),
            options={"time_limit": 10},
        )
        if not result.success:
            raise ValueError(
                "Correlation selection MILP did not solve: " + result.message
            )
        selected = result.x > 0.5
    capacities = payload.get("capacity_limits") or {c: 1 for c in cols}
    budgets = payload.get("risk_budgets") or {c: 1 / len(cols) for c in cols}
    if set(capacities) != set(cols) or set(budgets) != set(cols):
        raise ValueError("Capacities and budgets must name every strategy")
    upper = np.array([float(capacities[c]) for c in cols])
    risk_budget = np.array([float(budgets[c]) for c in cols])
    if (
        (upper < 0).any()
        or (upper > 1).any()
        or (risk_budget < 0).any()
        or not np.isclose(risk_budget.sum(), 1)
    ):
        raise ValueError("Invalid capacity fractions or normalized risk budgets")
    upper *= selected
    target = float(payload.get("vol_target", 0.1))
    desired = score * selected
    if desired.sum() > 0:
        desired /= desired.sum()
    seed = np.minimum(desired, upper) * min(
        1, target / max(np.sqrt(desired @ covariance @ desired), 1e-12)
    )

    def risk_components(w):
        vol = np.sqrt(max(float(w @ covariance @ w), 1e-24))
        return w * (covariance @ w) / vol

    constraints = [
        {"type": "ineq", "fun": lambda w: 1 - w.sum()},
        {"type": "ineq", "fun": lambda w: target**2 - w @ covariance @ w},
        {"type": "ineq", "fun": lambda w: target * risk_budget - risk_components(w)},
    ]

    def goal(w):
        return (
            float(0.5 * w @ covariance @ w - w @ mean)
            if rule == "kelly"
            else float(np.square(w - desired).sum())
        )

    active = np.flatnonzero(upper > 0)
    if not len(active):
        raise ValueError("No strategies have positive eligible capacity")

    def expand(x):
        w = np.zeros(len(cols))
        w[active] = x
        return w

    # Remove fixed-zero MILP exclusions from the nonlinear solve. This avoids
    # singular equality/bound directions without relaxing any risk constraint.
    rc = risk_components(seed)
    positive = rc > 0
    if positive.any():
        seed *= (
            min(1.0, float(np.min(target * risk_budget[positive] / rc[positive])))
            * 0.95
        )
    reduced_constraints = [
        {"type": "ineq", "fun": lambda x, c=c: c["fun"](expand(x))} for c in constraints
    ]
    fit = minimize(
        lambda x: goal(expand(x)),
        seed[active],
        method="SLSQP",
        bounds=list(zip(np.zeros(len(active)), upper[active])),
        constraints=reduced_constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    weights = expand(fit.x)
    if not fit.success or any(np.min(c["fun"](weights)) < -1e-6 for c in constraints):
        raise ValueError("Strategy allocation did not solve: " + fit.message)
    if any(weights[i] > 1e-6 and weights[j] > 1e-6 for i, j in pairs):
        raise ValueError("Correlation constraint violated")
    return pd.Series(weights, index=cols), {
        **regime_detail,
        "annual_vol": float(np.sqrt(weights @ covariance @ weights)),
        "risk_components": dict(zip(cols, risk_components(weights))),
        "cash_weight": float(1 - weights.sum()),
        "correlation_constraint": "No simultaneous nonzero allocations to observed pairs above threshold; MILP chooses an eligible set using the selected rule's scores",
    }


def strategy_backtest(returns, payload):
    window = int(payload.get("training_window", 126))
    interval = int(payload.get("rebalance_days", 21))
    limit = float(payload.get("kill_switch_drawdown", 0.15))
    if len(returns) <= window:
        raise ValueError("Strategy returns need training and held-out dates")
    if (
        returns.isna().any().any()
        or not np.isfinite(returns).all().all()
        or (returns <= -1).any().any()
    ):
        raise ValueError("Complete finite observed strategy returns above -1 required")
    wealth = (1 + returns).cumprod()
    drawdowns = wealth / wealth.cummax().clip(lower=1) - 1
    current = pd.Series(0.0, index=returns.columns)
    target = current.copy()
    rows = []
    allocations = []
    audits = []
    capital = 1.0
    cash = 1.0
    positions = np.zeros(len(returns.columns))
    previous_scale = np.ones(len(returns.columns))
    for t in range(window, len(returns)):
        date = returns.index[t]
        value = positions.sum() + cash
        current = pd.Series(positions / value, index=returns.columns)
        if (t - window) % interval == 0:
            target, detail = constrained_allocation(
                returns.iloc[t - window : t], payload, current
            )
            audits.append(
                {"date": date, "training_end": returns.index[t - 1], **detail}
            )
        # The action uses the prior close's drawdown, never today's realized loss.
        prior = drawdowns.iloc[t - 1].abs()
        scale = np.where(
            prior >= limit,
            0,
            np.where(
                prior >= 0.75 * limit, 0.5, np.where(prior >= 0.5 * limit, 0.75, 1.0)
            ),
        )
        desired = target * scale
        fee = 0.0
        turnover = 0.0
        if (t - window) % interval == 0 or not np.allclose(
            scale, previous_scale if t > window else np.ones(len(scale))
        ):
            rate = float(payload.get("transaction_cost_bps", 10)) / 10000
            post = value
            for _ in range(100):
                trades = desired.to_numpy() * post - positions
                updated = value - np.abs(trades).sum() * rate
                if abs(updated - post) < 1e-12 * value:
                    post = updated
                    break
                post = updated
            else:
                raise ValueError("Strategy post-fee accounting did not converge")
            if post <= 0:
                raise ValueError("Strategy transaction costs exhaust NAV")
            trades = desired.to_numpy() * post - positions
            fee = float(np.abs(trades).sum() * rate / value)
            turnover = float(np.abs(trades).sum() / value)
            positions = desired.to_numpy() * post
            cash = post - positions.sum()
        allocated = positions / (positions.sum() + cash)
        positions *= 1 + returns.iloc[t].to_numpy()
        capital = positions.sum() + cash
        rows.append(
            {
                "date": date,
                "return": capital / value - 1,
                "wealth": capital,
                "turnover": turnover,
                "cost_fraction": fee,
                "training_end": returns.index[t - 1],
            }
        )
        allocations.extend(
            {
                "date": date,
                "strategy": c,
                "allocated_weight": float(allocated[i]),
                "target_weight": float(desired[c]),
                "kill_scale": float(scale[i]),
                "prior_drawdown": float(prior[c]),
            }
            for i, c in enumerate(returns.columns)
        )
        previous_scale = scale
    return pd.DataFrame(rows), allocations, audits


def netting_savings(strategy_trades, tc_bps=10, nav=1000000):
    required = {"date", "asset", "strategy", "trade_weight"}
    if not required <= set(strategy_trades):
        raise ValueError(
            "Netting needs actual date,asset,strategy,trade_weight records"
        )
    if strategy_trades.duplicated(["date", "asset", "strategy"]).any():
        raise ValueError("Duplicate strategy trade records")
    rows = []
    for (date, asset), g in strategy_trades.groupby(["date", "asset"]):
        gross = float(g.trade_weight.abs().sum())
        net = abs(float(g.trade_weight.sum()))
        saved = gross - net
        rows.append(
            {
                "date": date,
                "asset": asset,
                "gross_trade": gross,
                "net_trade": net,
                "netting_ratio": saved / gross if gross else 0,
                "savings_dollars": saved * nav * tc_bps / 10000,
            }
        )
    return rows


def kill_switch_pnl_calibration(strategy_returns, thresholds=(0.05, 0.1, 0.15, 0.2)):
    rows = []
    for c in strategy_returns:
        series = strategy_returns[c]
        wealth = (1 + series).cumprod()
        dd = wealth / wealth.cummax().clip(lower=1) - 1
        for threshold in thresholds:
            triggered = dd.shift(1, fill_value=0).le(-threshold).cummax()
            held = float((1 + series).prod() - 1)
            cut = float((1 + series.where(~triggered, 0)).prod() - 1)
            rows.append(
                {
                    "strategy": c,
                    "threshold": threshold,
                    "held_return": held,
                    "cut_return": cut,
                    "return_saved_by_cut": cut - held,
                    "triggered": bool(triggered.any()),
                    "policy": "Exit at next observed interval after first closing drawdown breach; no hindsight reset",
                }
            )
    return rows
