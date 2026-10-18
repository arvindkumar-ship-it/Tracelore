import json
import platform
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import TypeVar

from tracelore.canonical import canonical_json

from backend.ledger.records import order_key
from backend.ml.compression.decoder import decode_file
from backend.ml.compression.encoder import encode_partition
from backend.ml.compression.verify import verify_roundtrip
from backend.ml.counterfactual.interventions import LatencyScale
from backend.ml.counterfactual.report import build_report
from backend.replay.engine import fold_events
from scripts.seed_e2e import fixture_events

T = TypeVar("T")


def timed(operation: Callable[[], T]) -> tuple[T, float]:
    started = perf_counter()
    result = operation()
    return result, (perf_counter() - started) * 1000


def main() -> None:
    _, events = fixture_events()
    events = sorted(events, key=order_key)
    directory = Path("artifacts/local-bench")
    directory.mkdir(parents=True, exist_ok=True)
    _, replay_ms = timed(lambda: fold_events(events))
    report, simulation_ms = timed(
        lambda: build_report(events, LatencyScale(node="db:inventory", factor=0.3))
    )
    encode_partition(events[:10], directory / "warm.parquet")
    encoded, encode_ms = timed(
        lambda: encode_partition(events[:1000], directory / "events.parquet")
    )
    _, decode_ms = timed(lambda: list(decode_file(encoded.path)))
    verify_roundtrip(encoded.path, events[:1000])
    data = {
        "python": platform.python_version(),
        "events": len(events),
        "replay_ms": replay_ms,
        "simulation_ms": simulation_ms,
        "encode_1000_ms": encode_ms,
        "decode_1000_ms": decode_ms,
        "parquet_to_wire_ratio": encoded.path.stat().st_size
        / sum(len(canonical_json(event)) for event in events[:1000]),
        "simulation_digest": report.result_digest,
        "scope": (
            "Local CPU/codec measurements; not a Postgres throughput, fault accuracy, or"
            " full-stack certification."
        ),
    }
    Path("benchmarks/local.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
