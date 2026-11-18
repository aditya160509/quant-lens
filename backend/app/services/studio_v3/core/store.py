"""Saved strategies (immutable versions, one draft each), the trial ledger and the actor log. One SQLite file."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from app.services.screener_v2.core.data_loader import BACKEND_DATA

from .spec import Strategy

DB_PATH = BACKEND_DATA / "studio_v3" / "studio.sqlite"
_LOCK = threading.Lock()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (id TEXT PRIMARY KEY, name TEXT NOT NULL, folder TEXT DEFAULT '', tags TEXT DEFAULT '[]', archived INTEGER DEFAULT 0, created REAL, updated REAL, draft TEXT);
CREATE TABLE IF NOT EXISTS versions (strategy_id TEXT, version INTEGER, spec TEXT NOT NULL, hash TEXT, actor TEXT, created REAL, PRIMARY KEY (strategy_id, version));
CREATE TABLE IF NOT EXISTS trials (strategy_id TEXT, run_hash TEXT, actor TEXT, kind TEXT, sharpe REAL, returns TEXT, created REAL, PRIMARY KEY (strategy_id, run_hash));
CREATE TABLE IF NOT EXISTS runs (job_id TEXT PRIMARY KEY, strategy_id TEXT, version INTEGER, feature TEXT, run_hash TEXT, result_hash TEXT, summary TEXT, created REAL);
CREATE TABLE IF NOT EXISTS actor_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, actor TEXT, action TEXT, strategy_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""


@contextmanager
def db(path: Path | None = None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(_SCHEMA)
            yield con
            con.commit()
        finally:
            con.close()


def log(actor: str, action: str, strategy_id: str | None = None, detail: dict | None = None) -> None:
    with db() as con:
        con.execute("INSERT INTO actor_log (at, actor, action, strategy_id, detail) VALUES (?,?,?,?,?)", (time.time(), actor, action, strategy_id, json.dumps(detail or {})))


def actor_log(strategy_id: str | None = None, limit: int = 200) -> list[dict]:
    with db() as con:
        rows = con.execute("SELECT at, actor, action, strategy_id, detail FROM actor_log WHERE (? IS NULL OR strategy_id = ?) ORDER BY id DESC LIMIT ?", (strategy_id, strategy_id, limit)).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


# --- strategies -------------------------------------------------------------


def _card(con, row) -> dict:
    v = con.execute("SELECT MAX(version) v FROM versions WHERE strategy_id = ?", (row["id"],)).fetchone()["v"]
    run = con.execute("SELECT job_id, summary, created, version FROM runs WHERE strategy_id = ? AND feature = 'st01' ORDER BY created DESC LIMIT 1", (row["id"],)).fetchone()
    validated = {r["version"] for r in con.execute("SELECT version FROM runs WHERE strategy_id = ? AND feature = 'st04'", (row["id"],))}
    paper = con.execute("SELECT value FROM kv WHERE key = ?", (f"paper:{row['id']}",)).fetchone()
    on_paper = any(x["version"] == v for x in json.loads(paper["value"])) if paper else False
    status = "Paper" if on_paper else "Validated" if v in validated else "Backtested" if run else "Draft"  # Live needs real fills, which Studio does not hold yet
    last = {"job_id": run["job_id"], "at": run["created"], "version": run["version"], **json.loads(run["summary"])} if run else None
    return {"id": row["id"], "name": row["name"], "folder": row["folder"], "tags": json.loads(row["tags"]), "archived": row["archived"] == 1, "trashed": row["archived"] == 2, "created": row["created"],
            "updated": row["updated"], "version": v or 0, "has_draft": row["draft"] is not None, "status": status, "spark": (last or {}).get("spark") or [],
            "validation_expired": bool(validated and v not in validated), "last_run": last}


def list_strategies(include_archived: bool = False) -> list[dict]:
    with db() as con:
        rows = con.execute("SELECT * FROM strategies WHERE archived = 0 OR (? AND archived = 1) ORDER BY updated DESC", (int(include_archived),)).fetchall()
        cards = [_card(con, r) for r in rows]
    for c in cards:
        c["trials"] = ledger(c["id"], detail=False)
    return cards


TRASH_DAYS = 30


def trash(sid: str, restore: bool = False) -> dict:
    """Soft delete: kept 30 days, then purged on the next trash listing (H-10)."""
    with db() as con:
        con.execute("UPDATE strategies SET archived = ?, updated = ? WHERE id = ?", (0 if restore else 2, time.time(), sid))
    return get(sid)


def list_trash(now: float | None = None) -> list[dict]:
    cutoff = (now or time.time()) - TRASH_DAYS * 86400
    with db() as con:
        for r in con.execute("SELECT id FROM strategies WHERE archived = 2 AND updated < ?", (cutoff,)).fetchall():
            _purge(con, r["id"])
        rows = con.execute("SELECT * FROM strategies WHERE archived = 2 ORDER BY updated DESC").fetchall()
        return [{**_card(con, r), "purge_at": r["updated"] + TRASH_DAYS * 86400} for r in rows]


def _purge(con, sid: str) -> None:
    for t, col in (("versions", "strategy_id"), ("trials", "strategy_id"), ("runs", "strategy_id"), ("actor_log", "strategy_id"), ("strategies", "id")):
        con.execute(f"DELETE FROM {t} WHERE {col} = ?", (sid,))
    con.execute("DELETE FROM kv WHERE key LIKE ?", (f"%:{sid}",))


def hard_delete(sid: str, confirm: str, actor: str = "human") -> None:
    """Permanent. The typed confirmation must equal the strategy's name."""
    name = get(sid)["name"]
    if confirm != name:
        raise ValueError(f"Type the strategy name ({name}) to delete it for good")
    with db() as con:
        _purge(con, sid)
    log(actor, "hard_delete", None, {"id": sid, "name": name})


