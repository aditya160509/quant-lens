from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi import FastAPI

from app.studio_v2.shared.local_user import CurrentUser, get_current_user
from app.studio_v2.data_studio.catalog import CustomDataUploader
from app.studio_v2.router import Router
from app.studio_v2.shared import data_manifest


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "ticker": ["spy", "QQQ"],
            "value": [1.25, -0.5],
        }
    )


def _encoded_sample(suffix: str) -> bytes:
    frame = _sample_frame()
    if suffix == ".csv":
        return frame.to_csv(index=False).encode("utf-8")
    if suffix == ".json":
        return frame.to_json(orient="records").encode("utf-8")
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


@pytest.mark.parametrize("suffix", [".csv", ".json", ".parquet"])
def test_custom_uploader_safely_supports_each_advertised_format(
    tmp_path: Path, suffix: str
) -> None:
    uploader = CustomDataUploader(output_dir=str(tmp_path))

    result = uploader.upload(
        _encoded_sample(suffix),
        f"sample{suffix}",
        source_name="Sample dataset",
        date_column="date",
        symbol_column="ticker",
        owner_id="private-user@example.test",
        license_status="licensed research",
        permitted_use_attested=True,
        retention_days=30,
    )

    published = tmp_path / result.storage_key
    stored = pd.read_parquet(published)
    assert result.success is True
    assert result.format == "parquet"
    assert result.checksum_sha256 == hashlib.sha256(published.read_bytes()).hexdigest()
    assert "private-user@example.test" not in result.storage_key
    assert stored["ticker"].tolist() == ["SPY", "QQQ"]
    assert not list(published.parent.glob(".upload-*.tmp"))
    assert result.governance["visibility"] == "private-owner-only"
    assert result.governance["license_status"] == "licensed research"
    assert result.governance["malware_scan"]["status"] == "passed"
    assert result.expires_at






