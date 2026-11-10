from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.screener_v2.core import estimators


def test_pit_scope_matches_per_date_technical_panel(monkeypatch):
    from app.services.screener_v2.core import data_loader, performance
    dates = pd.bdate_range("2023-01-02", periods=320)
    rng = np.random.default_rng(7)
    rows = []
    for ticker in ["AAA", "BBB", "SPY"]:
        close = 100 * np.exp(rng.normal(0, .01, len(dates)).cumsum())
        rows.append(pd.DataFrame({"Ticker": ticker, "Date": dates, "Open": close * .999, "High": close * 1.01, "Low": close * .99, "Close": close, "Volume": 1_000_000.}))
    raw = pd.concat(rows, ignore_index=True)
    def ohlcv(symbols, lookback_days=None):
        cutoff = data_loader.AS_OF.get()
        return raw[raw.Ticker.isin(list(symbols)) & (raw.Date <= cutoff)]
    factors = pd.DataFrame({"date": dates, **{name: rng.normal(0, .01, len(dates)) for name in ["mkt_rf", "smb", "hml"]}, "rf": .0001})
    monkeypatch.setattr(data_loader, "ohlcv_for_symbols", ohlcv)
    monkeypatch.setattr(estimators, "ohlcv_for_symbols", ohlcv)
    monkeypatch.setattr(estimators, "load_factor_returns", lambda: factors)
    as_of = dates[300]
    periods = {"as_of_date": str(as_of.date())}
    with data_loader.as_of_context(as_of):
        old = estimators.latest_technical_features(["AAA", "BBB"], 260, periods)
        with performance.pit_scope({}):
            fast = estimators.latest_technical_features(["AAA", "BBB"], 260, periods)
    pd.testing.assert_frame_equal(old, fast, check_exact=False, rtol=1e-9)
    assert (old.price_observation_date == as_of).all()


def test_panel_cache_is_bounded_by_bytes(monkeypatch):
    from app.services.screener_v2.core import validation
    monkeypatch.setattr(validation, "_PANEL_CACHE", validation.OrderedDict())
    monkeypatch.setattr(validation, "_panel_cache_bytes", 0)
    panel = pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "score": np.arange(100.0)})
    size = int(panel.memory_usage(deep=True, index=True).sum())
    monkeypatch.setattr(validation, "_PANEL_CACHE_MAX_BYTES", size * 3)
    for key in range(5):
        validation._panel_cache_put(key, panel)
    assert list(validation._PANEL_CACHE) == [2, 3, 4]
    assert validation._panel_cache_bytes == size * 3
    assert validation._panel_cache_get(2) is panel  # a hit becomes most recent
    validation._panel_cache_put(5, panel)
    assert list(validation._PANEL_CACHE) == [4, 2, 5]
    validation._panel_cache_put(6, pd.concat([panel] * 4))  # larger than the whole budget: never stored
    assert 6 not in validation._PANEL_CACHE and validation._panel_cache_bytes == size * 3


def test_batched_idiosyncratic_vol_matches_statsmodels_per_ticker():
    import statsmodels.api as sm
    dates = pd.bdate_range("2024-01-01", periods=63)
    rng = np.random.default_rng(3)
    factors = pd.DataFrame({"date": dates, **{k: rng.normal(0, .01, 63) for k in ["mkt_rf", "smb", "hml"]}, "rf": .0001})
    returns = pd.DataFrame(rng.normal(0, .02, (63, 6)), index=dates, columns=list("ABCDEF"))
    returns.iloc[5, 2] = np.nan  # one gap makes a ticker ineligible
    out = estimators._idiosyncratic_vol(returns, factors)
    aligned = factors.set_index("date").reindex(dates)
    for ticker in returns:
        frame = pd.concat([returns[ticker].rename("y"), aligned], axis=1).dropna()
        if len(frame) < 63:
            assert np.isnan(out[ticker])
            continue
        fit = sm.OLS(frame.y - frame.rf, sm.add_constant(frame[["mkt_rf", "smb", "hml"]])).fit()
        assert np.isclose(out[ticker], np.sqrt(np.mean(fit.resid ** 2) * 252), rtol=1e-9, atol=0)
    assert estimators._idiosyncratic_vol(returns.iloc[:62], factors).isna().all()
    alone = estimators._idiosyncratic_vol(returns[["A"]], factors)["A"]
    assert alone == out["A"]  # bit-identical whatever else is in the batch
