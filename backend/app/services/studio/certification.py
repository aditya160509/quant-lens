"""Immutable, reproducible certification bundles for Studio artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from typing import Any, Optional

from app.services.studio.reports import ReportComposer, ReportError
from app.services.studio.quotas import get_quota
from app.studio_v2.shared.persistence import SQLiteStore


NAMESPACE = "studio_certifications"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class CertificationError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message); self.status_code = status_code


class CertificationService:
    def __init__(self, store: Optional[SQLiteStore] = None, job_store: Any = None) -> None:
        self.store = store or SQLiteStore(); self.job_store = job_store
        self.resolver = ReportComposer(self.store, job_store)

    def create(self, *, source: dict[str, str], validation_job_id: str, tests: list[dict[str, Any]], thresholds: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any]:
        try: artifact = self.resolver.resolve(source)
        except ReportError as exc: raise CertificationError(str(exc)) from exc
        job = self.job_store.get(validation_job_id) if self.job_store else None
        if not job or job.get("status") != "completed": raise CertificationError("a completed validation job is required")
        artifact_id = artifact.get("artifact_id") or artifact.get("source_artifact_id")
        if job.get("params", {}).get("source_artifact_id") != artifact_id:
            raise CertificationError("validation job does not match the source artifact")
        if not tests: raise CertificationError("at least one executed or skipped test record is required")
        normalized = []
        for test in tests:
            status = test.get("status")
            if status not in {"passed", "failed", "skipped"}: raise CertificationError("test status must be passed, failed, or skipped")
            if status == "skipped" and not str(test.get("reason", "")).strip(): raise CertificationError("skipped tests require a reason")
            normalized.append(dict(test))
        content = {
            "source": source, "source_artifact_id": artifact_id, "source_hash": _digest(artifact),
            "validation_job_id": validation_job_id, "validation_input_hash": job.get("input_hash"),
            "validation_result_hash": _digest(job.get("result")), "tests": normalized,
            "thresholds": thresholds, "overrides": overrides,
        }
        content_hash = _digest(content); identifier = f"cert_{content_hash[:16]}"
        existing = self.store.maybe_get(NAMESPACE, identifier)
        if existing is None and self.store.count(NAMESPACE) >= get_quota("STUDIO_MAX_CERTIFICATIONS"):
            raise CertificationError("certification quota exceeded", 429)
        return existing or self.store.put(NAMESPACE, identifier, {"certification_id": identifier, "content_hash": content_hash, **content}, create_only=True)

    def get(self, identifier: str) -> dict[str, Any]:
        try: return self.store.get(NAMESPACE, identifier)
        except KeyError as exc: raise CertificationError("certification bundle not found") from exc

    def reproduce(self, identifier: str) -> dict[str, Any]:
        bundle = self.get(identifier)
        artifact = self.resolver.resolve(bundle["source"])
        job = self.job_store.get(bundle["validation_job_id"]) if self.job_store else None
        checks = {
            "source_hash": _digest(artifact) == bundle["source_hash"],
            "validation_input_hash": bool(job) and job.get("input_hash") == bundle["validation_input_hash"],
            "validation_result_hash": bool(job) and _digest(job.get("result")) == bundle["validation_result_hash"],
            "content_hash": _digest({key: bundle[key] for key in ("source", "source_artifact_id", "source_hash", "validation_job_id", "validation_input_hash", "validation_result_hash", "tests", "thresholds", "overrides")}) == bundle["content_hash"],
        }
        return {"certification_id": identifier, "reproducible": all(checks.values()), "checks": checks}
