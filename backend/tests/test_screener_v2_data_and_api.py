"""Strict universe and HTTP connection regression checks."""
import polars
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import screener_v2
from app.services.screener_v2.core import data_loader


def test_explicit_universe_rejects_partial_unknowns(monkeypatch):
    monkeypatch.setattr(data_loader, 'available_symbols', lambda: ('AAPL', 'MSFT'))
    with pytest.raises(data_loader.UnknownSymbolsError, match='XYZ'):
        data_loader.parse_symbols({'tickers': 'AAPL XYZ'})
    assert data_loader.parse_symbols({'tickers': 'AAPL AAPL'}) == ['AAPL']
    with pytest.raises(ValueError, match='membership'):
        data_loader.parse_symbols({'universe': 'sp500'})


def test_run_contract_and_errors(monkeypatch):
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    monkeypatch.setattr(screener_v2, 'run_feature', lambda feature, payload: {'feature_id': feature, 'payload': payload})
    result = client.post('/api/screener-v2/run/01', json={'payload': {'tickers': 'AAPL'}})
    assert result.status_code == 200
    assert result.json()['payload'] == {'tickers': 'AAPL'}
    def invalid(*args):
        raise ValueError('Unknown tickers: XYZ')
    monkeypatch.setattr(screener_v2, 'run_feature', invalid)
    assert client.post('/api/screener-v2/run/01', json={'payload': {}}).status_code == 422
    def absent(*args):
        raise KeyError('Unknown feature')
    monkeypatch.setattr(screener_v2, 'run_feature', absent)
    assert client.post('/api/screener-v2/run/99', json={'payload': {}}).status_code == 404


def test_csv_preserves_fields(monkeypatch):
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    monkeypatch.setattr(screener_v2, 'run_feature', lambda feature, payload: payload)
    result = client.post('/api/screener-v2/run/01/csv', files={'file': ('tickers.csv', b'ticker\nAAPL\n', 'text/csv')}, data={'payload': '{"score_min": 80}'})
    assert result.status_code == 200
    assert result.json()['score_min'] == 80
    assert result.json()['tickers'] == ['AAPL']
    assert client.post('/api/screener-v2/run/01/csv', files={'file': ('tickers.csv', b'AAPL')}, data={'payload': '[]'}).status_code == 422


