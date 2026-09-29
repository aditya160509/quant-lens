from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.studio.schemas import (
    ArtifactManifest,
    ArtifactRef,
    DataQuality,
    ProjectRequest,
    Provenance,
    RunRequest,
    STUDIO_CONTRACT_VERSION,
)


def test_unknown_contract_version_has_upgrade_message() -> None:
    with pytest.raises(ValidationError, match=f"Upgrade the client to contract {STUDIO_CONTRACT_VERSION}"):
        ProjectRequest(contract_version="9.0", name="Research")


def test_run_request_requires_stable_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        RunRequest(
            project_id=uuid4(),
            dataset_id=uuid4(),
            strategy_version_id=uuid4(),
            idempotency_key="short",
        )


def test_artifact_manifest_serializes_identity_and_provenance() -> None:
    artifact = ArtifactRef(
        artifact_id=uuid4(),
        schema_version="1.0",
        content_hash="sha256:abc",
        media_type="application/x-parquet",
    )
    manifest = ArtifactManifest(
        manifest_id=uuid4(),
        owner_id=uuid4(),
        artifacts=[artifact],
        provenance=Provenance(engine_version="test/1.0"),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    assert manifest.contract_version == "1.0"
    assert manifest.artifacts[0].content_hash == "sha256:abc"


def test_data_quality_cannot_report_negative_missing_observations() -> None:
    with pytest.raises(ValidationError):
        DataQuality(status="observed", observations=5, missing_observations=-1)
