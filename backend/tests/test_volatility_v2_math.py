import math
import pytest
import numpy as np
import pandas as pd
from app.services.volatility_v2.core.analytics import (
    volatility_estimators,
    volatility_estimators_multi,
    _frame_cache_key,
    _rolling_mean_np,
)


def fixture():
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 45)))
    opening = close * np.exp(rng.normal(0, 0.003, 45))
    return pd.DataFrame(
        {
            "Ticker": "BTC_USD",
            "Date": pd.date_range("2024-01-01", periods=45),
            "Open": opening,
            "High": np.maximum(close, opening) * 1.012,
            "Low": np.minimum(close, opening) * 0.991,
            "Close": close,
            "Volume": 1000.0,
        }
    )


def test_yang_zhang_golden_and_continuous_sessions():
    frame = fixture()
    window = 21
    overnight = np.log(frame.Open / frame.Close.shift())
    intraday = np.log(frame.Close / frame.Open)
    rs = np.log(frame.High / frame.Close) * np.log(frame.High / frame.Open) + np.log(
        frame.Low / frame.Close
    ) * np.log(frame.Low / frame.Open)
    k = 0.34 / (1.34 + (window + 1) / (window - 1))
    expected = math.sqrt(
        252
        * (
            overnight.tail(window).var()
            + k * intraday.tail(window).var()
            + (1 - k) * rs.tail(window).mean()
        )
    )
    actual = volatility_estimators(frame, window)
    assert actual.yang_zhang.iloc[-1] == np.float32(expected)
    pd.testing.assert_frame_equal(
        actual, volatility_estimators_multi(frame, [window])[window]
    )


def test_missing_window_is_not_partially_imputed():
    values = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
    output = _rolling_mean_np(values, 3)
    assert np.isnan(output[:4]).all()
    assert output[-1] == 4.0


def test_content_fingerprint_changes_on_interior_observation():
    frame = fixture()
    before = _frame_cache_key(frame, "test")
    frame.loc[10, "Close"] += 1
    assert _frame_cache_key(frame, "test") != before


def test_estimator_is_causal():
    frame = fixture()
    original = volatility_estimators(frame)
    frame.loc[35:, ["Open", "High", "Low", "Close"]] *= 2
    changed = volatility_estimators(frame)
    pd.testing.assert_frame_equal(
        original.loc[original.date < frame.Date.iloc[35]],
        changed.loc[changed.date < frame.Date.iloc[35]],
    )


def test_har_uses_matured_targets_and_is_future_invariant():
    from app.services.volatility_v2.core.har import expanding_forecasts

    dates = pd.date_range("2020-01-01", periods=220)
    rng = np.random.default_rng(19)
    x = pd.DataFrame({"daily": rng.uniform(0.1, 0.3, len(dates))}, index=dates)
    target = x.daily.shift(-5)
    original, _, _, _ = expanding_forecasts(x, target, horizon=5, min_train=40)
    changed_x = x.copy()
    changed_x.loc[dates[150] :] *= 5
    changed, _, _, _ = expanding_forecasts(
        changed_x, changed_x.daily.shift(-5), horizon=5, min_train=40
    )
    cols = ["date", "forecast", "training_observed_through", "train_size", "p05", "p95"]
    pd.testing.assert_frame_equal(original.loc[:149, cols], changed.loc[:149, cols])
    valid = original.dropna(subset=["forecast"])
    assert (valid.training_observed_through <= valid.date).all()
    assert valid.actual.tail(5).isna().all()


def test_garch_forecasts_are_formed_before_observed_return():
    from app.services.volatility_v2.core.garch import expanding_model

    dates = pd.date_range("2020-01-01", periods=210)
    returns = pd.Series(
        np.random.default_rng(71).normal(0, 0.01, len(dates)), index=dates
    )
    first, _ = expanding_model(
        returns, min_train=120, refit_interval=21, evaluation_days=90
    )
    changed = returns.copy()
    changed.iloc[170:] *= 3
    second, _ = expanding_model(
        changed, min_train=120, refit_interval=21, evaluation_days=90
    )
    pd.testing.assert_frame_equal(first.loc[: dates[169]], second.loc[: dates[169]])
    assert (first.training_observed_through < first.index).all()
    assert (first.forecast_observed_through < first.index).all()


def test_var_backtests_do_not_invent_independence_pvalue():
    from app.services.volatility_v2.core.garch import var_backtests

    path = pd.DataFrame({"return": [0.0, 0.01, 0.0, -0.01], "var_cutoff": [-0.02] * 4})
    result = var_backtests(path, 0.99)
    assert result["exceptions"] == 0
    assert np.isfinite(result["kupiec_lr"])
    assert result["christoffersen_independence_p_value"] is None


def test_hmm_filtering_is_causal_and_cache_does_not_hide_mutation():
    from app.services.volatility_v2.core.regimes import filtered_regimes

    dates = pd.date_range("2020-01-01", periods=260)
    rng = np.random.default_rng(5)
    features = pd.DataFrame(
        {
            "log_vol": rng.normal(0, 1, len(dates)),
            "return_21d": rng.normal(0, 1, len(dates)),
        },
        index=dates,
    )
    first = filtered_regimes(
        features, states=2, min_train=120, refit_interval=63, restarts=1
    )
    changed = features.copy()
    changed.iloc[200:] += 8
    second = filtered_regimes(
        changed, states=2, min_train=120, refit_interval=63, restarts=1
    )
    pd.testing.assert_frame_equal(
        first["probabilities"].loc[: dates[199]],
        second["probabilities"].loc[: dates[199]],
    )
    probs = first["probabilities"][["low_vol", "high_vol"]]
    np.testing.assert_allclose(probs.sum(axis=1), 1, atol=1e-12)
    assert (
        first["probabilities"].training_observed_through < first["probabilities"].index
    ).all()
    assert first["source_fingerprint"] != second["source_fingerprint"]


def test_regime_duration_right_censor_and_transitions():
    from app.services.volatility_v2.core.regimes import (
        duration_survival,
        transition_matrices,
        transition_alerts,
    )

    seq = np.array(
        [0] * 4
        + [1] * 3
        + [0] * 2
        + [1] * 4
        + [0] * 5
        + [1] * 2
        + [0] * 3
        + [1] * 6
        + [0] * 10
    )
    rows = duration_survival(seq, ["low_vol", "high_vol"])
    assert rows[0]["completed_spells"] == 3
    assert rows[0]["current_duration_days"] == 10
    assert rows[0]["right_censored_spells"] == 1
    assert rows[0]["left_censored_first_spell_excluded"]
    assert rows[0]["survival_curve"][0]["survival_prob"] <= 1
    probs = pd.DataFrame(
        {
            "low_vol": np.r_[np.ones(10) * 0.9, np.ones(10) * 0.1],
            "high_vol": np.r_[np.ones(10) * 0.1, np.ones(10) * 0.9],
        },
        index=pd.date_range("2020-01-01", periods=20),
    )
    matrix = pd.DataFrame(transition_matrices(probs))
    np.testing.assert_allclose(
        matrix[matrix.horizon.eq("1w")].groupby("row").value.sum(), 1
    )
    alerts = transition_alerts(probs, "SPY", 0.3, 5)
    assert len(alerts) == 1
    assert alerts[0]["date"] == probs.index[10]
    assert alerts == transition_alerts(probs, "SPY", 0.3, 5)


