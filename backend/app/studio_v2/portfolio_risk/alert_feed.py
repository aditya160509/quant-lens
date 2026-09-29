"""Durable deduplicated risk-alert feed."""

from __future__ import annotations

import hashlib
from typing import Any

from ..shared.persistence import SQLiteStore, VersionConflictError, utc_now


class AlertFeed:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()

    def create(self, alert: dict[str, Any]) -> dict[str, Any]:
        fingerprint = hashlib.sha256(f"{alert.get('type')}|{alert.get('strategy_id')}|{alert.get('message')}".encode()).hexdigest()
        existing = self.store.maybe_get("risk_alerts", fingerprint)
        if existing is not None and not existing.get("acknowledged"):
            return existing
        payload = {
            **(existing or {}),
            **alert,
            "fingerprint": fingerprint,
            "acknowledged": False,
            "occurrence_count": int((existing or {}).get("occurrence_count", 0)) + 1,
            "last_occurred_at": utc_now(),
        }
        payload.pop("acknowledged_by", None)
        payload.pop("acknowledged_at", None)
        if existing is None:
            try:
                return self.store.put(
                    "risk_alerts", fingerprint, payload, create_only=True
                )
            except ValueError:
                # Another worker won the deterministic insert race.
                return self.store.get("risk_alerts", fingerprint)
        try:
            return self.store.put(
                "risk_alerts",
                fingerprint,
                payload,
                expected_version=int(existing.get("_revision", 1)),
            )
        except VersionConflictError:
            # A concurrent worker already reopened the same alert.
            return self.store.get("risk_alerts", fingerprint)

    def list(self, acknowledged: bool | None = None, severity: str | None = None,
             limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if severity and severity not in {"info", "warning", "critical"}:
            raise ValueError("severity must be info, warning, or critical")
        if not 1 <= int(limit) <= 500 or int(offset) < 0:
            raise ValueError("limit must be 1..500 and offset must be non-negative")
        rows = self.store.list("risk_alerts", limit=100_000)
        if acknowledged is not None:
            rows = [row for row in rows if bool(row.get("acknowledged")) == acknowledged]
        if severity:
            rows = [row for row in rows if row.get("severity") == severity]
        return rows[int(offset):int(offset) + int(limit)]

    def ingest_breaches(self, source: str, breaches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.create({
            "type": f"{source}_breach",
            "severity": breach.get("severity", "warning"),
            "strategy_id": breach.get("strategy_id"),
            "message": breach.get("message") or (
                f"{breach.get('metric', 'risk metric')} is {breach.get('value')} "
                f"against limit {breach.get('threshold')}"
            ),
            "source": source,
            "details": breach,
        }) for breach in breaches]

    def ingest_reconciliation(self, strategies: list[Any]) -> list[dict[str, Any]]:
        rows = []
        for record in strategies:
            value = record.to_dict() if hasattr(record, "to_dict") else dict(record)
            verdict = str(value.get("metrics", {}).get("reconciliation_verdict", "")).lower()
            if verdict in {"red", "failed", "break"}:
                rows.append(self.create({
                    "type": "reconciliation",
                    "severity": "critical",
                    "strategy_id": value.get("run_id", value.get("strategy_id")),
                    "message": "Live and backtest behavior have a material reconciliation break.",
                    "details": value.get("metrics", {}),
                }))
        return rows

    def ingest_var(self, result: dict[str, Any], threshold: float = 0.05) -> list[dict[str, Any]]:
        primary = result.get("primary", result)
        value = float(primary.get("historical_var", 0.0))
        portfolio_value = float(primary.get("portfolio_value", 1.0) or 1.0)
        ratio = value / portfolio_value
        if ratio <= float(threshold):
            return []
        return [self.create({
            "type": "var_breach", "severity": "critical", "strategy_id": None,
            "message": f"Portfolio VaR {ratio:.2%} exceeds {float(threshold):.2%}.",
            "details": {"value": value, "ratio": ratio, "threshold": float(threshold)},
        })]

    def ingest_freshness(self, statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for status in statuses:
            state = str(status.get("status", "")).lower()
            if state not in {"current", "recorded"}:
                rows.append(self.create({
                    "type": "data_freshness",
                    "severity": "critical" if state == "failed" else "warning",
                    "strategy_id": None,
                    "message": f"{status.get('source_name', 'data source')} is {state}.",
                    "details": status,
                }))
        return rows

    def acknowledge(self, alert_id: str, actor: str) -> dict[str, Any]:
        record = self.store.get("risk_alerts", alert_id)
        acknowledged_at = utc_now()
        record.setdefault("acknowledgement_history", []).append(
            {"actor": actor, "at": acknowledged_at}
        )
        record.update({"acknowledged": True, "acknowledged_by": actor, "acknowledged_at": acknowledged_at})
        return self.store.put(
            "risk_alerts", alert_id, record,
            expected_version=int(record.get("_revision", 1)),
        )
