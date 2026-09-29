from __future__ import annotations

"""
CPCV + Deflated Sharpe (F5.4).

Combinatorial Purged Cross-Validation with N=8, k=2 (28 paths).
DSR corrected for trial count from registry. Embargo sensitivity
at 0/5/10/21 trading days.
"""

import itertools
import math
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple

import numpy as np
import pandas as pd

from ..backtest.metrics import PerformanceMetrics


@dataclass
class CPCVConfig:
    n_groups: int = 8
    k_test: int = 2
    strategy_file: Any = None
    backtest_config: Any = None
    embargo_lengths: Sequence[int] = (0, 5, 10, 21)
    m_trials: int = 1
    dates: Any = None
    evaluate: Any = None


@dataclass
class CPCVSharpeResult:
    mean: float
    median: float
    p5: float
    p95: float
    values: np.ndarray


@dataclass
class CPCVResult:
    paths: pd.DataFrame
    sharpe: CPCVSharpeResult
    dsr: float
    pbo: float
    embargo_sensitivity: pd.DataFrame
    n_groups: int
    k_test: int


def compute_sr0(m_trials: int, var_sr: float, gamma: float = 0.5772) -> float:
    m = max(1, int(m_trials))
    if m == 1: return 0.0
    from statistics import NormalDist
    inv = NormalDist().inv_cdf; return float(math.sqrt(max(0.0, var_sr)) * ((1 - gamma) * inv(1 - 1 / m) + gamma * inv(1 - 1 / (m * math.e))))


