"""Persistent personal snippet library."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from ..shared.persistence import SQLiteStore


class SnippetRepository:
    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self.store = store or SQLiteStore()

    def list(self, tag: Optional[str] = None) -> list[dict[str, Any]]:
        rows = self.store.list("snippets", limit=1000)
        if tag:
            rows = [row for row in rows if tag in row.get("tags", [])]
        return rows

    def get(self, snippet_id: str) -> dict[str, Any]:
        return self.store.get("snippets", snippet_id)

    def create(
        self,
        name: str,
        code: str,
        language: str = "python",
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if not name.strip() or not code.strip():
            raise ValueError("snippet name and code are required")
        snippet_id = f"snp_{uuid.uuid4().hex[:12]}"
        return self.store.put(
            "snippets",
            snippet_id,
            {
                "name": name.strip(),
                "code": code,
                "language": language.strip().lower() or "python",
                "tags": sorted(set(tags or [])),
            },
            create_only=True,
        )

    def update(self, snippet_id: str, **changes: Any) -> dict[str, Any]:
        record = self.get(snippet_id)
        for key in ("name", "code", "language", "tags"):
            if key in changes and changes[key] is not None:
                record[key] = sorted(set(changes[key])) if key == "tags" else changes[key]
        if not str(record["name"]).strip() or not str(record["code"]).strip():
            raise ValueError("snippet name and code cannot be empty")
        return self.store.put("snippets", snippet_id, record)

    def delete(self, snippet_id: str) -> dict[str, Any]:
        if not self.store.delete("snippets", snippet_id):
            raise KeyError(f"snippet '{snippet_id}' not found")
        return {"deleted": True, "id": snippet_id}
