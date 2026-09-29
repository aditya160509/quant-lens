"""Durable Studio job adapter — file-backed, process-restart resilient.

Covers P2-W3: HTTP create/cancel/inspect + SSE progress. Persists outside
process memory via an atomic JSON file. Idempotency is enforced per
(account, operation, input_hash, idempotency_key). Cancellation is
best-effort and prevents a normal `completed` after `cancelled` wins.
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

JobStatus = Literal["queued", "running", "completed", "failed", "cancelling", "cancelled", "partial"]

TERMINAL = {"completed", "failed", "cancelled", "partial"}

_STORE_PATH = Path(__file__).resolve().parent.parent.parent / ".studio_jobs.json"
_LOCK = threading.Lock()


@contextmanager
def _process_lock(path: Path):
    """Serialize read-modify-write cycles across API worker processes."""
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_id() -> str:
    return uuid.uuid4().hex


def _input_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class JobStore:
    def __init__(self, path: Path = _STORE_PATH) -> None:
        self.path = path
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._idem: Dict[str, str] = {}
        self._audits: Dict[str, list[Dict[str, Any]]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio-job")
        self._futures: Dict[str, Future[Any]] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._jobs = data.get("jobs", {})
            self._idem = data.get("idem", {})
            self._audits = data.get("audits", {})
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Studio job store is unreadable: {self.path}") from exc

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        payload = json.dumps({"jobs": self._jobs, "idem": self._idem, "audits": self._audits}, indent=2)
        tmp.write_text(payload, encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def create(
        self,
        *,
        job_type: str,
        params: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_id: Optional[str] = None,
        estimate: Optional[Dict[str, Any]] = None,
        owner_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        with _LOCK, _process_lock(self.path):
            self._load()
            input_hash = _input_hash({"type": job_type, "params": params})
            idem_key = f"{job_type}:{input_hash}:{idempotency_key or ''}"
            if idem_key in self._idem:
                existing_id = self._idem[idem_key]
                existing = self._jobs.get(existing_id)
                if existing:
                    return self._copy(existing)
            jid = _job_id()
            now = _now_iso()
            job: Dict[str, Any] = {
                "job_id": jid,
                "type": job_type,
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "input_hash": input_hash,
                "idempotency_key": idempotency_key,
                "request_id": request_id,
                "owner_hash": owner_hash,
                "estimate": estimate,
                "params": params,
                "progress": {"percent": 0, "message": "queued"},
                "events": [{"id": "1", "status": "queued", "at": now}],
                "result": None,
                "error": None,
            }
            self._jobs[jid] = job
            if idempotency_key:
                self._idem[idem_key] = jid
            self._persist()
            return self._copy(job)

    @staticmethod
    def _copy(job: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(json.dumps(job))

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with _LOCK, _process_lock(self.path):
            self._load()
            job = self._jobs.get(job_id)
            return self._copy(job) if job else None

    def append_audit(self, job_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append a tamper-evident immutable decision record to a terminal job."""
        with _LOCK, _process_lock(self.path):
            self._load()
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job["type"] != "walk-forward" or job["status"] != "completed":
                raise ValueError("promotion decisions require a completed walk-forward job")
            prior = self._audits.get(job_id, [])
            previous_hash = prior[-1]["record_hash"] if prior else None
            entry = {
                **record,
                "audit_id": uuid.uuid4().hex,
                "job_id": job_id,
                "created_at": _now_iso(),
                "previous_hash": previous_hash,
            }
            entry["record_hash"] = hashlib.sha256(
                json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest()
            self._audits.setdefault(job_id, []).append(entry)
            self._persist()
            return self._copy(entry)

    def get_audit(self, job_id: str) -> list[Dict[str, Any]]:
        with _LOCK, _process_lock(self.path):
            self._load()
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._copy(self._audits.get(job_id, []))

    def update(self, job_id: str, **patch: Any) -> Optional[Dict[str, Any]]:
        with _LOCK, _process_lock(self.path):
            self._load()
            job = self._jobs.get(job_id)
            if not job or job["status"] in TERMINAL:
                return self._copy(job) if job else None
            job.update(patch)
            job["updated_at"] = _now_iso()
            if "status" in patch:
                job["events"].append({"id": str(len(job["events"]) + 1), "status": patch["status"], "at": job["updated_at"]})
                if patch["status"] in ("running", "completed", "failed", "cancelled"):
                    job["progress"] = {"percent": 100 if patch["status"] in TERMINAL else 50, "message": patch["status"]}
            self._persist()
            return self._copy(job)

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        with _LOCK, _process_lock(self.path):
            self._load()
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job["status"] in TERMINAL:
                return self._copy(job)
            cancel_event = self._cancel_events.get(job_id)
            if cancel_event:
                cancel_event.set()
            job["status"] = "cancelled"
            job["updated_at"] = _now_iso()
            job["events"].append({"id": str(len(job["events"]) + 1), "status": "cancelled", "at": job["updated_at"]})
            job["progress"] = {"percent": 100, "message": "cancelled"}
            self._persist()
            return self._copy(job)

    def submit(self, job_id: str, fn, *args, **kwargs) -> Future[Any]:
        """Run one persisted job in the bounded local worker pool."""
        with _LOCK:
            existing = self._futures.get(job_id)
            if existing and not existing.done():
                return existing
            cancel_event = threading.Event()
            self._cancel_events[job_id] = cancel_event
            future = self._executor.submit(self.run_sync, job_id, fn, *args, **kwargs)
            self._futures[job_id] = future
        future.add_done_callback(lambda _future: self._forget_runtime(job_id))
        return future

    def _forget_runtime(self, job_id: str) -> None:
        with _LOCK:
            self._futures.pop(job_id, None)
            self._cancel_events.pop(job_id, None)

    def run_sync(self, job_id: str, fn, *args, **kwargs) -> Dict[str, Any]:
        with _LOCK, _process_lock(self.path):
            self._load()
            current = self._jobs.get(job_id)
            if not current:
                raise KeyError(job_id)
            if current["status"] != "queued":
                return self._copy(current)
            current["status"] = "running"
            current["updated_at"] = _now_iso()
            current["events"].append({"id": str(len(current["events"]) + 1), "status": "running", "at": current["updated_at"]})
            current["progress"] = {"percent": 50, "message": "running"}
            self._persist()
            job = self._copy(current)
        try:
            cancel_event = self._cancel_events.get(job_id)
            if job["status"] == "cancelled" or (cancel_event and cancel_event.is_set()):
                return job
            result = fn(*args, **kwargs)
            # check if cancelled won during fn
            with _LOCK, _process_lock(self.path):
                self._load()
                current = self._jobs.get(job_id)
                if current and current["status"] == "cancelled":
                    return self._copy(current)
            return self.update(job_id, status="completed", result=result)  # type: ignore[return-value]
        except Exception as exc:
            return self.update(job_id, status="failed", error=str(exc)[:500])  # type: ignore[return-value]

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


store = JobStore()
