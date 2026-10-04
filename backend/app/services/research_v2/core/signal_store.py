"""Saved, versioned signals in a small SQLite file (stdlib sqlite3)."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .data_loader import BACKEND_DATA

DB_PATH = BACKEND_DATA / "research_v2_signals.sqlite"
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, project_id TEXT, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS versions (signal_id INTEGER NOT NULL REFERENCES signals(id), version INTEGER NOT NULL, expr TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY (signal_id, version));
        """
    )
    return c


def save(name: str, expr: str, project_id: str | None = None) -> dict[str, Any]:
    now = time.time()
    with _LOCK, _conn() as c:
        row = c.execute("SELECT id FROM signals WHERE name=?", (name,)).fetchone()
        if row is None:
            sid = c.execute("INSERT INTO signals(name, project_id, updated_at) VALUES (?,?,?)", (name, project_id, now)).lastrowid
            version = 1
        else:
            sid = row["id"]
            version = c.execute("SELECT MAX(version) FROM versions WHERE signal_id=?", (sid,)).fetchone()[0] + 1
            c.execute("UPDATE signals SET updated_at=?, project_id=COALESCE(?, project_id) WHERE id=?", (now, project_id, sid))
        c.execute("INSERT INTO versions(signal_id, version, expr, created_at) VALUES (?,?,?,?)", (sid, version, expr, now))
    return {"id": sid, "version": version}


def list_saved() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT s.id, s.name, s.updated_at, (SELECT MAX(version) FROM versions v WHERE v.signal_id=s.id) AS latest_version FROM signals s ORDER BY s.updated_at DESC").fetchall()
    return [{"id": r["id"], "name": r["name"], "latest_version": r["latest_version"], "updated_at": r["updated_at"]} for r in rows]


def get(signal_id: int) -> dict[str, Any] | None:
    with _conn() as c:
        s = c.execute("SELECT id, name FROM signals WHERE id=?", (signal_id,)).fetchone()
        if s is None:
            return None
        vs = c.execute("SELECT version, expr, created_at FROM versions WHERE signal_id=? ORDER BY version", (signal_id,)).fetchall()
    return {"id": s["id"], "name": s["name"], "versions": [dict(v) for v in vs]}


def resolve_ref(ref: str) -> str:
    """Formula for ``"<id>@<version>"`` (version optional = latest)."""

    sid, _, ver = str(ref).partition("@")
    try:
        rec = get(int(sid))
    except ValueError:
        rec = None
    if rec is None or not rec["versions"]:
        raise ValueError(f"Unknown signal_ref '{ref}'")
    if ver:
        match = [v for v in rec["versions"] if str(v["version"]) == ver]
        if not match:
            raise ValueError(f"Signal {sid} has no version {ver}")
        return match[0]["expr"]
    return rec["versions"][-1]["expr"]
