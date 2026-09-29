from __future__ import annotations

"""
Auto-overfitting verdict and trial registry (F5.5-F5.6).

Traffic light: DSR > 0.5, PBO < 25%, IS/OOS > 0.60, stability > 65%.
Trial registry logs every optimization trial with lineage integration.
"""

import uuid
import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from itertools import islice
from typing import Any, Iterable, List, Optional

import numpy as np
import pandas as pd

from ..shared.persistence import SQLiteStore


@dataclass
class CriterionResult:
    name: str
    value: float
    threshold: float
    direction: str
    passed: bool


@dataclass
class VerdictResult:
    color: str
    criteria: List[CriterionResult]
    passed_count: int
    failed_count: int
    recommendations: List[str]

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class TrialRecord:
    trial_id: str = ""
    study_id: str = ""
    trial_number: int | None = None
    session_id: str = "default"
    strategy_file_hash: str = ""
    parameter_dict: dict[str, Any] = field(default_factory=dict)
    objective_value: float | None = None
    objective_name: str = "sharpe"
    objective_values: dict[str, float | None] = field(default_factory=dict)
    timestamp: str = ""
    mode: str = "bayesian"
    state: str = "complete"

    def __post_init__(self) -> None:
        if not self.trial_id:
            self.trial_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrialRecord":
        accepted = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in payload.items() if key in accepted})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudyRecord:
    study_id: str
    session_id: str = "default"
    mode: str = "bayesian"
    status: str = "running"
    strategy_file_hash: str = ""
    objective_names: list[str] = field(default_factory=list)
    objective_directions: dict[str, str] = field(default_factory=dict)
    trial_count: int = 0
    started_at: str = ""
    completed_at: str | None = None
    configuration: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OverfittingVerdict:
    def check_criterion(self, name: str, value: Any, threshold: float, direction: str) -> CriterionResult:
        try: numeric = float(value)
        except (TypeError, ValueError): numeric = np.nan
        passed = bool(np.isfinite(numeric) and ((numeric > threshold) if direction == "greater" else (numeric < threshold)))
        return CriterionResult(name, numeric, threshold, direction, passed)

    def get_recommendation(self, failed_criteria: List[str]) -> str:
        return "All criteria passed; strategy can advance." if not failed_criteria else "Investigate: " + ", ".join(failed_criteria) + "."

    def compute_verdict(self, dsr: Any, pbo: Any, mean_isoos: Any, stability: Any) -> VerdictResult:
        criteria = [self.check_criterion("DSR", dsr, 0.5, "greater"), self.check_criterion("PBO", pbo, 0.25, "less"), self.check_criterion("IS/OOS ratio", mean_isoos, 0.60, "greater"), self.check_criterion("parameter stability", stability, 0.65, "greater")]
        failed = [criterion.name for criterion in criteria if not criterion.passed]; passed = sum(criterion.passed for criterion in criteria); color = "green" if passed == 4 else ("amber" if passed == 3 else "red"); return VerdictResult(color, criteria, passed, len(criteria) - passed, [self.get_recommendation(failed)])


