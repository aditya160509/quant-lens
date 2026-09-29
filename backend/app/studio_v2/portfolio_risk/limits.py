"""Persistent risk limits and breach evaluation."""

from __future__ import annotations

import uuid
from typing import Any, Callable

import pandas as pd

from ..shared.persistence import SQLiteStore, utc_now


class RiskLimitService:
    def __init__(self, store: SQLiteStore | None = None,
                 strategy_provider: Callable[[], list[Any]] | None = None) -> None:
        self.store = store or SQLiteStore()
        self.strategy_provider = strategy_provider

    def list(self) -> list[dict[str, Any]]:
        return self.store.list("risk_limits", limit=1000)

    def replace(self, limits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing = {row["id"] for row in self.list()}
        kept = set()
        for item in limits:
            identifier = str(item.get("id") or uuid.uuid4())
            if item.get("operator", "max") not in {"max", "min"}:
                raise ValueError("limit operator must be max or min")
            self.store.put("risk_limits", identifier, {**item, "id": identifier})
            kept.add(identifier)
        for identifier in existing - kept:
            self.store.delete("risk_limits", identifier)
        return self.list()

    def breaches(self, metrics: dict[str, float]) -> list[dict[str, Any]]:
        rows = []
        for limit in self.list():
            if not limit.get("enabled", True) or limit["metric"] not in metrics:
                continue
            value, threshold = float(metrics[limit["metric"]]), float(limit["threshold"])
            breached = value > threshold if limit.get("operator", "max") == "max" else value < threshold
            if breached:
                rows.append({"limit_id": limit["id"], "metric": limit["metric"], "value": value,
                             "threshold": threshold, "severity": limit.get("severity", "warning"), "detected_at": utc_now()})
        return rows

    def _compute_current_values(self, strategies: list[Any] | None = None) -> dict[str, float]:
        records = strategies if strategies is not None else (
            self.strategy_provider() if self.strategy_provider else []
        )
        metric_rows, return_series = [], {}
        for index, record in enumerate(records):
            value = record.to_dict() if hasattr(record, "to_dict") else dict(record)
            metrics = value.get("metrics", {})
            metric_rows.append(metrics)
            if metrics.get("daily_returns") is not None:
                return_series[str(value.get("run_id", index))] = metrics["daily_returns"]
        output: dict[str, float] = {"active_strategy_count": float(len(records))}
        for key in ("max_drawdown", "volatility", "gross_leverage", "largest_position"):
            values = [abs(float(row[key])) for row in metric_rows if row.get(key) is not None]
            if values:
                output[key] = max(values)
        if return_series:
            from .var_engine import VaREngine
            primary = VaREngine().compute(pd.DataFrame(return_series), None, 0.99, 1, 1.0)
            output["var_99_1d"] = float(primary["historical_var"])
            output["cvar_99_1d"] = float(primary["historical_cvar"])
        return output

    def get_computed_breaches(self, strategies: list[Any] | None = None) -> dict[str, Any]:
        current = self._compute_current_values(strategies)
        return {"current_values": current, "breaches": self.breaches(current)}
