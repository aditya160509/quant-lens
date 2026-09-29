from __future__ import annotations

"""
Model Lineage System (F2.6).

DAG storage for every backtest run. Each record: run_id, strategy_hash,
parent_run_id, parameters (JSONB), metrics (JSONB), timestamp, tag.
"""

import difflib
import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import orjson
    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False


class RunTag(str, Enum):
    CANDIDATE = "Candidate"
    ACTIVE = "Active"
    RETIRED = "Retired"
    DEPLOYED = "Deployed"


@dataclass
class RunRecord:
    run_id: str
    strategy_file_hash: str
    strategy_name: str
    parent_run_id: Optional[str]
    parameters: dict
    metrics: dict
    tags: List[str]
    created_at: str
    duration_seconds: float
    trade_log_path: Optional[str] = None
    equity_curve_path: Optional[str] = None
    data_freshness_snapshot: dict = field(default_factory=dict)
    data_manifest_snapshot: dict = field(default_factory=dict)
    strategy_file: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchQuery:
    dsr_min: Optional[float] = None
    pbo_max: Optional[float] = None
    sharpe_min: Optional[float] = None
    sortino_min: Optional[float] = None
    max_drawdown_max: Optional[float] = None
    date_range_start: Optional[Any] = None
    date_range_end: Optional[Any] = None
    tags: Optional[List[str]] = None
    strategy_name_contains: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass
class Edge:
    parent_run_id: str
    run_id: str
    relationship_type: str = "lineage"


@dataclass
class DiffResult:
    code_diff: List[str]
    parameter_diff: dict
    performance_diff: dict


def detect_non_default_parameters(run_params: dict, defaults: dict) -> dict:
    return {key: value for key, value in (run_params or {}).items() if key not in (defaults or {}) or value != defaults[key]}


