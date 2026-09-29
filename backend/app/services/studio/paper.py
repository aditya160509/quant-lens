"""Durable, artifact-bound paper execution lifecycle.

The service records user or simulator supplied events. It never fabricates
market prices, fills, positions, or broker acknowledgements.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.studio_v2.shared.persistence import SQLiteStore
from app.services.studio.quotas import get_quota


DEPLOYMENTS = "studio_paper_deployments"
EVENTS = "studio_paper_events"
EVENT_TYPES = {
    "signal", "intended_order", "submitted_order", "fill", "position",
    "valuation", "alert", "lifecycle",
}
PARENT_TYPES = {
    "intended_order": "signal",
    "submitted_order": "intended_order",
    "fill": "submitted_order",
    "position": "fill",
}
ACTIVE_STATES = {"armed", "running"}


class PaperLifecycleError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PaperLifecycle:
    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self.store = store or SQLiteStore()
        self._lock = threading.RLock()

    def create_deployment(
        self,
        *,
        name: str,
        source_version: dict[str, Any],
        validation_job: dict[str, Any],
        promotion: dict[str, Any],
        schedule: dict[str, Any],
        universe: list[str],
        limits: dict[str, Any],
    ) -> dict[str, Any]:
        artifact_id = source_version.get("artifact_id")
        if not artifact_id or source_version.get("version_id") is None:
            raise PaperLifecycleError("PAPER_SOURCE_NOT_VERSIONED", "A saved portfolio version is required.")
        if validation_job.get("type") != "walk-forward" or validation_job.get("status") != "completed":
            raise PaperLifecycleError("PAPER_VALIDATION_REQUIRED", "A completed walk-forward validation job is required.")
        if validation_job.get("params", {}).get("source_artifact_id") != artifact_id:
            raise PaperLifecycleError("PAPER_ARTIFACT_MISMATCH", "Validation does not belong to the selected artifact.")
        verdict = validation_job.get("result", {}).get("verdict", {})
        if verdict.get("status") != "PASSED":
            raise PaperLifecycleError("PAPER_VALIDATION_FAILED", "The selected artifact did not pass its validation policy.")
        if promotion.get("job_id") != validation_job.get("job_id") or promotion.get("action") != "promote":
            raise PaperLifecycleError("PAPER_PROMOTION_REQUIRED", "An exact promote decision for the validation job is required.")
        if not universe:
            raise PaperLifecycleError("PAPER_UNIVERSE_REQUIRED", "At least one paper-trading asset is required.")
        if self.store.count(DEPLOYMENTS) >= get_quota("STUDIO_MAX_PAPER_DEPLOYMENTS"):
            raise PaperLifecycleError("PAPER_QUOTA_EXCEEDED", "Paper deployment quota exceeded.", 429)

        deployment_id = f"paper_{uuid.uuid4().hex[:16]}"
        record = {
            "deployment_id": deployment_id,
            "name": name.strip(),
            "source_version_id": source_version["version_id"],
            "source_artifact_id": artifact_id,
            "validation_job_id": validation_job["job_id"],
            "promotion_audit_id": promotion["audit_id"],
            "schedule": schedule,
            "universe": list(dict.fromkeys(asset.strip().upper() for asset in universe if asset.strip())),
            "limits": limits,
            "state": "armed",
            "kill_switch": {"engaged": False, "reason": None, "actor": None, "at": None},
            "event_count": 0,
            "last_event_hash": None,
        }
        if not record["name"] or not record["universe"]:
            raise PaperLifecycleError("PAPER_CONFIGURATION_INVALID", "Deployment name and normalized universe are required.")
        return self.store.put(DEPLOYMENTS, deployment_id, record, create_only=True)

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        try:
            return self.store.get(DEPLOYMENTS, deployment_id)
        except KeyError as exc:
            raise PaperLifecycleError("PAPER_DEPLOYMENT_NOT_FOUND", "Paper deployment not found.", 404) from exc

    def list_deployments(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list(DEPLOYMENTS, limit=limit)

    def set_kill_switch(self, deployment_id: str, *, engaged: bool, actor: str, reason: str) -> dict[str, Any]:
        if not actor.strip() or not reason.strip():
            raise PaperLifecycleError("PAPER_AUDIT_REQUIRED", "Kill-switch actor and reason are required.")
        with self._lock:
            deployment = self.get_deployment(deployment_id)
            deployment["kill_switch"] = {
                "engaged": engaged, "actor": actor.strip(), "reason": reason.strip(), "at": _now(),
            }
            deployment["state"] = "halted" if engaged else "armed"
            self.store.put(DEPLOYMENTS, deployment_id, deployment, expected_version=deployment["_revision"])
            self._append_event_locked(deployment_id, "lifecycle", {
                "action": "kill_switch_engaged" if engaged else "kill_switch_released",
                "actor": actor.strip(), "reason": reason.strip(),
            }, None, None, bypass_state=True)
            return self.get_deployment(deployment_id)

    def append_event(
        self,
        deployment_id: str,
        event_type: str,
        payload: dict[str, Any],
        parent_event_id: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            return self._append_event_locked(deployment_id, event_type, payload, parent_event_id, occurred_at)

    def _append_event_locked(
        self,
        deployment_id: str,
        event_type: str,
        payload: dict[str, Any],
        parent_event_id: Optional[str],
        occurred_at: Optional[str],
        *,
        bypass_state: bool = False,
    ) -> dict[str, Any]:
        deployment = self.get_deployment(deployment_id)
        if event_type not in EVENT_TYPES:
            raise PaperLifecycleError("PAPER_EVENT_TYPE_INVALID", f"Unsupported paper event type: {event_type}.")
        if not bypass_state and deployment["kill_switch"]["engaged"] and event_type in {"signal", "intended_order", "submitted_order", "fill"}:
            raise PaperLifecycleError("PAPER_KILL_SWITCH_ENGAGED", "Trading events are blocked while the kill switch is engaged.", 409)
        expected_parent = PARENT_TYPES.get(event_type)
        parent = None
        if expected_parent:
            if not parent_event_id:
                raise PaperLifecycleError("PAPER_PARENT_REQUIRED", f"{event_type} requires a {expected_parent} parent event.")
            try:
                parent = self.store.get(EVENTS, parent_event_id)
            except KeyError as exc:
                raise PaperLifecycleError("PAPER_PARENT_NOT_FOUND", "Parent paper event not found.", 404) from exc
            if parent.get("deployment_id") != deployment_id or parent.get("event_type") != expected_parent:
                raise PaperLifecycleError("PAPER_CAUSALITY_INVALID", f"{event_type} must follow a {expected_parent} in the same deployment.")

        breaches = self._limit_breaches(deployment, event_type, payload)
        if breaches and event_type != "alert":
            alert = self._write_event(deployment, "alert", {"category": "limit_breach", "breaches": breaches, "rejected_event_type": event_type}, None, occurred_at)
            if deployment["limits"].get("auto_kill_on_breach", True):
                latest = self.get_deployment(deployment_id)
                latest["kill_switch"] = {"engaged": True, "actor": "system", "reason": "; ".join(breaches), "at": _now()}
                latest["state"] = "halted"
                self.store.put(DEPLOYMENTS, deployment_id, latest, expected_version=latest["_revision"])
            raise PaperLifecycleError("PAPER_LIMIT_BREACH", f"Event rejected: {'; '.join(breaches)}. Alert {alert['event_id']} recorded.", 409)
        event = self._write_event(deployment, event_type, payload, parent, occurred_at)
        if event_type == "submitted_order" and str(payload.get("status", "")).lower() == "rejected":
            latest = self.get_deployment(deployment_id)
            self._write_event(latest, "alert", {
                "category": "rejected_order",
                "submitted_order_event_id": event["event_id"],
                "reason": payload.get("rejection_reason"),
            }, event, occurred_at)
        return event

    def _write_event(self, deployment: dict[str, Any], event_type: str, payload: dict[str, Any], parent: Optional[dict[str, Any]], occurred_at: Optional[str]) -> dict[str, Any]:
        sequence = int(deployment.get("event_count", 0)) + 1
        event_id = f"pev_{uuid.uuid4().hex[:16]}"
        record = {
            "event_id": event_id,
            "deployment_id": deployment["deployment_id"],
            "sequence": sequence,
            "event_type": event_type,
            "occurred_at": occurred_at or _now(),
            "recorded_at": _now(),
            "parent_event_id": parent.get("event_id") if parent else None,
            "root_signal_id": (parent.get("root_signal_id") or parent.get("event_id")) if parent else (event_id if event_type == "signal" else None),
            "payload": payload,
            "previous_hash": deployment.get("last_event_hash"),
        }
        record["record_hash"] = _hash(record)
        saved = self.store.put(EVENTS, event_id, record, create_only=True)
        deployment["event_count"] = sequence
        deployment["last_event_hash"] = record["record_hash"]
        if event_type not in {"alert", "lifecycle"} and deployment["state"] == "armed":
            deployment["state"] = "running"
        self.store.put(DEPLOYMENTS, deployment["deployment_id"], deployment, expected_version=deployment["_revision"])
        return saved

    @staticmethod
    def _limit_breaches(deployment: dict[str, Any], event_type: str, payload: dict[str, Any]) -> list[str]:
        limits = deployment.get("limits", {})
        checks = {
            "intended_order": (("notional", "max_order_notional"),),
            "position": (("weight", "max_position_weight"), ("gross_exposure", "max_gross_exposure")),
        }
        breaches = []
        for value_key, limit_key in checks.get(event_type, ()):
            value, limit = payload.get(value_key), limits.get(limit_key)
            if value is not None and limit is not None and abs(float(value)) > float(limit):
                breaches.append(f"{value_key} {value} exceeds {limit_key} {limit}")
        if event_type == "valuation" and payload.get("daily_pnl") is not None and limits.get("max_daily_loss") is not None:
            if float(payload["daily_pnl"]) < -abs(float(limits["max_daily_loss"])):
                breaches.append(f"daily_pnl {payload['daily_pnl']} exceeds max_daily_loss {limits['max_daily_loss']}")
        if payload.get("price_missing") is True:
            breaches.append("price is missing")
        if payload.get("data_age_seconds") is not None and limits.get("max_data_age_seconds") is not None:
            if float(payload["data_age_seconds"]) > float(limits["max_data_age_seconds"]):
                breaches.append("market data is stale")
        return breaches

    def list_events(self, deployment_id: str, limit: int = 500) -> list[dict[str, Any]]:
        self.get_deployment(deployment_id)
        records = self.store.list(EVENTS, limit=1000)
        selected = [row for row in records if row.get("deployment_id") == deployment_id]
        return sorted(selected, key=lambda row: int(row["sequence"]))[-limit:]

    def trace(self, deployment_id: str, event_id: str) -> list[dict[str, Any]]:
        events = {row["event_id"]: row for row in self.list_events(deployment_id, 1000)}
        if event_id not in events:
            raise PaperLifecycleError("PAPER_EVENT_NOT_FOUND", "Paper event not found.", 404)
        chain, current = [], events[event_id]
        while current:
            chain.append(current)
            parent_id = current.get("parent_event_id")
            current = events.get(parent_id) if parent_id else None
        return list(reversed(chain))

    def reconciliation(self, deployment_id: str) -> dict[str, Any]:
        events = self.list_events(deployment_id, 1000)
        intended = {row["event_id"]: row for row in events if row["event_type"] == "intended_order"}
        submitted = {row["event_id"]: row for row in events if row["event_type"] == "submitted_order"}
        rows = []
        for fill in (row for row in events if row["event_type"] == "fill"):
            submit = submitted.get(fill.get("parent_event_id"))
            order = intended.get(submit.get("parent_event_id")) if submit else None
            expected = order.get("payload", {}).get("expected_price") if order else None
            actual = fill.get("payload", {}).get("price")
            slippage_bps = None
            classification = "missing_expected_price"
            if expected not in (None, 0) and actual is not None:
                side = str(order.get("payload", {}).get("side", "buy")).lower()
                signed = (float(actual) / float(expected) - 1.0) * (1 if side == "buy" else -1)
                slippage_bps = signed * 10_000
                classification = "favorable" if slippage_bps < 0 else "matched" if abs(slippage_bps) < 1e-9 else "adverse"
            rows.append({
                "fill_event_id": fill["event_id"], "intended_order_event_id": order.get("event_id") if order else None,
                "expected_price": expected, "fill_price": actual, "slippage_bps": slippage_bps,
                "classification": classification,
            })
        alerts = [row for row in events if row["event_type"] == "alert"]
        return {
            "deployment_id": deployment_id,
            "fills": rows,
            "summary": {
                "fill_count": len(rows),
                "classified_fill_count": sum(row["slippage_bps"] is not None for row in rows),
                "alert_count": len(alerts),
                "mean_slippage_bps": (sum(row["slippage_bps"] for row in rows if row["slippage_bps"] is not None) / sum(row["slippage_bps"] is not None for row in rows)) if any(row["slippage_bps"] is not None for row in rows) else None,
            },
        }
