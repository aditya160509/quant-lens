import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.routers import studio
from app.services.studio.jobs import JobStore
from app.services.studio.paper import PaperLifecycle, PaperLifecycleError
from app.studio_v2.shared.persistence import SQLiteStore


def _source() -> dict:
    return {"version_id": "pfv_one", "artifact_id": "portfolio_abc"}


def _validation() -> dict:
    return {
        "job_id": "job_one",
        "type": "walk-forward",
        "status": "completed",
        "params": {"source_artifact_id": "portfolio_abc"},
        "result": {"verdict": {"status": "PASSED"}},
    }


def _promotion() -> dict:
    return {"audit_id": "audit_one", "job_id": "job_one", "action": "promote"}


def _lifecycle(tmp_path: Path) -> PaperLifecycle:
    return PaperLifecycle(SQLiteStore(tmp_path / "paper.sqlite3"))


def _deployment(service: PaperLifecycle) -> dict:
    return service.create_deployment(
        name="User paper route",
        source_version=_source(),
        validation_job=_validation(),
        promotion=_promotion(),
        schedule={"kind": "manual"},
        universe=["spy", "TLT", "SPY"],
        limits={
            "max_order_notional": 100_000,
            "max_position_weight": 0.4,
            "max_gross_exposure": 1.2,
            "max_daily_loss": 5_000,
            "max_data_age_seconds": 900,
            "auto_kill_on_breach": True,
        },
    )


def test_paper_deployment_requires_exact_passed_promoted_artifact(tmp_path: Path) -> None:
    service = _lifecycle(tmp_path)
    invalid = _validation()
    invalid["params"]["source_artifact_id"] = "portfolio_other"
    with pytest.raises(PaperLifecycleError, match="does not belong") as mismatch:
        service.create_deployment(
            name="Route", source_version=_source(), validation_job=invalid,
            promotion=_promotion(), schedule={}, universe=["SPY"], limits={},
        )
    assert mismatch.value.code == "PAPER_ARTIFACT_MISMATCH"

    failed = _validation()
    failed["result"]["verdict"]["status"] = "FAILED"
    with pytest.raises(PaperLifecycleError) as rejected:
        service.create_deployment(
            name="Route", source_version=_source(), validation_job=failed,
            promotion=_promotion(), schedule={}, universe=["SPY"], limits={},
        )
    assert rejected.value.code == "PAPER_VALIDATION_FAILED"


def test_paper_event_chain_is_durable_traceable_and_reconciled(tmp_path: Path) -> None:
    service = _lifecycle(tmp_path)
    deployment = _deployment(service)
    deployment_id = deployment["deployment_id"]
    signal = service.append_event(deployment_id, "signal", {"asset": "SPY", "target_weight": 0.25})
    intended = service.append_event(deployment_id, "intended_order", {
        "asset": "SPY", "side": "buy", "quantity": 10, "notional": 1_000, "expected_price": 100,
    }, signal["event_id"])
    submitted = service.append_event(deployment_id, "submitted_order", {
        "external_order_id": "paper-user-1",
    }, intended["event_id"])
    fill = service.append_event(deployment_id, "fill", {
        "quantity": 10, "price": 100.1,
    }, submitted["event_id"])
    position = service.append_event(deployment_id, "position", {
        "asset": "SPY", "quantity": 10, "weight": 0.25, "gross_exposure": 0.25,
    }, fill["event_id"])
    service.append_event(deployment_id, "valuation", {"equity": 100_100, "daily_pnl": 100}, position["event_id"])

    trace = service.trace(deployment_id, position["event_id"])
    assert [event["event_type"] for event in trace] == ["signal", "intended_order", "submitted_order", "fill", "position"]
    reconciliation = service.reconciliation(deployment_id)
    assert reconciliation["summary"]["fill_count"] == 1
    assert reconciliation["fills"][0]["classification"] == "adverse"
    assert reconciliation["fills"][0]["slippage_bps"] == pytest.approx(10.0)

    recovered = PaperLifecycle(SQLiteStore(tmp_path / "paper.sqlite3"))
    assert recovered.get_deployment(deployment_id)["event_count"] == 6
    assert len(recovered.list_events(deployment_id)) == 6


