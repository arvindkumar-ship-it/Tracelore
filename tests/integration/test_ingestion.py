from uuid import uuid4

import httpx
import pytest
from redis.asyncio import Redis
from tracelore.canonical import hash_payload

from backend.common.errors import ApiError
from backend.common.settings import get_settings
from backend.ingest.main import app
from backend.ingest.ratelimit import check_rate

pytestmark = pytest.mark.integration


async def test_real_ingest_and_reject(databases, event_factory):
    key = "integration-" + str(uuid4())
    async with databases[0].acquire() as connection:
        await connection.execute(
            "INSERT INTO api_keys(key_hash,name) VALUES($1,$2)", hash_payload(key), "integration"
        )
    event = event_factory()
    bad = event_factory()
    bad["event_hash"] = "f" * 64
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/ingest",
                json={"batch_id": str(uuid4()), "events": [event, bad]},
                headers={"x-api-key": key},
            )
            assert response.status_code == 200, response.text
            assert (
                response.json()["accepted"] == 1
                and response.json()["rejected"][0]["code"] == "HASH_MISMATCH"
            )
            repeat = await client.post(
                "/ingest",
                json={"batch_id": str(uuid4()), "events": [event]},
                headers={"x-api-key": key},
            )
            assert repeat.json()["duplicates"] == 1
            response = await client.post(
                "/ingest", json={"wrong": "shape"}, headers={"x-api-key": key}
            )
            assert response.status_code == 400 and "error" in response.json()


async def test_redis_rate_window():
    redis = Redis.from_url(get_settings().redis_url)
    try:
        key = str(uuid4())
        await check_rate(redis, key, 4, 5)
        with pytest.raises(ApiError):
            await check_rate(redis, key, 2, 5)
        assert 0 <= await redis.ttl("ingest-rate:" + key) <= 1
    finally:
        await redis.aclose()
