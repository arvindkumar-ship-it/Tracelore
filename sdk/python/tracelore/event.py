import math
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .canonical import hash_payload
from .config import TraceloreConfig

REQUIRED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "http.request": frozenset(("method", "route", "status_code")),
    "http.client": frozenset(("method", "host", "downstream_service", "status_code", "timeout_ms")),
    "db.query": frozenset(("operation", "db_table", "query_hash", "rows")),
    "cache.get": frozenset(("key_hash", "hit")),
    "cache.set": frozenset(("key_hash",)),
    "cache.delete": frozenset(("key_hash",)),
    "queue.publish": frozenset(("queue", "message_hash")),
    "queue.consume": frozenset(("queue", "message_hash")),
    "error": frozenset(("exception_type", "message_hash")),
}


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def build_event(
    config: TraceloreConfig,
    type: str,
    attributes: dict[str, Any],
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    started_at: datetime,
    duration_ms: float,
    status: str,
    payload: bytes | str | None = None,
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    if type not in REQUIRED_ATTRIBUTES or attributes.keys() != REQUIRED_ATTRIBUTES[type]:
        raise ValueError(f"invalid attributes for event type {type}")
    if status not in ("ok", "error") or not math.isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("invalid status or duration")
    duration_ms = float(round(duration_ms, 3))
    return {
        "event_id": event_id or str(uuid4()),
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "stream_id": config.stream_id,
        "timestamp": format_timestamp(started_at),
        "ended_at": format_timestamp(started_at + timedelta(milliseconds=duration_ms)),
        "duration_ms": duration_ms,
        "service": config.service,
        "type": type,
        "status": status,
        "attributes": attributes.copy(),
        "payload_hash": hash_payload(payload),
    }
