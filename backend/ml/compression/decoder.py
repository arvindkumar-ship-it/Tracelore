import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow.parquet as parquet

from .codec import decode_rows
from .encoder import file_hash
from .schema import SCHEMA_VERSION
from .trace_index import find_groups


def validate_file(path: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(path.with_suffix(".manifest.json").read_text())
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported archive schema version")
    if (
        file_hash(path) != manifest["sha256"]
        or file_hash(path.with_suffix(".index.parquet")) != manifest["index_sha256"]
    ):
        raise ValueError("archive checksum mismatch")
    return manifest


def decode_file(path: Path) -> Iterator[dict[str, Any]]:
    validate_file(path)
    file = parquet.ParquetFile(path)
    for group in range(file.num_row_groups):
        yield from decode_rows(file.read_row_group(group).to_pylist())


def decode_trace(path: Path, trace_id: str) -> list[dict[str, Any]]:
    validate_file(path)
    file = parquet.ParquetFile(path)
    return [
        event
        for group in find_groups(path.with_suffix(".index.parquet"), trace_id)
        for event in decode_rows(file.read_row_group(group).to_pylist())
        if event["trace_id"] == trace_id
    ]
