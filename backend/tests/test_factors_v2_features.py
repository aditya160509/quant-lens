import json
import pytest
from factors_v2_fixtures import factors_data


@pytest.mark.parametrize("fid", [f"{i:02}" for i in range(1, 15)])
def test_each_supported_feature_executes_and_returns_contract(fid, factors_data):
    from app.services.factors_v2.registry import run_feature
    from app.services.factors_v2.features.inputs import outputs

    payload = {
        "tickers": factors_data["symbols"],
        "max_tickers": 40,
        "instrument_metadata": factors_data["metadata"],
        "window_days": 360,
        "factor": "momentum_12_1",
    }
    if fid == "02":
        payload.update(holdings=[{"ticker": "SPY", "weight": 1}])
    if fid == "03":
        payload.update(factor_exposures={"HML": 0.4, "Mom": 0.6})
    if fid == "05":
        payload.update(horizons=[1, 5, 21], bootstrap_samples=20)
    if fid == "07":
        payload.update(mc_simulations=10)
    if fid == "11":
        payload.update(var_bootstrap_samples=20, var_lags=1)
    if fid == "14":
        payload.update(
            include_sections=["Current Factor Exposures"],
            feature_payloads={"02": {"holdings": [{"ticker": "SPY", "weight": 1}]}},
        )
    from app.services.factors_v2.features.inputs import inputs

    allowed = {s["key"] for s in inputs(fid)}
    out = run_feature(fid, {k: v for k, v in payload.items() if k in allowed})
    assert out["status"] == "ok", out.get("meta")
    json.dumps(out, allow_nan=False)
    for spec in outputs(fid):
        assert spec["key"] in out[spec["source"]]


def test_stock_exposure_matches_usd_excess_return_ols(factors_data):
    import pandas as pd
    import statsmodels.api as sm
    from app.services.factors_v2.registry import run_feature
    from app.services.factors_v2.core.data_loader import load_factor_returns

    payload = {
        "tickers": ["SPY"],
        "holdings": [{"ticker": "SPY", "weight": 1}],
        "instrument_metadata": factors_data["metadata"],
        "estimation_days": 252,
    }
    out = run_feature("02", payload)
    quotes = (
        factors_data["prices"]
        .loc[factors_data["prices"].Ticker.eq("SPY")]
        .set_index("Date")
        .Close.sort_index()
    )
    ff = load_factor_returns("ff5_mom")
    excess = quotes.pct_change(fill_method=None).tail(252) - ff.RF.reindex(
        quotes.index[-252:]
    )
    joined = pd.concat([excess.rename("y"), ff.drop(columns="RF")], axis=1).dropna()
    fit = sm.OLS(joined.y, sm.add_constant(joined.drop(columns="y"))).fit()
    row = next(r for r in out["tables"]["return_exposures"] if r["factor"] == "HML")
    assert row["return_exposure"] == pytest.approx(fit.params["HML"])
    assert row["standard_error"] == pytest.approx(fit.bse["HML"])
    assert row["ci_low_95"] == pytest.approx(fit.conf_int().loc["HML", 0])