def test_integrated_garch_variance_is_causal_and_matches_library_forecast():
    from app.services.volatility_v2.core.vrp import integrated_garch_variance
    from app.services.volatility_v2.core.garch import fit_model

    dates = pd.date_range("2020-01-01", periods=210)
    returns = pd.Series(
        np.random.default_rng(81).normal(0, 0.01, len(dates)), index=dates
    )
    original = integrated_garch_variance(
        returns, (3,), min_train=120, refit_interval=21
    )
    changed = returns.copy()
    changed.iloc[180:] *= 2
    second = integrated_garch_variance(changed, (3,), min_train=120, refit_interval=21)
    pd.testing.assert_frame_equal(original.loc[: dates[179]], second.loc[: dates[179]])
    fit = fit_model(returns.iloc[:120])
    expected = float(
        fit.forecast(horizon=3).residual_variance.iloc[-1].mean() / 10000 * 252
    )
    assert original.loc[dates[119], 3] == pytest.approx(expected, rel=1e-9)


def test_hodrick_null_covariance_matches_lagged_predictor_reference():
    from app.services.volatility_v2.core.vrp import hodrick_null_standard_errors
    import statsmodels.api as sm

    dates = pd.date_range("2020-01-01", periods=130)
    rng = np.random.default_rng(42)
    predictor = pd.DataFrame({"x": rng.uniform(0.01, 0.1, len(dates))}, index=dates)
    returns = pd.Series(rng.normal(0, 0.01, len(dates)), index=dates)
    horizon = 5
    design = sm.add_constant(predictor.iloc[:-horizon])
    scores = np.array(
        [
            (returns.iloc[t] - returns.mean())
            * np.r_[horizon, predictor.x.iloc[t - horizon : t].sum()]
            for t in range(horizon, len(dates))
        ]
    )
    bread = np.linalg.inv(design.to_numpy().T @ design.to_numpy())
    expected = np.sqrt(np.diag(bread @ scores.T @ scores @ bread))
    actual = hodrick_null_standard_errors(predictor, returns, horizon, design)
    np.testing.assert_allclose(actual, expected, rtol=1e-10)


def test_generalized_fevd_golden_ordering_and_frequency_additivity():
    from app.services.volatility_v2.core.connectedness import (
        VolatilityVAR,
        generalized_decomposition,
        frequency_connectedness,
        spillovers,
    )

    model = VolatilityVAR(
        np.zeros((1, 2, 2)),
        np.array([[1.0, 0.5], [0.5, 1.0]]),
        np.zeros(2),
        1,
        None,
        True,
        "ols",
    )
    theta = generalized_decomposition(model, 10)
    np.testing.assert_allclose(theta, [[0.8, 0.2], [0.2, 0.8]], atol=1e-12)
    frequency = frequency_connectedness(model)
    assert sum(row["frequency_connectedness"] for row in frequency) == pytest.approx(
        20.0, abs=1e-10
    )
    assert sum(row["variance_mass_share"] for row in frequency) == pytest.approx(
        1.0, abs=1e-12
    )
    assert all(
        row["within_band_connectedness"] == pytest.approx(20.0) for row in frequency
    )
    nonuniform = VolatilityVAR(
        np.array([[[0.4, 0.1], [0.05, 0.2]]]),
        np.array([[2.0, 0.3], [0.3, 1.0]]),
        np.zeros(2),
        1,
        None,
        True,
        "ols",
    )
    order = [1, 0]
    reordered = VolatilityVAR(
        nonuniform.coefs[:, order][:, :, order],
        nonuniform.covariance[np.ix_(order, order)],
        np.zeros(2),
        1,
        None,
        True,
        "ols",
    )
    np.testing.assert_allclose(
        generalized_decomposition(nonuniform, 10)[np.ix_(order, order)],
        generalized_decomposition(reordered, 10),
        atol=1e-12,
    )
    ranking = spillovers(np.array([[0.8, 0.2], [0.3, 0.7]]), ["A", "B"])
    np.testing.assert_allclose(ranking.net_spillover, [10.0, -10.0])
    np.testing.assert_allclose(ranking.from_spillover, [20.0, 30.0])


def test_connectedness_var_matches_statsmodels_and_daily_updates_are_causal():
    from app.services.volatility_v2.core.connectedness import (
        fit_volatility_var,
        rolling_connectedness,
    )
    from statsmodels.tsa.api import VAR

    dates = pd.date_range("2020-01-01", periods=150)
    rng = np.random.default_rng(53)
    panel = pd.DataFrame(
        rng.normal(size=(len(dates), 2)), index=dates, columns=["A", "B"]
    )
    fit = fit_volatility_var(panel, max_lag=1)
    reference = VAR(panel).fit(1)
    np.testing.assert_allclose(fit.coefs, reference.coefs)
    np.testing.assert_allclose(fit.covariance, reference.sigma_u)
    first = rolling_connectedness(
        panel, window=60, max_lag=2, include_network_history=True
    )
    assert len(first["timeline"]) == len(panel) - 60 + 1
    assert len(first["network_history"]) == len(first["timeline"])
    assert len(first["attribution"]) == 2 * len(first["timeline"])
    changed = panel.copy()
    changed.iloc[120:] *= 3
    second = rolling_connectedness(changed, window=60, max_lag=2)
    pd.testing.assert_frame_equal(
        first["timeline"].loc[: dates[119]], second["timeline"].loc[: dates[119]]
    )


def test_ew_var_keeps_selected_weighting_without_fake_bic():
    from app.services.volatility_v2.core.connectedness import (
        fit_volatility_var,
        rolling_connectedness,
    )

    dates = pd.date_range("2020-01-01", periods=90)
    panel = pd.DataFrame(
        np.random.default_rng(18).normal(size=(90, 2)), index=dates, columns=["A", "B"]
    )
    model = fit_volatility_var(panel, weighting="ew", lag_order=2, delta=0.99)
    assert model.weighting == "ew" and model.lag == 2 and model.bic is None
    result = rolling_connectedness(
        panel, window=60, weighting="ew", lag_order=2, delta=0.99
    )
    assert result["latest"][1].weighting == "ew"
    assert result["timeline"].var_lag_order.eq(2).all()


def test_irf_bootstrap_uses_seeded_library_blocks_and_actual_var_refits():
    from app.services.volatility_v2.core.connectedness import (
        fit_volatility_var,
        bootstrap_irf,
    )

    dates = pd.date_range("2020-01-01", periods=100)
    panel = pd.DataFrame(
        np.random.default_rng(29).normal(size=(100, 2)), index=dates, columns=["A", "B"]
    )
    model = fit_volatility_var(panel, max_lag=1)
    rows, info = bootstrap_irf(panel, model, horizons=(1, 5), reps=20, max_lag=1)
    again, second = bootstrap_irf(panel, model, horizons=(1, 5), reps=20, max_lag=1)
    assert rows == again and info == second
    assert len(rows) == 8 and info["successful_replications"] == 20
    assert all(row["lower"] <= row["upper"] for row in rows)
    assert rows[0]["response"] == pytest.approx(model.ma(5)[1, 0, 0])


