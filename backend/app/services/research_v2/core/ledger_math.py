"""Multiple-testing math for the trial ledger: deflated Sharpe hurdle, Harvey-Liu haircut, PBO via CSCV."""
from __future__ import annotations

from itertools import combinations
from math import e

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


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
    blocks = np.array_split(np.arange(m.shape[0]), n_splits)
    logits = []
    for train_ids in combinations(range(n_splits), n_splits // 2):
        test_ids = [i for i in range(n_splits) if i not in train_ids]
        tr = m[np.concatenate([blocks[i] for i in train_ids])]
        te = m[np.concatenate([blocks[i] for i in test_ids])]
        sr_tr = tr.mean(0) / (tr.std(0, ddof=1) + 1e-12)
        sr_te = te.mean(0) / (te.std(0, ddof=1) + 1e-12)
        best = int(np.argmax(sr_tr))
        rank = (sr_te < sr_te[best]).sum() + 0.5 * ((sr_te == sr_te[best]).sum() - 1)
        w = (rank + 1) / (len(sr_te) + 1)
        logits.append(np.log(w / (1 - w)))
    return float(np.mean(np.asarray(logits) <= 0))
