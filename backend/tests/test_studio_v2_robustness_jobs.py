from __future__ import annotations

import asyncio
import multiprocessing
import socket
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.studio_v2.robustness.jobs import (
    DurableRobustnessJobService,
    JobResultUnavailableError,
)
from app.studio_v2.router import Router
from app.studio_v2.shared.persistence import SQLiteStore, utc_now


def _success_runner(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "echo": payload.get("value", 0)}


def _slow_runner(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    time.sleep(float(payload.get("delay", 0.25)))
    return {"kind": kind, "finished": True}


def _failing_runner(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    raise ValueError(str(payload.get("message", "expected worker failure")))


def _large_runner(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "data": "x" * int(payload.get("size", 10_000))}


def _start_method() -> str:
    return "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"


def _wait_for_status(
    service: DurableRobustnessJobService,
    job_id: str,
    statuses: set[str],
    timeout: float = 8.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = service.get_status(job_id)
        if status["status"] in statuses:
            return status
        time.sleep(0.01)
    raise AssertionError(
        f"job {job_id} did not reach {sorted(statuses)}; "
        f"last status was {service.get_status(job_id)}"
    )


def _service(
    database: Path,
    runner: Any,
    **kwargs: Any,
) -> DurableRobustnessJobService:
    return DurableRobustnessJobService(
        SQLiteStore(database),
        runner=runner,
        process_start_method=_start_method(),
        **kwargs,
    )


def test_job_lifecycle_and_result_persist_across_service_instances(tmp_path: Path) -> None:
    database = tmp_path / "robustness-jobs.sqlite3"
    first = _service(database, _success_runner)
    try:
        created = first.submit("core", {"value": 7}, timeout_seconds=2)
        completed = _wait_for_status(first, created["job_id"], {"completed"})
        assert completed["progress"] == 1.0
        assert completed["result_available"] is True
        assert [item["status"] for item in completed["transitions"]] == [
            "queued",
            "running",
            "completed",
        ]
        assert first.get_result(created["job_id"])["result"] == {
            "echo": 7,
            "kind": "core",
        }

        reloaded = _service(database, _success_runner)
        try:
            assert reloaded.get_status(created["job_id"])["status"] == "completed"
            assert reloaded.get_result(created["job_id"])["result"]["echo"] == 7
        finally:
            reloaded.shutdown()
    finally:
        first.shutdown()


def test_running_job_can_be_cancelled_and_stays_cancelled(tmp_path: Path) -> None:
    service = _service(tmp_path / "cancel.sqlite3", _slow_runner)
    try:
        job = service.submit("core", {"delay": 2.0}, timeout_seconds=3)
        _wait_for_status(service, job["job_id"], {"running"})
        cancelled = service.cancel(job["job_id"])
        assert cancelled["status"] == "cancelled"
        assert cancelled["progress"] == 1.0
        time.sleep(0.05)
        assert service.get_status(job["job_id"])["status"] == "cancelled"
        with pytest.raises(JobResultUnavailableError, match="cancelled"):
            service.get_result(job["job_id"])
    finally:
        service.shutdown()


def test_queue_allows_only_configured_active_workers_and_cancels_queued_job(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path / "queue.sqlite3", _slow_runner, max_concurrency=1
    )
    try:
        first = service.submit("core", {"delay": 2.0}, timeout_seconds=3)
        _wait_for_status(service, first["job_id"], {"running"})
        second = service.submit("core", {"delay": 2.0}, timeout_seconds=3)
        assert service.get_status(second["job_id"])["status"] == "queued"
        assert service.cancel(second["job_id"])["status"] == "cancelled"
        assert service.cancel(first["job_id"])["status"] == "cancelled"
    finally:
        service.shutdown()


def test_job_timeout_terminates_worker_and_persists_failure(tmp_path: Path) -> None:
    service = _service(tmp_path / "timeout.sqlite3", _slow_runner)
    try:
        job = service.submit("extended", {"delay": 0.5}, timeout_seconds=0.05)
        failed = _wait_for_status(service, job["job_id"], {"failed"})
        assert failed["failure"]["code"] == "timeout"
        assert failed["result_available"] is False
        assert [item["status"] for item in failed["transitions"]][-1] == "failed"
    finally:
        service.shutdown()


def test_worker_failure_and_output_limit_are_explicit(tmp_path: Path) -> None:
    failure_service = _service(tmp_path / "failure.sqlite3", _failing_runner)
    try:
        job = failure_service.submit("core", {"message": "bad diagnostic"})
        failed = _wait_for_status(failure_service, job["job_id"], {"failed"})
        assert failed["failure"] == {
            "code": "execution_failed",
            "message": "bad diagnostic",
        }
    finally:
        failure_service.shutdown()

    output_service = _service(tmp_path / "output.sqlite3", _large_runner)
    try:
        job = output_service.submit(
            "core", {"size": 10_000}, max_output_bytes=512
        )
        failed = _wait_for_status(output_service, job["job_id"], {"failed"})
        assert failed["failure"]["code"] == "output_limit_exceeded"
    finally:
        output_service.shutdown()


@pytest.mark.parametrize("interrupted_status", ["queued", "running"])
def test_restart_recovery_marks_interrupted_jobs_deterministically(
    tmp_path: Path, interrupted_status: str
) -> None:
    store = SQLiteStore(tmp_path / f"restart-{interrupted_status}.sqlite3")
    job_id = f"rjob_interrupted_{interrupted_status}"
    now = utc_now()
    store.put(
        "robustness_jobs",
        job_id,
        {
            "job_id": job_id,
            "kind": "core",
            "status": interrupted_status,
            "phase": interrupted_status,
            "progress": 0.05 if interrupted_status == "running" else 0.0,
            "request_payload": {"returns": [0.0] * 20},
            "timeout_seconds": 60.0,
            "max_output_bytes": 10_000,
            "started_at": now if interrupted_status == "running" else None,
            "completed_at": None,
            "failure": None,
            "result_available": False,
            "owner_instance": "dead-worker",
            "owner_pid": -1,
            "owner_host": socket.gethostname(),
            "heartbeat_at": now,
            "transitions": [{"status": interrupted_status, "at": now}],
        },
    )

    recovered = DurableRobustnessJobService(
        store,
        runner=_success_runner,
        process_start_method=_start_method(),
    )
    try:
        status = recovered.get_status(job_id)
        assert status["status"] == "failed"
        assert status["failure"]["code"] == "interrupted_by_restart"
        assert status["completed_at"] is not None
    finally:
        recovered.shutdown()


def test_robustness_job_http_contract_runs_existing_core_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUDIO_V2_JOB_START_METHOD", _start_method())
    studio_router = Router(store=SQLiteStore(tmp_path / "http-jobs.sqlite3"))
    app = FastAPI()
    app.include_router(studio_router)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            invalid = await client.post(
                "/api/v2/robustness/jobs",
                json={"kind": "unknown", "payload": {}},
            )
            assert invalid.status_code == 422

            response = await client.post(
                "/api/v2/robustness/jobs",
                json={
                    "kind": "core",
                    "payload": {
                        "returns": [0.004, -0.002, 0.003, -0.001] * 5,
                        "n_simulations": 10,
                        "seed": 17,
                    },
                    "timeout_seconds": 10,
                    "max_output_bytes": 200_000,
                },
            )
            assert response.status_code == 200, response.text
            job_id = response.json()["job_id"]
            for _ in range(400):
                status_response = await client.get(
                    f"/api/v2/robustness/jobs/{job_id}"
                )
                assert status_response.status_code == 200
                if status_response.json()["status"] in {
                    "completed",
                    "failed",
                    "cancelled",
                }:
                    break
                await asyncio.sleep(0.01)
            assert status_response.json()["status"] == "completed", status_response.text

            result = await client.get(
                f"/api/v2/robustness/jobs/{job_id}/result"
            )
            assert result.status_code == 200, result.text
            payload = result.json()
            assert payload["job"]["result_available"] is True
            assert payload["result"]["data_source"]["simulations"] == 10
            assert payload["result"]["run_id"].startswith("robust_")

            missing = await client.get("/api/v2/robustness/jobs/missing")
            assert missing.status_code == 404
            assert missing.json()["detail"]["code"] == "not_found"

        schema = app.openapi()
        create_operation = schema["paths"]["/api/v2/robustness/jobs"]["post"]
        assert create_operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/RobustnessJobStatusResponse")
        assert create_operation["responses"]["409"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/ErrorResponse")

    try:
        asyncio.run(exercise())
    finally:
        studio_router.robustness_jobs.shutdown()
