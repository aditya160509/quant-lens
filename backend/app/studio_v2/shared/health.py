"""Studio V2 liveness and dependency-readiness probes."""

from __future__ import annotations

from datetime import datetime, timezone
import multiprocessing
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Optional

from .data_manifest import validate_manifest
from .persistence import default_database_path


_STARTED = time.monotonic()


class StudioHealthService:
    """Probe local dependencies without running analytics or mutating state."""

    def __init__(
        self,
        database_path: Optional[str | Path] = None,
        *,
        manifest_probe: Callable[..., dict[str, Any]] = validate_manifest,
    ) -> None:
        self.database_path = Path(database_path or default_database_path())
        self.manifest_probe = manifest_probe

    @staticmethod
    def liveness() -> dict[str, Any]:
        return {
            "status": "alive",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": max(0.0, time.monotonic() - _STARTED),
        }

    def readiness(self, *, deep_manifest: bool = False) -> dict[str, Any]:
        dependencies: dict[str, dict[str, Any]] = {}
        dependencies["database"] = self._database_probe()
        dependencies["job_runner"] = self._job_runner_probe()
        dependencies.update(self._manifest_and_data_probe(deep_manifest=deep_manifest))
        ready = all(row.get("status") == "ready" for row in dependencies.values())
        return {
            "status": "ready" if ready else "not_ready",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "deep_manifest": bool(deep_manifest),
            "dependencies": dependencies,
        }

    def _database_probe(self) -> dict[str, Any]:
        path = self.database_path.expanduser().resolve()
        if not path.is_file():
            return {
                "status": "not_ready",
                "path": str(path),
                "error": "Studio V2 database file does not exist",
            }
        try:
            uri = f"file:{path}?mode=rw"
            with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
                check = str(connection.execute("PRAGMA quick_check(1)").fetchone()[0])
                journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
            return {
                "status": "ready" if check.lower() == "ok" else "not_ready",
                "path": str(path),
                "integrity": check,
                "journal_mode": journal_mode,
            }
        except (OSError, sqlite3.Error) as exc:
            return {
                "status": "not_ready",
                "path": str(path),
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            }

    @staticmethod
    def _job_runner_probe() -> dict[str, Any]:
        methods = multiprocessing.get_all_start_methods()
        return {
            "status": "ready" if methods else "not_ready",
            "durable_state": True,
            "process_isolation": bool(methods),
            "start_methods": sorted(methods),
        }

    def _manifest_and_data_probe(self, *, deep_manifest: bool) -> dict[str, Any]:
        try:
            result = self.manifest_probe(deep=bool(deep_manifest))
            datasets = list(result.get("datasets", []))
            healthy_count = sum(row.get("status") == "healthy" for row in datasets)
            manifest_ready = bool(result.get("healthy"))
            return {
                "manifest": {
                    "status": "ready" if manifest_ready else "not_ready",
                    "version": result.get("manifest_version"),
                    "generated_at": result.get("generated_at"),
                    "checksum_validation": bool(result.get("deep_validation")),
                },
                "data_files": {
                    "status": (
                        "ready" if datasets and healthy_count == len(datasets) else "not_ready"
                    ),
                    "healthy": healthy_count,
                    "total": len(datasets),
                    "unhealthy_ids": [
                        str(row.get("id"))
                        for row in datasets
                        if row.get("status") != "healthy"
                    ],
                },
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
            return {
                "manifest": {"status": "not_ready", "error": error},
                "data_files": {"status": "not_ready", "error": error},
            }
