from datetime import UTC, datetime
from typing import Any

from tracelore.canonical import canonical_json, hash_payload

from .contracts import BaselineRange
from .store import predict


async def predict_cached(
    connection: Any, redis: Any, service: str, route: str, at: datetime
) -> BaselineRange:
    hour = at.astimezone(UTC).replace(minute=0, second=0, microsecond=0).isoformat()
    key = "baseline:" + hash_payload(canonical_json([service, route, hour]))
    if cached := await redis.get(key):
        result = BaselineRange.model_validate_json(cached)
        return result.model_copy(update={"at": at})
    result = await predict(connection, service, route, at)
    await redis.set(key, result.model_dump_json(), ex=60)
    return result
