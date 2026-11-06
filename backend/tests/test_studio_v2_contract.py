from __future__ import annotations

import io
import json
import asyncio
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.studio_v2.algorithm_lab.exporter import StandaloneExporter
from app.studio_v2.backtest.attribution import AttributionEngine
from app.studio_v2.backtest.tax_engine import TaxEngine
from app.studio_v2.backtest.monte_carlo import bootstrap_paths
from app.studio_v2.factors.composite_combiner import CompositeFactorCombiner
from app.studio_v2.factors.governance import FactorGovernance
from app.studio_v2.factors.library import FactorLibrary
from app.studio_v2.optimizer.cross_validation import OptimizerCrossValidation
from app.studio_v2.optimizer.multi_objective import ParetoOptimizer
from app.studio_v2.portfolio_risk.concentration import ConcentrationEngine
from app.studio_v2.portfolio_risk.var_engine import VaREngine
from app.studio_v2.robustness.data_source_test import DataSourceRobustnessTest
from app.studio_v2.contracts import RobustnessCoreRequest
from app.studio_v2.data_studio.explorer import DataExplorer
from app.studio_v2.router import router
from app.studio_v2.shared.persistence import SQLiteStore


def test_every_documented_new_route_is_registered() -> None:
    paths = {getattr(route, "path", "") for route in router.routes}
    required = {
        "/api/v2/algorithm-lab/templates",
        "/api/v2/algorithm-lab/strategies",
        "/api/v2/algorithm-lab/paper-trade/run",
        "/api/v2/algorithm-lab/push-to-backtest",
        "/api/v2/algorithm-lab/kernel/restore/{run_id}",
        "/api/v2/algorithm-lab/compose",
        "/api/v2/algorithm-lab/export/{strategy_id}",
        "/api/v2/algorithm-lab/session/{session_id}/collaborate",
        "/api/v2/algorithm-lab/snippets",
        "/api/v2/backtest/portfolio-run",
        "/api/v2/backtest/export/{run_id}",
        "/api/v2/backtest/attribution/{run_id}",
        "/api/v2/backtest/slippage-audit/{run_id}",
        "/api/v2/backtest/tax-report/{run_id}",
        "/api/v2/backtest/scenarios",
        "/api/v2/backtest/compare",
        "/api/v2/robustness/run-core-tests",
        "/api/v2/robustness/run-extended",
        "/api/v2/robustness/composite-score",
        "/api/v2/robustness/audit-trail/{strategy_id}",
        "/api/v2/robustness/adversarial",
        "/api/v2/factors/evaluate",
        "/api/v2/factors/library",
        "/api/v2/factors/library/{id}",
        "/api/v2/factors/library/{id}/restore",
        "/api/v2/factors/ic-diagnostics",
        "/api/v2/factors/library/{id}/versions",
        "/api/v2/optimizer/bayesian-search",
        "/api/v2/optimizer/ensemble",
        "/api/v2/optimizer/cross-validate",
        "/api/v2/optimizer/verdict",
        "/api/v2/optimizer/trials",
        "/api/v2/optimizer/studies",
        "/api/v2/optimizer/studies/{study_id}",
        "/api/v2/data-studio/asset-classes",
        "/api/v2/data-studio/catalog",
        "/api/v2/data-studio/freshness",
        "/api/v2/data-studio/explorer/series/{ticker}",
        "/api/v2/data-studio/explorer/anomalies",
        "/api/v2/data-studio/explorer/heatmap",
        "/api/v2/data-studio/universe/build",
        "/api/v2/data-studio/upload",
        "/api/v2/data-studio/manifests/refresh",
        "/api/v2/data-studio/events/{ticker}",
        "/api/v2/data-studio/synthetic-ranges/{ticker}",
        "/api/v2/portfolio-risk/active-strategies",
        "/api/v2/portfolio-risk/var",
        "/api/v2/portfolio-risk/correlation",
        "/api/v2/portfolio-risk/concentration",
        "/api/v2/portfolio-risk/limits",
        "/api/v2/portfolio-risk/alerts",
        "/api/v2/journal",
        "/api/v2/journal/tags",
    }
    assert required <= paths




def test_template_library_contains_seven_executable_templates() -> None:
    templates = asyncio.run(router.list_templates())
    assert len(templates) == 7
    for metadata in templates:
        detail = asyncio.run(router.get_template(metadata["id"]))
        source = detail["source_code"]
        compiled = compile(source, metadata["id"], "exec")
        namespace: dict = {}
        exec(compiled, namespace)
        assert "generate_signals" in source
        assert callable(namespace["generate_signals"])


