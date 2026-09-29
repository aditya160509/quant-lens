from __future__ import annotations

import asyncio
import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import httpx
from fastapi import FastAPI

from app.studio_v2.backtest.attribution import AttributionEngine
from app.studio_v2.backtest.repository import BacktestResultRepository
from app.studio_v2.backtest.portfolio_engine import PortfolioBacktestEngine
from app.studio_v2.algorithm_lab.portfolio_composer import PortfolioComposer
from app.studio_v2.algorithm_lab.repository import StrategyRepository
from app.studio_v2.data_studio.multi_asset import MultiAssetCatalog
from app.studio_v2.data_studio.event_calendar import EventCalendar
from app.studio_v2.data_studio.synthetic_flagging import SyntheticRangeDetector
from app.studio_v2.factors.composite_combiner import CompositeFactorCombiner
from app.studio_v2.factors.turnover_estimator import TurnoverDecayEstimator
from app.studio_v2.optimizer.cross_validation import OptimizerCrossValidation
from app.studio_v2.optimizer.ensemble import ParameterEnsemble
from app.studio_v2.optimizer.multi_objective import ParetoOptimizer
from app.studio_v2.portfolio_risk.alert_feed import AlertFeed
from app.studio_v2.portfolio_risk.concentration import ConcentrationEngine
from app.studio_v2.portfolio_risk.limits import RiskLimitService
from app.studio_v2.portfolio_risk.var_engine import VaREngine
from app.studio_v2.robustness.adversarial import AdversarialStressTest
from app.studio_v2.robustness.audit_trail import AuditTrail
from app.studio_v2.robustness.data_source_test import DataSourceRobustnessTest
from app.studio_v2.robustness.parameter_interaction import ParameterInteractionTest
from app.studio_v2.services.journal_service import JournalService
from app.studio_v2.router import Router
from app.studio_v2.shared import data_loader
from app.studio_v2.shared.data_loader import get_factor_returns, get_returns
from app.studio_v2.shared.data_manifest import validate_manifest
from app.studio_v2.shared.liquidity import LiquidityCalibrator
from app.studio_v2.shared.persistence import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "studio-test.sqlite3")


def test_factor_loader_uses_backend_factor_data_and_scales_percent() -> None:
    ff3 = get_factor_returns("ff3")
    ff5 = get_factor_returns("ff5")
    momentum = get_factor_returns("momentum")
    assert {"mkt-rf", "smb", "hml", "rf"} <= set(ff3)
    assert {"mkt-rf", "smb", "hml", "rmw", "cma", "rf"} <= set(ff5)
    assert not momentum.empty
    assert ff5.index.is_monotonic_increasing
    assert float(ff5.abs().quantile(0.99).max()) < 1.0
    assert float(momentum.abs().quantile(0.99).max()) < 1.0


def test_factor_loader_prefers_manifest_backed_parquet(monkeypatch: pytest.MonkeyPatch) -> None:
    data_loader._load_factor_file.cache_clear()

    def reject_csv(*args: object, **kwargs: object) -> None:
        raise AssertionError("CSV fallback should not be used when factor parquet exists")

    monkeypatch.setattr(pd, "read_csv", reject_csv)
    manifest = validate_manifest(deep=False)
    expected_rows = {
        dataset["id"]: dataset["rows"] for dataset in manifest["datasets"]
    }
    assert len(get_factor_returns("ff3")) == expected_rows["fama_french_3_daily"]
    assert len(get_factor_returns("ff5")) == expected_rows["fama_french_5_daily"]
    assert len(get_factor_returns("momentum")) == expected_rows["momentum_daily"]


def test_dataset_manifest_deep_validation() -> None:
    validation = validate_manifest(deep=True)
    assert validation["healthy"] is True
    assert len(validation["datasets"]) == 6
    assert all(dataset["checksum_verified"] for dataset in validation["datasets"])
    assert all(dataset["status"] == "healthy" for dataset in validation["datasets"])


