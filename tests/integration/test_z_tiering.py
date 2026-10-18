from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from backend.common.settings import get_settings
from backend.ingest.schemas import EventIn
from backend.ledger.repository import insert_events
from backend.ml.compression.object_store import ObjectStore
from backend.ml.compression.tiered_repository import TieredRepository
from backend.ml.compression.tiering import archive_day
from backend.replay.engine import replay_until

pytestmark = pytest.mark.integration


async def test_real_s3_archive_and_cross_tier_digest(databases, event_factory, tmp_path):
    settings = get_settings().model_copy(update={"archive_dir": tmp_path})
    store = ObjectStore(settings)
    day = datetime(2019, 1, 1, tzinfo=UTC)
    events = [event_factory(started_at=day + timedelta(seconds=index)) for index in range(10)]
    until = day + timedelta(days=1)
    async with databases[0].acquire() as connection:
        async with connection.transaction():
            await insert_events(
                connection,
                [EventIn.model_validate(event) for event in events],
                datetime.now(UTC),
                30,
            )
        repo = TieredRepository(connection, store)
        before = await replay_until(repo, None, until)
        assert await archive_day(connection, store, day.date())
        after = await replay_until(repo, None, until)
        assert after.digest() == before.digest()
        assert (await repo.get_trace_events(events[0]["trace_id"]))[0] == events[0]
        start = datetime.fromisoformat(events[0]["ended_at"])
        end = datetime.fromisoformat(events[-1]["ended_at"])
        window = await repo.get_window(start, end)
        assert {event["event_id"] for event in events} <= {event["event_id"] for event in window}


async def test_drop_guard_refuses_changed_count(databases, event_factory):
    day = datetime(2019, 1, 2, tzinfo=UTC)
    event = event_factory(started_at=day)
    async with databases[0].acquire() as connection:
        async with connection.transaction():
            await insert_events(connection, [EventIn.model_validate(event)], datetime.now(UTC), 30)
        with pytest.raises(asyncpg.PostgresError, match="partition changed"):
            await connection.execute("SELECT drop_archived_partition($1,$2)", day.date(), -1)
        assert (
            await connection.fetchval("SELECT to_regclass($1)", "public.events_20190102")
            is not None
        )
