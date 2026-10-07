import math
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


def test_iv_upload_validation_and_sandbox(prices, tmp_path, monkeypatch):
    from app.services.volatility_v2.core import uploads

    dl, _, _ = prices
    monkeypatch.setattr(dl, "BACKEND_DATA", tmp_path)
    raw = b"date,asset,implied_vol,maturity_days,source\n2024-01-01,SPY,0.2,30,observed vendor\n2024-01-02,SPY,0.21,30,observed vendor\n"
    saved = uploads.save_upload(raw, "implied_volatility")
    assert saved["rows"] == 2
    assert saved["assets"] == ["SPY"]
    assert (
        uploads.upload_path(saved["upload_id"]).parent
        == tmp_path / "volatility_v2/uploads"
    )
    for identifier in ("../../outside", "/etc/passwd", "../" + "a" * 64, "A" * 64):
        with pytest.raises(ValueError, match="identifier"):
            uploads.upload_path(identifier)
    with dl.request_scope({"as_of_date": "2024-01-01"}):
        assert len(uploads.load_implied_volatility(saved["upload_id"], "SPY")) == 1
    for data in (
        raw.replace(b"0.2,30", b"20,30"),
        raw.replace(b"SPY", b"UNKNOWN"),
        raw.replace(b"30,observed", b"31,observed"),
        raw + raw.split(b"\n")[1] + b"\n",
    ):
        with pytest.raises(ValueError):
            uploads.save_upload(data, "implied_volatility")


def test_vix_cannot_be_substituted_for_an_individual_asset(prices):
    from app.services.volatility_v2.core.vrp import observed_iv

    with pytest.raises(ValueError, match="matching observed"):
        observed_iv("SPY", pd.date_range("2024-01-01", periods=200))


def test_portfolio_currency_uses_observed_fx_and_rejects_stale_rates(
    prices, tmp_path, monkeypatch
):
    from app.services.volatility_v2.core import currency

    dl, frame, path = prices
    foreign = frame.copy()
    foreign["Ticker"] = "^N225"
    foreign["Close"] = foreign.Close * 100
    foreign["Open"] = foreign.Open * 100
    foreign["High"] = foreign.High * 100
    foreign["Low"] = foreign.Low * 100
    pd.concat([frame, foreign]).to_parquet(path)
    data = dl.ohlcv_for_symbols(["SPY", "^N225"])
    fx_path = tmp_path / "fx.parquet"
    fx = pd.DataFrame(
        {
            "Ticker": "USDJPY=X",
            "Date": frame.Date,
            "Close": 150 + pd.Series(range(len(frame))),
        }
    )
    fx.to_parquet(fx_path)
    monkeypatch.setattr(currency, "FX_DAILY", fx_path)
    with pytest.raises(ValueError, match="quote_currencies"):
        currency.portfolio_returns(data, {})
    returns, metadata = currency.portfolio_returns(
        data, {"quote_currencies": {"^N225": "JPY"}}
    )
    assert metadata["base_currency"] == "USD"
    assert returns["^N225"].iloc[0] == pytest.approx(math.log(150 / 151))
    fx.iloc[1:].to_parquet(fx_path)
    with pytest.raises(ValueError, match="exact-date"):
        currency.portfolio_returns(data, {"quote_currencies": {"^N225": "JPY"}})
