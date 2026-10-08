"""Causal re-estimation, drifting exposures and actual trade cost accounting."""

from __future__ import annotations
import numpy as np
import pandas as pd
from .construction import solve_portfolio
from .context import parse_weights
from .stats import performance_metrics


def walk_forward(returns, payload=None):
    payload = dict(payload or {})
    window = int(payload.get("walk_forward_window", 252))
    interval = payload.get("rebalance_days")
    frequency = payload.get("rebalance_frequency", "monthly")
    periods = {
        "weekly": "W",
        "monthly": "M",
        "quarterly": "Q",
        "semiannual": "2Q",
        "annual": "Y",
    }
    if interval is not None:
        interval = int(interval)
    if frequency not in {*periods, "daily", "threshold"}:
        raise ValueError("Unknown rebalance frequency")
    calendar = (
        (returns.index.year * 2 + (returns.index.month - 1) // 6)
        if frequency == "semiannual"
        else (
            returns.index.to_period(periods[frequency])
            if frequency in periods
            else None
        )
    )
    ann = float(
        payload.get(
            "annualization",
            {"daily": 252, "weekly": 52, "monthly": 12}.get(
                payload.get("frequency", "daily"), 252
            ),
        )
    )
    if window < 30 or (interval is not None and interval < 1) or len(returns) <= window:
        raise ValueError(
            "Walk-forward requires a training window >=30 and subsequent observations"
        )
    objective = payload.get("objective", "global_min_variance")
    manual = parse_weights(payload, list(returns.columns))
    cash_rate = float(payload.get("cash_rate_annual", 0)) / float(ann)
    cost = float(payload.get("transaction_cost_bps", 5)) / 10000
    positions = np.zeros(returns.shape[1])
    cash = 1.0
    gross_wealth = 1.0
    last_rebalance = None
    target = np.zeros(returns.shape[1])
    records = []
    trades = []
    folds = []
    for t in range(window, len(returns)):
        date = returns.index[t]
        value = positions.sum() + cash
        if value <= 0:
            raise ValueError(f"Portfolio became insolvent before {date}")
        current = positions / value
        training = returns.iloc[t - window : t].dropna()
        trigger = last_rebalance is None
        if last_rebalance is not None:
            trigger = (
                (t - last_rebalance >= interval)
                if interval is not None
                else (
                    frequency == "daily"
                    or (
                        calendar is not None and calendar[t] != calendar[last_rebalance]
                    )
                )
            )
        if (
            payload.get("rebalance_frequency") == "threshold"
            and last_rebalance is not None
        ):
            trigger = np.max(np.abs(current - target)) >= float(
                payload.get("drift_tolerance", 0.05)
            )
        if trigger:
            if len(training) < 30:
                raise ValueError(f"Insufficient complete training data before {date}")
            if manual is None:
                params = {
                    **payload,
                    "current_weights": dict(zip(returns.columns, current)),
                }
                # Static current classifications must never enter a historical constraint.
                if payload.get("sector_max_weights"):
                    raise ValueError(
                        "Historical sector constraints require point-in-time sector classifications"
                    )
                target, detail = solve_portfolio(training, params, objective)
                target = target.to_numpy()
            else:
                target = manual.to_numpy()
                detail = {"success": True, "solver": "explicit manual target"}
            pre_value = value
            # Trades target post-fee NAV, solved by a scalar fixed point.
            for _ in range(100):
                trade = target * value - positions
                fee = np.abs(trade).sum() * cost
                updated = pre_value - fee
                if abs(updated - value) < 1e-12 * pre_value:
                    value = updated
                    break
                value = updated
            else:
                raise ValueError("Post-fee trade accounting did not converge")
            if value <= 0:
                raise ValueError("Transaction costs exhaust NAV")
            trade = target * value - positions
            fee = np.abs(trade).sum() * cost
            positions = target * value
            cash = value - positions.sum()
            turnover = float(np.abs(trade).sum() / pre_value)
            for i, c in enumerate(returns.columns):
                trades.append(
                    {
                        "date": date,
                        "ticker": c,
                        "training_end": training.index[-1],
                        "pre_trade_weight": current[i],
                        "target_weight": target[i],
                        "trade_nav_fraction": float(trade[i] / pre_value),
                        "cost_nav_fraction": float(abs(trade[i]) * cost / pre_value),
                        "turnover": turnover,
                    }
                )
            train_metric = performance_metrics(training @ target, ann)
            folds.append(
                {
                    "rebalance_date": date,
                    "training_end": training.index[-1],
                    "train_sharpe": train_metric["sharpe"],
                    "success": detail["success"],
                    "solver": detail["solver"],
                }
            )
            last_rebalance = t
        else:
            fee = 0.0
            turnover = 0.0
            pre_value = value
        observed = returns.iloc[t].to_numpy()
        held = np.abs(positions) > 1e-14
        if not np.isfinite(observed[held]).all():
            raise ValueError(
                f"Missing observed return for held asset at {date}; delisting/halt cannot be valued as zero"
            )
        pnl = float(positions[held] @ observed[held] + cash * cash_rate)
        gross_return = pnl / value
        positions[held] *= 1 + observed[held]
        cash *= 1 + cash_rate
        end_value = positions.sum() + cash
        net_return = end_value / pre_value - 1
        if end_value <= 0:
            raise ValueError(f"Portfolio insolvent at {date}")
        gross_wealth *= 1 + gross_return
        records.append(
            {
                "date": date,
                "gross_return": gross_return,
                "net_return": net_return,
                "gross": gross_wealth,
                "net": float(end_value),
                "cost": fee / pre_value,
                "turnover": turnover,
            }
        )
    rows = pd.DataFrame(records)
    for i, fold in enumerate(folds):
        end = (
            folds[i + 1]["rebalance_date"]
            if i + 1 < len(folds)
            else returns.index[-1] + pd.Timedelta(nanoseconds=1)
        )
        sample = rows.loc[
            (rows.date >= fold["rebalance_date"]) & (rows.date < end), "net_return"
        ]
        test = performance_metrics(sample, ann)["sharpe"] if len(sample) > 1 else None
        fold["test_sharpe"] = test
        fold["oos_to_is_sharpe_ratio"] = (
            test / fold["train_sharpe"]
            if test is not None and fold["train_sharpe"] not in {None, 0}
            else None
        )
    return rows, trades, folds


def drawdown_episodes(series):
    wealth = (1 + series).cumprod()
    peak = 1.0
    start = None
    trough = None
    depth = 0.0
    rows = []
    for date, value in wealth.items():
        if value >= peak:
            if start is not None:
                rows.append(
                    {
                        "start": start,
                        "trough": trough,
                        "recovery": date,
                        "depth": depth,
                        "calendar_days": (date - start).days,
                        "open": False,
                    }
                )
            peak = value
            start = None
            depth = 0
        else:
            if start is None:
                start = date
            dd = value / peak - 1
            if dd < depth:
                depth = dd
                trough = date
    if start is not None:
        rows.append(
            {
                "start": start,
                "trough": trough,
                "recovery": None,
                "depth": depth,
                "calendar_days": (series.index[-1] - start).days,
                "open": True,
            }
        )
    return sorted(rows, key=lambda row: row["depth"])
