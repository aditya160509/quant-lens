from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from app.studio_v2.shared import data_loader
from app.studio_v2.shared import data_manifest


@pytest.fixture()
def isolated_market_universe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    path = tmp_path / "market_universe.parquet"
    monkeypatch.setattr(data_loader, "UNIVERSE_PATH", path)
    data_loader._load_universe.cache_clear()
    data_loader._load_universe_subset.cache_clear()
    data_loader._load_ticker.cache_clear()
    data_loader._all_tickers_tuple.cache_clear()
    data_loader.get_trading_sessions.cache_clear()
    data_loader.clear_data_access_metrics()
    yield path
    data_loader._load_universe.cache_clear()
    data_loader._load_universe_subset.cache_clear()
    data_loader._load_ticker.cache_clear()
    data_loader._all_tickers_tuple.cache_clear()
    data_loader.get_trading_sessions.cache_clear()
    data_loader.clear_data_access_metrics()


def test_unknown_asset_class_fails_with_supported_values() -> None:
    with pytest.raises(ValueError, match="Unsupported asset class.*crypto.*futures"):
        data_loader.get_returns(["SPY"], asset_class="options")


def test_market_universe_rejects_malformed_schema(
    isolated_market_universe: Path,
) -> None:
    pd.DataFrame(
        {
            "Ticker": ["SPY"],
            "Date": ["2024-01-02"],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
        }
    ).to_parquet(isolated_market_universe)

    with pytest.raises(ValueError, match="missing required columns.*volume"):
        data_loader._load_universe()


def test_duplicate_bars_timezone_missing_symbol_and_empty_range(
    isolated_market_universe: Path,
) -> None:
    pd.DataFrame(
        {
            "Ticker": ["aapl", "AAPL", "AAPL"],
            "Date": [
                "2024-01-02T00:00:00Z",
                "2024-01-01T19:00:00-05:00",
                "2024-01-03T00:00:00Z",
            ],
            "Open": [99.0, 100.0, 109.0],
            "High": [101.0, 102.0, 111.0],
            "Low": [98.0, 99.0, 108.0],
            "Close": [100.0, 101.0, 110.0],
            "Volume": [10, 20, 30],
        }
    ).to_parquet(isolated_market_universe)

    returns = data_loader.get_returns(["aapl", "AAPL", "missing"])

    assert list(returns.columns) == ["AAPL"]
    assert returns.index.tz is None
    assert returns["AAPL"].dropna().iloc[0] == pytest.approx(110.0 / 101.0 - 1.0)
    assert len(data_loader.get_ohlcv("AAPL")) == 2

    empty = data_loader.get_returns(
        ["AAPL"], start="2024-02-01", end="2024-01-01"
    )
    assert empty.empty


def test_data_access_metrics_track_pushdown_scan_and_cache_hits(
    isolated_market_universe: Path,
) -> None:
    pd.DataFrame(
        {
            "Ticker": ["SPY", "QQQ"],
            "Date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "Open": [100.0, 200.0],
            "High": [101.0, 201.0],
            "Low": [99.0, 199.0],
            "Close": [100.5, 200.5],
            "Volume": [1_000, 2_000],
        }
    ).to_parquet(isolated_market_universe)

    first = data_loader.get_ohlcv_batch(["SPY"], "2024-01-01", "2024-01-03")
    second = data_loader.get_ohlcv_batch(["SPY"], "2024-01-01", "2024-01-03")
    metrics = data_loader.get_data_access_metrics()

    assert list(first) == ["SPY"]
    assert list(second) == ["SPY"]
    scan = metrics["scans"]
    assert scan["queries"] == 1
    assert scan["rows_scanned"] == 1
    assert scan["bytes_scanned"] > 0
    assert scan["predicate_pushdown_rate"] == 1.0
    assert scan["datasets"]["market_universe"]["fallback_queries"] == 0
    subset_cache = metrics["cache"]["functions"]["universe_subset"]
    assert subset_cache["misses"] == 1
    assert subset_cache["hits"] == 1