def search(q: str) -> list[dict]:
    """Case-insensitive substring over name, tags, hypothesis, rule text, code and params (so `rsi(` finds users of rsi) (H-8)."""
    needle = q.strip().lower()
    out = []
    for c in list_strategies():
        spec = get(c["id"])["spec"]
        fields = {"name": c["name"], "tag": " ".join(c["tags"]), "hypothesis": spec.get("hypothesis", ""),
                  "rules": " ".join([spec.get("code", ""), *(spec.get(k, "") for k in ("entry_long", "exit_long", "entry_short", "exit_short", "score", "market_filter")), *spec.get("params", {})])}
        hit = next((k for k, v in fields.items() if needle in v.lower()), None)
        if needle and hit:
            out.append({**c, "match": hit})
    return out


def create(spec: Strategy, actor: str = "human", folder: str = "") -> dict:
    sid, now = uuid.uuid4().hex[:12], time.time()
    with db() as con:
        con.execute("INSERT INTO strategies (id, name, folder, created, updated) VALUES (?,?,?,?,?)", (sid, spec.name, folder, now, now))
        con.execute("INSERT INTO versions VALUES (?,?,?,?,?,?)", (sid, 1, spec.model_dump_json(), spec.hash(), actor, now))
    log(actor, "create", sid, {"version": 1})
    return get(sid)


def get(sid: str, version: int | None = None) -> dict:
    with db() as con:
        row = con.execute("SELECT * FROM strategies WHERE id = ?", (sid,)).fetchone()
        if not row:
            raise KeyError(f"Unknown strategy {sid}")
        versions = con.execute("SELECT version, hash, actor, created FROM versions WHERE strategy_id = ? ORDER BY version", (sid,)).fetchall()
        v = version or versions[-1]["version"]
        spec = con.execute("SELECT spec FROM versions WHERE strategy_id = ? AND version = ?", (sid, v)).fetchone()
        if not spec:
            raise KeyError(f"Strategy {sid} has no version {v}")
        card = _card(con, row)
        runs = con.execute("SELECT version, summary, created FROM runs WHERE strategy_id = ? AND feature = 'st01' ORDER BY created", (sid,)).fetchall()
        claimed = next((r for r in versions if json.loads(con.execute("SELECT spec FROM versions WHERE strategy_id = ? AND version = ?", (sid, r["version"])).fetchone()["spec"]).get("regime_claim")), None)
    by_version = {r["version"]: json.loads(r["summary"]) for r in runs}  # latest backtest per version
    regime_after = bool(claimed and claimed["version"] > 1 and any(r["created"] < claimed["created"] for r in runs))
    return {**card, "version": v, "runs_by_version": by_version, "regime_written_after": regime_after, "latest": versions[-1]["version"], "spec": json.loads(spec["spec"]), "draft": json.loads(row["draft"]) if row["draft"] else None,
            "versions": [dict(r) for r in versions], "trials": ledger(sid, detail=False)}


def save_version(sid: str, spec: Strategy, actor: str = "human") -> dict:
    """A new immutable version; saving an unchanged rule returns the latest instead of adding a copy."""
    now = time.time()
    with db() as con:
        last = con.execute("SELECT version, spec FROM versions WHERE strategy_id = ? ORDER BY version DESC LIMIT 1", (sid,)).fetchone()
        if not last:
            raise KeyError(f"Unknown strategy {sid}")
        if json.loads(last["spec"]) != json.loads(spec.model_dump_json()):
            con.execute("INSERT INTO versions VALUES (?,?,?,?,?,?)", (sid, last["version"] + 1, spec.model_dump_json(), spec.hash(), actor, now))
        con.execute("UPDATE strategies SET name = ?, updated = ?, draft = NULL WHERE id = ?", (spec.name, now, sid))
    log(actor, "save_version", sid)
    return get(sid)


