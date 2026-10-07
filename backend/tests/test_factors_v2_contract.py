import json
import pandas as pd
import numpy as np
import pytest
from factors_v2_fixtures import factors_data


def test_manifest_is_complete_and_unsupported_options_rejected():
    from app.services.factors_v2.registry import feature_manifest
    from app.services.factors_v2.features.inputs import validate

    manifest = feature_manifest()
    assert len(manifest) == 14
    for f in manifest:
        for item in f["inputs"]:
            assert {"key", "label", "type", "default", "group", "help"} <= set(item)
        for item in f["outputs"]:
            assert {"key", "source", "render", "primary", "label"} <= set(item)
    with pytest.raises(ValueError, match="Unsupported"):
        validate("10", {"cardinality": 3})
    with pytest.raises(ValueError):
        validate("08", {"dcc_a": 0.1, "dcc_b": 0.95})


def test_future_data_does_not_change_past_scores(factors_data):
    from app.services.factors_v2.core.panel import characteristic_panel

    date = factors_data["dates"][300]
    payload = {
        "as_of_date": str(date.date()),
        "tickers": factors_data["symbols"],
        "max_tickers": 40,
        "instrument_metadata": factors_data["metadata"],
    }
    before = characteristic_panel(payload).set_index("Ticker")
    p = factors_data["backend"] / "market_universe.parquet"
    frame = pd.read_parquet(p)
    frame.loc[frame.Date > date, "Close"] *= 100
    frame.loc[frame.Date > date, "Volume"] *= 1e5
    frame.to_parquet(p, index=False)
    f = factors_data["backend"] / "fundamentals/master_fundamentals.parquet"
    frame = pd.read_parquet(f)
    future = frame.iloc[[0]].copy()
    future.reportDate = date + pd.Timedelta(days=1)
    future["Net Income"] = 1e100
    frame = pd.concat([frame, future])
    frame.to_parquet(f, index=False)
    after = characteristic_panel(payload).set_index("Ticker")
    pd.testing.assert_frame_equal(before, after)


def test_statement_lag_and_snapshot_ratios_ignored(factors_data):
    from app.services.factors_v2.core.panel import characteristic_panel

    payload = {
        "as_of_date": "2022-03-01",
        "tickers": ["SPY"],
        "instrument_metadata": factors_data["metadata"],
    }
    result = characteristic_panel(payload)
    assert result.statement_date.iloc[0] == pd.Timestamp("2021-01-01")
    assert result.value_pb.iloc[0] != pytest.approx(1 / 99)


def test_fx_exact_date_and_missing_quote_metadata(factors_data):
    from app.services.factors_v2.core.panel import usd_prices

    d = factors_data["dates"][:3]
    close = pd.DataFrame({"A": [150, 300, 450]}, index=d)
    usd = usd_prices(close, {"A": {"quote_currency": "JPY"}})
    np.testing.assert_allclose(usd.A, [1, 2, 3])
    assert usd_prices(close, {}).A.isna().all()
    p = factors_data["backend"] / "canonical/fx_daily.parquet"
    frame = pd.read_parquet(p)
    frame = frame.loc[frame.Date != d[1]]
    frame.to_parquet(p, index=False)
    assert pd.isna(usd_prices(close, {"A": {"quote_currency": "JPY"}}).A.iloc[1])


def test_momentum_uses_observed_skip_month_endpoints(factors_data):
    from app.services.factors_v2.core.panel import characteristic_panel

    payload = {
        "tickers": ["SPY"],
        "as_of_date": str(factors_data["dates"][-1].date()),
        "instrument_metadata": factors_data["metadata"],
    }
    row = characteristic_panel(payload).iloc[0]
    prices = (
        factors_data["prices"]
        .loc[factors_data["prices"].Ticker.eq("SPY")]
        .sort_values("Date")
        .Close
    )
    assert row.momentum_12_1 == pytest.approx(prices.iloc[-22] / prices.iloc[-253] - 1)
