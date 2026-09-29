import json
from pathlib import Path

import pytest

from app.services.studio.reports import ReportComposer, ReportError
from app.studio_v2.shared.persistence import SQLiteStore


def _composer(tmp_path: Path) -> tuple[ReportComposer, SQLiteStore]:
    store = SQLiteStore(tmp_path / "reports.sqlite3")
    store.put("studio_portfolio_versions", "pfv_1", {
        "version_id": "pfv_1", "artifact_id": "portfolio_1",
        "portfolio": {"metrics": {"sharpe": 1.25}, "warnings": ["User supplied assumptions"]},
    })
    return ReportComposer(store), store


def test_recipe_stores_references_only_and_resolves_current_artifact(tmp_path: Path) -> None:
    composer, store = _composer(tmp_path)
    recipe = composer.save_recipe("Portfolio review", "portfolio_review", [{
        "kind": "artifact", "title": "Risk-adjusted result",
        "reference": {"type": "portfolio_version", "id": "pfv_1"},
        "metric_paths": ["portfolio.metrics.sharpe", "portfolio.warnings"],
        "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
    }])
    assert "portfolio" not in recipe["blocks"][0]
    first = composer.render(recipe["recipe_id"])
    assert first["blocks"][0]["resolved"]["metrics"]["portfolio.metrics.sharpe"] == 1.25

    source = store.get("studio_portfolio_versions", "pfv_1")
    source["portfolio"]["metrics"]["sharpe"] = 1.5
    store.put("studio_portfolio_versions", "pfv_1", source, expected_version=source["_revision"])
    second = composer.render(recipe["recipe_id"])
    assert second["blocks"][0]["resolved"]["metrics"]["portfolio.metrics.sharpe"] == 1.5
    assert first["report_hash"] != second["report_hash"]


