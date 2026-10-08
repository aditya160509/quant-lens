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


def test_api_errors_symbols_and_upload(prices):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.volatility_v2 import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.post('/labs/volatility/v2/feature/99/run', json={}).status_code == 404
        assert client.post('/labs/volatility/v2/feature/01/run', json={'assets': ['UNKNOWN']}).status_code == 422
        assert client.post('/labs/volatility/v2/feature/01/run', json={'payload': [], 'assets': ['SPY']}).status_code == 422
        assert client.get('/labs/volatility/v2/symbols?q=SP').json()['symbols'] == [{'symbol': 'SPY'}]
        assert client.post('/labs/volatility/v2/uploads?kind=implied_volatility', files={'file': ('bad.csv', b'bad')}).status_code == 422
        assert client.get('/labs/volatility/v2/jobs/missing').status_code == 404
        assert client.post('/labs/volatility/v2/jobs/missing/cancel').status_code == 404


def test_api_jobs_persist_real_results_and_detect_changed_upload(prices, tmp_path, monkeypatch):
    from app.api import volatility_v2 as api
    from app.services.studio.jobs import JobStore
    from app.services.volatility_v2.core import uploads
    store = JobStore(path=tmp_path / 'jobs.json')
    monkeypatch.setattr(api, 'JOBS', store)
    monkeypatch.setattr(api, 'RESULTS', tmp_path / 'results')
    monkeypatch.setattr(uploads, 'upload_directory', lambda: tmp_path / 'uploads')
    raw = b'date,asset,implied_vol,maturity_days,source\n2024-01-01,SPY,0.2,30,observed\n'
    identifier = uploads.save_upload(raw, 'implied_volatility')['upload_id']
    submitted = []
    submit = store.submit
    def capture(*args, **kwargs):
        future = submit(*args, **kwargs)
        submitted.append(future)
        return future
    monkeypatch.setattr(store, 'submit', capture)
    response = api.create_job('01', {'assets': ['SPY'], 'lookback_days': 40})
    submitted[0].result(timeout=30)
    result = api.status(response['job_id'])
    assert result['status'] == 'completed', result['error']
    assert result['result']['feature_id'] == 'feature_01'
    assert JobStore(path=store.path).get(response['job_id'])['status'] == 'completed'
    payload = {'assets': ['SPY'], 'iv_upload_id': identifier}
    job = store.create(job_type='test', params={'source_versions': api.sources(payload)})
    path = uploads.upload_path(identifier)
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='changed after'):
        api._execute(job['job_id'], '01', payload)


def test_nonfinite_prices_and_null_explicit_universe_fail(prices):
    from app.services.volatility_v2.registry import prepare_payload
    dl, frame, path = prices
    frame.loc[0, "High"] = float("inf")
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="finite"):
        dl.ohlcv_for_symbols(["SPY"])
    with pytest.raises(ValueError, match="cannot be null"):
        prepare_payload("01", {"assets": None})


def test_exports_cancel_and_source_changes_during_estimation(prices, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import volatility_v2 as api
    from app.services.studio.jobs import JobStore
    dl, frame, path = prices
    store = JobStore(path=tmp_path / 'jobs.json')
    monkeypatch.setattr(api, 'JOBS', store)
    monkeypatch.setattr(api, 'RESULTS', tmp_path / 'results')
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        exported = client.post('/labs/volatility/v2/export/01', json={'assets': ['SPY']})
        assert exported.status_code == 200
        body = exported.json()
        assert body['json']['feature_id'] == 'feature_01'
        assert 'estimator' in body['csv_tables']['estimator_efficiency']
        assert client.post('/labs/volatility/v2/export/99', json={}).status_code == 404
        assert client.post('/labs/volatility/v2/export/01', json={'assets': ['UNKNOWN']}).status_code == 422
        job = store.create(job_type='test', params={'source_versions': api.sources({})})
        cancelled = client.post(f"/labs/volatility/v2/jobs/{job['job_id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()['status'] == 'cancelled'
        assert 'result' not in client.get(f"/labs/volatility/v2/jobs/{job['job_id']}").json()
    original = api.run_feature
    def changing_source(fid, payload):
        result = original(fid, payload)
        frame.loc[0, 'Close'] = 101.5
        frame.to_parquet(path)
        return result
    monkeypatch.setattr(api, 'run_feature', changing_source)
    job = store.create(job_type='test', params={'source_versions': api.sources({})})
    with pytest.raises(ValueError, match='changed during'):
        api._execute(job['job_id'], '01', {'assets': ['SPY']})
    assert not (api.RESULTS / f"{job['job_id']}.json").exists()


def test_duplicate_exposure_and_object_keys_fail(prices):
    from app.services.volatility_v2.core.analytics import parse_weights
    from app.services.volatility_v2.registry import prepare_payload
    for raw in [{'SPY': 1, 'spy': 2}, 'SPY:1,SPY:2', '{"SPY":1,"SPY":2}']:
        with pytest.raises(ValueError):
            parse_weights({'weights': raw}, ['SPY'])
    with pytest.raises(ValueError, match='Duplicate'):
        prepare_payload('09', {'weights': '{"SPY":1,"SPY":2}'})
