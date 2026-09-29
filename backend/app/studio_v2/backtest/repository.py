"""Durable storage for complete backtest artifacts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..shared.persistence import SQLiteStore


def _serializable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [{str(key): _serializable(item) for key, item in row.items()}
                for row in value.replace([np.inf, -np.inf], np.nan).to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return {str(key): _serializable(item) for key, item in
                value.replace([np.inf, -np.inf], np.nan).items()}
    if isinstance(value, dict):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_serializable(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    return value


class BacktestResultRepository:
    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self.store = store or SQLiteStore()

    def save(self, run_id: str, result: Any, metrics: Optional[dict[str, Any]] = None,
             kind: str = "single") -> dict[str, Any]:
        if hasattr(result, "to_dict"):
            payload = result.to_dict()
        elif hasattr(result, "__dataclass_fields__"):
            payload = asdict(result)
        else:
            payload = dict(result)
        record = {
            "run_id": run_id,
            "kind": kind,
            "result": payload,
            "metrics": dict(metrics or payload.get("metrics", {})),
        }
        return self.store.put("backtest_results", run_id, _serializable(record))

    def get(self, run_id: str) -> dict[str, Any]:
        return self.store.get("backtest_results", run_id)

    def get_result(self, run_id: str) -> dict[str, Any]:
        return self.get(run_id)["result"]

    def batch_get(self, run_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch runs in caller order with one stable public contract."""
        return [self.get(str(run_id)) for run_id in run_ids]

    def batch_get_metrics(self, run_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {str(run_id): record.get("metrics", {})
                for run_id, record in zip(run_ids, self.batch_get(run_ids))}

    def batch_get_equity_curves(self, run_ids: list[str]) -> dict[str, Any]:
        curves: dict[str, Any] = {}
        for run_id, record in zip(run_ids, self.batch_get(run_ids)):
            result = record.get("result", {})
            curves[str(run_id)] = result.get("equity_curve", result.get("daily_nav", []))
        return curves

    def batch_get_daily_returns(self, run_ids: list[str]) -> dict[str, Any]:
        return {
            str(run_id): record.get("result", {}).get("daily_returns", [])
            for run_id, record in zip(run_ids, self.batch_get(run_ids))
        }
