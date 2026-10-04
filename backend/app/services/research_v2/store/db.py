"""Stdlib sqlite3 (WAL) store. One short-lived connection per call, so fresh Store instances see the same data."""
from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.data_loader import BACKEND_DATA
from .ledger import ledger_stats

DEFAULT_PATH = Path(BACKEND_DATA) / "research_v2.sqlite"
_path = DEFAULT_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, feature_id TEXT, payload TEXT, status TEXT, progress REAL, result TEXT, error TEXT, project_id TEXT, created_at TEXT, finished_at TEXT);
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, description TEXT, created_at TEXT, sealed_after TEXT);
CREATE TABLE IF NOT EXISTS preregistrations (id TEXT PRIMARY KEY, project_id TEXT, hypothesis TEXT, expected_sign TEXT, primary_test TEXT, signal TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, job_id TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS jobs_project ON jobs(project_id);
"""


def set_db_path(path: Path | str) -> None:
    global _path
    _path = Path(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(v: Any) -> str | None:
    return None if v is None else json.dumps(v, default=str)


def _loads(s: str | None) -> Any:
    return None if s is None else json.loads(s)


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._c() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    def _c(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def _run(self, sql: str, args: tuple = ()) -> None:
        c = self._c()
        try:
            with c:
                c.execute(sql, args)
        finally:
            c.close()

    def _q(self, sql: str, args: tuple = ()) -> list[dict]:
        c = self._c()
        try:
            return [dict(r) for r in c.execute(sql, args).fetchall()]
        finally:
            c.close()

    # jobs
    def save_job(self, job_id: str, feature_id: str, payload: dict, status: str = "queued", progress: float = 0.0, result: Any = None, error: str | None = None, project_id: str | None = None, created_at: str | None = None) -> None:
        finished = _now() if status in ("completed", "failed", "cancelled") else None
        self._run(
            "INSERT INTO jobs(id,feature_id,payload,status,progress,result,error,project_id,created_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, progress=excluded.progress, result=COALESCE(excluded.result, jobs.result), error=excluded.error, finished_at=COALESCE(excluded.finished_at, jobs.finished_at)",
            (job_id, feature_id, _dumps(payload), status, progress, _dumps(result), error, project_id, created_at or _now(), finished),
        )

    def get_job(self, job_id: str) -> dict | None:
        rows = self._q("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not rows:
            return None
        r = rows[0]
        r["payload"], r["result"] = _loads(r["payload"]), _loads(r["result"])
        return r

    # projects
    def create_project(self, name: str, description: str = "") -> dict:
        p = {"id": uuid.uuid4().hex[:12], "name": name, "created_at": _now()}
        self._run("INSERT INTO projects(id,name,description,created_at) VALUES(?,?,?,?)", (p["id"], name, description, p["created_at"]))
        return p

    def list_projects(self) -> list[dict]:
        return self._q("SELECT id,name,description,created_at FROM projects ORDER BY created_at DESC")

    def get_project(self, pid: str) -> dict | None:
        rows = self._q("SELECT * FROM projects WHERE id=?", (pid,))
        return rows[0] if rows else None

    def project_jobs(self, pid: str) -> list[dict]:
        out = []
        for r in self._q("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at", (pid,)):
            r["payload"], r["result"] = _loads(r["payload"]), _loads(r["result"])
            out.append(r)
        return out

    # holdout
    def holdout(self, pid: str) -> dict:
        p = self.get_project(pid)
        s = p["sealed_after"] if p else None
        return {"sealed_after": s, "unsealed": s is None}

    def set_holdout(self, pid: str, sealed_after: str | None) -> None:
        self._run("UPDATE projects SET sealed_after=? WHERE id=?", (sealed_after, pid))

    def sealed_after(self, pid: str | None) -> str | None:
        return self.holdout(pid)["sealed_after"] if pid else None

    # preregistrations
    def create_prereg(self, project_id: str, hypothesis: str, expected_sign: str, primary_test: str, signal: str) -> dict:
        r = {"id": uuid.uuid4().hex[:12], "created_at": _now()}
        self._run("INSERT INTO preregistrations VALUES(?,?,?,?,?,?,?)", (r["id"], project_id, hypothesis, expected_sign, primary_test, signal, r["created_at"]))
        return r

    def preregs(self, pid: str) -> list[dict]:
        return self._q("SELECT * FROM preregistrations WHERE project_id=? ORDER BY created_at", (pid,))

    def is_preregistered(self, pid: str | None, payload: dict) -> bool:
        sig = str(payload.get("signal") or "")
        return bool(pid and sig and any(p["signal"] == sig for p in self.preregs(pid)))

    # shares
    def create_share(self, job_id: str) -> str | None:
        if not self.get_job(job_id):
            return None
        token = secrets.token_urlsafe(24)
        self._run("INSERT INTO shares VALUES(?,?,?)", (token, job_id, _now()))
        return token

    def get_share(self, token: str) -> dict | None:
        rows = self._q("SELECT job_id, created_at FROM shares WHERE token=?", (token,))
        if not rows:
            return None
        job = self.get_job(rows[0]["job_id"])
        if not job:
            return None
        return {"feature_id": job["feature_id"], "result": job["result"], "created_at": rows[0]["created_at"]}

    # ledger
    def ledger(self, pid: str) -> dict:
        return ledger_stats(self.project_jobs(pid))


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None or _store.path != _path:
        _store = Store()
    return _store
