from datetime import timedelta
from typing import Any
from uuid import UUID

from tracelore.canonical import compute_event_hash
from tracelore.event import REQUIRED_ATTRIBUTES, format_timestamp

from backend.common.time import EPOCH, microseconds

from .schema import ATTRIBUTE_TYPES


def encode_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordinals = {event["span_id"]: index for index, event in enumerate(events)}
    sequences: dict[str, int] = {}
    return [_encode(event, ordinals, sequences) for event in events]


def _encode(
    event: dict[str, Any], ordinals: dict[str, int], sequences: dict[str, int]
) -> dict[str, Any]:
    parent = event["parent_span_id"]
    row: dict[str, Any] = {
        key: UUID(event[key]).bytes for key in ("event_id", "trace_id", "span_id")
    }
    row.update(
        parent_ordinal=ordinals.get(parent),
        parent_uuid=UUID(parent).bytes if parent and parent not in ordinals else None,
        ended_us=microseconds(event["ended_at"]),
        timestamp_delta_us=microseconds(event["ended_at"]) - microseconds(event["timestamp"]),
        sequence_delta=event["sequence"] - sequences.get(event["stream_id"], 0),
    )
    sequences[event["stream_id"]] = event["sequence"]
    row.update(
        {key: event[key] for key in ("stream_id", "duration_ms", "service", "type", "status")}
    )
    row.update({key: bytes.fromhex(event[key]) for key in ("payload_hash", "prev_event_hash")})
    for key in ATTRIBUTE_TYPES:
        value = event["attributes"].get(key)
        row[f"attr_{key}"] = (
            bytes.fromhex(value) if value is not None and key.endswith("_hash") else value
        )
    return row


def decode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans = [str(UUID(bytes=row["span_id"])) for row in rows]
    sequences: dict[str, int] = {}
    return [_decode(row, spans, sequences) for row in rows]


def _decode(row: dict[str, Any], spans: list[str], sequences: dict[str, int]) -> dict[str, Any]:
    event: dict[str, Any] = {
        key: str(UUID(bytes=row[key])) for key in ("event_id", "trace_id", "span_id")
    }
    parent = row["parent_ordinal"]
    event["parent_span_id"] = (
        spans[parent]
        if parent is not None
        else (str(UUID(bytes=row["parent_uuid"])) if row["parent_uuid"] else None)
    )
    sequence = sequences.get(row["stream_id"], 0) + row["sequence_delta"]
    sequences[row["stream_id"]] = sequence
    event.update(
        sequence=sequence,
        ended_at=format_timestamp(EPOCH + timedelta(microseconds=row["ended_us"])),
        timestamp=format_timestamp(
            EPOCH + timedelta(microseconds=row["ended_us"] - row["timestamp_delta_us"])
        ),
    )
    event.update(
        {key: row[key] for key in ("stream_id", "duration_ms", "service", "type", "status")}
    )
    event.update({key: row[key].hex() for key in ("payload_hash", "prev_event_hash")})
    event["attributes"] = {
        key: row[f"attr_{key}"].hex()
        if row[f"attr_{key}"] is not None and key.endswith("_hash")
        else row[f"attr_{key}"]
        for key in REQUIRED_ATTRIBUTES[event["type"]]
    }
    event["event_hash"] = compute_event_hash(event)
    return event
