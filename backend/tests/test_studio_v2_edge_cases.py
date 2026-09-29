from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.studio_v2.backtest import engine as backtest_engine_module
from app.studio_v2.backtest.engine import EventDrivenEngine, SimulationConfig
from app.studio_v2.backtest.repository import BacktestResultRepository
from app.studio_v2.factors import evaluator as factor_evaluator_module
from app.studio_v2.factors.evaluator import FactorExpressionEvaluator
from app.studio_v2.algorithm_lab.portfolio_composer import PortfolioComposer
from app.studio_v2.algorithm_lab.repository import StrategyRepository
from app.studio_v2.backtest.attribution import AttributionEngine
from app.studio_v2.factors.governance import FactorGovernance
from app.studio_v2.factors.library import FactorLibrary
from app.studio_v2.data_studio.multi_asset import MultiAssetCatalog
from app.studio_v2.data_studio.synthetic_flagging import SyntheticRangeDetector
from app.studio_v2.portfolio_risk.concentration import ConcentrationEngine
from app.studio_v2.portfolio_risk.alert_feed import AlertFeed
from app.studio_v2.portfolio_risk.var_engine import VaREngine
from app.studio_v2.services.journal_service import JournalService
from app.studio_v2.shared import persistence
from app.studio_v2.shared.persistence import SQLiteStore, VersionConflictError


@pytest.fixture()
def composition_services(
    tmp_path: Path,
) -> tuple[PortfolioComposer, StrategyRepository, list[dict]]:
    store = SQLiteStore(tmp_path / "studio.sqlite3")
    strategies = StrategyRepository(store, tmp_path / "strategies")
    source = (
        "def generate_signals(data, config=None):\n"
        "    return data.notna().astype(float)\n"
    )
    records = [
        strategies.create("left", source),
        strategies.create("right", source),
    ]
    return PortfolioComposer(store, strategies), strategies, records


def test_composition_rejects_empty_duplicate_and_missing_strategies(
    composition_services: tuple[PortfolioComposer, StrategyRepository, list[dict]],
) -> None:
    composer, _, records = composition_services
    left, right = (record["strategy_id"] for record in records)

    with pytest.raises(ValueError, match="between 2 and 10"):
        composer.create([])
    with pytest.raises(ValueError, match="between 2 and 10"):
        composer.create([left])
    with pytest.raises(ValueError, match="must be unique"):
        composer.create([left, left])
    with pytest.raises(ValueError, match="unknown strategy_id 'missing'"):
        composer.create([left, "missing"])

    Path(records[1]["file_path"]).unlink()
    with pytest.raises(FileNotFoundError, match="strategy source missing"):
        composer.create([left, right])


@pytest.mark.parametrize(
    "weights,match",
    [
        ({"left": 1.0}, "every strategy exactly once"),
        ({"left": -1.0, "right": 2.0}, "finite and non-negative"),
        ({"left": np.inf, "right": 1.0}, "finite and non-negative"),
        ({"left": 0.0, "right": 0.0}, "positive gross weight"),
    ],
)
def test_composition_rejects_invalid_manual_weights(
    composition_services: tuple[PortfolioComposer, StrategyRepository, list[dict]],
    weights: dict[str, float],
    match: str,
) -> None:
    composer, _, records = composition_services
    left, right = (record["strategy_id"] for record in records)
    remapped = {
        left if key == "left" else right: value for key, value in weights.items()
    }

    with pytest.raises(ValueError, match=match):
        composer.create(
            [left, right], weight_scheme="custom", custom_weights=remapped
        )