def test_covariance_estimators_match_libraries_and_reject_missing_returns():
    from sklearn.covariance import LedoitWolf, OAS
    from app.services.volatility_v2.core.covariance import covariance_estimates

    values = np.random.default_rng(71).normal(size=(100, 3)) / 100
    frame = pd.DataFrame(values, columns=["A", "B", "C"])
    result = covariance_estimates(frame)
    np.testing.assert_allclose(
        result["ledoit_wolf"], LedoitWolf().fit(values).covariance_ * 252
    )
    np.testing.assert_allclose(result["oas"], OAS().fit(values).covariance_ * 252)
    np.testing.assert_allclose(result["sample"], np.cov(values, rowvar=False) * 252)
    frame.iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite observed"):
        covariance_estimates(frame)


def test_euler_and_pairwise_attribution_conserve_actual_portfolio_risk():
    from app.services.volatility_v2.core.covariance import portfolio_attribution

    cov = pd.DataFrame(
        [[0.04, 0.01], [0.01, 0.09]], index=["A", "B"], columns=["A", "B"]
    )
    weights = pd.Series({"A": 0.7, "B": -0.2})
    result = portfolio_attribution(cov, weights)
    expected = float(weights.to_numpy() @ cov.to_numpy() @ weights.to_numpy())
    assert result["variance"] == pytest.approx(expected)
    assert sum(
        row["component_volatility"] for row in result["assets"]
    ) == pytest.approx(np.sqrt(expected))
    assert result["pairwise_variance"].to_numpy().sum() == pytest.approx(expected)
    assert result["minimum_variance_weights"].sum() == pytest.approx(1)


def test_dcc_forecasts_are_positive_definite_and_ignore_future_returns():
    from app.services.volatility_v2.core.dcc import expanding_dcc

    rng = np.random.default_rng(817)
    values = rng.standard_t(7, size=(155, 2)) * 0.01
    values[:, 1] += values[:, 0] * 0.4
    frame = pd.DataFrame(
        values, index=pd.date_range("2020-01-01", periods=155), columns=["A", "B"]
    )
    first = expanding_dcc(frame, min_train=120, refit_interval=20)
    changed = frame.copy()
    changed.iloc[145:] *= 2
    second = expanding_dcc(changed, min_train=120, refit_interval=20)
    assert first["timeline"][:25] == second["timeline"][:25]
    for row, cov in zip(first["timeline"], first["covariances"]):
        np.testing.assert_allclose(np.diag(row["correlation"]), 1)
        assert np.linalg.eigvalsh(cov).min() > 0
        assert (
            row["training_observed_through"]
            <= row["forecast_observed_through"]
            < row["date"]
        )
    assert np.linalg.eigvalsh(first["forecast_covariance"]).min() > 0


