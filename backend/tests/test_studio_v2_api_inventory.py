"""Contract tests for the generated Studio V2 API inventory."""

import pytest

from scripts.generate_studio_v2_api_inventory import (
    DEFAULT_OUTPUT,
    collect_routes,
    render_inventory,
    validate_routes,
)


def test_studio_v2_api_inventory_matches_registered_routes() -> None:
    http_routes, websocket_routes = collect_routes()
    validate_routes(http_routes, websocket_routes)
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_inventory()


def test_studio_v2_api_inventory_has_http_and_websocket_surfaces() -> None:
    http_routes, websocket_routes = collect_routes()
    assert http_routes
    assert websocket_routes


def test_inventory_accepts_only_the_readiness_dependency_response_exception() -> None:
    http_routes, websocket_routes = collect_routes()
    readiness = next(route for route in http_routes if route.path == "/api/v2/health/ready")
    validate_routes(http_routes, websocket_routes)

    ordinary = next(route for route in http_routes if route.path != readiness.path)
    original = ordinary.responses[500]["model"]
    ordinary.responses[500]["model"] = readiness.responses[503]["model"]
    try:
        with pytest.raises(ValueError, match="does not register ErrorResponse for 500"):
            validate_routes(http_routes, websocket_routes)
    finally:
        ordinary.responses[500]["model"] = original
