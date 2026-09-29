from __future__ import annotations

"""
Honest Performance Card metrics (F2.4).

DSR (M=1 default for standalone runs), PBO, PSR, Sharpe, Sortino,
Calmar, max drawdown, win rate, profit factor.
"""

import math
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


def _clean(returns: pd.Series) -> pd.Series:
    return pd.Series(returns, copy=True).astype(float).replace([np.inf, -np.inf], np.nan).dropna()


def _normal_cdf(value: float) -> float:
    try:
        from scipy.stats import norm
        return float(norm.cdf(value))
    except Exception:
        return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_ppf(probability: float) -> float:
    p = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    try:
        from scipy.stats import norm
        return float(norm.ppf(p))
    except Exception:
        return float(__import__("statistics").NormalDist().inv_cdf(p))


@dataclass
class MetricCard:
    dsr: Optional[float]
    pbo: Optional[float]
    psr: Optional[float]
    sharpe: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    max_drawdown: Optional[float]
    win_rate: Optional[float]
    profit_factor: Optional[float]
    skewness: Optional[float]
    excess_kurtosis: Optional[float]
    m_trials: int
    lookahead_inflation: Optional[float] = None
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class PerformanceMetrics:
    """Compute the Honest Performance Card without hiding invalid statistics."""

    def compute_all(self, returns: pd.Series, cpcv_paths: Any = None, m_trials: int = 1) -> MetricCard:
        clean = _clean(returns)
        if len(clean) < 2:
            values = [float("nan")] * 11
            return MetricCard(*values, max(1, int(m_trials)), label="insufficient data")
        sharpe = self.compute_sharpe(clean)
        pbo = self.compute_pbo(cpcv_paths) if cpcv_paths is not None else float("nan")
        return MetricCard(self.compute_dsr(clean, sharpe, m_trials), pbo, self.compute_psr(clean, sharpe), sharpe, self.compute_sortino(clean), self.compute_calmar(clean), self.compute_max_drawdown(clean), self.compute_win_rate(clean), self.compute_profit_factor(clean), self.compute_skewness(clean), self.compute_excess_kurtosis(clean), max(1, int(m_trials)), label=None if cpcv_paths is not None else "run CPCV (F5.4) to compute PBO")

    def compute_sharpe(self, returns: pd.Series, rf: float = 0.0) -> float:
        clean = _clean(returns)
        if len(clean) < 2:
            return float("nan")
        sd = float(clean.std(ddof=1))
        return 0.0 if sd == 0 else float((clean.mean() - rf) / sd * math.sqrt(252.0))

    def compute_sortino(self, returns: pd.Series, rf: float = 0.0) -> float:
        clean = _clean(returns)
        if len(clean) < 2:
            return float("nan")
        downside = np.minimum(clean.to_numpy(), 0.0)
        denominator = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
        numerator = float(clean.mean() - rf)
        return float("inf") if denominator == 0 and numerator > 0 else (0.0 if denominator == 0 else float(numerator / denominator * math.sqrt(252.0)))

    def compute_calmar(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        if len(clean) < 2:
            return float("nan")
        drawdown, growth = self.compute_max_drawdown(clean), cagr(clean)
        return float("inf") if drawdown == 0 and growth > 0 else (0.0 if drawdown == 0 else float(growth / drawdown))

    def compute_max_drawdown(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        if clean.empty:
            return float("nan")
        wealth = np.cumprod(1.0 + clean.to_numpy())
        peaks = np.maximum.accumulate(wealth)
        drawdowns = np.divide(peaks - wealth, peaks, out=np.zeros_like(wealth), where=peaks != 0)
        return float(np.max(drawdowns))

    def compute_psr(self, returns: pd.Series, sharpe: float, rf: float = 0.0) -> float:
        clean = _clean(returns)
        if len(clean) < 2 or not np.isfinite(sharpe):
            return float("nan")
        skew, kurtosis = self.compute_skewness(clean), self.compute_excess_kurtosis(clean)
        denominator = math.sqrt(max(1e-12, 1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe ** 2))
        return _normal_cdf(sharpe * math.sqrt(len(clean) - 1.0) / denominator)

    def compute_dsr(self, returns: pd.Series, sharpe: float, m_trials: int, gamma: float = 0.5772) -> float:
        clean = _clean(returns)
        if len(clean) < 2 or not np.isfinite(sharpe):
            return float("nan")
        m = max(1, int(m_trials))
        if m == 1:
            sr0 = 0.0
        else:
            var_sr = (1.0 + 0.5 * sharpe ** 2) / max(1.0, len(clean) - 1.0)
            sr0 = math.sqrt(var_sr) * ((1.0 - gamma) * _normal_ppf(1.0 - 1.0 / m) + gamma * _normal_ppf(1.0 - 1.0 / (m * math.e)))
        skew, kurtosis = self.compute_skewness(clean), self.compute_excess_kurtosis(clean)
        denominator = math.sqrt(max(1e-12, 1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe ** 2))
        return _normal_cdf((sharpe - sr0) * math.sqrt(len(clean) - 1.0) / denominator)

    def compute_pbo(self, cpcv_paths: Any) -> float:
        if cpcv_paths is None:
            return float("nan")
        if isinstance(cpcv_paths, pd.DataFrame):
            matrix = cpcv_paths.to_numpy(dtype=float)
            if matrix.ndim == 1:
                matrix = matrix[:, None]
            finite = np.isfinite(matrix)
            counts = finite.sum(axis=0)
            means = np.divide(np.where(finite, matrix, 0.0).sum(axis=0), counts, out=np.full(matrix.shape[1], np.nan), where=counts > 0)
            centered = np.where(finite, matrix - means, 0.0)
            std = np.sqrt(np.divide((centered ** 2).sum(axis=0), np.maximum(counts - 1, 1), out=np.full(matrix.shape[1], np.nan), where=counts > 1))
            values = np.divide(means, std, out=np.full(matrix.shape[1], np.nan), where=std > 0) * math.sqrt(252.0)
            zero_std = (std == 0) & np.isfinite(means)
            values[zero_std] = 0.0
            positive_zero = zero_std & (means > 0)
            negative_zero = zero_std & (means < 0)
            values[positive_zero] = np.inf
            values[negative_zero] = -np.inf
            if not np.isfinite(values).any():
                values = np.asarray([self.compute_sharpe(row) for row in matrix], dtype=float)
        else:
            values = np.asarray(cpcv_paths, dtype=float)
            if values.ndim > 1:
                values = np.asarray([self.compute_sharpe(row) for row in values])
        values = values[np.isfinite(values)]
        return float(np.mean(values < np.median(values))) if values.size else float("nan")

    def compute_skewness(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        value = clean.skew() if len(clean) >= 3 else 0.0
        return float(value) if np.isfinite(value) else 0.0

    def compute_excess_kurtosis(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        value = clean.kurt() if len(clean) >= 4 else 0.0
        return float(value) if np.isfinite(value) else 0.0

    def compute_win_rate(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        return float((clean > 0).mean()) if len(clean) else float("nan")

    def compute_profit_factor(self, returns: pd.Series) -> float:
        clean = _clean(returns)
        gains, losses = clean[clean > 0].sum(), abs(clean[clean < 0].sum())
        return float("inf") if losses == 0 and gains > 0 else (0.0 if losses == 0 else float(gains / losses))


def annualized_sharpe(daily_returns: pd.Series, rf_annual: float = 0.0) -> float:
    clean = _clean(daily_returns)
    if len(clean) < 2:
        return float("nan")
    rf_daily = (1.0 + float(rf_annual)) ** (1.0 / 252.0) - 1.0
    sd = float(clean.std(ddof=1))
    return 0.0 if sd == 0 else float((clean.mean() - rf_daily) / sd * math.sqrt(252.0))


def cagr(returns: pd.Series) -> float:
    clean = _clean(returns)
    if len(clean) == 0:
        return float("nan")
    wealth = float(np.prod(1.0 + clean.to_numpy()))
    return float(wealth ** (252.0 / len(clean)) - 1.0) if wealth >= 0 else float("nan")
