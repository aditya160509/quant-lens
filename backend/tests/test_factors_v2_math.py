from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.factors_v2.core.analytics import predictive_regression
from app.services.factors_v2.features.feature_05 import _fit_decay
from app.services.factors_v2.features.feature_07 import (
    _empty_quintile_rows,
    _stationary_bootstrap_equity,
)
from app.services.factors_v2.core.capacity import cost_sweep


def test_predictive_regression_uses_hac_standard_error() -> None:
    rng = np.random.default_rng(7)
    index = pd.date_range("2010-01-01", periods=900, freq="B")
    signal = pd.Series(rng.normal(size=len(index)), index=index)
    returns = pd.Series(
        0.001 * signal.shift(1).fillna(0) + rng.normal(scale=0.01, size=len(index)),
        index=index,
    )
    result = predictive_regression(signal, returns, horizon=21)
    assert result["sample_size"] > 30
    assert str(result["standard_error_method"]).startswith("newey_west_hac_lag_")
    assert result["ci_90_low"] <= result["predicted_return"] <= result["ci_90_high"]


def test_linear_half_life_solves_fitted_curve() -> None:
    x = np.array([1.0, 5.0, 10.0, 21.0])
    y = 0.10 - 0.002 * x
    result = _fit_decay(x, y)["linear"]
    assert result["half_life"] == pytest.approx(25.5)


def test_missing_quintiles_are_not_fabricated() -> None:
    rows = _empty_quintile_rows("missing")
    assert all(row["annual_return"] is None for row in rows)
    assert all(row["monotonicity_score"] is None for row in rows)


def test_monte_carlo_uses_resampled_paths() -> None:
    returns = np.linspace(-0.01, 0.02, 120)
    paths = _stationary_bootstrap_equity(
        returns, 12, np.random.default_rng(4), block_size=10
    )
    assert paths.shape == (12, 120)
    assert np.unique(paths[:, -1]).size > 1


def test_capacity_impact_is_continuous_and_liquidation_uses_full_book(
    monkeypatch,
) -> None:
    import app.services.factors_v2.core.capacity as capacity

    chars = pd.DataFrame(
        {
            "Ticker": [f"T{i}" for i in range(10)],
            "momentum_12_1": range(10),
            "adv": [50_000_000.0] * 10,
            "realized_vol": [0.25] * 10,
        }
    )
    monkeypatch.setattr(capacity, "characteristic_panel", lambda payload: chars)
    rows = cost_sweep(
        {"turnover": 0.35, "participation_cap": 0.15}, [99_999_999.0, 100_000_001.0]
    )
    assert abs(rows[1]["impact_drag"] - rows[0]["impact_drag"]) < 1e-6
    assert rows[0]["time_to_liquidate_days"] == pytest.approx(
        99_999_999.0 * 0.5 / (0.15 * 50_000_000.0)
    )


def test_next_close_execution_and_exact_fee():
    from app.services.factors_v2.core.backtest import execute_targets

    dates = pd.bdate_range("2020-01-01", periods=4)
    close = pd.DataFrame({"A": [10.0, 11.0, 12.0, 13.0]}, index=dates)
    result = execute_targets(close, {dates[0]: pd.Series({"A": 1.0})}, 100)
    assert result["gross"].iloc[1] == 0
    assert result["gross"].iloc[2] == pytest.approx(12 / 11 - 1)
    assert result["net"].iloc[1] == pytest.approx(1 / 1.01 - 1)
    assert result["trades"][0]["turnover"] == pytest.approx(1 / 1.01)


def test_missing_held_marks_raise():
    from app.services.factors_v2.core.backtest import execute_targets

    dates = pd.bdate_range("2020-01-01", periods=4)
    close = pd.DataFrame({"A": [10.0, 11.0, np.nan, 13.0]}, index=dates)
    with pytest.raises(ValueError, match="Missing held return"):
        execute_targets(close, {dates[0]: pd.Series({"A": 1.0})})


def test_fap_is_regression_on_loadings():
    from app.services.factors_v2.core.optimization import alignment

    rng = np.random.default_rng(9)
    x = rng.normal(size=(100, 3))
    y = 2 + x @ np.array([1.0, 2.0, 3.0])
    result = alignment(y, x)
    assert result["r_squared"] == pytest.approx(1)
    assert alignment(None, None)["r_squared"] is None


def test_structural_break_diagnostic_has_actual_pvalue():
    from app.services.factors_v2.features.feature_13 import break_diagnostic

    y = pd.Series(np.r_[np.zeros(80), np.ones(80)])
    result = break_diagnostic(y)
    assert result["p_value"] < 0.001
    assert "chow" not in result["diagnostic"]


def test_forward_filter_does_not_smooth_future():
    from app.services.factors_v2.features.feature_04 import forward_filter

    emissions = np.array([[0, -2], [-1, -1], [-2, 0]], float)
    first = forward_filter(
        emissions, np.array([0.5, 0.5]), np.array([[0.9, 0.1], [0.1, 0.9]])
    )
    emissions[-1] = [-100, 0]
    changed = forward_filter(
        emissions, np.array([0.5, 0.5]), np.array([[0.9, 0.1], [0.1, 0.9]])
    )
    np.testing.assert_allclose(first[:2], changed[:2])


def test_covariance_matches_numpy_and_constant_correlation_is_missing():
    from app.services.factors_v2.core.covariance import covariance_payload

    frame = pd.DataFrame(
        {"a": [0.01, 0.02, -0.03, 0.04], "b": [0.02, 0.01, -0.01, 0.03]}
    )
    result = covariance_payload(frame, "sample")
    np.testing.assert_allclose(
        result["covariance"], np.cov(frame.to_numpy().T) * 252, rtol=1e-6
    )
    constant = frame.assign(b=0.0)
    assert pd.isna(covariance_payload(constant, "sample")["correlation"].loc["a", "b"])


def test_optimizer_preserves_all_constraints_and_rejects_infeasible():
    from app.services.factors_v2.core.optimization import solve

    payload = {
        "position_limit": 0.6,
        "gross_limit": 1.0,
        "turnover_limit": 0.2,
        "current_weights": [0.5, 0.5],
    }
    weights, _ = solve(np.array([0.1, 0.02]), np.eye(2) * 0.04, payload, 5, 0.25, 252)
    assert abs(weights.sum() - 1) < 1e-6
    assert weights.min() >= -1e-6 and weights.max() <= 0.6 + 1e-6
    assert np.abs(weights - np.array([0.5, 0.5])).sum() <= 0.2 + 1e-6
    with pytest.raises(ValueError, match="did not solve"):
        solve(
            np.array([0.1, 0.02]), np.eye(2) * 0.04, {"position_limit": 0.1}, 5, 0, 252
        )


def test_initial_cost_loss_is_in_drawdown():
    from app.services.factors_v2.core.stats import perf_stats

    assert perf_stats(pd.Series([-0.1, 0.0]))["max_drawdown"] == pytest.approx(-0.1)


def test_gross_counterfactual_is_independent_of_borrow():
    from app.services.factors_v2.core.backtest import execute_targets

    dates = pd.date_range("2023-01-01", periods=5)
    close = pd.DataFrame(
        {"a": [10, 11, 12, 13, 14], "b": [10, 10, 9, 9, 8]}, index=dates
    )
    target = {dates[0]: pd.Series({"a": 1.0, "b": -1.0})}
    free = execute_targets(close, target)
    charged = execute_targets(close, target, borrow_bps=1000)
    pd.testing.assert_series_equal(free["gross"], charged["gross"])
    assert (charged["net"] < charged["gross"]).any()
