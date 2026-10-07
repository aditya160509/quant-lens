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
