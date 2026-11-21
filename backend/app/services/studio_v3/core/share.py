"""Read-only share links: a snapshot frozen at share time, looked up by an unguessable token."""
from __future__ import annotations

import secrets
import time

from . import store

KEY = "share:"


def create(snapshot: dict) -> str:
    token = secrets.token_urlsafe(16)
    store.kv_set(KEY + token, {**snapshot, "created": time.time()})
    return token


def get(token: str) -> dict | None:
    return store.kv_get(KEY + token)


def revoke(token: str) -> bool:
    with store.db() as con:
        return con.execute("DELETE FROM kv WHERE key = ?", (KEY + token,)).rowcount > 0
