from datetime import datetime
from typing import Any
from uuid import UUID

from tracelore.event import format_timestamp

EVENT_COLUMNS = (
    "event_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "stream_id",
    "sequence",
    "timestamp",
    "ended_at",
    "duration_ms",
    "service",
    "type",
    "status",
    "attributes",
    "payload_hash",
    "prev_event_hash",
    "event_hash",
)
OrderKey = tuple[datetime, str, int]


def wire_event(row: Any) -> dict[str, Any]:
    event = {key: row[key] for key in EVENT_COLUMNS}
    for key, value in event.items():
        if isinstance(value, UUID):
            event[key] = str(value)
        elif isinstance(value, datetime):
            event[key] = format_timestamp(value)
    return event


def order_key(event: dict[str, Any]) -> OrderKey:
    ended_at = event["ended_at"]
    if isinstance(ended_at, str):
        ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    return ended_at, event["stream_id"], event["sequence"]
