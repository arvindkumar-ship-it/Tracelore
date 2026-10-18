import asyncio
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from tracelore.canonical import canonical_json

from .decoder import decode_file
from .lossy_sampling import summarize
from .object_store import ObjectStore


def _summarize_file(path: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="tracelore-summary-") as directory:
        with closing(sqlite3.connect(str(Path(directory) / "traces.sqlite"))) as database:
            database.execute("CREATE TABLE spans(trace_id TEXT, body TEXT)")
            database.executemany(
                "INSERT INTO spans VALUES(?,?)",
                (
                    (event["trace_id"], canonical_json(event).decode())
                    for event in decode_file(path)
                ),
            )
            database.execute("CREATE INDEX trace_order ON spans(trace_id)")
            results: list[dict[str, Any]] = []
            for batch in _trace_batches(database):
                results.extend(asdict(summary) for summary in summarize(batch))
            return results


def _trace_batches(database: sqlite3.Connection) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for (trace_id,) in database.execute("SELECT DISTINCT trace_id FROM spans ORDER BY trace_id"):
        count = database.execute(
            "SELECT count(*) FROM spans WHERE trace_id=?", (trace_id,)
        ).fetchone()[0]
        if count > 50_000:
            raise ValueError("summary trace exceeds 50,000 spans; lossless archive is preserved")
        if len(batch) + count > 50_000:
            yield batch
            batch = []
        batch.extend(
            json.loads(row[0])
            for row in database.execute(
                "SELECT body FROM spans WHERE trace_id=? ORDER BY rowid", (trace_id,)
            )
        )
    if batch:
        yield batch


async def summarize_archives(connection: Any, store: ObjectStore, before: date) -> int:
    enabled = await connection.fetchval(
        "SELECT value FROM runtime_settings WHERE key='lossy_sampling_enabled'"
    )
    if not (enabled if enabled is not None else store.settings.lossy_sampling_enabled):
        return 0
    rows = await connection.fetch("SELECT * FROM archive_manifests WHERE day<$1", before)
    completed = 0
    for row in rows:
        checkpoint = "summary:" + str(row["day"])
        previous = await connection.fetchval(
            "SELECT value FROM runtime_settings WHERE key=$1", checkpoint
        )
        if previous == row["manifest"]["sha256"]:
            continue
        path = store.settings.archive_dir / "summary" / f"{row['day']}.parquet"
        await store.download(row["object_key"], path, force=True, expected_manifest=row["manifest"])
        summaries = await asyncio.to_thread(_summarize_file, path)
        async with connection.transaction():
            await connection.execute("DELETE FROM trace_summaries WHERE day=$1", row["day"])
            await connection.executemany(
                "INSERT INTO trace_summaries(day,representative_trace,trace_count,quantiles) "
                "VALUES($1,$2::text::uuid,$3,$4)",
                [
                    (
                        row["day"],
                        item["representative_trace"],
                        item["trace_count"],
                        item["quantiles"],
                    )
                    for item in summaries
                ],
            )
            await connection.execute(
                "INSERT INTO runtime_settings(key,value) VALUES($1,$2) "
                "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                checkpoint,
                row["manifest"]["sha256"],
            )
        completed += 1
    return completed