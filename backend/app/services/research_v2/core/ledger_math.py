"""Multiple-testing math for the trial ledger: deflated Sharpe hurdle, Harvey-Liu haircut, PBO via CSCV."""
from __future__ import annotations

from math import e

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329

from app.services.shared.stats import cscv_pbo as shared_cscv_pbo


def deflated_sharpe_hurdle(n_trials: int, sharpe_variance: float) -> float | None:
    """Expected max Sharpe under the null across N trials (Bailey & Lopez de Prado 2014, eq. for SR0)."""
    if n_trials < 2 or not np.isfinite(sharpe_variance) or sharpe_variance < 0:
        return None
    return float(np.sqrt(sharpe_variance) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials) + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * e))))


def haircut_t(t_stat: float, n_trials: int) -> dict:
    """Harvey-Liu Bonferroni haircut: fraction of the observed statistic lost after adjusting for N trials."""
    t = abs(float(t_stat))
    if t == 0 or n_trials < 1:
        return {"adjusted": 0.0, "haircut": None}
    p_adj = min(1.0, n_trials * 2 * (1 - norm.cdf(t)))
    adj = float(norm.ppf(1 - p_adj / 2)) if p_adj < 1 else 0.0
    return {"adjusted": adj, "haircut": float(1 - adj / t)}


def pbo_cscv(returns: np.ndarray, n_splits: int = 8) -> float | None:
    """Probability of backtest overfitting via combinatorially symmetric CV. returns: T x N (N >= 8 strategies)."""
    m = np.asarray(returns, dtype=float)
    if m.ndim != 2 or m.shape[1] < 8 or m.shape[0] < n_splits * 2:
        return None
    try:
        return shared_cscv_pbo(m, n_splits)["pbo"]
    except ValueError:  # non-finite or constant strategy returns have no defined Sharpe
        return None