def test_missing_dataset_and_missing_job_result_are_explicit(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    def missing(*args):
        raise FileNotFoundError('Required market dataset is missing')
    monkeypatch.setattr(screener_v2, 'run_feature', missing)
    assert client.post('/api/screener-v2/run/01', json={'payload': {}}).status_code == 503
    monkeypatch.setattr(screener_v2.JOBS, 'get', lambda _: {'job_id': 'x', 'status': 'completed', 'progress': 1, 'error': None, 'result': {'result_file': 'missing.json'}})
    monkeypatch.setattr(screener_v2, 'RESULTS_DIR', tmp_path)
    assert client.get('/api/screener-v2/jobs/x').status_code == 503


def test_upload_is_sandboxed_and_invalid_symbols_do_not_write(monkeypatch, tmp_path):
    import json

    from app.services.screener_v2.core import state
    monkeypatch.setattr(data_loader, 'UPLOADS_DIR', tmp_path / 'screener_v2' / 'uploads')
    monkeypatch.setattr(state, 'STATE_PATH', tmp_path / 'state.sqlite3')
    monkeypatch.setattr(data_loader, 'available_symbols', lambda: ('AAPL', 'MSFT'))
    data_loader.store_universe_upload(b'ticker\nAAPL\nMSFT\n', '../../outside.csv')
    files = list((tmp_path / 'screener_v2' / 'uploads').glob('*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text())['symbols'] == ['AAPL', 'MSFT']
    with pytest.raises(ValueError):
        data_loader.store_universe_upload(b'ticker\nXYZ\n', 'bad.csv')
    assert len(list(files[0].parent.glob('*.json'))) == 1


def test_manifest_constraints_and_indicator_inputs_are_enforced():
    from app.services.screener_v2.features.inputs import normalize_payload
    from app.services.screener_v2.registry import get_feature
    for value in [0, -1, 1.5]:
        with pytest.raises(ValueError):
            normalize_payload(get_feature('05').inputs, {'top_n': value})
    with pytest.raises(ValueError):
        normalize_payload(get_feature('01').inputs, {'periods': {'adx_period': 1}})


def test_market_source_deduplicates_only_identical_quotes_and_discloses_unusable_prices():
    import pandas as pd
    frame = pd.DataFrame({'Ticker': ['AAPL'], 'Date': ['2025-01-01'], 'Close': [100.]})
    result = data_loader._standardize_ohlcv(pd.concat([frame, frame]))
    assert len(result) == 1
    assert result.attrs['source_integrity']['identical_alias_rows_removed'] == 1
    with pytest.raises(ValueError, match='Conflicting'):
        data_loader._standardize_ohlcv(pd.concat([frame, frame.assign(Close=105)]))
    invalid = data_loader._standardize_ohlcv(frame.assign(Close=0))
    assert pd.isna(invalid.Close.iloc[0])
    assert invalid.attrs['source_integrity']['unsupported_nonpositive_or_nonfinite_close_rows'] == 1
    with pytest.raises(ValueError, match='invalid dates'):
        data_loader._standardize_ohlcv(frame.assign(Date='bad'))


def test_equity_inventory_does_not_confuse_reporting_and_trading_currency(monkeypatch):
    import pandas as pd
    monkeypatch.setattr(data_loader, 'load_market_frame', lambda: polars.DataFrame({'Ticker': ['AAA', 'BBB', 'CCC'], 'Close': [10., 20., 30.]}))
    monkeypatch.setattr(data_loader, 'load_fundamentals', lambda: pd.DataFrame({'ticker': ['AAA', 'BBB'], 'currency': ['USD', 'EUR']}))
    data_loader._available_symbols_versioned.cache_clear()
    try:
        assert data_loader._available_symbols_versioned(1, 1) == ('AAA', 'BBB')
    finally:
        data_loader._available_symbols_versioned.cache_clear()


def test_fx_and_macro_observations_respect_as_of_date(monkeypatch, tmp_path):
    import pandas as pd
    fx = tmp_path / 'fx.parquet'
    macro = tmp_path / 'macro.parquet'
    pd.DataFrame({'Ticker': ['USDINR=X'] * 2, 'Date': pd.to_datetime(['2025-01-01', '2025-01-03']),
                  'Close': [85., 86.]}).to_parquet(fx)
    pd.DataFrame({'date': pd.to_datetime(['2025-01-01', '2025-01-03']),
                  'dgs10': [4.1, 4.2]}).to_parquet(macro)
    monkeypatch.setattr(data_loader, 'FX_DAILY', fx)
    monkeypatch.setattr(data_loader, 'CATEGORY7_MACRO', macro)
    data_loader._load_fx_versioned.cache_clear()
    data_loader._load_macro_versioned.cache_clear()
    try:
        with data_loader.as_of_context('2025-01-02'):
            assert data_loader.load_fx().Close.tolist() == [85.]
            assert data_loader.load_macro().dgs10.tolist() == [4.1]
        assert len(data_loader.load_fx()) == len(data_loader.load_macro()) == 2
    finally:
        data_loader._load_fx_versioned.cache_clear()
        data_loader._load_macro_versioned.cache_clear()


def test_invalid_instrument_metadata_is_rejected_before_job_creation(monkeypatch):
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    monkeypatch.setattr(screener_v2, 'parse_symbols', lambda payload: ['AAPL'])
    response = client.post('/api/screener-v2/feature/01/jobs', json={'payload': {'tickers': ['AAPL'], 'instrument_metadata': {'AAPL': {'quoted_units_per_ordinary_share': 0}}}})
    assert response.status_code == 422
    assert 'positive' in response.json()['detail']


def test_lookup_routes_map_errors(monkeypatch):
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    monkeypatch.setattr(screener_v2.lookup, 'lookup', lambda t: {'ticker': t})
    assert client.get('/api/screener-v2/lookup/AAPL').json() == {'ticker': 'AAPL'}
    def absent(t):
        raise KeyError(f'{t} is not in the universe we hold')
    monkeypatch.setattr(screener_v2.lookup, 'lookup', absent)
    assert client.get('/api/screener-v2/lookup/ZZZ').status_code == 404
    assert client.get('/api/screener-v2/lookup/compare?tickers=AAPL').status_code == 422


def test_lookup_compare_adds_sector_and_all_name_medians(monkeypatch):
    import pandas as pd

    from app.services.screener_v2.core import lookup as lk
    frame = pd.DataFrame({'ticker': ['AAA', 'BBB', 'CCC', 'DDD'], 'company_name': ['A', 'B', 'C', 'D'], 'sector': ['Tech', 'Tech', 'Tech', 'Energy'], 'trailing_pe': [10.0, 20.0, 30.0, 5.0]})
    monkeypatch.setattr(lk, 'panel', lambda: frame)
    out = lk.compare(['AAA', 'DDD'])
    meds = {m['label']: (m['n'], m['trailing_pe']) for m in out['medians']}
    assert meds == {'Tech median': (3, 20.0), 'Energy median': (1, 5.0), 'All names median': (4, 15.0)}
    assert [r['ticker'] for r in out['rows']] == ['AAA', 'DDD']


def test_lookup_lenses_apply_fixed_rules_and_sector_fair_value(monkeypatch):
    import pandas as pd

    from app.services.screener_v2.core import lookup as lk
    frame = pd.DataFrame({
        'ticker': ['AAA', 'BBB', 'CCC'], 'company_name': ['A', 'B', 'C'], 'sector': ['Tech', 'Tech', 'Tech'], 'price': [10.0, 20.0, 30.0],
        'roe': [0.2, 0.05, 0.3], 'debt_equity': [0.3, 1.0, 0.2], 'fcf_yield': [0.05, 0.01, 0.02], 'net_margin': [0.15, 0.02, 0.2],
        'trailing_pe': [10.0, 20.0, 30.0], 'pb_ratio': [2.0, 3.0, 4.0], 'ps_ratio': [1.0, 2.0, 3.0],
        'dividend_yield': [0.03, 0.0, 0.01], 'payout_ratio': [0.4, 0.0, 0.8], 'debt_ebitda': [1.0, 2.0, 1.0], 'return_12m': [0.1, -0.2, 0.5],
    })
    monkeypatch.setattr(lk, 'panel', lambda: frame)
    rows = {r['ticker']: r for r in lk.lenses(['AAA', 'CCC'])['rows']}
    assert (rows['AAA']['buffett'], rows['AAA']['graham'], rows['AAA']['dividend']) == (True, True, True)
    assert (rows['CCC']['graham'], rows['CCC']['dividend'], rows['CCC']['momentum']) == (False, False, True)
    # AAA: sector medians P/E 20, P/B 3, P/S 2 against its own 10, 2, 1 price it at 20, 15 and 20.
    assert (rows['AAA']['fair_low'], rows['AAA']['fair_mid'], rows['AAA']['fair_high']) == (15.0, 20.0, 20.0)
    assert rows['AAA']['discount'] == 1.0
