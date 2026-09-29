"""Bounded real-backtest CPCV and walk-forward integration."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from ..algorithm_lab.repository import StrategyRepository
from ..backtest.engine import EventDrivenEngine, SimulationConfig, SimulationResult
from ..backtest.metrics import PerformanceMetrics
from ..shared.data_loader import get_trading_sessions


class TemporalValidationService:
    """Run temporal validation with strict local compute and data bounds."""

    MAX_CPCV_PATHS = 28
    MAX_CANDIDATES = 6
    MAX_WINDOWS = 8
    MAX_SESSIONS = 756
    MIN_SESSIONS = 60
    MAX_STRATEGY_BYTES = 1_000_000

    def __init__(
        self,
        strategies: Optional[StrategyRepository] = None,
        *,
        engine_factory: Callable[[], EventDrivenEngine] = EventDrivenEngine,
        sessions_loader: Callable[[], pd.DatetimeIndex] = get_trading_sessions,
    ) -> None:
        self.strategies = strategies or StrategyRepository()
        self.engine_factory = engine_factory
        self.sessions_loader = sessions_loader
        self.metrics = PerformanceMetrics()

    def run_cpcv(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        source, strategy_id, strategy_hash = self._resolve_strategy(payload)
        config, sessions = self._resolve_backtest(payload["backtest_config"], source)
        n_groups = int(payload.get("n_groups") or payload.get("n_splits") or 6)
        k_test = int(payload.get("k_test", 2))
        splits = list(itertools.combinations(range(n_groups), k_test))
        if len(splits) > self.MAX_CPCV_PATHS:
            raise ValueError(f"CPCV is capped at {self.MAX_CPCV_PATHS} paths")
        if len(sessions) < n_groups * 10:
            raise ValueError(
                f"CPCV requires at least {n_groups * 10} master-universe sessions "
                f"for {n_groups} groups"
            )

        simulation = self._run_backtest(config)
        returns = self._validated_returns(simulation, sessions)
        if len(returns) < n_groups * 10:
            raise ValueError("the backtest produced too few aligned sessions for CPCV")
        groups = [np.asarray(group, dtype=int) for group in np.array_split(np.arange(len(returns)), n_groups)]
        purge_days = int(payload.get("purge_days", 21))
        embargo_days = int(payload.get("embargo_days", 10))

        rows: list[dict[str, Any]] = []
        path_returns: list[pd.Series] = []
        for path_index, split in enumerate(splits):
            test_indices = np.sort(np.concatenate([groups[index] for index in split]))
            train_indices = self._purged_train_indices(
                len(returns), test_indices, purge_days, embargo_days
            )
            values = returns.iloc[test_indices]
            path_returns.append(values.reset_index(drop=True))
            sharpe = self._finite(self.metrics.compute_sharpe(values), default=0.0)
            total_return = self._finite(float((1.0 + values).prod() - 1.0), default=0.0)
            rows.append({
                "path": path_index,
                "test_groups": list(split),
                "test_start": self._date_string(values.index.min()),
                "test_end": self._date_string(values.index.max()),
                "observations": int(len(values)),
                "train_observations": int(len(train_indices)),
                "sharpe": sharpe,
                "total_return": total_return,
                "positive": bool(sharpe > 0.0),
            })

        path_sharpes = np.asarray([row["sharpe"] for row in rows], dtype=float)
        mean_sharpe = float(path_sharpes.mean())
        dsr = self._optional_finite(
            self.metrics.compute_dsr(returns, mean_sharpe, int(payload.get("m_trials", 1)))
        )
        embargo_sensitivity = []
        for embargo in payload.get("embargo_lengths", [0, 5, 10, 21]):
            counts = [
                len(self._purged_train_indices(
                    len(returns),
                    np.sort(np.concatenate([groups[index] for index in split])),
                    purge_days,
                    int(embargo),
                ))
                for split in splits
            ]
            embargo_sensitivity.append({
                "embargo_days": int(embargo),
                "mean_train_observations": float(np.mean(counts)),
                "min_train_observations": int(min(counts)),
            })

        return {
            "mode": "cpcv",
            "method": "fixed_parameter_combinatorial_purged_cv",
            "strategy_id": strategy_id,
            "strategy_hash": strategy_hash,
            "n_groups": n_groups,
            "k_test": k_test,
            "n_splits": len(splits),
            "source_observations": int(len(returns)),
            "paths": rows,
            "sharpe": {
                "mean": self._optional_finite(path_sharpes.mean()),
                "median": self._optional_finite(np.median(path_sharpes)),
                "p5": self._optional_finite(np.percentile(path_sharpes, 5)),
                "p95": self._optional_finite(np.percentile(path_sharpes, 95)),
            },
            # A single fixed configuration cannot identify classical PBO,
            # which requires ranking competing configurations in and out of sample.
            "pbo": None,
            "pbo_reason": "PBO requires at least two competing parameter configurations",
            "path_failure_probability": float(np.mean(path_sharpes <= 0.0)),
            "dsr": dsr,
            "embargo_sensitivity": embargo_sensitivity,
            "backtests_executed": 1,
            "duration_seconds": time.monotonic() - started,
            "warnings": sorted(set(map(str, simulation.warnings))),
        }

    def run_walk_forward(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        source, strategy_id, strategy_hash = self._resolve_strategy(payload)
        base_config, sessions = self._resolve_backtest(payload["backtest_config"], source)
        windows = self._generate_windows(
            sessions,
            int(payload.get("is_months", 12)),
            int(payload.get("oos_months", 3)),
            str(payload.get("window_mode", "rolling")),
        )
        max_windows = min(int(payload.get("max_windows", self.MAX_WINDOWS)), self.MAX_WINDOWS)
        if len(windows) < 2:
            raise ValueError("walk-forward requires a date range producing at least two OOS windows")
        if len(windows) > max_windows:
            raise ValueError(
                f"walk-forward produced {len(windows)} windows; increase oos_months, "
                f"shorten the date range, or set max_windows up to {self.MAX_WINDOWS}"
            )

        requested_budget = int(
            payload.get("trials_per_window")
            or payload.get("trial_budget")
            or self.MAX_CANDIDATES
        )
        candidate_limit = min(requested_budget, self.MAX_CANDIDATES)
        candidates = self._parameter_candidates(
            payload["parameters"], candidate_limit, int(payload.get("seed", 42))
        )
        if not candidates:
            raise ValueError("walk-forward generated no valid parameter candidates")

        returns_by_candidate: list[tuple[dict[str, Any], pd.Series]] = []
        warnings: list[str] = []
        for candidate in candidates:
            config = SimulationConfig(**{
                **base_config.__dict__,
                "parameters": {**dict(base_config.parameters or {}), **candidate},
            })
            try:
                simulation = self._run_backtest(config)
                candidate_returns = self._validated_returns(simulation, sessions)
            except Exception as exc:
                warnings.append(
                    f"candidate {json.dumps(candidate, sort_keys=True, default=str)[:300]} "
                    f"failed: {type(exc).__name__}: {exc}"
                )
                continue
            returns_by_candidate.append((candidate, candidate_returns))
            warnings.extend(map(str, simulation.warnings))
        if not returns_by_candidate:
            raise ValueError("all bounded walk-forward parameter candidates failed")

        objective = str(payload.get("objective", "sharpe"))
        rows: list[dict[str, Any]] = []
        stitched_parts: list[pd.Series] = []
        ratios: list[float] = []
        for index, (train_dates, test_dates) in enumerate(windows):
            scored: list[tuple[float, dict[str, Any], pd.Series, float]] = []
            for params, candidate_returns in returns_by_candidate:
                train = candidate_returns.reindex(train_dates).dropna()
                if len(train) < 20:
                    continue
                raw_objective = self._metric(train, objective)
                if np.isnan(raw_objective):
                    continue
                ranking_score = float(np.clip(raw_objective, -1e12, 1e12))
                scored.append((ranking_score, params, candidate_returns, raw_objective))
            if not scored:
                raise ValueError(f"walk-forward window {index} has no finite in-sample candidate")
            _, best_params, best_returns, is_objective = max(scored, key=lambda item: item[0])
            train = best_returns.reindex(train_dates).dropna()
            oos = best_returns.reindex(test_dates).dropna()
            if len(oos) < 5:
                raise ValueError(f"walk-forward window {index} has fewer than five OOS returns")
            is_sharpe = self._finite(self.metrics.compute_sharpe(train), default=0.0)
            oos_sharpe = self._finite(self.metrics.compute_sharpe(oos), default=0.0)
            oos_objective = self._metric(oos, objective)
            ratio = oos_sharpe / is_sharpe if is_sharpe != 0.0 else None
            if ratio is not None and np.isfinite(ratio):
                ratios.append(float(ratio))
            else:
                ratio = None
            stitched_parts.append(oos)
            span = len(train) + len(oos)
            rows.append({
                "id": f"wf_{index:02d}",
                "window": index,
                "train_start": self._date_string(train.index.min()),
                "train_end": self._date_string(train.index.max()),
                "test_start": self._date_string(oos.index.min()),
                "test_end": self._date_string(oos.index.max()),
                "train_observations": int(len(train)),
                "oos_observations": int(len(oos)),
                "train_pct": float(len(train) / span * 100.0),
                "test_pct": float(len(oos) / span * 100.0),
                "optimal_params": best_params,
                "is_objective": self._optional_finite(is_objective),
                "oos_objective": self._optional_finite(oos_objective),
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "ratio": ratio,
            })

        stitched = pd.concat(stitched_parts).sort_index()
        stitched = stitched.loc[~stitched.index.duplicated(keep="first")]
        equity = (1.0 + stitched).cumprod()
        curve = [
            {
                "date": self._date_string(date),
                "return_value": self._finite(value, default=0.0),
                "equity": max(self._finite(equity.loc[date], default=1.0), 1e-12),
            }
            for date, value in stitched.items()
        ]
        interval = self._bootstrap_interval(ratios, int(payload.get("seed", 42)))
        oos_sharpes = np.asarray([row["oos_sharpe"] for row in rows], dtype=float)
        return {
            "mode": "walk_forward",
            "method": "precomputed_candidate_walk_forward",
            "strategy_id": strategy_id,
            "strategy_hash": strategy_hash,
            "objective": objective,
            "windows": rows,
            "stitched_oos_curve": curve,
            "window_count": len(rows),
            "candidate_count": len(returns_by_candidate),
            "requested_trial_budget": requested_budget,
            "backtests_executed": len(returns_by_candidate),
            "mean_oos_sharpe": float(oos_sharpes.mean()),
            "pass_rate": float(np.mean(oos_sharpes > 0.0)),
            "mean_isoos_ratio": float(np.mean(ratios)) if ratios else None,
            "confidence_interval": interval,
            "duration_seconds": time.monotonic() - started,
            "warnings": sorted(set(warnings)),
        }

    def _resolve_strategy(self, payload: dict[str, Any]) -> tuple[str, Optional[str], str]:
        strategy_id = payload.get("strategy_id")
        if strategy_id:
            record = self.strategies.get(str(strategy_id))
            path = Path(record["file_path"]).expanduser().resolve()
            expected_hash = str(record.get("source_hash", ""))
        else:
            path = Path(str(payload["strategy_file"])).expanduser().resolve()
            expected_hash = ""
        if path.suffix.lower() != ".py":
            raise ValueError("strategy_file must be a Python file")
        if not path.is_file():
            raise FileNotFoundError(f"Strategy file not found: {path}")
        if path.stat().st_size > self.MAX_STRATEGY_BYTES:
            raise ValueError(
                f"strategy_file exceeds the {self.MAX_STRATEGY_BYTES} byte limit"
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_hash and digest != expected_hash:
            raise ValueError("stored strategy source hash does not match its file")
        return str(path), str(strategy_id) if strategy_id else None, digest

    def _resolve_backtest(
        self, raw_config: dict[str, Any], source: str
    ) -> tuple[SimulationConfig, pd.DatetimeIndex]:
        config = dict(raw_config)
        start = self._timestamp(config["date_start"])
        end = self._timestamp(config["date_end"])
        if end <= start:
            raise ValueError("backtest date_end must be after date_start")
        sessions = pd.DatetimeIndex(self.sessions_loader()).tz_localize(None).sort_values()
        sessions = sessions[(sessions >= start) & (sessions <= end)].unique()
        if len(sessions) < self.MIN_SESSIONS:
            raise ValueError(
                f"temporal validation requires at least {self.MIN_SESSIONS} master-universe sessions"
            )
        if len(sessions) > self.MAX_SESSIONS:
            raise ValueError(
                f"temporal validation is capped at {self.MAX_SESSIONS} master-universe sessions"
            )
        config["strategy_source"] = source
        config["date_start"] = self._date_string(sessions.min())
        config["date_end"] = self._date_string(sessions.max())
        return SimulationConfig(**config), sessions

    def _run_backtest(self, config: SimulationConfig) -> SimulationResult:
        result = self.engine_factory().run(config)
        if result.daily_returns is None or len(result.daily_returns) < 20:
            detail = "; ".join(map(str, result.warnings)) or "no daily returns"
            raise ValueError(f"backtest produced insufficient validation data: {detail}")
        return result

    def _validated_returns(
        self, result: SimulationResult, requested_sessions: pd.DatetimeIndex
    ) -> pd.Series:
        values = pd.Series(result.daily_returns, dtype=float).replace([np.inf, -np.inf], np.nan)
        values.index = pd.DatetimeIndex(values.index).tz_localize(None)
        values = values.sort_index()
        values = values.loc[values.index.intersection(requested_sessions)]
        if len(values) < 20 or values.isna().any():
            raise ValueError("backtest returns are missing or non-finite on validation sessions")
        if len(values) > self.MAX_SESSIONS:
            raise ValueError(f"backtest returns exceed the {self.MAX_SESSIONS} session cap")
        return values

    @staticmethod
    def _purged_train_indices(
        n_observations: int,
        test_indices: np.ndarray,
        purge_days: int,
        embargo_days: int,
    ) -> np.ndarray:
        blocked = np.zeros(int(n_observations), dtype=bool)
        for index in np.asarray(test_indices, dtype=int):
            lower = max(0, int(index) - int(purge_days))
            upper = min(int(n_observations), int(index) + int(embargo_days) + 1)
            blocked[lower:upper] = True
        return np.flatnonzero(~blocked)

    def _generate_windows(
        self,
        sessions: pd.DatetimeIndex,
        is_months: int,
        oos_months: int,
        mode: str,
    ) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        windows: list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]] = []
        test_start = int(sessions.searchsorted(
            sessions[0] + pd.DateOffset(months=int(is_months)), side="left"
        ))
        while test_start < len(sessions):
            if mode == "anchored":
                train_start = 0
            else:
                train_start = int(sessions.searchsorted(
                    sessions[test_start] - pd.DateOffset(months=int(is_months)),
                    side="left",
                ))
            test_end = int(sessions.searchsorted(
                sessions[test_start] + pd.DateOffset(months=int(oos_months)),
                side="left",
            ))
            test_end = min(max(test_end, test_start + 1), len(sessions))
            train_dates = sessions[train_start:test_start]
            test_dates = sessions[test_start:test_end]
            if len(train_dates) >= 20 and len(test_dates) >= 5:
                windows.append((train_dates, test_dates))
            if test_end >= len(sessions):
                break
            test_start = test_end
        return windows

    @staticmethod
    def _parameter_candidates(
        parameters: list[dict[str, Any]], limit: int, seed: int
    ) -> list[dict[str, Any]]:
        enabled = [parameter for parameter in parameters if parameter.get("included", True)]
        if not enabled or limit < 1:
            return []
        rng = np.random.default_rng(seed)

        def base_value(parameter: dict[str, Any]) -> Any:
            if parameter.get("current_value") is not None:
                return parameter["current_value"]
            values = parameter.get("values") or []
            if values:
                return values[0]
            low, high = parameter["suggested_range"]
            return float(low + (high - low) / 2.0)

        candidates = [{parameter["name"]: base_value(parameter) for parameter in enabled}]
        signatures = {json.dumps(candidates[0], sort_keys=True, default=str)}
        attempts = 0
        while len(candidates) < limit and attempts < limit * 50:
            attempts += 1
            candidate: dict[str, Any] = {}
            for parameter in enabled:
                kind = parameter.get("type", "continuous")
                if kind == "continuous":
                    bounds = parameter.get("suggested_range")
                    if bounds is None:
                        current = float(parameter["current_value"])
                        bounds = tuple(sorted((current * 0.5, current * 1.5)))
                        if bounds[0] == bounds[1]:
                            bounds = (current - 1.0, current + 1.0)
                    candidate[parameter["name"]] = float(rng.uniform(*map(float, bounds)))
                else:
                    values = list(parameter.get("values") or [parameter.get("current_value")])
                    candidate[parameter["name"]] = values[int(rng.integers(0, len(values)))]
            signature = json.dumps(candidate, sort_keys=True, default=str)
            if signature not in signatures:
                signatures.add(signature)
                candidates.append(candidate)
        return candidates

    def _metric(self, returns: pd.Series, objective: str) -> float:
        if objective == "sortino":
            return float(self.metrics.compute_sortino(returns))
        if objective == "calmar":
            return float(self.metrics.compute_calmar(returns))
        return float(self.metrics.compute_sharpe(returns))

    @staticmethod
    def _bootstrap_interval(values: list[float], seed: int) -> Optional[tuple[float, float]]:
        clean = np.asarray(values, dtype=float)
        clean = clean[np.isfinite(clean)]
        if len(clean) < 2:
            return None
        rng = np.random.default_rng(seed)
        samples = rng.choice(clean, size=(500, len(clean)), replace=True).mean(axis=1)
        return float(np.percentile(samples, 5)), float(np.percentile(samples, 95))

    @staticmethod
    def _timestamp(value: Any) -> pd.Timestamp:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            raise ValueError(f"invalid validation date: {value}")
        return pd.Timestamp(parsed).tz_convert(None)

    @staticmethod
    def _date_string(value: Any) -> str:
        return pd.Timestamp(value).date().isoformat()

    @staticmethod
    def _finite(value: Any, *, default: float) -> float:
        numeric = float(value)
        return numeric if math.isfinite(numeric) else float(default)

    @staticmethod
    def _optional_finite(value: Any) -> Optional[float]:
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
