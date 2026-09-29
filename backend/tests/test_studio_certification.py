from pathlib import Path

import pytest

from app.services.studio.certification import CertificationError, CertificationService
from app.services.studio.jobs import JobStore
from app.studio_v2.shared.persistence import SQLiteStore


def test_certification_is_content_addressed_and_reproducible(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "cert.sqlite3")
    store.put("studio_portfolio_versions", "pfv_1", {"version_id": "pfv_1", "artifact_id": "portfolio_1", "portfolio": {"metrics": {"sharpe": 1.0}}})
    jobs = JobStore(tmp_path / "jobs.json")
    try:
        job = jobs.create(job_type="walk-forward", params={"source_artifact_id": "portfolio_1", "returns": [0.01] * 100})
        jobs.run_sync(job["job_id"], lambda: {"verdict": {"status": "PASSED"}})
        service = CertificationService(store, jobs)
        kwargs = {
            "source": {"type": "portfolio_version", "id": "pfv_1"}, "validation_job_id": job["job_id"],
            "tests": [{"name": "walk-forward", "status": "passed"}, {"name": "borrow", "status": "skipped", "reason": "borrow data not supplied"}],
            "thresholds": {"minimum_oos_sharpe": 0.5}, "overrides": [],
        }
        first = service.create(**kwargs); second = service.create(**kwargs)
        assert first["certification_id"] == second["certification_id"]
        assert service.reproduce(first["certification_id"])["reproducible"] is True
        source = store.get("studio_portfolio_versions", "pfv_1"); source["portfolio"]["metrics"]["sharpe"] = 2.0
        store.put("studio_portfolio_versions", "pfv_1", source, expected_version=source["_revision"])
        assert service.reproduce(first["certification_id"])["checks"]["source_hash"] is False
    finally: jobs.shutdown()


def test_certification_requires_reasons_for_skipped_tests(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "cert.sqlite3")
    store.put("studio_portfolio_versions", "pfv_1", {"version_id": "pfv_1", "artifact_id": "portfolio_1"})
    jobs = JobStore(tmp_path / "jobs.json")
    try:
        job = jobs.create(job_type="walk-forward", params={"source_artifact_id": "portfolio_1", "returns": [0.01] * 100})
        jobs.run_sync(job["job_id"], lambda: {"verdict": {"status": "PASSED"}})
        with pytest.raises(CertificationError, match="reason"):
            CertificationService(store, jobs).create(source={"type": "portfolio_version", "id": "pfv_1"}, validation_job_id=job["job_id"], tests=[{"name": "borrow", "status": "skipped"}], thresholds={}, overrides=[])
    finally: jobs.shutdown()
