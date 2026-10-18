from datetime import UTC, datetime, timedelta

import pytest
from tracelore.canonical import compute_event_hash

from backend.ingest.schemas import EventIn
from backend.ingest.validation import check_batch_links, validate_event
from backend.ledger.verify import verify_events

pytestmark = pytest.mark.unit


def test_schema_hash_roundtrip(event_factory):
    event = event_factory()
    parsed = EventIn.model_validate(event)
    assert parsed.model_dump(mode="json") == event
    assert isinstance(parsed.model_dump()["ended_at"], datetime)
    assert validate_event(parsed, datetime.now(UTC)) is None


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("attributes", {"unexpected": True}, "BAD_ATTRIBUTES"),
        ("duration_ms", 100.0, "BAD_TIMING"),
        ("event_hash", "a" * 64, "HASH_MISMATCH"),
    ],
)
def test_bad_event(event_factory, field, value, code):
    event = event_factory()
    event[field] = value
    assert validate_event(EventIn.model_validate(event), datetime.now(UTC)) == code


def test_future(event_factory):
    event = event_factory(started_at=datetime.now(UTC) + timedelta(hours=1))
    assert validate_event(EventIn.model_validate(event), datetime.now(UTC)) == "FUTURE_TIMESTAMP"


def test_attribute_types(event_factory):
    event = event_factory()
    event["attributes"]["status_code"] = True
    event["event_hash"] = compute_event_hash(event)
    assert validate_event(EventIn.model_validate(event), datetime.now(UTC)) == "BAD_ATTRIBUTES"


def test_broken_links(event_factory):
    events = [event_factory() for _ in range(3)]
    events[1]["prev_event_hash"] = "a" * 64
    assert len(check_batch_links([EventIn.model_validate(event) for event in events])) == 2


def test_chain_gap_vs_break(event_factory):
    events = [event_factory() for _ in range(5)]
    assert verify_events(events, events[0]["stream_id"]) == []
    assert verify_events(events[:2] + events[3:], events[0]["stream_id"])[0].kind == "gap"
    events[2]["duration_ms"] += 1
    assert any(finding.kind == "break" for finding in verify_events(events, events[0]["stream_id"]))
