from __future__ import annotations

"""
Internal factor library (F4.10-F4.11).

40 baseline factors (momentum, reversal, low-vol, volume, higher moments).
User library CRUD with validation gates: IC t-stat > 2.0,
orthogonalized IC-IR > 0.04, half-life 3-90 days, crowding < 80th.
"""

import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .governance import FactorGovernance
from ..shared.persistence import SQLiteStore


@dataclass
class ValidationResult:
    valid: bool
    failed_gates: List[str]


@dataclass
class FactorRecord:
    factor_id: str
    name: str
    expression: str
    expression_hash: str
    naive_ic: float = np.nan
    purged_ic: float = np.nan
    icir: float = np.nan
    ic_tstat: float = np.nan
    ic_pvalue: float = np.nan
    half_life: float = np.nan
    crowding_pctile: float = np.nan
    orthogonalized_icir: float = np.nan
    regime_universality: float = np.nan
    date_added: str = ""
    is_baseline: bool = False
    is_active: bool = True
    def to_dict(self) -> dict: return asdict(self)


class FactorLibrary:
    def __init__(self, governance: FactorGovernance | None = None,
                 store: SQLiteStore | None = None) -> None:
        self._factors: Dict[str, FactorRecord] = {}
        self.store = store or SQLiteStore()
        self.governance = governance or FactorGovernance(self.store)
        self._seed_baseline()
        self._load_user_factors()

    def _load_user_factors(self) -> None:
        for payload in self.store.list("factor_library", limit=1000):
            values = {name: payload.get(name) for name in FactorRecord.__dataclass_fields__}
            self._factors[str(payload["factor_id"])] = FactorRecord(**values)

    def _seed_baseline(self) -> None:
        for group, count in (("momentum", 12), ("reversal", 8), ("low_vol", 6), ("volume_liquidity", 8), ("higher_moment", 6)):
            for index in range(count):
                expression = f"{group}_{index + 1}"; factor_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "quant360:" + expression)); self._factors[factor_id] = FactorRecord(factor_id, expression, expression, self.compute_expression_hash(expression), is_baseline=True, date_added=str(date.today()))

    def get_all_factors(self) -> List[FactorRecord]:
        self._load_user_factors()
        return [factor for factor in self._factors.values() if factor.is_active]
    def list_factors(self, active_only: bool = True) -> List[FactorRecord]:
        self._load_user_factors()
        return [factor for factor in self._factors.values() if factor.is_active or not active_only]
    def get_baseline_factors(self) -> List[FactorRecord]:
        allowed = set(self.governance.get_baseline_factors([
            factor.factor_id for factor in self._factors.values() if factor.is_baseline
        ]))
        return [factor for factor in self._factors.values() if factor.is_baseline and factor.factor_id in allowed]
    def get_user_factors(self) -> List[FactorRecord]: return [factor for factor in self._factors.values() if not factor.is_baseline and factor.is_active]
    def compute_expression_hash(self, expression: str) -> str: return hashlib.sha256(str(expression).encode("utf-8")).hexdigest()

    def validate_factor(self, metrics: dict) -> ValidationResult:
        failed = []
        if not (np.isfinite(metrics.get("ic_tstat", np.nan)) and abs(float(metrics.get("ic_tstat"))) > 2.0): failed.append("|IC t-stat| must exceed 2.0")
        if not (np.isfinite(metrics.get("orthogonalized_icir", np.nan)) and float(metrics.get("orthogonalized_icir")) > 0.04): failed.append("orthogonalized IC-IR must exceed 0.04")
        half = float(metrics.get("half_life", np.nan))
        if not (np.isfinite(half) and 3 <= half <= 90): failed.append("half-life must be between 3 and 90 trading days")
        if not (np.isfinite(metrics.get("crowding_pctile", np.nan)) and float(metrics.get("crowding_pctile")) < 80): failed.append("crowding percentile must be below 80")
        return ValidationResult(not failed, failed)

    def add_factor(self, name: str, expression: str, metrics: dict, user_name: Optional[str] = None) -> str:
        expression_hash = self.compute_expression_hash(expression); duplicate = self.get_factor_by_expression_hash(expression_hash)
        if duplicate is not None: raise ValueError(f"Expression already exists as '{duplicate.name}'")
        validation = self.validate_factor(metrics)
        if not validation.valid: raise ValueError("Factor failed validation gates: " + "; ".join(validation.failed_gates))
        data = {field: metrics.get(field, np.nan) for field in ("naive_ic", "purged_ic", "icir", "ic_tstat", "ic_pvalue", "half_life", "crowding_pctile", "orthogonalized_icir", "regime_universality")}; factor_id = str(uuid.uuid4()); record = FactorRecord(factor_id, name, expression, expression_hash, date_added=str(date.today()), **data); self._factors[factor_id] = record; self.store.put("factor_library", factor_id, record.to_dict(), create_only=True); self.governance.create_version(factor_id, expression, user_name or "unknown", "Created through factor library"); return factor_id

    def remove_factor(self, factor_id: str) -> FactorRecord:
        record = self.get_factor_by_id(factor_id)
        if record.is_baseline: raise ValueError("baseline factors cannot be removed")
        record.is_active = False
        self.store.put("factor_library", factor_id, record.to_dict())
        return record
    def restore_factor(self, factor_id: str, author: str = "unknown", notes: str = "") -> FactorRecord:
        record = self.get_factor_by_id(factor_id)
        if record.is_baseline: raise ValueError("baseline factors do not require restoration")
        record.is_active = True
        self.store.put("factor_library", factor_id, record.to_dict())
        self.governance.restore(factor_id, author, notes)
        return record
    def update_factor(self, factor_id: str, expression: str, author: str = "unknown",
                      notes: str = "") -> FactorRecord:
        record = self.get_factor_by_id(factor_id)
        if record.is_baseline: raise ValueError("baseline factors cannot be edited")
        duplicate = self.get_factor_by_expression_hash(self.compute_expression_hash(expression))
        if duplicate is not None and duplicate.factor_id != factor_id:
            raise ValueError(f"Expression already exists as '{duplicate.name}'")
        record.expression = expression
        record.expression_hash = self.compute_expression_hash(expression)
        self.store.put("factor_library", factor_id, record.to_dict())
        self.governance.create_version(factor_id, expression, author, notes)
        return record
    def get_factor_by_id(self, factor_id: str) -> FactorRecord:
        self._load_user_factors()
        return self._factors[factor_id]
    def get_factor_by_expression_hash(self, expression_hash: str) -> Optional[FactorRecord]: return next((factor for factor in self._factors.values() if factor.expression_hash == expression_hash), None)
    def get_factor_for_comparison(self) -> pd.DataFrame:
        rows = []
        for factor in self._factors.values():
            if not factor.is_active:
                continue
            governance = self.governance.status(factor.factor_id)
            rows.append({**factor.to_dict(), **governance})
        return pd.DataFrame(rows)

    def compute_quality_rating(self, metrics: dict, weights: Optional[dict] = None) -> float:
        weights = weights or {"purged_ic": 0.30, "icir": 0.30, "half_life": 0.20, "regime_universality": 0.20}; half = np.clip(float(metrics.get("half_life", 0.0)) / 90.0, 0.0, 1.0); return float(weights["purged_ic"] * np.nan_to_num(metrics.get("purged_ic", 0.0)) + weights["icir"] * np.nan_to_num(metrics.get("icir", 0.0)) + weights["half_life"] * half + weights["regime_universality"] * np.nan_to_num(metrics.get("regime_universality", 0.0)))


class FactorComparisonTable:
    def __init__(self, library: Optional[FactorLibrary] = None) -> None: self.library, self.session_factors, self._sort_column, self._ascending = library or FactorLibrary(), [], None, False
    def add_session_factor(self, expression: str, metrics: dict) -> None: self.session_factors.append({"name": expression, "expression": expression, **metrics, "is_baseline": False})
    def get_combined_table(self, include_baseline: bool = True) -> pd.DataFrame:
        frame = pd.DataFrame(([factor.to_dict() for factor in self.library.get_baseline_factors()] if include_baseline else []) + self.session_factors); return frame.sort_values(self._sort_column, ascending=self._ascending, na_position="last").reset_index(drop=True) if self._sort_column and self._sort_column in frame else frame.reset_index(drop=True)
    def sort_by(self, column: str, ascending: bool = False) -> None: self._sort_column, self._ascending = column, bool(ascending)
    def get_quality_color(self, rating: float) -> str: return "green" if rating >= 0.65 else ("amber" if rating >= 0.40 else "red")