class TrialRegistry:
    """Durable optimizer study and trial registry.

    The SQLite document store is the source of truth. No process-local cache is
    used, so independent Router instances and workers observe completed writes
    immediately. A study is written before compute begins, its trials are
    persisted before completion, and the final result is committed last. This
    ordering leaves an interrupted study visibly ``running`` instead of falsely
    reporting a completed result with missing trials.
    """

    STUDIES_NAMESPACE = "optimizer_studies"
    TRIALS_NAMESPACE = "optimizer_trials"
    PAGE_SIZE = 1_000
    _DIRECTIONS = {
        "max": "maximize", "maximize": "maximize",
        "min": "minimize", "minimize": "minimize",
    }
    _COMPLETE_STATES = {"complete", "completed", "success", "succeeded"}

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()

    @staticmethod
    def strategy_hash(strategy_file: Any, backtest_config: Any = None) -> str:
        source = strategy_file
        if source is None and isinstance(backtest_config, dict):
            source = backtest_config.get("strategy_source")
        if source is None:
            return ""
        if isinstance(source, bytes):
            encoded = source
        else:
            encoded = json.dumps(
                source, sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _documents(self, namespace: str) -> Iterable[dict[str, Any]]:
        offset = 0
        while True:
            page = self.store.list(namespace, limit=self.PAGE_SIZE, offset=offset)
            yield from page
            if len(page) < self.PAGE_SIZE:
                return
            offset += len(page)

    @staticmethod
    def _bounded_page(limit: int, offset: int) -> tuple[int, int]:
        return min(max(int(limit), 1), 1_000), max(int(offset), 0)

    @staticmethod
    def _finite_float(value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if np.isfinite(numeric) else None

    @classmethod
    def _normalize_direction(cls, direction: Any) -> str:
        normalized = cls._DIRECTIONS.get(str(direction).strip().lower())
        if normalized is None:
            raise ValueError("objective direction must be min/minimize or max/maximize")
        return normalized

    @classmethod
    def _is_complete_state(cls, state: Any) -> bool:
        normalized = str(state or "complete").strip().lower().rsplit(".", 1)[-1]
        return normalized in cls._COMPLETE_STATES

    def start_study(
        self,
        *,
        session_id: str,
        mode: str,
        strategy_file_hash: str,
        objective_directions: dict[str, str],
        configuration: dict[str, Any] | None = None,
        study_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = study_id or str(uuid.uuid4())
        if not objective_directions:
            raise ValueError("at least one objective direction is required")
        normalized_directions = {
            str(name): self._normalize_direction(direction)
            for name, direction in objective_directions.items()
        }
        study = StudyRecord(
            study_id=identifier,
            session_id=session_id,
            mode=mode,
            strategy_file_hash=strategy_file_hash,
            objective_names=list(normalized_directions),
            objective_directions=normalized_directions,
            configuration=dict(configuration or {}),
        )
        return self.store.put(
            self.STUDIES_NAMESPACE, identifier, study.to_dict(), create_only=True
        )

    def complete_study(
        self,
        study_id: str,
        result: dict[str, Any],
        *,
        trial_count: int,
    ) -> dict[str, Any]:
        study = self.get_study(study_id)
        study.update(
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            trial_count=max(int(trial_count), 0),
            result=dict(result),
            error=None,
        )
        return self.store.put(self.STUDIES_NAMESPACE, study_id, study)

    def fail_study(self, study_id: str, error: str) -> dict[str, Any]:
        study = self.get_study(study_id)
        study.update(
            status="failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=str(error)[:2_000],
        )
        return self.store.put(self.STUDIES_NAMESPACE, study_id, study)

    def get_study(self, study_id: str) -> dict[str, Any]:
        return self.store.get(self.STUDIES_NAMESPACE, study_id)

    def list_studies(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        include_result: bool = False,
    ) -> list[dict[str, Any]]:
        bounded_limit, bounded_offset = self._bounded_page(limit, offset)
        records = (
            row for row in self._documents(self.STUDIES_NAMESPACE)
            if (session_id is None or row.get("session_id") == session_id)
            and (status is None or row.get("status") == status)
        )
        selected = list(islice(
            records, bounded_offset, bounded_offset + bounded_limit
        ))
        if include_result:
            return selected
        return [{key: value for key, value in row.items() if key != "result"} for row in selected]

    def record_trial(self, trial: TrialRecord) -> str:
        if isinstance(trial, dict):
            trial = TrialRecord.from_dict(trial)
        self.store.put(self.TRIALS_NAMESPACE, trial.trial_id, trial.to_dict())
        return trial.trial_id

    def persist_output(
        self,
        study_id: str,
        result: dict[str, Any],
        *,
        parameter_names: Iterable[str],
    ) -> dict[str, Any]:
        study = self.get_study(study_id)
        objective_names = list(study.get("objective_names") or ["objective"])
        primary_objective = objective_names[0]
        names = list(parameter_names)
        trials = result.get("trials", [])
        if not isinstance(trials, list):
            raise ValueError("optimizer result trials must be a list")
        seen_trial_ids: set[str] = set()
        for index, raw in enumerate(trials):
            if not isinstance(raw, dict):
                raise ValueError("optimizer trial rows must be objects")
            local_id = raw.get("trial_id", index)
            storage_id = f"{study_id}:{local_id}"
            if storage_id in seen_trial_ids:
                raise ValueError(f"duplicate optimizer trial_id '{local_id}'")
            seen_trial_ids.add(storage_id)
        for index, raw in enumerate(trials):
            local_id = raw.get("trial_id", index)
            objective_values = {
                name: self._finite_float(
                    raw.get(name, raw.get("objective") if len(objective_names) == 1 else None)
                )
                for name in objective_names
            }
            state = str(raw.get("state", "complete")).strip().lower().rsplit(".", 1)[-1]
            if self._is_complete_state(state) and any(
                value is None for value in objective_values.values()
            ):
                state = "invalid"
            record = TrialRecord(
                trial_id=f"{study_id}:{local_id}",
                study_id=study_id,
                trial_number=int(local_id) if isinstance(local_id, (int, np.integer)) else index,
                session_id=str(study.get("session_id", "default")),
                strategy_file_hash=str(study.get("strategy_file_hash", "")),
                parameter_dict={name: raw.get(name) for name in names if name in raw},
                objective_value=objective_values.get(primary_objective),
                objective_name=primary_objective,
                objective_values=objective_values,
                timestamp=str(raw.get("timestamp") or datetime.now(timezone.utc).isoformat()),
                mode=str(study.get("mode", "bayesian")),
                state=state,
            )
            self.record_trial(record)
        return self.complete_study(study_id, result, trial_count=len(trials))

    def get_trial(self, trial_id: str) -> TrialRecord:
        return TrialRecord.from_dict(self.store.get(self.TRIALS_NAMESPACE, trial_id))

    def list_trials(
        self,
        *,
        session_id: str | None = None,
        study_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TrialRecord]:
        bounded_limit, bounded_offset = self._bounded_page(limit, offset)
        records = (
            TrialRecord.from_dict(row) for row in self._documents(self.TRIALS_NAMESPACE)
            if (session_id is None or row.get("session_id") == session_id)
            and (study_id is None or row.get("study_id") == study_id)
        )
        return list(islice(
            records, bounded_offset, bounded_offset + bounded_limit
        ))

    def get_session_trials(
        self,
        session_id: str,
        *,
        study_id: str | None = None,
        limit: int = 1_000,
        offset: int = 0,
    ) -> List[TrialRecord]:
        return self.list_trials(
            session_id=session_id, study_id=study_id, limit=limit, offset=offset
        )

    def get_best_trial(self, strategy_hash: str, objective_name: str) -> Optional[TrialRecord]:
        candidates: list[TrialRecord] = []
        directions: set[str] = set()
        studies: dict[str, dict[str, Any]] = {}
        for row in self._documents(self.TRIALS_NAMESPACE):
            if row.get("strategy_file_hash") != strategy_hash:
                continue
            if not self._is_complete_state(row.get("state")):
                continue
            values = row.get("objective_values") or {}
            selected = values.get(objective_name)
            if selected is None and row.get("objective_name") == objective_name:
                selected = row.get("objective_value")
            numeric = self._finite_float(selected)
            if numeric is None:
                continue
            study_id = str(row.get("study_id", ""))
            if study_id:
                if study_id not in studies:
                    studies[study_id] = self.get_study(study_id)
                configured = studies[study_id].get("objective_directions", {}).get(
                    objective_name, "maximize"
                )
                directions.add(self._normalize_direction(configured))
            else:
                directions.add("maximize")
            trial = TrialRecord.from_dict(row)
            trial.objective_name = objective_name
            trial.objective_value = numeric
            candidates.append(trial)
        if not candidates:
            return None
        if len(directions) != 1:
            raise ValueError(
                f"objective '{objective_name}' has inconsistent directions across studies"
            )
        chooser = min if next(iter(directions)) == "minimize" else max
        return chooser(candidates, key=lambda trial: float(trial.objective_value))

    def get_trial_count(self, strategy_hash: str) -> int:
        count = sum(
            1 for row in self._documents(self.TRIALS_NAMESPACE)
            if row.get("strategy_file_hash") == strategy_hash
        )
        return count or 1

    def get_trials_for_lineage(self, strategy_hash: str) -> List[dict[str, Any]]:
        return [
            TrialRecord.from_dict(row).to_dict()
            for row in self._documents(self.TRIALS_NAMESPACE)
            if row.get("strategy_file_hash") == strategy_hash
        ]

    def get_search_path(self, session_id: str) -> pd.DataFrame:
        trials = self.get_session_trials(session_id)
        if not trials:
            return pd.DataFrame(
                columns=["trial_id", "session_id", "objective_value", "timestamp"]
            )
        return pd.DataFrame([trial.to_dict() for trial in trials]).sort_values("timestamp")
