"""Cheap daily OHLCV liquidity and friction estimators used as Alpha features (no standalone page)."""
from __future__ import annotations
import numpy as np


def market_residual_ivol(returns, annualization, window=21):
    """Rolling OLS with intercept and equal-weight market, residual df = n-2."""
    market = returns.mean(axis=1,skipna=False)
    market_var = market.rolling(window).var(ddof=1)
    covariance = returns.rolling(window).cov(market)
    residual_variance = returns.rolling(window).var(ddof=1) - covariance.pow(2).div(market_var,axis=0)
    return np.sqrt(residual_variance.clip(lower=0)*(window-1)/(window-2)*annualization)


def roll_spread(close, window=21):
    """Roll (1984) effective spread as a fraction of price: 2*sqrt(-cov(dP_t, dP_t-1)), zero when the covariance is positive."""
    changes = close.diff()
    covariance = changes.rolling(window).cov(changes.shift(1))
    return 2 * np.sqrt((-covariance).clip(lower=0)) / close