def test_bounded_market_request_uses_predicate_pushdown_not_full_table() -> None:
    data_loader._load_universe.cache_clear()
    data_loader._load_universe_subset.cache_clear()
    rows = data_loader.get_ohlcv_batch(
        ["AAPL", "MSFT"],
        start="2024-01-01",
        end="2024-12-31",
    )
    assert set(rows) == {"AAPL", "MSFT"}
    assert all(len(frame) > 200 for frame in rows.values())
    assert data_loader._load_universe_subset.cache_info().misses == 1
    assert data_loader._load_universe.cache_info().misses == 0


def test_studio_v2_runtime_has_no_apdi_dependency() -> None:
    studio_root = Path(data_loader.__file__).resolve().parents[1]
    runtime_sources = [
        path.read_text(encoding="utf-8")
        for path in studio_root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert "APDI/" not in "\n".join(runtime_sources)


def test_liquidity_calibration_is_bounded_and_cached() -> None:
    data_loader._load_universe.cache_clear()
    calibrator = LiquidityCalibrator()
    first = calibrator.calibrate(pd.Timestamp("2025-01-31"))
    second = calibrator.calibrate(pd.Timestamp("2025-01-31"))
    assert first == second
    assert set(first) == {"large", "mid", "small"}
    assert all(np.isfinite(value) and value > 0 for value in first.values())
    assert data_loader._load_universe.cache_info().misses == 0


@pytest.mark.parametrize("asset_class,ticker", [
    ("fx", "AUDJPY=X"),
    ("crypto", "AVAX_USD"),
    ("future", "BZ=F"),
])
def test_canonical_multi_asset_returns_are_reachable(asset_class: str, ticker: str) -> None:
    values = get_returns([ticker], asset_class=asset_class)
    assert ticker in values
    assert values[ticker].notna().sum() > 100


def test_multi_asset_catalog_exposes_real_canonical_universes() -> None:
    catalog = MultiAssetCatalog()
    assert "AVAX_USD" in catalog.build_crypto_universe(quote_currency="USD")["instruments"]
    assert "AUDJPY=X" in catalog.build_fx_universe("deliverable_spot")["instruments"]
    futures = catalog.build_futures_universe(roll_method="ratio_adjusted")
    assert futures["continuous"]
    assert futures["warning"]


def test_event_calendar_auto_populates_fundamental_and_index_events(store: SQLiteStore) -> None:
    events = EventCalendar(store).get("AAPL", start="2024-01-01", end="2026-12-31")
    types = {row["event_type"] for row in events}
    assert "earnings" in types
    assert "index_rebalance" in types
    assert all(row["ticker"] == "AAPL" for row in events)
    index_events = [row for row in events if row["event_type"] == "index_rebalance"]
    assert all(row["source"] == "market_universe_trading_calendar" for row in index_events)
    assert all(row["is_proxy"] is True for row in index_events)


def test_repository_batch_helpers_and_compare_inputs(store: SQLiteStore) -> None:
    repository = BacktestResultRepository(store)
    repository.save("a", {"daily_returns": [0.01, 0.02], "equity_curve": [1, 1.01]}, {"sharpe": 1})
    repository.save("b", {"daily_returns": [0.02, 0.01], "equity_curve": [1, 1.02]}, {"sharpe": 2})
    assert repository.batch_get_metrics(["b", "a"])["b"]["sharpe"] == 2
    assert repository.batch_get_equity_curves(["a"])["a"] == [1, 1.01]
    assert set(repository.batch_get_daily_returns(["a", "b"])) == {"a", "b"}


def test_portfolio_backtest_resolves_composition_and_full_response(store: SQLiteStore,
                                                                  tmp_path: Path) -> None:
    strategies = StrategyRepository(store, tmp_path / "strategies")
    source = (
        "STUDIO_INPUT = 'wide_close'\n"
        "def generate_signals(data, config=None):\n"
        "    lookback = int((config or {}).get('lookback', 5))\n"
        "    return (data.pct_change(lookback) > 0).astype(float)\n"
    )
    left = strategies.create("left", source, default_config={"lookback": 3})
    right = strategies.create("right", source, default_config={"lookback": 8})
    composer = PortfolioComposer(store, strategies)
    composition = composer.create(
        [left["strategy_id"], right["strategy_id"]], "equal_weight", "Test portfolio"
    )
    engine = PortfolioBacktestEngine(BacktestResultRepository(store), composer, strategies)
    result = engine.run({
        "composition_id": composition["composition_id"],
        "shared_config": {
            "universe_id": ["AAPL", "MSFT"],
            "date_start": "2024-01-01",
            "date_end": "2024-06-30",
        },
    })
    assert result["composition_id"] == composition["composition_id"]
    assert len(result["per_strategy"]) == 2
    assert set(result["correlation_matrix"].columns) == {"left", "right"}
    assert {"equity_curve", "sharpe", "sortino", "max_drawdown", "calmar"} <= set(result["combined"])


def test_attribution_contract_exposes_totals_sectors_and_factors() -> None:
    payload = {
        "benchmark_name": "SPY",
        "sector_rows": [
            {"sector": "Tech", "portfolio_weight": .6, "benchmark_weight": .5,
             "portfolio_return": .12, "benchmark_return": .10},
            {"sector": "Other", "portfolio_weight": .4, "benchmark_weight": .5,
             "portfolio_return": .03, "benchmark_return": .04},
        ],
        "returns": [.01, .02, -.01, .03, .01],
        "factor_returns": {"MKT": [.01, .01, -.02, .02, .01]},
    }
    result = AttributionEngine().compute(payload)
    assert result["benchmark_name"] == "SPY"
    assert len(result["sectors"]) == 2
    assert len(result["factors"]) == 1
    assert result["total_allocation_effect"] == result["allocation_effect"]


def test_gaussian_robustness_is_deterministic_and_bounded() -> None:
    returns = np.sin(np.linspace(0, 20, 300)) * .005 + .0005
    first = DataSourceRobustnessTest().perturb(returns, simulations=200, seed=9)
    second = DataSourceRobustnessTest().perturb(returns, simulations=200, seed=9)
    assert first == second
    assert 0 <= first["sensitivity_score"] <= 1
    assert set(first["percentiles"]) == {"p5", "p25", "p50", "p75", "p95"}


def test_gaussian_robustness_executes_real_strategy_on_perturbed_prices(tmp_path: Path) -> None:
    source = tmp_path / "strategy.py"
    source.write_text(
        "STUDIO_INPUT = 'wide_close'\n"
        "def generate_signals(data, config=None):\n"
        "    return data.pct_change().rolling(5).mean().apply(lambda x: (x > 0) * 1.0)\n"
    )
    prices = pd.DataFrame({
        "A": 100 * np.cumprod(1 + np.sin(np.linspace(0, 10, 80)) * .002 + .0003),
        "B": 100 * np.cumprod(1 + np.cos(np.linspace(0, 10, 80)) * .002),
    })
    result = DataSourceRobustnessTest().perturb_strategy(
        prices, str(source), simulations=10, seed=11,
    )
    assert result["method"] == "strategy_gaussian_price_perturbation"
    assert result["simulations"] == 10
    assert np.isfinite(result["mean_perturbed_sharpe"])


def test_adversarial_search_returns_constrained_baseline_comparison(store: SQLiteStore) -> None:
    rng = np.random.default_rng(5)
    returns = rng.normal(.0004, .01, 400)
    result = AdversarialStressTest(store).run(returns, window=63)
    assert result["method"] == "constrained_historical_window_search"
    assert {"baseline", "adversarial", "degradation_percentage", "recovery_days",
            "survival_verdict", "constraints"} <= set(result)
    assert result["candidates_evaluated"] > 0


def test_parameter_interaction_contract_has_grid_stability_and_verdict() -> None:
    test = ParameterInteractionTest()
    grid = test.auto_grid({"lookback": [5, 25], "threshold": [0.1, 0.5]})
    rows = [
        {"lookback": left, "threshold": right, "sharpe": left * .01 + right}
        for left in grid["lookback"] for right in grid["threshold"]
    ]
    result = test.run(grid, observations=rows)
    assert all(len(values) == 11 for values in grid.values())
    assert result["objective"] == "sharpe"
    assert result["verdict"] in {"independent", "interaction", "strong"}
    assert set(result["marginal_stability"]) == {"lookback", "threshold"}


def test_composite_supports_ic_ir_and_safe_custom_combiner() -> None:
    factors = {"value": [1, 2, 3, 4, 5], "momentum": [5, 3, 4, 2, 1]}
    histories = {"value": [.03, .04, .02], "momentum": [.01, -.01, .02]}
    weighted = CompositeFactorCombiner().combine(
        factors, weighting="ic_ir", ic_history=histories
    )
    assert weighted["weighting"] == "ic_ir"
    custom = CompositeFactorCombiner().combine(
        factors, weighting="custom",
        custom_code="def combine(factors_dict):\n    return factors_dict['value'] - factors_dict['momentum']\n",
    )
    assert len(custom["composite_score"]) == 5
    with pytest.raises(ValueError):
        CompositeFactorCombiner().combine(
            factors, weighting="custom",
            custom_code="import os\ndef combine(factors_dict):\n return factors_dict['value']\n",
        )


def test_turnover_decay_returns_cost_regions_and_implementability() -> None:
    rng = np.random.default_rng(3)
    scores = pd.DataFrame(rng.normal(size=(100, 8)))
    forward = scores.shift(1) * .01 + rng.normal(0, .001, scores.shape)
    result = TurnoverDecayEstimator().estimate(scores, forward, asset_class="fx")
    assert result["realistic_cost_bps"] == 2
    assert len(result["chart_data"]) == 5
    assert all({"break_even_cost_bps", "implementable", "region"} <= set(row)
               for row in result["chart_data"])


def test_optimizer_region_overlap_hypervolume_and_signal_ensemble() -> None:
    trials = [
        {"trial_id": "a", "x": 1, "y": 1, "objective": 2.0, "risk": .2},
        {"trial_id": "b", "x": 2, "y": 2, "objective": 1.5, "risk": .1},
        {"trial_id": "c", "x": 3, "y": 3, "objective": .2, "risk": .3},
    ]
    region = OptimizerCrossValidation().compare_regions(
        trials,
        [{"optimal_params": {"x": 1, "y": 1}}],
        top_fraction=.34,
    )
    assert region["verdict"] in {"stable", "diverging", "divergent"}
    assert region["overlay"]
    pareto = ParetoOptimizer().frontier(trials, {"objective": "max", "risk": "min"})
    assert 0 <= pareto["hypervolume"] <= 1
    assert len(pareto["hypervolume_progression"]) == 3
    ensemble = ParameterEnsemble().build(
        trials, top_n=2, return_series={"a": [.01, .02, -.01], "b": [.02, .01, 0]}
    )
    assert ensemble["mode"] == "signal_ensemble"
    assert len(ensemble["ensemble_returns"]) == 3
    assert "overfitting_warning" in ensemble["distribution"]


def test_synthetic_ranges_are_explicit_and_portfolio_auditable(store: SQLiteStore) -> None:
    detector = SyntheticRangeDetector(store)
    detector.record("AAPL", "2024-01-01", "2024-01-05", "missing vendor bars", "linear")
    result = detector.detect("AAPL", [{"date": "2024-01-01", "close": 100, "volume": 1}])
    assert result["has_synthetic_data"]
    assert detector.get_all_ranges("AAPL")[0]["method"] == "linear"


def test_overlap_limits_alerts_and_active_var(store: SQLiteStore) -> None:
    overlap = ConcentrationEngine.overlapping_positions({
        "alpha": {"AAPL": .4, "MSFT": .2},
        "beta": {"AAPL": .3, "NVDA": .2},
    })
    assert overlap[0]["ticker"] == "AAPL"
    strategies = [
        {"run_id": "a", "metrics": {"daily_returns": [.01, -.01, .02] * 30}},
        {"run_id": "b", "metrics": {"daily_returns": [.02, -.005, .01] * 30}},
    ]
    var = VaREngine().compute_from_active_strategies(strategies)
    assert set(var["combinations"]) == {"95pct_1d", "95pct_10d", "99pct_1d", "99pct_10d"}
    limits = RiskLimitService(store, strategy_provider=lambda: strategies)
    limits.replace([{"id": "var", "metric": "var_99_1d", "operator": "max",
                     "threshold": 0.001, "severity": "critical"}])
    computed = limits.get_computed_breaches()
    assert computed["current_values"]["active_strategy_count"] == 2
    alerts = AlertFeed(store)
    alerts.ingest_breaches("limits", computed["breaches"])
    assert alerts.list(severity="critical", limit=10)


def test_journal_date_filters_and_pagination(store: SQLiteStore) -> None:
    journal = JournalService(store)
    for index in range(4):
        journal.create({"title": f"Note {index}", "content": "evidence", "tags": ["alpha"]})
    assert len(journal.list(limit=2, offset=1)) == 2
    assert len(journal.list(tag="alpha", date_from="2000-01-01", date_to="2100-01-01")) == 4
    with pytest.raises(ValueError):
        journal.list(limit=501)


def test_audit_sections_hash_and_pdf(store: SQLiteStore) -> None:
    audit = AuditTrail(store)
    record = audit.create("strategy", "def generate_signals(data): return data", [],
                          {"purge": 5, "embargo": 5, "fill_timing": []})
    assert set(record["sections"]) == {"linter_section", "engine_section", "cv_section"}
    assert audit.verify(record)
    pdf = audit.render_pdf(record)
    assert pdf.startswith(b"%PDF")


def test_every_mutating_api_has_a_named_validated_payload_schema() -> None:
    app = FastAPI()
    app.include_router(Router())
    schema = app.openapi()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"post", "put"}:
                continue
            body = operation.get("requestBody")
            if body is None:
                continue
            content = body["content"]
            media_type = (
                "application/json"
                if "application/json" in content
                else "multipart/form-data"
            )
            payload_schema = content[media_type]["schema"]
            assert "$ref" in payload_schema or "$ref" in payload_schema.get("items", {}), (
                method, path, payload_schema
            )


