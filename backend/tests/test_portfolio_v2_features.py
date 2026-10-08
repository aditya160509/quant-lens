"""Exercise every backend feature contract on deterministic observed-data fixtures."""

import importlib
import json
import numpy as np
import pandas as pd
import pytest
from app.services.portfolio_v2.registry import run_feature, contract_for


@pytest.fixture
def observed_data(monkeypatch):
    from app.services.portfolio_v2.core import data_loader as data

    # Import aliases before patching their source module, so fixture teardown
    # restores real readers rather than aliases captured from a prior fixture.
    modules = {
        name: importlib.import_module("app.services.portfolio_v2.features." + name)
        for name in ["feature_03", "feature_05", "feature_06"]
    }

    dates = pd.bdate_range("2020-01-01", periods=420)
    rng = np.random.default_rng(271)
    symbols = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "AGG"]
    factor = rng.normal(0, 0.005, (420, 6))
    returns = pd.DataFrame(
        factor[:, :3] @ rng.normal(0, 0.3, (3, 7))
        + rng.normal(0.0003, 0.006, (420, 7)),
        index=dates,
        columns=symbols,
    )
    closes = 100 * (1 + returns).cumprod()
    frames = []
    for c in symbols:
        close = closes[c]
        opening = close * (1 + rng.normal(0, 0.001, 420))
        frames.append(
            pd.DataFrame(
                {
                    "Ticker": c,
                    "Date": dates,
                    "Open": opening,
                    "High": np.maximum(close, opening) * 1.002,
                    "Low": np.minimum(close, opening) * 0.998,
                    "Close": close,
                    "Volume": 1000000.0,
                    "Asset_Class": "equity",
                }
            )
        )
    raw = pd.concat(frames, ignore_index=True)
    monkeypatch.setattr(
        data,
        "_selected_ohlcv",
        lambda selected, frequency, version: raw.loc[raw.Ticker.isin(selected)].copy(),
    )
    monkeypatch.setattr(data, "available_symbols", lambda **kwargs: symbols)
    monkeypatch.setattr(data, "source_version", lambda: (("fixture", 1, 1),))
    metadata = pd.DataFrame(
        {
            "ticker": symbols,
            "sector": ["a", "a", "b", "b", "b", "c", "c"],
            "currency": "USD",
        }
    )
    monkeypatch.setattr(data, "load_fundamentals_metadata", lambda: metadata.copy())
    from app.services.portfolio_v2.core import liquidity

    monkeypatch.setattr(
        liquidity, "load_fundamentals_metadata", lambda: metadata.copy()
    )
    factors = pd.DataFrame(
        factor, columns=["mkt_rf", "smb", "hml", "rmw", "cma", "mom"]
    ).assign(date=dates, rf=0.00001)
    monkeypatch.setattr(data, "load_factor_returns", lambda: factors.copy())
    macro = pd.DataFrame(
        {
            "date": dates,
            "vixcls": 20 + np.cumsum(rng.normal(0, 0.1, 420)),
            "yc_slope_10y_2y": np.cumsum(rng.normal(0, 0.01, 420)),
            "bamlh0a0hym2": 4 + np.cumsum(rng.normal(0, 0.02, 420)),
        }
    )
    monkeypatch.setattr(data, "load_macro", lambda: macro.copy())
    for name in ["feature_03", "feature_05", "feature_06"]:
        module = modules[name]
        if hasattr(module, "load_factor_returns"):
            monkeypatch.setattr(module, "load_factor_returns", lambda: factors.copy())
        if hasattr(module, "load_macro"):
            monkeypatch.setattr(module, "load_macro", lambda: macro.copy())
    return returns, raw


def payload_for(fid, returns):
    payload = {"tickers": ["SPY", "QQQ", "IWM"], "lookback_days": 400}
    if fid == "01":
        payload["frontier_points"] = 3
    if fid == "02":
        payload.update(walk_forward_window=100, rebalance_days=50)
    if fid == "03":
        payload["bootstrap_draws"] = 30
    if fid == "04":
        payload["monte_carlo_paths"] = 100
    if fid == "06":
        payload.update(regime_count=2, regime_min_train=60, regime_refit_interval=100)
    if fid == "09":
        payload.update(max_horizon=3, bootstrap_draws=20)
    if fid == "11":
        payload.update(
            target_weights={"SPY": 0.5, "QQQ": 0.3, "IWM": 0.2}, portfolio_nav=1000000
        )
    if fid == "12":
        payload.update(
            peer_portfolios={"peer1": {"SPY": 0.5, "QQQ": 0.3, "IWM": 0.2}},
            peer_navs={"peer1": 2000000},
            market_depth_coefficient=0.01,
        )
    if fid == "13":
        strategy = (
            returns[["SPY", "QQQ", "IWM"]]
            .rename(
                columns={"SPY": "strategy_a", "QQQ": "strategy_b", "IWM": "strategy_c"}
            )
            .reset_index()
            .rename(columns={"index": "date"})
        )
        strategy.date = strategy.date.dt.strftime("%Y-%m-%d")
        payload = {
            "strategy_returns": strategy.to_dict("records"),
            "lookback_days": 400,
            "training_window": 100,
            "rebalance_days": 50,
        }
    return payload


