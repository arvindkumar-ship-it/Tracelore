from datetime import UTC, datetime

import asyncpg
import pytest

from backend.ingest.schemas import EventIn
from backend.ledger.repository import get_trace_events, insert_events
from backend.ledger.verify import verify_stream

pytestmark = pytest.mark.integration


async def insert(connection, events):
    async with connection.transaction():
        return await insert_events(
            connection, [EventIn.model_validate(event) for event in events], datetime.now(UTC), 30
        )


async def test_duplicate_and_late(databases, event_factory):
    owner, runtime = databases
    events = [event_factory() for _ in range(5)]
    async with runtime.acquire() as connection:
        first = await insert(connection, events)
        second = await insert(connection, events)
        assert len(first.inserted_ids) == 5 and second.duplicates == 5
        assert await connection.fetchval(
            "SELECT late FROM events WHERE event_id=$1", EventIn.model_validate(events[0]).event_id
        )
        assert len(await get_trace_events(connection, events[0]["trace_id"])) == 1


async def test_append_only_both_roles(databases, event_factory):
    owner, runtime = databases
    event = event_factory()
    async with runtime.acquire() as connection:
        await insert(connection, [event])
    for pool in (owner, runtime):
        async with pool.acquire() as connection:
            for statement in (
                "UPDATE events SET status=status WHERE event_id=$1",
                "DELETE FROM events WHERE event_id=$1",
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(statement, EventIn.model_validate(event).event_id)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute("TRUNCATE events")


async def test_out_of_order_and_identity_conflict(databases, event_factory):
    from tracelore.canonical import compute_event_hash

    owner, runtime = databases
    events = [event_factory() for _ in range(100)]
    async with runtime.acquire() as connection:
        await insert(connection, events[50:])
        await insert(connection, events[:50])
        assert await verify_stream(connection, events[0]["stream_id"]) == []
        changed = events[0] | {"status": "error"}
        changed["event_hash"] = compute_event_hash(changed)
        outcome = await insert(connection, [changed])
        assert outcome.rejections[0].code == "CHAIN_BROKEN"
        assert not outcome.inserted_ids