def test_every_http_api_has_named_response_and_error_schemas() -> None:
    app = FastAPI()
    app.include_router(Router())
    schema = app.openapi()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            success = operation["responses"].get("200", {})
            payload = success.get("content", {}).get("application/json", {}).get("schema")
            if path.endswith("/export/{strategy_id}"):
                continue
            assert payload, (method, path, "missing success schema")
            assert "$ref" in payload or "$ref" in payload.get("items", {}) or payload.get("items", {}).get("type") == "string", (
                method, path, payload
            )
            for status in ("400", "403", "404", "409", "422", "500"):
                error_schema = operation["responses"][status]["content"]["application/json"]["schema"]
                assert error_schema["$ref"].endswith("/ErrorResponse"), (method, path, status)


def test_http_payload_validation_pagination_and_new_universe_routes(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "http.sqlite3"))
    app = FastAPI()
    app.include_router(Router())

    async def exercise_api() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            invalid = await client.post("/api/v2/robustness/adversarial", json={"returns": [0.1]})
            assert invalid.status_code == 422
            invalid_extra = await client.post("/api/v2/backtest/compare", json={
                "run_ids": ["a", "b"], "unknown": True,
            })
            assert invalid_extra.status_code == 422
            created = await client.post("/api/v2/journal", json={
                "title": "Contract evidence", "content": "validated", "tags": ["api"],
            })
            assert created.status_code == 200
            page = await client.get("/api/v2/journal", params={"limit": 1, "offset": 0})
            assert page.json()[0]["title"] == "Contract evidence"
            assert (await client.get("/api/v2/journal", params={"limit": 501})).status_code == 422
            crypto = await client.get("/api/v2/data-studio/universes/crypto", params={"quote_currency": "USD"})
            assert crypto.status_code == 200
            assert crypto.json()["asset_class"] == "crypto"
            manifests = await client.get("/api/v2/data-studio/manifests")
            assert manifests.status_code == 200
            assert manifests.json()["healthy"] is True
            missing = await client.get("/api/v2/backtest/result/does-not-exist")
            assert missing.status_code == 404
            assert missing.json()["detail"]["code"] == "not_found"
            malformed = await client.get("/api/v2/portfolio-risk/correlation", params={
                "returns": "{not-json}", "weights": "{}",
            })
            assert malformed.status_code == 422
            assert malformed.json()["detail"]["code"] == "invalid_request"

    asyncio.run(exercise_api())
