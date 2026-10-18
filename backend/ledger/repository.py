from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from backend.common.metrics import LEDGER_SECONDS
from backend.ingest.schemas import EventIn, Rejection

from .records import EVENT_COLUMNS, OrderKey, wire_event


@dataclass(frozen=True)
class InsertOutcome:
    inserted_ids: frozenset[str]
    duplicates: int
    earliest_late_ended_at: datetime | None
    rejections: tuple[Rejection, ...] = ()


async def insert_events(
    connection: Any, events: list[EventIn], now: datetime, late_grace: int
) -> InsertOutcome:
    if not events:
        return InsertOutcome(frozenset(), 0, None)
    for day in sorted({event.ended_at.date() for event in events}):
        await connection.execute("SELECT ensure_partition($1)", day)
    await connection.execute(
        "CREATE TEMP TABLE ingest_stage (LIKE events INCLUDING DEFAULTS INCLUDING "
        "IDENTITY) ON COMMIT DROP"
    )
    records = [
        tuple(value[key] for key in EVENT_COLUMNS)
        for value in (event.model_dump() for event in events)
    ]
    with LEDGER_SECONDS.time():
        await connection.copy_records_to_table(
            "ingest_stage", records=records, columns=EVENT_COLUMNS
        )
        rejected = await reserve_positions(connection)
        rows = await connection.fetch(INSERT_SQL, now - timedelta(seconds=late_grace))
        await connection.execute("""
            INSERT INTO endpoint_registry(service,route,first_seen,last_seen)
            SELECT service,attributes->>'route',min(timestamp),max(ended_at) FROM ingest_stage
            WHERE type='http.request' AND event_id IN(SELECT event_id FROM ingest_reserved)
            GROUP BY service,attributes->>'route'
            ON CONFLICT(service,route) DO UPDATE SET
            first_seen=LEAST(endpoint_registry.first_seen,EXCLUDED.first_seen),
            last_seen=GREATEST(endpoint_registry.last_seen,EXCLUDED.last_seen)
        """)
    inserted = frozenset(str(row["event_id"]) for row in rows)
    late = [row["ended_at"] for row in rows if row["late"]]
    return InsertOutcome(
        inserted,
        len(events) - len(inserted) - len(rejected),
        min(late) if late else None,
        tuple(rejected),
    )


INSERT_SQL = """
INSERT INTO events (event_id,trace_id,span_id,parent_span_id,stream_id,sequence,timestamp,
ended_at,duration_ms,service,type,status,attributes,payload_hash,prev_event_hash,event_hash,late)
SELECT DISTINCT ON (event_id) event_id,trace_id,span_id,parent_span_id,stream_id,sequence,timestamp,
ended_at,duration_ms,service,type,status,attributes,payload_hash,prev_event_hash,event_hash,ended_at<$1
FROM ingest_stage WHERE event_id IN (SELECT event_id FROM ingest_reserved)
ORDER BY event_id ON CONFLICT DO NOTHING RETURNING event_id,ended_at,late
"""


async def reserve_positions(connection: Any) -> list[Rejection]:
    await connection.execute("CREATE TEMP TABLE ingest_reserved(event_id uuid) ON COMMIT DROP")
    await connection.execute("""
        WITH reserved AS (
            INSERT INTO stream_positions(stream_id,sequence,event_id,event_hash,ended_at)
            SELECT DISTINCT stream_id,sequence,event_id,event_hash,ended_at FROM ingest_stage
            ORDER BY stream_id,sequence,event_id
            ON CONFLICT DO NOTHING RETURNING event_id
        ) INSERT INTO ingest_reserved SELECT event_id FROM reserved
    """)
    conflicts = await connection.fetch("""
        SELECT s.event_id FROM ingest_stage s JOIN stream_positions p
            ON p.stream_id=s.stream_id AND p.sequence=s.sequence
            WHERE p.event_hash<>s.event_hash OR p.event_id<>s.event_id
        UNION
        SELECT s.event_id FROM ingest_stage s JOIN stream_positions p USING(event_id)
            WHERE p.event_hash<>s.event_hash OR p.ended_at<>s.ended_at
    """)
    return [Rejection(event_id=str(row["event_id"]), code="CHAIN_BROKEN") for row in conflicts]


async def get_trace_events(
    connection: Any, trace_id: str, around: datetime | None = None
) -> list[dict[str, Any]]:
    rows = await connection.fetch(
        "SELECT * FROM events WHERE trace_id=$1 "
        "AND ($2::timestamptz IS NULL OR ended_at BETWEEN "
        "$2-interval '1 day' AND $2+interval '1 day') "
        "ORDER BY timestamp,ended_at,stream_id,sequence",
        UUID(trace_id),
        around,
    )
    return [wire_event(row) for row in rows]


async def iter_events_ordered(
    connection: Any, after_key: OrderKey | None, until: datetime, batch: int = 5000
) -> AsyncGenerator[dict[str, Any], None]:
    after = after_key or (datetime.min.replace(tzinfo=until.tzinfo), "", 0)
    async with connection.transaction():
        async for row in connection.cursor(
            "SELECT * FROM events WHERE ended_at <= $4 "
            "AND (ended_at,stream_id,sequence)>($1,$2,$3) "
            "ORDER BY ended_at,stream_id,sequence",
            *after,
            until,
            prefetch=batch,
        ):
            yield wire_event(row)


async def get_window(
    connection: Any,
    start: datetime,
    end: datetime,
    service: str | None = None,
    type: str | None = None,
    limit: int = 10_001,
) -> list[dict[str, Any]]:
    rows = await connection.fetch(
        "SELECT * FROM events WHERE ended_at >= $1 AND ended_at <= $2 "
        "AND ($3::text IS NULL OR service=$3) "
        "AND ($4::text IS NULL OR type=$4) "
        "ORDER BY ended_at,stream_id,sequence LIMIT $5",
        start,
        end,
        service,
        type,
        limit,
    )
    return [wire_event(row) for row in rows]


async def get_stream_events(
    connection: Any, stream_id: str, from_seq: int = 1, to_seq: int = 2**63 - 1
) -> list[dict[str, Any]]:
    rows = await connection.fetch(
        "SELECT * FROM events WHERE stream_id=$1 AND sequence BETWEEN $2 AND $3 ORDER BY sequence",
        stream_id,
        from_seq,
        to_seq,
    )
    return [wire_event(row) for row in rows]


class LedgerRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def iter_events_ordered(
        self, after_key: OrderKey | None, until: datetime
    ) -> AsyncGenerator[dict[str, Any], None]:
        return iter_events_ordered(self.connection, after_key, until)

    async def get_trace_events(self, trace_id: str) -> list[dict[str, Any]]:
        return await get_trace_events(self.connection, trace_id)

    async def get_window(
        self, start: datetime, end: datetime, limit: int = 10_001
    ) -> list[dict[str, Any]]:
        return await get_window(self.connection, start, end, limit=limit)


async def get_traces_events(
    connection: Any, trace_ids: list[str], limit: int = 10_001
) -> list[dict[str, Any]]:
    rows = await connection.fetch(
        "SELECT * FROM events WHERE trace_id=ANY($1::uuid[]) "
        "ORDER BY ended_at,stream_id,sequence LIMIT $2",
        [UUID(trace_id) for trace_id in trace_ids],
        limit,
    )
    return [wire_event(row) for row in rows]
