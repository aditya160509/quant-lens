from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
import httpx

from app.studio_v2.router import Router
from app.studio_v2.shared.health import StudioHealthService
from app.studio_v2.shared.observability import METRICS, StudioObservabilityMiddleware
from app.studio_v2.shared.persistence import SQLiteStore


def _healthy_manifest(*, deep: bool = False) -> dict:
    return {
        "manifest_version": 1,
        "generated_at": "2026-08-08T00:00:00Z",
        "deep_validation": deep,
        "healthy": True,
        "datasets": [
            {"id": "market_universe_daily", "status": "healthy"},
            {"id": "fama_french_5_daily", "status": "healthy"},
        ],
    }


def test_health_service_reports_live_and_ready_dependencies(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite3"
    SQLiteStore(database)
    service = StudioHealthService(database, manifest_probe=_healthy_manifest)

    live = service.liveness()
    ready = service.readiness(deep_manifest=True)

    assert live["status"] == "alive"
    assert live["uptime_seconds"] >= 0
    assert ready["status"] == "ready"
    assert ready["dependencies"]["database"]["integrity"] == "ok"
    assert ready["dependencies"]["job_runner"]["process_isolation"] is True
    assert ready["dependencies"]["manifest"]["checksum_validation"] is True
    assert ready["dependencies"]["data_files"] == {
        "status": "ready",
        "healthy": 2,
        "total": 2,
        "unhealthy_ids": [],
    }


def test_health_service_does_not_create_missing_database_and_surfaces_manifest_failure(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.sqlite3"

    def broken_manifest(*, deep: bool = False) -> dict:
        raise ValueError("checksum mismatch")

    result = StudioHealthService(
        database, manifest_probe=broken_manifest
    ).readiness()

    assert result["status"] == "not_ready"
    assert result["dependencies"]["database"]["status"] == "not_ready"
    assert result["dependencies"]["manifest"]["status"] == "not_ready"
    assert "checksum mismatch" in result["dependencies"]["manifest"]["error"]
    assert not database.exists()


def test_health_metrics_and_request_ids_are_exposed_through_typed_routes(
    tmp_path: Path,
) -> None:
    METRICS.clear()
    studio = Router(store=SQLiteStore(tmp_path / "studio.sqlite3"))
    app = FastAPI()
    app.add_middleware(StudioObservabilityMiddleware)
    app.include_router(studio)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            live = await client.get(
                "/api/v2/health/live", headers={"X-Request-ID": "health-check-1"}
            )
            ready = await client.get("/api/v2/health/ready")
            missing = await client.get(
                "/api/v2/optimizer/studies/does-not-exist",
                headers={"X-Request-ID": "missing-study-1"},
            )
            metrics = await client.get("/api/v2/health/metrics")

        assert live.status_code == 200
        assert live.headers["x-request-id"] == "health-check-1"
        assert live.json()["status"] == "alive"
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"
        assert missing.status_code == 404
        assert missing.json()["detail"]["request_id"] == "missing-study-1"
        payload = metrics.json()
        assert payload["requests"]["request_count"] >= 3
        assert (
            "GET /api/v2/optimizer/studies/{study_id}"
            in payload["requests"]["endpoints"]
        )
        assert "cache" in payload["data_access"]
        assert "scans" in payload["data_access"]
        assert payload["jobs"]["max_concurrency"] >= 1

        schema = app.openapi()
        for path, model in (
            ("/api/v2/health/live", "StudioLivenessResponse"),
            ("/api/v2/health/ready", "StudioReadinessResponse"),
            ("/api/v2/health/metrics", "StudioOperationalMetricsResponse"),
        ):
            response = schema["paths"][path]["get"]["responses"]["200"]
            assert response["content"]["application/json"]["schema"]["$ref"].endswith(
                f"/{model}"
            )
        assert schema["paths"]["/api/v2/health/ready"]["get"]["responses"][
            "503"
        ]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/StudioReadinessResponse"
        )

    try:
        asyncio.run(exercise())
    finally:
        studio.robustness_jobs.shutdown(wait=True)
