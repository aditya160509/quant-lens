"""Secret-material guard for persisted Studio inputs and artifacts."""

from __future__ import annotations

import re
from typing import Any


_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("literal_credential", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|client[_-]?secret)\b\s*[:=]\s*['\"][^'\"\r\n]{16,}['\"]")),
)


class SecretMaterialError(ValueError):
    def __init__(self, location: str, category: str) -> None:
        super().__init__(f"embedded {category.replace('_', ' ')} detected at {location}; use a server-side secret reference")
        self.location = location
        self.category = category


_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESERVED_NAMES = {"", ".", ".."}


class UnsafeFilenameError(ValueError):
    pass


def validate_filename(value: Any, location: str = "filename") -> str:
    """Reject path traversal, separators, archives with traversal, and odd names.

    Reuses the upload catalog's safe-name rule (1-128 chars, no ``..`` or
    separators) so Studio export/download filenames cannot escape or inject
    shell metacharacters via ``Content-Disposition``.
    """
    name = str(value or "").strip()
    if (
        not name
        or name in _RESERVED_NAMES
        or ".." in name
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or not _SAFE_FILENAME.fullmatch(name)
    ):
        raise UnsafeFilenameError(f"unsafe {location}: must be 1-128 safe letters, numbers, dots, dashes, or underscores")
    return name


def validate_upload_meta(
    *,
    filename: Any,
    content_type: str | None = None,
    size_bytes: int | None = None,
    max_bytes: int = 64 * 1024 * 1024,
) -> str:
    """Validate upload envelope metadata before bytes are trusted."""
    name = validate_filename(filename)
    lowered = name.lower()
    if lowered.endswith((".zip", ".tar", ".tgz", ".tar.gz", ".7z")):
        raise UnsafeFilenameError("archives must be unpacked and validated entry-by-entry before acceptance")
    if size_bytes is not None and (size_bytes < 0 or size_bytes > max_bytes):
        raise UnsafeFilenameError(f"upload size {size_bytes} exceeds the {max_bytes}-byte limit")
    if content_type is not None and len(str(content_type)) > 128:
        raise UnsafeFilenameError("content type is too long")
    return name


def assert_no_secret_material_in_export(content: Any, location: str = "export") -> None:
    """Extend the write-boundary secret guard to rendered export content.

    Export bodies (HTML/JSON/CSV) are scanned with the same patterns as
    request payloads so resolved artifact text cannot smuggle credentials
    into downloads. Raises :class:`SecretMaterialError` without echoing.
    """
    if isinstance(content, (bytes, bytearray)):
        try:
            content = bytes(content).decode("utf-8", errors="replace")
        except Exception:
            return
    assert_no_secret_material(content, location)


def assert_no_secret_material(value: Any, location: str = "payload") -> None:
    if isinstance(value, str):
        for category, pattern in _PATTERNS:
            if pattern.search(value):
                raise SecretMaterialError(location, category)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert_no_secret_material(item, f"{location}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_no_secret_material(item, f"{location}[{index}]")
