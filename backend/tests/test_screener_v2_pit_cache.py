from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.screener_v2.core import estimators


def test_pit_scope_matches_per_date_technical_panel(monkeypatch):
    from app.services.screener_v2.core import data_loader, pit_cache
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
        with pit_cache.pit_scope({}):
            fast = estimators.latest_technical_features(["AAA", "BBB"], 260, periods)
    pd.testing.assert_frame_equal(old, fast, check_exact=False, rtol=1e-9)
    assert (old.price_observation_date == as_of).all()
