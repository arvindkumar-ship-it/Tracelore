from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from backend.api.auth import issue_token, verify_token
from backend.common.body_limit import BodyLimit
from backend.common.errors import ApiError
from backend.common.logging import redact
from backend.common.settings import Settings

pytestmark = pytest.mark.unit


def test_signed_token_expiry_and_tamper():
    settings = Settings(tracelore_secret="test-secret-long-enough-to-be-required")
    at = datetime(2026, 1, 1, tzinfo=UTC)
    value = issue_token(settings, at)
    verify_token(value.access_token, settings, at)
    with pytest.raises(ApiError):
        verify_token(value.access_token + "a", settings, at)
    with pytest.raises(ApiError):
        verify_token(value.access_token, settings, at + timedelta(hours=9))


def test_log_redaction():
    for value in (
        "Authorization: Bearer abc-secret",
        "x-api-key=abc-secret",
        '{"authorization":"Bearer abc-secret"}',
        "postgresql://user:abc-secret@host/db",
    ):
        assert "abc-secret" not in redact(value)


async def test_body_cap_and_gzip_bomb():
    import gzip

    app = FastAPI()
    app.add_middleware(BodyLimit, max_bytes=100)

    @app.post("/x")
    async def route():
        return {"ok": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as http:
        response = await http.post("/x", content=b"a" * 101)
        assert response.status_code == 413
        response = await http.post(
            "/x", content=gzip.compress(b"a" * 10000), headers={"content-encoding": "gzip"}
        )
        assert response.status_code == 413
        response = await http.post("/x", content=b"broken", headers={"content-encoding": "gzip"})
        assert response.status_code == 400
