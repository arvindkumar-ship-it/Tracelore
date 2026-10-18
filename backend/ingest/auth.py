import hmac
from time import monotonic
from typing import Any

from fastapi import Request
from tracelore.canonical import hash_payload

from backend.common.errors import ApiError, Code

CACHE_SECONDS = 60


class ApiKeyCache:
    def __init__(self) -> None:
        self.entries: dict[str, tuple[str, float]] = {}

    async def verify(self, connection: Any, key: str) -> str:
        digest = hash_payload(key)
        cached = self.entries.get(digest)
        if cached and cached[1] > monotonic() and hmac.compare_digest(cached[0], digest):
            return digest
        expected = await connection.fetchval(
            "SELECT key_hash FROM api_keys WHERE key_hash=$1 AND revoked_at IS NULL", digest
        )
        if expected is None or not hmac.compare_digest(expected, digest):
            raise ApiError(Code.UNAUTHORIZED, "Invalid API key", 401)
        if len(self.entries) >= 10_000:
            self.entries = {
                key: value for key, value in self.entries.items() if value[1] > monotonic()
            }
        self.entries[digest] = (expected, monotonic() + CACHE_SECONDS)
        return digest


async def require_api_key(request: Request) -> str:
    key = request.headers.get("x-api-key", "")
    if not key:
        raise ApiError(Code.UNAUTHORIZED, "Missing API key", 401)
    async with request.app.state.pool.acquire() as connection:
        return str(await request.app.state.key_cache.verify(connection, key))
