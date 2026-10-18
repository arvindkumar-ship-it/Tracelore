import pytest

from backend.ml.compression.encoder import encode_partition
from backend.ml.compression.summary_job import _summarize_file
from scripts.seed_e2e import fixture_events

pytestmark = pytest.mark.unit


def test_summary_counts_partition_members_without_modifying_archive(tmp_path):
    _, events = fixture_events()
    encoded = encode_partition(events[:1000], tmp_path / "summary.parquet")
    original = encoded.path.read_bytes()
    results = _summarize_file(encoded.path)
    assert sum(item["trace_count"] for item in results) == len(
        {event["trace_id"] for event in events[:1000]}
    )
    assert all(item["mode"] == "summarized" for item in results)
    assert encoded.path.read_bytes() == original
