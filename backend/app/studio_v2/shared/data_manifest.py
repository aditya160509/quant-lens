"""Versioned dataset manifests and fast structural validation."""

from __future__ import annotations

from functools import lru_cache
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from typing import Any, Iterable
import uuid

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = ROOT / "backend/data/manifests/studio_v2.json"
_ENTRY_KEYS = frozenset(
    {
        "id",
        "path",
        "rows",
        "size_bytes",
        "required_columns",
        "sha256",
        "provenance",
    }
)
_PROVENANCE_KEYS = frozenset(
    {
        "source",
        "license_status",
        "transformation_version",
        "generation_command",
        "point_in_time_policy",
        "adjustment_policy",
    }
)
_REFRESH_LOCK = RLock()


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("manifest_version") != 1 or not isinstance(payload.get("datasets"), list):
        raise ValueError("Studio V2 dataset manifest has an unsupported structure")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_path(entry: dict[str, Any], root: Path) -> Path:
    missing = sorted(_ENTRY_KEYS.difference(entry))
    if missing:
        raise ValueError(f"Manifest dataset entry is missing keys: {missing}")
    relative = Path(str(entry["path"]))
    if relative.is_absolute():
        raise ValueError("Manifest dataset paths must be relative to the project root")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("Manifest dataset path escapes the project root")
    return resolved