def test_exact_minimum_torsion_decorrelates_and_conserves_signed_portfolio_variance():
    from app.services.volatility_v2.core.torsion import minimum_torsion

    cov = pd.DataFrame(
        [[0.04, 0.025, -0.008], [0.025, 0.09, 0.015], [-0.008, 0.015, 0.025]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    weights = pd.Series({"A": 0.8, "B": -0.3, "C": 0.5})
    result = minimum_torsion(cov, weights)
    transform = result["transformation"].to_numpy()
    transformed = transform @ cov.to_numpy() @ transform.T
    np.testing.assert_allclose(transformed, np.diag(np.diag(transformed)), atol=1e-10)
    assert sum(
        row["variance_contribution"] for row in result["attribution"]
    ) == pytest.approx(float(weights @ cov @ weights))
    assert 1 <= result["effective_number_of_bets"] <= 3
    diagonal = pd.DataFrame(
        np.diag([0.04, 0.09, 0.025]), index=cov.index, columns=cov.columns
    )
    np.testing.assert_allclose(
        minimum_torsion(diagonal, weights)["transformation"], np.eye(3), atol=1e-12
    )
    permutation = ["C", "A", "B"]
    permuted = minimum_torsion(cov.loc[permutation, permutation], weights)
    np.testing.assert_allclose(
        permuted["transformation"].loc[cov.index, cov.columns], transform, atol=1e-10
    )


def test_torsion_matches_independent_two_asset_rotation_minimum():
    from scipy.optimize import minimize_scalar
    from scipy.linalg import sqrtm
    from app.services.volatility_v2.core.torsion import minimum_torsion

    cov = pd.DataFrame(
        [[0.04, 0.035], [0.035, 0.09]], index=["A", "B"], columns=["A", "B"]
    )
    weights = pd.Series({"A": 0.6, "B": 0.4})
    root = sqrtm(
        cov.to_numpy() / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    )

    def objective(angle):
        rotation = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        diagonal = np.diag(rotation @ root)
        return float(np.linalg.norm(root - diagonal[:, None] * rotation, "fro"))

    optimum = minimize_scalar(
        objective, bounds=(-np.pi / 2, np.pi / 2), method="bounded"
    )
    actual = minimum_torsion(cov, weights)
    assert actual["objective"] == pytest.approx(optimum.fun, abs=1e-8)


def test_weighted_crisis_correlation_centers_on_weighted_mean():
    from app.services.volatility_v2.core.crisis import weighted_correlation

    rng = np.random.default_rng(345)
    index = pd.date_range("2020-01-01", periods=50)
    frame = pd.DataFrame(rng.normal(size=(50, 2)), index=index, columns=["A", "B"])
    weights = pd.Series(np.linspace(0.01, 0.9, 50), index=index)
    actual, metadata = weighted_correlation(frame, weights)
    expected_cov = np.cov(frame.to_numpy(), rowvar=False, aweights=weights, ddof=0)
    expected = expected_cov / np.sqrt(
        np.outer(np.diag(expected_cov), np.diag(expected_cov))
    )
    np.testing.assert_allclose(actual, expected)
    assert metadata["effective_sample_size"] < 50
    with pytest.raises(ValueError, match="30 aligned"):
        weighted_correlation(frame.iloc[:20], weights)


def test_midas_uses_completed_months_and_enters_actual_dcc_recursion():
    from app.services.volatility_v2.core.dcc import expanding_dcc
    from app.services.volatility_v2.core.midas import (
        beta_weights,
        monthly_correlations,
        lag_matrices,
    )

    rng = np.random.default_rng(312)
    index = pd.bdate_range("2020-01-31", periods=285)
    values = rng.standard_t(9, size=(285, 2)) * 0.01
    values[:, 1] += np.sin(np.arange(285) / 30) * values[:, 0] * 0.7
    frame = pd.DataFrame(values, index=index, columns=["A", "B"])
    monthly = monthly_correlations(values, index)
    query = pd.Timestamp("2020-08-03")
    lagged = lag_matrices(monthly, query, 3)
    np.testing.assert_allclose(lagged[0], monthly[pd.Period("2020-07", freq="M")])
    np.testing.assert_allclose(beta_weights(3, 1), np.ones(3) / 3)
    actual = expanding_dcc(
        frame, min_train=120, refit_interval=100, dynamics="dcc_midas", midas_k=3
    )
    changed = frame.copy()
    changed.iloc[240:] *= 2
    second = expanding_dcc(
        changed, min_train=120, refit_interval=100, dynamics="dcc_midas", midas_k=3
    )
    before = [row for row in actual["timeline"] if row["date"] < index[240]]
    assert before == [row for row in second["timeline"] if row["date"] < index[240]]
    long_run = np.array(
        [row["long_run_correlation"][0][1] for row in actual["timeline"]]
    )
    assert np.ptp(long_run) > 0.01
    for row in actual["timeline"]:
        np.testing.assert_allclose(np.diag(row["long_run_correlation"]), 1)
    assert actual["parameters"][0]["midas_beta_theta"] >= 1
    assert np.linalg.eigvalsh(actual["forecast_covariance"]).min() > 0


def test_dcc_optimizer_failure_is_explicit(monkeypatch):
    from types import SimpleNamespace
    from app.services.volatility_v2.core import dcc

    monkeypatch.setattr(
        dcc, "minimize", lambda *args, **kwargs: SimpleNamespace(success=False)
    )
    with pytest.raises(ValueError, match="all starting points"):
        dcc.fit_dcc(np.random.default_rng(67).normal(size=(150, 2)))


def test_midas_likelihood_matches_independent_matrix_recursion():
    from app.services.volatility_v2.core.midas import _likelihood

    z = np.array([[0.3, -0.6], [1.1, 0.4], [-0.9, 0.8], [0.2, -0.1]])
    targets = np.array(
        [
            [[1, 0.1], [0.1, 1]],
            [[1, 0.4], [0.4, 1]],
            [[1, -0.2], [-0.2, 1]],
            [[1, 0.6], [0.6, 1]],
        ],
        dtype=float,
    )
    a, b = 0.1, 0.7
    q = targets[0].copy()
    expected = 0.0
    for pos in range(1, len(z)):
        q = (1 - a - b) * targets[pos] + a * np.outer(z[pos - 1], z[pos - 1]) + b * q
        r = q / np.sqrt(np.outer(np.diag(q), np.diag(q)))
        expected += 0.5 * (
            np.linalg.slogdet(r)[1] + z[pos] @ np.linalg.solve(r, z[pos])
        )
    assert _likelihood(z, targets, a, b) == pytest.approx(expected)
    assert _likelihood(z, targets, a, b) != pytest.approx(
        _likelihood(z, np.repeat(targets[:1], len(z), axis=0), a, b)
    )


def test_historical_stress_compounds_and_attribution_matches_nav():
    from app.services.volatility_v2.core.stress import replay

    index = pd.bdate_range("2020-01-01", periods=80)
    values = np.random.default_rng(9).normal(0.001, 0.01, size=(80, 2))
    frame = pd.DataFrame(values, index=index, columns=["A", "B"])
    weights = pd.Series({"A": 0.8, "B": -0.2})
    selected = frame.iloc[25:45]
    actual = replay(frame, weights, index[25], index[44])
    expected = float(np.prod(1 + selected.to_numpy() @ weights.to_numpy()) - 1)
    assert actual["portfolio_return"] == pytest.approx(expected)
    assert sum(
        row["cumulative_return_contribution"] for row in actual["attribution"]
    ) == pytest.approx(expected)
    assert len(actual["path"]) == 20
    assert actual["path"][-1]["nav"] == pytest.approx(1 + expected)
    assert actual["portfolio_return"] != pytest.approx(float(selected.mean() @ weights))
    with pytest.raises(ValueError, match="not covered"):
        replay(frame, weights, "2008-09-01", "2008-12-31")


def test_stress_gaussian_units_match_daily_analytic_quantile_and_seed():
    from scipy.stats import norm
    from app.services.volatility_v2.core.stress import gaussian_stress

    cov = pd.DataFrame(
        [[0.04, 0.01], [0.01, 0.09]], index=["A", "B"], columns=["A", "B"]
    )
    weights = pd.Series({"A": 0.6, "B": 0.4})
    risk, distribution = gaussian_stress(cov, weights, paths=100000, aum=1e6)
    sigma = np.sqrt(weights @ cov @ weights / 252)
    assert risk["var_99"] == pytest.approx(norm.ppf(0.01) * sigma, abs=0.0004)
    assert risk["var_99_usd"] == pytest.approx(risk["var_99"] * 1e6)
    repeated, second = gaussian_stress(cov, weights, paths=100000, aum=1e6)
    assert repeated == risk and second == distribution


def test_rotated_clayton_recovers_tail_dependence_and_conditions_on_vol_spikes():
    from scipy.stats import norm
    from statsmodels.distributions.copula.api import ClaytonCopula
    from app.services.volatility_v2.core.tails import rotated_clayton

    import inspect

    rng_name = (
        "rng"
        if "rng" in inspect.signature(ClaytonCopula.rvs).parameters
        else "random_state"
    )
    uniforms = ClaytonCopula(theta=3).rvs(
        2000, **{rng_name: np.random.default_rng(341)}
    )
    index = pd.date_range("2015-01-01", periods=len(uniforms))
    returns = pd.Series(norm.ppf(uniforms[:, 0]) * 0.02, index=index)
    vol_change = pd.Series(-norm.ppf(uniforms[:, 1]) * 0.03, index=index)
    result = rotated_clayton(returns, vol_change, loss_threshold=0.03)
    assert result["theta"] == pytest.approx(3, rel=0.2)
    median = next(
        row["return"]
        for row in result["conditional_return_quantiles"]
        if row["quantile"] == 0.5
    )
    assert median < returns.median() - 0.015
    assert result["reverse_stress_status"] == "ok"
    for row in result["conditional_return_quantiles"]:
        actual_cdf = (
            ClaytonCopula(theta=result["theta"]).cdf(
                np.array([[row["unconditional_return_cdf"], 0.2]])
            )[0]
            / 0.2
        )
        assert actual_cdf == pytest.approx(row["quantile"], abs=1e-10)
    unsupported = rotated_clayton(returns, vol_change, loss_threshold=0.5)
    assert unsupported["reverse_stress_status"] == "unavailable"
    assert "outside observed" in unsupported["reverse_stress_reason"]


def test_macro_analogs_use_every_window_and_continuous_adversary_is_feasible():
    from app.services.volatility_v2.core.analogs import analyze, COLUMNS

    rng = np.random.default_rng(467)
    index = pd.bdate_range("2020-01-01", periods=300)
    returns = pd.DataFrame(
        rng.normal(0, 0.01, (300, 2)), index=index, columns=["A", "B"]
    )
    changes = pd.DataFrame(rng.normal(size=(300, 5)), index=index, columns=COLUMNS)
    changes.iloc[:10] = np.nan
    weights = pd.Series({"A": 0.5, "B": 0.5})
    result = analyze(
        returns,
        weights,
        {
            "analog_horizon": 10,
            "macro_scenario": dict.fromkeys(COLUMNS, 0),
            "adversarial_c": 2,
        },
        changes=changes,
    )
    assert result["meta"]["candidate_windows"] == 290
    assert len(result["analogs"]) == 10
    successful = [row for row in result["meta"]["precision_candidates"] if "bic" in row]
    selected = min(successful, key=lambda row: row["bic"])
    assert result["meta"]["selected_alpha"] == selected["alpha"]
    assert result["adversarial"]["distance_squared_from_query"] == pytest.approx(4)
    first = result["analogs"][0]
    episode = returns.loc[first["window_start"] : first["window_end"]]
    assert first["portfolio_return"] == pytest.approx(
        float((1 + episode @ weights).prod() - 1)
    )
    assert len(result["volatility_paths"]) == 10 * 10 * 2
    # Compare the claimed worst scenario with 1,000 independent feasible points.
    precision = result["precision_matrix"].to_numpy()
    covariance = np.linalg.inv(precision)
    beta = np.array(
        [result["meta"]["conditional_mean_coefficients"][column] for column in COLUMNS]
    )
    intercept = result["meta"]["conditional_mean_coefficients"]["intercept"]
    query_z = -np.array(
        [result["meta"]["center"][column] for column in COLUMNS]
    ) / np.array([result["meta"]["scale"][column] for column in COLUMNS])
    vectors = rng.normal(size=(1000, 5))
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    feasible = query_z + (vectors @ np.linalg.cholesky(covariance).T) * 2
    alternative = intercept + feasible @ beta
    assert (
        result["adversarial"]["predicted_portfolio_return"] <= alternative.min() + 1e-10
    )


def test_stress_irfs_use_a_source_residual_standard_deviation():
    from app.services.volatility_v2.core.connectedness import (
        fit_volatility_var,
        bootstrap_irf,
    )

    rng = np.random.default_rng(88)
    panel = pd.DataFrame(rng.normal(size=(80, 2)) * [0.2, 0.7], columns=["A", "B"])
    model = fit_volatility_var(panel, max_lag=1)
    rows, _ = bootstrap_irf(
        panel, model, horizons=(1,), reps=20, max_lag=1, shock_scale="one_residual_sd"
    )
    row = next(row for row in rows if row["source"] == "B" and row["target"] == "A")
    assert row["response"] == pytest.approx(
        model.ma(1)[1, 0, 1] * np.sqrt(model.covariance[1, 1])
    )
    assert row["shock_scale"] == "one_residual_sd"


def test_convex_risk_budgets_and_two_step_alignment_conserve_constraints():
    from app.services.volatility_v2.core.allocation import (
        risk_budget_weights,
        two_step_alignment,
        fractions,
    )

    covariance = np.array(
        [[0.04, 0.01, 0.004], [0.01, 0.09, 0.006], [0.004, 0.006, 0.025]]
    )
    weights = np.array([0.65, 0.25, 0.1])
    budgets = np.array([0.3, 0.4, 0.3])
    proposed, meta = risk_budget_weights(
        covariance, weights, budgets, target=0.12, gross_cap=3
    )
    np.testing.assert_allclose(fractions(proposed, covariance), budgets, atol=1e-6)
    assert np.sqrt(proposed @ covariance @ proposed) == pytest.approx(0.12)
    scaled, aligned, details = two_step_alignment(
        covariance, weights, budgets, target=0.12, gross_cap=3
    )
    assert aligned.sum() == pytest.approx(scaled.sum(), abs=1e-8)
    assert aligned @ covariance @ aligned == pytest.approx(
        scaled @ covariance @ scaled, rel=1e-6
    )
    assert np.abs(aligned).sum() <= 3 + 1e-8
    assert (
        np.sum((fractions(aligned, covariance) - budgets) ** 2)
        <= np.sum((fractions(scaled, covariance) - budgets) ** 2) + 1e-8
    )
    signed, _ = risk_budget_weights(
        covariance, np.array([0.65, -0.25, 0.1]), budgets, target=0.12
    )
    assert signed[1] < 0
    np.testing.assert_allclose(fractions(signed, covariance), budgets, atol=1e-6)


def test_execution_costs_are_self_financing_and_use_actual_trades():
    from app.services.volatility_v2.core.execution import trade_cost

    old = np.array([0.6, 0.4])
    desired = np.array([0.3, 0.2])
    result = trade_cost(old, desired, explicit_bps=10, aum=1e6)
    delta = (1 - result["cost_fraction"]) * desired - old
    assert result["cost_fraction"] == pytest.approx(
        np.abs(delta).sum() * 10 / 10000, abs=1e-12
    )
    np.testing.assert_allclose(result["trade_size_usd"], np.abs(delta) * 1e6)
    assert result["one_way_turnover_including_cash"] == pytest.approx(
        (np.abs(delta).sum() + abs(delta.sum())) / 2
    )
    assert trade_cost(old, old, explicit_bps=10)["cost_fraction"] == 0
    impact = trade_cost(
        old,
        desired,
        explicit_bps=10,
        aum=1e6,
        impact_gamma=0.1,
        daily_vol=np.array([0.01, 0.02]),
        adv=np.array([1e7, 2e7]),
    )
    assert impact["cost_fraction"] > result["cost_fraction"]
    with pytest.raises(ValueError, match="positive USD ADV"):
        trade_cost(
            old,
            desired,
            impact_gamma=0.1,
            daily_vol=np.array([0.01, 0.02]),
            adv=np.array([0, 2e7]),
        )


def test_overlay_uses_each_forecast_once_and_holdings_drift_without_trades():
    from app.services.volatility_v2.core.execution import simulate

    index = pd.date_range("2020-01-01", periods=8)
    frame = pd.DataFrame(
        {"A": [0.1, 0.1, -0.05, 0.02, 0.01, 0.02, 0.03, 0.01], "B": 0.0}, index=index
    )
    matrix = np.diag([0.04, 0.09])
    covariance = pd.Series([matrix.copy() for _ in index], index=index, dtype=object)
    reference = pd.Series({"A": 0.5, "B": 0.5})
    target = pd.Series(np.sqrt(reference @ matrix @ reference) * 0.5, index=index)
    result = simulate(
        frame, covariance, reference, target=target, explicit_bps=0, schedule="weekly"
    )
    assert result.iloc[0].gross_return == pytest.approx(0.025)
    assert result.iloc[0].scaling_factor == pytest.approx(0.5)
    expected = np.array([0.25, 0.25]) * [1.1, 1] / 1.025
    np.testing.assert_allclose(result.iloc[0].drifted_weights_after_return, expected)
    np.testing.assert_allclose(result.iloc[1].weights_before_return, expected)
    assert result.iloc[1].gross_traded_notional_fraction == 0
    assert list(result.index[result.rebalance]) == [index[0], index[5]]
    changed = frame.copy()
    changed.iloc[5:, 0] *= 2
    second = simulate(
        changed, covariance, reference, target=target, explicit_bps=0, schedule="weekly"
    )
    pd.testing.assert_frame_equal(result.iloc[:5], second.iloc[:5])


def test_ewma_forecasts_and_exposure_ignore_the_current_and_future_return():
    from app.services.volatility_v2.core.budget_forecasts import covariances

    index = pd.bdate_range("2020-01-01", periods=160)
    frame = pd.DataFrame(
        np.random.default_rng(156).normal(0, 0.01, (160, 2)),
        index=index,
        columns=["A", "B"],
    )
    first, latest, meta = covariances(
        frame, {"forecast_source": "ewma", "min_train": 120}
    )
    changed = frame.copy()
    changed.iloc[140:] *= 3
    second, _, _ = covariances(changed, {"forecast_source": "ewma", "min_train": 120})
    for date in index[120:141]:
        np.testing.assert_allclose(first.loc[date], second.loc[date])
    assert not np.allclose(first.loc[index[141]], second.loc[index[141]])
    assert np.linalg.eigvalsh(latest).min() > 0


def test_regime_target_strings_are_parsed_and_shifted_once_without_future_asset_data(
    monkeypatch,
):
    from app.services.volatility_v2.core import budget_forecasts

    index = pd.date_range("2020-01-01", periods=4)
    returns = pd.DataFrame({"A": [0.01, -0.01, 0.02]}, index=index[:3])
    prices = pd.DataFrame({"Date": index})
    probs = pd.DataFrame(
        {
            "low_vol": [0.6, 0.2, 0.1],
            "transition": [0.3, 0.3, 0.3],
            "high_vol": [0.1, 0.5, 0.6],
            "hmm_converged": True,
        },
        index=index[:3],
    )

    def features(frame, asset):
        assert frame.Date.max() == returns.index[-1]
        return frame

    monkeypatch.setattr(budget_forecasts, "regime_features", features)
    monkeypatch.setattr(
        budget_forecasts,
        "filtered_regimes",
        lambda *args, **kwargs: {
            "probabilities": probs,
            "selected_states": 3,
            "source_fingerprint": "fixture",
        },
    )
    historical, current, _, meta = budget_forecasts.regime_targets(
        prices,
        "A",
        returns,
        {"states": 3, "regime_targets": "low:0.08,normal:0.10,high:0.16"},
        0.1,
    )
    assert pd.isna(historical.iloc[0])
    assert historical.iloc[1] == pytest.approx(0.094)
    assert historical.iloc[2] == pytest.approx(0.126)
    assert current == pytest.approx(0.134)
    assert meta["assigned_targets"]["high_vol"] == 0.16
    with pytest.raises(ValueError, match="duplicate regime aliases"):
        budget_forecasts.regime_targets(
            prices,
            "A",
            returns,
            {
                "regime_targets": {
                    "low": 0.1,
                    "low_vol": 0.2,
                    "normal": 0.1,
                    "high": 0.1,
                }
            },
            0.1,
        )


def test_kelly_leverage_and_volatility_use_btz_return_units_and_real_variance():
    from app.services.volatility_v2.core.budget_forecasts import kelly_target

    result = kelly_target(
        np.array([0.06]), np.array([[0.04]]), np.array([1.0]), gross_cap=3
    )
    assert result["btz_implied_annual_excess_return"] == pytest.approx(0.08)
    assert result["unconstrained_kelly_leverage"] == pytest.approx(2)
    assert result["kelly_optimal_vol_target"] == pytest.approx(0.4)
    capped = kelly_target(
        np.array([0.06]), np.array([[0.04]]), np.array([1.0]), gross_cap=1
    )
    assert capped["constrained_kelly_leverage"] == 1
    assert capped["kelly_optimal_vol_target"] == pytest.approx(0.2)
    negative = kelly_target(np.array([-0.1]), np.array([[0.04]]), np.array([1.0]))
    assert negative["kelly_optimal_vol_target"] == 0


def test_btz_return_training_waits_for_forward_labels_to_mature(monkeypatch):
    from app.services.volatility_v2.core import budget_forecasts

    index = pd.bdate_range("2020-01-01", periods=220)
    frame = pd.DataFrame(
        np.random.default_rng(215).normal(0, 0.01, (220, 1)), index=index, columns=["A"]
    )
    iv = pd.DataFrame({30: 0.2 + np.sin(np.arange(220) / 20) * 0.02}, index=index)
    monkeypatch.setattr(budget_forecasts, "observed_iv", lambda *args: (iv, "fixture"))
    monkeypatch.setattr(
        budget_forecasts,
        "integrated_garch_variance",
        lambda *args: pd.DataFrame({21: 0.035}, index=index),
    )
    controls = {"btz_min_train": 60, "kelly_return_horizon": 21, "refit_interval": 21}
    first, _ = budget_forecasts.btz_returns(frame, controls)
    changed = frame.copy()
    changed.iloc[180:] *= 2
    second, _ = budget_forecasts.btz_returns(changed, controls)
    pd.testing.assert_frame_equal(first.iloc[:180], second.iloc[:180])
    assert first.iloc[-1].notna().all()


def test_estimator_dm_horizon_units_and_asset_isolation():
    from app.services.volatility_v2.core.estimator_diagnostics import dm_tournament

    rng = np.random.default_rng(190)
    dates = pd.date_range("2020-01-01", periods=120)
    group = pd.DataFrame(
        {"date": dates, "asset": "A", "return": rng.normal(0, 0.02, 120)}
    )
    for i, key in enumerate(
        ["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"]
    ):
        group[key] = 0.2 + 0.01 * i + rng.uniform(0, 0.01, 120)
    first = dm_tournament(group, 252, 5)
    rescaled = group.copy()
    rescaled[["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"]] *= (
        np.sqrt(365 / 252)
    )
    second = dm_tournament(rescaled, 365, 5)
    for a, b in zip(first, second):
        assert a["observations"] == 115
        assert a["value"] == pytest.approx(b["value"], abs=1e-9)
    other = group.assign(asset="B", **{"return": group["return"] * 10})
    combined = dm_tournament(pd.concat([other, group]), 252, 5)
    assert [row for row in combined if row["asset"] == "A"] == first


def test_range_correlations_use_observed_pairs_and_declared_method():
    from app.services.volatility_v2.core.estimator_diagnostics import (
        range_correlation_matrix,
    )

    dates = pd.date_range("2020-01-01", periods=45)
    a = pd.DataFrame(
        {
            "Date": dates,
            "Ticker": "A",
            "High": np.exp(np.linspace(0.01, 0.2, 45)),
            "Low": 1.0,
        }
    )
    b = a.assign(Ticker="B", High=np.exp(np.linspace(0.2, 0.01, 45))).drop(
        index=[2, 4, 6]
    )
    frame = pd.concat([a, b])
    actual = range_correlation_matrix(frame)
    assert actual.loc["A", "B"] == pytest.approx(-1.0)
    cosine = range_correlation_matrix(frame, method="uncentered_cosine")
    assert 0 < cosine.loc["A", "B"] < 1
    assert pd.isna(range_correlation_matrix(frame.tail(20)).loc["B", "B"])


def test_sampled_hourly_variation_has_no_overnight_or_gap_imputation():
    from app.services.volatility_v2.core.intraday import variation_from_bars

    dates = pd.date_range("2024-01-01 10:00", periods=7, freq="h")
    returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02, -0.01])
    prices = 100 * np.exp(np.r_[0, np.cumsum(returns)])
    frame = pd.DataFrame(
        {"date": dates.normalize(), "timestamp": dates, "Close": prices}
    )
    actual = variation_from_bars(frame).iloc[0]
    assert actual.sampled_hourly_variance == pytest.approx(returns @ returns)
    expected = np.pi / 2 * 6 / 5 * (np.abs(returns[1:]) @ np.abs(returns[:-1]))
    assert actual.sampled_hourly_bipower == pytest.approx(expected)
    shifted = frame.copy()
    shifted.Close *= 100
    pd.testing.assert_frame_equal(
        variation_from_bars(frame), variation_from_bars(shifted), check_exact=False
    )
    with pytest.raises(ValueError, match="consecutive"):
        variation_from_bars(frame.drop(index=3))