class ModelLineage:
    """Thread-safe lineage store with optional JSON persistence."""

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._walkforward: Dict[str, List[dict]] = {}
        self._strategy_content: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._search_cache: Dict[str, List[RunRecord]] = {}
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.storage_path.read_text())
            self._runs = {row["run_id"]: RunRecord(**row) for row in payload.get("runs", [])}
            self._walkforward = payload.get("walkforward", {})
        except (OSError, ValueError, TypeError):
            self._runs, self._walkforward = {}, {}

    def _save(self) -> None:
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"runs": [run.to_dict() for run in self._runs.values()], "walkforward": self._walkforward}
            if _HAS_ORJSON:
                self.storage_path.write_bytes(orjson.dumps(payload, default=lambda value: str(value)))
            else:
                self.storage_path.write_text(json.dumps(payload, default=str))

    def compute_strategy_hash(self, file_content: str) -> str:
        return hashlib.sha256(str(file_content).encode("utf-8")).hexdigest()

    def _content_for(self, strategy_file: str) -> tuple[str, str]:
        path = Path(strategy_file)
        if path.exists() and path.is_file():
            return str(path), path.read_text(encoding="utf-8")
        # Inline strategies are content, while missing paths must not hash to
        # the path string as if that string were executable source.
        return str(strategy_file), ""

    def record_run(
        self,
        strategy_file: str,
        config: Any,
        result: Any,
        parent_run_id: Optional[str] = None,
        *,
        data_manifest_snapshot: Optional[dict[str, Any]] = None,
    ) -> str:
        path, content = self._content_for(strategy_file)
        strategy_hash = self.compute_strategy_hash(content)
        with self._lock:
            if parent_run_id is None:
                prior = [run for run in self._runs.values() if run.strategy_file_hash == strategy_hash]
                if prior:
                    parent_run_id = max(prior, key=lambda run: run.created_at).run_id
            config_dict = asdict(config) if hasattr(config, "__dataclass_fields__") else dict(config or {})
            metrics = {}
            if hasattr(result, "daily_returns"):
                from .metrics import PerformanceMetrics
                metrics = PerformanceMetrics().compute_all(result.daily_returns).to_dict()
                metrics["daily_returns"] = pd.Series(result.daily_returns).replace([np.inf, -np.inf], np.nan).fillna(0.0).tolist()
            else:
                metrics = dict(getattr(result, "metrics", {}) or {})
            run_id = str(uuid.uuid4())
            if parent_run_id and parent_run_id not in self._runs:
                raise KeyError(f"Parent run '{parent_run_id}' does not exist")
            record = RunRecord(
                run_id,
                strategy_hash,
                Path(path).name,
                parent_run_id,
                config_dict,
                metrics,
                [RunTag.CANDIDATE.value],
                datetime.now(timezone.utc).isoformat(),
                float(getattr(result, "run_duration_seconds", 0.0)),
                data_manifest_snapshot=dict(data_manifest_snapshot or {}),
                strategy_file=path,
                error=None if metrics else "empty metrics",
            )
            self._runs[run_id] = record
            self._strategy_content[strategy_hash] = content
            self._search_cache.clear()
            self._save()
            return run_id

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Lineage run '{run_id}' not found")
            return self._runs[run_id]

    def get_lineage_graph(self, strategy_file_hash: str) -> List[Edge]:
        with self._lock:
            runs = sorted((r for r in self._runs.values() if r.strategy_file_hash == strategy_file_hash), key=lambda r: r.created_at)
        edges = [Edge(r.parent_run_id, r.run_id) for r in runs if r.parent_run_id]
        self._assert_acyclic(edges)
        return edges

    @staticmethod
    def _assert_acyclic(edges: List[Edge]) -> None:
        graph: Dict[str, List[str]] = {}
        for edge in edges:
            graph.setdefault(edge.parent_run_id, []).append(edge.run_id)
        visiting, visited = set(), set()
        def visit(node: str) -> None:
            if node in visiting: raise ValueError("Lineage graph contains a cycle")
            if node in visited: return
            visiting.add(node)
            for child in graph.get(node, []): visit(child)
            visiting.remove(node); visited.add(node)
        for node in graph: visit(node)

    def diff_runs(self, run_id_a: str, run_id_b: str) -> DiffResult:
        a, b = self.get_run(run_id_a), self.get_run(run_id_b)
        code_a = self._strategy_content.get(a.strategy_file_hash, "").splitlines(keepends=True)
        code_b = self._strategy_content.get(b.strategy_file_hash, "").splitlines(keepends=True)
        keys = set(a.parameters) | set(b.parameters)
        parameter_diff = {key: {"a": a.parameters.get(key), "b": b.parameters.get(key)} for key in sorted(keys) if a.parameters.get(key) != b.parameters.get(key)}
        metric_keys = set(a.metrics) | set(b.metrics)
        performance_diff = {key: {"a": a.metrics.get(key), "b": b.metrics.get(key)} for key in sorted(metric_keys)}
        return DiffResult(list(difflib.unified_diff(code_a, code_b, fromfile=run_id_a, tofile=run_id_b)), parameter_diff, performance_diff)

    def search_runs(self, query: Any) -> List[RunRecord]:
        query = SearchQuery(**query) if isinstance(query, dict) else (query or SearchQuery())
        cache_key = repr(asdict(query))
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        result = []
        with self._lock:
            runs = list(self._runs.values())
        for run in runs:
            metrics = run.metrics
            if query.dsr_min is not None and not (metrics_value(metrics.get("dsr")) >= query.dsr_min): continue
            if query.pbo_max is not None and not (metrics_value(metrics.get("pbo")) <= query.pbo_max): continue
            if query.sharpe_min is not None and not (metrics_value(metrics.get("sharpe")) >= query.sharpe_min): continue
            if query.sortino_min is not None and not (metrics_value(metrics.get("sortino")) >= query.sortino_min): continue
            if query.max_drawdown_max is not None and not (metrics_value(metrics.get("max_drawdown")) <= query.max_drawdown_max): continue
            if query.tags and not set(query.tags).intersection(run.tags): continue
            if query.strategy_name_contains and query.strategy_name_contains.lower() not in run.strategy_name.lower(): continue
            created = pd.Timestamp(run.created_at)
            if query.date_range_start is not None and created < pd.Timestamp(query.date_range_start): continue
            if query.date_range_end is not None and created > pd.Timestamp(query.date_range_end): continue
            result.append(run)
        result.sort(key=lambda run: metrics_value(run.metrics.get("dsr")), reverse=True)
        start, end = max(0, int(query.offset)), max(0, int(query.offset)) + max(0, int(query.limit))
        selected = result[start:end]
        self._search_cache[cache_key] = list(selected)
        return selected

    def set_run_tag(self, run_id: str, tag: Any) -> None:
        record = self.get_run(run_id)
        value = tag.value if isinstance(tag, RunTag) else str(tag)
        if value not in {item.value for item in RunTag}: raise ValueError(f"Unknown run tag '{tag}'")
        with self._lock:
            record.tags = [value]
            self._search_cache.clear()
            self._save()

    def fork_run(self, run_id: str, new_config: dict) -> str:
        parent = self.get_run(run_id)
        params = dict(parent.parameters); params.update(new_config or {})
        new_id = str(uuid.uuid4())
        self._runs[new_id] = RunRecord(new_id, parent.strategy_file_hash, parent.strategy_name, parent.run_id, params, dict(parent.metrics), [RunTag.CANDIDATE.value], datetime.now(timezone.utc).isoformat(), 0.0, strategy_file=parent.strategy_file)
        self._search_cache.clear()
        self._assert_acyclic([Edge(r.parent_run_id, r.run_id) for r in self._runs.values() if r.parent_run_id])
        self._save()
        return new_id

    def record_walkforward_window(self, parent_run_id: str, window_index: int, is_sharpe: float, oos_sharpe: float, optimal_params: dict) -> None:
        self.get_run(parent_run_id)
        ratio = float(oos_sharpe / is_sharpe) if np.isfinite(is_sharpe) and is_sharpe != 0 else float("nan")
        self._walkforward.setdefault(parent_run_id, []).append({"window_index": int(window_index), "is_sharpe": float(is_sharpe), "oos_sharpe": float(oos_sharpe), "ratio": ratio, "optimal_params": dict(optimal_params or {})})
        self._search_cache.clear()
        self._save()

    def get_dag_layout(self, strategy_file_hash: str) -> dict:
        runs = [run for run in self._runs.values() if run.strategy_file_hash == strategy_file_hash]
        edges = self.get_lineage_graph(strategy_file_hash)
        levels: Dict[str, int] = {}
        def level(run_id: str) -> int:
            if run_id in levels: return levels[run_id]
            parent = self._runs[run_id].parent_run_id
            levels[run_id] = 0 if not parent else level(parent) + 1
            return levels[run_id]
        nodes = [{"id": run.run_id, "label": run.strategy_name, "tag": run.tags, "level": level(run.run_id), "metrics": run.metrics} for run in runs]
        return {"nodes": nodes, "edges": [asdict(edge) for edge in edges]}


def metrics_value(value: Any) -> float:
    try:
        converted = float(value)
        return converted if np.isfinite(converted) else -float("inf")
    except (TypeError, ValueError):
        return -float("inf")
