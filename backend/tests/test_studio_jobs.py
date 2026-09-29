import asyncio
import json
import stat
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.routers import studio
from app.services.studio.jobs import JobStore


def test_job_store_executes_and_persists_terminal_result(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.json")
    try:
        job = store.create(job_type="monte-carlo", params={"returns": [0.01]}, idempotency_key="stable-key")
        store.submit(job["job_id"], lambda: {"answer": 42}).result(timeout=2)

        completed = store.get(job["job_id"])
        assert completed is not None
        assert completed["status"] == "completed"
        assert completed["result"] == {"answer": 42}
        assert [event["status"] for event in completed["events"]] == ["queued", "running", "completed"]
        assert stat.S_IMODE((tmp_path / "jobs.json").stat().st_mode) == 0o600

        reloaded = JobStore(tmp_path / "jobs.json")
        try:
            assert reloaded.get(job["job_id"])["result"] == {"answer": 42}
        finally:
            reloaded.shutdown()
    finally:
        store.shutdown()


def test_job_store_cancellation_wins_over_late_completion(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.json")
    started = threading.Event()
    release = threading.Event()

    def slow_job():
        started.set()
        release.wait(timeout=2)
        return {"too_late": True}

    try:
        job = store.create(job_type="execute", params={"code": "pass"})
        future = store.submit(job["job_id"], slow_job)
        assert started.wait(timeout=1)
        assert store.cancel(job["job_id"])["status"] == "cancelled"
        release.set()
        future.result(timeout=2)
        assert store.get(job["job_id"])["status"] == "cancelled"
        assert store.get(job["job_id"])["result"] is None
    finally:
        release.set()
        store.shutdown()


def test_promotion_audit_is_append_only_hash_chained_and_persistent(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.json")
    try:
        job = store.create(job_type="walk-forward", params={"returns": [0.01] * 100})
        store.run_sync(job["job_id"], lambda: {"verdict": {"status": "PASSED", "thresholds": {"min": 0.5}}})
        first = store.append_audit(job["job_id"], {"action": "promote", "actor": "risk", "rationale": "meets policy"})
        second = store.append_audit(job["job_id"], {"action": "override", "actor": "cio", "rationale": "approved exception"})

        assert first["previous_hash"] is None
        assert second["previous_hash"] == first["record_hash"]
        assert store.get_audit(job["job_id"]) == [first, second]
        reloaded = JobStore(tmp_path / "jobs.json")
        try:
            assert reloaded.get_audit(job["job_id"])[1]["record_hash"] == second["record_hash"]
        finally:
            reloaded.shutdown()
    finally:
        store.shutdown()


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        ({"type": "execute", "params": {}}, "code"),
        ({"type": "monte-carlo", "params": {}}, "returns"),
        ({"type": "walk-forward", "params": {}}, "returns"),
        ({"type": "invalid", "params": {}}, "type"),
    ],
)
def test_create_job_contract_rejects_incomplete_operations(payload, expected_fragment) -> None:
    with pytest.raises(Exception) as exc_info:
        studio.CreateJobRequest(**payload)
    assert expected_fragment in str(exc_info.value)


def test_sse_resumes_after_last_event_id(tmp_path: Path, monkeypatch) -> None:
    isolated = JobStore(tmp_path / "jobs.json")
    job = isolated.create(job_type="monte-carlo", params={"returns": [0.01]})
    isolated.update(job["job_id"], status="running")
    isolated.update(job["job_id"], status="completed", result={"ok": True})
    monkeypatch.setattr(studio, "job_store", isolated)

    app = FastAPI()
    app.include_router(studio.router)
    transport = httpx.ASGITransport(app=app)
    async def request_events():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                f"/studio/jobs/{job['job_id']}/events",
                headers={"Last-Event-ID": "1"},
            )

    try:
        response = asyncio.run(request_events())
        assert response.status_code == 200
        chunks = [chunk for chunk in response.text.split("\n\n") if chunk]
        assert all("id: 1" not in chunk for chunk in chunks)
        assert any("event: running" in chunk for chunk in chunks)
        assert any("event: completed" in chunk for chunk in chunks)
        completed = next(chunk for chunk in chunks if "event: completed" in chunk)
        data_line = next(line for line in completed.splitlines() if line.startswith("data: "))
        assert json.loads(data_line.removeprefix("data: "))["job_id"] == job["job_id"]
    finally:
        isolated.shutdown()


def test_create_route_launches_job_and_reuses_idempotent_request(tmp_path: Path, monkeypatch) -> None:
    isolated = JobStore(tmp_path / "jobs.json")
    monkeypatch.setattr(studio, "job_store", isolated)
    monkeypatch.setattr(studio, "_execute_job", lambda job_type, params: {"type": job_type, "count": len(params["returns"])})
    app = FastAPI()
    app.include_router(studio.router)
    transport = httpx.ASGITransport(app=app)

    async def exercise_route():
        payload = {
            "type": "monte-carlo",
            "params": {"returns": [0.01, -0.02] * 10, "simulations": 100, "time_horizon": 2},
            "idempotency_key": "route-stable-key",
        }
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/studio/jobs", json=payload)
            duplicate = await client.post("/studio/jobs", json=payload)
            assert first.status_code == 200
            assert duplicate.json()["job"]["job_id"] == first.json()["job"]["job_id"]
            assert "params" not in first.json()["job"]
            assert "idempotency_key" not in first.json()["job"]
            assert first.json()["job"]["estimate"] == {
                "work_units": 200,
                "budget_units": 25_200_000,
                "budget_utilization_pct": 0.0,
                "size": "small",
                "basis": "simulation paths × horizon bars",
            }
            job_id = first.json()["job"]["job_id"]
            for _ in range(20):
                snapshot = (await client.get(f"/studio/jobs/{job_id}")).json()["job"]
                if snapshot["status"] == "completed":
                    return snapshot
                await asyncio.sleep(0.01)
        raise AssertionError("Studio job did not complete")

    try:
        completed = asyncio.run(exercise_route())
        assert completed["result"] == {"type": "monte-carlo", "count": 20}
    finally:
        isolated.shutdown()


@pytest.mark.parametrize(
    ("job_type", "params", "expected_units"),
    [
        ("execute", {"lookback_years": 10}, 2520),
        ("monte-carlo", {"simulations": 5000, "time_horizon": 252}, 1_260_000),
        ("walk-forward", {"returns": [0.0] * 500, "n_folds": 5}, 2500),
    ],
)
def test_job_estimate_is_deterministic_and_bounded(job_type, params, expected_units) -> None:
    estimate = studio._estimate_job(job_type, params)

    assert estimate["work_units"] == expected_units
    assert 0 <= estimate["budget_utilization_pct"] <= 100
    assert estimate["work_units"] <= estimate["budget_units"]
    assert estimate["size"] in {"small", "standard", "large"}
