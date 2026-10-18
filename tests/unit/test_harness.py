from datetime import UTC, datetime

import pytest
from tracelore.canonical import canonical_json, sha256_hex

from bench.faults.catalogue import load_catalogue
from bench.scorer import false_positive_rate, score_scenario
from bench.synth.history_generator import generate

pytestmark = pytest.mark.unit


def test_catalogue_and_seeded_history():
    faults = load_catalogue()
    assert len(faults) == 45 and len({fault.id for fault in faults}) == 45
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = list(generate(start, 1, 19))[:300]
    second = list(generate(start, 1, 19))[:300]
    assert sha256_hex(canonical_json(first)) == sha256_hex(canonical_json(second))


def test_scorer_known_answer(event_factory):
    event = event_factory(status="error")
    fault = next(fault for fault in load_catalogue() if fault.id == "B07")
    at = datetime(2026, 1, 1, tzinfo=UTC)
    incident = {"id": "i", "opened_at": at, "start_event_id": event["event_id"]}
    result = score_scenario(fault, at, [event], [incident], [])
    assert result["exact_start"] is True and result["root_cause_correct"] is None


def test_false_positive_windows():
    from datetime import timedelta

    at = datetime(2026, 1, 1, tzinfo=UTC)
    result = false_positive_rate(at, at + timedelta(hours=24), [at + timedelta(hours=3)])
    assert result["rate"] == pytest.approx(1 / 24)
