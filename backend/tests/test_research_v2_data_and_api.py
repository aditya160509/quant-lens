"""Point-in-time data rules, causal estimator identities and the Research V2 API."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import research_v2 as api
from app.services.research_v2.core.causal import goodman_bacon
from app.services.research_v2.core.data_loader import UnknownSymbolsError, _safe_user_path, load_fundamentals, parse_symbols, point_in_time_fundamental


def test_fundamentals_are_unavailable_until_the_filing_lag_passes() -> None:
    f = load_fundamentals()
    row = f.dropna(subset=["Total Assets", "reportDate"]).sort_values("reportDate").iloc[0]
    first = pd.Timestamp(row["reportDate"])
    dates = pd.DatetimeIndex([first + pd.Timedelta(days=30), first + pd.Timedelta(days=91)])
    vals = point_in_time_fundamental("Total Assets", dates, [row["ticker"]])
    assert np.isnan(vals.iloc[0, 0])
    assert np.isfinite(vals.iloc[1, 0])


def test_unknown_tickers_are_rejected_not_replaced() -> None:
    with pytest.raises(UnknownSymbolsError):
        parse_symbols({"universe": "AAPL,NOT_A_REAL_TICKER"})
    assert parse_symbols({"universe": "AAPL"}) == ["AAPL"]


def test_uploads_cannot_escape_the_upload_directory() -> None:
    with pytest.raises(ValueError):
        _safe_user_path("../../main.py")
    with pytest.raises(ValueError):
        _safe_user_path("/etc/passwd")


def test_goodman_bacon_weights_reproduce_twfe() -> None:
    import pyfixest as pf

    rng = np.random.default_rng(0)
    rows = []
    for u in range(60):
        g = [8, 16, 0][u % 3]
        for t in range(1, 25):
            d = int(g > 0 and t >= g)
            rows.append({"unit": u, "unit_id": u, "time": t, "g": g, "treat": d, "y": 0.1 * u + 0.05 * t + d * (1 + 0.1 * (t - g)) + rng.normal()})
    df = pd.DataFrame(rows)
    twfe = float(pf.feols("y ~ treat | unit_id + time", data=df).coef()["treat"])
    bacon = goodman_bacon(df)
    assert bacon["weight"].sum() == pytest.approx(1.0)
    assert bacon["contribution"].sum() == pytest.approx(twfe, abs=1e-8)


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    return TestClient(app)


def test_manifest_declares_every_feature(client: TestClient) -> None:
    features = client.get("/api/labs/research/v2/features").json()["features"]
    assert [f["id"] for f in features] == ["01", "02", "03", "04", "05", "06", "07", "08", "09", "11"]
    for f in features:
        assert f["inputs"] and f["outputs"]
        assert all({"key", "label", "type", "group"} <= set(i) for i in f["inputs"])
        assert sum(o["primary"] for o in f["outputs"]) == 1


def test_upload_validates_columns(client: TestClient) -> None:
    bad = client.post("/api/labs/research/v2/uploads", params={"kind": "signal"}, files={"file": ("s.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422
    good = client.post("/api/labs/research/v2/uploads", params={"kind": "event"}, files={"file": ("e.csv", b"ticker,event_date\nAAPL,2022-01-10\n", "text/csv")})
    assert good.status_code == 200 and good.json()["upload_id"].startswith("event_")


def test_job_reports_unknown_tickers(client: TestClient) -> None:
    job = client.post("/api/labs/research/v2/feature/01/jobs", json={"payload": {"universe": "AAPL,NOT_A_REAL_TICKER"}}).json()
    api.JOBS._futures.get(job["job_id"]) and api.JOBS._futures[job["job_id"]].result(timeout=60)
    status = client.get(f"/api/labs/research/v2/jobs/{job['job_id']}").json()
    assert status["status"] == "failed"
    assert "NOT_A_REAL_TICKER" in status["error"]


def test_every_render_hint_has_a_frontend_renderer() -> None:
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "frontend/src/components/research-v2/renderers.jsx").read_text()
    block = src[src.index("export const RENDERERS = {"):]
    block = block[: block.index("};")]
    renderers = set(re.findall(r"(\w+):\s*\w+", block))
    hints = {o["render"] for f in api.feature_manifest() for o in f["outputs"]}
    assert hints <= renderers, f"render hints without a renderer: {sorted(hints - renderers)}"