@pytest.mark.parametrize("name", ["cc", "parkinson", "garman_klass", "rogers_satchell"])
def test_each_daily_estimator_matches_independent_formula(name):
    frame = fixture()
    window = 21
    oc = np.log(frame.Close / frame.Open)
    hl = np.log(frame.High / frame.Low)
    values = {
        "cc": np.log(frame.Close / frame.Close.shift()).pow(2),
        "parkinson": hl.pow(2) / (4 * np.log(2)),
        "garman_klass": 0.5 * hl.pow(2) - (2 * np.log(2) - 1) * oc.pow(2),
        "rogers_satchell": np.log(frame.High / frame.Close)
        * np.log(frame.High / frame.Open)
        + np.log(frame.Low / frame.Close) * np.log(frame.Low / frame.Open),
    }
    expected = np.sqrt(values[name].tail(window).mean() * 252)
    assert volatility_estimators(frame, window)[name].iloc[-1] == pytest.approx(
        expected, rel=1e-6
    )


@pytest.mark.parametrize("model", ["GARCH", "EGARCH", "GJR-GARCH", "APARCH", "FIGARCH"])
def test_news_impact_curve_matches_arch_one_step_forecast(model):
    from app.services.volatility_v2.core.garch import fit_model, news_impact_curve

    returns = pd.Series(
        np.random.default_rng(73).normal(0, 0.01, 650),
        index=pd.date_range("2020-01-01", periods=650),
    )
    fit = fit_model(returns, model, "Gaussian")
    curve = news_impact_curve(fit)
    process = fit.model.volatility
    residuals = fit.resid.to_numpy()
    params = fit.params.reindex(process.parameter_names()).to_numpy()
    variance = np.empty(len(residuals) + 1)
    process.compute_variance(
        params,
        np.r_[residuals, 0],
        variance,
        process.backcast(residuals),
        np.vstack([process.variance_bounds(residuals), [0, np.inf]]),
    )
    # Reconstruct exactly the observed final innovation, independently of grid.
    from scipy.interpolate import interp1d

    actual_shock = residuals[-1] / fit.conditional_volatility.iloc[-1]
    interpolated = interp1d(
        [r["standardized_shock"] for r in curve],
        [r["next_period_variance"] for r in curve],
    )(actual_shock)
    expected = float(fit.forecast(horizon=1).residual_variance.iloc[-1, 0]) / 10000
    assert variance[-1] / 10000 == pytest.approx(expected, rel=1e-5)
    assert interpolated == pytest.approx(expected, rel=0.02)


