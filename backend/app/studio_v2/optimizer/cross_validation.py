"""Purged, embargoed time-series cross-validation."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


class OptimizerCrossValidation:
    _COMPLETE_STATES = {"complete", "completed", "success", "succeeded"}

    @classmethod
    def _is_complete(cls, value: Any) -> bool:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return True
        normalized = str(value).strip().lower().rsplit(".", 1)[-1]
        return normalized in cls._COMPLETE_STATES

    @staticmethod
    def _point_key(parameters: dict[str, Any], keys: list[str],
                   precision: int = 8) -> tuple[Any, ...]:
        output = []
        for key in keys:
            value = parameters.get(key)
            output.append(round(float(value), precision) if isinstance(value, (int, float, np.number)) else value)
        return tuple(output)

    def compare_regions(self, bayesian_trials: Any, walk_forward_windows: Any,
                        top_fraction: float = 0.20,
                        objective: str = "objective") -> dict[str, Any]:
        trials = pd.DataFrame(bayesian_trials)
        windows = list(walk_forward_windows or [])
        reserved = {
            "trial_id", "id", objective, "timestamp", "score", "metrics",
            "state", "status", "error", "failure_reason", "pareto_optimal",
            "valid_objectives", "duplicate_of",
        }
        trial_parameter_keys = [
            column for column in trials.columns
            if column not in reserved
            and pd.to_numeric(trials[column], errors="coerce").notna().any()
        ]
        window_parameters = []
        for window in windows:
            if not isinstance(window, dict) or not self._is_complete(window.get("state")):
                continue
            params = window.get("optimal_params", window.get("parameters", window))
            if isinstance(params, dict):
                window_parameters.append(params)
        window_parameter_keys = []
        for params in window_parameters:
            for key, value in params.items():
                if key in reserved or key in window_parameter_keys:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(numeric):
                    window_parameter_keys.append(key)
        if trial_parameter_keys and window_parameter_keys:
            parameter_keys = [key for key in trial_parameter_keys if key in window_parameter_keys]
        else:
            parameter_keys = trial_parameter_keys or window_parameter_keys
        if not parameter_keys:
            return {
                "parameter_keys": [], "overlap_percentage": 0.0,
                "verdict": "insufficient", "bayesian_region_size": 0,
                "walk_forward_region_size": 0, "intersection_size": 0,
                "overlay": [], "comparable": False,
                "reason": "No shared numeric parameter dimensions were available.",
            }

        eligible = trials.iloc[0:0].copy()
        if objective in trials:
            objective_values = pd.to_numeric(trials[objective], errors="coerce")
            states = (
                trials["state"].map(self._is_complete)
                if "state" in trials else pd.Series(True, index=trials.index)
            )
            finite = np.isfinite(objective_values.to_numpy(float)) & states.to_numpy(bool)
            eligible = trials.loc[finite].copy()
            eligible[objective] = objective_values.loc[finite]
            for key in parameter_keys:
                if key not in eligible:
                    eligible = eligible.iloc[0:0]
                    break
                numeric = pd.to_numeric(eligible[key], errors="coerce")
                eligible = eligible.loc[np.isfinite(numeric.to_numpy(float))].copy()
                eligible[key] = numeric.loc[eligible.index]
            eligible = eligible.sort_values(objective, ascending=False).drop_duplicates(
                subset=parameter_keys, keep="first"
            )
        fraction = min(max(float(top_fraction), 0.01), 1.0)
        count = max(1, int(np.ceil(len(eligible) * fraction))) if len(eligible) else 0
        bayes_top = eligible.head(count)
        bayes_region = {
            self._point_key(row, parameter_keys)
            for row in bayes_top[parameter_keys].to_dict(orient="records")
        }
        walk_points = []
        for params in window_parameters:
            if not all(key in params for key in parameter_keys):
                continue
            try:
                point = self._point_key(params, parameter_keys)
                if all(np.isfinite(float(value)) for value in point):
                    walk_points.append(point)
            except (TypeError, ValueError):
                continue
        walk_region = set(walk_points)
        union = bayes_region | walk_region
        intersection = bayes_region & walk_region
        overlap = 100.0 * len(intersection) / len(union) if union else 0.0
        comparable = bool(bayes_region and walk_region)
        verdict = (
            "insufficient" if not comparable
            else "stable" if overlap > 80
            else "diverging" if overlap >= 50
            else "divergent"
        )
        overlay = []
        for point in sorted(union, key=str):
            overlay.append({
                **dict(zip(parameter_keys, point)),
                "bayesian_preferred": point in bayes_region,
                "walk_forward_preferred": point in walk_region,
                "overlap": point in intersection,
            })
        return {
            "parameter_keys": parameter_keys,
            "overlap_percentage": overlap,
            "verdict": verdict,
            "bayesian_region_size": len(bayes_region),
            "walk_forward_region_size": len(walk_region),
            "intersection_size": len(intersection),
            "overlay": overlay,
            "comparable": comparable,
            "reason": None if comparable else "Both preferred regions need at least one finite completed point.",
        }

    def run(self, observations: Any, evaluate: Callable[[pd.DataFrame, pd.DataFrame], Any] | None = None,
            folds: int = 5, purge: int = 5, embargo: int = 5) -> dict[str, Any]:
        frame = pd.DataFrame(observations)
        if len(frame) < folds * 2:
            raise ValueError("insufficient observations for requested folds")
        indices = np.arange(len(frame))
        rows = []
        for fold, test_idx in enumerate(np.array_split(indices, folds)):
            forbidden_start = max(0, int(test_idx[0]) - purge)
            forbidden_end = min(len(frame), int(test_idx[-1]) + embargo + 1)
            train_idx = np.concatenate([indices[:forbidden_start], indices[forbidden_end:]])
            if evaluate:
                result = evaluate(frame.iloc[train_idx], frame.iloc[test_idx])
            elif "return" in frame:
                test = pd.to_numeric(frame.iloc[test_idx]["return"], errors="coerce")
                result = float(test.mean() / test.std(ddof=1) * np.sqrt(252)) if test.std(ddof=1) else 0.0
            else:
                result = None
            rows.append({"fold": fold, "train_size": len(train_idx), "test_size": len(test_idx), "score": result,
                         "test_start": int(test_idx[0]), "test_end": int(test_idx[-1])})
        scores = pd.to_numeric(pd.Series([row["score"] for row in rows]), errors="coerce")
        return {"folds": rows, "mean_score": float(scores.mean()), "score_std": float(scores.std(ddof=1)), "purge": purge, "embargo": embargo}
