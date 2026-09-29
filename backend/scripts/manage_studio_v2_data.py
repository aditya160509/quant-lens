#!/usr/bin/env python3
"""Validate, refresh, migrate, or atomically install Studio V2 datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.studio_v2.shared import data_manifest  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operate the versioned Studio V2 dataset manifest safely."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=data_manifest.MANIFEST_PATH,
        help="Manifest JSON path (default: production Studio V2 manifest).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root used to resolve manifest dataset paths.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate all manifest datasets.")
    validate.add_argument("--deep", action="store_true", help="Verify SHA-256 checksums.")

    refresh = subparsers.add_parser(
        "refresh", help="Refresh metadata for already-installed datasets."
    )
    refresh.add_argument("dataset_ids", nargs="*", help="IDs; omit to refresh all.")

    install = subparsers.add_parser(
        "install", help="Validate and atomically install a replacement Parquet."
    )
    install.add_argument("dataset_id")
    install.add_argument("replacement", type=Path)
    install.add_argument("--schema-version", type=int)
    install.add_argument("--required-column", action="append", dest="required_columns")

    migrate = subparsers.add_parser(
        "migrate-schema", help="Accept the installed schema with an audited version bump."
    )
    migrate.add_argument("dataset_id")
    migrate.add_argument("schema_version", type=int)
    migrate.add_argument("--required-column", action="append", dest="required_columns")
    return parser


def _validate(manifest_path: Path, root: Path, *, deep: bool) -> dict[str, Any]:
    original_manifest = data_manifest.MANIFEST_PATH
    original_root = data_manifest.ROOT
    try:
        data_manifest.MANIFEST_PATH = manifest_path
        data_manifest.ROOT = root
        data_manifest.load_manifest.cache_clear()
        return data_manifest.validate_manifest(deep=deep)
    finally:
        data_manifest.MANIFEST_PATH = original_manifest
        data_manifest.ROOT = original_root
        data_manifest.load_manifest.cache_clear()


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    manifest_path = arguments.manifest.expanduser().resolve()
    root = arguments.root.expanduser().resolve()
    if arguments.command == "validate":
        return _validate(manifest_path, root, deep=bool(arguments.deep))
    if arguments.command == "refresh":
        return data_manifest.refresh_manifest(
            arguments.dataset_ids,
            manifest_path=manifest_path,
            root=root,
        )
    if arguments.command == "install":
        return data_manifest.install_dataset_atomically(
            arguments.dataset_id,
            arguments.replacement,
            new_schema_version=arguments.schema_version,
            required_columns=arguments.required_columns,
            manifest_path=manifest_path,
            root=root,
        )
    if arguments.command == "migrate-schema":
        return data_manifest.migrate_dataset_schema(
            arguments.dataset_id,
            new_schema_version=arguments.schema_version,
            required_columns=arguments.required_columns,
            manifest_path=manifest_path,
            root=root,
        )
    raise ValueError(f"unsupported command: {arguments.command}")


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = run(arguments)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if arguments.command == "validate" and not result.get("healthy", False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