def test_exports_are_deterministic_reconciled_and_standalone(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    recipe = composer.save_recipe("Review", "portfolio_review", [{
        "kind": "narrative", "title": "Decision",
        "text": "Risk-adjusted performance",
        "reference": {"type": "portfolio_version", "id": "pfv_1"},
        "metric_paths": ["portfolio.metrics.sharpe"],
        "citations": ["portfolio.metrics.sharpe"],
    }])
    first, second = composer.export_json(recipe["recipe_id"]), composer.export_json(recipe["recipe_id"])
    assert first == second
    assert json.loads(first)["blocks"][0]["resolved"]["metrics"]["portfolio.metrics.sharpe"] == 1.25
    csv_export = composer.export_csv(recipe["recipe_id"]).decode()
    assert "portfolio.metrics.sharpe" in csv_export and "1.25" in csv_export
    html_export = composer.export_html(recipe["recipe_id"]).decode()
    assert "<!doctype html>" in html_export and "Report hash" in html_export and "1.25" in html_export


def test_recipe_rejects_embedded_result_copies(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    with pytest.raises(ReportError) as error:
        composer.save_recipe("Bad", "custom", [{
            "kind": "artifact", "reference": {"type": "portfolio_version", "id": "pfv_1"},
            "data": {"hardcoded": True},
        }])
    assert error.value.code == "REPORT_EMBEDDED_DATA_FORBIDDEN"


def test_notes_require_a_real_linked_artifact(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    note = composer.save_note("Allocation decision", "Kept the constraint.", {"type": "portfolio_version", "id": "pfv_1"})
    assert note["reference"]["id"] == "pfv_1"
    with pytest.raises(ReportError, match="not found"):
        composer.save_note("Missing", "No source", {"type": "portfolio_version", "id": "nope"})


def test_persistent_report_quotas_are_configurable(tmp_path: Path, monkeypatch) -> None:
    composer, _ = _composer(tmp_path)
    monkeypatch.setenv("STUDIO_MAX_REPORT_RECIPES", "0")
    with pytest.raises(ReportError) as error:
        composer.save_recipe("Blocked", "custom", [{"kind": "narrative", "text": "No source required"}])
    assert error.value.code == "REPORT_QUOTA_EXCEEDED"
    assert error.value.status_code == 429


def test_template_defaults_resolve_to_block_lists(tmp_path: Path) -> None:
    from app.services.studio.reports import TEMPLATE_DEFAULTS, template_block_list

    assert set(TEMPLATE_DEFAULTS) == {"strategy_review", "validation", "portfolio_review", "paper_reconciliation"}
    for name in TEMPLATE_DEFAULTS:
        blocks = template_block_list(name)
        assert len(blocks) >= 2
        assert all("block_id" in block and "metric_paths" in block for block in blocks)
    with pytest.raises(ReportError) as error:
        template_block_list("unknown_template")
    assert error.value.code == "REPORT_TEMPLATE_NOT_FOUND"


def test_render_carries_formulas_policy_warnings_and_versions(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    recipe = composer.save_recipe("Review", "portfolio_review", [{
        "kind": "artifact", "title": "Allocation",
        "reference": {"type": "portfolio_version", "id": "pfv_1"},
        "metric_paths": ["portfolio.metrics.sharpe"],
    }])
    report = composer.render(recipe["recipe_id"])
    assert report["export_version"] and report["engine_version"]
    assert report["formulas"]["portfolio.metrics.sharpe"].startswith("mean(excess_returns)")
    assert report["blocks"][0]["resolved"]["formulas"]["portfolio.metrics.sharpe"]
    assert report["policy"]["template"] == "portfolio_review"
    assert "portfolio.metrics.volatility" in report["policy"]["missing_required_paths"]
    assert any("volatility" in item["warning"] for item in report["warnings"])
    assert any("User supplied assumptions" in item["warning"] for item in report["warnings"])


def test_saved_views_persist_in_recipe(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    recipe = composer.save_recipe("Review", "custom", [{
        "kind": "narrative", "title": "Note", "text": "Hello",
    }], views=[{"name": "Wide", "layouts": {"block_1": {"w": 12, "h": 6}}}])
    assert recipe["views"][0]["name"] == "Wide"
    updated = composer.save_view(recipe["recipe_id"], "Narrow", {"block_1": {"w": 6, "h": 4}})
    assert {view["name"] for view in updated["views"]} == {"Wide", "Narrow"}
    assert composer.render(recipe["recipe_id"])["views"]


def test_arrow_export_is_deterministic_and_reconciled(tmp_path: Path) -> None:
    import pyarrow.ipc as ipc

    composer, _ = _composer(tmp_path)
    recipe = composer.save_recipe("Review", "portfolio_review", [{
        "kind": "artifact", "title": "Allocation",
        "reference": {"type": "portfolio_version", "id": "pfv_1"},
        "metric_paths": ["portfolio.metrics.sharpe"],
    }])
    first, second = composer.export_arrow(recipe["recipe_id"]), composer.export_arrow(recipe["recipe_id"])
    assert first == second
    table = ipc.open_stream(first).read_all()
    assert table.num_rows == 1
    row = table.to_pylist()[0]
    assert row["metric"] == "portfolio.metrics.sharpe"
    assert "1.25" in row["value_json"]
    assert "mean(excess_returns)" in row["formula"]
    assert row["report_hash"] == composer.render(recipe["recipe_id"])["report_hash"]


def test_html_export_has_print_css_formulas_and_versions(tmp_path: Path) -> None:
    composer, _ = _composer(tmp_path)
    recipe = composer.save_recipe("Review", "portfolio_review", [{
        "kind": "artifact", "title": "Allocation",
        "reference": {"type": "portfolio_version", "id": "pfv_1"},
        "metric_paths": ["portfolio.metrics.sharpe"],
    }])
    document = composer.export_html(recipe["recipe_id"]).decode()
    assert "media='print'" in document
    assert "Save as PDF" in document
    assert "mean(excess_returns)" in document
    assert "export version" in document
    first, second = composer.export_html(recipe["recipe_id"]), composer.export_html(recipe["recipe_id"])
    assert first == second
