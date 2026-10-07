import math
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
