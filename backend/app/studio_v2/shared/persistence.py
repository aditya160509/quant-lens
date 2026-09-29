"""Durable SQLite primitives shared by Studio v2 services."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_database_path() -> Path:
    configured = os.environ.get("STUDIO_V2_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "storage" / "studio_v2.sqlite3"


class VersionConflictError(ValueError):
    """Raised when an optimistic write targets an outdated document version."""


class SQLiteStore:
    """Small transactional JSON document store backed by SQLite.

    Services keep their domain logic in dedicated modules while sharing one
    durable, indexed persistence layer. JSON payloads remain schema-flexible,
    and common identity/timestamp fields stay queryable.
    """

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=30.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS studio_documents (
                    namespace TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, document_id)
                );
                CREATE INDEX IF NOT EXISTS idx_studio_documents_namespace_updated
                    ON studio_documents(namespace, updated_at DESC);
                """
            )

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload"])
        payload.setdefault("id", row["document_id"])
        payload.setdefault("created_at", row["created_at"])
        payload.setdefault("updated_at", row["updated_at"])
        payload.setdefault("_revision", 1)
        return payload

    def put(
        self,
        namespace: str,
        document_id: str,
        payload: dict[str, Any],
        *,
        create_only: bool = False,
        expected_version: Optional[int] = None,
    ) -> dict[str, Any]:
        now = utc_now()
        record = dict(payload)
        record["id"] = document_id
        with self.connection() as connection:
            # Serialize writers across processes so the version check and
            # update form one compare-and-swap transaction.
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT payload, created_at FROM studio_documents WHERE namespace=? AND document_id=?",
                (namespace, document_id),
            ).fetchone()
            if current is not None and create_only:
                raise ValueError(f"{namespace} '{document_id}' already exists")
            if current is None and expected_version is not None:
                raise VersionConflictError(
                    f"{namespace} '{document_id}' no longer exists"
                )
            current_version = (
                int(json.loads(current["payload"]).get("_revision", 1))
                if current is not None
                else 0
            )
            if expected_version is not None and int(expected_version) != current_version:
                raise VersionConflictError(
                    f"{namespace} '{document_id}' version conflict: "
                    f"expected {expected_version}, current {current_version}"
                )
            created_at = current["created_at"] if current else record.get("created_at", now)
            record["created_at"] = created_at
            record["updated_at"] = now
            record["_revision"] = current_version + 1
            connection.execute(
                """
                INSERT INTO studio_documents(namespace, document_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, document_id) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (namespace, document_id, self._encode(record), created_at, now),
            )
        return record

    def get(self, namespace: str, document_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM studio_documents WHERE namespace=? AND document_id=?",
                (namespace, document_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"{namespace} '{document_id}' not found")
        return self._decode(row)

    def maybe_get(self, namespace: str, document_id: str) -> Optional[dict[str, Any]]:
        try:
            return self.get(namespace, document_id)
        except KeyError:
            return None

    def delete(self, namespace: str, document_id: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM studio_documents WHERE namespace=? AND document_id=?",
                (namespace, document_id),
            )
        return cursor.rowcount > 0

    def list(
        self,
        namespace: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        bounded_limit = min(max(int(limit), 0), 1000)
        bounded_offset = max(int(offset), 0)
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM studio_documents
                WHERE namespace=?
                ORDER BY updated_at DESC, document_id ASC
                LIMIT ? OFFSET ?
                """,
                (namespace, bounded_limit, bounded_offset),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def count(self, namespace: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM studio_documents WHERE namespace=?",
                (namespace,),
            ).fetchone()
        return int(row["count"])

    def replace_many(
        self,
        namespace: str,
        records: Iterable[tuple[str, dict[str, Any]]],
    ) -> None:
        for document_id, payload in records:
            self.put(namespace, document_id, payload)