def test_har_qlike_loss_and_direction_are_actual_held_out_values():
    from app.services.volatility_v2.core.har import expanding_forecasts

    dates = pd.date_range("2020-01-01", periods=180)
    x = pd.DataFrame(
        {"daily": np.random.default_rng(31).uniform(0.1, 0.3, 180)}, index=dates
    )
    y = 0.08 + 0.6 * x.daily
    rows, metrics, loss, _ = expanding_forecasts(
        x, y, min_train=40, loss_function="qlike", directional_baseline=x.daily
    )
    valid = rows.set_index("date").dropna(subset=["forecast", "actual"])
    ratio = (valid.actual / valid.forecast).pow(2)
    pd.testing.assert_series_equal(
        loss, ratio - np.log(ratio) - 1, check_names=False, check_freq=False
    )
    assert 0 <= metrics["directional_hit_rate"] <= 1


def test_fixed_aparch_power_uses_arch_process():
    from app.services.volatility_v2.core.garch import fit_model

    returns = pd.Series(np.random.default_rng(39).normal(0, 0.01, 500))
    fit = fit_model(returns, "APARCH", "Gaussian", aparch_delta=1.5)
    assert fit.model.volatility.delta == 1.5
    assert "delta" not in fit.params


def test_combination_weights_use_only_matured_outcomes():
    from app.services.volatility_v2.core.har import causal_combination

    dates = pd.date_range("2020-01-01", periods=100)
    actual = pd.Series(np.linspace(0.1, 0.3, 100), index=dates)
    models = {
        name: pd.DataFrame(
            {
                "date": dates,
                "actual": actual.to_numpy(),
                "forecast": (actual + offset).to_numpy(),
            }
        )
        for name, offset in [("a", 0.02), ("b", -0.01)]
    }
    first = causal_combination(models, 5, min_history=10)
    for rows in models.values():
        rows.loc[rows.date >= dates[60], "actual"] *= 4
    changed = causal_combination(models, 5, min_history=10)
    # Targets can change at origin 60 but cannot affect formation weights before 65.
    first_weights = [
        r["weights"] for r in first if "weights" in r and r["date"] < dates[65]
    ]
    changed_weights = [
        r["weights"] for r in changed if "weights" in r and r["date"] < dates[65]
    ]
    assert first_weights == changed_weights


