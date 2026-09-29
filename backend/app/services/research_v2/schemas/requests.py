"""Pydantic schemas for Research V2.

The service is not route-wired yet, but these schemas give the API layer a
strict contract when it is connected.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ResearchRunRequest(BaseModel):
    feature_id: str = Field(..., pattern=r"^(0?[1-9]|11)$")
    universe: str | list[str] = "master"
    max_symbols: int = Field(400, ge=1, le=5000)
    lookback_days: int = Field(2520, ge=120, le=8000)
    signal: str = "momentum"
    signal_csv_path: str | None = None
    event_csv_path: str | None = None
    instrument_csv_path: str | None = None
    treated_unit: str | None = None
    treatment_date: str | None = None
    weighting_scheme: Literal["equal", "value", "rank"] = "equal"
    controls: str | list[str] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("feature_id")
    @classmethod
    def normalize_feature_id(cls, value: str) -> str:
        return str(value).zfill(2)

    def as_payload(self) -> dict[str, Any]:
        base = self.model_dump(exclude={"feature_id", "payload"}, exclude_none=True)
        return {**base, **self.payload}


class ResearchRunResponse(BaseModel):
    feature_id: str
    status: str
    summary_cards: list[dict[str, Any]] = Field(default_factory=list)
    charts: dict[str, Any] = Field(default_factory=dict)
    tables: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
