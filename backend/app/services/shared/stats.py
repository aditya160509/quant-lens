"""Validation statistics shared by every lab."""
import math
from itertools import combinations

import numpy as np
from scipy import stats


def cscv_pbo(returns, partitions=8):
    matrix = np.asarray(returns, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] < 2 or not np.isfinite(matrix).all():
        raise ValueError("CSCV requires a complete time-by-strategy return matrix with at least two strategies")
    if partitions < 4 or partitions > 12 or partitions % 2 or matrix.shape[0] < partitions * 2:
        raise ValueError("CSCV partitions must be even, 4 to 12, with at least two observations per partition")
    blocks = np.array_split(np.arange(len(matrix)), partitions)
    logits = []
    for train_blocks in combinations(range(partitions), partitions // 2):
        train = np.concatenate([blocks[i] for i in train_blocks])
        test = np.concatenate([blocks[i] for i in range(partitions) if i not in train_blocks])
        sd_train, sd_test = matrix[train].std(0, ddof=1), matrix[test].std(0, ddof=1)
        if np.any(sd_train <= 1e-12) or np.any(sd_test <= 1e-12):
            raise ValueError("CSCV Sharpe is undefined for constant strategy returns")
        insample = matrix[train].mean(0) / sd_train
        outsample = matrix[test].mean(0) / sd_test
        winner = int(np.argmax(insample))
        relative_rank = stats.rankdata(outsample, method="average")[winner] / (matrix.shape[1] + 1)
        logits.append(math.log(relative_rank / (1 - relative_rank)))
    return {"pbo": float(np.mean(np.asarray(logits) <= 0)), "combinations": len(logits), "logits": logits}


def deflated_sharpe_probability(returns, trials, trial_sharpe_variance):
    values = np.asarray(returns, dtype=float)
    if len(values) < 3 or not np.isfinite(values).all() or values.std(ddof=1) <= 1e-12:
        raise ValueError("DSR requires at least three finite nonconstant returns")
    if trials < 1 or trial_sharpe_variance < 0 or not math.isfinite(trial_sharpe_variance):
        raise ValueError("Invalid trial count or trial Sharpe variance")
    sr = values.mean() / values.std(ddof=1)
    expected = 0.
    if trials > 1:
        gamma = np.euler_gamma
        expected = math.sqrt(trial_sharpe_variance) * ((1-gamma)*stats.norm.ppf(1-1/trials) + gamma*stats.norm.ppf(1-1/(trials*math.e)))
    skew = stats.skew(values, bias=False)
    kurtosis = stats.kurtosis(values, fisher=False, bias=False)
    variance = (1 - skew * sr + (kurtosis - 1) * sr * sr / 4) / (len(values) - 1)
    if variance <= 0:
        raise ValueError("DSR variance is nonpositive")
    return float(stats.norm.cdf((sr - expected) / math.sqrt(variance)))
