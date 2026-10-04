"""Grading rules, BHY, data audit shape, input metadata, universes endpoint and report card."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import research_v2 as core_api
from app.api import research_v2_reports as api
from app.services.research_v2 import reports
from app.services.research_v2.registry import feature_manifest, run_feature

BASE = "/api/labs/research/v2"


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(core_api.router, prefix="/api")
    app.include_router(api.router, prefix="/api")
    return TestClient(app)


def test_grade_thresholds() -> None:
    assert reports.grade_from_thresholds(3.2, reports.T_THRESHOLDS) == "A"
    assert reports.grade_from_thresholds(2.1, reports.T_THRESHOLDS) == "C"
    assert reports.grade_from_thresholds(0.5, reports.T_THRESHOLDS) == "F"
    assert reports.grade_from_thresholds(0.03, (0.01, 0.05, 0.10, 0.20), higher_better=False) == "B"
    assert reports.grade_from_score(90) == "A" and reports.grade_from_score(39) == "F"


def test_bhy_adjustment() -> None:
    adj = reports.bhy_adjust([0.001, 0.01, 0.04, 0.5])
    assert all(a >= p for a, p in zip(adj, [0.001, 0.01, 0.04, 0.5]))
    assert adj[0] == pytest.approx(0.001 * 4 * (1 + 1 / 2 + 1 / 3 + 1 / 4), rel=1e-6)
    assert max(adj) <= 1.0 and reports.bhy_adjust([]) == []


def test_input_metadata_present() -> None:
    for f in feature_manifest():
        for i in f["inputs"]:
            assert {"required", "depends_on", "conflicts_with", "unit", "level"} <= set(i), (f["id"], i["key"])
            assert i["level"] in {"quick", "standard", "expert"}
    f07 = next(f for f in feature_manifest() if f["id"] == "07")
    group = next(i for i in f07["inputs"] if i["key"] == "kernel")
    assert group["depends_on"]["field"] == "identification_design"
    assert next(i for i in next(f for f in feature_manifest() if f["id"] == "08")["inputs"] if i["key"] == "discovery_date")["required"]
    f09 = next(f for f in feature_manifest() if f["id"] == "09")
    assert next(i for i in f09["inputs"] if i["key"] == "treated_unit")["required_unless"] == "event_csv_path"


def test_universes_endpoint(client: TestClient) -> None:
    rows = client.get(f"{BASE}/universes").json()
    assert {"id", "label", "region", "asset_type", "count"} <= set(rows[0])
    assert any(r["id"] == "global" and r["count"] > 4000 for r in rows)
    assert len({r["region"] for r in rows}) > 2


def test_universe_filters_wired_into_selection() -> None:
    from app.services.research_v2.core.data_loader import parse_symbols

    eu = parse_symbols({"regions": ["europe"], "asset_types": ["equity"], "max_symbols": 10})
    assert eu and all("_" in s for s in eu)
    with pytest.raises(ValueError):
        parse_symbols({"universe_id": "us_equities", "min_price": 1e9})


def test_data_audit_costs_and_return_series() -> None:
    res = run_feature("01", {"max_symbols": 80, "bootstrap_replications": 50, "include_merged": False})
    audit = res["meta"]["data_audit"]
    assert {"universe_size_by_month", "coverage_by_month", "missing_share", "survivorship", "pit_lag_days", "adjustments"} <= set(audit)
    assert audit["universe_size_by_month"][0].keys() == {"month", "n"}
    assert audit["survivorship"] in {"handled", "not handled"}
    costs = res["meta"]["costs"]
    assert {"breakeven_bps", "net_sharpe", "turnover", "capacity_usd"} <= set(costs)
    assert len(res["meta"]["return_series"]) > 12
    lo = run_feature("01", {"max_symbols": 80, "bootstrap_replications": 50, "include_merged": False, "long_only": True})
    assert lo["meta"]["costs"]["long_only"] is True


def test_report_card_job_and_exports(client: TestClient) -> None:
    payload = {"max_symbols": 80, "bootstrap_replications": 50, "permutation_replications": 30, "max_specifications": 10, "signal": "reversal", "discovery_date": "2019-01-01"}
    job = client.post(f"{BASE}/report-card/jobs", json={"payload": payload}).json()
    for _ in range(240):
        st = client.get(f"{BASE}/jobs/{job['job_id']}").json()
        if st["status"] in {"completed", "failed"}:
            break
        time.sleep(1)
    assert st["status"] == "completed", st
    r = st["result"]
    assert {g["dimension"] for g in r["grades"]} >= {"significance", "robustness", "placebo", "regimes", "diagnostics", "decay", "factor_zoo"}
    assert all(g["grade"] in set("ABCDF") for g in r["grades"])
    assert r["overall"]["grade"] in set("ABCDF") and r["explain"] and r["protocol"]["name"].startswith("Novy-Marx")
    assert {c["id"] for c in r["checklist"]} >= {"microcaps_excluded", "value_vs_equal_weight", "january", "transaction_costs", "post_publication_decay"}
    assert r["meta"]["return_series"]
    tex = client.get(f"{BASE}/report/{job['job_id']}.tex")
    assert tex.status_code == 200 and "\\begin{abstract}" in tex.text
    assert client.get(f"{BASE}/report/{job['job_id']}.md").status_code == 200
    assert client.get(f"{BASE}/report/{job['job_id']}.pdf").content[:4] == b"%PDF"


def test_batch_validation_and_literature() -> None:
    b = reports.run_batch({"max_symbols": 60}, ["momentum", "low_vol"])
    assert b["method"] == "BHY" and all(r["p_adj_bhy"] >= r["p"] for r in b["rows"])
    for method, n in (("walk_forward", 5), ("cpcv", 10)):
        v = reports.run_validation({"max_symbols": 60}, method, 5, 30)
        assert len(v["folds"]) == n and {"train", "test", "is_sharpe", "oos_sharpe"} <= set(v["folds"][0])
    assert reports.literature_match("reversal", {"max_symbols": 60})["matches"]


def test_synthetic_design_inside_causal() -> None:
    r = run_feature("07", {"identification_design": "synthetic", "treated_unit": "AAPL", "treatment_date": "2023-01-31", "donor_limit": 25, "max_symbols": 60})
    assert "treatment_effect" in r["tables"]
