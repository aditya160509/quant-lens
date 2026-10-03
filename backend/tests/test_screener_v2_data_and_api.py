"""Strict universe and HTTP connection regression checks."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.screener_v2.core import data_loader
from app.api import screener_v2


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
    saved = data_loader.store_universe_upload(b'ticker\nAAPL\nMSFT\n', '../../outside.csv')
    files = list((tmp_path / 'screener_v2' / 'uploads').glob('*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text())['symbols'] == ['AAPL', 'MSFT']
    with pytest.raises(ValueError):
        data_loader.store_universe_upload(b'ticker\nXYZ\n', 'bad.csv')
    assert len(list(files[0].parent.glob('*.json'))) == 1


def test_manifest_constraints_and_indicator_inputs_are_enforced():
    from app.services.screener_v2.registry import get_feature
    from app.services.screener_v2.features.inputs import normalize_payload
    for value in [0, -1, 1.5]:
        with pytest.raises(ValueError):
            normalize_payload(get_feature('05').inputs, {'top_n': value})
    with pytest.raises(ValueError):
        normalize_payload(get_feature('01').inputs, {'periods': {'adx_period': 1}})
