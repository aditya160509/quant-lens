"""Per-owner scoping for Studio records — P15 hardening.

Reuses the owner-hash pattern from the upload catalog
(`app/studio_v2/data_studio/catalog.py::_owner_key`): raw owner ids are
never used as directory keys or echoed; only a truncated SHA-256 digest is
stored and compared.

Backward compatibility: records written before P15 carry no ``owner_hash``
and are treated as legacy shared records readable by any caller. New writes
always stamp ``owner_hash``; reads of stamped records from a different owner
raise :class:`OwnerMismatchError` (mapped to 403 by routers).
"""

from __future__ import annotations

import hashlib

from fastapi import Request


class OwnerMismatchError(PermissionError):
    def __init__(self, location: str = "record") -> None:
        super().__init__(f"record at {location} belongs to a different owner")
        self.location = location


def owner_hash(owner_id: str | None) -> str:
    value = str(owner_id or "").strip() or "anonymous"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def owner_from_request(request: Request | None) -> str:
    """Resolve the caller digest from ``X-Owner-Id`` (never echoed)."""
    if request is None:
        return owner_hash(None)
    header = request.headers.get("X-Owner-Id") if hasattr(request, "headers") else None
    return owner_hash(header)


def stamp_owner(record: dict, digest: str) -> dict:
    record["owner_hash"] = digest
    return record


def require_owner_match(record: dict | None, digest: str, location: str = "record") -> None:
    """Enforce ownership; legacy records without a stamp remain readable."""
    if record is None:
        return
    stamped = record.get("owner_hash")
    if not stamped:
        return
    if stamped != digest:
        raise OwnerMismatchError(location)


def owner_matches(record: dict | None, digest: str) -> bool:
    if record is None:
        return False
    stamped = record.get("owner_hash")
    if not stamped:
        return True
    return stamped == digest


OWNER_INDEX = "studio_owner_index"


def remember_owner(store: object, record_id: str, digest: str) -> None:
    """Record the owner of a service-layer document without mutating it.

    Services (paper/recipes/notes/certs) own their payload schemas; the
    router keeps a sidecar ``record_id -> owner_hash`` entry so ownership
    can be enforced and listed without schema migrations.
    """
    put = getattr(store, "put", None)
    if put is None:
        return
    put(OWNER_INDEX, str(record_id), {"record_id": str(record_id), "owner_hash": digest})


def _indexed_owner(store: object, record_id: str) -> str | None:
    maybe_get = getattr(store, "maybe_get", None)
    if maybe_get is None:
        return None
    try:
        entry = maybe_get(OWNER_INDEX, str(record_id))
    except Exception:
        return None
    if not isinstance(entry, dict):
        return None
    return entry.get("owner_hash")


def check_indexed_owner(store: object, record_id: str, digest: str, location: str = "record") -> None:
    stamped = _indexed_owner(store, record_id)
    if stamped and stamped != digest:
        raise OwnerMismatchError(location)


def indexed_visible(store: object, record_id: str, digest: str) -> bool:
    stamped = _indexed_owner(store, record_id)
    return not stamped or stamped == digest
