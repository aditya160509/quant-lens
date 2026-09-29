import math

import numpy as np
import pytest

from app.services.studio.metrics import calculate_performance_metrics
import asyncio

import pytest
from fastapi import HTTPException

from app.routers.studio import MonteCarloEngine, WalkForwardEngine, get_tickers, health_check, router


def test_retired_dynamics_route_is_not_exposed() -> None:
    paths = {getattr(route, "path", "") for route in router.routes}

    assert "/studio/dynamics" not in paths
    assert "/studio/data" in paths


def test_ticker_catalog_rejects_unknown_universe() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_tickers(universe="not-a-real-universe"))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "UNIVERSE_UNKNOWN"


def test_ticker_catalog_response_is_versioned() -> None:
    response = asyncio.run(get_tickers(q="SPY", universe="all"))

    assert response["status"] == "success"
    assert response["contract_version"] == "1.0"


def test_health_is_liveness_not_execution_readiness() -> None:
    response = asyncio.run(health_check())

    assert response["status"] == "ok"
    assert response["check"] == "liveness"
    assert response["execution"]["readiness"] == "not_checked"


def test_metrics_match_independent_deterministic_fixture() -> None:
    returns = np.array([0.01, -0.02, 0.03, 0.005], dtype=float)
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    trades = [
        {"pnl": 0.04, "holding_period": 3, "mae": -0.01, "mfe": 0.06},
        {"pnl": -0.02, "holding_period": 5, "mae": -0.03, "mfe": 0.01},
    ]

    bundle = calculate_performance_metrics(
        equity,
        trades,
        periods_per_year=252,
        annual_risk_free_rate=0.0,
        turnover=0.75,
        average_exposure=0.8,
    )

    expected_total = float(np.prod(1.0 + returns) - 1.0)
    expected_vol = float(np.std(returns, ddof=0) * math.sqrt(252))
    assert bundle.metrics["total_return"].value == pytest.approx(expected_total, abs=1e-10)
    assert bundle.metrics["volatility"].value == pytest.approx(expected_vol, abs=1e-10)
    assert bundle.metrics["hit_rate"].value == pytest.approx(0.5, abs=1e-10)
    assert bundle.metrics["payoff"].value == pytest.approx(2.0, abs=1e-10)
    assert bundle.metrics["average_holding_period"].value == pytest.approx(4.0, abs=1e-10)
    assert bundle.metrics["mae"].value == pytest.approx(-0.02, abs=1e-10)
    assert bundle.metrics["mfe"].value == pytest.approx(0.035, abs=1e-10)
    assert bundle.metrics["average_win"].value == pytest.approx(0.04, abs=1e-10)
    assert bundle.metrics["average_loss"].value == pytest.approx(-0.02, abs=1e-10)
    assert bundle.metrics["expectancy"].value == pytest.approx(0.01, abs=1e-10)
    assert bundle.metrics["max_win"].value == pytest.approx(0.04, abs=1e-10)
    assert bundle.metrics["max_loss"].value == pytest.approx(-0.02, abs=1e-10)


def test_missing_inputs_are_unavailable_not_zero() -> None:
    bundle = calculate_performance_metrics([1.0, 1.01, 1.02])

    assert bundle.metrics["beta"].value is None
    assert bundle.metrics["beta"].status == "unavailable"
    assert bundle.metrics["average_holding_period"].value is None
    assert bundle.metrics["cost_drag"].value is None
    assert bundle.warnings[0].code == "METRICS_UNAVAILABLE"


def test_insufficient_or_nonfinite_equity_is_explicitly_unavailable() -> None:
    for equity in ([1.0], [1.0, float("nan")], [1.0, 0.0]):
        bundle = calculate_performance_metrics(equity)
        assert bundle.metrics["total_return"].value is None
        assert bundle.metrics["total_return"].status == "unavailable"
        assert bundle.warnings[0].code == "INSUFFICIENT_EQUITY"


def test_benchmark_must_be_aligned_and_finite() -> None:
    with pytest.raises(ValueError, match="aligned"):
        calculate_performance_metrics([1.0, 1.01, 1.02], benchmark_returns=[0.01])


def test_benchmark_relative_metrics_are_deterministic() -> None:
    returns = np.array([0.01, -0.01, 0.02, 0.005])
    benchmark = np.array([0.005, -0.005, 0.01, 0.0])
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    bundle = calculate_performance_metrics(equity, benchmark_returns=benchmark)

    expected_beta = float(np.cov(returns, benchmark, ddof=0)[0, 1] / np.var(benchmark, ddof=0))
    active = returns - benchmark
    expected_te = float(np.std(active, ddof=0) * math.sqrt(252))
    assert bundle.metrics["beta"].value == pytest.approx(expected_beta, abs=1e-10)
    assert bundle.metrics["tracking_error"].value == pytest.approx(expected_te, abs=1e-10)