def test_standalone_export_is_valid_zip() -> None:
    source = "import pandas as pd\nimport numpy as np\n\ndef generate_signals(data, config=None):\n    return data.pct_change()\n"
    archive = StandaloneExporter().build_zip("portable", source)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert {"strategy_module.py", "requirements.txt", "README.md"} <= set(bundle.namelist())
        compile(bundle.read("strategy_module.py"), "strategy_module.py", "exec")


def test_brinson_effects_reconcile_to_active_return() -> None:
    rows = [
        {"sector": "A", "portfolio_weight": 0.6, "benchmark_weight": 0.5, "portfolio_return": 0.12, "benchmark_return": 0.10},
        {"sector": "B", "portfolio_weight": 0.4, "benchmark_weight": 0.5, "portfolio_return": 0.03, "benchmark_return": 0.04},
    ]
    result = AttributionEngine.brinson(rows)
    portfolio_return = sum(row["portfolio_weight"] * row["portfolio_return"] for row in rows)
    benchmark_return = sum(row["benchmark_weight"] * row["benchmark_return"] for row in rows)
    assert result["active_return_explained"] == pytest.approx(portfolio_return - benchmark_return)


def test_tax_fifo_and_long_term_classification() -> None:
    trades = [
        {"ticker": "A", "quantity": 10, "price": 100, "date": "2020-01-01"},
        {"ticker": "A", "quantity": 5, "price": 120, "date": "2021-06-01"},
        {"ticker": "A", "quantity": -12, "price": 150, "date": "2022-01-02"},
    ]
    result = TaxEngine().apply_tax(trades, {"st_rate": 0.35, "lt_rate": 0.20})
    assert sum(row["quantity"] for row in result["realized_lots"]) == pytest.approx(12)
    assert {row["term"] for row in result["realized_lots"]} == {"LT", "ST"}
    assert result["summary"]["total_tax_paid"] == pytest.approx(500 * 0.20 + 60 * 0.35)


def test_composite_factor_is_weighted_normalized_sum() -> None:
    factors = {"value": [1, 2, 3, 4], "momentum": [4, 3, 2, 1]}
    result = CompositeFactorCombiner().combine(factors, {"value": 0.75, "momentum": 0.25})
    expected = result["normalized_factors"].mul(pd.Series(result["weights"]), axis=1).sum(axis=1)
    pd.testing.assert_series_equal(result["composite_score"], expected)


def test_pareto_frontier_excludes_dominated_trial() -> None:
    trials = [
        {"id": "a", "return": 0.2, "risk": 0.1},
        {"id": "b", "return": 0.1, "risk": 0.2},
        {"id": "c", "return": 0.3, "risk": 0.3},
    ]
    result = ParetoOptimizer().frontier(trials, {"return": "max", "risk": "min"})
    assert {row["id"] for row in result["frontier"]} == {"a", "c"}


def test_purged_cross_validation_has_no_train_test_overlap() -> None:
    observations = [{"return": value} for value in np.linspace(-0.01, 0.01, 100)]
    result = OptimizerCrossValidation().run(observations, folds=5, purge=2, embargo=3)
    assert len(result["folds"]) == 5
    assert all(row["train_size"] + row["test_size"] < 100 for row in result["folds"])


def test_var_and_component_risk_are_finite_and_reconcile() -> None:
    rng = np.random.default_rng(4)
    returns = pd.DataFrame(rng.normal(0, 0.01, (500, 3)), columns=["A", "B", "C"])
    weights = [0.5, 0.3, 0.2]
    var = VaREngine().compute(returns, weights)
    concentration = ConcentrationEngine().compute(returns, weights)
    assert var["historical_cvar"] >= var["historical_var"] >= 0
    assert sum(concentration["component_risk"].values()) == pytest.approx(concentration["portfolio_volatility"])


def test_data_source_robustness_detects_drift() -> None:
    dates = pd.date_range("2024-01-01", periods=20)
    close = np.linspace(100, 120, 20)
    sources = {
        "reference": [{"date": str(date), "close": value} for date, value in zip(dates, close)],
        "aligned": [{"date": str(date), "close": value * 1.00001} for date, value in zip(dates, close)],
    }
    result = DataSourceRobustnessTest().run(sources, tolerance_bps=1)
    assert result["passed"]
    assert result["comparisons"][0]["correlation"] == pytest.approx(1.0)


