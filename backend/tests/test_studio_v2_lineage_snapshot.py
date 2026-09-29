from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.studio_v2.backtest.lineage import ModelLineage
from app.studio_v2.shared.data_manifest import manifest_snapshot


@dataclass
class _Config:
    initial_cash: float = 100_000.0


def test_lineage_persists_exact_manifest_snapshot(tmp_path) -> None:
    storage = tmp_path / "lineage.json"
    lineage = ModelLineage(str(storage))
    snapshot = manifest_snapshot()

    run_id = lineage.record_run(
        "return 0",
        _Config(),
        SimpleNamespace(metrics={"sharpe": 1.25}, run_duration_seconds=0.01),
        data_manifest_snapshot=snapshot,
    )

    assert lineage.get_run(run_id).data_manifest_snapshot == snapshot
    assert snapshot["snapshot_id"].startswith("sha256:")

    reloaded = ModelLineage(str(storage)).get_run(run_id)
    assert reloaded.data_manifest_snapshot == snapshot


def test_legacy_lineage_rows_default_to_empty_manifest_snapshot(tmp_path) -> None:
    storage = tmp_path / "lineage.json"
    storage.write_text(
        '{"runs":[{"run_id":"legacy","strategy_file_hash":"hash",'
        '"strategy_name":"legacy.py","parent_run_id":null,"parameters":{},'
        '"metrics":{},"tags":["Candidate"],"created_at":"2026-01-01T00:00:00+00:00",'
        '"duration_seconds":0.0}],"walkforward":{}}',
        encoding="utf-8",
    )

    assert ModelLineage(str(storage)).get_run("legacy").data_manifest_snapshot == {}