def _date_text(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _parquet_date_bounds(parquet: pq.ParquetFile, column: str) -> tuple[str, str]:
    names = parquet.schema_arrow.names
    if column not in names:
        return "", ""
    column_index = names.index(column)
    minima: list[str] = []
    maxima: list[str] = []
    for row_group_index in range(parquet.metadata.num_row_groups):
        statistics = parquet.metadata.row_group(row_group_index).column(column_index).statistics
        if statistics is None or not statistics.has_min_max:
            continue
        minimum, maximum = _date_text(statistics.min), _date_text(statistics.max)
        if minimum:
            minima.append(minimum)
        if maximum:
            maxima.append(maximum)
    return (min(minima) if minima else "", max(maxima) if maxima else "")


def _schema_fingerprint(parquet: pq.ParquetFile) -> str:
    schema_bytes = parquet.schema_arrow.remove_metadata().serialize().to_pybytes()
    return hashlib.sha256(schema_bytes).hexdigest()


def _write_manifest_atomic(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=manifest_path.parent,
        prefix=f".{manifest_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, manifest_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_dataset(entry: dict[str, Any], *, deep: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    checksum_verified = False
    checksum_match: bool | None = None
    try:
        path = _resolved_path(entry, ROOT)
    except (TypeError, ValueError) as exc:
        return {
            **entry,
            "status": "invalid",
            "errors": [str(exc)],
            "checksum_verified": False,
            "checksum_match": None,
        }
    if not path.exists():
        return {
            **entry,
            "status": "missing",
            "errors": [f"file not found: {path}"],
            "checksum_verified": False,
            "checksum_match": None,
        }
    if not path.is_file():
        return {
            **entry,
            "status": "invalid",
            "errors": [f"dataset path is not a file: {path}"],
            "checksum_verified": False,
            "checksum_match": None,
        }
    provenance = entry.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        missing_provenance = sorted(_PROVENANCE_KEYS.difference(provenance))
        if missing_provenance:
            errors.append(f"provenance is missing keys: {missing_provenance}")
        blank_provenance = sorted(
            key
            for key in _PROVENANCE_KEYS.intersection(provenance)
            if not isinstance(provenance[key], str) or not provenance[key].strip()
        )
        if blank_provenance:
            errors.append(
                f"provenance values must be non-empty strings: {blank_provenance}"
            )
        source_urls = provenance.get("source_urls", [])
        if not isinstance(source_urls, list) or any(
            not isinstance(url, str) or not url.strip() for url in source_urls
        ):
            errors.append("provenance source_urls must be a list of non-empty strings")
    try:
        expected_size = int(entry["size_bytes"])
        expected_rows = int(entry["rows"])
    except (TypeError, ValueError):
        return {
            **entry,
            "status": "invalid",
            "errors": ["manifest rows and size_bytes must be integers"],
            "checksum_verified": False,
            "checksum_match": None,
        }
    stat = path.stat()
    if stat.st_size != expected_size:
        errors.append(f"size mismatch: expected {entry['size_bytes']}, found {stat.st_size}")
    try:
        parquet = pq.ParquetFile(path)
    except Exception as exc:
        return {
            **entry,
            "status": "invalid",
            "errors": [*errors, f"invalid parquet file: {exc}"],
            "checksum_verified": False,
            "checksum_match": None,
        }
    actual_columns = set(parquet.schema_arrow.names)
    actual_schema_fingerprint = _schema_fingerprint(parquet)
    expected_schema_fingerprint = str(entry.get("schema_fingerprint", ""))
    if expected_schema_fingerprint and expected_schema_fingerprint != actual_schema_fingerprint:
        errors.append(
            "schema fingerprint mismatch: an explicit schema migration is required"
        )
    try:
        schema_version = int(entry.get("schema_version", 1))
        if schema_version < 1:
            raise ValueError
    except (TypeError, ValueError):
        schema_version = 0
        errors.append("schema_version must be a positive integer")
    missing_columns = sorted(set(entry["required_columns"]).difference(actual_columns))
    if missing_columns:
        errors.append(f"missing required columns: {missing_columns}")
    if parquet.metadata.num_rows != expected_rows:
        errors.append(f"row mismatch: expected {entry['rows']}, found {parquet.metadata.num_rows}")
    date_column = str(entry.get("date_column", ""))
    if date_column and date_column in actual_columns:
        actual_min, actual_max = _parquet_date_bounds(parquet, date_column)
        for key, actual in (("date_min", actual_min), ("date_max", actual_max)):
            expected = str(entry.get(key, ""))
            if expected and actual and expected != actual:
                errors.append(f"{key} mismatch: expected {expected}, found {actual}")
    if deep:
        checksum_verified = True
        actual_hash = _sha256(path)
        checksum_match = actual_hash == entry["sha256"]
        if not checksum_match:
            errors.append(f"checksum mismatch: expected {entry['sha256']}, found {actual_hash}")
    return {
        **entry,
        "status": "healthy" if not errors else "invalid",
        "errors": errors,
        "checksum_verified": checksum_verified,
        "checksum_match": checksum_match,
        "schema_version": schema_version,
        "schema_fingerprint": actual_schema_fingerprint,
        "schema_verified": (
            not expected_schema_fingerprint
            or expected_schema_fingerprint == actual_schema_fingerprint
        ),
    }


def build_dataset_entry(
    entry: dict[str, Any], *, root: Path = ROOT, include_checksum: bool = True,
    allow_schema_change: bool = False, schema_version: int | None = None,
) -> dict[str, Any]:
    """Rebuild inexpensive metadata and, when requested, the content hash."""
    path = _resolved_path(entry, root)
    parquet = pq.ParquetFile(path)
    actual_schema_fingerprint = _schema_fingerprint(parquet)
    expected_schema_fingerprint = str(entry.get("schema_fingerprint", ""))
    if (
        expected_schema_fingerprint
        and expected_schema_fingerprint != actual_schema_fingerprint
        and not allow_schema_change
    ):
        raise ValueError(
            f"Dataset '{entry['id']}' schema changed; run an explicit schema migration"
        )
    resolved_schema_version = int(
        schema_version if schema_version is not None else entry.get("schema_version", 1)
    )
    if resolved_schema_version < 1:
        raise ValueError("schema_version must be a positive integer")
    rebuilt = {
        **entry,
        "rows": parquet.metadata.num_rows,
        "size_bytes": path.stat().st_size,
        "schema_version": resolved_schema_version,
        "schema_fingerprint": actual_schema_fingerprint,
    }
    date_column = str(entry.get("date_column", ""))
    if date_column:
        date_min, date_max = _parquet_date_bounds(parquet, date_column)
        if date_min:
            rebuilt["date_min"] = date_min
        if date_max:
            rebuilt["date_max"] = date_max
    if include_checksum:
        rebuilt["sha256"] = _sha256(path)
    return rebuilt


def refresh_manifest(
    dataset_ids: Iterable[str] | None = None,
    *,
    manifest_path: Path = MANIFEST_PATH,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Atomically refresh selected manifest entries after an explicit data update."""
    selected = {str(value) for value in dataset_ids or []}
    with _REFRESH_LOCK:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        entries = manifest.get("datasets")
        if manifest.get("manifest_version") != 1 or not isinstance(entries, list):
            raise ValueError("Studio V2 dataset manifest has an unsupported structure")
        known = {str(entry.get("id")) for entry in entries}
        unknown = sorted(selected.difference(known))
        if unknown:
            raise ValueError(f"Unknown manifest dataset ids: {unknown}")
        manifest["datasets"] = [
            build_dataset_entry(entry, root=root)
            if not selected or str(entry.get("id")) in selected
            else entry
            for entry in entries
        ]
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        _write_manifest_atomic(manifest, manifest_path)
        load_manifest.cache_clear()
        return manifest


def migrate_dataset_schema(
    dataset_id: str,
    *,
    new_schema_version: int,
    required_columns: Iterable[str] | None = None,
    manifest_path: Path = MANIFEST_PATH,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Explicitly accept a validated Parquet schema change and audit the bump."""
    with _REFRESH_LOCK:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        entries = manifest.get("datasets")
        if manifest.get("manifest_version") != 1 or not isinstance(entries, list):
            raise ValueError("Studio V2 dataset manifest has an unsupported structure")
        index = next(
            (position for position, entry in enumerate(entries)
             if str(entry.get("id")) == str(dataset_id)),
            None,
        )
        if index is None:
            raise ValueError(f"Unknown manifest dataset id: {dataset_id}")
        current = dict(entries[index])
        current_version = int(current.get("schema_version", 1))
        if int(new_schema_version) <= current_version:
            raise ValueError("new_schema_version must be greater than the current version")
        if required_columns is not None:
            resolved_columns = list(dict.fromkeys(str(value) for value in required_columns))
            if not resolved_columns:
                raise ValueError("required_columns cannot be empty")
            current["required_columns"] = resolved_columns
        migrated = build_dataset_entry(
            current,
            root=root,
            allow_schema_change=True,
            schema_version=int(new_schema_version),
        )
        missing = sorted(
            set(migrated["required_columns"]).difference(
                pq.ParquetFile(_resolved_path(migrated, root)).schema_arrow.names
            )
        )
        if missing:
            raise ValueError(f"Migrated schema is missing required columns: {missing}")
        entries[index] = migrated
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        manifest.setdefault("schema_migrations", []).append({
            "dataset_id": str(dataset_id),
            "from_version": current_version,
            "to_version": int(new_schema_version),
            "from_fingerprint": current.get("schema_fingerprint"),
            "to_fingerprint": migrated["schema_fingerprint"],
            "migrated_at": manifest["generated_at"],
        })
        _write_manifest_atomic(manifest, manifest_path)
        load_manifest.cache_clear()
        return manifest


def install_dataset_atomically(
    dataset_id: str,
    replacement_path: str | Path,
    *,
    new_schema_version: int | None = None,
    required_columns: Iterable[str] | None = None,
    manifest_path: Path = MANIFEST_PATH,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Validate and atomically install a dataset with manifest rollback.

    Schema drift is rejected unless the caller supplies a strictly higher
    schema version. The old dataset remains recoverable until the new manifest
    has been durably replaced.
    """
    source = Path(replacement_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"replacement dataset not found: {source}")
    with _REFRESH_LOCK:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        entries = manifest.get("datasets")
        if manifest.get("manifest_version") != 1 or not isinstance(entries, list):
            raise ValueError("Studio V2 dataset manifest has an unsupported structure")
        index = next(
            (
                position
                for position, entry in enumerate(entries)
                if str(entry.get("id")) == str(dataset_id)
            ),
            None,
        )
        if index is None:
            raise ValueError(f"Unknown manifest dataset id: {dataset_id}")
        current = dict(entries[index])
        target = _resolved_path(current, root)
        if source == target.resolve():
            raise ValueError("replacement_path must differ from the installed dataset path")
        target.parent.mkdir(parents=True, exist_ok=True)
        current_version = int(current.get("schema_version", 1))
        requested_version = (
            int(new_schema_version) if new_schema_version is not None else current_version
        )
        if new_schema_version is not None and requested_version <= current_version:
            raise ValueError("new_schema_version must be greater than the current version")
        if required_columns is not None:
            columns = list(dict.fromkeys(str(value) for value in required_columns))
            if not columns:
                raise ValueError("required_columns cannot be empty")
            current["required_columns"] = columns

        temporary_path: Path | None = None
        backup_path: Path | None = None
        installed = False
        target_existed = target.exists()
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".install.tmp",
                delete=False,
            ) as handle, source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle, length=1024 * 1024)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)

            relative_temporary = temporary_path.resolve().relative_to(root.resolve())
            candidate_input = {**current, "path": relative_temporary.as_posix()}
            candidate = build_dataset_entry(
                candidate_input,
                root=root,
                allow_schema_change=new_schema_version is not None,
                schema_version=requested_version,
            )
            parquet = pq.ParquetFile(temporary_path)
            missing = sorted(
                set(candidate["required_columns"]).difference(parquet.schema_arrow.names)
            )
            if missing:
                raise ValueError(f"Replacement schema is missing required columns: {missing}")
            schema_changed = (
                bool(current.get("schema_fingerprint"))
                and current.get("schema_fingerprint") != candidate["schema_fingerprint"]
            )
            if schema_changed and new_schema_version is None:
                raise ValueError(
                    f"Dataset '{dataset_id}' schema changed; supply an explicit new schema version"
                )
            if not schema_changed and new_schema_version is not None:
                raise ValueError("new_schema_version was supplied but the schema did not change")

            candidate["path"] = current["path"]
            if target_existed:
                backup_path = target.parent / f".{target.name}.{uuid.uuid4().hex}.backup"
                try:
                    os.link(target, backup_path)
                except OSError:
                    shutil.copy2(target, backup_path)
            os.replace(temporary_path, target)
            temporary_path = None
            installed = True
            try:
                directory_handle = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_handle)
                finally:
                    os.close(directory_handle)
            except OSError:
                pass

            entries[index] = candidate
            manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
            if schema_changed:
                manifest.setdefault("schema_migrations", []).append(
                    {
                        "dataset_id": str(dataset_id),
                        "from_version": current_version,
                        "to_version": requested_version,
                        "from_fingerprint": current.get("schema_fingerprint"),
                        "to_fingerprint": candidate["schema_fingerprint"],
                        "migrated_at": manifest["generated_at"],
                    }
                )
            _write_manifest_atomic(manifest, manifest_path)
            load_manifest.cache_clear()
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
                backup_path = None
            return manifest
        except Exception:
            if installed:
                if backup_path is not None and backup_path.exists():
                    os.replace(backup_path, target)
                    backup_path = None
                elif not target_existed:
                    target.unlink(missing_ok=True)
            raise
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)


def manifest_snapshot(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a deterministic, compact data snapshot for stored analytics."""
    source = manifest or load_manifest()
    datasets = [
        {
            "id": str(entry["id"]),
            "sha256": str(entry["sha256"]),
            "schema_version": int(entry.get("schema_version", 1)),
            "schema_fingerprint": str(entry.get("schema_fingerprint", "")),
            "date_min": str(entry.get("date_min", "")),
            "date_max": str(entry.get("date_max", "")),
            "rows": int(entry["rows"]),
        }
        for entry in sorted(source.get("datasets", []), key=lambda row: str(row["id"]))
    ]
    identity = {
        "manifest_version": int(source["manifest_version"]),
        "generated_at": str(source["generated_at"]),
        "datasets": datasets,
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {
        **identity,
        "snapshot_id": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
    }


def validate_manifest(*, deep: bool = False) -> dict[str, Any]:
    manifest = load_manifest()
    datasets = [validate_dataset(entry, deep=deep) for entry in manifest["datasets"]]
    return {
        "manifest_version": manifest["manifest_version"],
        "generated_at": manifest["generated_at"],
        "manifest_path": str(MANIFEST_PATH),
        "deep_validation": deep,
        "healthy": all(entry["status"] == "healthy" for entry in datasets),
        "datasets": datasets,
    }