@pytest.mark.parametrize("fid", [f"{i:02}" for i in range(1, 14)])
def test_every_feature_returns_declared_outputs(fid, observed_data):
    returns, _ = observed_data
    result = run_feature(fid, payload_for(fid, returns))
    contract = contract_for(fid)
    assert result["feature_id"] == f"feature_{fid}"
    assert result["status"] in {"ok", "warning"}
    json.dumps(result, allow_nan=False)
    assert set(result["output_status"]) == {d["key"] for d in contract["outputs"]}
    declared = {(d["source"], d["key"]) for d in contract["outputs"]}
    for source in ["charts", "tables"]:
        assert all((source, key) in declared for key in result[source])
    for item in contract["outputs"]:
        state = result["output_status"][item["key"]]
        if state["status"] == "not_produced":
            assert state["reason"]


def test_real_strategy_and_peer_data_required(observed_data):
    peers = run_feature("12", {"tickers": ["SPY", "QQQ", "IWM"]})
    assert "peer_data_requirement" in peers["tables"]
    strategies = run_feature("13", {})
    assert "strategy_data_requirement" in strategies["tables"]
    assert not strategies["charts"]


def test_benchmark_is_honored_and_constituents_not_invented(observed_data):
    result = run_feature(
        "03",
        {"tickers": ["SPY", "QQQ", "IWM"], "benchmark": "AGG", "bootstrap_draws": 20},
    )
    assert result["meta"]["benchmark"] == "AGG"
    assert result["tables"]["brinson_table"] == []
    assert result["tables"]["factor_attribution"]


def test_judgment_taxonomy_requires_actual_scores(observed_data):
    with pytest.raises(ValueError, match="actual signal_scores"):
        run_feature(
            "09", {"tickers": ["SPY", "QQQ", "IWM"], "factor_taxonomy": "judgment"}
        )


def test_nav_alias_changes_dollar_positions(observed_data):
    first = run_feature("07", {"tickers": ["SPY", "QQQ", "IWM"], "aum": 1000000})
    second = run_feature(
        "07", {"tickers": ["SPY", "QQQ", "IWM"], "portfolio_nav": 10000000}
    )
    assert second["tables"]["liquidity_table"][0]["position_dollars"] == pytest.approx(
        first["tables"]["liquidity_table"][0]["position_dollars"] * 10
    )


def test_execution_requires_target_weights(observed_data):
    with pytest.raises(ValueError, match="target_weights"):
        run_feature("11", {"tickers": ["SPY", "QQQ", "IWM"]})


def test_amihud_adv_and_dtl_golden_fixture(observed_data):
    from app.services.portfolio_v2.core.liquidity import liquidity_table

    _, raw = observed_data
    g = raw.loc[raw.Ticker.eq("SPY")].tail(100)
    rows = liquidity_table(["SPY"], 100, 1000000, pd.Series({"SPY": 0.5}), 60, 0.2)
    dv = g.Close * g.Volume
    expected = (g.Close / g.Open - 1).abs() / dv
    assert rows[0]["amihud"] == pytest.approx(expected.mean())
    assert rows[0]["recency_weighted_amihud"] == pytest.approx(
        np.average(expected, weights=np.arange(1, 101))
    )
    assert rows[0]["adv_dollars"] == pytest.approx(dv.tail(60).mean())
    assert rows[0]["days_to_liquidate"] == pytest.approx(
        500000 / (0.2 * dv.tail(60).mean())
    )


def test_manual_backtest_is_one_evaluated_trial(observed_data):
    result = run_feature(
        "02",
        {
            "tickers": ["SPY", "QQQ", "IWM"],
            "weights": {"SPY": 0.5, "QQQ": 0.3, "IWM": 0.2},
            "walk_forward_window": 100,
        },
    )
    row = result["tables"]["psr_dsr"][0]
    assert row["trials"] == row["evaluated_variants"] == 1
    assert row["pbo"] is None


@pytest.mark.skipif(
    __import__("os").environ.get("PORTFOLIO_V2_REAL_DATA") != "1",
    reason="Opt-in local repository-data integration check",
)
@pytest.mark.parametrize("fid", [f"{i:02}" for i in range(1, 14)])
def test_real_repository_feature_smoke(fid):
    from app.services.portfolio_v2.core.data_loader import returns_matrix, request_scope

    with request_scope({"as_of_date": "2026-01-28"}):
        observed = returns_matrix(["SPY", "QQQ", "IWM"], 420).dropna()
    observed.index.name = None
    payload = payload_for(fid, observed)
    payload["as_of_date"] = "2026-01-28"
    result = run_feature(fid, payload)
    json.dumps(result, allow_nan=False)
    assert result["status"] in {"ok", "warning"}
    assert any(row["status"] == "produced" for row in result["output_status"].values())
    assert set(result["output_status"]) == {
        item["key"] for item in contract_for(fid)["outputs"]
    }


def test_historical_current_sector_caps_refused(observed_data):
    with pytest.raises(ValueError, match="point-in-time sector"):
        run_feature(
            "01",
            {
                "tickers": ["SPY", "QQQ", "IWM"],
                "sector_max_weights": {"a": 0.4},
                "as_of_date": "2021-08-01",
            },
        )
