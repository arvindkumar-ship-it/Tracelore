import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from tracelore.canonical import canonical_json, compute_event_hash

from backend.ledger.records import order_key
from backend.ml.compression.decoder import decode_file, decode_trace
from backend.ml.compression.encoder import encode_partition
from backend.ml.compression.verify import verify_roundtrip

pytestmark = pytest.mark.unit


def test_lossless_unicode_nulls_gaps_and_timestamp_precision(tmp_path, event_factory):
    events = [event_factory() for _ in range(20)]
    events = events[:7] + events[9:]
    events[0]["attributes"]["route"] = "/हिन्दी/☀"
    events[0]["timestamp"] = "2026-01-01T00:00:00.000001Z"
    events[0]["event_hash"] = compute_event_hash(events[0])
    encoded = encode_partition(sorted(events, key=order_key), tmp_path / "events.parquet")
    decoded = list(decode_file(encoded.path))
    assert [canonical_json(event) for event in decoded] == [
        canonical_json(event) for event in events
    ]
    assert verify_roundtrip(encoded.path, events)["row_count"] == len(events)
    assert decode_trace(encoded.path, events[0]["trace_id"]) == [events[0]]


def test_tamper_refused(tmp_path, event_factory):
    encoded = encode_partition([event_factory()], tmp_path / "events.parquet")
    data = bytearray(encoded.path.read_bytes())
    data[len(data) // 2] ^= 1
    encoded.path.write_bytes(data)
    with pytest.raises(ValueError, match="checksum"):
        verify_roundtrip(encoded.path)


@given(st.text(max_size=40), st.integers(min_value=1, max_value=15), st.booleans())
@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_roundtrip_property(tmp_path, event_factory, route, count, orphan):
    from uuid import uuid4

    events = [
        event_factory(
            attributes={"method": "GET", "route": route, "status_code": 200},
            parent_span_id=str(uuid4()) if orphan else None,
        )
        for _ in range(count)
    ]
    encoded = encode_partition(events, tmp_path / "property.parquet")
    assert [canonical_json(event) for event in decode_file(encoded.path)] == [
        canonical_json(event) for event in events
    ]