def test_har_rejects_unidentifiable_predictors():
    from app.services.volatility_v2.core.har import expanding_forecasts

    dates = pd.date_range("2020-01-01", periods=100)
    values = np.linspace(0.1, 0.3, 100)
    x = pd.DataFrame({"a": values, "b": values}, index=dates)
    with pytest.raises(ValueError, match="rank-deficient"):
        expanding_forecasts(x, x.a.shift(-1), min_train=40)


def test_fixed_figarch_d_is_constrained_mle_with_causal_forecasts():
    from app.services.volatility_v2.core.garch import fit_model, expanding_model

    returns = pd.Series(
        np.random.default_rng(48).normal(0, 0.01, 350),
        index=pd.bdate_range("2020-01-01", periods=350),
    )
    fitted = fit_model(returns, "FIGARCH", "Gaussian", figarch_d=0.4)
    assert fitted.params["d"] == 0.4
    assert np.isfinite(fitted.loglikelihood)
    path, _ = expanding_model(
        returns,
        "FIGARCH",
        "Gaussian",
        min_train=120,
        evaluation_days=30,
        refit_interval=15,
        figarch_d=0.4,
    )
    assert all(record["d"] == 0.4 for record in path.attrs["parameter_history"])
    changed = returns.copy()
    changed.iloc[-10:] *= 2
    other, _ = expanding_model(
        changed,
        "FIGARCH",
        "Gaussian",
        min_train=120,
        evaluation_days=30,
        refit_interval=15,
        figarch_d=0.4,
    )
    np.testing.assert_allclose(path.variance.iloc[:-10], other.variance.iloc[:-10])


def test_duration_backtest_reports_insufficient_exceptions_and_actual_gaps():
    from app.services.volatility_v2.core.garch import duration_backtest

    frame = pd.DataFrame({"return": np.zeros(150), "var_cutoff": -0.02})
    assert "duration_unavailable_reason" in duration_backtest(frame)
    frame.loc[[4, 17, 33, 52, 71, 90, 110], "return"] = -0.03
    result = duration_backtest(frame)
    assert result["completed_durations"] == 6
    assert result["right_censored_sessions"] == 39
    assert np.isfinite(result["duration_lr"])
    assert 0 <= result["duration_p_value"] <= 1


