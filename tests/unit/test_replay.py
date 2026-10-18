import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.replay.buckets import Histogram
from backend.replay.engine import fold_events
from backend.replay.reducers import ReplayError
from backend.replay.state import SystemState

pytestmark = pytest.mark.unit


def test_histogram():
    histogram = Histogram()
    for duration in [1000, 1000, 2000, 10000]:
        histogram.add(duration)
    assert histogram.quantile(0.5) == 1000
    assert histogram.quantile(1) == 11000
    assert Histogram.from_dict(histogram.to_dict()).counts == histogram.counts


def test_state_roundtrip(event_factory):
    state = fold_events([event_factory(), event_factory(status="error")])
    assert SystemState.from_dict(state.to_dict()).digest() == state.digest()
    assert state.copy().digest() == state.digest()


@given(st.lists(st.integers(min_value=0, max_value=1_000_000), min_size=1, max_size=80))
@settings(max_examples=500, deadline=None)
def test_arrival_order_deterministic(durations):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from tracelore.chain import HashChain
    from tracelore.config import TraceloreConfig
    from tracelore.event import build_event

    config = TraceloreConfig(api_key="test", service="test", instance_id="property")
    chain = HashChain(config.stream_id)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        chain.seal(
            build_event(
                config,
                "http.request",
                {"method": "GET", "route": "/x", "status_code": 200},
                str(UUID(int=1)),
                str(UUID(int=index + 2)),
                None,
                start + timedelta(seconds=index),
                duration / 1000,
                "ok",
            )
        )
        for index, duration in enumerate(durations)
    ]
    digest = fold_events(events).digest()
    for seed in (1, 2, 3):
        random.Random(seed).shuffle(events)
        assert fold_events(events).digest() == digest


def test_reducers(event_factory):
    events = [
        event_factory("cache.set", {"key_hash": "a" * 64}),
        event_factory("cache.get", {"key_hash": "a" * 64, "hit": True}),
        event_factory("queue.publish", {"queue": "orders", "message_hash": "b" * 64}),
        event_factory("queue.consume", {"queue": "orders", "message_hash": "b" * 64}),
        event_factory(
            "db.query",
            {"operation": "select", "db_table": "orders", "rows": 1, "query_hash": "c" * 64},
        ),
        event_factory("error", {"exception_type": "ValueError", "message_hash": "d" * 64}),
    ]
    state = fold_events(events)
    assert state.cache.hits == 1
    assert state.queues["orders"] == 0
    assert state.db_tables["orders"]["reads"] == 1
    assert state.errors_by_type["ValueError"] == 1


def test_unknown_type(event_factory):
    event = event_factory()
    event["type"] = "unknown"
    with pytest.raises(ReplayError):
        fold_events([event])


def test_state_keys_are_reversible():
    from backend.replay.keys import pair_key, split_key

    pair = ("service|blue", "/path~1|x")
    assert split_key(pair_key(pair)) == pair
