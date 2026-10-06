"""Regression checks for ML V2 data integrity."""
import numpy as np
import pandas as pd
import pytest
from app.services.ml_v2.core import data_loader as loader

@pytest.fixture
def quotes(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=40)
    rows = [{"Ticker": ticker, "Date": date, "Close": 100 + i, "Volume": 1000}
            for ticker in ["AAA", "BBB"] for i, date in enumerate(dates)
            if not (ticker == "AAA" and i == 25)]
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(loader, "load_market_ohlcv", lambda *a, **k: frame)
    monkeypatch.setattr(loader, "available_symbols", lambda **kwargs: ["AAA", "BBB"])
    return dates

def test_unknown_symbols_are_not_substituted(quotes):
    with pytest.raises(ValueError, match="MISSING"):
        loader.parse_symbols({"symbols": ["AAA", "MISSING"]})

def test_single_symbol_is_not_padded(quotes):
    assert loader.parse_symbols({"symbols": ["AAA"], "max_symbols": 1}) == ["AAA"]

def test_sp500_requires_membership(quotes):
    with pytest.raises(ValueError, match="membership"):
        loader.parse_symbols({"universe": "sp500"})

def test_missing_quotes_and_returns_remain_missing(quotes):
    closes = loader.close_matrix(["AAA", "BBB"], 40)
    returns = loader.returns_matrix(["AAA", "BBB"], 40)
    assert np.isnan(closes.loc[quotes[25], "AAA"])
    assert np.isnan(returns.loc[quotes[25], "AAA"])
    assert np.isnan(returns.loc[quotes[26], "AAA"])

def test_as_of_excludes_future_quotes(quotes):
    token = loader.AS_OF_DATE.set(quotes[20])
    try:
        closes = loader.close_matrix(["AAA", "BBB"], 40)
        assert closes.index.max() == quotes[20]
    finally:
        loader.AS_OF_DATE.reset(token)

@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import ml_v2 as api
    from app.services.studio.jobs import JobStore
    store = JobStore(path=tmp_path / "jobs.json")
    monkeypatch.setattr(api, "JOBS", store)
    monkeypatch.setattr(api, "ROOT", tmp_path)
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    with TestClient(app) as client:
        yield client
    store.shutdown()

def test_api_maps_unknown_symbols_to_422(client, monkeypatch):
    from app.api import ml_v2 as api
    def reject(*args):
        raise ValueError("Unknown ML V2 symbols: MISSING")
    monkeypatch.setattr(api, "run_feature", reject)
    response = client.post("/api/ml/v2/features/01/run", json={"symbols": ["MISSING"]})
    assert response.status_code == 422
    assert "MISSING" in response.json()["detail"]

def test_universe_upload_is_sandboxed(client, quotes, tmp_path):
    response = client.post("/api/ml/v2/uploads?kind=universe", files={"file": ("../../escape.csv", b"ticker\nAAA\n", "text/csv")})
    assert response.status_code == 200
    identifier = response.json()["upload_id"]
    assert (tmp_path / "uploads" / f"{identifier}.json").is_file()
    assert response.json()["symbols"] == ["AAA"]

def test_unknown_job_is_404(client):
    assert client.get("/api/ml/v2/jobs/missing").status_code == 404
    assert client.post("/api/ml/v2/jobs/missing/cancel").status_code == 404


def test_job_rejects_unsupported_feature_options_before_enqueue(client, quotes):
    response = client.post("/api/ml/v2/features/01/jobs",json={"symbols":["AAA"],"model_type":"fake_model"})
    assert response.status_code == 422


def test_job_persists_and_returns_completed_artifact(client, quotes, monkeypatch):
    import time
    from app.api import ml_v2 as api
    monkeypatch.setattr(api,"run_feature",lambda *args: {"status":"ok","summary_cards":[],"charts":{},"tables":{}})
    response = client.post("/api/ml/v2/features/01/jobs",json={"symbols":["AAA"]})
    assert response.status_code == 200
    identifier = response.json()["job_id"]
    deadline = time.monotonic()+5
    while time.monotonic()<deadline:
        result = client.get(f"/api/ml/v2/jobs/{identifier}").json()
        if result["status"] in {"completed","failed"}:
            break
        time.sleep(.02)
    assert result["status"] == "completed"
    assert result["result"]["status"] == "ok"