def test_nyblom_uses_actual_individual_likelihood_or_reports_boundary():
    from app.services.volatility_v2.core.garch import fit_model, nyblom_stability

    rng = np.random.default_rng(891)
    variance, previous = 0.0001, 0.0
    values = []
    for _ in range(1200):
        variance = 0.00001 + 0.15 * previous**2 + 0.75 * variance
        previous = np.sqrt(variance) * rng.normal()
        values.append(previous)
    fit = fit_model(pd.Series(values), "GARCH", "Gaussian")
    result = nyblom_stability(fit, simulations=100)
    assert "unavailable_reason" not in result
    assert result["observations"] == 1200
    assert result["parameters"] == list(fit.params.index)
    assert result["nyblom_joint_statistic"] >= 0
    assert 0 <= result["p_value"] <= 1


def test_connectedness_percentile_window_counts_sessions_not_sampled_rows(monkeypatch):
    from types import SimpleNamespace
    from app.services.volatility_v2.core import connectedness

    dates = pd.bdate_range("2000-01-01", periods=3000)
    panel = pd.DataFrame({"A": np.arange(3000), "B": np.arange(3000)}, index=dates)
    monkeypatch.setattr(
        connectedness,
        "fit_volatility_var",
        lambda *args, **kwargs: SimpleNamespace(lag=1, stable=True),
    )
    monkeypatch.setattr(
        connectedness,
        "generalized_decomposition",
        lambda *args: np.array([[0.8, 0.2], [0.3, 0.7]]),
    )
    result = connectedness.rolling_connectedness(panel, window=60, interval=63)
    timeline = result["timeline"]
    lower = panel.index[-1 - 2520]
    expected = ((timeline.index >= lower) & (timeline.index < panel.index[-1])).sum()
    assert timeline.percentile_history_observations.iloc[-1] == expected
    assert expected < len(timeline) - 1


def test_dcc_cache_is_bounded_content_sensitive_and_isolated(monkeypatch):
    from app.services.volatility_v2.core import dcc

    calls = []

    def compute(frame, *controls):
        calls.append(frame.to_numpy().copy())
        return {"values": frame.to_numpy().copy()}

    monkeypatch.setattr(dcc, "_expanding_dcc", compute)
    dcc._CACHE.clear()
    frame = pd.DataFrame({"A": [0.01, 0.02], "B": [0.02, -0.01]})
    first = dcc.expanding_dcc(frame)
    first["values"][0, 0] = 99
    assert dcc.expanding_dcc(frame)["values"][0, 0] == 0.01
    assert len(calls) == 1
    for number in range(6):
        changed = frame.copy()
        changed.iloc[0, 0] += number + 1
        dcc.expanding_dcc(changed)
    assert len(dcc._CACHE) == 4
    dcc._CACHE.clear()


def test_intraday_only_yang_zhang_does_not_rename_close_close_returns():
    frame = fixture()
    original = volatility_estimators(frame)
    excluded = volatility_estimators(frame, include_overnight=False)
    pd.testing.assert_series_equal(original.cc, excluded.cc)
    pd.testing.assert_series_equal(original["return"], excluded["return"])
    assert (excluded.yang_zhang <= original.yang_zhang).all()


def test_shared_return_primitives_do_not_silently_collapse_duplicate_prices():
    from app.services.volatility_v2.core.analytics import returns_panel

    frame = fixture()
    with pytest.raises(ValueError):
        returns_panel(pd.concat([frame, frame.iloc[:1]], ignore_index=True))


def test_observed_iv_rejects_unsupported_continuous_session_mapping():
    from app.services.volatility_v2.core.vrp import observed_iv

    with pytest.raises(ValueError, match="continuous-session"):
        observed_iv("^GSPC", pd.date_range("2020-01-01", periods=200))


def test_global_hmm_sync_is_future_invariant_for_each_asset(monkeypatch):
    from app.services.volatility_v2.features import feature_04

    rng = np.random.default_rng(230)
    dates = pd.bdate_range("2020-01-01", periods=600)
    assets, frames = ["SPY", "QQQ"], []
    for asset in assets:
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
        opening = close * np.exp(rng.normal(0, 0.003, len(dates)))
        frames.append(
            pd.DataFrame(
                {
                    "Ticker": asset,
                    "Date": dates,
                    "Open": opening,
                    "High": np.maximum(opening, close) * 1.015,
                    "Low": np.minimum(opening, close) * 0.985,
                    "Close": close,
                    "Volume": 1e6,
                }
            )
        )
    observed = pd.concat(frames, ignore_index=True)
    monkeypatch.setattr(
        feature_04, "load_assets", lambda *args, **kwargs: (assets, observed)
    )
    controls = {"states": 2, "min_train": 120, "refit_interval": 120, "hmm_restarts": 1}
    original = feature_04.run(controls)
    mask = observed.Ticker.eq("QQQ") & observed.Date.ge(dates[480])
    observed.loc[mask, ["Open", "High", "Low", "Close"]] *= 1.5
    changed = feature_04.run(controls)
    for key in ["probabilistic_regime_timeline", "global_vol_regime_sync_index"]:
        cutoff = dates[480].strftime("%Y-%m-%d")
        before = [r for r in original["charts"][key] if r["date"] < cutoff]
        after = [r for r in changed["charts"][key] if r["date"] < cutoff]
        assert before == after


def test_causal_combination_does_not_create_weights_from_nonfinite_qlike():
    from app.services.volatility_v2.core.har import causal_combination

    dates = pd.date_range("2020-01-01", periods=80)
    actual = np.r_[np.zeros(40), np.repeat(0.15, 40)]
    rows = {
        name: pd.DataFrame({"date": dates, "actual": actual, "forecast": prediction})
        for name, prediction in [("a", 0.1), ("b", 0.2)]
    }
    records = causal_combination(rows, 5, min_history=10)
    weighted = [r for r in records if "weights" in r]
    assert weighted
    assert all(r["latest_training_origin"] >= dates[40] for r in weighted)
    assert all(np.isfinite(list(r["weights"].values())).all() for r in weighted)


def test_each_asset_return_uses_its_actual_prior_observation_without_fill():
    from app.services.volatility_v2.core.analytics import returns_panel

    dates = pd.date_range("2024-01-05", periods=4)
    frame = pd.DataFrame(
        {
            "Ticker": ["SPY", "SPY", "BTC_USD", "BTC_USD", "BTC_USD", "BTC_USD"],
            "Date": [dates[0], dates[3], *dates],
            "Close": [100.0, 102.0, 100.0, 101.0, 102.0, 103.0],
        }
    )
    returns = returns_panel(frame)
    assert returns.loc[dates[3], "SPY"] == pytest.approx(np.log(102 / 100))
    assert returns.loc[dates[3], "BTC_USD"] == pytest.approx(np.log(103 / 102))
    assert returns.loc[dates[1:3], "SPY"].isna().all()
