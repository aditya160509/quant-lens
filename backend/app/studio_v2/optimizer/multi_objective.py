"""Non-dominated sorting and Pareto frontier selection."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd


class ParetoOptimizer:
    _DIRECTIONS = {
        "max": "maximize", "maximize": "maximize",
        "min": "minimize", "minimize": "minimize",
    }
    _COMPLETE_STATES = {"complete", "completed", "success", "succeeded"}
    _TRIAL_METADATA = {
        "trial_id", "id", "number", "timestamp", "state", "status", "error",
        "failure_reason", "pareto_optimal", "valid_objectives", "duplicate_of",
    }

    @classmethod
    def _normalized_directions(cls, objectives: dict[str, str]) -> list[str]:
        if not objectives:
            raise ValueError("at least one objective is required")
        directions = []
        for name, direction in objectives.items():
            normalized = cls._DIRECTIONS.get(str(direction).strip().lower())
            if normalized is None:
                raise ValueError(
                    f"objective '{name}' direction must be min/minimize or max/maximize"
                )
            directions.append(normalized)
        return directions

    @classmethod
    def _state_name(cls, state: Any) -> str:
        normalized = str(getattr(state, "name", state)).strip().lower().rsplit(".", 1)[-1]
        return "failed" if normalized == "fail" else normalized

    @classmethod
    def _is_complete(cls, state: Any) -> bool:
        if state is None or (isinstance(state, float) and np.isnan(state)):
            return True
        return cls._state_name(state) in cls._COMPLETE_STATES

    @staticmethod
    def _signature(row: dict[str, Any], columns: list[str]) -> str:
        def encode(value: Any) -> Any:
            if isinstance(value, np.generic):
                return value.item()
            return value

        return json.dumps(
            {column: encode(row.get(column)) for column in columns},
            sort_keys=True, separators=(",", ":"), default=str,
        )

    def optimize(self, config: Any, objectives: dict[str, str]) -> dict[str, Any]:
        """Run a true multi-objective TPE study for explicitly requested jobs."""
        from .search import BayesianOptimizer, OptimizerConfig, SearchParameter
        from ..backtest.engine import EventDrivenEngine, SimulationConfig
        from ..backtest.metrics import PerformanceMetrics
        resolved = config if isinstance(config, OptimizerConfig) else OptimizerConfig(**config)
        resolved.parameters = [
            item if isinstance(item, SearchParameter) else SearchParameter(**item)
            for item in resolved.parameters
        ]
        parameters = [item for item in resolved.parameters if item.included]
        if not parameters or not objectives:
            raise ValueError("parameters and objectives are required")
        try:
            import optuna
        except ImportError as exc:
            raise RuntimeError("Optuna is required for multi-objective optimization") from exc
        directions = self._normalized_directions(objectives)
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(directions=directions, sampler=sampler)
        suggester = BayesianOptimizer()

        def objective(trial: Any) -> tuple[float, ...]:
            params = {parameter.name: suggester._suggest(trial, parameter) for parameter in parameters}
            try:
                if callable(resolved.evaluate):
                    evaluated = resolved.evaluate(params)
                    metrics = dict(evaluated) if isinstance(evaluated, dict) else {next(iter(objectives)): evaluated}
                else:
                    base = dict(resolved.backtest_config or {})
                    source = resolved.strategy_file or base.pop("strategy_source", None)
                    result = EventDrivenEngine().run(SimulationConfig(
                        **{**base, "strategy_source": source,
                           "parameters": {**base.get("parameters", {}), **params}}
                    ))
                    metrics = PerformanceMetrics().compute_all(result.daily_returns).to_dict()
                values = tuple(float(metrics.get(name, np.nan)) for name in objectives)
                if not all(np.isfinite(value) for value in values):
                    raise ValueError("all objective values must be finite")
                return values
            except Exception as exc:
                trial.set_user_attr("failure_reason", f"{type(exc).__name__}: {exc}"[:2_000])
                raise

        study.optimize(objective, n_trials=max(1, int(resolved.trial_budget)),
                       n_jobs=max(1, int(resolved.n_jobs)), show_progress_bar=False,
                       catch=(Exception,))
        rows = []
        for trial in study.trials:
            values = list(trial.values or [])
            rows.append({
                "trial_id": int(trial.number), **trial.params,
                **{
                    name: float(values[index]) if index < len(values) and np.isfinite(values[index]) else None
                    for index, name in enumerate(objectives)
                },
                "state": self._state_name(trial.state),
                "failure_reason": trial.user_attrs.get("failure_reason"),
            })
        output = self.frontier(rows, objectives)
        output["method"] = "optuna_multi_objective_tpe"
        return output

    @staticmethod
    def _hypervolume(values: np.ndarray, signs: np.ndarray) -> float:
        """Return normalized dominated area for two objectives."""
        if values.ndim != 2 or values.shape[1] != 2:
            return float("nan")
        if not len(values):
            return 0.0
        utility = values * signs
        finite = np.all(np.isfinite(utility), axis=1)
        utility = utility[finite]
        if not len(utility):
            return 0.0
        low, high = utility.min(axis=0), utility.max(axis=0)
        span = np.where(high > low, high - low, 1.0)
        points = (utility - low) / span
        points = points[np.argsort(-points[:, 0])]
        area, best_y = 0.0, 0.0
        for index, (x, y) in enumerate(points):
            best_y = max(best_y, float(y))
            next_x = float(points[index + 1, 0]) if index + 1 < len(points) else 0.0
            area += max(0.0, float(x) - next_x) * best_y
        return float(np.clip(area, 0.0, 1.0))

    def _hypervolume_progression(self, values: np.ndarray, signs: np.ndarray) -> list[dict[str, float]]:
        if values.shape[1] != 2:
            return []
        return [
            {"trial": index, "hypervolume": self._hypervolume(values[:index], signs)}
            for index in range(1, len(values) + 1)
        ]

    def frontier(self, trials: Any, objectives: dict[str, str]) -> dict[str, Any]:
        frame = pd.DataFrame(trials).reset_index(drop=True)
        directions = self._normalized_directions(objectives)
        objective_names = list(objectives)
        signs = np.array([1.0 if direction == "maximize" else -1.0 for direction in directions])
        for name in objective_names:
            if name not in frame:
                frame[name] = np.nan
        values = frame[objective_names].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        finite_objectives = np.all(np.isfinite(values), axis=1)
        complete = np.array([
            self._is_complete(value) for value in (
                frame["state"] if "state" in frame else [None] * len(frame)
            )
        ], dtype=bool)
        candidate = finite_objectives & complete

        frame["valid_objectives"] = finite_objectives
        frame["pareto_optimal"] = False
        frame["duplicate_of"] = None
        parameter_columns = [
            column for column in frame.columns
            if column not in self._TRIAL_METADATA and column not in objective_names
        ]
        signature_columns = parameter_columns or objective_names
        seen: dict[str, Any] = {}
        eligible_indices = []
        for index in np.flatnonzero(candidate):
            row = frame.iloc[int(index)].to_dict()
            signature = self._signature(row, signature_columns)
            identifier = row.get("trial_id", row.get("id", int(index)))
            if signature in seen:
                frame.at[int(index), "duplicate_of"] = seen[signature]
                continue
            seen[signature] = identifier
            eligible_indices.append(int(index))

        eligible_values = values[eligible_indices] if eligible_indices else np.empty((0, len(objective_names)))
        utility = eligible_values * signs
        dominated = np.zeros(len(eligible_indices), dtype=bool)
        for index in range(len(eligible_indices)):
            better = np.all(utility >= utility[index], axis=1)
            strictly_better = np.any(utility > utility[index], axis=1)
            dominated[index] = bool(np.any(better & strictly_better))
        frontier_indices = [
            eligible_indices[index] for index in np.flatnonzero(~dominated)
        ]
        if frontier_indices:
            frame.loc[frontier_indices, "pareto_optimal"] = True

        return {
            "frontier": frame.loc[frontier_indices].to_dict(orient="records"),
            "trials": frame.to_dict(orient="records"),
            "objectives": objectives,
            "frontier_size": len(frontier_indices),
            "eligible_trial_count": len(eligible_indices),
            "duplicate_trial_count": int(candidate.sum()) - len(eligible_indices),
            "failed_trial_count": int((~complete).sum()),
            "invalid_objective_count": int((~finite_objectives).sum()),
            "hypervolume": self._hypervolume(eligible_values, signs) if len(objectives) == 2 else None,
            "hypervolume_progression": self._hypervolume_progression(eligible_values, signs),
        }
