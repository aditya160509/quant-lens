"""Versioned, additive contracts shared by Studio service boundaries."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


STUDIO_CONTRACT_VERSION = "1.0"


class ContractVersionedModel(BaseModel):
    contract_version: str = STUDIO_CONTRACT_VERSION

    @field_validator("contract_version")
    @classmethod
    def require_supported_contract(cls, value: str) -> str:
        if value != STUDIO_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported Studio contract version '{value}'. Upgrade the client to contract {STUDIO_CONTRACT_VERSION}."
            )
        return value


class StudioWarning(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class DataQuality(BaseModel):
    status: Literal["observed", "partial", "unavailable", "synthetic"]
    observations: int = Field(ge=0)
    missing_observations: int = Field(default=0, ge=0)
    source: Optional[str] = None
    as_of: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    calendar: Optional[str] = None
    corporate_actions: Literal["adjusted", "unadjusted", "unknown"] = "unknown"
    look_ahead_check: Literal["verified", "not_verified"] = "not_verified"


class Provenance(BaseModel):
    engine_version: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    code_hash: Optional[str] = None
    dataset_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class MetricValue(BaseModel):
    value: Optional[float]
    unit: str
    status: Literal["observed", "estimated", "unavailable"]
    sample_size: int = Field(ge=0)
    methodology: str


class StudioErrorEnvelope(ContractVersionedModel):
    code: str
    message: str
    field_errors: Dict[str, str] = Field(default_factory=dict)
    retryable: bool = False
    request_id: Optional[str] = None
    documentation_hint: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class StudioResultMetadata(BaseModel):
    contract_version: str = STUDIO_CONTRACT_VERSION
    data_quality: DataQuality
    provenance: Provenance
    warnings: List[StudioWarning] = Field(default_factory=list)
    partial: bool = False
    synthetic: bool = False


class ArtifactRef(BaseModel):
    artifact_id: UUID
    schema_version: str
    content_hash: str
    media_type: str


class ArtifactManifest(ContractVersionedModel):
    manifest_id: UUID
    owner_id: UUID
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    provenance: Provenance
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectRequest(ContractVersionedModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectResponse(ContractVersionedModel):
    project_id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DatasetRequest(ContractVersionedModel):
    project_id: UUID
    dataset_id: Optional[UUID] = None
    symbols: List[str] = Field(min_length=1)
    start: datetime
    end: datetime
    frequency: str
    timezone: str
    currency: str


class DatasetResponse(ContractVersionedModel):
    dataset_id: UUID
    quality: DataQuality
    artifact: ArtifactRef
    provenance: Provenance


class RunRequest(ContractVersionedModel):
    project_id: UUID
    dataset_id: UUID
    strategy_version_id: UUID
    parameters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=200)


class RunResponse(ContractVersionedModel):
    run_id: UUID
    status: Literal["queued", "running", "cancelling", "cancelled", "succeeded", "failed"]
    created_at: datetime
    updated_at: datetime


class ResultResponse(ContractVersionedModel):
    run_id: UUID
    metrics: Dict[str, MetricValue]
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    metadata: StudioResultMetadata


class ValidationRequest(ContractVersionedModel):
    run_id: UUID
    methods: List[str] = Field(min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=200)


class ValidationResponse(ContractVersionedModel):
    validation_id: UUID
    status: Literal["queued", "running", "cancelled", "succeeded", "failed"]
    verdict: Optional[Literal["pass", "review", "fail"]] = None
    artifacts: List[ArtifactRef] = Field(default_factory=list)


class FactorRequest(ContractVersionedModel):
    project_id: UUID
    dataset_id: UUID
    definitions: List[Dict[str, Any]] = Field(min_length=1)


class FactorResponse(ContractVersionedModel):
    factor_run_id: UUID
    status: Literal["queued", "running", "cancelled", "succeeded", "failed"]
    artifacts: List[ArtifactRef] = Field(default_factory=list)


class PortfolioRequest(ContractVersionedModel):
    project_id: UUID
    run_ids: List[UUID] = Field(min_length=1)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class PortfolioResponse(ContractVersionedModel):
    portfolio_id: UUID
    weights: Dict[str, float]
    metadata: StudioResultMetadata


class ReplayRequest(ContractVersionedModel):
    run_id: UUID
    start_event_id: Optional[str] = None
    speed: float = Field(default=1.0, gt=0, le=100)


class ReplayResponse(ContractVersionedModel):
    replay_id: UUID
    event_stream_url: str
    ordered_event_hash: str


class ExportRequest(ContractVersionedModel):
    project_id: UUID
    artifact_ids: List[UUID] = Field(min_length=1)
    format: Literal["pdf", "csv", "json", "parquet", "notebook"]


class ExportResponse(ContractVersionedModel):
    export_id: UUID
    status: Literal["queued", "running", "cancelled", "succeeded", "failed"]
    artifact: Optional[ArtifactRef] = None


class PaperRunRequest(ContractVersionedModel):
    project_id: UUID
    portfolio_id: UUID
    broker: str
    idempotency_key: str = Field(min_length=8, max_length=200)


class PaperRunResponse(ContractVersionedModel):
    paper_run_id: UUID
    status: Literal["active", "paused", "stopped", "failed"]
    started_at: datetime
