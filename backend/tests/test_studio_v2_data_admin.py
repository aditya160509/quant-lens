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

from app.auth.dependencies import CurrentUser, get_current_user
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


def test_custom_upload_endpoint_auth_validation_size_formula_path_and_quota(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_MAX_BYTES", str(1024 * 1024))
    monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_QUOTA_BYTES", str(1024 * 1024))
    app = FastAPI()
    app.include_router(Router())

    async def authenticated_user() -> CurrentUser:
        return CurrentUser(id="upload-owner", email="owner@example.test")

    async def post_upload(
        client: httpx.AsyncClient,
        content: bytes,
        *,
        filename: str = "sample.csv",
        source_name: str = "Sample dataset",
    ) -> httpx.Response:
        return await client.post(
            "/api/v2/data-studio/upload",
            files={"file": (filename, content, "text/csv")},
            data={
                "source_name": source_name,
                "date_column": "date",
                "symbol_column": "ticker",
                "license_status": "licensed research",
                "permitted_use_attested": "true",
                "retention_days": "30",
            },
        )

    async def exercise_api() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthenticated = await post_upload(client, _encoded_sample(".csv"))
            assert unauthenticated.status_code == 401

            app.dependency_overrides[get_current_user] = authenticated_user
            success = await post_upload(client, _encoded_sample(".csv"))
            assert success.status_code == 200, success.text
            success_payload = success.json()
            assert success_payload["success"] is True
            assert success_payload["validation_report"]["rows"] == 2
            assert len(success_payload["checksum_sha256"]) == 64
            assert "upload-owner" not in success_payload["storage_key"]
            assert success_payload["governance"]["visibility"] == "private-owner-only"
            assert success_payload["governance"]["permitted_use_attested"] is True

            inventory = await client.get("/api/v2/data-studio/uploads")
            assert inventory.status_code == 200
            assert inventory.json()["count"] == 1
            upload_id = inventory.json()["uploads"][0]["upload_id"]

            forbidden = await post_upload(
                client,
                b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
            )
            assert forbidden.status_code == 422
            assert "malware content scan" in forbidden.json()["detail"]["message"]

            monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_MAX_BYTES", "32")
            oversized = await post_upload(client, b"x" * 33)
            assert oversized.status_code == 413
            assert oversized.json()["detail"]["code"] == "upload_too_large"
            monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_MAX_BYTES", str(1024 * 1024))

            malformed = await post_upload(
                client,
                b"date,asset,value\n2024-01-02,SPY,1.0\n",
            )
            assert malformed.status_code == 422
            assert malformed.json()["detail"]["code"] == "invalid_upload"

            invalid_date = await post_upload(
                client,
                b"date,ticker,value\nnot-a-date,SPY,1.0\n",
            )
            assert invalid_date.status_code == 422
            assert "date column" in invalid_date.json()["detail"]["message"]
            invalid_symbol = await post_upload(
                client,
                b'date,ticker,value\n2024-01-02,"../../SPY",1.0\n',
            )
            assert invalid_symbol.status_code == 422
            assert "symbol column" in invalid_symbol.json()["detail"]["message"]

            traversal = await post_upload(
                client, _encoded_sample(".csv"), filename="../escape.csv"
            )
            assert traversal.status_code == 422
            assert "unsafe upload filename" in traversal.json()["detail"]["message"]
            unsafe_name = await post_upload(
                client, _encoded_sample(".csv"), source_name="../escape"
            )
            assert unsafe_name.status_code == 422

            formula = await post_upload(
                client,
                b'date,ticker,value,note\n2024-01-02,SPY,1.0,"=HYPERLINK(1)"\n',
            )
            assert formula.status_code == 422
            assert "formula-like" in formula.json()["detail"]["message"]

            monkeypatch.setenv("STUDIO_V2_CUSTOM_UPLOAD_QUOTA_BYTES", "1")
            quota = await post_upload(client, _encoded_sample(".csv"))
            assert quota.status_code == 413
            assert quota.json()["detail"]["code"] == "upload_quota_exceeded"

            deleted = await client.delete(f"/api/v2/data-studio/uploads/{upload_id}")
            assert deleted.status_code == 200
            assert deleted.json()["status"] == "deleted"
            missing = await client.delete(f"/api/v2/data-studio/uploads/{upload_id}")
            assert missing.status_code == 404

    asyncio.run(exercise_api())
    published = list((tmp_path / "uploads").glob("*/*.parquet"))
    assert len(published) == 0
    assert not list((tmp_path / "uploads").glob("*/.upload-*.tmp"))


def test_authenticated_manifest_refresh_endpoint_is_bounded_and_atomic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dataset_path = tmp_path / "data" / "sample.parquet"
    dataset_path.parent.mkdir()
    pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "close": [1.0, 2.0]}
    ).to_parquet(dataset_path)
    manifest_path = tmp_path / "manifests" / "studio_v2.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generated_at": "2000-01-01T00:00:00Z",
                "datasets": [
                    {
                        "id": "test_daily",
                        "path": "data/sample.parquet",
                        "format": "parquet",
                        "compression": "zstd",
                        "rows": 99,
                        "size_bytes": 1,
                        "date_column": "date",
                        "date_min": "2000-01-01",
                        "date_max": "2000-01-02",
                        "required_columns": ["date", "close"],
                        "sha256": "x",
                        "role": "endpoint test",
                        "provenance": {
                            "source": "test fixture",
                            "source_urls": [],
                            "license_status": "test-only",
                            "transformation_version": "test-v1",
                            "generation_command": "pytest fixture",
                            "point_in_time_policy": "not applicable",
                            "adjustment_policy": "not applicable",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    atomic_refresh = data_manifest.refresh_manifest

    def refresh_in_sandbox(dataset_ids: list[str]) -> dict:
        return atomic_refresh(dataset_ids, manifest_path=manifest_path, root=tmp_path)

    monkeypatch.setattr(data_manifest, "refresh_manifest", refresh_in_sandbox)
    app = FastAPI()
    app.include_router(Router())

    async def authenticated_user() -> CurrentUser:
        return CurrentUser(id="manifest-operator", role="authenticated")

    async def exercise_api() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthenticated = await client.post(
                "/api/v2/data-studio/manifests/refresh",
                json={"dataset_ids": ["test_daily"]},
            )
            assert unauthenticated.status_code == 401

            app.dependency_overrides[get_current_user] = authenticated_user
            unknown = await client.post(
                "/api/v2/data-studio/manifests/refresh",
                json={"dataset_ids": ["unknown"]},
            )
            assert unknown.status_code == 422
            assert "Unknown manifest dataset ids" in unknown.json()["detail"]["message"]

            refreshed = await client.post(
                "/api/v2/data-studio/manifests/refresh",
                json={"dataset_ids": ["test_daily"]},
            )
            assert refreshed.status_code == 200, refreshed.text
            payload = refreshed.json()
            assert payload["status"] == "refreshed"
            assert payload["refreshed_dataset_ids"] == ["test_daily"]
            assert payload["datasets"][0]["rows"] == 2
            assert payload["datasets"][0]["size_bytes"] == dataset_path.stat().st_size
            assert payload["datasets"][0]["sha256"] == hashlib.sha256(
                dataset_path.read_bytes()
            ).hexdigest()

    asyncio.run(exercise_api())
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk["datasets"][0]["rows"] == 2
    assert not list(manifest_path.parent.glob("*.tmp"))


def test_data_admin_openapi_declares_multipart_auth_and_explicit_schemas() -> None:
    app = FastAPI()
    app.include_router(Router())
    schema = app.openapi()
    upload = schema["paths"]["/api/v2/data-studio/upload"]["post"]
    refresh = schema["paths"]["/api/v2/data-studio/manifests/refresh"]["post"]

    assert upload["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
    assert refresh["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ManifestRefreshRequest"
    )
    assert upload["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CustomUploadResponse"
    )
    assert refresh["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ManifestRefreshResponse"
    )
    for operation in (upload, refresh):
        assert operation["security"]
        for status in ("401", "422", "500"):
            assert operation["responses"][status]["content"]["application/json"]["schema"][
                "$ref"
            ].endswith("/ErrorResponse")
    assert upload["responses"]["413"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ErrorResponse")
