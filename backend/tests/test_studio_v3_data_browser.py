import numpy as np
import pandas as pd
import polars as pl
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import studio_v3 as api
from app.services.studio_v3.core import data_browser


def test_audit_finds_gap_bad_price_jump_stale_and_duplicate():
    d = list(pd.bdate_range("2024-01-01", periods=30))
    close = np.linspace(100, 110, 30)
    close[10] = 0
    close[8] *= 3
    close[24:30] = close[24]
    d = d[:12] + d[22:] + [d[5]]  # 10-day gap, one duplicate date
    close = np.r_[close[:12], close[22:], close[5]]
    a = data_browser.audit(d, close, issues=True)
    assert (a["gaps"], a["bad"], a["dups"], a["jumps"]) == (1, 1, 1, 2) and a["missing"] == 10
    assert {i["kind"] for i in a["issues"]} >= {"gap", "bad_price", "duplicate", "jump", "stale"}
    assert len(data_browser._strip(a["_dates"], a["_dates"][0], a["_dates"][-1])) == data_browser.BUCKETS


def test_routes_filter_and_page(monkeypatch):
    d = pd.bdate_range("2024-01-01", periods=60)
    frame = pl.DataFrame({"Ticker": ["AAA"] * 60 + ["BBB"] * 30, "Date": list(d) + list(d[:15]) + list(d[45:]),
                          "Close": [10.0 + i % 7 * 0.1 for i in range(90)]})
    monkeypatch.setattr(data_browser, "_frame", lambda v: frame)
    data_browser._summary.cache_clear()
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    c = TestClient(app)
    all_ = c.get("/api/studio-v3/data/symbols").json()
    assert all_["total"] == 2 and len(all_["symbols"][0]["strip"]) == data_browser.BUCKETS
    assert [s["symbol"] for s in c.get("/api/studio-v3/data/symbols?flagged=true").json()["symbols"]] == ["BBB"]
    assert c.get("/api/studio-v3/data/symbols?q=aa").json()["total"] == 1
    assert c.get("/api/studio-v3/data/symbols/bbb").json()["issues"][0]["kind"] == "gap"
    assert c.get("/api/studio-v3/data/symbols/NOPE").status_code == 404
    data_browser._summary.cache_clear()
