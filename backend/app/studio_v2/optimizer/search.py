from __future__ import annotations

"""
Parameter search (F5.2-F5.3).

Bayesian search via Optuna TPE with Sharpe-per-Capacity-Dollar objective.
Walk-forward optimization with regime-conditional IS/OOS ratio.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class SearchParameter:
    name: str
    type: str = "continuous"
    current_value: Any = None
    suggested_range: Optional[Tuple[float, float]] = None
    values: Optional[List[Any]] = None
    included: bool = True


@dataclass
class OptimizerConfig:
    strategy_file: Any = None
    backtest_config: Any = None
    parameters: List[SearchParameter] = field(default_factory=list)
    trial_budget: int = 50
    objective: str = "sharpe"
    capacity_data: Any = None
    evaluate: Any = None
    session_id: str = "default"
    n_jobs: int = 1


@dataclass
class OptimizerResult:
    trials: pd.DataFrame
    best_params: dict
    best_value: float
    perturbation_results: pd.DataFrame
    stability_score: float
    trajectory: List[dict]


@dataclass
class Window:
    index: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp


@dataclass
class ISResult:
    best_params: dict
    sharpe: float
    trials: pd.DataFrame


@dataclass
class OOSResult:
    returns: pd.Series
    sharpe: float


@dataclass
class WalkForwardConfig:
    is_months: int = 24
    oos_months: int = 3
    mode: str = "rolling"
    objective: str = "sharpe"
    trials_per_window: int = 50
    strategy_file: Any = None
    backtest_config: Any = None
    parameters: List[SearchParameter] = field(default_factory=list)
    date_range: Optional[Tuple[Any, Any]] = None
    evaluate: Any = None


@dataclass
class WalkForwardResult:
    windows: pd.DataFrame
    stitched_oos_curve: pd.Series
    mean_isoos_ratio: float
    confidence_interval: tuple
    regime_conditional: pd.DataFrame


def _two_sig(value: float) -> float:
    if value == 0: return 0.0
    digits = 2 - int(math.floor(math.log10(abs(value)))) - 1
    return round(value, max(0, digits))


def infer_parameter_range(current_value: Any) -> Tuple[float, float]:
    value = float(current_value); return (_two_sig(value * 0.5), _two_sig(value * 1.5))


class BayesianOptimizer:
    _COMPLETE_STATES = {"complete", "completed", "success", "succeeded"}

    @staticmethod
    def _state_name(state: Any) -> str:
        normalized = str(getattr(state, "name", state)).strip().lower().rsplit(".", 1)[-1]
        return "failed" if normalized == "fail" else normalized

    def _sample(self, parameter: SearchParameter, rng: np.random.Generator) -> Any:
        if parameter.type == "categorical": return (parameter.values or [parameter.current_value])[int(rng.integers(0, len(parameter.values or [parameter.current_value])))]
        if parameter.type == "discrete": return int(rng.choice(parameter.values or [parameter.current_value]))
        low, high = parameter.suggested_range or infer_parameter_range(parameter.current_value); return float(rng.uniform(low, high))

    def _suggest(self, trial: Any, parameter: SearchParameter) -> Any:
        kind = str(parameter.type).lower()
        if kind == "categorical": return trial.suggest_categorical(parameter.name, parameter.values or [parameter.current_value])
        if kind == "discrete":
            values = parameter.values or [parameter.current_value]
            return trial.suggest_categorical(parameter.name, [int(value) for value in values])
        low, high = parameter.suggested_range or infer_parameter_range(parameter.current_value)
        return trial.suggest_float(parameter.name, float(low), float(high), log=bool(low > 0 and high / max(low, 1e-12) >= 10))

    def _objective(self, trial: dict, config: OptimizerConfig) -> float:
        callback = config.evaluate or (config.backtest_config.get("evaluate") if isinstance(config.backtest_config, dict) else None)
        if callable(callback):
            value = callback(trial)
            if isinstance(value, dict):
                raw = value.get(config.objective, value.get("sharpe", np.nan)); capacity = value.get("capacity_ceiling", 0.0)
                return float(raw * capacity / 1e9) if config.objective == "sharpe_per_capacity_dollar" else float(raw)
            return float(value) if np.isscalar(value) else float(np.nanmean(value))
        if config.strategy_file or isinstance(config.backtest_config, dict):
            from ..backtest.engine import EventDrivenEngine, SimulationConfig
            from ..backtest.metrics import PerformanceMetrics
            base = dict(config.backtest_config or {})
            source = config.strategy_file or base.pop("strategy_source", None)
            result = EventDrivenEngine().run(SimulationConfig(
                **{**base, "strategy_source": source,
                   "parameters": {**base.get("parameters", {}), **trial}}
            ))
            metrics = PerformanceMetrics().compute_all(result.daily_returns).to_dict()
            raw = metrics.get(config.objective, metrics.get("sharpe", np.nan))
            return float(raw)
        return float("nan")

    def _compute_capacity_ceiling(self, trade_log: Any, params: dict) -> float:
        if trade_log is None: return 0.0
        if isinstance(trade_log, dict): return float(trade_log.get("capacity_ceiling", 0.0))
        return float(getattr(trade_log, "capacity_ceiling", 0.0))

    def _compute_sharpe_per_capacity_dollar(self, params: dict) -> float:
        return float(params.get("sharpe", 0.0) * params.get("capacity_ceiling", 0.0) / 1e9)

    def _trajectory_callback(self, study: Any, trial: Any) -> None:
        if not hasattr(self, "_trajectory"):
            self._trajectory = []
        self._trajectory.append({
            "trial": int(trial.number),
            "value": float(trial.value) if trial.value is not None and np.isfinite(trial.value) else None,
            "params": dict(trial.params),
            "state": self._state_name(trial.state),
            "failure_reason": trial.user_attrs.get("failure_reason"),
        })

    def run_perturbation_grid(self, optimal_params: dict, pct: float = 0.30, n_steps: int = 5) -> pd.DataFrame:
        keys = list(optimal_params); numeric_keys = [key for key in keys if np.isscalar(optimal_params[key]) and not isinstance(optimal_params[key], bool)]
        if not numeric_keys: return pd.DataFrame([optimal_params])
        grids = [np.linspace(float(optimal_params[key]) * (1 - pct), float(optimal_params[key]) * (1 + pct), n_steps) for key in numeric_keys]
        mesh = np.meshgrid(*grids, indexing="ij")
        rows = {key: values.reshape(-1) for key, values in zip(numeric_keys, mesh)}
        result = pd.DataFrame(rows)
        for key, value in optimal_params.items():
            if key not in result: result[key] = value
        return result[keys]

    def compute_stability_score(self, perturbation_results: pd.DataFrame, optimal_sharpe: float) -> float:
        if perturbation_results.empty or "sharpe" not in perturbation_results or not np.isfinite(optimal_sharpe): return 0.0
        return float((pd.to_numeric(perturbation_results["sharpe"], errors="coerce") > 0.5 * optimal_sharpe).mean())

    def run(self, config: OptimizerConfig) -> OptimizerResult:
        if isinstance(config, dict): config = OptimizerConfig(**config); config.parameters = [SearchParameter(**p) if isinstance(p, dict) else p for p in config.parameters]
        config.parameters = [SearchParameter(**parameter) if isinstance(parameter, dict) else parameter for parameter in config.parameters]
        parameters = [parameter for parameter in config.parameters if parameter.included]
        if not parameters: raise ValueError("No parameters toggled on")
        try:
            import optuna
        except ImportError as exc:
            raise RuntimeError("Optuna is required for Bayesian TPE optimization") from exc
        self._trajectory = []
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        def objective(trial: Any) -> float:
            params = {parameter.name: self._suggest(trial, parameter) for parameter in parameters}
            try:
                value = self._objective(params, config)
                if not np.isfinite(value):
                    raise ValueError("objective value must be finite")
                return float(value)
            except Exception as exc:
                trial.set_user_attr("failure_reason", f"{type(exc).__name__}: {exc}"[:2_000])
                raise
        study.optimize(
            objective,
            n_trials=max(1, int(config.trial_budget)),
            callbacks=[self._trajectory_callback],
            show_progress_bar=False,
            n_jobs=max(1, int(config.n_jobs)),
            catch=(Exception,),
        )
        rows = [{
            "trial_id": int(trial.number), **trial.params,
            "objective": (
                float(trial.value)
                if trial.value is not None and np.isfinite(trial.value) else None
            ),
            "timestamp": datetime.utcnow().isoformat(),
            "state": self._state_name(trial.state),
            "failure_reason": trial.user_attrs.get("failure_reason"),
        } for trial in study.trials]
        trajectory = list(self._trajectory)
        trials = pd.DataFrame(rows)
        valid = trials.loc[
            np.isfinite(pd.to_numeric(trials["objective"], errors="coerce"))
            & trials["state"].isin(self._COMPLETE_STATES)
        ] if not trials.empty else trials
        if valid.empty: best_params, best_value = {}, float("nan")
        else: best = valid.iloc[int(valid["objective"].argmax())]; best_params = {parameter.name: best[parameter.name] for parameter in parameters}; best_value = float(best["objective"])
        perturb = self.run_perturbation_grid(best_params) if best_params else pd.DataFrame()
        callback = config.evaluate
        if callable(callback) and not perturb.empty: perturb["sharpe"] = [float(callback(row)) for row in perturb.to_dict(orient="records")]
        return OptimizerResult(trials, best_params, best_value, perturb, self.compute_stability_score(perturb, best_value), trajectory)


class WalkForwardOptimizer:
    def generate_windows(self, is_months: int, oos_months: int, mode: str, date_range: Tuple[Any, Any]) -> List[Window]:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]); cursor, index, windows = start + pd.DateOffset(months=is_months), 0, []
        while cursor < end:
            is_start = start if str(mode).lower() == "anchored" else cursor - pd.DateOffset(months=is_months); oos_end = min(cursor + pd.DateOffset(months=oos_months), end); windows.append(Window(index, is_start, cursor - pd.Timedelta(days=1), cursor, oos_end)); index += 1; cursor = oos_end; 
        return windows

    def run_is_search(self, is_start: Any, is_end: Any, config: WalkForwardConfig) -> ISResult:
        optimizer = BayesianOptimizer(); search_config = OptimizerConfig(config.strategy_file, config.backtest_config, config.parameters, config.trials_per_window, config.objective, evaluate=config.evaluate); result = optimizer.run(search_config); return ISResult(result.best_params, result.best_value, result.trials)

    def evaluate_oos(self, oos_start: Any, oos_end: Any, optimal_params: dict, config: WalkForwardConfig) -> OOSResult:
        if callable(config.evaluate):
            value = config.evaluate({**optimal_params, "start": oos_start, "end": oos_end}); returns = pd.Series(value if not np.isscalar(value) else [value], dtype=float)
        else: returns = pd.Series(dtype=float)
        return OOSResult(returns, float(np.nanmean(returns)) if len(returns) == 1 else (float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252)) if len(returns) > 1 and np.std(returns, ddof=1) else 0.0))

    def compute_stitched_oos_curve(self, windows: Sequence[Any]) -> pd.Series:
        series = [window.oos_returns if hasattr(window, "oos_returns") else window.get("oos_returns", pd.Series(dtype=float)) for window in windows]; return pd.concat(series) if series else pd.Series(dtype=float)

    def compute_mean_isoos_ratio(self, windows: Sequence[Any]) -> tuple:
        ratios = []
        for window in windows:
            is_sharpe, oos_sharpe = (window["is_sharpe"], window["oos_sharpe"]) if isinstance(window, dict) else (window.is_sharpe, window.oos_sharpe)
            if np.isfinite(is_sharpe) and is_sharpe != 0: ratios.append(oos_sharpe / is_sharpe)
        if not ratios: return float("nan"), (float("nan"), float("nan"))
        rng = np.random.default_rng(42); means = [np.mean(rng.choice(ratios, len(ratios), replace=True)) for _ in range(1000)]; return float(np.mean(ratios)), (float(np.percentile(means, 5)), float(np.percentile(means, 95)))

    def compute_regime_conditional_isoos(self, windows: Sequence[Any]) -> pd.DataFrame:
        frame = pd.DataFrame(windows)
        if frame.empty: return frame
        regime_column = next((column for column in ("regime", "market_regime", "state") if column in frame.columns), None)
        if regime_column is None: return frame
        return frame.groupby(regime_column, dropna=False).agg(windows=("ratio", "size"), mean_isoos_ratio=("ratio", "mean"), median_oos_sharpe=("oos_sharpe", "median")).reset_index()

    def run(self, config: WalkForwardConfig) -> WalkForwardResult:
        if isinstance(config, dict): config = WalkForwardConfig(**config)
        if not config.date_range: raise ValueError("Walk-forward date_range is required")
        windows = self.generate_windows(config.is_months, config.oos_months, config.mode, config.date_range); rows, curves = [], []
        for window in windows:
            is_result = self.run_is_search(window.is_start, window.is_end, config); oos = self.evaluate_oos(window.oos_start, window.oos_end, is_result.best_params, config); rows.append({"window": window.index, "is_start": window.is_start, "is_end": window.is_end, "oos_start": window.oos_start, "oos_end": window.oos_end, "optimal_params": is_result.best_params, "is_sharpe": is_result.sharpe, "oos_sharpe": oos.sharpe, "ratio": oos.sharpe / is_result.sharpe if is_result.sharpe else np.nan}); curves.append(oos.returns)
        frame = pd.DataFrame(rows); mean, interval = self.compute_mean_isoos_ratio(frame.to_dict(orient="records")); return WalkForwardResult(frame, pd.concat(curves) if curves else pd.Series(dtype=float), mean, interval, self.compute_regime_conditional_isoos(rows))
