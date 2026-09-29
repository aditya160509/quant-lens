#!/usr/bin/env python3
"""Generate and verify the Studio V2 API inventory from registered routes.

The inventory intentionally reads FastAPI's runtime route objects instead of
duplicating ``Router._register_routes``.  Run with ``--check`` in CI to fail
when the checked-in document no longer matches the application surface.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import inspect
import json
import sys
import types
import typing
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence, get_args, get_origin


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "STUDIO_V2_API_INVENTORY.md"
for import_root in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)

from fastapi.routing import APIRoute, APIWebSocketRoute  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.studio_v2 import router as router_module  # noqa: E402


HTTP_METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
REQUIRED_ERROR_STATUSES = {400, 403, 404, 409, 422, 500}
UNDEFINED_TYPE_NAMES = {"PydanticUndefinedType", "UndefinedType"}
NON_ERROR_RESPONSE_MODELS = {
    ("GET", "/api/v2/health/ready", 503): "StudioReadinessResponse",
}


def _is_undefined(value: Any) -> bool:
    return type(value).__name__ in UNDEFINED_TYPE_NAMES


def _type_name(annotation: Any) -> str:
    """Render Python/Pydantic annotations without module-path noise."""

    if annotation is Any:
        return "Any"
    if annotation in {None, type(None)}:
        return "null"

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is typing.Annotated:
        return _type_name(args[0])
    union_origins = {typing.Union}
    union_type = getattr(types, "UnionType", None)
    if union_type is not None:
        union_origins.add(union_type)
    if origin in union_origins:
        non_null = [arg for arg in args if arg is not type(None)]
        if len(non_null) + 1 == len(args):
            return f"{_type_name(non_null[0])} | null"
        return " | ".join(_type_name(arg) for arg in args)
    if origin is typing.Literal:
        return "Literal[" + ", ".join(json.dumps(arg) for arg in args) + "]"
    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin).replace("typing.", ""))
        return f"{origin_name}[{', '.join(_type_name(arg) for arg in args)}]"
    if inspect.isclass(annotation):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _default_name(value: Any) -> str:
    if _is_undefined(value):
        return "required"
    if isinstance(value, BaseModel):
        return "default object"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple, dict)):
        rendered = json.dumps(value, sort_keys=True, default=str)
        return rendered if len(rendered) <= 80 else "default value"
    return "default value"


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _code(value: str) -> str:
    return f"`{_escape_cell(value)}`"


def _field_required(field: Any) -> bool:
    required = getattr(field, "required", None)
    if required is not None:
        return bool(required)
    checker = getattr(field, "is_required", None)
    return bool(checker()) if checker is not None else _is_undefined(getattr(field, "default", None))


def _field_annotation(field: Any) -> Any:
    return getattr(field, "annotation", None) or getattr(field, "type_", Any)


def _parameter_text(field: Any) -> str:
    annotation = _type_name(getattr(field, "type_", Any))
    if _field_required(field):
        return f"{_code(field.name)}: {_code(annotation)} (required)"
    return f"{_code(field.name)}: {_code(annotation)} = {_code(_default_name(field.default))}"


def _domain(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[:2] != ["api", "v2"]:
        raise ValueError(f"Studio V2 route is outside /api/v2: {path}")
    return parts[2]


def _http_method(route: APIRoute) -> str:
    methods = sorted(route.methods or (), key=lambda method: HTTP_METHOD_ORDER.get(method, 99))
    if len(methods) != 1:
        raise ValueError(f"Expected exactly one method for {route.path}; found {methods}")
    return methods[0]


def _request_text(route: APIRoute) -> str:
    parts: list[str] = []
    if route.dependant.path_params:
        parts.append("Path: " + "; ".join(_parameter_text(field) for field in route.dependant.path_params))
    if route.dependant.query_params:
        parts.append("Query: " + "; ".join(_parameter_text(field) for field in route.dependant.query_params))
    if route.dependant.body_params:
        media_type = getattr(getattr(route.body_field, "field_info", None), "media_type", None)
        if media_type == "application/json" and len(route.dependant.body_params) == 1:
            field = route.dependant.body_params[0]
            body_type = _type_name(getattr(field, "type_", Any))
            requirement = "required" if _field_required(field) else "optional"
            parts.append(f"Body: {_code(body_type)} ({requirement} JSON body)")
        else:
            bodies = "; ".join(_parameter_text(field) for field in route.dependant.body_params)
            parts.append(f"Body ({_code(media_type or 'encoded form')}): {bodies}")
    if route.dependant.dependencies:
        dependencies = []
        for dependency in route.dependant.dependencies:
            call_name = getattr(dependency.call, "__name__", type(dependency.call).__name__)
            dependencies.append(f"{_code(dependency.name or 'dependency')} via {_code(call_name)}")
        parts.append("Dependency: " + "; ".join(dependencies))
    if not parts:
        return "None"
    return "<br>".join(parts)


def _registered_errors(route: APIRoute) -> tuple[int, ...]:
    statuses: list[int] = []
    for raw_status in route.responses:
        try:
            statuses.append(int(raw_status))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(statuses))


def _registered_response_model(route: APIRoute, status: int) -> Any:
    response = route.responses.get(status) or route.responses.get(str(status)) or {}
    return response.get("model")


def _error_text(route: APIRoute, explicit_errors: dict[str, list[tuple[int, str]]]) -> str:
    error_statuses: list[int] = []
    alternate_statuses: list[str] = []
    for status in _registered_errors(route):
        model_name = getattr(_registered_response_model(route, status), "__name__", "unknown")
        if model_name == "ErrorResponse":
            error_statuses.append(status)
        else:
            alternate_statuses.append(f"{status} via {_code(model_name)}")
    text = f"{_code('/'.join(str(status) for status in error_statuses))} via {_code('ErrorResponse')}"
    if alternate_statuses:
        text += "<br>Alternate responses: " + ", ".join(alternate_statuses)
    details = explicit_errors.get(route.name, [])
    if details:
        rendered = ", ".join(
            f"{status} {_code(detail)}" if detail else str(status) for status, detail in details
        )
        text += f"<br>Direct handler errors: {rendered}"
    return text


def _ast_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Tuple):
        return ", ".join(_ast_name(item) for item in node.elts)
    return "unknown"


def _literal_int(node: ast.AST | None) -> int | None:
    if node is None:
        return None
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
    return int(value) if isinstance(value, int) else None


def _detail_label(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Call) and _ast_name(node.func).endswith("_error_detail"):
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return str(node.args[0].value)
        return "structured detail"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return "custom detail"


def _http_exception(raise_node: ast.Raise) -> tuple[int, str] | None:
    call = raise_node.exc
    if not isinstance(call, ast.Call) or not _ast_name(call.func).endswith("HTTPException"):
        return None
    status_node = call.args[0] if call.args else None
    detail_node = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "status_code":
            status_node = keyword.value
        elif keyword.arg == "detail":
            detail_node = keyword.value
    status = _literal_int(status_node)
    return (status, _detail_label(detail_node)) if status is not None else None


def _router_ast() -> ast.Module:
    source_path = Path(inspect.getsourcefile(router_module) or router_module.__file__)
    return ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))


def _direct_handler_errors(tree: ast.Module) -> dict[str, list[tuple[int, str]]]:
    errors: dict[str, list[tuple[int, str]]] = defaultdict(list)
    router_class = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Router"),
        None,
    )
    if router_class is None:
        raise ValueError("Could not find the Studio V2 Router class")
    for function in router_class.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Raise):
                continue
            error = _http_exception(node)
            if error is not None and error not in errors[function.name]:
                errors[function.name].append(error)
    return dict(errors)


def _guard_mappings(tree: ast.Module) -> list[tuple[str, int, str]]:
    guarded = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_guarded"
        ),
        None,
    )
    if guarded is None:
        raise ValueError("Could not find the Studio V2 exception guard")
    mappings: list[tuple[str, int, str]] = []
    for handler in (node for node in ast.walk(guarded) if isinstance(node, ast.ExceptHandler)):
        exception_name = _ast_name(handler.type)
        mapped: tuple[int, str] | None = None
        for raise_node in (node for node in ast.walk(handler) if isinstance(node, ast.Raise)):
            mapped = _http_exception(raise_node)
            if mapped is not None:
                break
        if mapped is not None:
            mappings.append((exception_name, mapped[0], mapped[1]))
    return mappings


def _iter_model_types(annotation: Any) -> Iterable[type[BaseModel]]:
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        yield annotation
    for argument in get_args(annotation):
        yield from _iter_model_types(argument)


def _body_model_catalog(routes: Sequence[APIRoute]) -> tuple[list[type[BaseModel]], dict[str, set[str]]]:
    models: dict[str, type[BaseModel]] = {}
    usage: dict[str, set[str]] = defaultdict(set)
    queue: list[type[BaseModel]] = []
    for route in routes:
        for field in route.dependant.body_params:
            for model in _iter_model_types(getattr(field, "type_", Any)):
                usage[model.__name__].add(f"{_http_method(route)} {route.path}")
                queue.append(model)
    while queue:
        model = queue.pop()
        if model.__name__ in models:
            continue
        models[model.__name__] = model
        for field in model.model_fields.values():
            for nested in _iter_model_types(_field_annotation(field)):
                usage[nested.__name__].add(f"nested in {model.__name__}")
                queue.append(nested)
    return [models[name] for name in sorted(models)], usage


def _model_field_text(name: str, field: Any) -> str:
    annotation = _type_name(_field_annotation(field))
    if _field_required(field):
        return f"{_code(name)}: {_code(annotation)}"
    factory = getattr(field, "default_factory", None)
    default = "factory" if factory is not None else _default_name(getattr(field, "default", None))
    return f"{_code(name)}: {_code(annotation)} = {_code(default)}"


def _model_extra_policy(model: type[BaseModel]) -> str:
    config = getattr(model, "model_config", {})
    extra = config.get("extra") if hasattr(config, "get") else None
    return str(extra or "ignore")


def collect_routes() -> tuple[list[APIRoute], list[APIWebSocketRoute]]:
    """Return the current registered Studio V2 routes in registration order."""

    http_routes = [route for route in router_module.router.routes if isinstance(route, APIRoute)]
    websocket_routes = [
        route for route in router_module.router.routes if isinstance(route, APIWebSocketRoute)
    ]
    return http_routes, websocket_routes


def validate_routes(http_routes: Sequence[APIRoute], websocket_routes: Sequence[APIWebSocketRoute]) -> None:
    """Fail fast on incomplete or ambiguous route metadata."""

    seen_http: set[tuple[str, str]] = set()
    for route in http_routes:
        method = _http_method(route)
        key = (method, route.path)
        if key in seen_http:
            raise ValueError(f"Duplicate HTTP operation: {method} {route.path}")
        seen_http.add(key)
        _domain(route.path)
        if route.response_model is None:
            raise ValueError(f"Missing response model: {method} {route.path}")
        registered_errors = set(_registered_errors(route))
        missing_errors = REQUIRED_ERROR_STATUSES - registered_errors
        if missing_errors:
            raise ValueError(
                f"Missing baseline error schemas for {method} {route.path}: {sorted(missing_errors)}"
            )
        for status in registered_errors:
            model = _registered_response_model(route, status)
            model_name = getattr(model, "__name__", None)
            allowed_model = NON_ERROR_RESPONSE_MODELS.get((method, route.path, status))
            if model_name != "ErrorResponse" and model_name != allowed_model:
                raise ValueError(
                    f"{method} {route.path} does not register ErrorResponse for {status}"
                )
        placeholders = {
            part[1:-1] for part in route.path.split("/") if part.startswith("{") and part.endswith("}")
        }
        parameters = {field.name for field in route.dependant.path_params}
        if placeholders != parameters:
            raise ValueError(
                f"Path parameter mismatch for {method} {route.path}: {placeholders} != {parameters}"
            )

    seen_websockets: set[str] = set()
    for route in websocket_routes:
        _domain(route.path)
        if route.path in seen_websockets:
            raise ValueError(f"Duplicate WebSocket route: {route.path}")
        seen_websockets.add(route.path)


def _websocket_request(route: APIWebSocketRoute) -> str:
    parts: list[str] = []
    if route.dependant.path_params:
        parts.append("Path: " + "; ".join(_parameter_text(field) for field in route.dependant.path_params))
    source = inspect.getsource(route.endpoint)
    if 'query_params.get("token"' in source or "query_params.get('token'" in source:
        parts.append(f"Query: {_code('token')}: {_code('str')} (required invite token)")
    return "<br>".join(parts) or "None"


def render_inventory() -> str:
    http_routes, websocket_routes = collect_routes()
    validate_routes(http_routes, websocket_routes)
    tree = _router_ast()
    direct_errors = _direct_handler_errors(tree)
    guard_mappings = _guard_mappings(tree)
    models, model_usage = _body_model_catalog(http_routes)

    registered_error_statuses = sorted({
        status for route in http_routes for status in _registered_errors(route)
    })

    method_counts = Counter(_http_method(route) for route in http_routes)
    domain_counts: "OrderedDict[str, int]" = OrderedDict()
    grouped: "OrderedDict[str, list[APIRoute]]" = OrderedDict()
    for route in http_routes:
        domain = _domain(route.path)
        grouped.setdefault(domain, []).append(route)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    for route in websocket_routes:
        domain = _domain(route.path)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    lines = [
        "# Studio V2 API Inventory",
        "",
        "<!-- Generated by backend/scripts/generate_studio_v2_api_inventory.py. Do not edit by hand. -->",
        "",
        "This inventory is generated from the FastAPI route objects registered by "
        "`app.studio_v2.router.router`. It records the runtime path, method, handler, "
        "request surface, declared response model, and registered error schemas. A handler that "
        "returns `Response` or `StreamingResponse` bypasses response-model serialization even though "
        "the declared model remains listed here.",
        "",
        "## Verification",
        "",
        "```bash",
        "python3 backend/scripts/generate_studio_v2_api_inventory.py --check",
        "```",
        "",
        f"- HTTP operations: **{len(http_routes)}**",
        f"- WebSocket routes: **{len(websocket_routes)}**",
        f"- Total registered Studio V2 routes: **{len(http_routes) + len(websocket_routes)}**",
        "- HTTP methods: " + ", ".join(
            f"{method} {method_counts[method]}"
            for method in sorted(method_counts, key=lambda value: HTTP_METHOD_ORDER.get(value, 99))
        ),
        "- Domains: " + ", ".join(f"{domain} {count}" for domain, count in domain_counts.items()),
        "",
        "The verifier also rejects duplicate operations, routes outside `/api/v2`, missing response "
        "models, incomplete `ErrorResponse` registrations, and path-template/parameter mismatches.",
        "",
        "## Shared HTTP error behavior",
        "",
        "Every HTTP operation registers the baseline `ErrorResponse` set 400, 403, 404, 409, 422, "
        "and 500. Route-specific statuses currently present across the surface are: "
        + ", ".join(str(status) for status in registered_error_statuses)
        + ". "
        "FastAPI request validation runs before the handler and returns 422 with its validation-detail "
        "list. Existing `HTTPException` instances pass through unchanged, including handler-specific "
        "status codes and details.",
        "",
        "The readiness route additionally declares 503 with `StudioReadinessResponse`, preserving "
        "dependency diagnostics when the service is alive but unavailable for traffic.",
        "",
        "The shared handler guard maps uncaught exceptions as follows:",
        "",
        "| Source exception | Status | Structured `detail.code` |",
        "|---|---:|---|",
    ]
    for exception_name, status, detail in guard_mappings:
        lines.append(f"| {_code(exception_name)} | {status} | {_code(detail)} |")
    lines.extend(
        [
            "",
            "A documented 400 schema is registered on every HTTP operation, but the shared guard has "
            "no generic 400 conversion. A handler must raise a 400 `HTTPException` explicitly for that "
            "response to occur.",
            "",
            "## HTTP routes",
            "",
        ]
    )

    for domain, routes in grouped.items():
        title = domain.replace("-", " ").title()
        lines.extend(
            [
                f"### {title} ({len(routes)} HTTP operations)",
                "",
                "| Method | Path | Handler | Request | Declared response model | Errors |",
                "|---|---|---|---|---|---|",
            ]
        )
        for route in routes:
            method = _http_method(route)
            response_model = _type_name(route.response_model)
            lines.append(
                "| "
                + " | ".join(
                    [
                        method,
                        _code(route.path),
                        _code(route.name),
                        _request_text(route),
                        _code(response_model),
                        _error_text(route, direct_errors),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## WebSocket routes",
            "",
            "WebSockets do not register HTTP response models or the shared HTTP error schemas. The "
            "collaboration handler accepts a one-time invite token, emits a `session_snapshot`, accepts "
            "JSON object messages, broadcasts participant and editing events, treats "
            "`WebSocketDisconnect` as a normal disconnect, and always removes a joined participant in "
            "its cleanup path.",
            "",
            "| Domain | Path | Handler | Handshake request | Response/error contract |",
            "|---|---|---|---|---|",
        ]
    )
    for route in websocket_routes:
        lines.append(
            "| "
            + " | ".join(
                [
                    _domain(route.path),
                    _code(route.path),
                    _code(route.name),
                    _websocket_request(route),
                    "JSON frames; no FastAPI response model or registered HTTP error schema",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## JSON request body contracts",
            "",
            "These are the named Pydantic models reachable from registered JSON bodies. Field limits, "
            "patterns, validators, and other constraints remain authoritative in `contracts.py` and "
            "the generated JSON Schema; this compact view records field types, requiredness, defaults, "
            "and unknown-key policy.",
            "",
            "| Model | Used by | Required fields | Defaulted or nullable fields | Unknown keys |",
            "|---|---|---|---|---|",
        ]
    )
    for model in models:
        required: list[str] = []
        defaulted: list[str] = []
        for name, field in model.model_fields.items():
            target = required if _field_required(field) else defaulted
            target.append(_model_field_text(name, field))
        usage_text = "<br>".join(_code(value) for value in sorted(model_usage[model.__name__]))
        lines.append(
            "| "
            + " | ".join(
                [
                    _code(model.__name__),
                    usage_text,
                    "<br>".join(required) or "None",
                    "<br>".join(defaulted) or "None",
                    _code(_model_extra_policy(model)),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _check(output: Path, expected: str) -> int:
    if not output.exists():
        print(f"Missing generated inventory: {output}", file=sys.stderr)
        return 1
    actual = output.read_text(encoding="utf-8")
    if actual == expected:
        return 0
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(output),
        tofile="generated Studio V2 inventory",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the checked-in inventory is stale")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="inventory Markdown path")
    args = parser.parse_args(argv)

    expected = render_inventory()
    if args.check:
        status = _check(args.output, expected)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected, encoding="utf-8")
        status = 0

    if status == 0:
        http_routes, websocket_routes = collect_routes()
        verb = "Validated" if args.check else "Generated"
        print(
            f"{verb} {len(http_routes)} HTTP operations and {len(websocket_routes)} WebSocket route "
            f"({len(http_routes) + len(websocket_routes)} total)."
        )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
