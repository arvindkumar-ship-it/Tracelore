from datetime import UTC, datetime
from typing import Any

from backend.common.metrics import INGEST_EVENTS, SDK_DROPPED
from backend.ledger.repository import insert_events
from backend.replay.snapshots import invalidate_from

from .publisher import enqueue
from .ratelimit import check_rate
from .schemas import BatchIn, IngestResult
from .validation import split_valid

STATS_SCRIPT = """
local old=tonumber(redis.call('GET',KEYS[1]) or '0')
local new=tonumber(ARGV[1])
if new>old then redis.call('SET',KEYS[1],new,'EX',86400); return new-old end
return 0
"""


async def ingest_batch(state: Any, batch: BatchIn, key_hash: str) -> IngestResult:
    await check_rate(state.redis, key_hash, len(batch.events), state.settings.ingest_rate_limit)
    valid, rejected = split_valid(batch.events, datetime.now(UTC))
    async with state.pool.acquire() as connection, connection.transaction():
        outcome = await insert_events(
            connection, valid, datetime.now(UTC), state.settings.late_grace_seconds
        )
        await enqueue(
            connection,
            [
                event.model_dump(mode="json")
                for event in valid
                if str(event.event_id) in outcome.inserted_ids
            ],
        )
        if outcome.earliest_late_ended_at:
            await invalidate_from(connection, outcome.earliest_late_ended_at)
    rejected.extend(outcome.rejections)
    INGEST_EVENTS.labels("accepted").inc(len(outcome.inserted_ids))
    INGEST_EVENTS.labels("duplicate").inc(outcome.duplicates)
    INGEST_EVENTS.labels("rejected").inc(len(rejected))
    if batch.sdk_stats and batch.events:
        delta = await state.redis.eval(
            STATS_SCRIPT, 1, f"sdk-drop:{batch.events[0].stream_id}", batch.sdk_stats.dropped
        )
        SDK_DROPPED.inc(delta)
    return IngestResult(
        accepted=len(outcome.inserted_ids), duplicates=outcome.duplicates, rejected=rejected
    )