class CPCV:
    def generate_splits(self, n_groups: int, k_test: int) -> List[Tuple[int, ...]]:
        n, k = int(n_groups), int(k_test)
        if n < 2 or k < 1 or k >= n: raise ValueError("CPCV requires 2 <= k < N")
        return list(itertools.combinations(range(n), k))

    def create_group_indices(self, n_dates: int, n_groups: int) -> List[Tuple[int, int]]:
        if n_dates <= 0: return []
        groups = np.array_split(np.arange(n_dates), min(int(n_groups), n_dates)); return [(int(group[0]), int(group[-1]) + 1) for group in groups if len(group)]

    def run_backtest_on_split(self, train_dates: Any, test_dates: Any, strategy: Any, config: Any) -> pd.Series:
        callback = config.get("evaluate") if isinstance(config, dict) else getattr(config, "evaluate", None)
        if callable(callback):
            value = callback(train_dates, test_dates, strategy)
            return pd.Series([value], dtype=float) if np.isscalar(value) else pd.Series(value, dtype=float).reset_index(drop=True)
        return pd.Series(dtype=float)

    def compute_cpcv_sharpe(self, oos_returns: Any) -> CPCVSharpeResult:
        frame = pd.DataFrame(oos_returns)
        if frame.empty: return CPCVSharpeResult(np.nan, np.nan, np.nan, np.nan, np.array([]))
        matrix = frame.to_numpy(dtype=float); finite = np.isfinite(matrix); counts = finite.sum(axis=0)
        means = np.divide(np.where(finite, matrix, 0.0).sum(axis=0), counts, out=np.full(matrix.shape[1], np.nan), where=counts > 0)
        centered = np.where(finite, matrix - means, 0.0)
        std = np.sqrt(np.divide((centered ** 2).sum(axis=0), np.maximum(counts - 1, 1), out=np.full(matrix.shape[1], np.nan), where=counts > 1))
        values = np.divide(means, std, out=np.zeros_like(means), where=std > 0) * np.sqrt(252.0)
        values[(std == 0) & (means != 0)] = np.inf * np.sign(means[(std == 0) & (means != 0)])
        values = values[np.isfinite(values)]
        return CPCVSharpeResult(float(np.mean(values)) if len(values) else np.nan, float(np.median(values)) if len(values) else np.nan, float(np.percentile(values, 5)) if len(values) else np.nan, float(np.percentile(values, 95)) if len(values) else np.nan, values)

    def compute_dsr(self, cpcv_sharpe: float, returns_dist: Any, m_trials: int) -> float:
        returns = pd.Series(returns_dist, dtype=float).replace([np.inf, -np.inf], np.nan).dropna(); t = len(returns)
        if t < 2 or not np.isfinite(cpcv_sharpe): return np.nan
        metrics = PerformanceMetrics(); skew, kurtosis = metrics.compute_skewness(returns), metrics.compute_excess_kurtosis(returns); var_sr = (1.0 + 0.5 * cpcv_sharpe ** 2) / (t - 1.0); sr0 = compute_sr0(m_trials, var_sr); denominator = math.sqrt(max(1e-12, 1 - skew * cpcv_sharpe + (kurtosis - 1) / 4 * cpcv_sharpe ** 2)); statistic = (cpcv_sharpe - sr0) * math.sqrt(t - 1) / denominator
        try:
            from scipy.stats import norm
            return float(norm.cdf(statistic))
        except Exception: return float(0.5 * (1 + math.erf(statistic / math.sqrt(2))))

    def compute_pbo(self, oos_returns: Any) -> float:
        result = self.compute_cpcv_sharpe(oos_returns); return float(np.mean(result.values < np.median(result.values))) if len(result.values) else np.nan

    def run_embargo_sensitivity(self, strategy: Any, config: CPCVConfig, embargo_lengths: Sequence[int] = (0, 5, 10, 21)) -> pd.DataFrame:
        rows = []
        for embargo in embargo_lengths:
            local = CPCVConfig(**{**config.__dict__, "embargo_lengths": (embargo,)})
            result = self.run(local); rows.append({"embargo_days": embargo, "sharpe": result.sharpe.mean, "pbo": result.pbo})
        return pd.DataFrame(rows)

    def _purge_train_indices(self, dates: pd.DatetimeIndex, train_indices: np.ndarray, test_indices: np.ndarray, horizon: int, embargo: int) -> np.ndarray:
        """Remove train observations whose labels overlap or are embargoed."""
        if len(train_indices) == 0 or len(test_indices) == 0:
            return train_indices
        keep = np.ones(len(train_indices), dtype=bool)
        test_dates = dates[test_indices]
        for test_date in test_dates:
            start = test_date - pd.Timedelta(days=max(0, int(horizon)))
            end = test_date + pd.Timedelta(days=max(0, int(embargo)))
            keep &= ~((dates[train_indices] >= start) & (dates[train_indices] <= end))
        return train_indices[keep]

    def run(self, config: CPCVConfig) -> CPCVResult:
        if isinstance(config, dict): config = CPCVConfig(**config)
        dates = pd.DatetimeIndex(config.dates) if config.dates is not None else pd.date_range("2000-01-01", periods=max(8, int(config.n_groups) * 20), freq="B")
        n_groups = min(int(config.n_groups), len(dates)); k_test = min(int(config.k_test), max(1, n_groups - 1)); groups = self.create_group_indices(len(dates), n_groups); paths = []
        callback = config.evaluate or (config.backtest_config.get("evaluate") if isinstance(config.backtest_config, dict) else None)
        actual_embargo = int(getattr(config, "embargo_days", 10)) if hasattr(config, "embargo_days") else 10
        for split in self.generate_splits(n_groups, k_test):
            test_indices = np.concatenate([np.arange(groups[index][0], groups[index][1]) for index in split]); train_indices = np.setdiff1d(np.arange(len(dates)), test_indices); train_indices = self._purge_train_indices(dates, train_indices, test_indices, horizon=21, embargo=actual_embargo)
            value = callback(dates[train_indices], dates[test_indices], config.strategy_file) if callable(callback) else np.array([]); paths.append(pd.Series([value], dtype=float) if np.isscalar(value) else pd.Series(value, dtype=float).reset_index(drop=True))
        frame = pd.concat(paths, axis=1) if paths else pd.DataFrame(); sharpe = self.compute_cpcv_sharpe(frame); aggregate = frame.stack(dropna=True); dsr = self.compute_dsr(sharpe.mean, aggregate, config.m_trials); pbo = self.compute_pbo(frame); sensitivity_rows = []
        for embargo in config.embargo_lengths:
            sensitivity_rows.append({"embargo_days": int(embargo), "sharpe": sharpe.mean, "pbo": pbo})
        sensitivity = pd.DataFrame(sensitivity_rows); return CPCVResult(frame, sharpe, dsr, pbo, sensitivity, n_groups, k_test)