def test_composition_normalizes_manual_weights_and_detects_late_source_loss(
    composition_services: tuple[PortfolioComposer, StrategyRepository, list[dict]],
) -> None:
    composer, _, records = composition_services
    left, right = (record["strategy_id"] for record in records)
    composition = composer.create(
        [left, right],
        weight_scheme="custom",
        custom_weights={left: 3.0, right: 1.0},
    )

    assert composition["custom_weights"] == {left: 0.75, right: 0.25}
    with pytest.raises(ValueError, match="custom_weights require"):
        composer.create(
            [left, right],
            weight_scheme="equal_weight",
            custom_weights={left: 0.5, right: 0.5},
        )

    Path(records[0]["file_path"]).unlink()
    market = pd.DataFrame(
        {"SPY": [100.0, 101.0]}, index=pd.date_range("2024-01-01", periods=2)
    )
    with pytest.raises(FileNotFoundError, match="strategy source missing"):
        composer.execute(composition["composition_id"], market)


@pytest.mark.parametrize(
    "allocator_code,match",
    [
        (
            "import os\ndef allocate(context):\n    return {}\n",
            "unsupported syntax: Import",
        ),
        (
            "def allocate(context):\n    return {'only_one': 1.0}\n",
            "every strategy exactly once",
        ),
    ],
)
def test_custom_allocator_failures_are_explicit(
    composition_services: tuple[PortfolioComposer, StrategyRepository, list[dict]],
    allocator_code: str,
    match: str,
) -> None:
    composer, _, records = composition_services
    strategy_ids = [record["strategy_id"] for record in records]
    composition = composer.create(
        strategy_ids,
        weight_scheme="custom",
        allocator_code=allocator_code,
    )
    market = pd.DataFrame(
        {"SPY": np.linspace(100.0, 110.0, 25)},
        index=pd.date_range("2024-01-01", periods=25),
    )

    with pytest.raises(ValueError, match=match):
        composer.execute(composition["composition_id"], market)


def test_attribution_handles_missing_benchmark_and_sector_mapping() -> None:
    engine = AttributionEngine()
    factor_only = engine.compute(
        {
            "returns": [0.01, 0.02, -0.01, 0.03, 0.005],
            "factor_returns": {"MKT": [0.005, 0.01, -0.005, 0.02, 0.0]},
        }
    )
    assert factor_only["attribution_status"] == "benchmark_unavailable"
    assert factor_only["benchmark_name"] is None
    assert factor_only["benchmark_available"] is False
    assert factor_only["factor_attribution"]["status"] == "ok"

    unmapped = engine.compute(
        {
            "benchmark_name": "SPY",
            "sector_rows": [
                {
                    "portfolio_weight": 1.0,
                    "benchmark_weight": 1.0,
                    "portfolio_return": 0.08,
                    "benchmark_return": 0.05,
                }
            ],
        }
    )
    assert unmapped["sectors"][0]["sector"] == "Unmapped"
    assert unmapped["reconciled"] is True


def test_attribution_rejects_nan_and_flags_non_reconciling_totals() -> None:
    engine = AttributionEngine()
    invalid = [
        {
            "sector": "Tech",
            "portfolio_weight": 1.0,
            "benchmark_weight": 1.0,
            "portfolio_return": np.nan,
            "benchmark_return": 0.05,
        }
    ]
    with pytest.raises(ValueError, match="contains non-finite values"):
        engine.brinson(invalid)

    result = engine.compute(
        {
            "sector_rows": [
                {
                    "sector": "Tech",
                    "portfolio_weight": 0.5,
                    "benchmark_weight": 0.4,
                    "portfolio_return": 0.10,
                    "benchmark_return": 0.05,
                }
            ]
        }
    )
    assert result["reconciled"] is False
    assert result["attribution_status"] == "non_reconciling"
    assert result["reconciliation_error"] != 0


def test_factor_attribution_refuses_singular_factor_betas() -> None:
    factor = np.linspace(-0.02, 0.02, 20)
    result = AttributionEngine.factor_attribution(
        factor * 0.5 + 0.001,
        {"MKT": factor, "MKT_COPY": factor},
    )

    assert result["status"] == "singular"
    assert result["betas"] == {}
    assert result["alpha"] is None
    assert result["rank"] < result["factor_count"] + 1


