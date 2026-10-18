from datetime import UTC, datetime, timedelta

import pytest

from backend.ingest.schemas import EventIn
from backend.ledger.repository import LedgerRepository, insert_events
from backend.replay.engine import replay_until
from backend.replay.snapshots import Snapshots, invalidate_from

pytestmark = pytest.mark.integration


async def test_snapshot_and_late_invalidation(databases, event_factory):
    events = [event_factory() for _ in range(10)]
    until = datetime.fromisoformat(events[-1]["ended_at"]) + timedelta(seconds=1)
    async with databases[0].acquire() as connection:
        async with connection.transaction():
            await insert_events(
                connection,
                [EventIn.model_validate(event) for event in events],
                datetime.now(UTC),
                30,
            )
        repo, snapshots = LedgerRepository(connection), Snapshots(connection)
        state = await replay_until(repo, None, until)
        await snapshots.save(state)
        assert (await replay_until(repo, snapshots, until)).digest() == state.digest()
        late = event_factory(
            started_at=datetime.fromisoformat(events[0]["timestamp"]) - timedelta(seconds=1)
        )
        async with connection.transaction():
            outcome = await insert_events(
                connection, [EventIn.model_validate(late)], datetime.now(UTC), 30
            )
            await invalidate_from(connection, outcome.earliest_late_ended_at)
        assert await snapshots.latest_before(until) is None
        assert (await replay_until(repo, snapshots, until)).digest() == (
            await replay_until(repo, None, until)
        ).digest()
