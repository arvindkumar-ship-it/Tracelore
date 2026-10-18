import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from tracelore.canonical import canonical_json, compute_event_hash, sha256_hex
from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event

from backend.api.main import app


def generate() -> None:
    root = Path(__file__).resolve().parents[1]
    (root / "docs/openapi.json").write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    )
    values = [
        {},
        {"b": 2, "a": 1},
        {"unicode": "हिन्दी ☀"},
        {"nested": {"z": [True, None, 3.125]}},
        {"payload": ""},
        [1, 2, 3],
        {"number": 0.0000123},
        {"key": 'quoted"\\\n'},
        {"a": False, "b": None},
        {"emoji": "🌌"},
        {"\ue000": 1, "\U00010000": 2},
    ]
    vectors = [
        {
            "name": f"canonical-{index}",
            "kind": "json",
            "value": value,
            "sha256": sha256_hex(canonical_json(value)),
        }
        for index, value in enumerate(values)
    ]
    config = TraceloreConfig(api_key="vectors-only", service="gateway", instance_id="vectors")
    chain = HashChain(config.stream_id)
    for index, duration in enumerate([0.0, 1.0, 1.125, 123.456]):
        event = build_event(
            config,
            "http.client",
            {
                "method": "POST",
                "host": "payments",
                "downstream_service": "payments",
                "status_code": 200,
                "timeout_ms": None,
            },
            str(UUID(int=1)),
            str(UUID(int=2)),
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            duration,
            "ok",
            event_id=str(UUID(int=index + 3, version=4)),
        )
        event = chain.seal(event)
        vectors.append(
            {
                "name": f"event-{index}",
                "kind": "event",
                "value": event,
                "sha256": compute_event_hash(event),
            }
        )
    (root / "docs/hash_vectors.json").write_text(
        json.dumps(vectors, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    generate()