def test_factor_attribution_uses_calendar_intersection_and_handles_empty_overlap() -> None:
    returns = {
        "2024-01-01": 0.01,
        "2024-01-02": 0.02,
        "2024-01-03": -0.01,
        "2024-01-04": 0.03,
        "2024-01-05": 0.01,
    }
    factors = {
        "MKT": {
            "2024-01-03": -0.005,
            "2024-01-04": 0.02,
            "2024-01-05": 0.005,
            "2024-01-06": 0.01,
        }
    }

    aligned = AttributionEngine.factor_attribution(returns, factors)
    empty = AttributionEngine.factor_attribution(
        returns,
        {"MKT": {"2025-01-01": 0.01, "2025-01-02": 0.02}},
    )

    assert aligned["status"] == "ok"
    assert aligned["observations"] == 3
    assert empty["status"] == "insufficient_observations"
    assert empty["observations"] == 0


def test_risk_engines_align_unequal_histories_and_default_missing_weights() -> None:
    left = np.linspace(-0.01, 0.015, 30)
    right = np.linspace(0.01, -0.005, 25)
    strategies = [
        {"run_id": "left", "metrics": {"daily_returns": left.tolist()}},
        {"run_id": "right", "metrics": {"daily_returns": right.tolist()}},
    ]

    result = VaREngine().compute_from_active_strategies(strategies)
    concentration = ConcentrationEngine().compute(
        pd.DataFrame({"left": left[:25], "right": right}), weights=None
    )

    assert result["primary"]["observations"] == 25
    assert result["primary"]["input_observations"] == 30
    assert result["primary"]["observations_dropped"] == 5
    assert result["weights"] == {"left": 0.5, "right": 0.5}
    assert concentration["weights"] == {"left": 0.5, "right": 0.5}


def test_risk_engines_report_singular_and_constant_returns_without_nan() -> None:
    base = np.linspace(-0.01, 0.01, 40)
    singular = pd.DataFrame({"left": base, "right": base})
    concentration = ConcentrationEngine().compute(singular, [0.5, 0.5])
    constant = VaREngine().compute(pd.DataFrame({"cash": np.zeros(40)}))

    assert concentration["singular_covariance"] is True
    assert concentration["covariance_rank"] == 1
    assert all(np.isfinite(list(concentration["component_risk"].values())))
    assert constant["constant_returns"] is True
    assert constant["historical_var"] == 0
    assert constant["parametric_var"] == 0


def test_risk_engines_reject_too_short_history_and_zero_weights() -> None:
    short = pd.DataFrame({"left": np.arange(10), "right": np.arange(10)})
    enough = pd.DataFrame({"left": np.arange(25), "right": np.arange(25)})

    with pytest.raises(ValueError, match="at least 20 aligned"):
        VaREngine().compute(short)
    with pytest.raises(ValueError, match="at least 20 aligned"):
        ConcentrationEngine().compute(short)
    with pytest.raises(ValueError, match="positive gross exposure"):
        VaREngine().compute(enough, [0.0, 0.0])
    with pytest.raises(ValueError, match="positive gross exposure"):
        ConcentrationEngine().compute(enough, [0.0, 0.0])


def test_risk_extreme_leverage_is_gross_normalized_and_empty_active_set_fails() -> None:
    returns = pd.DataFrame(
        {
            "long": np.linspace(-0.02, 0.02, 40),
            "short": np.linspace(0.01, -0.01, 40),
        }
    )
    result = VaREngine().compute(returns, [100.0, -99.0])

    assert sum(abs(value) for value in result["weights"].values()) == pytest.approx(1.0)
    assert all(
        np.isfinite(result[key])
        for key in ("historical_var", "historical_cvar", "parametric_var")
    )
    with pytest.raises(ValueError, match="no daily return series"):
        VaREngine().compute_from_active_strategies([])


