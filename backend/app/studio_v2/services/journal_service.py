"""Persistent research journal with tag indexing."""

from __future__ import annotations

import uuid
import unicodedata
from typing import Any

import pandas as pd

from ..shared.persistence import SQLiteStore, VersionConflictError


class JournalService:
    MAX_TITLE_CHARS = 300
    MAX_CONTENT_CHARS = 200_000
    MAX_TAGS = 100
    MAX_TAG_CHARS = 100
    MAX_LINKED_RUNS = 500

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()

    def list(self, tag: str | None = None, search: str | None = None,
             date_from: str | None = None, date_to: str | None = None,
             limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= int(limit) <= 500 or int(offset) < 0:
            raise ValueError("limit must be 1..500 and offset must be non-negative")
        # Filter before pagination so pages remain full and deterministic.
        rows = [self._public(row) for row in self.store.list("journal", limit=100_000)]
        if tag:
            rows = [row for row in rows if tag in row.get("tags", [])]
        if search:
            needle = search.lower()
            rows = [row for row in rows if needle in f"{row.get('title', '')} {row.get('content', '')}".lower()]
        def utc_timestamp(value: Any) -> pd.Timestamp:
            try:
                parsed = pd.Timestamp(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid journal date '{value}'") from exc
            return parsed.tz_localize("UTC") if parsed.tzinfo is None else parsed.tz_convert("UTC")
        lower = utc_timestamp(date_from) if date_from else None
        upper_inclusive = utc_timestamp(date_to) if date_to else None
        if lower is not None and upper_inclusive is not None and lower > upper_inclusive:
            raise ValueError("date_from must be on or before date_to")
        if date_from:
            rows = [row for row in rows if utc_timestamp(row.get("created_at", row.get("updated_at"))) >= lower]
        if date_to:
            upper = upper_inclusive + pd.Timedelta(days=1)
            rows = [row for row in rows if utc_timestamp(row.get("created_at", row.get("updated_at"))) < upper]
        # Immutable ascending creation order keeps offset pages stable when new
        # entries are inserted between requests. ID is the deterministic tie-break.
        rows.sort(key=lambda row: (
            utc_timestamp(row.get("created_at", row.get("updated_at"))),
            str(row.get("id", "")),
        ))
        return rows[int(offset):int(offset) + int(limit)]

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = self._validated(payload)
        identifier = str(uuid.uuid4())
        return self._public(
            self.store.put("journal", identifier, record, create_only=True)
        )

    def update(self, entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.store.get("journal", entry_id)
        patch = dict(payload)
        expected_version = patch.pop("expected_version", patch.pop("version", None))
        if expected_version is None:
            raise VersionConflictError("expected_version is required for journal updates")
        immutable = {"id", "created_at", "updated_at"}
        record.update({key: value for key, value in patch.items() if key not in immutable})
        return self._public(
            self.store.put(
                "journal",
                entry_id,
                self._validated(record),
                expected_version=int(expected_version),
            )
        )

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        public = dict(record)
        public["version"] = int(public.pop("_revision", 1))
        return public

    @classmethod
    def _normalize_tags(cls, values: Any) -> list[str]:
        if values is None:
            return []
        if not isinstance(values, (list, tuple, set)):
            raise ValueError("journal tags must be a list")
        unique: dict[str, str] = {}
        for raw in values:
            tag = unicodedata.normalize("NFC", str(raw)).strip()
            if not tag:
                continue
            if len(tag) > cls.MAX_TAG_CHARS:
                raise ValueError(f"journal tags cannot exceed {cls.MAX_TAG_CHARS} characters")
            unique.setdefault(tag.casefold(), tag)
        if len(unique) > cls.MAX_TAGS:
            raise ValueError(f"journal entries support at most {cls.MAX_TAGS} tags")
        return sorted(unique.values(), key=lambda value: (value.casefold(), value))

    @classmethod
    def _validated(cls, payload: dict[str, Any]) -> dict[str, Any]:
        title_value = payload.get("title", "")
        content_value = payload.get("content", "")
        if not isinstance(title_value, str) or not title_value.strip():
            raise ValueError("journal title is required")
        if not isinstance(content_value, str):
            raise ValueError("journal content must be text")
        title = unicodedata.normalize("NFC", title_value).strip()
        if len(title) > cls.MAX_TITLE_CHARS:
            raise ValueError(f"journal title cannot exceed {cls.MAX_TITLE_CHARS} characters")
        if len(content_value) > cls.MAX_CONTENT_CHARS:
            raise ValueError(f"journal content cannot exceed {cls.MAX_CONTENT_CHARS} characters")
        linked = payload.get("linked_run_ids", []) or []
        if not isinstance(linked, (list, tuple)):
            raise ValueError("linked_run_ids must be a list")
        linked_ids = list(dict.fromkeys(str(value).strip() for value in linked if str(value).strip()))
        if len(linked_ids) > cls.MAX_LINKED_RUNS:
            raise ValueError(
                f"journal entries support at most {cls.MAX_LINKED_RUNS} linked runs"
            )
        return {
            **payload,
            "title": title,
            "content": content_value,
            "tags": cls._normalize_tags(payload.get("tags", [])),
            "linked_run_ids": linked_ids,
        }

    def delete(self, entry_id: str) -> bool:
        if not self.store.delete("journal", entry_id):
            raise KeyError(f"journal entry '{entry_id}' not found")
        return True

    def tags(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in self.store.list("journal", limit=100_000):
            for tag in row.get("tags", []):
                counts[tag] = counts.get(tag, 0) + 1
        return [{"tag": tag, "count": count} for tag, count in sorted(counts.items())]
