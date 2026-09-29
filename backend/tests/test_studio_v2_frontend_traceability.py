"""Drift tests for Studio V2 frontend-to-backend API traceability."""

from scripts.generate_studio_v2_frontend_traceability import (
    DEFAULT_OUTPUT,
    render_traceability,
    trace_calls,
    validate_traceability,
)


def test_studio_v2_frontend_traceability_matches_sources_and_router() -> None:
    _, calls, _ = trace_calls()
    validate_traceability(calls)
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_traceability()


def test_studio_v2_frontend_traceability_classifies_every_call() -> None:
    _, calls, _ = trace_calls()
    assert calls
    assert all(call.registered or call.backend_path is None for call in calls)
    assert all(call.consumer_surfaces for call in calls)
    assert all(
        surface.source_kind in {"component", "page"}
        for call in calls
        for surface in call.consumer_surfaces
    )
