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
