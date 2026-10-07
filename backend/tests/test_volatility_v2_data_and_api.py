import pandas as pd
import pytest


@pytest.fixture
def prices(tmp_path, monkeypatch):
    from app.services.volatility_v2.core import data_loader as dl

    path = tmp_path / "prices.parquet"
    dates = pd.date_range("2024-01-01", periods=40)
    frame = pd.DataFrame(
        {
            "Ticker": "SPY",
            "Date": dates,
            "Open": 100.0,
            "High": 102.0,
            "Low": 99.0,
            "Close": 101.0,
            "Volume": 1000.0,
        }
    )
    frame.to_parquet(path)
    monkeypatch.setattr(dl, "MARKET_UNIVERSE", path)
    return dl, frame, path


def test_unknown_and_empty_assets_fail(prices):
    from app.services.volatility_v2.core.analytics import load_assets

    for assets in (["SPY", "UNKNOWN"], [], ""):
        with pytest.raises(ValueError):
            load_assets({"assets": assets})


def test_cutoff_and_exact_observation_lookback(prices):
    dl, frame, _ = prices
    with dl.request_scope({"as_of_date": "2024-01-20"}):
        data = dl.ohlcv_for_symbols(["SPY"], 7)
    assert len(data) == 7
    assert data.Date.max() == frame.Date.iloc[19]
    assert data.Date.min() == frame.Date.iloc[13]


def test_source_replacement_invalidates_cache(prices):
    dl, frame, path = prices
    assert dl.ohlcv_for_symbols(["SPY"]).Close.iloc[-1] == 101.0
    frame.loc[frame.index[-1], "Close"] = 101.5
    frame.to_parquet(path)
    assert dl.ohlcv_for_symbols(["SPY"]).Close.iloc[-1] == 101.5


def test_weights_are_parsed_without_silent_normalization(prices):
    from app.services.volatility_v2.core.analytics import parse_weights

    assert parse_weights({"weights": "SPY:1.5"}, ["SPY"]).iloc[0] == 1.5
    assert parse_weights({"weights": '{"SPY": 0.7}'}, ["SPY"]).iloc[0] == 0.7
    for raw in ("garbage", {"SPY": 0}, {"SPY": "bad"}, {"UNKNOWN": 1}):
        with pytest.raises(ValueError):
            parse_weights({"weights": raw}, ["SPY"])


def test_duplicates_and_bad_ohlc_are_rejected(prices):
    dl, frame, path = prices
    pd.concat([frame, frame.iloc[-1:]]).to_parquet(path)
    with pytest.raises(ValueError, match="Duplicate"):
        dl.ohlcv_for_symbols(["SPY"])
    frame.loc[0, "High"] = 100.0
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="inconsistent"):
        dl.ohlcv_for_symbols(["SPY"])
