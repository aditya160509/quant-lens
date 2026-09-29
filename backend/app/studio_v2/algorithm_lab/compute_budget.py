"""Tracked compute jobs with queueing, timeouts, and process cancellation."""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from multiprocessing.process import BaseProcess
from typing import Any, Optional


@dataclass
class Job:
    job_id: str
    session_id: str
    type: str
    cell_id: str
    started_at: Optional[str]
    status: str
    position: Optional[int] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.started_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.now(timezone.utc)
            if self.completed_at:
                end = datetime.fromisoformat(self.completed_at)
            payload["elapsed_seconds"] = max(0.0, (end - start).total_seconds())
        else:
            payload["elapsed_seconds"] = 0.0
        return payload


class ComputeBudget:
    def __init__(self, threshold_seconds: int = 60, max_concurrent_per_session: int = 2) -> None:
        self.threshold_seconds = self._validate_threshold(threshold_seconds)
        self.max_concurrent_per_session = max(1, int(max_concurrent_per_session))
        self._jobs: dict[str, Job] = {}
        self._processes: dict[str, BaseProcess] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _validate_threshold(seconds: int) -> int:
        resolved = int(seconds)
        if not 1 <= resolved <= 86_400:
            raise ValueError("threshold_seconds must be between 1 and 86400")
        return resolved

    def set_threshold(self, seconds: int) -> int:
        self.threshold_seconds = self._validate_threshold(seconds)
        return self.threshold_seconds

    def start_job(
        self,
        session_id: str,
        job_id: Optional[str] = None,
        type: str = "cell_execution",
        cell_id: str = "cell-1",
        process: Optional[BaseProcess] = None,
    ) -> Job:
        resolved_id = job_id or f"job_{uuid.uuid4().hex[:12]}"
        with self._lock:
            active = [
                job for job in self._jobs.values()
                if job.session_id == session_id and job.status == "running"
            ]
            queued = [
                job for job in self._jobs.values()
                if job.session_id == session_id and job.status == "queued"
            ]
            status = "running" if len(active) < self.max_concurrent_per_session else "queued"
            job = Job(
                resolved_id,
                session_id,
                type,
                cell_id,
                datetime.now(timezone.utc).isoformat() if status == "running" else None,
                status,
                len(queued) + 1 if status == "queued" else None,
            )
            self._jobs[resolved_id] = job
            if process is not None:
                self._processes[resolved_id] = process
            return job

    def attach_process(self, job_id: str, process: BaseProcess) -> None:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"job '{job_id}' not found")
            self._processes[job_id] = process

    def _promote_next(self, session_id: str) -> Optional[Job]:
        queued = sorted(
            (
                job for job in self._jobs.values()
                if job.session_id == session_id and job.status == "queued"
            ),
            key=lambda job: job.position or 0,
        )
        if not queued:
            return None
        job = queued[0]
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.position = None
        for pending in queued[1:]:
            pending.position = max(1, (pending.position or 1) - 1)
        return job

    def complete_job(self, session_id: str, job_id: str, error: Optional[str] = None) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.session_id != session_id:
                raise KeyError(f"job '{job_id}' not found in session '{session_id}'")
            job.status = "failed" if error else "completed"
            job.error = error
            job.completed_at = datetime.now(timezone.utc).isoformat()
            self._processes.pop(job_id, None)
            self._promote_next(session_id)
            return job

    def get_status(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.session_id == session_id]
            running = [job.to_dict() for job in jobs if job.status == "running"]
            queued = [job.to_dict() for job in jobs if job.status == "queued"]
            recent = [
                job.to_dict() for job in jobs
                if job.status in {"completed", "failed", "killed"}
            ][-20:]
        return {
            "running": running,
            "queued": queued,
            "recent": recent,
            "threshold_seconds": self.threshold_seconds,
            "over_threshold": [
                job for job in running
                if job["elapsed_seconds"] > self.threshold_seconds
            ],
        }

    def kill_job(self, session_id: str, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.session_id != session_id:
                raise KeyError(f"job '{job_id}' not found in session '{session_id}'")
            process = self._processes.get(job_id)
            signal = "cancelled_before_start"
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=3.0)
                signal = "SIGTERM"
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
                    process.join(timeout=1.0)
                    signal = "SIGKILL"
            job.status = "killed"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            self._processes.pop(job_id, None)
            self._promote_next(session_id)
        return {"killed": True, "job_id": job_id, "signal": signal}

    def kill_all(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            ids = [
                job.job_id for job in self._jobs.values()
                if job.session_id == session_id and job.status in {"running", "queued"}
            ]
        killed = [self.kill_job(session_id, job_id) for job_id in ids]
        return {"killed": len(killed), "job_ids": ids}
