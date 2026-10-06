"""Feature-level numerical and execution regressions."""
import numpy as np
import pandas as pd
import pytest

@pytest.fixture
def local_market(monkeypatch):
    from app.services.ml_v2.core import data_loader
    import importlib
    rng = np.random.default_rng(77)
    dates = pd.bdate_range("2022-01-03", periods=380)
    symbols = [f"T{i}" for i in range(8)]
    rows = []
    for ticker in symbols:
        close = 100 * np.exp(np.cumsum(rng.normal(.0003, .01, len(dates))))
        for date, price in zip(dates, close):
            rows.append({"Ticker": ticker, "Date": date, "Open": price * .999,
                         "High": price * 1.01, "Low": price * .99, "Close": price, "Volume": 100000.})
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(data_loader, "load_market_ohlcv", lambda *a, **k: frame)
    monkeypatch.setattr(data_loader, "available_symbols", lambda **kwargs: symbols)
    monkeypatch.setattr(data_loader, "load_macro", lambda: pd.DataFrame(columns=["date"]))
    monkeypatch.setattr(data_loader, "load_fama_french", lambda: pd.DataFrame(columns=["date"]))
    metadata = pd.DataFrame({"ticker": symbols, "sector": [f"S{i//2}" for i in range(8)]})
    monkeypatch.setattr(data_loader, "load_fundamentals_metadata", lambda: metadata)
    for name in ["panel", "alpha", "volatility", "barriers", "allocation", "regimes", "composite", "microstructure"]:
        module = importlib.import_module("app.services.ml_v2.core." + name)
        monkeypatch.setattr(module, "load_macro", lambda: pd.DataFrame(columns=["date"]), raising=False)
        monkeypatch.setattr(module, "load_fama_french", lambda: pd.DataFrame(columns=["date"]), raising=False)
    return symbols

@pytest.mark.parametrize("feature", ["01", "02", "03", "04", "05", "06", "08"])
def test_feature_runs_on_local_observations(local_market, feature):
    import json
    from app.services.ml_v2.registry import run_feature
    payload = {"symbols":local_market,"max_symbols":8,"lookback_days":380}
    payload.update({"01":{"model_type":"ridge","cpcv_n_groups":4},"02":{"model_family":"ridge"},
        "03":{"asset":"T0","forecast_horizons":[1,5]}}.get(feature,{}))
    result = run_feature(feature, payload)
    assert result["status"] != "error"
    json.dumps(result, allow_nan=False)
    from importlib import import_module
    contract = import_module(f"app.services.ml_v2.features.feature_{feature}").OUTPUTS
    assert all(row["id"] in result[row["location"]] for row in contract)
