"""Durable factor versioning, review, approval, and deprecation."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from ..shared.persistence import SQLiteStore, utc_now


class FactorGovernance:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()

    def create_version(self, factor_id: str, expression: str, author: str = "unknown",
                       notes: str = "") -> dict[str, Any]:
        versions = self.versions(factor_id)
        record = {
            "factor_id": factor_id,
            "version": len(versions) + 1,
            "expression": expression,
            "expression_hash": hashlib.sha256(expression.encode()).hexdigest(),
            "author": author,
            "notes": notes,
            "status": "draft",
            "history": [{"action": "created", "actor": author, "at": utc_now()}],
        }
        return self.store.put("factor_versions", str(uuid.uuid4()), record, create_only=True)

    def versions(self, factor_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.store.list("factor_versions", limit=1000) if row["factor_id"] == factor_id]
        return sorted(rows, key=lambda row: row["version"])

    def _transition(self, factor_id: str, status: str, actor: str, reason: str = "",
                    action: str | None = None) -> dict[str, Any]:
        versions = self.versions(factor_id)
        if not versions:
            raise KeyError(f"factor '{factor_id}' has no versions")
        record = versions[-1]
        record["status"] = status
        record.setdefault("history", []).append({
            "action": action or status, "status": status, "actor": actor,
            "reason": reason, "at": utc_now(),
        })
        return self.store.put("factor_versions", record["id"], record)

    def approve(self, factor_id: str, actor: str, reason: str = "") -> dict[str, Any]:
        return self._transition(factor_id, "approved", actor, reason)

    def deprecate(self, factor_id: str, actor: str, reason: str) -> dict[str, Any]:
        if not reason:
            raise ValueError("deprecation reason is required")
        return self._transition(factor_id, "deprecated", actor, reason)

    def restore(self, factor_id: str, actor: str, reason: str = "") -> dict[str, Any]:
        return self._transition(
            factor_id, "approved", actor, reason or "Restored to active use",
            action="restored",
        )

    def changelog(self, factor_id: str) -> list[dict[str, Any]]:
        return [event for version in self.versions(factor_id) for event in version.get("history", [])]

    def status(self, factor_id: str) -> dict[str, Any]:
        versions = self.versions(factor_id)
        if not versions:
            return {"status": "unversioned", "deprecation_reason": None}
        latest = versions[-1]
        history = latest.get("history", [])
        reason = next((event.get("reason") for event in reversed(history)
                       if event.get("action") == "deprecated"), None)
        return {"status": latest.get("status", "draft"), "deprecation_reason": reason,
                "version": latest.get("version")}

    def get_baseline_factors(self, factor_ids: list[str]) -> list[str]:
        return [factor_id for factor_id in factor_ids
                if self.status(factor_id)["status"] != "deprecated"]
