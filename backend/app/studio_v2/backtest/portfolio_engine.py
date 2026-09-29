"""Portfolio-level backtesting with strategy aggregation and contribution math."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .engine import EventDrivenEngine, SimulationConfig
from .metrics import PerformanceMetrics
from .repository import BacktestResultRepository
from ..algorithm_lab.portfolio_composer import PortfolioComposer
from ..algorithm_lab.repository import StrategyRepository


class PortfolioBacktestEngine:
    def __init__(self, repository: BacktestResultRepository | None = None,
                 composer: PortfolioComposer | None = None,
                 strategies: StrategyRepository | None = None) -> None:
        self.repository = repository or BacktestResultRepository()
        self.strategies = strategies or StrategyRepository()
        self.composer = composer or PortfolioComposer(strategies=self.strategies)

    @staticmethod
    def _weights(count: int, scheme: str, custom: Any, returns: pd.DataFrame) -> np.ndarray:
        if count < 2 or count > 10:
            raise ValueError("portfolio backtest requires 2 to 10 strategies")
        if scheme == "custom":
            values = np.asarray(custom, dtype=float)
            if values.size != count or not np.all(np.isfinite(values)):
                raise ValueError("custom weights must contain one finite value per strategy")
        elif scheme == "risk_parity":
            vol = returns.std(ddof=1).replace(0, np.nan).to_numpy(float)
            values = np.nan_to_num(1.0 / vol, nan=0.0, posinf=0.0)
        else:
            values = np.ones(count)
        gross = np.abs(values).sum()
        if gross <= 0:
            raise ValueError("portfolio weights cannot sum to zero")
        return values / gross

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        composition_id = payload.get("composition_id")
        composition = self.composer.get(str(composition_id)) if composition_id else None
        if composition:
            overrides = payload.get("strategy_configs", {})
            if isinstance(overrides, list):
                overrides = {
                    str(row.get("strategy_id")): row for row in overrides if row.get("strategy_id")
                }
            strategies = []
            for strategy_id in composition["strategy_ids"]:
                record = self.strategies.get(strategy_id)
                strategies.append({
                    "strategy_id": strategy_id,
                    "name": record["name"],
                    "strategy_source": record["file_path"],
                    "parameters": {
                        **record.get("default_config", {}),
                        **dict(overrides.get(strategy_id, {})).get("parameters", {}),
                    },
                })
            payload = {
                **payload,
                "weight_scheme": (
                    composition["weight_scheme"]
                    if composition["weight_scheme"] != "custom" or composition.get("custom_weights")
                    else "equal_weight"
                ),
                "weights": [
                    (composition.get("custom_weights") or {}).get(strategy_id, 0.0)
                    for strategy_id in composition["strategy_ids"]
                ],
            }
        else:
            strategies = payload.get("strategies") or payload.get("strategy_configs") or []
        results, names = [], []
        for index, strategy in enumerate(strategies):
            item = dict(strategy)
            names.append(str(item.pop("name", item.get("strategy_id", f"strategy_{index}"))))
            item.pop("strategy_id", None)
            config = SimulationConfig(**{**payload.get("shared_config", {}), **item})
            results.append(EventDrivenEngine().run(config))
        aligned = pd.concat(
            [result.daily_returns.rename(name) for name, result in zip(names, results)],
            axis=1,
        ).fillna(0.0)
        weights = self._weights(
            len(results),
            str(payload.get("weight_scheme", "equal_weight")).lower(),
            payload.get("weights", []),
            aligned,
        )
        portfolio_returns = aligned.mul(weights, axis=1).sum(axis=1)
        initial = float(payload.get("initial_cash", 1_000_000.0))
        equity = initial * (1.0 + portfolio_returns).cumprod()
        contributions = aligned.mul(weights, axis=1)
        correlation = aligned.corr(min_periods=2).fillna(0.0)
        redundancy_flags = []
        for left_index, left in enumerate(names):
            for right in names[left_index + 1:]:
                value = float(correlation.loc[left, right])
                if abs(value) > float(payload.get("redundancy_threshold", 0.7)):
                    redundancy_flags.append({
                        "strategy_a": left, "strategy_b": right,
                        "correlation": value,
                        "threshold": float(payload.get("redundancy_threshold", 0.7)),
                    })
        combined_metrics = asdict(PerformanceMetrics().compute_all(portfolio_returns))
        per_strategy = []
        for name, result in zip(names, results):
            metrics = asdict(PerformanceMetrics().compute_all(result.daily_returns))
            per_strategy.append({
                "name": name,
                "metrics": metrics,
                "sharpe": metrics.get("sharpe"),
                "equity_curve": initial * (1.0 + result.daily_returns).cumprod(),
                "daily_returns": result.daily_returns,
            })
        run_id = str(uuid.uuid4())
        output = {
            "run_id": run_id,
            "composition_id": composition_id,
            "strategy_names": names,
            "weights": dict(zip(names, weights.tolist())),
            "daily_returns": portfolio_returns,
            "equity_curve": equity,
            "strategy_returns": aligned,
            "return_contributions": contributions,
            "metrics": combined_metrics,
            "individual_results": [result.to_dict() for result in results],
            "combined": {
                "equity_curve": equity,
                "daily_returns": portfolio_returns,
                **combined_metrics,
            },
            "per_strategy": per_strategy,
            "correlation_matrix": correlation,
            "redundancy_flags": redundancy_flags,
        }
        self.repository.save(run_id, output, kind="portfolio")
        return output

    def get_result(self, run_id: str) -> dict[str, Any]:
        return self.repository.get(run_id)
