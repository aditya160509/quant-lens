import asyncio

import httpx
import pytest
from fastapi import FastAPI

from app.routers.studio import router
from app.services.studio.security import SecretMaterialError, assert_no_secret_material


@pytest.mark.parametrize("secret", [
    "api_key = 'abcdefghijklmnop1234567890'",
    "AKIAABCDEFGHIJKLMNOP",
    "eyJabcdefghijk.abcdefghijklmnop.abcdefghijklmnop",
    "-----BEGIN PRIVATE KEY-----\nmaterial",
])
def test_secret_material_is_rejected_without_echoing_value(secret: str) -> None:
    with pytest.raises(SecretMaterialError) as error:
        assert_no_secret_material({"nested": [{"source": secret}]})
    assert "payload.nested[0].source" in str(error.value)
    assert secret not in str(error.value)


def test_environment_secret_references_and_normal_strategy_tokens_are_allowed() -> None:
    assert_no_secret_material({"code": "token = os.environ['BROKER_TOKEN']\ndef generate_signals(data): return data", "label": "password strength factor"})


def test_studio_write_boundary_returns_typed_secret_error() -> None:
    async def exercise() -> None:
        app = FastAPI(); app.include_router(router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/studio/reports/recipes", json={
                "name": "Unsafe", "template": "custom",
                "blocks": [{"kind": "narrative", "text": "api_key='abcdefghijklmnop1234567890'"}],
            })
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "SECRET_MATERIAL_REJECTED"
        assert "abcdefghijklmnop1234567890" not in response.text

    asyncio.run(exercise())