def test_monte_carlo_is_reproducible_for_the_same_seed() -> None:
    returns = np.array([0.01, -0.005, 0.002, 0.004] * 10)

    first = MonteCarloEngine.run_simulation(returns, n_simulations=100, time_horizon=20, seed=7)
    second = MonteCarloEngine.run_simulation(returns, n_simulations=100, time_horizon=20, seed=7)

    assert first == second
    assert min(min(path) for path in first["samplePaths"]) >= 0


@pytest.mark.parametrize("method", ["gaussian", "historical_bootstrap", "moving_block_bootstrap"])
def test_monte_carlo_resampling_methods_are_named_and_reproducible(method: str) -> None:
    returns = np.array([0.01, -0.005, 0.002, 0.004] * 10)
    kwargs = {"n_simulations": 100, "time_horizon": 20, "seed": 11, "method": method, "block_size": 4}

    first = MonteCarloEngine.run_simulation(returns, **kwargs)
    second = MonteCarloEngine.run_simulation(returns, **kwargs)

    assert first == second
    assert first["assumptions"] == {
        "method": method,
        "seed": 11,
        "blockSize": 4 if method == "moving_block_bootstrap" else None,
        "inputObservations": 40,
        "returnConvention": "simple",
    }


def test_walk_forward_returns_observed_fold_values_without_placeholders() -> None:
    returns = np.array([0.002, -0.001, 0.003, -0.002, 0.001] * 60)

    result = WalkForwardEngine.run_analysis(returns, oos_days=20, n_folds=5)

    assert result["summary"]["totalFolds"] == 5
    assert len(result["folds"]) == 5
    assert set(result["folds"][0]) == {
        "fold", "isSharpe", "oosSharpe", "isReturn", "oosReturn", "degradation",
        "trainStart", "trainEnd", "testStart", "testEnd", "purgeDays", "embargoDays",
    }


def test_walk_forward_uses_expanding_temporal_folds_with_leakage_gap() -> None:
    returns = np.array([0.01, -0.01] * 200)

    result = WalkForwardEngine.run_analysis(returns, oos_days=20, n_folds=5, purge_days=3, embargo_days=2)
    folds = result["folds"]

    assert len(folds) == 5
    assert [fold["trainStart"] for fold in folds] == [0] * 5
    assert all(fold["testStart"] - fold["trainEnd"] == 5 for fold in folds)
    assert all(fold["trainEnd"] <= fold["testStart"] for fold in folds)
    assert all(left["trainEnd"] < right["trainEnd"] for left, right in zip(folds, folds[1:]))
    assert all(left["testEnd"] == right["testStart"] for left, right in zip(folds, folds[1:]))


def test_walk_forward_verdict_exposes_every_threshold_test() -> None:
    returns = np.array([0.01, -0.01] * 200)

    result = WalkForwardEngine.run_analysis(
        returns,
        oos_days=20,
        n_folds=5,
        min_oos_sharpe=0.5,
        min_consistency_pct=90.0,
    )

    assert result["verdict"]["status"] == "FAILED"
    assert result["verdict"]["thresholds"] == {"minOosSharpe": 0.5, "minConsistencyPct": 90.0}
    assert {test["id"] for test in result["verdict"]["tests"]} == {
        "minimum_oos_sharpe",
        "minimum_profitable_fold_consistency",
    }
    assert all(test["status"] in {"pass", "fail", "unavailable"} for test in result["verdict"]["tests"])
    assert any(test["status"] == "fail" for test in result["verdict"]["tests"])
    assert result["verdict"]["methodology"] == "deterministic_threshold_rules_not_statistical_confidence"


def test_walk_forward_keeps_uncomputable_evidence_unavailable() -> None:
    result = WalkForwardEngine.run_analysis(np.zeros(200), oos_days=20, n_folds=5)

    assert result["summary"]["avgIsSharpe"] is None
    assert result["summary"]["avgOosSharpe"] is None
    assert result["summary"]["consistency"] is None
    assert result["alphaShield"] == {"status": "UNAVAILABLE", "confidence": None}
    assert result["verdict"]["status"] == "UNAVAILABLE"
    assert all(test["status"] == "unavailable" for test in result["verdict"]["tests"])
    assert all(cell["alpha_preserved"] is None for cell in result["heatmap"])