def test_public_read_routes_smoke() -> None:
    assert asyncio.run(router.asset_classes())
    assert asyncio.run(router.list_scenarios())
    assert isinstance(asyncio.run(router.journal_tags()), list)


def test_data_preview_is_recent_and_server_bounded(monkeypatch) -> None:
    dates = pd.date_range("2025-01-01", periods=700, freq="D")
    frame = pd.DataFrame({
        "date": dates,
        "open": np.arange(700, dtype=float) + 100,
        "high": np.arange(700, dtype=float) + 101,
        "low": np.arange(700, dtype=float) + 99,
        "close": np.arange(700, dtype=float) + 100.5,
        "adjusted_close": np.arange(700, dtype=float) + 100.5,
        "volume": np.full(700, 1_000.0),
        "dollar_volume": np.full(700, 100_000.0),
    })
    monkeypatch.setattr(
        "app.studio_v2.data_studio.explorer.get_ohlcv",
        lambda ticker, start, end: frame.copy(),
    )

    preview = DataExplorer().get_primary_series("SPY", None, None, limit=9_999)

    assert len(preview) == 500
    assert preview.iloc[0]["date"] == dates[200]
    assert preview.iloc[-1]["date"] == dates[-1]


def test_frontend_data_and_library_routes_return_typed_shapes() -> None:
    library = asyncio.run(router.list_factor_library())
    assert len(library) >= 40
    assert {"factor_id", "name", "expression"} <= set(library[0])

    catalog = asyncio.run(router.data_catalog())
    assert {"market_universe", "category7_macro", "ff3", "ff5", "momentum", "crypto", "fx", "futures"} <= {
        row["name"] for row in catalog
    }
    freshness = asyncio.run(router.data_freshness())
    assert len(freshness) == len(catalog)
    assert all({"source_name", "status", "lag_trading_days"} <= set(row) for row in freshness)
    assert all(row["freshness_slo_trading_days"] >= 0 for row in freshness)
    assert all(row["data_as_of"] for row in freshness if row["source_name"] != "fundamentals")

    universe = asyncio.run(router.build_universe({"tickers": ["spy", "QQQ"], "operation": "universe"}))
    assert universe["constituents"] == ["SPY", "QQQ"]
    assert universe["count"] == 2
    assert asyncio.run(router.optimizer_trials("default")) == []

    verdict = asyncio.run(router.optimizer_verdict(0.8, 0.1, 0.75, 0.8))
    assert verdict["color"] == "green"
    assert [row["name"] for row in verdict["criteria"]] == [
        "DSR", "PBO", "IS/OOS ratio", "parameter stability"
    ]


def test_algorithm_handoff_checkpoint_and_backtest_export() -> None:
    source = "def generate_signals(data):\n    return {'SPY': 1.0}\n"
    handoff = asyncio.run(router.push_to_backtest({
        "strategy_source": source,
        "name": "contract-handoff",
        "target": "backtest",
        "default_config": {"universe_id": ["SPY"]},
    }))
    assert handoff["status"] == "ready"
    assert handoff["backtest_config"]["strategy_source"].endswith(".py")

    router.kernel.start_session("checkpoint-contract", {"alpha": 1})
    router.kernel.save_checkpoint("checkpoint-contract-run", "checkpoint-contract")
    restored = asyncio.run(router.restore_kernel("checkpoint-contract-run"))
    assert restored["status"] == "restored"
    assert restored["session_id"] == "checkpoint-contract"

    run_id = "export-contract-run"
    router.results.save(run_id, {"equity_curve": [{"date": "2024-01-01", "equity": 1.0}], "trade_log": []}, {"sharpe": 1.2})
    response = asyncio.run(router.export_backtest(run_id, {"format": "json", "sections": ["metrics", "equity"]}))
    async def consume() -> bytes:
        return b"".join([chunk async for chunk in response.body_iterator])
    exported = json.loads(asyncio.run(consume()))
    assert exported["run_id"] == run_id
    assert exported["sections"]["metrics"]["sharpe"] == pytest.approx(1.2)


