"""Historical and parametric VaR/CVaR."""

from __future__ import annotations

from statistics import NormalDist
from typing import Any, Callable

import numpy as np
import pandas as pd


class VaREngine:
    MIN_OBSERVATIONS = 20

    def __init__(self, strategy_provider: Callable[[], list[Any]] | None = None) -> None:
        self.strategy_provider = strategy_provider

    def compute(self, returns: Any, weights: Any = None, confidence: float = 0.99,
                horizon_days: int = 1, portfolio_value: float = 1.0) -> dict[str, Any]:
        frame = pd.DataFrame(returns, dtype=float).replace([np.inf, -np.inf], np.nan)
        if frame.empty:
            raise ValueError("return observations are required")
        input_observations = len(frame)
        frame = frame.dropna(axis=0, how="any")
        if len(frame) < self.MIN_OBSERVATIONS:
            raise ValueError(
                f"at least {self.MIN_OBSERVATIONS} aligned return observations are required"
            )
        if not 0.5 < float(confidence) < 1.0:
            raise ValueError("confidence must be between 0.5 and 1")
        if not 1 <= int(horizon_days) <= 252:
            raise ValueError("horizon_days must be between 1 and 252")
        if not np.isfinite(portfolio_value) or float(portfolio_value) <= 0:
            raise ValueError("portfolio_value must be finite and positive")
        vector = np.asarray(weights if weights is not None else np.ones(frame.shape[1]), dtype=float)
        if vector.size != frame.shape[1]:
            raise ValueError("weights length does not match return columns")
        if not np.isfinite(vector).all():
            raise ValueError("weights must be finite")
        gross_weight = float(np.abs(vector).sum())
        if gross_weight <= 0:
            raise ValueError("weights must have positive gross exposure")
        vector /= gross_weight
        portfolio = frame.to_numpy() @ vector
        alpha = 1.0 - float(confidence)
        historical_cutoff = float(np.quantile(portfolio, alpha))
        tail = portfolio[portfolio <= historical_cutoff]
        mean, sigma = float(np.mean(portfolio)), float(np.std(portfolio, ddof=1))
        z = NormalDist().inv_cdf(alpha)
        scale = np.sqrt(max(1, int(horizon_days)))
        hist_var = max(0.0, -historical_cutoff * scale * portfolio_value)
        hist_cvar = max(0.0, -float(tail.mean() if tail.size else historical_cutoff) * scale * portfolio_value)
        parametric = max(0.0, -(mean * horizon_days + z * sigma * scale) * portfolio_value)
        return {"confidence": confidence, "horizon_days": horizon_days, "historical_var": hist_var,
                "historical_cvar": hist_cvar, "parametric_var": parametric,
                "portfolio_value": float(portfolio_value), "observations": int(len(portfolio)),
                "input_observations": input_observations,
                "observations_dropped": input_observations - len(portfolio),
                "alignment": "inner",
                "weights": dict(zip(map(str, frame.columns), map(float, vector))),
                "constant_returns": bool(sigma <= np.finfo(float).eps)}

    def compute_from_active_strategies(self, strategies: list[Any] | None = None,
                                       portfolio_value: float = 1.0) -> dict[str, Any]:
        records = strategies if strategies is not None else (
            self.strategy_provider() if self.strategy_provider else []
        )
        series, weights = {}, []
        for index, record in enumerate(records):
            value = record.to_dict() if hasattr(record, "to_dict") else dict(record)
            metrics = value.get("metrics", {})
            observations = metrics.get("daily_returns", value.get("daily_returns"))
            if observations is None:
                continue
            name = str(value.get("run_id", value.get("strategy_id", f"strategy_{index}")))
            series[name] = pd.Series(observations, dtype=float)
            weights.append(float(value.get("weight", value.get("parameters", {}).get("portfolio_weight", 1.0))))
        if not series:
            raise ValueError("active strategies contain no daily return series")
        frame = pd.DataFrame(series)
        combinations = {}
        for confidence in (0.95, 0.99):
            for horizon in (1, 10):
                key = f"{int(confidence * 100)}pct_{horizon}d"
                combinations[key] = self.compute(frame, weights, confidence, horizon, portfolio_value)
        return {
            "strategy_ids": list(series),
            "weights": dict(zip(series, (np.asarray(weights) / np.abs(weights).sum()).tolist())),
            "history_alignment": "inner",
            "input_history_lengths": {key: int(value.notna().sum()) for key, value in series.items()},
            "combinations": combinations,
            "primary": combinations["99pct_1d"],
        }
