import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tracelore.canonical import canonical_json

from .decoder import decode_file, validate_file


def verify_roundtrip(path: Path, source: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    manifest = validate_file(path)
    digest, count = hashlib.sha256(), 0
    tails: dict[str, dict[str, Any]] = {}
    for event in decode_file(path):
        digest.update(canonical_json(event) + b"\n")
        count += 1
        previous = tails.get(event["stream_id"])
        if previous is None or previous["sequence"] < event["sequence"]:
            tails[event["stream_id"]] = {
                "sequence": event["sequence"],
                "event_hash": event["event_hash"],
            }
    if (
        digest.hexdigest() != manifest["event_digest"]
        or count != manifest["row_count"]
        or tails != manifest["chain_tails"]
    ):
        raise ValueError("archive round-trip verification failed")
    if source is not None:
        original = hashlib.sha256()
        for event in source:
            original.update(canonical_json(event) + b"\n")
        if original.hexdigest() != digest.hexdigest():
            raise ValueError("archive differs from original source")
    return manifest