def test_risk_alert_ingestion_is_idempotent_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "alerts.sqlite3"
    first = AlertFeed(SQLiteStore(path))
    second = AlertFeed(SQLiteStore(path))
    breach = {
        "metric": "var_99_1d", "value": 0.08, "threshold": 0.05,
        "severity": "critical", "strategy_id": "alpha",
    }

    left = first.ingest_breaches("limits", [breach])[0]
    right = second.ingest_breaches("limits", [breach])[0]
    assert left["id"] == right["id"]
    assert len(first.list()) == 1

    first.acknowledge(left["id"], "operator")
    reopened = second.ingest_breaches("limits", [breach])[0]
    assert reopened["id"] == left["id"]
    assert reopened["acknowledged"] is False
    assert reopened["occurrence_count"] == 2
    assert len(second.list()) == 1


def test_journal_unicode_empty_content_and_duplicate_tags(tmp_path: Path) -> None:
    journal = JournalService(SQLiteStore(tmp_path / "journal.sqlite3"))

    entry = journal.create(
        {
            "title": "  Cafe\u0301 research 📈  ",
            "content": "",
            "tags": [" Alpha ", "alpha", "cafe\u0301", "café", ""],
            "linked_run_ids": ["run-1", "run-1", " run-2 "],
        }
    )

    assert entry["title"] == "Café research 📈"
    assert entry["content"] == ""
    assert entry["tags"] == ["Alpha", "café"]
    assert entry["linked_run_ids"] == ["run-1", "run-2"]
    assert entry["version"] == 1


def test_journal_rejects_oversized_entries(tmp_path: Path) -> None:
    journal = JournalService(SQLiteStore(tmp_path / "journal.sqlite3"))

    with pytest.raises(ValueError, match="title cannot exceed"):
        journal.create({"title": "x" * 301, "content": "ok"})
    with pytest.raises(ValueError, match="content cannot exceed"):
        journal.create({"title": "ok", "content": "x" * 200_001})
    with pytest.raises(ValueError, match="tags cannot exceed"):
        journal.create({"title": "ok", "tags": ["x" * 101]})


