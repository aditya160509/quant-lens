"""Token-gated collaborative kernel sessions over WebSocket."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import WebSocket

from ..shared.persistence import SQLiteStore, utc_now


class CollaboratorSession:
    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self.store = store or SQLiteStore()
        self._connections: dict[str, dict[str, WebSocket]] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _connection_lock(self) -> asyncio.Lock:
        """Create the lock in the running loop instead of at router startup."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def create(self, session_id: str, primary_user_id: str, name: str = "Owner") -> dict[str, Any]:
        payload = {
            "session_id": session_id,
            "primary_user_id": primary_user_id,
            "participants": {
                primary_user_id: {
                    "user_id": primary_user_id,
                    "name": name,
                    "role": "owner",
                    "connected_since": None,
                    "cursor_position": None,
                }
            },
        }
        return self.store.put("collaboration_sessions", session_id, payload)

    def invite(
        self,
        session_id: str,
        user_id: str,
        role: str,
        *,
        name: Optional[str] = None,
        expires_minutes: int = 60,
    ) -> dict[str, Any]:
        if role not in {"read", "edit"}:
            raise ValueError("role must be 'read' or 'edit'")
        if not self.store.maybe_get("collaboration_sessions", session_id):
            self.create(session_id, "owner")
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, min(expires_minutes, 1440)))
        self.store.put(
            "collaboration_invites",
            token_hash,
            {
                "session_id": session_id,
                "user_id": user_id,
                "name": name or user_id,
                "role": role,
                "expires_at": expires_at.isoformat(),
                "used": False,
            },
            create_only=True,
        )
        return {"invite_token": raw_token, "expires_at": expires_at.isoformat()}

    def _consume_invite(self, session_id: str, raw_token: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        invite = self.store.get("collaboration_invites", token_hash)
        if invite["session_id"] != session_id:
            raise PermissionError("invite does not belong to this session")
        if datetime.fromisoformat(invite["expires_at"]) <= datetime.now(timezone.utc):
            raise PermissionError("invite has expired")
        invite["used"] = True
        invite["used_at"] = utc_now()
        self.store.put("collaboration_invites", token_hash, invite)
        return invite

    async def join(
        self,
        session_id: str,
        invite_token: str,
        websocket: WebSocket,
        initial_state: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        invite = self._consume_invite(session_id, invite_token)
        await websocket.accept()
        participant = {
            "user_id": invite["user_id"],
            "name": invite["name"],
            "role": invite["role"],
            "connected_since": utc_now(),
            "cursor_position": None,
        }
        session = self.store.get("collaboration_sessions", session_id)
        session.setdefault("participants", {})[participant["user_id"]] = participant
        self.store.put("collaboration_sessions", session_id, session)
        async with self._connection_lock():
            self._connections.setdefault(session_id, {})[participant["user_id"]] = websocket
        await websocket.send_json(
            {
                "type": "session_snapshot",
                "participant": participant,
                "participants": list(session["participants"].values()),
                "state": initial_state or {},
            }
        )
        await self.broadcast(session_id, {"type": "participant_joined", **participant}, exclude=participant["user_id"])
        return participant

    async def broadcast(
        self,
        session_id: str,
        message: dict[str, Any],
        *,
        exclude: Optional[str] = None,
    ) -> None:
        async with self._connection_lock():
            targets = list(self._connections.get(session_id, {}).items())
        stale: list[str] = []
        for user_id, websocket in targets:
            if user_id == exclude:
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(user_id)
        for user_id in stale:
            await self.leave(session_id, user_id)

    async def receive(self, session_id: str, user_id: str, message: dict[str, Any]) -> None:
        session = self.store.get("collaboration_sessions", session_id)
        participant = session.get("participants", {}).get(user_id)
        if not participant:
            raise PermissionError("participant is not registered")
        message_type = message.get("type")
        if participant["role"] == "read" and message_type in {"code_edit", "cell_execute", "cell_executed"}:
            raise PermissionError("read-only participants cannot edit or execute")
        if message_type == "cursor_update":
            participant["cursor_position"] = message.get("position")
            self.store.put("collaboration_sessions", session_id, session)
        await self.broadcast(
            session_id,
            {"user_id": user_id, "name": participant["name"], **message},
            exclude=user_id,
        )

    async def leave(self, session_id: str, user_id: str) -> None:
        async with self._connection_lock():
            self._connections.get(session_id, {}).pop(user_id, None)
        session = self.store.maybe_get("collaboration_sessions", session_id)
        if session and user_id in session.get("participants", {}):
            session["participants"][user_id]["connected_since"] = None
            self.store.put("collaboration_sessions", session_id, session)
        await self.broadcast(session_id, {"type": "participant_left", "user_id": user_id}, exclude=user_id)

    def get_participants(self, session_id: str) -> list[dict[str, Any]]:
        session = self.store.get("collaboration_sessions", session_id)
        return list(session.get("participants", {}).values())
