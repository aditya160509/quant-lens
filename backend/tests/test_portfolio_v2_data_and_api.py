"""Strict tickers, typed contracts, sandbox uploads, exports and durable job transport."""

import sys
import time
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.portfolio_v2.registry import prepare_payload, feature_manifest
from app.services.portfolio_v2.core.data_loader import (
    parse_symbols,
    UnknownSymbolsError,
    returns_matrix,
)
from test_portfolio_v2_features import observed_data as _observed_data

observed_data = _observed_data


@pytest.fixture
def client(observed_data, tmp_path, monkeypatch):
    from app.api import portfolio_v2 as api
    from app.services.studio.jobs import JobStore
    from app.services.portfolio_v2.core import uploads

    monkeypatch.setattr(api, "JOBS", JobStore(tmp_path / "jobs.json"))
    monkeypatch.setattr(api, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(uploads, "ROOT", tmp_path / "uploads")
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    with TestClient(app) as c:
        yield c


def test_unknown_and_fake_index_universes_rejected(observed_data):
    with pytest.raises(UnknownSymbolsError, match="UNKNOWN"):
        parse_symbols({"tickers": ["SPY", "UNKNOWN"]})
    with pytest.raises(ValueError, match="Named index"):
        parse_symbols({"universe": "sp500"})


def test_missing_prices_remain_missing(observed_data, monkeypatch):
    from app.services.portfolio_v2.core import data_loader as data

    _, raw = observed_data
    date = raw.Date.sort_values().unique()[100]
    sparse = raw.loc[~(raw.Ticker.eq("SPY") & raw.Date.eq(date))]
    monkeypatch.setattr(
        data,
        "_selected_ohlcv",
        lambda symbols, frequency, version: sparse.loc[
            sparse.Ticker.isin(symbols)
        ].copy(),
    )
    result = returns_matrix(["SPY", "QQQ"], 420)
    assert pd.isna(result.loc[date, "SPY"])
    assert result.SPY.isna().sum() >= 2


def test_complete_manifest_and_alias_conflicts():
    contracts = feature_manifest()
    assert len(contracts) == 13
    assert [c["spec_id"] for c in contracts[-3:]] == [12, 13, 15]
    for c in contracts:
        assert all(
            {"key", "label", "type", "group", "default", "help", "options"} <= set(d)
            for d in c["inputs"]
        )
        assert all(
            {"key", "source", "render_hint", "primary"} <= set(d) for d in c["outputs"]
        )
    with pytest.raises(ValueError, match="Conflicting"):
        prepare_payload("07", {"aum": 1, "portfolio_nav": 2})
    with pytest.raises(ValueError, match="Unknown objective"):
        prepare_payload("01", {"objective": "min_variance"})
    with pytest.raises(ValueError, match="Unsupported"):
        prepare_payload("01", {"imaginary_control": 2})


def test_api_errors_and_symbol_search(client):
    prefix = "/api/labs/portfolio/v2"
    assert client.get(prefix + "/features").status_code == 200
    assert client.get(prefix + "/symbols?q=SP").json()["symbols"] == [{"symbol": "SPY"}]
    assert client.post(prefix + "/feature/99/run", json={}).status_code == 404
    assert (
        client.post(
            prefix + "/feature/07/run", json={"payload": {"tickers": ["UNKNOWN"]}}
        ).status_code
        == 422
    )
    assert (
        client.post(
            prefix + "/feature/07/run", json={"payload": {}, "other": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            prefix + "/feature/07/run", json={"participation_rate": 0}
        ).status_code
        == 422
    )


def test_upload_sandbox_and_validation(client):
    prefix = "/api/labs/portfolio/v2"
    valid = b"date,a,b\n2020-01-01,0.01,-0.01\n2020-01-02,0.02,0.01\n"
    result = client.post(
        prefix + "/uploads?kind=strategy_returns",
        files={"file": ("../../escape.csv", valid, "text/csv")},
    )
    assert result.status_code == 200
    from app.services.portfolio_v2.core.uploads import upload_path

    assert upload_path(result.json()["upload_id"]).is_file()
    with pytest.raises(ValueError):
        upload_path("../../escape")
    assert (
        client.post(
            prefix + "/uploads?kind=strategy_returns",
            files={"file": ("bad.csv", b"date,a\n2020-01-01,NaN\n", "text/csv")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            prefix + "/uploads?kind=strategy_returns",
            files={"file": ("big.csv", b"a" * (2 * 1024 * 1024 + 1), "text/csv")},
        ).status_code
        == 413
    )


def test_export_and_background_job(client):
    prefix = "/api/labs/portfolio/v2"
    body = {"payload": {"tickers": ["SPY", "QQQ", "IWM"], "aum": 1000000}}
    exported = client.post(prefix + "/export/07", json=body)
    assert exported.status_code == 200
    assert "liquidity_table" in exported.json()["csv_tables"]
    assert "liquidity_table" in exported.json()["latex_tables"]
    queued = client.post(prefix + "/feature/07/jobs", json=body)
    assert queued.status_code == 200
    jid = queued.json()["job_id"]
    for _ in range(100):
        result = client.get(prefix + "/jobs/" + jid).json()
        if result["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    assert result["status"] == "completed", result
    assert result["result"]["feature_id"] == "feature_07"
    assert client.get(prefix + "/jobs/missing").status_code == 404
    assert client.post(prefix + "/jobs/missing/cancel").status_code == 404


def test_registry_import_is_lazy():
    import subprocess

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.services.portfolio_v2.registry; assert not any(k.startswith('app.services.portfolio_v2.features.feature_') for k in sys.modules)",
        ],
        check=True,
    )


def test_nested_nonfinite_controls_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        prepare_payload("11", {"temporary_impact_coefficient": {"SPY": float("nan")}})


def test_daily_liquidity_contract_rejects_monthly_impact_units():
    with pytest.raises(ValueError, match="frequency"):
        prepare_payload("11", {"frequency": "monthly"})


def test_required_primary_source_never_replaced(monkeypatch, tmp_path):
    from app.services.portfolio_v2.core import data_loader as data

    monkeypatch.setattr(data, "MARKET_UNIVERSE", tmp_path / "absent.parquet")
    with pytest.raises(ValueError, match="Required observed market source"):
        data._symbol_counts((("missing_source_test", 1, 1),), "daily", True)