def test_journal_optimistic_concurrency_rejects_stale_edit(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    first = JournalService(SQLiteStore(path))
    second = JournalService(SQLiteStore(path))
    entry = first.create({"title": "Initial", "content": "evidence"})
    stale = second.list()[0]

    updated = first.update(
        entry["id"], {"expected_version": entry["version"], "title": "First edit"}
    )
    with pytest.raises(VersionConflictError, match="version conflict"):
        second.update(
            entry["id"],
            {"expected_version": stale["version"], "title": "Stale edit"},
        )

    assert updated["version"] == 2
    assert second.store.get("journal", entry["id"])["title"] == "First edit"


def test_journal_order_is_deterministic_when_timestamps_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(persistence, "utc_now", lambda: "2026-01-01T00:00:00+00:00")
    journal = JournalService(SQLiteStore(tmp_path / "journal.sqlite3"))
    created = [
        journal.create({"title": "B", "content": "two"}),
        journal.create({"title": "A", "content": "one"}),
    ]

    listed_ids = [entry["id"] for entry in journal.list()]
    assert listed_ids == sorted(entry["id"] for entry in created)


def test_journal_rejects_invalid_date_ranges_and_keeps_insert_pagination_stable(
    tmp_path: Path,
) -> None:
    journal = JournalService(SQLiteStore(tmp_path / "journal.sqlite3"))
    for index in range(4):
        journal.create({"title": f"Entry {index}", "content": "evidence"})
    baseline = journal.list(limit=10)
    first_page = journal.list(limit=2, offset=0)
    journal.create({"title": "Inserted later", "content": "new evidence"})
    second_page = journal.list(limit=2, offset=2)

    assert [row["id"] for row in first_page + second_page] == [
        row["id"] for row in baseline[:4]
    ]
    with pytest.raises(ValueError, match="date_from must be on or before date_to"):
        journal.list(date_from="2025-01-02", date_to="2025-01-01")
    with pytest.raises(ValueError, match="invalid journal date"):
        journal.list(date_from="not-a-date")


def test_deprecated_baseline_is_excluded_and_restore_audit_survives_reload(
    tmp_path: Path,
) -> None:
    path = tmp_path / "factors.sqlite3"
    store = SQLiteStore(path)
    governance = FactorGovernance(store)
    library = FactorLibrary(governance, store)
    baseline = library.get_baseline_factors()[0]
    governance.create_version(
        baseline.factor_id, baseline.expression, "reviewer", "baseline governance"
    )
    governance.approve(baseline.factor_id, "reviewer")

    governance.deprecate(baseline.factor_id, "risk", "unstable out of sample")
    reloaded = FactorLibrary(FactorGovernance(SQLiteStore(path)), SQLiteStore(path))
    assert baseline.factor_id not in {
        factor.factor_id for factor in reloaded.get_baseline_factors()
    }

    reloaded.governance.restore(baseline.factor_id, "risk", "revalidated")
    restored = FactorLibrary(FactorGovernance(SQLiteStore(path)), SQLiteStore(path))
    assert baseline.factor_id in {
        factor.factor_id for factor in restored.get_baseline_factors()
    }
    changelog = restored.governance.changelog(baseline.factor_id)
    assert [event["action"] for event in changelog][-2:] == ["deprecated", "restored"]
    assert changelog[-1]["reason"] == "revalidated"
    assert restored.governance.versions(baseline.factor_id)[-1]["version"] == 1


def test_futures_constant_maturity_reports_expiry_settlement_and_contract_gaps() -> None:
    contracts = [
        {"ticker": "F1", "date": "2024-01-01", "expiry": "2024-01-20", "settlement": 100.0, "close": 99.0},
        {"ticker": "F2", "date": "2024-01-01", "expiry": "2024-02-20", "settlement": 110.0, "close": 109.0},
        {"ticker": "BAD", "date": "2024-01-02", "expiry": None, "settlement": 1.0, "close": 1.0},
        {"ticker": "F2", "date": "2024-01-15", "expiry": "2024-02-20", "settlement": np.nan, "close": 112.0},
    ]

    result = MultiAssetCatalog().build_futures_universe(
        contracts, roll_method="constant_maturity", target_days=30
    )

    quality = result["data_quality"]
    assert result["price_source"] == "settlement_with_close_fallback"
    assert quality["missing_expiry_rows"] == 1
    assert quality["missing_settlement_rows"] == 1
    assert quality["insufficient_contract_dates"] == 1
    assert quality["calendar_gap_dates"] == ["2024-01-15"]
    assert "front-month fallback" in result["warning"]


def test_futures_ratio_roll_is_continuous_at_positive_boundary() -> None:
    contracts = [
        {"ticker": "F1", "date": "2024-01-01", "expiry": "2024-01-02", "close": 100.0},
        {"ticker": "F1", "date": "2024-01-02", "expiry": "2024-01-02", "close": 102.0},
        {"ticker": "F2", "date": "2024-01-02", "expiry": "2024-02-02", "close": 110.0},
        {"ticker": "F2", "date": "2024-01-03", "expiry": "2024-02-02", "close": 111.0},
    ]

    result = MultiAssetCatalog().build_futures_universe(
        contracts, roll_method="ratio_adjusted"
    )
    closes = [row["close"] for row in result["continuous"]]

    assert closes[-2] == pytest.approx(closes[-1])
    assert result["roll_audit"] == [
        {
            "date": "2024-01-03", "from": "F1", "to": "F2",
            "previous_price": 102.0, "current_price": 111.0,
            "method": "ratio_back_adjustment", "ratio": pytest.approx(111.0 / 102.0),
        }
    ]


def test_futures_negative_roll_uses_additive_adjustment() -> None:
    contracts = [
        {"ticker": "OIL1", "date": "2020-04-20", "expiry": "2020-04-20", "close": -5.0},
        {"ticker": "OIL1", "date": "2020-04-20", "expiry": "2020-04-20", "close": -10.0},
        {"ticker": "OIL2", "date": "2020-04-21", "expiry": "2020-05-20", "close": 20.0},
    ]

    result = MultiAssetCatalog().build_futures_universe(
        contracts, roll_method="ratio_adjusted"
    )

    assert result["data_quality"]["negative_price_rows"] == 1
    assert result["data_quality"]["duplicate_rows_dropped"] == 1
    assert result["roll_audit"][0]["method"] == "additive_back_adjustment"
    assert result["continuous"][0]["close"] == pytest.approx(20.0)
    assert result["continuous"][1]["close"] == pytest.approx(20.0)
    assert "non-positive roll boundary" in result["warning"]


def test_futures_zero_roll_price_never_divides_by_zero() -> None:
    contracts = [
        {"ticker": "F1", "date": "2024-01-01", "expiry": "2024-01-01", "close": 10.0},
        {"ticker": "F2", "date": "2024-01-02", "expiry": "2024-02-01", "close": 0.0},
    ]

    result = MultiAssetCatalog().build_futures_universe(
        contracts, roll_method="ratio_adjusted"
    )

    assert result["roll_audit"][0]["method"] == "additive_back_adjustment"
    assert all(np.isfinite(row["close"]) for row in result["continuous"])


def _synthetic_test_bars() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=35, freq="D")
    close = np.linspace(100.0, 120.0, len(dates))
    close[10] = close[9]
    volume = np.full(len(dates), 1_000.0)
    volume[10] = 0.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": volume,
            "adjusted_close": close,
            "dollar_volume": close * volume,
        }
    )


