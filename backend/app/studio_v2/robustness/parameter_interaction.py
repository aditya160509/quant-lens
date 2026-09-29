"""Parameter interaction diagnostics based on factorial response surfaces."""

from __future__ import annotations

import itertools
from typing import Any, Callable

import numpy as np
import pandas as pd


class ParameterInteractionTest:
    @staticmethod
    def auto_grid(parameters: dict[str, Any], points: int = 11) -> dict[str, list[float]]:
        if len(parameters) != 2:
            raise ValueError("exactly two parameter definitions are required")
        grid = {}
        for name, specification in parameters.items():
            if isinstance(specification, dict):
                low, high = float(specification["min"]), float(specification["max"])
            elif isinstance(specification, (list, tuple)) and len(specification) == 2:
                low, high = map(float, specification)
            else:
                center = float(specification)
                spread = max(abs(center) * 0.5, 1.0)
                low, high = center - spread, center + spread
            if high <= low:
                raise ValueError(f"parameter '{name}' max must exceed min")
            grid[name] = np.linspace(low, high, max(3, int(points))).tolist()
        return grid

    def run(self, parameter_grid: dict[str, list], evaluate: Callable[[dict], float] | None = None,
            observations: Any = None) -> dict[str, Any]:
        names = list(parameter_grid)
        if len(names) < 2:
            raise ValueError("at least two parameters are required")
        if observations is None:
            combinations = [dict(zip(names, values)) for values in itertools.product(*(parameter_grid[n] for n in names))]
            if evaluate is None:
                raise ValueError("evaluate callback or observations is required")
            frame = pd.DataFrame([{**params, "objective": float(evaluate(params))} for params in combinations])
        else:
            frame = pd.DataFrame(observations)
        if "objective" not in frame and "sharpe" in frame:
            frame = frame.rename(columns={"sharpe": "objective"})
        if "objective" not in frame:
            raise ValueError("observations must contain Sharpe in objective or sharpe")
        interactions = []
        marginal_stability = {}
        total_variance = float(frame.objective.var(ddof=0))
        for name in names:
            conditional = frame.groupby(name, observed=True)["objective"].var(ddof=0)
            marginal_variance = float(conditional.mean()) if len(conditional) else 0.0
            marginal_stability[name] = float(np.clip(1.0 - marginal_variance / total_variance, 0.0, 1.0)) if total_variance > 0 else 1.0
        for left, right in itertools.combinations(names, 2):
            surface = frame.pivot_table(index=left, columns=right, values="objective", aggfunc="mean")
            additive = surface.mean(axis=1).to_numpy()[:, None] + surface.mean(axis=0).to_numpy()[None, :] - surface.to_numpy().mean()
            residual = surface.to_numpy() - additive
            strength = float(np.nanvar(residual) / total_variance) if total_variance > 0 else 0.0
            interactions.append({"parameters": [left, right], "strength": strength, "surface": surface.to_dict()})
        interactions.sort(key=lambda row: row["strength"], reverse=True)
        maximum = interactions[0]["strength"] if interactions else 0.0
        verdict = "independent" if maximum < 0.1 else ("interaction" if maximum <= 0.5 else "strong")
        return {"interactions": interactions, "observations": int(len(frame)),
                "max_interaction": interactions[0] if interactions else None,
                "marginal_stability": marginal_stability, "verdict": verdict,
                "objective": "sharpe"}

    def run_backtests(self, parameter_ranges: dict[str, Any],
                      backtest_config: dict[str, Any]) -> dict[str, Any]:
        from ..backtest.engine import EventDrivenEngine, SimulationConfig
        from ..backtest.metrics import PerformanceMetrics
        grid = self.auto_grid(parameter_ranges, 11)
        names = list(grid)
        observations = []
        for values in itertools.product(*(grid[name] for name in names)):
            parameters = dict(zip(names, values))
            config = SimulationConfig(**{
                **backtest_config,
                "parameters": {**backtest_config.get("parameters", {}), **parameters},
            })
            result = EventDrivenEngine().run(config)
            metrics = PerformanceMetrics().compute_all(result.daily_returns).to_dict()
            observations.append({**parameters, "objective": metrics.get("sharpe")})
        return self.run(grid, observations=observations)
