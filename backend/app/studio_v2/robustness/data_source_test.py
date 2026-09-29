"""Cross-vendor robustness using aligned returns, signal agreement, and drift tests."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


class DataSourceRobustnessTest:
    @staticmethod
    def _sharpe(matrix: np.ndarray) -> np.ndarray:
        means = np.nanmean(matrix, axis=1)
        std = np.nanstd(matrix, axis=1, ddof=1)
        return np.divide(
            means, std,
            out=np.zeros_like(means, dtype=float),
            where=np.isfinite(std) & (std > 0),
        ) * np.sqrt(252.0)

    def perturb(self, returns: Any, noise_std: float = 0.001,
                simulations: int = 200, seed: int = 42,
                evaluate: Callable[[pd.Series], float] | None = None) -> dict[str, Any]:
        base = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if len(base) < 20:
            raise ValueError("at least 20 daily returns are required")
        count = int(simulations)
        if not 10 <= count <= 500:
            raise ValueError("simulations must be between 10 and 500")
        sigma = float(noise_std)
        if not 0 <= sigma <= 0.05:
            raise ValueError("noise_std must be between 0 and 0.05")
        rng = np.random.default_rng(seed)
        perturbed = base.to_numpy()[None, :] + rng.normal(0.0, sigma, (count, len(base)))
        if evaluate:
            sharpes = np.asarray([float(evaluate(pd.Series(row, index=base.index))) for row in perturbed])
            original = float(evaluate(base))
        else:
            sharpes = self._sharpe(perturbed)
            original = float(self._sharpe(base.to_numpy()[None, :])[0])
        finite = sharpes[np.isfinite(sharpes)]
        if not len(finite):
            raise ValueError("perturbation produced no finite Sharpe ratios")
        mean, standard_deviation = float(finite.mean()), float(finite.std(ddof=1))
        denominator = max(abs(mean), 1e-12)
        sensitivity = float(np.clip(1.0 - standard_deviation / denominator, 0.0, 1.0))
        percentiles = np.percentile(finite, [5, 25, 50, 75, 95])
        return {
            "method": "gaussian_return_perturbation",
            "noise_std": sigma,
            "simulations": count,
            "seed": int(seed),
            "original_sharpe": original,
            "mean_perturbed_sharpe": mean,
            "std_perturbed_sharpe": standard_deviation,
            "sensitivity_score": sensitivity,
            "percentiles": dict(zip(("p5", "p25", "p50", "p75", "p95"), map(float, percentiles))),
            "passed": bool(sensitivity >= 0.70),
        }

    def perturb_strategy(self, prices: Any, strategy_source: Any,
                         parameters: dict[str, Any] | None = None,
                         noise_std: float = 0.001, simulations: int = 200,
                         seed: int = 42) -> dict[str, Any]:
        from ..backtest.engine import _load_strategy
        from ..backtest.metrics import PerformanceMetrics
        close = pd.DataFrame(prices, dtype=float).replace([np.inf, -np.inf], np.nan)
        if len(close) < 20 or close.shape[1] < 1:
            raise ValueError("prices require at least 20 dates and one asset")
        count = int(simulations)
        if not 10 <= count <= 500:
            raise ValueError("simulations must be between 10 and 500")
        returns = close.pct_change(fill_method=None).fillna(0.0)
        strategy = _load_strategy(strategy_source)
        if strategy is None:
            raise ValueError("strategy_source is required")

        def strategy_returns(price_frame: pd.DataFrame) -> pd.Series:
            try:
                signals = strategy(price_frame.copy(), parameters or {})
            except TypeError:
                signals = strategy(price_frame.copy())
            positions = pd.DataFrame(signals).reindex_like(price_frame).fillna(0.0)
            return (positions.shift(1).fillna(0.0) * price_frame.pct_change(fill_method=None).fillna(0.0)).sum(axis=1)

        original_returns = strategy_returns(close)
        original_sharpe = PerformanceMetrics().compute_sharpe(original_returns)
        rng = np.random.default_rng(seed)
        sharpes = np.empty(count, dtype=float)
        base = returns.to_numpy()
        for index in range(count):
            noisy_returns = base + rng.normal(0.0, float(noise_std), base.shape)
            perturbed_prices = pd.DataFrame(
                close.iloc[0].to_numpy()[None, :] * np.cumprod(1.0 + noisy_returns, axis=0),
                index=close.index, columns=close.columns,
            )
            sharpes[index] = PerformanceMetrics().compute_sharpe(strategy_returns(perturbed_prices))
        finite = sharpes[np.isfinite(sharpes)]
        mean = float(finite.mean())
        standard_deviation = float(finite.std(ddof=1))
        percentiles = np.percentile(finite, [5, 25, 50, 75, 95])
        sensitivity = float(np.clip(1.0 - standard_deviation / max(abs(mean), 1e-12), 0, 1))
        return {
            "method": "strategy_gaussian_price_perturbation",
            "original_sharpe": float(original_sharpe),
            "mean_perturbed_sharpe": mean,
            "std_perturbed_sharpe": standard_deviation,
            "sensitivity_score": sensitivity,
            "percentiles": dict(zip(("p5", "p25", "p50", "p75", "p95"), map(float, percentiles))),
            "simulations": count, "noise_std": float(noise_std), "seed": int(seed),
            "passed": bool(sensitivity >= 0.70),
        }

    def run(self, sources: dict[str, Any], tolerance_bps: float = 10.0) -> dict[str, Any]:
        if len(sources) < 2:
            raise ValueError("at least two data sources are required")
        closes = {}
        for name, rows in sources.items():
            frame = pd.DataFrame(rows)
            if "date" in frame:
                frame = frame.set_index(pd.to_datetime(frame.pop("date")))
            series = frame["close"] if "close" in frame else frame.iloc[:, 0]
            closes[name] = pd.to_numeric(series, errors="coerce")
        matrix = pd.concat(closes, axis=1).dropna()
        if len(matrix) < 3:
            raise ValueError("sources have insufficient overlapping observations")
        returns = matrix.pct_change(fill_method=None).dropna()
        reference = returns.iloc[:, 0]
        comparisons = []
        for name in returns.columns[1:]:
            diff = returns[name] - reference
            drift_bps = float(diff.abs().mean() * 10_000)
            comparisons.append({
                "source": str(name),
                "correlation": float(reference.corr(returns[name])),
                "mean_absolute_drift_bps": drift_bps,
                "directional_agreement": float((np.sign(reference) == np.sign(returns[name])).mean()),
                "passed": drift_bps <= float(tolerance_bps),
            })
        return {
            "reference_source": str(returns.columns[0]),
            "overlap_observations": int(len(returns)),
            "comparisons": comparisons,
            "passed": all(row["passed"] for row in comparisons),
        }
