"""Low-overhead request telemetry for the Studio V2 API.

The registry intentionally stores aggregate counters only. It never retains
request bodies, query strings, authorization headers, or strategy source.
"""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
import logging
import re
from threading import Lock
import time
from typing import Any
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)
_REQUEST_ID: ContextVar = ContextVar("studio_v2_request_id", default=None)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_MAX_RECORDED_BYTES = 1_000_000_000_000


def current_request_id() -> str | None:
    """Return the request ID in the current async context, when available."""
    return _REQUEST_ID.get()


def _request_id(value: str | None) -> str:
    candidate = str(value or "").strip()
    return candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else str(uuid.uuid4())


def _bounded_bytes(value: str | None) -> int:
    try:
        return min(max(int(value or 0), 0), _MAX_RECORDED_BYTES)
    except (TypeError, ValueError):
        return 0


def failure_category(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code in {401, 403}:
        return "permission"
    if status_code == 404:
        return "not_found"
    if status_code in {408, 504}:
        return "timeout"
    if status_code == 409:
        return "conflict"
    if status_code in {413, 429}:
        return "resource_limit"
    if status_code == 422:
        return "validation"
    if status_code >= 500:
        return "server"
    return "client"


@dataclass
class EndpointAggregate:
    count: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    request_bytes: int = 0
    response_bytes: int = 0
    statuses: Counter[int] = field(default_factory=Counter)
    failure_categories: Counter[str] = field(default_factory=Counter)

    def record(
        self,
        *,
        status_code: int,
        duration_ms: float,
        request_bytes: int,
        response_bytes: int,
    ) -> None:
        category = failure_category(status_code)
        self.count += 1
        self.failures += int(status_code >= 400)
        self.total_duration_ms += duration_ms
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.request_bytes += request_bytes
        self.response_bytes += response_bytes
        self.statuses[status_code] += 1
        self.failure_categories[category] += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "failures": self.failures,
            "failure_rate": self.failures / self.count if self.count else 0.0,
            "mean_duration_ms": (
                self.total_duration_ms / self.count if self.count else 0.0
            ),
            "max_duration_ms": self.max_duration_ms,
            "request_bytes": self.request_bytes,
            "response_bytes": self.response_bytes,
            "statuses": {str(key): value for key, value in sorted(self.statuses.items())},
            "categories": dict(sorted(self.failure_categories.items())),
        }


class EndpointMetricsRegistry:
    """Thread-safe aggregate registry keyed by method and route template."""

    def __init__(self, *, max_endpoints: int = 256) -> None:
        self.max_endpoints = max(1, int(max_endpoints))
        self._lock = Lock()
        self._aggregates: dict[tuple[str, str], EndpointAggregate] = {}

    def record(
        self,
        method: str,
        route: str,
        *,
        status_code: int,
        duration_ms: float,
        request_bytes: int = 0,
        response_bytes: int = 0,
    ) -> None:
        key = (str(method).upper(), str(route))
        with self._lock:
            if key not in self._aggregates and len(self._aggregates) >= self.max_endpoints:
                key = ("OTHER", "__overflow__")
            aggregate = self._aggregates.setdefault(key, EndpointAggregate())
            aggregate.record(
                status_code=int(status_code),
                duration_ms=max(0.0, float(duration_ms)),
                request_bytes=min(max(int(request_bytes), 0), _MAX_RECORDED_BYTES),
                response_bytes=min(max(int(response_bytes), 0), _MAX_RECORDED_BYTES),
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            endpoints = {
                f"{method} {route}": aggregate.to_dict()
                for (method, route), aggregate in sorted(self._aggregates.items())
            }
        return {
            "endpoint_count": len(endpoints),
            "request_count": sum(row["count"] for row in endpoints.values()),
            "failure_count": sum(row["failures"] for row in endpoints.values()),
            "endpoints": endpoints,
        }

    def clear(self) -> None:
        with self._lock:
            self._aggregates.clear()


METRICS = EndpointMetricsRegistry()


class StudioObservabilityMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and record aggregate telemetry for Studio V2."""

    def __init__(
        self,
        app: Any,
        *,
        registry: EndpointMetricsRegistry = METRICS,
        path_prefix: str | tuple[str, ...] = ("/api/v2/", "/api/studio/"),
    ) -> None:
        super().__init__(app)
        self.registry = registry
        self.path_prefixes = (path_prefix,) if isinstance(path_prefix, str) else tuple(path_prefix)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not request.url.path.startswith(self.path_prefixes):
            return await call_next(request)
        request_id = _request_id(request.headers.get("x-request-id"))
        token = _REQUEST_ID.set(request_id)
        started = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = int(response.status_code)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1_000.0
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", None) or request.url.path
            request_bytes = _bounded_bytes(request.headers.get("content-length"))
            response_bytes = _bounded_bytes(
                response.headers.get("content-length") if response is not None else None
            )
            self.registry.record(
                request.method,
                route,
                status_code=status_code,
                duration_ms=duration_ms,
                request_bytes=request_bytes,
                response_bytes=response_bytes,
            )
            logger.info(
                "studio_v2_request %s",
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": status_code,
                        "duration_ms": round(duration_ms, 3),
                        "request_bytes": request_bytes,
                        "response_bytes": response_bytes,
                        "category": failure_category(status_code),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            _REQUEST_ID.reset(token)
