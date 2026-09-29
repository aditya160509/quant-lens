from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException
import httpx

from app.studio_v2.shared.observability import (
    EndpointMetricsRegistry,
    StudioObservabilityMiddleware,
    current_request_id,
    failure_category,
)


def test_observability_uses_route_templates_and_safe_request_ids() -> None:
    registry = EndpointMetricsRegistry(max_endpoints=8)
    app = FastAPI()
    app.add_middleware(StudioObservabilityMiddleware, registry=registry)

    @app.get("/api/v2/items/{item_id}")
    async def item(item_id: str) -> dict[str, str | None]:
        return {"item_id": item_id, "request_id": current_request_id()}

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get(
                "/api/v2/items/secret-value", headers={"X-Request-ID": "client.req-1"}
            )
            second = await client.get(
                "/api/v2/items/another-secret", headers={"X-Request-ID": "bad id\nvalue"}
            )
        assert first.headers["x-request-id"] == "client.req-1"
        assert first.json()["request_id"] == "client.req-1"
        assert second.headers["x-request-id"] != "bad id\nvalue"
        assert len(second.headers["x-request-id"]) == 36

    asyncio.run(exercise())
    snapshot = registry.snapshot()
    assert snapshot["request_count"] == 2
    assert snapshot["failure_count"] == 0
    assert list(snapshot["endpoints"]) == ["GET /api/v2/items/{item_id}"]
    assert "secret-value" not in str(snapshot)


def test_observability_classifies_errors_and_records_only_sizes() -> None:
    registry = EndpointMetricsRegistry(max_endpoints=8)
    app = FastAPI()
    app.add_middleware(StudioObservabilityMiddleware, registry=registry)

    @app.post("/api/v2/rejected")
    async def rejected(payload: dict) -> None:
        assert current_request_id()
        raise HTTPException(422, detail="invalid payload")

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v2/rejected", json={"strategy_source": "TOP-SECRET-CODE"}
            )
        assert response.status_code == 422
        assert response.headers["x-request-id"]

    asyncio.run(exercise())
    row = registry.snapshot()["endpoints"]["POST /api/v2/rejected"]
    assert row["count"] == 1
    assert row["failures"] == 1
    assert row["categories"] == {"validation": 1}
    assert row["request_bytes"] > 0
    assert "TOP-SECRET-CODE" not in str(row)
    assert failure_category(401) == "permission"
    assert failure_category(429) == "resource_limit"
    assert failure_category(503) == "server"


def test_observability_registry_bounds_endpoint_cardinality() -> None:
    registry = EndpointMetricsRegistry(max_endpoints=1)
    registry.record("GET", "/one", status_code=200, duration_ms=1)
    registry.record("GET", "/two", status_code=500, duration_ms=2)
    registry.record("POST", "/three", status_code=503, duration_ms=3)

    snapshot = registry.snapshot()
    assert snapshot["endpoint_count"] == 2
    assert snapshot["request_count"] == 3
    assert snapshot["failure_count"] == 2
    assert snapshot["endpoints"]["OTHER __overflow__"]["count"] == 2


def test_observability_covers_canonical_studio_without_recording_artifact_ids() -> None:
    registry = EndpointMetricsRegistry(max_endpoints=8)
    app = FastAPI()
    app.add_middleware(StudioObservabilityMiddleware, registry=registry)

    @app.get("/api/studio/reports/recipes/{recipe_id}")
    async def recipe(recipe_id: str) -> dict[str, str | None]:
        return {"recipe_id": recipe_id, "request_id": current_request_id()}

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/studio/reports/recipes/private-artifact-id", headers={"X-Request-ID": "studio-request-1"})
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "studio-request-1"
        assert response.json()["request_id"] == "studio-request-1"

    asyncio.run(exercise())
    snapshot = registry.snapshot()
    assert list(snapshot["endpoints"]) == ["GET /api/studio/reports/recipes/{recipe_id}"]
    assert "private-artifact-id" not in str(snapshot)
