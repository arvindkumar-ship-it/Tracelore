import asyncio
import heapq
from collections.abc import AsyncGenerator, Iterator
from contextlib import AsyncExitStack, aclosing
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any

from backend.ledger.records import OrderKey, order_key
from backend.ledger.repository import LedgerRepository

from .decoder import decode_file, decode_trace
from .object_store import ObjectStore


async def _async_events(iterator: Iterator[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
    try:
        while batch := await asyncio.to_thread(lambda: list(islice(iterator, 5000))):
            for event in batch:
                yield event
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


class TieredRepository:
    def __init__(self, connection: Any, store: ObjectStore) -> None:
        self.connection, self.store = connection, store
        self.hot = LedgerRepository(connection)

    async def _archives(self, until: datetime, after_key: OrderKey | None = None) -> list[Any]:
        return list(
            await self.connection.fetch(
                """
            SELECT day,object_key,manifest FROM archive_manifests
            WHERE archived_at IS NOT NULL AND day<=$1 AND ($2::date IS NULL OR day>=$2)
            ORDER BY day
        """,
                until.date(),
                after_key[0].date() if after_key else None,
            )
        )

    async def _path(self, record: Any) -> Path:
        path = (
            self.store.settings.archive_dir
            / str(record["day"])
            / record["object_key"].split("/")[-1]
        )
        return await self.store.download(
            record["object_key"], path, expected_manifest=record["manifest"]
        )

    async def iter_events_ordered(
        self, after_key: OrderKey | None, until: datetime
    ) -> AsyncGenerator[dict[str, Any], None]:
        async with self.connection.transaction(), AsyncExitStack() as stack:
            await self.connection.execute("LOCK TABLE events IN ACCESS SHARE MODE")
            sources = [
                await stack.enter_async_context(
                    aclosing(self.hot.iter_events_ordered(after_key, until))
                )
            ]
            for archive in await self._archives(until, after_key):
                source = _async_events(iter(decode_file(await self._path(archive))))
                sources.append(await stack.enter_async_context(aclosing(source)))
            async for event in _merge(sources, after_key, until):
                yield event

    async def get_trace_events(self, trace_id: str) -> list[dict[str, Any]]:
        async with self.connection.transaction():
            await self.connection.execute("LOCK TABLE events IN ACCESS SHARE MODE")
            events = await self.hot.get_trace_events(trace_id)
            for record in await self._archives(datetime.max.replace(tzinfo=UTC)):
                events.extend(
                    await asyncio.to_thread(decode_trace, await self._path(record), trace_id)
                )
            return sorted(
                {event["event_id"]: event for event in events}.values(),
                key=lambda event: (event["timestamp"], event["ended_at"]),
            )

    async def get_window(
        self, start: datetime, end: datetime, limit: int = 10_001
    ) -> list[dict[str, Any]]:
        events = []
        async with aclosing(self.iter_events_ordered((start, "", 0), end)) as iterator:
            async for event in iterator:
                events.append(event)
                if len(events) == limit:
                    break
        return events

    async def get_traces_events(
        self, trace_ids: list[str], limit: int = 10_001
    ) -> list[dict[str, Any]]:
        from backend.ledger.repository import get_traces_events

        async with self.connection.transaction():
            await self.connection.execute("LOCK TABLE events IN ACCESS SHARE MODE")
            events = await get_traces_events(self.connection, trace_ids, limit)
            wanted = set(trace_ids)
            for archive in await self._archives(datetime.max.replace(tzinfo=UTC)):
                if len(events) >= limit:
                    break
                path = await self._path(archive)
                events.extend(
                    await asyncio.to_thread(_matching_traces, path, wanted, limit - len(events))
                )
            return sorted({event["event_id"]: event for event in events}.values(), key=order_key)[
                :limit
            ]


async def _merge(
    sources: list[Any], after_key: OrderKey | None, until: datetime
) -> AsyncGenerator[dict[str, Any], None]:
    heap: list[Any] = []
    for index, source in enumerate(sources):
        if (event := await anext(source, None)) is not None:
            heapq.heappush(heap, (order_key(event), index, event))
    previous = None
    while heap:
        key, index, event = heapq.heappop(heap)
        if key != previous and (after_key is None or key > after_key) and key[0] <= until:
            yield event
            previous = key
        if (next_event := await anext(sources[index], None)) is not None:
            heapq.heappush(heap, (order_key(next_event), index, next_event))


def _matching_traces(path: Path, wanted: set[str], limit: int) -> list[dict[str, Any]]:
    events = []
    for event in decode_file(path):
        if event["trace_id"] in wanted:
            events.append(event)
            if len(events) >= limit:
                break
    return events