def test_factor_csv_fallback_parses_preamble_scales_and_masks_sentinels(
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "ff3_daily.parquet"
    csv_path = parquet_path.with_suffix(".csv")
    csv_path.write_text(
        "Research Factors\n"
        "Generated for test coverage\n"
        ",Mkt-RF,SMB,HML,RF\n"
        "20240102,1.00,0.50,-0.25,0.01\n"
        "20240103,-99.99,0.25,0.10,0.01\n",
        encoding="utf-8",
    )
    data_loader._load_factor_file.cache_clear()

    factors = data_loader._load_factor_file(parquet_path)

    assert list(factors.columns) == ["mkt-rf", "smb", "hml", "rf"]
    assert factors.index.equals(pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="date"))
    assert factors.loc[pd.Timestamp("2024-01-02"), "mkt-rf"] == pytest.approx(0.01)
    assert np.isnan(factors.loc[pd.Timestamp("2024-01-03"), "mkt-rf"])


def _manifest_entry(path: Path, root: Path) -> dict:
    relative = path.relative_to(root).as_posix()
    return {
        "id": "test_daily",
        "path": relative,
        "format": "parquet",
        "rows": 2,
        "size_bytes": path.stat().st_size,
        "date_column": "date",
        "date_min": "2024-01-02",
        "date_max": "2024-01-03",
        "required_columns": ["date", "close"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "provenance": {
            "source": "test fixture",
            "source_urls": [],
            "license_status": "test-only",
            "transformation_version": "test-v1",
            "generation_command": "pytest fixture",
            "point_in_time_policy": "not applicable",
            "adjustment_policy": "not applicable",
        },
    }


def test_manifest_reports_stale_metadata_schema_and_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "data" / "sample.parquet"
    path.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(path)
    entry = _manifest_entry(path, tmp_path)
    entry.update(
        rows=9,
        size_bytes=1,
        date_min="1999-01-01",
        date_max="2099-01-01",
        required_columns=["date", "close", "volume"],
        sha256="0" * 64,
    )
    monkeypatch.setattr(data_manifest, "ROOT", tmp_path)

    result = data_manifest.validate_dataset(entry, deep=True)

    errors = "\n".join(result["errors"])
    assert result["status"] == "invalid"
    assert result["checksum_verified"] is True
    assert result["checksum_match"] is False
    assert "size mismatch" in errors
    assert "row mismatch" in errors
    assert "missing required columns" in errors
    assert "date_min mismatch" in errors
    assert "date_max mismatch" in errors
    assert "checksum mismatch" in errors


def test_manifest_handles_partial_files_and_path_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    partial = tmp_path / "partial.parquet"
    partial.write_bytes(b"PAR1 interrupted")
    monkeypatch.setattr(data_manifest, "ROOT", tmp_path)
    entry = {
        "id": "partial",
        "path": "partial.parquet",
        "rows": 1,
        "size_bytes": partial.stat().st_size,
        "required_columns": ["date"],
        "sha256": hashlib.sha256(partial.read_bytes()).hexdigest(),
        "provenance": {
            "source": "partial test fixture",
            "source_urls": [],
            "license_status": "test-only",
            "transformation_version": "test-v1",
            "generation_command": "pytest fixture",
            "point_in_time_policy": "not applicable",
            "adjustment_policy": "not applicable",
        },
    }

    result = data_manifest.validate_dataset(entry, deep=True)
    escaped = data_manifest.validate_dataset({**entry, "path": "../outside.parquet"})

    assert result["status"] == "invalid"
    assert "invalid parquet file" in result["errors"][0]
    assert escaped["status"] == "invalid"
    assert "escapes the project root" in escaped["errors"][0]


def test_manifest_refresh_rebuilds_metadata_and_replaces_atomically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "data" / "sample.parquet"
    path.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(path)
    entry = _manifest_entry(path, tmp_path)
    entry.update(rows=99, size_bytes=1, date_min="2000-01-01", sha256="x")
    manifest_path = tmp_path / "manifests" / "studio_v2.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generated_at": "2000-01-01T00:00:00Z",
                "datasets": [entry],
            }
        ),
        encoding="utf-8",
    )

    refreshed = data_manifest.refresh_manifest(
        ["test_daily"], manifest_path=manifest_path, root=tmp_path
    )
    rebuilt = refreshed["datasets"][0]
    monkeypatch.setattr(data_manifest, "ROOT", tmp_path)

    assert rebuilt["rows"] == 2
    assert rebuilt["size_bytes"] == path.stat().st_size
    assert rebuilt["date_min"] == "2024-01-02"
    assert rebuilt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert data_manifest.validate_dataset(rebuilt, deep=True)["status"] == "healthy"
    assert not list(manifest_path.parent.glob("*.tmp"))

    with pytest.raises(ValueError, match="Unknown manifest dataset ids"):
        data_manifest.refresh_manifest(
            ["does_not_exist"], manifest_path=manifest_path, root=tmp_path
        )


