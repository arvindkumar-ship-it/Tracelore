from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from backend.common.metrics import OPEN_INCIDENTS
from backend.ingest.projections import enqueue_projection
from backend.ingest.publisher import ANOMALIES_TOPIC

from .contracts import Signal
from .fusion import Incident, fuse

UPSERT = """
INSERT INTO incidents(id,status,opened_at,closed_at,start_event_id,start_time,services,
confidence,signals,updated_at,version,signal_count)
VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT(id) DO UPDATE SET
start_event_id=EXCLUDED.start_event_id,start_time=EXCLUDED.start_time,services=EXCLUDED.services,
confidence=EXCLUDED.confidence,signals=EXCLUDED.signals,updated_at=EXCLUDED.updated_at,
version=EXCLUDED.version,signal_count=EXCLUDED.signal_count
"""
CACHE_FIRST_SIGNALS, CACHE_RECENT_SIGNALS = 16, 240


async def locate_start_event(connection: Any, incident: Incident) -> UUID | None:
    value = await connection.fetchval(
        """
        SELECT p.event_id FROM incident_signals s JOIN stream_positions p
        ON p.event_id=(s.body->>'event_id')::uuid WHERE s.incident_id=$1
        AND s.body->>'event_id' IS NOT NULL ORDER BY p.ended_at,p.stream_id,p.sequence LIMIT 1
    """,
        incident.id,
    )
    if value is not None:
        return UUID(str(value))
    return await _metric_start(connection, incident)


async def _metric_start(connection: Any, incident: Incident) -> UUID | None:
    for signal in sorted(incident.signals, key=lambda signal: signal.estimated_start):
        value = await connection.fetchval(
            """
            SELECT event_id FROM events WHERE service=$1 AND attributes->>'route'=$2
            AND ended_at BETWEEN $3 AND $4 AND (status='error' OR duration_ms>$5)
            ORDER BY ended_at,stream_id,sequence LIMIT 1
        """,
            signal.service,
            signal.route,
            signal.estimated_start - timedelta(seconds=5),
            signal.estimated_start + timedelta(seconds=5),
            signal.baseline_high,
        )
        if value is not None:
            return UUID(str(value))
    return None


async def save_signals(connection: Any, signals: list[Signal]) -> list[Incident]:
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(17031705)")
        existing = await connection.fetch(
            "SELECT signal_id FROM incident_signals WHERE signal_id=ANY($1::text[])",
            [signal.id for signal in signals],
        )
        known = {row["signal_id"] for row in existing}
        new = [signal for signal in signals if signal.id not in known]
        rows = await connection.fetch(
            "SELECT * FROM incidents WHERE status='open' ORDER BY opened_at"
        )
        opened = [Incident.model_validate(dict(row)) for row in rows]
        changed = fuse(new, opened, await _neighbours(connection))
        for incident in changed:
            await _persist(connection, incident, {signal.id for signal in new})
    OPEN_INCIDENTS.set(len(opened))
    return changed


async def _neighbours(connection: Any) -> dict[str, set[str]]:
    edges = await connection.fetch(
        "SELECT caller,callee FROM dependency_edges WHERE last_seen>now()-interval '7 days'"
    )
    neighbours: dict[str, set[str]] = {}
    for edge in edges:
        caller, callee = edge["caller"].removeprefix("svc:"), edge["callee"].removeprefix("svc:")
        neighbours.setdefault(caller, set()).add(callee)
        neighbours.setdefault(callee, set()).add(caller)
    return neighbours


async def _persist(connection: Any, incident: Incident, new_ids: set[str]) -> None:
    fresh = [signal for signal in incident.signals if signal.id in new_ids]
    if len(incident.signals) > CACHE_FIRST_SIGNALS + CACHE_RECENT_SIGNALS:
        incident.signals = (
            incident.signals[:CACHE_FIRST_SIGNALS] + incident.signals[-CACHE_RECENT_SIGNALS:]
        )
    values = incident.model_dump()
    values["signals"] = [signal.model_dump(mode="json") for signal in incident.signals]
    fields = (
        "id",
        "status",
        "opened_at",
        "closed_at",
        "start_event_id",
        "start_time",
        "services",
        "confidence",
        "signals",
        "updated_at",
        "version",
        "signal_count",
    )
    await connection.execute(UPSERT, *(values[key] for key in fields))
    await connection.executemany(
        "INSERT INTO incident_signals(signal_id,incident_id,detected_at,body) "
        "VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
        [
            (signal.id, incident.id, signal.detected_at, signal.model_dump(mode="json"))
            for signal in fresh
        ],
    )
    incident.start_event_id = await locate_start_event(connection, incident)
    await connection.execute(
        "UPDATE incidents SET start_event_id=$2 WHERE id=$1", incident.id, incident.start_event_id
    )
    await record_change(connection, incident)


async def record_change(connection: Any, incident: Incident) -> None:
    summary = incident.model_dump(mode="json", exclude={"signals"})
    await connection.execute(
        "INSERT INTO incident_changes(incident_id,body) VALUES($1,$2)", incident.id, summary
    )
    await enqueue_projection(connection, ANOMALIES_TOPIC, str(incident.id), summary)


async def resolve_stale(connection: Any, as_of: datetime) -> int:
    rows = await connection.fetch(
        "UPDATE incidents SET status='resolved',closed_at=$1,updated_at=$1,version=version+1 "
        "WHERE status='open' AND updated_at<$2 RETURNING *",
        as_of,
        as_of - timedelta(minutes=10),
    )
    for row in rows:
        await record_change(connection, Incident.model_validate(dict(row)))
    OPEN_INCIDENTS.set(
        await connection.fetchval("SELECT count(*) FROM incidents WHERE status='open'")
    )
    return len(rows)
