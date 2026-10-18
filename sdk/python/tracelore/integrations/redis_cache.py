from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from redis.asyncio import Redis

from ..canonical import hash_payload
from ..client import Tracelore

COMMANDS = {
    "GET": "cache.get",
    "MGET": "cache.get",
    "SET": "cache.set",
    "SETEX": "cache.set",
    "PSETEX": "cache.set",
    "MSET": "cache.set",
    "DEL": "cache.delete",
    "UNLINK": "cache.delete",
}


class InstrumentedRedis(Redis):
    tracelore: Tracelore | None = None

    async def execute_command(self, *args: Any, **options: Any) -> Any:
        execute: Callable[..., Awaitable[Any]] = super().execute_command
        command = str(args[0]).upper()
        event_type = COMMANDS.get(command)
        if not self.tracelore or event_type is None:
            return await execute(*args, **options)
        started_at, started, status, result = datetime.now(UTC), perf_counter(), "ok", None
        try:
            result = await execute(*args, **options)
            return result
        except BaseException:
            status = "error"
            raise
        finally:
            raw_key = args[1] if isinstance(args[1], bytes) else str(args[1]).encode()
            attributes: dict[str, Any] = {"key_hash": hash_payload(raw_key)}
            if event_type == "cache.get":
                attributes["hit"] = (
                    any(item is not None for item in result)
                    if command == "MGET" and result
                    else result is not None
                )
            self.tracelore.record(
                event_type,
                attributes,
                started_at=started_at,
                duration_ms=(perf_counter() - started) * 1000,
                status=status,
            )
