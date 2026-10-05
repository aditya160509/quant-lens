"""Observed close-to-close portfolio accounting, with next-close execution."""
from __future__ import annotations
import numpy as np
from scipy.optimize import brentq

def execute_portfolio(returns, targets, cost_bps=0.):
    """Targets formed at t execute at close t+1, earning returns from t+2.

    Assets use native-currency returns; FX and stock-borrow financing are excluded.
    """
    if not 0 <= cost_bps <= 1000:
        raise ValueError("cost_bps must be between 0 and 1000")
    weights = np.zeros(len(returns.columns))
    nav, rows = 1., []
    fee = cost_bps / 10000
    for i, (date, row) in enumerate(returns.iterrows()):
        values = row.to_numpy(dtype=float)
        held = np.abs(weights) > 1e-12
        if np.any(~np.isfinite(values[held])):
            raise ValueError(f"Missing held-asset return on {date}; portfolio cannot be valued")
        observed = np.where(np.isfinite(values), np.expm1(values), 0.)
        gross_return = float(weights @ observed)
        gross_growth = 1 + gross_return
        if gross_growth <= 0:
            raise ValueError("Portfolio NAV became nonpositive")
        drift = weights * (1 + observed) / gross_growth
        target = targets.get(returns.index[i-1]) if i else None
        turnover, cost = 0., 0.
        scale = 1.
        if target is not None:
            desired = np.array([target.get(ticker, 0.) for ticker in returns.columns])
            if np.any(~np.isfinite(values[np.abs(desired) > 1e-12])):
                raise ValueError(f"Missing execution return on {date}")
            if fee:
                scale = brentq(lambda q: q + fee * np.abs(desired * q - drift).sum() - 1., 0., 1.)
            turnover = float(np.abs(desired * scale - drift).sum())
            cost = fee * turnover
            weights = desired
        else:
            weights = drift
        growth = gross_growth * scale
        nav *= growth
        rows.append({"date": str(date.date()), "gross_return": gross_return,
                     "net_return": growth - 1, "turnover": turnover, "cost_fraction": cost,
                     "equity": nav})
    return rows
