#!/usr/bin/env python3
"""Build fast normalized Fama-French Parquets from provider CSV snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.studio_v2.shared import data_loader, data_manifest  # noqa: E402


DATASETS = {
    "fama_french_3_daily": {
        "csv": BACKEND_ROOT / "data/factors_us/ff3_daily.csv",
        "parquet": BACKEND_ROOT / "data/factors_us/ff3_daily.parquet",
        "columns": ["date", "mkt-rf", "smb", "hml", "rf"],
    },
    "fama_french_5_daily": {
        "csv": BACKEND_ROOT / "data/factors_us/ff5_daily.csv",
        "parquet": BACKEND_ROOT / "data/factors_us/ff5_daily.parquet",
        "columns": ["date", "mkt-rf", "smb", "hml", "rmw", "cma", "rf"],
    },
    "momentum_daily": {
        "csv": BACKEND_ROOT / "data/factors_us/momentum_daily.csv",
        "parquet": BACKEND_ROOT / "data/factors_us/momentum_daily.parquet",
        "columns": ["date", "mom"],
    },
}


def _normalized_frame(dataset_id: str) -> pd.DataFrame:
    specification = DATASETS[dataset_id]
    source = Path(specification["csv"])
    if not source.is_file():
        raise FileNotFoundError(f"Fama-French source CSV not found: {source}")
    data_loader._load_factor_file.cache_clear()
    frame = data_loader._load_factor_file(source).reset_index()
    expected = list(specification["columns"])
    if list(frame.columns) != expected:
        raise ValueError(
            f"{dataset_id} columns changed: expected {expected}, found {list(frame.columns)}"
        )
    if frame.empty or frame["date"].isna().any():
        raise ValueError(f"{dataset_id} contains no valid dated observations")
    if frame["date"].duplicated().any() or not frame["date"].is_monotonic_increasing:
        raise ValueError(f"{dataset_id} dates must be unique and increasing")
    values = frame.drop(columns="date").to_numpy(dtype=float, copy=False)
    if not np.isfinite(values).all():
        raise ValueError(f"{dataset_id} contains missing or non-finite factor values")
    if np.max(np.abs(values), initial=0.0) > 10.0:
        raise ValueError(
            f"{dataset_id} values exceed a decimal-return safety bound; percent scaling may be wrong"
        )
    return frame


def _compare(expected: pd.DataFrame, path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    actual = pd.read_parquet(path)
    columns_match = list(actual.columns) == list(expected.columns)
    dates_match = columns_match and actual["date"].equals(expected["date"])
    values_match = False
    max_absolute_difference: float | None = None
    if dates_match and len(actual) == len(expected):
        actual_values = actual.drop(columns="date").to_numpy(dtype=float, copy=False)
        expected_values = expected.drop(columns="date").to_numpy(dtype=float, copy=False)
        difference = np.abs(actual_values - expected_values)
        max_absolute_difference = float(np.max(difference, initial=0.0))
        values_match = bool(np.array_equal(actual_values, expected_values, equal_nan=True))
    matches = len(actual) == len(expected) and columns_match and dates_match and values_match
    return {
        "status": "current" if matches else "stale",
        "path": str(path),
        "expected_rows": len(expected),
        "actual_rows": len(actual),
        "expected_date_max": expected["date"].max().date().isoformat(),
        "actual_date_max": (
            pd.Timestamp(actual["date"].max()).date().isoformat()
            if columns_match and not actual.empty
            else None
        ),
        "columns_match": columns_match,
        "dates_match": dates_match,
        "values_match": values_match,
        "max_absolute_difference": max_absolute_difference,
    }


def check(dataset_ids: list[str]) -> dict[str, Any]:
    results = {
        dataset_id: _compare(
            _normalized_frame(dataset_id), Path(DATASETS[dataset_id]["parquet"])
        )
        for dataset_id in dataset_ids
    }
    return {
        "status": (
            "current"
            if all(row["status"] == "current" for row in results.values())
            else "stale"
        ),
        "datasets": results,
    }


def build(dataset_ids: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="studio-v2-fama-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        for dataset_id in dataset_ids:
            frame = _normalized_frame(dataset_id)
            temporary_path = temporary_root / f"{dataset_id}.parquet"
            table = pa.Table.from_pandas(frame, preserve_index=False)
            pq.write_table(
                table,
                temporary_path,
                compression="zstd",
                compression_level=3,
                use_dictionary=False,
                write_statistics=True,
                row_group_size=65_536,
                data_page_version="2.0",
            )
            manifest = data_manifest.install_dataset_atomically(
                dataset_id,
                temporary_path,
                manifest_path=data_manifest.MANIFEST_PATH,
                root=PROJECT_ROOT,
            )
            entry = next(
                row for row in manifest["datasets"] if row["id"] == dataset_id
            )
            results[dataset_id] = {
                "status": "installed",
                "rows": entry["rows"],
                "size_bytes": entry["size_bytes"],
                "date_min": entry.get("date_min"),
                "date_max": entry.get("date_max"),
                "sha256": entry["sha256"],
                "schema_version": entry["schema_version"],
            }
    data_loader._load_factor_file.cache_clear()
    data_manifest.load_manifest.cache_clear()
    return {"status": "installed", "datasets": results}


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--build", action="store_true")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=sorted(DATASETS),
        help="Dataset ID; repeat to select more than one. Defaults to all three.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    dataset_ids = arguments.dataset or list(DATASETS)
    try:
        result = check(dataset_ids) if arguments.check else build(dataset_ids)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "error", "error": type(exc).__name__, "message": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"current", "installed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