def test_rejected_submission_creates_linked_alert(tmp_path: Path) -> None:
    service = _lifecycle(tmp_path)
    deployment_id = _deployment(service)["deployment_id"]
    signal = service.append_event(deployment_id, "signal", {"asset": "SPY"})
    intended = service.append_event(deployment_id, "intended_order", {"asset": "SPY", "notional": 100}, signal["event_id"])
    submitted = service.append_event(deployment_id, "submitted_order", {
        "status": "rejected", "rejection_reason": "user supplied broker rejection",
    }, intended["event_id"])
    events = service.list_events(deployment_id)
    assert events[-1]["event_type"] == "alert"
    assert events[-1]["parent_event_id"] == submitted["event_id"]
    assert events[-1]["payload"]["category"] == "rejected_order"


def test_limit_breach_records_alert_engages_kill_switch_and_blocks_trading(tmp_path: Path) -> None:
    service = _lifecycle(tmp_path)
    deployment_id = _deployment(service)["deployment_id"]
    signal = service.append_event(deployment_id, "signal", {"asset": "SPY"})

    with pytest.raises(PaperLifecycleError) as breach:
        service.append_event(deployment_id, "intended_order", {
            "asset": "SPY", "side": "buy", "notional": 100_001,
        }, signal["event_id"])
    assert breach.value.code == "PAPER_LIMIT_BREACH"
    assert service.get_deployment(deployment_id)["kill_switch"]["engaged"] is True
    assert service.list_events(deployment_id)[-1]["payload"]["category"] == "limit_breach"

    with pytest.raises(PaperLifecycleError) as halted:
        service.append_event(deployment_id, "signal", {"asset": "TLT"})
    assert halted.value.code == "PAPER_KILL_SWITCH_ENGAGED"

    released = service.set_kill_switch(deployment_id, engaged=False, actor="operator", reason="reviewed alert")
    assert released["state"] == "armed"
    assert service.append_event(deployment_id, "signal", {"asset": "TLT"})["event_type"] == "signal"


def test_causal_parent_type_is_enforced(tmp_path: Path) -> None:
    service = _lifecycle(tmp_path)
    deployment_id = _deployment(service)["deployment_id"]
    signal = service.append_event(deployment_id, "signal", {"asset": "SPY"})
    with pytest.raises(PaperLifecycleError) as invalid:
        service.append_event(deployment_id, "fill", {"price": 100}, signal["event_id"])
    assert invalid.value.code == "PAPER_CAUSALITY_INVALID"


def test_paper_routes_bind_deployment_to_persisted_version_and_promotion(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "route.sqlite3"
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(database))
    source_store = SQLiteStore(database)
    source_store.put("studio_portfolio_versions", "pfv_route", {
        "version_id": "pfv_route", "artifact_id": "portfolio_route",
    })
    jobs = JobStore(tmp_path / "jobs.json")
    job = jobs.create(job_type="walk-forward", params={"source_artifact_id": "portfolio_route", "returns": [0.01] * 100})
    jobs.run_sync(job["job_id"], lambda: {"verdict": {"status": "PASSED", "thresholds": {}}})
    audit = jobs.append_audit(job["job_id"], {"action": "promote", "actor": "risk", "rationale": "passed"})
    monkeypatch.setattr(studio, "job_store", jobs)
    monkeypatch.setattr(studio, "paper_lifecycle", PaperLifecycle(source_store))

    async def exercise() -> None:
        app = FastAPI()
        app.include_router(studio.router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/studio/paper/deployments", json={
                "name": "Route", "source_version_id": "pfv_route",
                "validation_job_id": job["job_id"], "promotion_audit_id": audit["audit_id"],
                "schedule": {"kind": "manual"}, "universe": ["SPY"], "limits": {},
            })
            assert created.status_code == 200, created.text
            deployment_id = created.json()["deployment"]["deployment_id"]
            signal = await client.post(f"/studio/paper/deployments/{deployment_id}/events", json={
                "event_type": "signal", "payload": {"asset": "SPY"},
            })
            assert signal.status_code == 200
            ledger = await client.get(f"/studio/paper/deployments/{deployment_id}/events")
            assert [row["event_type"] for row in ledger.json()["events"]] == ["signal"]

    try:
        asyncio.run(exercise())
    finally:
        jobs.shutdown()
