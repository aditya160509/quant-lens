"""Public share links for saved screens and API keys with a daily request limit."""
from __future__ import annotations

import hashlib
import secrets
from datetime import date

from .state import _connection, get_screen, run_history


def _init(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, screen_id TEXT NOT NULL, created TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS api_keys (digest TEXT PRIMARY KEY, name TEXT NOT NULL, daily_limit INTEGER NOT NULL, created TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS api_usage (digest TEXT, day TEXT, n INTEGER NOT NULL, PRIMARY KEY (digest, day))")


def create_share(screen_id: str) -> str:
    get_screen(screen_id)
    token = secrets.token_urlsafe(18)
    with _connection() as conn:
        _init(conn)
        conn.execute("INSERT INTO shares VALUES (?, ?, ?)", (token, screen_id, date.today().isoformat()))
    return token


def shared_screen(token: str) -> dict:
    with _connection() as conn:
        _init(conn)
        row = conn.execute("SELECT screen_id FROM shares WHERE token=?", (token,)).fetchone()
    if not row:
        raise KeyError("Unknown share link")
    screen = get_screen(row[0])
    runs = run_history(row[0], 1)
    return {"name": screen["name"], "payload": screen["payload"], "latest_run": runs[0] if runs else None}


def list_shares() -> list[dict]:
    with _connection() as conn:
        _init(conn)
        return [{"token": t, "screen_id": s, "created": c} for t, s, c in conn.execute("SELECT token, screen_id, created FROM shares ORDER BY created DESC")]


def revoke_share(token: str) -> None:
    with _connection() as conn:
        _init(conn)
        conn.execute("DELETE FROM shares WHERE token=?", (token,))


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_key(name: str, daily_limit: int) -> str:
    if not name.strip() or daily_limit < 1:
        raise ValueError("Name and a daily limit of at least 1 are required")
    key = "sk_" + secrets.token_urlsafe(24)
    with _connection() as conn:
        _init(conn)
        conn.execute("INSERT INTO api_keys VALUES (?, ?, ?, ?)", (_digest(key), name.strip(), daily_limit, date.today().isoformat()))
    return key  # shown once; only the digest is stored


def list_keys() -> list[dict]:
    today = date.today().isoformat()
    with _connection() as conn:
        _init(conn)
        return [{"id": d[:10], "name": n, "daily_limit": lim, "used_today": u or 0, "created": c} for d, n, lim, c, u in conn.execute(
            "SELECT k.digest, k.name, k.daily_limit, k.created, (SELECT n FROM api_usage u WHERE u.digest=k.digest AND u.day=?) FROM api_keys k ORDER BY k.created DESC", (today,))]


def revoke_key(key_id: str) -> None:
    with _connection() as conn:
        _init(conn)
        conn.execute("DELETE FROM api_keys WHERE substr(digest,1,10)=?", (key_id,))


def spend(key: str) -> None:
    """Count one request against the key's daily limit; PermissionError for a bad key, OverflowError past the limit."""
    d, today = _digest(key), date.today().isoformat()
    with _connection() as conn:
        _init(conn)
        row = conn.execute("SELECT daily_limit FROM api_keys WHERE digest=?", (d,)).fetchone()
        if not row:
            raise PermissionError("Unknown API key")
        used = conn.execute("SELECT n FROM api_usage WHERE digest=? AND day=?", (d, today)).fetchone()
        if used and used[0] >= row[0]:
            raise OverflowError(f"Daily limit of {row[0]} requests reached")
        conn.execute("INSERT INTO api_usage VALUES (?, ?, 1) ON CONFLICT(digest, day) DO UPDATE SET n=n+1", (d, today))
