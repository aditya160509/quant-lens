"""P6-P8 polish: benchmark/orders/sensitivity/scenario contracts."""

import numpy as np

from app.routers.studio import (
    SKIPPED_SCENARIOS,
    _apply_cost_shock,
    _apply_delay,
    _apply_missing_data,
    _benchmark_buy_and_hold,
    _orders_from_signals,
    _sensitivity_sharpe,
    WalkForwardEngine,
)


def test_benchmark_normalized_from_same_closes():
    curve = _benchmark_buy_and_hold(np.array([100.0, 110.0, 105.0]))
    assert curve[0] == 1.0
    assert curve[1] == 1.1
    assert curve[2] == 1.05


def test_benchmark_unusable_closes_return_empty():
    assert _benchmark_buy_and_hold(np.array([0.0, 1.0])) == []
    assert _benchmark_buy_and_hold(np.array([np.nan, 1.0])) == []


def test_orders_derive_only_from_nonzero_signals():
    signals = [
        {"date": "2026-01-01", "timestamp": 1, "price": 100.0, "direction": 0, "idx": 0},
        {"date": "2026-01-02", "timestamp": 2, "price": 101.0, "direction": 1, "idx": 1},
        {"date": "2026-01-03", "timestamp": 3, "price": 102.0, "direction": -1, "idx": 2},
    ]
    orders = _orders_from_signals(signals)
    assert [order["direction"] for order in orders] == [1, -1]
    assert all(order["source"] == "observed_signal" for order in orders)


def test_sensitivity_cells_deterministic():
    closes = np.linspace(100, 130, 120)
    first = _sensitivity_sharpe(closes, 10, 0.01, 0.0, 0.0)
    second = _sensitivity_sharpe(closes, 10, 0.01, 0.0, 0.0)
    assert first == second
    assert first["status"] in {"observed", "unavailable"}


def test_scenario_transforms_deterministic_and_reuse_walk_forward():
    rng_returns = np.random.default_rng(7).normal(0.001, 0.01, 300)
    shocked = _apply_cost_shock(rng_returns, 10.0)
    assert np.allclose(shocked, rng_returns - 0.001)
    missing_a = _apply_missing_data(rng_returns, 5.0, seed=42)
    missing_b = _apply_missing_data(rng_returns, 5.0, seed=42)
    assert np.array_equal(missing_a, missing_b)
    delayed = _apply_delay(rng_returns, 1)
    assert delayed[0] == 0.0
    assert np.array_equal(delayed[1:], rng_returns[:-1])
    baseline = WalkForwardEngine.run_analysis(rng_returns, oos_days=20, n_folds=3)
    assert baseline["summary"]["totalFolds"] == 3


def test_skipped_scenarios_named_with_reasons():
    ids = {item["id"] for item in SKIPPED_SCENARIOS}
    assert ids == {"liquidity", "regime", "adversarial"}
    assert all(item["status"] == "skipped" and item["reason"] for item in SKIPPED_SCENARIOS)
