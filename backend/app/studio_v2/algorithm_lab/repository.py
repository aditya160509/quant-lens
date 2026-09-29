"""Durable strategy source repository used across Studio v2 domains."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Any, Optional

from ..shared.persistence import SQLiteStore


_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


class StrategyRepository:
    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        source_root: Optional[str | Path] = None,
    ) -> None:
        self.store = store or SQLiteStore()
        self.source_root = Path(source_root) if source_root else Path(__file__).resolve().parents[1] / "storage" / "strategies"
        self.source_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(name: str) -> str:
        value = _SAFE_NAME.sub("_", name.strip()).strip("_").lower()
        return value or "strategy"

    def create(
        self,
        name: str,
        source_code: str,
        *,
        default_config: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        strategy_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not source_code.strip():
            raise ValueError("strategy source code cannot be empty")
        resolved_id = strategy_id or f"strat_{uuid.uuid4().hex[:12]}"
        file_name = f"{self._slug(name)}_{resolved_id[-6:]}.py"
        path = (self.source_root / file_name).resolve()
        if self.source_root.resolve() not in path.parents:
            raise ValueError("invalid strategy name")
        path.write_text(source_code, encoding="utf-8")
        payload = {
            "strategy_id": resolved_id,
            "name": name.strip() or resolved_id,
            "file_path": str(path),
            "source_code": source_code,
            "source_hash": hashlib.sha256(source_code.encode("utf-8")).hexdigest(),
            "default_config": dict(default_config or {}),
            "metadata": dict(metadata or {}),
        }
        return self.store.put("strategies", resolved_id, payload, create_only=True)

    def get(self, strategy_id: str) -> dict[str, Any]:
        record = self.store.get("strategies", strategy_id)
        path = Path(record["file_path"])
        if path.exists():
            record["source_code"] = path.read_text(encoding="utf-8")
        return record

    def list(self) -> list[dict[str, Any]]:
        return self.store.list("strategies", limit=1000)

    def update_source(self, strategy_id: str, source_code: str) -> dict[str, Any]:
        record = self.get(strategy_id)
        Path(record["file_path"]).write_text(source_code, encoding="utf-8")
        record["source_code"] = source_code
        record["source_hash"] = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        return self.store.put("strategies", strategy_id, record)
