"""Self-financing portfolio replays and costs on actual dollar trades."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq


def trade_cost(
    old, desired, explicit_bps=5, aum=1e8, impact_gamma=None, daily_vol=None, adv=None
):
    old, desired = np.asarray(old, dtype=float), np.asarray(desired, dtype=float)
    if (
        old.shape != desired.shape
        or not np.isfinite(old).all()
        or not np.isfinite(desired).all()
        or explicit_bps < 0
        or aum <= 0
    ):
        raise ValueError("Invalid execution weights, cost or portfolio value")
    if impact_gamma is not None:
        daily_vol, adv = (
            np.asarray(daily_vol, dtype=float),
            np.asarray(adv, dtype=float),
        )
        if (
            impact_gamma < 0
            or daily_vol.shape != old.shape
            or adv.shape != old.shape
            or not np.isfinite(adv).all()
            or (adv <= 0).any()
            or not np.isfinite(daily_vol).all()
            or (daily_vol < 0).any()
        ):
            raise ValueError(
                "Temporary impact requires observed positive USD ADV and finite daily volatility"
            )

    def costs(cost):
        delta = np.abs((1 - cost) * desired - old)
        explicit = delta * explicit_bps / 10000
        impact = (
            np.zeros_like(delta)
            if impact_gamma is None
            else impact_gamma * daily_vol * delta**2 * aum / adv
        )
        return explicit + impact

    if costs(0).sum() == 0:
        fraction = 0.0
    else:
        if costs(1 - 1e-10).sum() >= 1 - 1e-10:
            raise ValueError("Estimated execution costs exhaust portfolio NAV")
        fraction = float(
            brentq(
                lambda cost: cost - float(costs(cost).sum()), 0, 1 - 1e-10, xtol=1e-13
            )
        )
    delta = (1 - fraction) * desired - old
    return {
        "cost_fraction": fraction,
        "asset_cost_fraction": costs(fraction),
        "traded_weights": delta,
        "gross_traded_notional_fraction": float(np.abs(delta).sum()),
        "one_way_turnover_including_cash": float(
            (np.abs(delta).sum() + abs(delta.sum())) / 2
        ),
        "trade_size_usd": np.abs(delta) * aum,
    }


def simulate(
    returns,
    covariance,
    reference_weights,
    target=None,
    explicit_bps=5,
    schedule="daily",
    signal_threshold=0.2,
    gross_cap=3,
    aum=1e8,
    impact_gamma=None,
    adv=None,
    annualization=252,
    cash_rate_annual=0,
):
    """Covariance/targets for date t must already be formed through t-1.

    Desired holdings are fractions of post-cost NAV. Fees are solved jointly
    with trade sizes. End-of-day holdings drift, including implicit cash.
    """
    if (
        schedule not in ("daily", "weekly", "monthly", "signal")
        or signal_threshold < 0
        or gross_cap <= 0
        or annualization <= 0
        or cash_rate_annual <= -1
    ):
        raise ValueError("Invalid rebalance or cash-financing controls")
    if not returns.index.equals(covariance.index):
        raise ValueError("Replay returns and covariance dates must match exactly")
    vector = reference_weights.reindex(returns.columns).to_numpy(dtype=float)
    old = vector.copy()
    wealth = 1.0
    gross_wealth = 1.0
    rows = []
    cash_rate = (1 + cash_rate_annual) ** (1 / annualization) - 1
    interval = {"daily": 1, "weekly": 5, "monthly": 21}.get(schedule)
    for position, (date, observed) in enumerate(returns.iterrows()):
        cov = np.asarray(covariance.loc[date], dtype=float)
        values = observed.to_numpy(dtype=float)
        if (
            not np.isfinite(values).all()
            or not np.isfinite(cov).all()
            or np.linalg.eigvalsh(cov).min() <= 0
        ):
            raise ValueError(
                "Replay requires finite observed returns and positive definite covariance"
            )
        forecast = float(np.sqrt(old @ cov @ old))
        desired_target = float(target.loc[date]) if target is not None else None
        if desired_target is not None and (
            not np.isfinite(desired_target) or desired_target < 0
        ):
            raise ValueError("Replay targets must be finite and nonnegative")
        signal = target is not None and (
            forecast > 0
            if desired_target == 0
            else abs(forecast - desired_target) / desired_target > signal_threshold
        )
        rebalance = (
            position == 0
            or (interval is not None and position % interval == 0)
            or (schedule == "signal" and signal)
            or np.abs(old).sum() > gross_cap + 1e-10
        )
        if target is None:
            desired = vector.copy() if rebalance else old.copy()
            scaling = 1.0
        else:
            reference_vol = float(np.sqrt(vector @ cov @ vector))
            scaling = min(
                desired_target / reference_vol, gross_cap / np.abs(vector).sum()
            )
            desired = vector * scaling if rebalance else old.copy()
        observed_adv = adv.loc[date].to_numpy(dtype=float) if adv is not None else None
        cost = trade_cost(
            old,
            desired,
            explicit_bps,
            aum * wealth,
            impact_gamma,
            np.sqrt(np.diag(cov) / annualization),
            observed_adv,
        )
        gross_return = float(desired @ values + (1 - desired.sum()) * cash_rate)
        net_return = (1 - cost["cost_fraction"]) * (1 + gross_return) - 1
        if gross_return <= -1 or net_return <= -1:
            raise ValueError(f"Portfolio NAV became nonpositive at {date}")
        fee_usd = cost["cost_fraction"] * wealth * aum
        wealth *= 1 + net_return
        gross_wealth *= 1 + gross_return
        old = desired * (1 + values) / (1 + gross_return)
        rows.append(
            {
                "date": date,
                "forecast_volatility_before_trade": forecast,
                "reference_forecast_volatility": float(np.sqrt(vector @ cov @ vector)),
                "target_volatility": desired_target,
                "scaling_factor": scaling,
                "applied_gross_scaling_factor": float(
                    np.abs(desired).sum() / np.abs(vector).sum()
                ),
                "rebalance": bool(rebalance),
                "gross_return": gross_return,
                "net_return": net_return,
                "gross_nav": gross_wealth,
                "net_nav": wealth,
                "cost_fraction": cost["cost_fraction"],
                "cost_usd": fee_usd,
                "gross_traded_notional_fraction": cost[
                    "gross_traded_notional_fraction"
                ],
                "one_way_turnover_including_cash": cost[
                    "one_way_turnover_including_cash"
                ],
                "weights_before_return": desired.tolist(),
                "drifted_weights_after_return": old.tolist(),
            }
        )
    return pd.DataFrame(rows).set_index("date")


def performance(returns, annualization=252, risk_free_annual=0):
    values = np.asarray(returns, dtype=float)
    if annualization <= 0 or risk_free_annual <= -1:
        raise ValueError("Invalid performance annualization or risk-free assumption")
    if len(values) < 2 or not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError(
            "Performance requires at least two finite solvent portfolio returns"
        )
    nav = np.cumprod(1 + values)
    cagr = float(nav[-1] ** (annualization / len(values)) - 1)
    volatility = float(np.std(values, ddof=1) * np.sqrt(annualization))
    arithmetic = float(np.mean(values) * annualization)
    drawdown = float(np.min(nav / np.maximum.accumulate(np.r_[1, nav])[1:] - 1))
    return {
        "annualized_return_cagr": cagr,
        "annualized_arithmetic_return": arithmetic,
        "annualized_volatility": volatility,
        "sharpe": (
            arithmetic
            - ((1 + risk_free_annual) ** (1 / annualization) - 1) * annualization
        )
        / volatility
        if volatility > 0
        else None,
        "maximum_drawdown": drawdown,
        "calmar": cagr / abs(drawdown) if drawdown < 0 else None,
        "observations": len(values),
        "risk_free_annual_assumption": risk_free_annual,
    }
