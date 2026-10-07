import time
import json
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from factors_v2_fixtures import factors_data


def client_for(data, tmp_path, monkeypatch):
    from app.api import factors_v2 as api
    from app.services.studio.jobs import JobStore

    monkeypatch.setattr(api, "JOBS", JobStore(tmp_path / "jobs.json"))
    monkeypatch.setattr(api, "RESULTS", tmp_path / "results")
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    return TestClient(app), api


def test_strict_symbols_and_missing_returns(factors_data):
    from app.services.factors_v2.core.data_loader import (
        parse_symbols,
        load_market_return_matrix,
        request_scope,
    )

    with pytest.raises(ValueError, match="UNKNOWN"):
        parse_symbols(["SPY", "UNKNOWN"])
    with request_scope({"tickers": factors_data["symbols"]}):
        result = load_market_return_matrix(31)
    assert pd.isna(result["returns"][0]).all()
    with request_scope(
        {
            "as_of_date": str(factors_data["dates"][100].date()),
            "tickers": factors_data["symbols"],
        }
    ):
        assert (
            pd.Timestamp(load_market_return_matrix(31)["dates"][-1])
            <= factors_data["dates"][100]
        )


def test_api_envelope_errors_and_input_roundtrip(factors_data, tmp_path, monkeypatch):
    client, _ = client_for(factors_data, tmp_path, monkeypatch)
    assert (
        client.post(
            "/api/labs/factors/v2/feature/99/run", json={"payload": {}}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/labs/factors/v2/feature/08/run", json={"window_days": 100}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/labs/factors/v2/feature/08/run",
            json={"payload": {"tickers": ["UNKNOWN"]}},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/labs/factors/v2/feature/08/run",
            json={"payload": {"method": "dcc_garch"}},
        ).status_code
        == 422
    )
    r = client.post(
        "/api/labs/factors/v2/feature/08/run",
        json={"payload": {"window_days": 100, "method": "ewma", "half_life": 17}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["meta"]["payload"]["half_life"] == 17
    assert r.json()["meta"]["method"] == "ewma"


def test_upload_sandbox_and_jobs(factors_data, tmp_path, monkeypatch):
    client, api = client_for(factors_data, tmp_path, monkeypatch)
    from app.services.factors_v2.core import uploads

    monkeypatch.setattr(uploads, "UPLOADS", tmp_path / "uploads")
    r = client.post(
        "/api/labs/factors/v2/uploads?kind=holdings",
        files={"file": ("holdings.csv", b"ticker,weight\nSPY,1\n", "text/csv")},
    )
    assert r.status_code == 200
    identifier = r.json()["upload_id"]
    assert "/" not in identifier
    assert (
        client.post(
            "/api/labs/factors/v2/feature/02/run",
            json={"payload": {"holdings_upload_id": "../secret"}},
        ).status_code
        == 422
    )
    r = client.post(
        "/api/labs/factors/v2/feature/08/jobs", json={"payload": {"window_days": 100}}
    )
    assert r.status_code == 200
    jid = r.json()["job_id"]
    for _ in range(100):
        result = client.get("/api/labs/factors/v2/jobs/" + jid).json()
        if result["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert result["status"] == "completed", result
    json.dumps(result["result"], allow_nan=False)
    assert client.get("/api/labs/factors/v2/jobs/not-found").status_code == 404
    assert client.post("/api/labs/factors/v2/jobs/not-found/cancel").status_code == 404
    assert (
        client.post("/api/labs/factors/v2/alert-subscription", json={}).status_code
        == 422
    )
    api.JOBS.shutdown()


def test_file_refresh_invalidates_prices(factors_data):
    from app.services.factors_v2.core.data_loader import load_market_universe

    first = load_market_universe()
    file = factors_data["backend"] / "market_universe.parquet"
    frame = pd.read_parquet(file)
    frame.loc[0, "Close"] = 12345.0
    frame.to_parquet(file, index=False)
    refreshed = load_market_universe()
    assert not refreshed.Close.equals(first.Close)


def test_alert_idempotency_and_recovery(factors_data):
    from app.services.factors_v2.core.alerts import record

    row = {"factor": "momentum_12_1", "ic_z_score": -2}
    payload = {"as_of_date": "2023-01-01", "ic_drift_threshold": -1.5}
    first = record(payload, [row], [row])
    assert len(first) == 1 and first[0]["state"] == "triggered"
    assert record(payload, [row], [row]) == first
    recovered = record(
        {**payload, "as_of_date": "2023-01-02"}, [{**row, "ic_z_score": 0}], []
    )
    assert len(recovered) == 2 and recovered[0]["state"] == "recovered"
    assert record(payload, [row], [row]) == recovered


def test_export_produces_csv_and_bad_batch_inputs_are_rejected(
    factors_data, tmp_path, monkeypatch
):
    client, _ = client_for(factors_data, tmp_path, monkeypatch)
    response = client.post(
        "/api/labs/factors/v2/export/08", json={"payload": {"window_days": 100}}
    )
    assert response.status_code == 200
    assert response.json()["csv_tables"]["volatility"].startswith(
        "factor,annualized_vol"
    )
    assert (
        client.post(
            "/api/labs/factors/v2/run-all",
            json={"payload": {"window_days": 100}, "feature_payloads": {"08": {}}},
        ).status_code
        == 422
    )
