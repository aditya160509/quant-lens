"""Strict data and mounted API contract checks."""
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.pca_v2.core import data_loader as d
from app.services.pca_v2.core import uploads
from app.api import pca_v2 as api


def test_unknown_and_partial_universe_rejected(monkeypatch):
    monkeypatch.setattr(d,"available_symbols",lambda limit=None:["A","B","C"])
    for symbols in (["UNKNOWN"],["A","UNKNOWN"]):
        with pytest.raises(d.UnknownSymbolsError,match="UNKNOWN"):
            d.parse_symbols({"symbols":symbols})


def test_missing_prices_never_generate_zero_returns():
    prices=pd.DataFrame({"A":[10.,11.,None,13.,14.],"B":[20.,21.,22.,23.,24.]})
    returns=d.complete_returns(prices,10)
    assert list(returns.index)==[1,4]
    assert not returns.eq(0).any().any()
    assert returns.attrs["rows_dropped_missing"]==2


def test_upload_sandbox_and_duplicate_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(uploads,"UPLOAD_DIR",tmp_path)
    with pytest.raises(ValueError,match="Invalid"):
        uploads.read_upload("../weights_any.csv","weights")
    with pytest.raises(ValueError,match="Duplicate"):
        uploads.save_upload(b"ticker,weight\nA,0.5\nA,0.5\n","weights")
    saved=uploads.save_upload(b"ticker,weight\nA,0.5\nB,0.5\n","weights")
    assert len(uploads.read_upload(saved["upload_id"],"weights"))==2


def test_api_404_422_and_manifest(monkeypatch):
    monkeypatch.setattr(d,"available_symbols",lambda limit=None:["A","B","C"])
    app=FastAPI();app.include_router(api.router,prefix="/api")
    client=TestClient(app)
    assert client.post("/api/labs/pca/v2/feature/99/run",json={"payload":{}}).status_code==404
    response=client.post("/api/labs/pca/v2/feature/01/run",json={"payload":{"symbols":"UNKNOWN"}})
    assert response.status_code==422 and "UNKNOWN" in response.text
    manifest=client.get("/api/labs/pca/v2/features").json()["features"]
    assert len(manifest)==11
    assert all(f["inputs"] and f["outputs"] for f in manifest)
    assert client.get("/api/labs/pca/v2/jobs/unknown").status_code==404


def test_jobs_complete_and_cancel_suppresses_result(tmp_path,monkeypatch):
    import threading
    from app.services.studio.jobs import JobStore
    store=JobStore(tmp_path/"jobs.json")
    monkeypatch.setattr(api,"JOBS",store)
    monkeypatch.setattr(api,"RESULTS_DIR",tmp_path/"results")
    monkeypatch.setattr(api,"parse_symbols",lambda payload:["A","B","C"])
    monkeypatch.setattr(api,"run_feature",lambda feature,payload:{"status":"ok","charts":{},"tables":{}})
    job=api.create_job("01",{"payload":{}})
    # Deterministic bounded wait on the job's actual future, no timing assumptions.
    future=store._futures.get(job["job_id"])
    if future:
        future.result(timeout=5)
    result=api.job_status(job["job_id"])
    assert result["status"]=="completed" and result["result"]["status"]=="ok"
    started=threading.Event();release=threading.Event()
    def blocked():
        started.set();release.wait(timeout=5);return {"secret":"never published"}
    cancellation=store.create(job_type="pca_test",params={})
    future=store.submit(cancellation["job_id"],blocked)
    assert started.wait(timeout=5)
    store.cancel(cancellation["job_id"]);release.set();future.result(timeout=5)
    cancelled=api.job_status(cancellation["job_id"])
    assert cancelled["status"]=="cancelled" and "result" not in cancelled
    store.shutdown()


def test_asof_price_matrix_is_unchanged_by_future_prices(monkeypatch):
    import numpy as np
    dates=pd.date_range("2020-01-01",periods=100,freq="B")
    frame=pd.DataFrame([{"Date":date,"Ticker":ticker,"Close":10+index+i} for index,date in enumerate(dates) for i,ticker in enumerate("ABC")])
    monkeypatch.setattr(d,"load_market_ohlcv",lambda:frame)
    first=d.returns_matrix(list("ABC"),60,end_date=str(dates[70].date()))
    frame.loc[frame.Date>dates[70],"Close"]*=100
    second=d.returns_matrix(list("ABC"),60,end_date=str(dates[70].date()))
    pd.testing.assert_frame_equal(first,second)
    assert first.index.max()==dates[70]
