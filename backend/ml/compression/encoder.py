import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any

import pyarrow as arrow
import pyarrow.parquet as parquet
from tracelore.canonical import canonical_json

from backend.ledger.records import order_key

from .codec import encode_rows
from .schema import DICTIONARY_COLUMNS, SCHEMA, SCHEMA_VERSION
from .trace_index import INDEX_SCHEMA, index_rows

ROW_GROUP_SIZE = 50_000


@dataclass(frozen=True)
class EncodedFile:
    path: Path
    manifest_path: Path
    index_path: Path
    manifest: dict[str, Any]


def batches(
    rows: Iterable[dict[str, Any]], size: int = ROW_GROUP_SIZE
) -> Iterator[list[dict[str, Any]]]:
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def encode_partition(rows: Iterable[dict[str, Any]], path: Path) -> EncodedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    index_path, manifest_path = (
        path.with_suffix(".index.parquet"),
        path.with_suffix(".manifest.json"),
    )
    digest, count, previous = hashlib.sha256(), 0, None
    tails: dict[str, dict[str, Any]] = {}
    traces: set[str] = set()
    with (
        parquet.ParquetWriter(
            path, SCHEMA, compression="zstd", compression_level=9, use_dictionary=DICTIONARY_COLUMNS
        ) as writer,
        parquet.ParquetWriter(index_path, INDEX_SCHEMA, compression="zstd") as index_writer,
    ):
        minimum = maximum = None
        for group, batch in enumerate(batches(rows)):
            for event in batch:
                key = order_key(event)
                if previous is not None and key <= previous:
                    raise ValueError("archive input must be strictly ordered")
                previous, maximum = key, [event["ended_at"], event["stream_id"], event["sequence"]]
                minimum = minimum or maximum
                digest.update(canonical_json(event) + b"\n")
                traces.add(event["trace_id"])
                tail = tails.get(event["stream_id"])
                if tail is None or event["sequence"] > tail["sequence"]:
                    tails[event["stream_id"]] = {
                        "sequence": event["sequence"],
                        "event_hash": event["event_hash"],
                    }
            writer.write_table(arrow.Table.from_pylist(encode_rows(batch), schema=SCHEMA))
            index_writer.write_table(index_rows(batch, group))
            count += len(batch)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "row_count": count,
        "trace_count": len(traces),
        "min_key": minimum,
        "max_key": maximum,
        "sha256": file_hash(path),
        "index_sha256": file_hash(index_path),
        "event_digest": digest.hexdigest(),
        "chain_tails": tails,
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    return EncodedFile(path, manifest_path, index_path, manifest)
