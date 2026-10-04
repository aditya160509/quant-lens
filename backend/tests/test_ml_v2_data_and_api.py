"""Regression checks for ML V2 data integrity."""
import numpy as np
import pandas as pd
import pytest
from app.services.ml_v2.core import data_loader as loader

@pytest.fixture
def quotes(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=40)
    rows = [{"Ticker": ticker, "Date": date, "Close": 100 + i, "Volume": 1000}
            for ticker in ["AAA", "BBB"] for i, date in enumerate(dates)
            if not (ticker == "AAA" and i == 25)]
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(loader, "load_market_ohlcv", lambda: frame)
    monkeypatch.setattr(loader, "available_symbols", lambda **kwargs: ["AAA", "BBB"])
    return dates

def test_unknown_symbols_are_not_substituted(quotes):
    with pytest.raises(ValueError, match="MISSING"):
        loader.parse_symbols({"symbols": ["AAA", "MISSING"]})

def test_single_symbol_is_not_padded(quotes):
    assert loader.parse_symbols({"symbols": ["AAA"], "max_symbols": 1}) == ["AAA"]

def test_sp500_requires_membership(quotes):
    with pytest.raises(ValueError, match="membership"):
        loader.parse_symbols({"universe": "sp500"})

def test_missing_quotes_and_returns_remain_missing(quotes):
    closes = loader.close_matrix(["AAA", "BBB"], 40)
    returns = loader.returns_matrix(["AAA", "BBB"], 40)
    assert np.isnan(closes.loc[quotes[25], "AAA"])
    assert np.isnan(returns.loc[quotes[25], "AAA"])
    assert np.isnan(returns.loc[quotes[26], "AAA"])

def test_as_of_excludes_future_quotes(quotes):
    token = loader.AS_OF_DATE.set(quotes[20])
    try:
        closes = loader.close_matrix(["AAA", "BBB"], 40)
        assert closes.index.max() == quotes[20]
    finally:
        loader.AS_OF_DATE.reset(token)
