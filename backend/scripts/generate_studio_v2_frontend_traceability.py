#!/usr/bin/env python3
"""Generate and verify Studio V2 frontend-to-backend API traceability."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "STUDIO_V2_FRONTEND_API_TRACEABILITY.md"
EXTRACTOR = BACKEND_ROOT / "scripts" / "extract_studio_v2_frontend_calls.mjs"
for import_root in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)

from fastapi.routing import APIRoute, APIWebSocketRoute  # noqa: E402

from app.studio_v2 import router as router_module  # noqa: E402


@dataclass(frozen=True)
class ConsumerSurface:
    owner: str
    source_kind: str
    file: str
    line: int


@dataclass(frozen=True)
class FrontendCall:
    file: str
    line: int
    source_kind: str
    owner: str
    hook_method: str
    protocol: str
    method: str
    path: str
    request_key: str | None
    response_consumer: str
    error_consumer: str
    consumer_surfaces: tuple[ConsumerSurface, ...]
    registered: bool = False
    backend_path: str | None = None
    backend_handler: str | None = None


def _method(route: APIRoute) -> str:
    methods = sorted(route.methods or ())
    if len(methods) != 1:
        raise ValueError(f"Expected one HTTP method for {route.path}: {methods}")
    return methods[0]


def _frontend_calls() -> tuple[int, list[FrontendCall]]:
    completed = subprocess.run(
        ["node", str(EXTRACTOR)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    calls = [
        FrontendCall(
            file=row["file"],
            line=int(row["line"]),
            source_kind=row["sourceKind"],
            owner=row["owner"],
            hook_method=row["hookMethod"],
            protocol=row["protocol"],
            method=row["method"],
            path=row["path"],
            request_key=row.get("requestKey"),
            response_consumer=row["responseConsumer"],
            error_consumer=row["errorConsumer"],
            consumer_surfaces=tuple(
                ConsumerSurface(
                    owner=surface["owner"],
                    source_kind=surface["sourceKind"],
                    file=surface["file"],
                    line=int(surface["line"]),
                )
                for surface in row["consumerSurfaces"]
            ),
        )
        for row in payload["calls"]
    ]
    return int(payload["filesScanned"]), calls


def _base_path(path: str) -> str:
    return path.split("?", 1)[0]


def _segments(path: str) -> list[str]:
    return [segment for segment in _base_path(path).split("/") if segment]


def _placeholder(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _match_score(frontend_path: str, backend_path: str) -> int | None:
    frontend = _segments(frontend_path)
    backend = _segments(backend_path)
    if len(frontend) != len(backend):
        return None
    score = 0
    for client_segment, server_segment in zip(frontend, backend):
        client_dynamic = _placeholder(client_segment)
        server_dynamic = _placeholder(server_segment)
        if not client_dynamic and not server_dynamic:
            if client_segment != server_segment:
                return None
            score += 5
        elif client_dynamic and server_dynamic:
            score += 4
        elif not client_dynamic and server_dynamic:
            score += 3
        else:
            score += 1
    return score


def trace_calls() -> tuple[int, list[FrontendCall], list[tuple[str, str, str]]]:
    files_scanned, calls = _frontend_calls()
    http_routes = [route for route in router_module.router.routes if isinstance(route, APIRoute)]
    websocket_routes = [
        route for route in router_module.router.routes if isinstance(route, APIWebSocketRoute)
    ]
    candidates: dict[str, list[tuple[str, str, str]]] = {
        "HTTP": [(_method(route), route.path, route.name) for route in http_routes],
        "WS": [("WS", route.path, route.name) for route in websocket_routes],
    }

    traced: list[FrontendCall] = []
    for call in calls:
        ranked: list[tuple[int, str, str]] = []
        for method, path, handler in candidates[call.protocol]:
            if method != call.method:
                continue
            score = _match_score(call.path, path)
            if score is not None:
                ranked.append((score, path, handler))
        if not ranked:
            traced.append(call)
            continue
        best_score = max(item[0] for item in ranked)
        best = [(path, handler) for score, path, handler in ranked if score == best_score]
        if len(best) != 1:
            matches = ", ".join(path for path, _ in best)
            raise ValueError(f"Ambiguous backend match for {call.method} {call.path}: {matches}")
        backend_path, backend_handler = best[0]
        traced.append(replace(
            call,
            registered=True,
            backend_path=backend_path,
            backend_handler=backend_handler,
        ))

    all_backend = candidates["HTTP"] + candidates["WS"]
    return files_scanned, traced, all_backend


def validate_traceability(calls: Sequence[FrontendCall]) -> None:
    if not calls:
        raise ValueError("No Studio V2 frontend API calls were extracted")
    seen: set[tuple[str, int, str, str]] = set()
    for call in calls:
        source = REPOSITORY_ROOT / call.file
        if not source.is_file():
            raise ValueError(f"Trace source does not exist: {call.file}")
        if not call.path.startswith("/api/v2/"):
            raise ValueError(f"Call is outside Studio V2: {call.method} {call.path}")
        key = (call.file, call.line, call.method, call.path)
        if key in seen:
            raise ValueError(f"Duplicate extracted call: {key}")
        seen.add(key)
        if call.registered and (not call.backend_path or not call.backend_handler):
            raise ValueError(f"Registered call has incomplete backend metadata: {key}")
        if not call.consumer_surfaces:
            raise ValueError(f"Call has no in-scope component/page consumer: {key}")
        for surface in call.consumer_surfaces:
            if surface.source_kind not in {"component", "page"}:
                raise ValueError(f"Invalid consumer kind for {key}: {surface.source_kind}")
            if not (REPOSITORY_ROOT / surface.file).is_file():
                raise ValueError(f"Consumer source does not exist for {key}: {surface.file}")


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _code(value: str) -> str:
    return f"`{_escape(value)}`"


def render_traceability() -> str:
    files_scanned, calls, all_backend = trace_calls()
    validate_traceability(calls)
    registered = [call for call in calls if call.registered]
    missing = [call for call in calls if not call.registered]
    source_files = {call.file for call in calls}
    referenced_backend = {
        (call.method, call.backend_path)
        for call in registered
        if call.backend_path is not None
    }
    unique_frontend = {(call.method, call.path) for call in calls}
    unreferenced_backend = [
        (method, path, handler)
        for method, path, handler in all_backend
        if (method, path) not in referenced_backend
    ]

    lines = [
        "# Studio V2 Frontend-to-Backend API Traceability",
        "",
        "<!-- Generated by backend/scripts/generate_studio_v2_frontend_traceability.py. Do not edit by hand. -->",
        "",
        "This artifact extracts API calls from Studio pages, Studio V2 components, and Studio hooks "
        "with the TypeScript compiler AST, then matches them against the live FastAPI router. Tests, "
        "spec files, and `__tests__` directories are excluded. Dynamic paths are expanded when their "
        "finite values are visible in the source, and remaining template segments are matched to one "
        "unambiguous backend path parameter. Hook call sites are traced through their imports to every "
        "in-scope component or page that invokes the hook. The extractor rejects any in-scope "
        "`/api/v2/` path expression it cannot classify as a request, so unsupported client call "
        "patterns fail the drift check instead of silently disappearing from this table.",
        "",
        "## Verification",
        "",
        "```bash",
        "python3 backend/scripts/generate_studio_v2_frontend_traceability.py --check",
        "```",
        "",
        f"- Frontend source files scanned: **{files_scanned}**",
        f"- Source files containing API calls: **{len(source_files)}**",
        f"- Logical frontend call sites: **{len(calls)}**",
        f"- Unique frontend method/path pairs: **{len(unique_frontend)}**",
        f"- Calls matched to a registered backend route: **{len(registered)}**",
        f"- Calls without a registered backend route: **{len(missing)}**",
        f"- Distinct backend routes referenced by the frontend: **{len(referenced_backend)}**",
        f"- Registered backend routes without an in-scope frontend call: **{len(unreferenced_backend)}**",
        "",
        "`useStudioApi` parses JSON, text, and download responses, stores per-request data/error state, "
        "normalizes failures, retries only retryable requests, and rethrows terminal errors. The "
        "consumer column records the additional component or domain-store handling visible at each "
        "call site. A missing route is a concrete integration gap. An unreferenced backend route is "
        "inventory information and is not automatically a defect.",
        "",
        "## Frontend call sites",
        "",
        "| Component/page consumer | Hook or local method | Method | Frontend path | Backend status | Response/error consumer | API call source |",
        "|---|---|---|---|---|---|---|",
    ]
    for call in calls:
        backend_status = (
            f"Registered: {_code(call.backend_path or '')} → {_code(call.backend_handler or '')}"
            if call.registered
            else "**MISSING**"
        )
        consumer = f"Response: {_escape(call.response_consumer)}<br>Error: {_escape(call.error_consumer)}"
        surfaces = "<br>".join(
            f"{_code(surface.owner)} ({surface.source_kind}; "
            f"{_code(f'{surface.file}:{surface.line}')})"
            for surface in call.consumer_surfaces
        )
        hook_method = (
            f"{call.owner}.{call.hook_method}"
            if call.source_kind == "hook"
            else call.hook_method
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    surfaces,
                    _code(hook_method),
                    call.method,
                    _code(call.path),
                    backend_status,
                    consumer,
                    _code(f"{call.file}:{call.line}"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Frontend integration gaps",
            "",
        ]
    )
    if missing:
        lines.extend(
            [
                "| Method | Frontend path | Hook method | Component/page consumers | Source |",
                "|---|---|---|---|---|",
            ]
        )
        for call in missing:
            surfaces = "<br>".join(
                f"{_code(surface.owner)} ({surface.source_kind})"
                for surface in call.consumer_surfaces
            )
            lines.append(
                f"| {call.method} | {_code(call.path)} | "
                f"{_code(f'{call.owner}.{call.hook_method}')} | {surfaces} | "
                f"{_code(f'{call.file}:{call.line}')} |"
            )
    else:
        lines.append("No unmatched frontend calls were found.")

    lines.extend(
        [
            "",
            "## Registered backend routes without an in-scope frontend call",
            "",
            "| Method | Backend path | Handler |",
            "|---|---|---|",
        ]
    )
    for method, path, handler in unreferenced_backend:
        lines.append(f"| {method} | {_code(path)} | {_code(handler)} |")
    lines.append("")
    return "\n".join(lines)


def _check(output: Path, expected: str) -> int:
    if not output.exists():
        print(f"Missing generated traceability artifact: {output}", file=sys.stderr)
        return 1
    actual = output.read_text(encoding="utf-8")
    if actual == expected:
        return 0
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(output),
        tofile="generated Studio V2 frontend traceability",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the checked-in artifact is stale")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="traceability Markdown path")
    args = parser.parse_args(argv)

    expected = render_traceability()
    if args.check:
        status = _check(args.output, expected)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected, encoding="utf-8")
        status = 0
    if status == 0:
        _, calls, _ = trace_calls()
        matched = sum(call.registered for call in calls)
        verb = "Validated" if args.check else "Generated"
        print(f"{verb} {len(calls)} frontend calls: {matched} registered, {len(calls) - matched} missing.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