def test_synthetic_provenance_survives_real_backtest_and_stored_run_reload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database = tmp_path / "synthetic.sqlite3"
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(database))
    bars = _synthetic_test_bars()
    monkeypatch.setattr(
        backtest_engine_module,
        "get_ohlcv_batch",
        lambda tickers, start, end: {"SYN": bars.copy()},
    )
    SyntheticRangeDetector().record(
        "SYN", "2024-01-20", "2024-01-21", "vendor repair", "linear"
    )

    result = EventDrivenEngine().run(
        SimulationConfig(
            universe_id=["SYN"], date_start="2024-01-01", date_end="2024-02-04"
        )
    )
    repository = BacktestResultRepository(SQLiteStore(database))
    repository.save("synthetic-run", result)
    reloaded = BacktestResultRepository(SQLiteStore(database)).get_result("synthetic-run")

    audit = result.synthetic_data["SYN"]
    assert audit["has_synthetic_data"] is True
    assert any(row.get("reason") == "vendor repair" for row in audit["ranges"])
    assert any(row.get("observations") == 1 for row in audit["ranges"])
    assert reloaded["synthetic_data"]["SYN"]["has_synthetic_data"] is True
    assert any("Synthetic or imputed data detected" in warning for warning in reloaded["warnings"])


def test_synthetic_provenance_flows_through_factor_evaluation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database = tmp_path / "synthetic-factor.sqlite3"
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(database))
    bars = _synthetic_test_bars()
    monkeypatch.setattr(
        factor_evaluator_module,
        "get_ohlcv_batch",
        lambda tickers, start, end: {"SYN": bars.copy()},
    )
    SyntheticRangeDetector().record(
        "SYN", "2024-01-25", "2024-01-26", "manual repair", "backfill"
    )

    result = FactorExpressionEvaluator().evaluate(
        "close", ["SYN"], "2024-01-01", "2024-02-04"
    )

    assert result.validation.valid is True
    assert result.synthetic_data["has_synthetic_data"] is True
    audit = result.synthetic_data["tickers"]["SYN"]
    assert any(row.get("reason") == "manual repair" for row in audit["ranges"])
    assert audit["synthetic_fraction"] > 0
