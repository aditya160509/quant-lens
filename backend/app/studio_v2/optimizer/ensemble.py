"""Trial ensembles with equal, objective, and inverse-variance weighting."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd


class ParameterEnsemble:
    _COMPLETE_STATES = {"complete", "completed", "success", "succeeded"}
    _METADATA_COLUMNS = {
        "trial_id", "id", "timestamp", "mode", "state", "status", "error",
        "failure_reason", "pareto_optimal", "valid_objectives", "duplicate_of",
    }

    @classmethod
    def _is_complete(cls, value: Any) -> bool:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return True
        return str(value).strip().lower().rsplit(".", 1)[-1] in cls._COMPLETE_STATES

    @staticmethod
    def _signature(row: dict[str, Any], columns: list[str]) -> str:
        return json.dumps(
            {column: row.get(column) for column in columns},
            sort_keys=True, separators=(",", ":"), default=str,
        )

    @staticmethod
    def _distribution(frame: pd.DataFrame, objective: str) -> dict[str, Any]:
        values = pd.to_numeric(frame[objective], errors="coerce")
        values = values.loc[np.isfinite(values.to_numpy(float))]
        if values.empty:
            raise ValueError("objective contains no finite observations")
        q = values.quantile([0.25, 0.50, 0.75])
        spread = float(q.loc[0.75] - q.loc[0.25])
        return {
            "count": int(len(values)), "min": float(values.min()),
            "p25": float(q.loc[0.25]), "p50": float(q.loc[0.50]),
            "p75": float(q.loc[0.75]), "max": float(values.max()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "iqr": spread,
            "overfitting_warning": bool(spread > max(0.25, abs(float(q.loc[0.50])) * 0.50)),
            "note": (
                "Wide out-of-sample performance dispersion indicates configuration sensitivity."
                if spread > max(0.25, abs(float(q.loc[0.50])) * 0.50)
                else "Performance dispersion is contained across evaluated configurations."
            ),
        }

    def build(self, trials: Any, top_n: int = 5, weighting: str = "equal",
              objective: str = "objective", return_series: dict[str, Any] | None = None,
              backtest_config: dict[str, Any] | None = None) -> dict[str, Any]:
        frame = pd.DataFrame(trials)
        if frame.empty or objective not in frame:
            raise ValueError("trials with an objective column are required")
        objective_values = pd.to_numeric(frame[objective], errors="coerce")
        complete = (
            frame["state"].map(self._is_complete)
            if "state" in frame else pd.Series(True, index=frame.index)
        )
        frame = frame.loc[
            np.isfinite(objective_values.to_numpy(float)) & complete.to_numpy(bool)
        ].copy()
        if frame.empty:
            raise ValueError("objective contains no finite completed observations")
        frame[objective] = objective_values.loc[frame.index]
        parameter_columns = [
            column for column in frame
            if column not in self._METADATA_COLUMNS and column != objective
        ]
        signature_columns = parameter_columns or [objective]
        frame["_configuration_signature"] = [
            self._signature(row, signature_columns)
            for row in frame.to_dict(orient="records")
        ]
        frame = (
            frame.sort_values(objective, ascending=False)
            .drop_duplicates("_configuration_signature", keep="first")
            .drop(columns="_configuration_signature")
        )
        selected = frame.head(min(max(1, int(top_n)), len(frame))).copy()
        if weighting == "objective":
            shifted = selected[objective] - selected[objective].min()
            weights = shifted + max(1e-12, shifted.std() * 0.01)
        elif weighting == "inverse_variance" and return_series:
            variances = []
            for _, row in selected.iterrows():
                series = pd.Series(return_series.get(str(row.get("trial_id")), []), dtype=float)
                variances.append(float(series.var(ddof=1)))
            weights = pd.Series(np.divide(1.0, variances, out=np.zeros(len(variances)), where=np.asarray(variances) > 0), index=selected.index)
        else:
            weights = pd.Series(1.0, index=selected.index)
        total_weight = float(pd.to_numeric(weights, errors="coerce").sum())
        if not np.isfinite(total_weight) or total_weight <= 0:
            weights = pd.Series(1.0, index=selected.index)
            total_weight = float(len(selected))
        weights = weights / total_weight
        identifiers = [
            str(row.get("trial_id", row.get("id", index)))
            for index, row in enumerate(selected.to_dict(orient="records"))
        ]
        signal_inputs = dict(return_series or {})
        if not signal_inputs and backtest_config:
            from ..backtest.engine import EventDrivenEngine, SimulationConfig
            reserved = self._METADATA_COLUMNS | {objective}
            for index, row in enumerate(selected.to_dict(orient="records")):
                identifier = str(row.get("trial_id", row.get("id", index)))
                parameters = {key: value for key, value in row.items() if key not in reserved}
                config = SimulationConfig(**{
                    **backtest_config,
                    "parameters": {**backtest_config.get("parameters", {}), **parameters},
                })
                signal_inputs[identifier] = EventDrivenEngine().run(config).daily_returns.tolist()
        available = {
            identifier: pd.Series(signal_inputs.get(identifier, []), dtype=float)
            for identifier in identifiers if len(signal_inputs.get(identifier, []))
        }
        available_weights = pd.Series({
            identifier: float(weights.iloc[index])
            for index, identifier in enumerate(identifiers) if identifier in available
        })
        if not available_weights.empty:
            available_weights /= available_weights.sum()
        ensemble_returns = (
            pd.DataFrame(available).mul(available_weights, axis=1).sum(axis=1, min_count=1)
            if available else pd.Series(dtype=float)
        )
        ensemble_metrics = {}
        if not ensemble_returns.empty:
            from ..backtest.metrics import PerformanceMetrics
            ensemble_metrics = PerformanceMetrics().compute_all(ensemble_returns).to_dict()
        parameter_columns = [
            column for column in selected
            if column not in self._METADATA_COLUMNS and column != objective
        ]
        averaged = {}
        for column in parameter_columns:
            numeric = pd.to_numeric(selected[column], errors="coerce")
            if numeric.notna().all():
                averaged[column] = float((numeric * weights).sum())
            else:
                averaged[column] = selected.loc[weights.idxmax(), column]
        return {
            "parameters": averaged,
            "members": [{**row, "ensemble_weight": float(weights.iloc[index])} for index, row in enumerate(selected.to_dict(orient="records"))],
            "weighting": weighting,
            "ensemble_returns": ensemble_returns,
            "ensemble_metrics": ensemble_metrics,
            "distribution": self._distribution(frame, objective),
            "mode": "signal_ensemble" if available else "parameter_summary",
            "overfitting_mitigation": (
                "Output-level ensembling diversifies configuration error; parameter averages are "
                "returned only as a diagnostic summary."
            ),
            "executed_backtests": bool(backtest_config and not return_series),
        }