def save_draft(sid: str, spec: dict | None) -> None:
    with db() as con:
        con.execute("UPDATE strategies SET draft = ?, updated = ? WHERE id = ?", (json.dumps(spec) if spec is not None else None, time.time(), sid))


def update_meta(sid: str, **fields) -> dict:
    allowed = {k: (json.dumps(v) if k == "tags" else int(v) if k == "archived" else v) for k, v in fields.items() if k in {"name", "folder", "tags", "archived"} and v is not None}
    if allowed:
        with db() as con:
            con.execute(f"UPDATE strategies SET {', '.join(f'{k} = ?' for k in allowed)}, updated = ? WHERE id = ?", (*allowed.values(), time.time(), sid))
    return get(sid)


def duplicate(sid: str, actor: str = "human") -> dict:
    """Version 1 of a new strategy; the source's trial ledger is not copied (H-3)."""
    src = get(sid)
    spec = Strategy(**{**src["spec"], "name": f"{src['name']} copy"})
    out = create(spec, actor, src["folder"])
    log(actor, "duplicate", out["id"], {"from": sid})
    return out


# --- runs and the trial ledger -----------------------------------------------


def record_run(job_id: str, sid: str | None, version: int | None, feature: str, run_hash: str, result_hash: str, summary: dict) -> None:
    with db() as con:
        con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)", (job_id, sid, version, feature, run_hash, result_hash, json.dumps(summary), time.time()))


def recent_runs(limit: int = 20) -> list[dict]:
    with db() as con:
        rows = con.execute("SELECT r.*, s.name, (SELECT MAX(version) FROM versions WHERE strategy_id = r.strategy_id) latest FROM runs r LEFT JOIN strategies s ON s.id = r.strategy_id ORDER BY r.created DESC LIMIT ?", (limit,)).fetchall()
    return [{"job_id": r["job_id"], "strategy_id": r["strategy_id"], "strategy": r["name"], "version": r["version"], "feature": r["feature"], "at": r["created"],
             "run_hash": r["run_hash"], "result_hash": r["result_hash"], "settings_changed": bool(r["latest"] and r["version"] and r["latest"] > r["version"]), **json.loads(r["summary"])} for r in rows]


def record_trial(sid: str, run_hash: str, actor: str, kind: str, sharpe: float | None, returns: np.ndarray) -> bool:
    """One trial per distinct (rule, settings, data). Returns False when this exact run was already counted."""
    blob = json.dumps([round(float(x), 6) for x in returns])
    with db() as con:
        cur = con.execute("INSERT OR IGNORE INTO trials VALUES (?,?,?,?,?,?,?)", (sid, run_hash, actor, kind, sharpe, blob, time.time()))
        return cur.rowcount > 0


def effective_trials(returns: list[np.ndarray]) -> float:
    """How many independent tries the trials amount to: the participation ratio of their return correlations' eigenvalues."""
    n = len(returns)
    if n < 2:
        return float(n)
    size = min(len(r) for r in returns)
    m = np.array([r[-size:] for r in returns], dtype=float)
    keep = m.std(axis=1) > 1e-12
    flat = int((~keep).sum() > 0)  # every flat series is the same non-strategy: one trial
    m = m[keep]
    if size < 3 or len(m) < 2:
        return float(len(m) + flat)
    lam = np.clip(np.linalg.eigvalsh(np.corrcoef(m)), 0, None)
    return float(lam.sum() ** 2 / (lam**2).sum()) + flat


def ledger(sid: str, detail: bool = True) -> dict:
    with db() as con:
        rows = con.execute("SELECT run_hash, actor, kind, sharpe, returns, created FROM trials WHERE strategy_id = ? ORDER BY created", (sid,)).fetchall()
    by: dict[str, int] = {}
    for r in rows:
        group = "agents" if r["actor"].startswith("agent") else "ai_helper" if r["actor"] == "ai_helper" else "humans"
        by[group] = by.get(group, 0) + 1
    eff = effective_trials([np.array(json.loads(r["returns"])) for r in rows[-400:]]) if rows else 0.0
    out = {"raw": len(rows), "effective": round(min(eff * max(len(rows), 1) / max(min(len(rows), 400), 1), len(rows)), 1), "by_actor": by}
    if detail:
        out["trials"] = [{"run_hash": r["run_hash"], "actor": r["actor"], "kind": r["kind"], "sharpe": r["sharpe"], "at": r["created"]} for r in rows]
    return out


def kv_get(key: str, default=None):
    with db() as con:
        row = con.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(key: str, value) -> None:
    with db() as con:
        con.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))
