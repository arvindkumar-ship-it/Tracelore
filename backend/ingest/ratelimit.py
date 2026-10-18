from typing import Any

from backend.common.errors import ApiError, Code

WINDOW_SCRIPT = """
local count=redis.call('INCRBY',KEYS[1],ARGV[1])
if count==tonumber(ARGV[1]) then redis.call('EXPIRE',KEYS[1],1) end
return count
"""


async def check_rate(redis: Any, key_hash: str, count: int, limit: int) -> None:
    current = await redis.eval(WINDOW_SCRIPT, 1, f"ingest-rate:{key_hash}", count)
    if current > limit:
        raise ApiError(Code.RATE_LIMITED, "Ingest event rate exceeded", 429)
