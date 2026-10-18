from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, TypeVar

import asyncpg

from ..client import Tracelore
from .sql import query_attributes

Result = TypeVar("Result")


class InstrumentedConnection(asyncpg.Connection):
    tracelore: Tracelore | None = None

    async def _traced(self, query: str, call: Callable[[], Awaitable[Result]]) -> Result:
        started_at, started, status = datetime.now(UTC), perf_counter(), "ok"
        try:
            return await call()
        except BaseException:
            status = "error"
            raise
        finally:
            if self.tracelore:
                self.tracelore.record(
                    "db.query",
                    query_attributes(query),
                    started_at=started_at,
                    duration_ms=(perf_counter() - started) * 1000,
                    status=status,
                )

    async def execute(self, query: str, *args: Any, timeout: float | None = None) -> str:
        call = super().execute
        return await self._traced(query, lambda: call(query, *args, timeout=timeout))

    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None, record_class: type | None = None
    ) -> Any:
        call = super().fetch
        return await self._traced(
            query, lambda: call(query, *args, timeout=timeout, record_class=record_class)
        )

    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None, record_class: type | None = None
    ) -> Any:
        call = super().fetchrow
        return await self._traced(
            query, lambda: call(query, *args, timeout=timeout, record_class=record_class)
        )

    async def fetchval(
        self, query: str, *args: Any, column: int = 0, timeout: float | None = None
    ) -> Any:
        call = super().fetchval
        return await self._traced(query, lambda: call(query, *args, column=column, timeout=timeout))

    async def executemany(
        self, command: str, args: Iterable[Any], *, timeout: float | None = None
    ) -> None:
        call = super().executemany
        await self._traced(command, lambda: call(command, args, timeout=timeout))
