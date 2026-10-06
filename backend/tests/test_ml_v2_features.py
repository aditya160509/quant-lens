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


def test_volatility_regime_switch_scored_with_dm_var_es_and_unmanaged_size(local_market):
    from app.services.ml_v2.registry import run_feature
    result = run_feature("03", {"symbols": local_market, "max_symbols": 8, "lookback_days": 380, "asset": "T0", "forecast_horizons": [1, 5, 21]})
    tournament = {(r["model"], r["horizon"]): r for r in result["tables"]["forecast_tournament"]}
    assert {"HAR-RV", "EWMA", "GJR-GARCH", "Regime-switch"} <= {m for m, _ in tournament}
    assert tournament[("Regime-switch", 1)]["dm_stat_vs_regime_switch"] is None
    assert "dm_p_value" in tournament[("EWMA", 5)]
    today = result["tables"]["risk_today"][0]
    assert today["regime"] in {"calm", "stress"} and today["unmanaged_size"] == 1.0
    assert all(today[f"range_{h}d_low"] < 0 < today[f"range_{h}d_high"] for h in (1, 5, 21))
    levels = {(r["horizon"], r["level"]): r for r in result["tables"]["var_es"]}
    assert levels[(1, 0.99)]["var"] > levels[(1, 0.95)]["var"] > 0 and levels[(1, 0.95)]["es"] >= levels[(1, 0.95)]["var"]
    assert {r["strategy"] for r in result["tables"]["position_sizing"]} == {"unmanaged", "vol_targeted"}
    assert result["provenance"]["purge"] == 21


def test_volatility_watchlist_is_capped_and_scores_each_ticker(local_market):
    from app.services.ml_v2.registry import run_feature
    result = run_feature("03", {"watchlist": local_market[:3], "lookback_days": 380})
    assert {r["asset"] for r in result["tables"]["risk_today"]} == set(local_market[:3])
    with pytest.raises(ValueError, match="at most 50"):
        run_feature("03", {"watchlist": [f"T{i}" for i in range(51)]})


def test_stress_probability_is_causal_and_regime_artifact_hands_off(local_market):
    from app.services.ml_v2.core.regimes import filtered_stress_probability
    rng = np.random.default_rng(5)
    calm, wild = rng.normal(0, .005, 200), rng.normal(0, .03, 100)
    returns = pd.Series(np.concatenate([calm, wild, calm]), index=pd.bdate_range("2022-01-03", periods=500))
    base = filtered_stress_probability(returns, 300)
    altered = returns.copy(); altered.iloc[400:] = 0.5
    changed = filtered_stress_probability(altered, 300)
    pd.testing.assert_series_equal(base.iloc[:400], changed.iloc[:400])
    assert base.iloc[220:290].mean() > base.iloc[:150].mean()
    from app.services.ml_v2.registry import run_feature
    regimes = run_feature("06", {"symbols": local_market, "max_symbols": 8, "lookback_days": 380})
    assert regimes["tables"]["regime_vs_constant_exposure"][0]["strategy"] == "regime_filtered"
    handed = run_feature("03", {"symbols": local_market, "max_symbols": 8, "lookback_days": 380, "asset": "T0", "forecast_horizons": [1],
                                "regime_artifact_id": regimes["meta"]["artifact_id"]})
    assert handed["meta"]["regime_source"] == "supplied regime_artifact_id"


def test_allocation_controls_bands_trade_list_and_alpha_views(local_market):
    from app.services.ml_v2.registry import run_feature
    base = {"symbols": local_market, "max_symbols": 8, "lookback_days": 380}
    alpha = run_feature("02", {**base, "model_family": "ridge", "prediction_horizon": 5})
    result = run_feature("05", {**base, "bootstrap_samples": 8, "alpha_artifact_id": alpha["meta"]["artifact_id"],
                                "holdings": {"T0": 100, "T1": 50, "T2": 10}, "holdings_unit": "shares"})
    strategies = {r["strategy"] for r in result["tables"]["controls_summary"]}
    assert strategies == {"min_variance", "turnover_aware", "standard_hrp", "inverse_variance", "equal_weight"}
    assert result["meta"]["variant"] == "min_variance" and result["meta"]["estimator"] == "ledoit_wolf"
    bands = result["tables"]["weight_stability"]
    assert bands and all(r["p05"] <= r["p95"] + 1e-12 for r in bands)
    trades = result["tables"]["trade_list"]
    assert sum(t["trade_weight"] for t in trades) == pytest.approx(0, abs=1e-9)
    summary = result["tables"]["rebalance_summary"][0]
    assert summary["turnover"] == pytest.approx(sum(abs(t["trade_weight"]) for t in trades))
    assert summary["volatility_before"] > 0 and isinstance(summary["trade_recommended"], bool)
    assert result["meta"]["alpha_views"]["artifact_id"] == alpha["meta"]["artifact_id"]


def test_allocation_relaxes_bounds_that_cannot_sum_to_one():
    from app.services.ml_v2.core.allocation import relax_infeasible_bounds
    request, notes = relax_infeasible_bounds({"max_weight": .25, "max_sector_weight": .4}, ["A", "B", "C", "D", "E"],
                                             {"A": "X", "B": "X", "C": "X", "D": "Y", "E": "Z"})
    assert request["max_weight"] * 5 >= 1 and request["max_sector_weight"] > .4 and len(notes) == 2
    unchanged, none = relax_infeasible_bounds({"max_weight": .5, "max_sector_weight": .6}, ["A", "B", "C"], {"A": "X", "B": "Y", "C": "Z"})
    assert unchanged["max_weight"] == .5 and none == []


def test_allocation_rebalances_only_when_gain_exceeds_cost():
    from app.services.ml_v2.core.allocation import rebalance_gain
    cov = pd.DataFrame(np.diag([.04, .01]) / 252, index=["A", "B"], columns=["A", "B"])
    current, target = pd.Series({"A": .5, "B": .5}), pd.Series({"A": .3, "B": .7})
    gain, turnover, cost = rebalance_gain(current, target, cov, 252., 2.5, cost_bps=5)
    assert gain > cost and turnover == pytest.approx(.4)
    assert rebalance_gain(current, target, cov, 252., 2.5, cost_bps=1000)[0] < rebalance_gain(current, target, cov, 252., 2.5, cost_bps=1000)[2]
