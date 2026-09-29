from __future__ import annotations

"""
Persistent Python kernel with reactive dependency tracking (F1.3-F1.6).

Supports incremental re-execution, staleness propagation, cyclic-dep
detection, LRU session caching, and checkpoint serialisation.
"""

import ast
import pickle
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from ..shared.exceptions import DependencyCycleError, DuplicateVariableError


_SAFE_GLOBALS: Dict[str, Any] = {"pd": pd, "np": np}


@lru_cache(maxsize=256)
def _parse_ast(code: str) -> ast.AST:
    """Cache immutable-by-convention syntax trees for repeated editor cells."""
    return ast.parse(code)


@lru_cache(maxsize=256)
def _compile_code(code: str) -> Any:
    return compile(code, "<studio-kernel>", "exec")


class DependencyTracker:
    """Tracks which cells define and read which variables."""

    def __init__(self) -> None:
        self.cell_variables: Dict[str, Set[str]] = {}
        self.variable_reads: Dict[str, Set[str]] = {}
        self.variable_to_cell: Dict[str, str] = {}
        self.cell_reads: Dict[str, Set[str]] = {}
        self._dep_cache: Dict[str, Set[str]] = {}
        self.stale_cells: Set[str] = set()

    def add_variable_definition(self, cell_id: str, variable_name: str) -> None:
        self.cell_variables.setdefault(cell_id, set()).add(variable_name)
        existing = self.variable_to_cell.get(variable_name)
        if existing is not None and existing != cell_id:
            raise DuplicateVariableError(variable_name, existing, cell_id)
        self.variable_to_cell[variable_name] = cell_id
        self._dep_cache.clear()

    def add_variable_read(self, cell_id: str, variable_name: str) -> None:
        self.variable_reads.setdefault(variable_name, set()).add(cell_id)
        self.cell_reads.setdefault(cell_id, set()).add(variable_name)
        self._dep_cache.clear()

    def remove_cell(self, cell_id: str) -> None:
        for variable_name in self.cell_variables.pop(cell_id, set()):
            self.variable_to_cell.pop(variable_name, None)
        for variable_name in self.cell_reads.pop(cell_id, set()):
            readers = self.variable_reads.get(variable_name, set())
            readers.discard(cell_id)
            if not readers:
                self.variable_reads.pop(variable_name, None)
        self.stale_cells.discard(cell_id)
        self._dep_cache.clear()

    def get_dependents(self, cell_id: str) -> Set[str]:
        if cell_id in self._dep_cache:
            return self._dep_cache[cell_id].copy()
        dependents: Set[str] = set()
        visited: Set[str] = set()
        queue: List[str] = [cell_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            defined = self.cell_variables.get(current, set())
            for variable_name in defined:
                readers = self.variable_reads.get(variable_name, set())
                for reader in readers:
                    if reader not in visited:
                        dependents.add(reader)
                        queue.append(reader)
        self._dep_cache[cell_id] = dependents.copy()
        return dependents

    def detect_cycles(self) -> None:
        adjacency: Dict[str, Set[str]] = {}
        for cell_id, variables in self.cell_variables.items():
            for variable_name in variables:
                readers = self.variable_reads.get(variable_name, set())
                adjacency.setdefault(cell_id, set()).update(readers)
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise DependencyCycleError(
                    f"Dependency cycle detected at cell '{node}'"
                )
            if node in visited:
                return
            visiting.add(node)
            for child in adjacency.get(node, set()):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in adjacency:
            visit(node)

    def mark_stale_downstream(self, cell_id: str) -> None:
        dependents = self.get_dependents(cell_id)
        self.stale_cells.update(dependents)
        self.stale_cells.discard(cell_id)

    def clear_stale(self, cell_id: str) -> None:
        self.stale_cells.discard(str(cell_id))

    def get_stale_cells(self) -> List[str]:
        return sorted(self.stale_cells)

    def get_graph(self) -> dict:
        edges: List[Tuple[str, str, str]] = []
        for variable_name, definer in self.variable_to_cell.items():
            for reader in self.variable_reads.get(variable_name, set()):
                if definer != reader:
                    edges.append((definer, reader, variable_name))
        return {
            "nodes": sorted(
                set(self.cell_variables) | set(self.cell_reads)
            ),
            "edges": edges,
            "stale_cells": sorted(self.stale_cells),
        }


class SessionCache:
    """Small LRU cache for session computations."""

    def __init__(self, maxsize: int = 128) -> None:
        self.maxsize = max(1, int(maxsize))
        self._data: OrderedDict[tuple, Any] = OrderedDict()

    def get(self, key: tuple) -> Any:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: tuple, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


class Session:
    """State for a single kernel session."""

    def __init__(self, session_id: str, namespace: dict) -> None:
        self.session_id = session_id
        self.namespace: Dict[str, Any] = dict(namespace)
        self.tracker = DependencyTracker()
        self.cache = SessionCache()
        self.created_at = datetime.now(timezone.utc)
        self.last_access = self.created_at

    def touch(self) -> None:
        self.last_access = datetime.now(timezone.utc)


class KernelGateway:
    """Public interface for the persistent kernel."""

    def __init__(self, checkpoint_dir: Optional[str] = None) -> None:
        self.sessions: Dict[str, Session] = {}
        self.active_session_id: Optional[str] = None
        self._lock = threading.RLock()
        self.checkpoint_dir = Path(
            checkpoint_dir or Path(__file__).resolve().parent.parent.parent
            / "checkpoints"
        )
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def start_session(
        self, session_id: str, namespace: Optional[dict] = None
    ) -> str:
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = Session(
                    session_id, namespace or {}
                )
            else:
                self.sessions[session_id].touch()
            self.active_session_id = session_id
            return session_id

    def execute_multi(self, namespace_map: dict[str, dict[str, Any]],
                      allocator_code: str = "") -> dict[str, Any]:
        """Execute strategy namespaces in one kernel while preventing collisions."""
        composite: dict[str, Any] = dict(_SAFE_GLOBALS)
        individual: dict[str, dict[str, Any]] = {}
        for prefix, namespace in namespace_map.items():
            if not prefix.isidentifier():
                raise ValueError(f"invalid namespace prefix '{prefix}'")
            isolated = dict(_SAFE_GLOBALS)
            isolated.update(namespace)
            code = isolated.pop("__code__", "")
            if code:
                exec(_compile_code(str(code)), {"__builtins__": __builtins__, **_SAFE_GLOBALS}, isolated)
            visible = {key: value for key, value in isolated.items() if not key.startswith("__") and key not in _SAFE_GLOBALS}
            individual[prefix] = visible
            composite.update({f"{prefix}_{key}": value for key, value in visible.items()})
        if allocator_code:
            exec(_compile_code(allocator_code), {"__builtins__": __builtins__, **_SAFE_GLOBALS}, composite)
        return {"individual": individual, "composite": {key: value for key, value in composite.items() if key not in _SAFE_GLOBALS and not key.startswith("__")}}

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self.sessions.get(session_id)
            if session is not None:
                session.touch()
            return session

    def _extract_definitions_and_reads(
        self, code: str
    ) -> Tuple[Set[str], Set[str]]:
        """Parse code AST to find defined and read variable names."""
        try:
            tree = _parse_ast(code)
        except SyntaxError:
            return set(), set()
        defined: Set[str] = set()
        read: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    self._collect_names(target, defined)
            elif isinstance(node, ast.AugAssign):
                self._collect_names(node.target, defined)
            elif isinstance(node, ast.AnnAssign):
                self._collect_names(node.target, defined)
            elif isinstance(node, ast.Name) and isinstance(
                node.ctx, ast.Load
            ):
                read.add(node.id)
        return defined, read

    def _collect_names(self, node: ast.AST, names: Set[str]) -> None:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for element in node.elts:
                self._collect_names(element, names)
        elif isinstance(node, ast.Starred):
            self._collect_names(node.value, names)

    def execute_code_sync(
        self, code: str, cell_id: Optional[str] = None
    ) -> dict:
        if not code.strip():
            return {"status": "empty", "ns_changes": [], "warnings": []}
        resolved = cell_id or f"cell-{uuid.uuid4().hex[:8]}"
        session_id = self.active_session_id or "default"
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                session = Session(session_id, {})
                self.sessions[session_id] = session
                self.active_session_id = session_id
            session.touch()
            tracker = session.tracker
            namespace = session.namespace

        defined, read = self._extract_definitions_and_reads(code)
        previous_values: Dict[str, Any] = {}
        for variable_name in defined:
            if variable_name in namespace:
                previous_values[variable_name] = namespace[variable_name]

        try:
            local_ns: Dict[str, Any] = {}
            compiled = _compile_code(code)
            execution_globals = dict(_SAFE_GLOBALS)
            execution_globals.update(namespace)
            exec(compiled, execution_globals, local_ns)
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "cell_id": resolved,
            }

        ns_changes: List[dict] = []
        for variable_name, value in local_ns.items():
            if variable_name.startswith("_"):
                continue
            namespace[variable_name] = value
            old_value = previous_values.get(variable_name)
            is_new = variable_name not in previous_values
            has_changed = is_new or (
                type(old_value) != type(value)
                or not isinstance(value, (int, float, str, bool, bytes))
                or old_value != value
            )
            ns_changes.append(
                {
                    "name": variable_name,
                    "type": type(value).__name__,
                    "new": True,
                    "changed": has_changed,
                }
            )
            tracker.add_variable_definition(resolved, variable_name)

        for name in read:
            tracker.add_variable_read(resolved, name)

        tracker.detect_cycles()
        tracker.clear_stale(resolved)

        return {
            "status": "ok",
            "cell_id": resolved,
            "ns_changes": ns_changes,
            "stale_cells": tracker.get_stale_cells(),
        }

    def snapshot_namespace(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                return {}
            snapshot = {}
            for key, value in session.namespace.items():
                try:
                    pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                    snapshot[key] = value
                except Exception:
                    continue
            return snapshot

    def apply_worker_result(self, session_id: str, cell_id: str, code: str,
                            changes: dict[str, Any], omitted: list[str] | None = None) -> dict[str, Any]:
        self.start_session(session_id)
        session = self.sessions[session_id]
        defined, read = self._extract_definitions_and_reads(code)
        ns_changes = []
        with self._lock:
            for name, value in changes.items():
                previous = session.namespace.get(name)
                session.namespace[name] = value
                ns_changes.append({"name": name, "type": type(value).__name__, "new": previous is None,
                                   "changed": previous is None or type(previous) is not type(value) or previous is not value})
                session.tracker.add_variable_definition(cell_id, name)
            for name in read:
                session.tracker.add_variable_read(cell_id, name)
            session.tracker.detect_cycles()
            session.tracker.mark_stale_downstream(cell_id)
            session.tracker.clear_stale(cell_id)
        return {"status": "ok", "cell_id": cell_id, "ns_changes": ns_changes,
                "stale_cells": session.tracker.get_stale_cells(),
                "warnings": [f"Variable '{name}' was not persisted because it is not serializable" for name in (omitted or [])]}

    def serialize_namespace(self) -> dict:
        session_id = self.active_session_id or "default"
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                return {}
            namespace = {
                key: value
                for key, value in session.namespace.items()
                if not key.startswith("_")
            }
            serialized: Dict[str, str] = {}
            for key, value in namespace.items():
                try:
                    serialized[key] = type(value).__name__
                except Exception:
                    serialized[key] = "unknown"
            return serialized

    def save_checkpoint(self, run_id: str, session_id: Optional[str] = None) -> str:
        resolved = session_id or self.active_session_id or "default"
        with self._lock:
            session = self.sessions.get(resolved)
            if session is None:
                raise KeyError(f"Session '{resolved}' not found")
            path = self.checkpoint_dir / f"{run_id}.pkl"
            data = {
                "namespace": session.namespace,
                "tracker": session.tracker,
                "session_id": resolved,
            }
            with open(path, "wb") as handle:
                pickle.dump(data, handle)
            return str(path)

    def restore_from_checkpoint(self, run_id: str) -> bool:
        path = self.checkpoint_dir / f"{run_id}.pkl"
        if not path.exists():
            return False
        with self._lock:
            try:
                with open(path, "rb") as handle:
                    data = pickle.load(handle)
                session_id = data.get("session_id", run_id)
                session = Session(session_id, data.get("namespace", {}))
                tracker: DependencyTracker = data.get("tracker")
                if tracker is not None:
                    session.tracker = tracker
                self.sessions[session_id] = session
                self.active_session_id = session_id
                return True
            except (pickle.UnpicklingError, OSError, EOFError):
                return False

    def get_session_timeout(self, session_id: str) -> Optional[int]:
        session = self.get_session(session_id)
        if session is None:
            return None
        elapsed = (
            datetime.now(timezone.utc) - session.last_access
        ).total_seconds()
        return max(0, 3600 - int(elapsed))

    def restart_kernel(self, session_id: Optional[str] = None) -> None:
        resolved = session_id or self.active_session_id or "default"
        with self._lock:
            self.sessions.pop(resolved, None)

    def list_sessions(self) -> List[str]:
        with self._lock:
            return list(self.sessions.keys())

    def idle_gc(self, max_idle_seconds: int = 3600) -> int:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [
                sid
                for sid, session in self.sessions.items()
                if (now - session.last_access).total_seconds()
                > max_idle_seconds
            ]
            for sid in expired:
                self.sessions.pop(sid, None)
            return len(expired)
