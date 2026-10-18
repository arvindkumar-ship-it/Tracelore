"""The only Python implementation of the wire hash contract."""

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_payload(value: bytes | str | None) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return sha256_hex(data or b"")


def compute_event_hash(event: dict[str, Any]) -> str:
    return sha256_hex(canonical_json({k: v for k, v in event.items() if k != "event_hash"}))