@pytest.mark.parametrize("payload", [
    {"test": "timing", "n_simulations": 250, "trade_log": []},
    {"test": "universe", "tickers": ["SPY", "QQQ"], "drop_pct": 0.10, "n_simulations": 250},
    {"test": "noise", "noise_bps": 5, "n_simulations": 250},
    {"test": "parameter", "parameter_grid": {"lookback": [10, 20], "threshold": [0.1, 0.2]}, "observations": []},
])
def test_robustness_panel_discriminators_are_contract_compatible(payload: dict) -> None:
    validated = RobustnessCoreRequest.model_validate(payload)
    assert validated.test == payload["test"]


def test_extended_robustness_is_bounded_reproducible_and_persisted() -> None:
    rng = np.random.default_rng(11)
    returns_by_ticker = {
        ticker: rng.normal(0.0005, 0.01, 80).tolist()
        for ticker in ("A", "B", "C", "D")
    }
    request = {
        "test": "universe", "returns_by_ticker": returns_by_ticker,
        "drop_pct": 0.25, "n_simulations": 25, "seed": 9,
    }
    first = asyncio.run(router.robustness_extended(request))
    second = asyncio.run(router.robustness_extended(request))
    assert first["universe"] == second["universe"]
    assert first["universe"]["simulations"] == 25
    assert 0 <= first["universe"]["failure_rate"] <= 1
    latest = asyncio.run(router.robustness_composite())
    assert "missing_components" in latest

    cost = asyncio.run(router.robustness_extended({
        "test": "cost",
        "cost_sharpes": [{"cost_bps": 0, "sharpe": 1.0}, {"cost_bps": 10, "sharpe": 0.5}, {"cost_bps": 20, "sharpe": 0.0}],
        "realistic_band": [5, 15],
    }))
    assert cost["cost"]["breakeven_bps"] == pytest.approx(20)
    assert cost["composite"]["component_scores"]["cost"] == pytest.approx(1.0)


def test_factor_library_crud_persists_across_instances(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "factor-library.sqlite3")
    governance = FactorGovernance(store)
    library = FactorLibrary(governance, store)
    metrics = {"ic_tstat": 2.5, "orthogonalized_icir": 0.08, "half_life": 20, "crowding_pctile": 40}
    factor_id = library.add_factor("Persistent value", "rank(book_to_market)", metrics, "researcher")

    reloaded = FactorLibrary(FactorGovernance(store), store)
    assert reloaded.get_factor_by_id(factor_id).name == "Persistent value"
    updated = reloaded.update_factor(factor_id, "zscore(book_to_market)", "reviewer", "normalize")
    assert updated.expression == "zscore(book_to_market)"
    assert len(governance.versions(factor_id)) == 2

    assert not reloaded.remove_factor(factor_id).is_active
    assert not FactorLibrary(FactorGovernance(store), store).get_factor_by_id(factor_id).is_active
    restored = reloaded.restore_factor(factor_id, "reviewer", "approved after review")
    assert restored.is_active
    assert governance.status(factor_id)["status"] == "approved"


def test_backtest_monte_carlo_is_bounded_deterministic_and_nonempty() -> None:
    returns = np.linspace(-0.02, 0.025, 80)
    first = bootstrap_paths(returns, initial_value=1_000_000, paths=40, seed=17)
    second = bootstrap_paths(returns, initial_value=1_000_000, paths=40, seed=17)
    assert first == second
    assert len(first["paths"]) == 40
    assert len(first["paths"][0]) == 81
    assert 0 <= first["loss_probability"] <= 1
    assert first["drawdown_95"] <= 0
    with pytest.raises(ValueError, match="between 0 and 1000"):
        bootstrap_paths(returns, paths=1_001)


def test_kernel_execution_is_isolated_and_cancellable() -> None:
    async def verify() -> None:
        normal = await router.execute_code({"session_id": "process-test", "cell_id": "fast", "code": "answer = 42"})
        assert normal["status"] == "ok"
        assert (await router.variables("process-test"))["answer"] == "int"

        pending = asyncio.create_task(router.execute_code({
            "session_id": "process-kill-test",
            "cell_id": "slow",
            "code": "import time\ntime.sleep(30)\nnever_written = True",
        }))
        await asyncio.sleep(0.2)
        status = await router.compute_status("process-kill-test")
        assert len(status["running"]) == 1
        killed = await router.kill_job("process-kill-test", status["running"][0]["job_id"])
        assert killed["killed"]
        assert (await asyncio.wait_for(pending, 3))["status"] == "killed"

    asyncio.run(verify())
