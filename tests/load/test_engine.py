from time import perf_counter

import pytest
from tracelore.canonical import canonical_json

from backend.ml.compression.decoder import decode_file
from backend.ml.compression.encoder import encode_partition
from backend.replay.engine import fold_events

pytestmark = pytest.mark.load


def test_10k_replay_under_200ms(event_factory):
    events = [event_factory() for _ in range(10000)]
    started = perf_counter()
    state = fold_events(events)
    elapsed = perf_counter() - started
    assert state.event_count == 10000 and elapsed < 0.2


def test_codec_batch_budget_and_wire_ratio(tmp_path, event_factory):
    events = [event_factory() for _ in range(1000)]
    encode_partition(events[:10], tmp_path / "warm.parquet")
    started = perf_counter()
    encoded = encode_partition(events, tmp_path / "events.parquet")
    encode_seconds = perf_counter() - started
    started = perf_counter()
    decoded = list(decode_file(encoded.path))
    decode_seconds = perf_counter() - started
    assert len(decoded) == 1000 and encode_seconds < 0.05 and decode_seconds < 0.05
    wire_bytes = sum(len(canonical_json(event)) for event in events)
    assert encoded.path.stat().st_size / wire_bytes < 0.4
