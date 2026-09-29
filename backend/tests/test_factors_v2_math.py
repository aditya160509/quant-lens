from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.factors_v2.core.analytics import predictive_regression
from app.services.factors_v2.features.feature_05 import _fit_decay
from app.services.factors_v2.features.feature_07 import _empty_quintile_rows, _stationary_bootstrap_equity
from app.services.factors_v2.features.feature_09 import _build_capacity_rows, _capacity_curve_piecewise


def test_predictive_regression_uses_hac_standard_error() -> None:
    rng = np.random.default_rng(7)
    index = pd.date_range("2010-01-01", periods=900, freq="B")
    signal = pd.Series(rng.normal(size=len(index)), index=index)
    returns = pd.Series(0.001 * signal.shift(1).fillna(0) + rng.normal(scale=0.01, size=len(index)), index=index)
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
    paths = _stationary_bootstrap_equity(returns, 12, np.random.default_rng(4), block_size=10)
    assert paths.shape == (12, 120)
    assert np.unique(paths[:, -1]).size > 1


def test_capacity_impact_is_continuous_and_liquidation_uses_turnover() -> None:
    aums = np.array([99_999_999.0, 100_000_001.0])
    impact, net, models, _ = _capacity_curve_piecewise(aums, 0.2, 0.0, 0.35, 50_000_000.0, 0.1, 0.25, 21)
    assert models[0] == models[1] == "continuous_square_root_impact"
    assert abs(impact[1] - impact[0]) < 1e-6
    rows = _build_capacity_rows(aums, 0.2, impact, net, models, 50_000_000.0, 0.35, 0.15)
    assert rows[0]["time_to_liquidate_days"] == pytest.approx(0.35 * aums[0] / (0.15 * 50_000_000.0))
