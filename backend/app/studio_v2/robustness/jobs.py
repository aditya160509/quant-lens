"""Durable, bounded local job execution for robustness diagnostics."""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import socket
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any, Callable, Literal, Optional

import numpy as np
import pandas as pd

from ..shared.persistence import SQLiteStore, VersionConflictError, utc_now
from .execution import run_core_diagnostics, run_extended_diagnostic

JobKind = Literal["core", "extended"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
Runner = Callable[[JobKind, dict[str, Any]], dict[str, Any]]
Finalizer = Callable[[dict[str, Any]], dict[str, Any]]

_JOBS_NAMESPACE = "robustness_jobs"
_RESULTS_NAMESPACE = "robustness_job_results"
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_ACTIVE_SERVICE_IDS: set[str] = set()
_ACTIVE_SERVICE_LOCK = threading.RLock()


class JobResultUnavailableError(RuntimeError):
    """Raised when a job has no completed result yet."""


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, pd.DataFrame):
        clean = value.replace([np.inf, -np.inf], np.nan)
        return [_json_safe(row) for row in clean.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        clean = value.replace([np.inf, -np.inf], np.nan)
        return {str(key): _json_safe(item) for key, item in clean.items()}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [_json_safe(item) for item in list(value)]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    return value


def _encode_result(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def execute_robustness_job(kind: JobKind, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute only the already-supported bounded core or extended work."""

    if kind == "core":
        result, components = run_core_diagnostics(payload)
        return {
            "kind": kind,
            "test": "core",
            "result": _json_safe(result),
            "components": _json_safe(components),
        }
    if kind == "extended":
        result, components = run_extended_diagnostic(payload)
        return {
            "kind": kind,
            "test": str(payload["test"]),
            "result": _json_safe(result),
            "components": _json_safe(components),
        }
    raise ValueError(f"unsupported robustness job kind: {kind}")


def _process_entry(
    sender: Connection,
    runner: Runner,
    kind: JobKind,
    payload: dict[str, Any],
    max_output_bytes: int,
) -> None:
    """Serialize a child result before IPC so the byte limit is a hard boundary."""

    try:
        encoded = _encode_result(runner(kind, payload))
        if len(encoded) > max_output_bytes:
            message = {
                "ok": False,
                "error": {
                    "code": "output_limit_exceeded",
                    "message": (
                        f"robustness result exceeded {max_output_bytes} serialized bytes"
                    ),
                },
            }
        else:
            message = {"ok": True, "encoded_result": encoded.decode("utf-8")}
    except BaseException as exc:  # The parent must receive deterministic worker failures.
        message = {
            "ok": False,
            "error": {
                "code": "execution_failed",
                "message": str(exc)[:1_000] or exc.__class__.__name__,
            },
        }
    try:
        sender.send_bytes(_encode_result(message))
    finally:
        sender.close()


class DurableRobustnessJobService:
    """Persist and supervise a small local queue of isolated robustness jobs."""

    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        *,
        max_concurrency: int = 1,
        max_pending_jobs: int = 100,
        max_timeout_seconds: float = 300.0,
        max_output_bytes: int = 5_000_000,
        max_input_bytes: int = 5_000_000,
        runner: Runner = execute_robustness_job,
        finalizer: Optional[Finalizer] = None,
        process_start_method: Optional[str] = None,
        auto_recover: bool = True,
    ) -> None:
        self.store = store or SQLiteStore()
        self.max_concurrency = min(max(1, int(max_concurrency)), 2)
        self.max_pending_jobs = min(max(1, int(max_pending_jobs)), 1_000)
        self.max_timeout_seconds = min(max(float(max_timeout_seconds), 0.01), 300.0)
        self.max_output_bytes = min(max(int(max_output_bytes), 256), 5_000_000)
        self.max_input_bytes = min(max(int(max_input_bytes), 1_024), 5_000_000)
        self.runner = runner
        self.finalizer = finalizer
        self.instance_id = f"robust_worker_{uuid.uuid4().hex[:16]}"
        self.owner_pid = os.getpid()
        self.owner_host = socket.gethostname()
        requested_method = process_start_method or os.getenv(
            "STUDIO_V2_JOB_START_METHOD", "spawn"
        )
        available = multiprocessing.get_all_start_methods()
        if requested_method not in available:
            raise ValueError(
                f"unsupported process start method '{requested_method}'; choose from {available}"
            )
        self._context = multiprocessing.get_context(requested_method)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_concurrency,
            thread_name_prefix="robustness-job",
        )
        self._lock = threading.RLock()
        self._futures: dict[str, Future[Any]] = {}
        self._processes: dict[str, BaseProcess] = {}
        self._closed = False
        with _ACTIVE_SERVICE_LOCK:
            _ACTIVE_SERVICE_IDS.add(self.instance_id)
        if auto_recover:
            self.recover_interrupted()

    def submit(
        self,
        kind: JobKind,
        payload: dict[str, Any],
        *,
        timeout_seconds: float = 60.0,
        max_output_bytes: int = 1_000_000,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("robustness job service is closed")
        if kind not in {"core", "extended"}:
            raise ValueError("kind must be 'core' or 'extended'")
        timeout = float(timeout_seconds)
        if not 0.01 <= timeout <= self.max_timeout_seconds:
            raise ValueError(
                f"timeout_seconds must be between 0.01 and {self.max_timeout_seconds:g}"
            )
        output_limit = int(max_output_bytes)
        if not 256 <= output_limit <= self.max_output_bytes:
            raise ValueError(
                f"max_output_bytes must be between 256 and {self.max_output_bytes}"
            )
        safe_payload = _json_safe(payload)
        if len(_encode_result(safe_payload)) > self.max_input_bytes:
            raise ValueError(
                f"robustness job payload exceeds {self.max_input_bytes} serialized bytes"
            )
        active = [
            job
            for job in self.store.list(_JOBS_NAMESPACE, limit=1_000)
            if job.get("status") in {"queued", "running"}
        ]
        if len(active) >= self.max_pending_jobs:
            raise RuntimeError("robustness job queue is at capacity")

        job_id = f"rjob_{uuid.uuid4().hex[:16]}"
        now = utc_now()
        record = self.store.put(
            _JOBS_NAMESPACE,
            job_id,
            {
                "job_id": job_id,
                "kind": kind,
                "status": "queued",
                "phase": "queued",
                "progress": 0.0,
                "request_payload": safe_payload,
                "timeout_seconds": timeout,
                "max_output_bytes": output_limit,
                "started_at": None,
                "completed_at": None,
                "failure": None,
                "result_available": False,
                "owner_instance": self.instance_id,
                "owner_pid": self.owner_pid,
                "owner_host": self.owner_host,
                "heartbeat_at": now,
                "transitions": [{"status": "queued", "at": now}],
            },
            create_only=True,
        )
        with self._lock:
            future = self._executor.submit(self._run_job, job_id)
            self._futures[job_id] = future
        return self._public_status(record)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return self._public_status(self.store.get(_JOBS_NAMESPACE, job_id))

    def get_result(self, job_id: str) -> dict[str, Any]:
        job = self.store.get(_JOBS_NAMESPACE, job_id)
        if job.get("status") != "completed":
            raise JobResultUnavailableError(
                f"robustness job '{job_id}' is {job.get('status')}; no result is available"
            )
        result = self.store.maybe_get(_RESULTS_NAMESPACE, job_id)
        if result is None:
            raise JobResultUnavailableError(
                f"robustness job '{job_id}' completed without a persisted result"
            )
        return {"job": self._public_status(job), "result": result["result"]}

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            current = self.store.get(_JOBS_NAMESPACE, job_id)
            status = str(current.get("status"))
            if status == "cancelled":
                return self._public_status(current)
            if status in {"completed", "failed"}:
                raise RuntimeError(
                    f"robustness job '{job_id}' is already {status} and cannot be cancelled"
                )
            updated, changed = self._transition(
                job_id,
                {"queued", "running"},
                "cancelled",
                phase="cancelled",
                progress=1.0,
                completed_at=utc_now(),
                failure=None,
                result_available=False,
            )
            if not changed:
                return self._public_status(updated)
            future = self._futures.get(job_id)
            if future is not None:
                future.cancel()
            process = self._processes.get(job_id)
            if process is not None:
                self._terminate(process)
            self.store.delete(_RESULTS_NAMESPACE, job_id)
            return self._public_status(updated)

    def recover_interrupted(self) -> list[str]:
        """Fail active records whose owning local worker is no longer alive."""

        recovered: list[str] = []
        for record in self.store.list(_JOBS_NAMESPACE, limit=1_000):
            if record.get("status") not in {"queued", "running"}:
                continue
            if self._owner_is_alive(record):
                continue
            job_id = str(record.get("job_id") or record["id"])
            _, changed = self._transition(
                job_id,
                {"queued", "running"},
                "failed",
                phase="failed",
                progress=1.0,
                completed_at=utc_now(),
                failure={
                    "code": "interrupted_by_restart",
                    "message": "the local worker stopped before this robustness job finished",
                },
                result_available=False,
            )
            if changed:
                self.store.delete(_RESULTS_NAMESPACE, job_id)
                recovered.append(job_id)
        return recovered

    def shutdown(self, *, wait: bool = True, cancel_running: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        if cancel_running:
            for record in self.store.list(_JOBS_NAMESPACE, limit=1_000):
                if (
                    record.get("owner_instance") == self.instance_id
                    and record.get("status") in {"queued", "running"}
                ):
                    try:
                        self.cancel(str(record.get("job_id") or record["id"]))
                    except (KeyError, RuntimeError):
                        pass
        with self._lock:
            for process in tuple(self._processes.values()):
                self._terminate(process)
        self._executor.shutdown(wait=wait, cancel_futures=True)
        with _ACTIVE_SERVICE_LOCK:
            _ACTIVE_SERVICE_IDS.discard(self.instance_id)

    def _run_job(self, job_id: str) -> None:
        receiver: Optional[Connection] = None
        process: Optional[BaseProcess] = None
        try:
            record, changed = self._transition(
                job_id,
                {"queued"},
                "running",
                phase="running",
                progress=0.05,
                started_at=utc_now(),
                heartbeat_at=utc_now(),
            )
            if not changed:
                return
            receiver, sender = self._context.Pipe(duplex=False)
            process = self._context.Process(
                target=_process_entry,
                args=(
                    sender,
                    self.runner,
                    record["kind"],
                    record["request_payload"],
                    int(record["max_output_bytes"]),
                ),
                name=f"robustness-{job_id}",
                daemon=True,
            )
            process.start()
            sender.close()
            with self._lock:
                self._processes[job_id] = process
            deadline = time.monotonic() + float(record["timeout_seconds"])

            while True:
                current = self.store.get(_JOBS_NAMESPACE, job_id)
                if current.get("status") == "cancelled":
                    self._terminate(process)
                    return
                if receiver.poll(0.02):
                    message = json.loads(receiver.recv_bytes().decode("utf-8"))
                    process.join(timeout=0.5)
                    if message.get("ok"):
                        raw_result = json.loads(message["encoded_result"])
                        self._complete(job_id, raw_result)
                    else:
                        self._fail(job_id, message.get("error") or {
                            "code": "execution_failed",
                            "message": "robustness worker failed without an error message",
                        })
                    return
                if time.monotonic() >= deadline:
                    self._terminate(process)
                    self._fail(
                        job_id,
                        {
                            "code": "timeout",
                            "message": (
                                "robustness job exceeded its "
                                f"{record['timeout_seconds']:g} second timeout"
                            ),
                        },
                    )
                    return
                if not process.is_alive():
                    if receiver.poll(0.05):
                        continue
                    self._fail(
                        job_id,
                        {
                            "code": "worker_exit",
                            "message": (
                                "robustness worker exited without a result "
                                f"(exit code {process.exitcode})"
                            ),
                        },
                    )
                    return
        except BaseException as exc:
            self._fail(
                job_id,
                {
                    "code": "worker_start_failed",
                    "message": str(exc)[:1_000] or exc.__class__.__name__,
                },
            )
        finally:
            if receiver is not None:
                receiver.close()
            if process is not None and process.is_alive():
                self._terminate(process)
            with self._lock:
                self._processes.pop(job_id, None)
                self._futures.pop(job_id, None)

    def _complete(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            current = self.store.get(_JOBS_NAMESPACE, job_id)
            if current.get("status") != "running":
                return
            final_result = self.finalizer(result) if self.finalizer else result
            encoded = _encode_result(final_result)
            if len(encoded) > int(current["max_output_bytes"]):
                self._fail(
                    job_id,
                    {
                        "code": "output_limit_exceeded",
                        "message": (
                            "final robustness result exceeded "
                            f"{current['max_output_bytes']} serialized bytes"
                        ),
                    },
                )
                return
            safe_result = json.loads(encoded.decode("utf-8"))
            self.store.put(
                _RESULTS_NAMESPACE,
                job_id,
                {"job_id": job_id, "result": safe_result},
            )
            _, changed = self._transition(
                job_id,
                {"running"},
                "completed",
                phase="completed",
                progress=1.0,
                completed_at=utc_now(),
                failure=None,
                result_available=True,
            )
            if not changed:
                self.store.delete(_RESULTS_NAMESPACE, job_id)

    def _fail(self, job_id: str, failure: dict[str, str]) -> None:
        try:
            _, changed = self._transition(
                job_id,
                {"queued", "running"},
                "failed",
                phase="failed",
                progress=1.0,
                completed_at=utc_now(),
                failure={
                    "code": str(failure.get("code", "execution_failed"))[:100],
                    "message": str(failure.get("message", "robustness job failed"))[:1_000],
                },
                result_available=False,
            )
            if changed:
                self.store.delete(_RESULTS_NAMESPACE, job_id)
        except KeyError:
            return

    def _transition(
        self,
        job_id: str,
        allowed: set[str],
        status: JobStatus,
        **updates: Any,
    ) -> tuple[dict[str, Any], bool]:
        with self._lock:
            for _ in range(3):
                current = self.store.get(_JOBS_NAMESPACE, job_id)
                if current.get("status") not in allowed:
                    return current, False
                now = utc_now()
                next_record = dict(current)
                next_record.update(updates)
                next_record["status"] = status
                next_record["heartbeat_at"] = now
                next_record["transitions"] = [
                    *current.get("transitions", []),
                    {"status": status, "at": now},
                ]
                try:
                    updated = self.store.put(
                        _JOBS_NAMESPACE,
                        job_id,
                        next_record,
                        expected_version=int(current.get("_revision", 1)),
                    )
                    return updated, True
                except VersionConflictError:
                    continue
            current = self.store.get(_JOBS_NAMESPACE, job_id)
            return current, False

    def _owner_is_alive(self, record: dict[str, Any]) -> bool:
        instance_id = str(record.get("owner_instance", ""))
        with _ACTIVE_SERVICE_LOCK:
            if instance_id in _ACTIVE_SERVICE_IDS:
                return True
        if str(record.get("owner_host", "")) != self.owner_host:
            updated = _parse_timestamp(record.get("heartbeat_at") or record.get("updated_at"))
            age = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds())
            return age <= float(record.get("timeout_seconds", 300.0)) + 30.0
        owner_pid = int(record.get("owner_pid") or -1)
        if owner_pid <= 0:
            return False
        if owner_pid == self.owner_pid:
            return False
        try:
            os.kill(owner_pid, 0)
        except (OSError, ValueError):
            return False
        return True

    @staticmethod
    def _terminate(process: BaseProcess) -> None:
        if not process.is_alive():
            process.join(timeout=0.1)
            return
        process.terminate()
        process.join(timeout=1.0)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(timeout=0.5)

    @staticmethod
    def _public_status(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": str(record.get("job_id") or record["id"]),
            "kind": record["kind"],
            "status": record["status"],
            "phase": record.get("phase", record["status"]),
            "progress": float(record.get("progress", 0.0)),
            "timeout_seconds": float(record["timeout_seconds"]),
            "max_output_bytes": int(record["max_output_bytes"]),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "failure": record.get("failure"),
            "result_available": bool(record.get("result_available", False)),
            "transitions": record.get("transitions", []),
        }


def _parse_timestamp(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.fromtimestamp(0, tz=timezone.utc)
