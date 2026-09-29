"""P15 hardening tests: tenancy, quotas, flags, validation, diagnostics."""

import asyncio
import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services.studio import feature_flags as flags
from app.services.studio import quotas
from app.services.studio import tenancy
from app.services.studio.jobs import JobStore
from app.services.studio.security import (
    SecretMaterialError,
    UnsafeFilenameError,
    assert_no_secret_material_in_export,
    validate_filename,
    validate_upload_meta,
)


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "headers": raw})


def test_owner_hash_is_stable_scoped_and_never_echoes_raw_id() -> None:
    first = tenancy.owner_hash("alice@example.com")
    assert first == tenancy.owner_hash("alice@example.com")
    assert len(first) == 32
    assert first != tenancy.owner_hash("bob@example.com")
    assert "alice@example.com" not in first
    assert tenancy.owner_from_request(_request({"X-Owner-Id": "alice@example.com"})) == first
    assert tenancy.owner_from_request(_request({})) == tenancy.owner_hash(None)


def test_require_owner_match_allows_legacy_and_same_owner() -> None:
    tenancy.require_owner_match(None, "abc", "job")
    tenancy.require_owner_match({"job_id": "j1"}, "abc", "job")
    tenancy.require_owner_match({"job_id": "j1", "owner_hash": "abc"}, "abc", "job")
    with pytest.raises(tenancy.OwnerMismatchError):
        tenancy.require_owner_match({"job_id": "j1", "owner_hash": "abc"}, "xyz", "job")


def test_owner_sidecar_index_roundtrip(tmp_path, monkeypatch) -> None:
    from app.studio_v2.shared.persistence import SQLiteStore

    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "scoped.sqlite3"))
    store = SQLiteStore()
    digest = tenancy.owner_hash("owner-a")
    assert tenancy.indexed_visible(store, "rec_1", digest)
    tenancy.remember_owner(store, "rec_1", digest)
    tenancy.check_indexed_owner(store, "rec_1", digest, "recipe")
    assert tenancy.indexed_visible(store, "rec_1", digest)
    assert not tenancy.indexed_visible(store, "rec_1", tenancy.owner_hash("owner-b"))
    with pytest.raises(tenancy.OwnerMismatchError):
        tenancy.check_indexed_owner(store, "rec_1", tenancy.owner_hash("owner-b"), "recipe")


def test_quotas_are_centralized_with_safe_fallbacks(monkeypatch) -> None:
    assert quotas.get_quota("STUDIO_MAX_PORTFOLIO_VERSIONS") == 200
    monkeypatch.setenv("STUDIO_MAX_PORTFOLIO_VERSIONS", "7")
    assert quotas.get_quota("STUDIO_MAX_PORTFOLIO_VERSIONS") == 7
    monkeypatch.setenv("STUDIO_MAX_PORTFOLIO_VERSIONS", "not-a-number")
    assert quotas.get_quota("STUDIO_MAX_PORTFOLIO_VERSIONS") == 200
    snapshot = quotas.snapshot()
    assert snapshot["STUDIO_MAX_CONCURRENT_JOBS"] == 2
    assert snapshot["STUDIO_OWNER_QUOTA_BYTES"] == 512 * 1024 * 1024


def test_feature_flags_default_safe_with_env_override(monkeypatch) -> None:
    assert flags.snapshot() == {
        "STUDIO_RENDERER_WEBGL": False,
        "STUDIO_WORKER_EXTERNAL": False,
        "STUDIO_GPU_ENABLED": False,
        "STUDIO_PARQUET_FAST_SCAN": False,
    }
    monkeypatch.setenv("STUDIO_RENDERER_WEBGL", "1")
    assert flags.is_enabled("STUDIO_RENDERER_WEBGL") is True
    assert flags.is_enabled("STUDIO_GPU_ENABLED") is False


def test_validate_filename_rejects_traversal_and_archives() -> None:
    assert validate_filename("pfv_abc123.json") == "pfv_abc123.json"
    for bad in ["../secret", "..", "a/b", "a\\b", "", "evil.sh;rm", "recipe.tar.gz"]:
        with pytest.raises(UnsafeFilenameError):
            validate_filename(bad) if not bad.endswith(".gz") else validate_upload_meta(filename=bad)
    with pytest.raises(UnsafeFilenameError):
        validate_upload_meta(filename="ok.csv", size_bytes=10**9)


def test_export_content_is_secret_scanned_without_echo() -> None:
    assert_no_secret_material_in_export(b'{"report": "clean metrics"}')
    secret = "api_key='abcdefghijklmnop1234567890'"
    with pytest.raises(SecretMaterialError) as error:
        assert_no_secret_material_in_export(f'{{"note": "{secret}"}}', location="export.body")
    assert "abcdefghijklmnop" not in str(error.value)


def test_job_store_persists_owner_hash(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.json")
    try:
        job = store.create(job_type="monte-carlo", params={"returns": [0.01]}, owner_hash="owner-a")
        assert store.get(job["job_id"])["owner_hash"] == "owner-a"
    finally:
        store.shutdown()


def test_router_job_owner_mismatch_maps_to_403() -> None:
    from app.routers import studio

    with pytest.raises(HTTPException) as error:
        studio._require_job_owner({"job_id": "j1", "owner_hash": "aaa"}, "bbb")
    assert error.value.status_code == 403
    assert studio._require_job_owner({"job_id": "j1"}, "bbb")["job_id"] == "j1"
    with pytest.raises(HTTPException) as missing:
        studio._require_job_owner(None, "bbb")
    assert missing.value.status_code == 404


def test_health_reports_diagnostics_without_secrets(tmp_path, monkeypatch) -> None:
    from app.routers import studio

    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "health.sqlite3"))
    payload = asyncio.run(studio.health_check())
    assert payload["status"] == "ok"
    assert payload["check"] == "liveness"
    assert payload["execution"]["readiness"] == "not_checked"
    assert payload["request_id"] is None  # no middleware context in a direct call
    assert set(payload["jobs"]) == {"by_status", "max_concurrent"}
    assert "studio_portfolio_versions" in payload["storage"]
    assert payload["quotas"]["STUDIO_MAX_PORTFOLIO_VERSIONS"] == 200
    assert payload["feature_flags"]["STUDIO_GPU_ENABLED"] is False
    assert "alice" not in str(payload)


def test_upload_meta_rejects_oversize_and_bad_names() -> None:
    assert validate_upload_meta(filename="holdings.csv", content_type="text/csv", size_bytes=1024) == "holdings.csv"
    with pytest.raises(UnsafeFilenameError):
        validate_upload_meta(filename="data.zip")
    with pytest.raises(UnsafeFilenameError):
        validate_upload_meta(filename="ok.csv", size_bytes=-1)
    assert os.path.sep not in validate_filename("version_1")
