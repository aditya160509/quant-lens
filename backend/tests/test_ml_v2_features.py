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


def test_alpha_controls_exact_contributions_formulas_and_artifact(local_market):
    from app.services.ml_v2.core.common import get_artifact
    from app.services.ml_v2.registry import run_feature
    result = run_feature("02", {"symbols": local_market, "max_symbols": 8, "lookback_days": 380, "model_family": "ridge",
                                "prediction_horizon": 5, "formulas": [{"name": "rev", "expr": "-ts_return(close, 5)"}]})
    controls = {row["model"] for row in result["tables"]["controls"]}
    assert {"ridge", "ols3", "ic_composite"} <= controls
    assert set(result["provenance"]) >= {"train_window", "test_window", "purge", "embargo", "universe", "missing_share"}
    assert "f_rev" in result["tables"]["training_audit"][0]["features"]
    for row in result["tables"]["ticker_contributions"]:
        assert row["base_value"] + sum(row["contributions"].values()) == pytest.approx(row["prediction"], abs=1e-9)
    stored = get_artifact(result["meta"]["artifact_id"])
    assert set(stored["predictions"]) == set(local_market)
    assert {row["weighting"] for row in result["tables"]["decile_summary"]} == {"equal", "value"}


def test_alpha_formula_rejects_unsafe_and_unknown_names(local_market):
    from app.services.ml_v2.registry import run_feature
    base = {"symbols": local_market, "max_symbols": 8, "lookback_days": 380, "model_family": "ridge"}
    for expr in ("__import__('os')", "close.sum()", "nonexistent_field + 1"):
        with pytest.raises(ValueError, match="Formula bad"):
            run_feature("02", {**base, "formulas": [{"name": "bad", "expr": expr}]})