def test_manifest_requires_explicit_versioned_schema_migration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "data" / "sample.parquet"
    path.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(path)
    entry = data_manifest.build_dataset_entry(
        _manifest_entry(path, tmp_path), root=tmp_path
    )
    original_fingerprint = entry["schema_fingerprint"]
    manifest_path = tmp_path / "manifests" / "studio_v2.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generated_at": "2024-01-03T00:00:00Z",
                "datasets": [entry],
            }
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "close": [1.0, 2.0],
            "volume": [100, 200],
        }
    ).to_parquet(path)

    with pytest.raises(ValueError, match="explicit schema migration"):
        data_manifest.refresh_manifest(
            ["test_daily"], manifest_path=manifest_path, root=tmp_path
        )

    migrated = data_manifest.migrate_dataset_schema(
        "test_daily",
        new_schema_version=2,
        required_columns=["date", "close", "volume"],
        manifest_path=manifest_path,
        root=tmp_path,
    )
    migrated_entry = migrated["datasets"][0]
    migration = migrated["schema_migrations"][0]
    monkeypatch.setattr(data_manifest, "ROOT", tmp_path)

    assert migrated_entry["schema_version"] == 2
    assert migrated_entry["schema_fingerprint"] != original_fingerprint
    assert migration["from_version"] == 1
    assert migration["to_version"] == 2
    assert migration["from_fingerprint"] == original_fingerprint
    assert migration["to_fingerprint"] == migrated_entry["schema_fingerprint"]
    assert data_manifest.validate_dataset(migrated_entry, deep=True)["status"] == "healthy"
    assert not list(manifest_path.parent.glob("*.tmp"))


def test_atomic_dataset_install_updates_file_and_manifest_together(
    tmp_path: Path,
) -> None:
    target = tmp_path / "data" / "sample.parquet"
    target.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(target)
    entry = data_manifest.build_dataset_entry(
        _manifest_entry(target, tmp_path), root=tmp_path
    )
    manifest_path = tmp_path / "manifests" / "studio_v2.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generated_at": "2024-01-03T00:00:00Z",
                "datasets": [entry],
            }
        ),
        encoding="utf-8",
    )
    replacement = tmp_path / "incoming.parquet"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-01", "2024-02-02", "2024-02-05"]),
            "close": [10.0, 11.0, 12.0],
        }
    ).to_parquet(replacement)

    installed = data_manifest.install_dataset_atomically(
        "test_daily", replacement, manifest_path=manifest_path, root=tmp_path
    )

    installed_entry = installed["datasets"][0]
    assert pd.read_parquet(target)["close"].tolist() == [10.0, 11.0, 12.0]
    assert installed_entry["rows"] == 3
    assert installed_entry["date_min"] == "2024-02-01"
    assert installed_entry["date_max"] == "2024-02-05"
    assert installed_entry["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == installed
    assert not list(target.parent.glob(".*.backup"))
    assert not list(target.parent.glob("*.install.tmp"))


def test_atomic_dataset_install_rolls_back_on_manifest_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "data" / "sample.parquet"
    target.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(target)
    original_bytes = target.read_bytes()
    entry = data_manifest.build_dataset_entry(
        _manifest_entry(target, tmp_path), root=tmp_path
    )
    manifest_path = tmp_path / "manifests" / "studio_v2.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generated_at": "2024-01-03T00:00:00Z",
                "datasets": [entry],
            }
        ),
        encoding="utf-8",
    )
    original_manifest = manifest_path.read_text(encoding="utf-8")
    replacement = tmp_path / "incoming.parquet"
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-02-01"]), "close": [99.0]}
    ).to_parquet(replacement)

    def fail_manifest_write(manifest: dict, path: Path) -> None:
        raise OSError("simulated manifest storage failure")

    monkeypatch.setattr(data_manifest, "_write_manifest_atomic", fail_manifest_write)
    with pytest.raises(OSError, match="simulated manifest storage failure"):
        data_manifest.install_dataset_atomically(
            "test_daily", replacement, manifest_path=manifest_path, root=tmp_path
        )

    assert target.read_bytes() == original_bytes
    assert manifest_path.read_text(encoding="utf-8") == original_manifest
    assert not list(target.parent.glob(".*.backup"))
    assert not list(target.parent.glob("*.install.tmp"))
