import re
from collections import defaultdict
from datetime import datetime, timedelta

from tracelore.canonical import compute_event_hash
from tracelore.event import REQUIRED_ATTRIBUTES

from .schemas import EventIn, Rejection

HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
INTEGER_FIELDS = {"rows", "status_code", "timeout_ms"}
NULLABLE_FIELDS = {"rows", "db_table", "status_code", "timeout_ms"}


def valid_attributes(event: EventIn) -> bool:
    if event.attributes.keys() != REQUIRED_ATTRIBUTES[event.type]:
        return False
    for key, value in event.attributes.items():
        if value is None:
            if key not in NULLABLE_FIELDS:
                return False
        elif key in INTEGER_FIELDS:
            if type(value) is not int or value < 0:
                return False
        elif key == "hit":
            if type(value) is not bool:
                return False
        elif not isinstance(value, str) or len(value) > 500:
            return False
        elif key.endswith("_hash") and not HASH_PATTERN.fullmatch(value):
            return False
    if event.type == "http.request" and event.attributes["status_code"] is None:
        return False
    status_code = event.attributes.get("status_code")
    if status_code is not None and not 100 <= status_code <= 599:
        return False
    if any(
        value is not None and value > 2**63 - 1
        for key, value in event.attributes.items()
        if key in INTEGER_FIELDS
    ):
        return False
    return event.attributes.get("operation", "select") in (
        "select",
        "insert",
        "update",
        "delete",
        "other",
    )


def validate_event(event: EventIn, now: datetime) -> str | None:
    if not valid_attributes(event):
        return "BAD_ATTRIBUTES"
    difference = (event.ended_at - event.timestamp).total_seconds() * 1000
    if difference < 0 or abs(difference - event.duration_ms) >= 1:
        return "BAD_TIMING"
    if event.timestamp > now + timedelta(minutes=5):
        return "FUTURE_TIMESTAMP"
    try:
        if compute_event_hash(event.model_dump(mode="json")) != event.event_hash:
            return "HASH_MISMATCH"
    except (ValueError, TypeError):
        return "HASH_MISMATCH"
    if not event.stream_id.startswith(event.service + ":"):
        return "BAD_ATTRIBUTES"
    return None


def check_batch_links(events: list[EventIn]) -> list[Rejection]:
    streams: dict[str, dict[int, EventIn]] = defaultdict(dict)
    rejected: dict[str, Rejection] = {}
    for event in events:
        existing = streams[event.stream_id].get(event.sequence)
        if existing and existing.event_hash != event.event_hash:
            for item in (existing, event):
                rejected[str(item.event_id)] = Rejection(
                    event_id=str(item.event_id), code="CHAIN_BROKEN"
                )
        streams[event.stream_id][event.sequence] = event
    for stream in streams.values():
        ordered = sorted(stream.values(), key=lambda event: event.sequence)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if (
                current.sequence == previous.sequence + 1
                and current.prev_event_hash != previous.event_hash
            ):
                for item in (previous, current):
                    rejected[str(item.event_id)] = Rejection(
                        event_id=str(item.event_id), code="CHAIN_BROKEN"
                    )
    return list(rejected.values())


def split_valid(events: list[EventIn], now: datetime) -> tuple[list[EventIn], list[Rejection]]:
    rejected = [
        Rejection(event_id=str(event.event_id), code=code)
        for event in events
        if (code := validate_event(event, now)) is not None
    ]
    by_id: dict[str, list[EventIn]] = defaultdict(list)
    for event in events:
        by_id[str(event.event_id)].append(event)
    for event_id, copies in by_id.items():
        if len({event.event_hash for event in copies}) > 1:
            rejected.append(Rejection(event_id=event_id, code="CHAIN_BROKEN"))
    rejected.extend(check_batch_links(events))
    bad_ids = {item.event_id for item in rejected}
    return [event for event in events if str(event.event_id) not in bad_ids], list(
        {item.event_id: item for item in rejected}.values()
    )
