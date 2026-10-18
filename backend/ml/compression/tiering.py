import asyncio
import heapq
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from tracelore.canonical import canonical_json

from backend.common.metrics import COMPRESSION_RATIO
from backend.common.settings import Settings
from backend.ledger.records import order_key, wire_event

from .decoder import decode_file
from .encoder import encode_partition
from .object_store import ObjectStore
from .verify import verify_roundtrip


def _source(path: Path, existing: Path | None) -> Any:
    def hot() -> Any:
        with path.open() as handle:
            for line in handle:
                yield json.loads(line)

    return heapq.merge(decode_file(existing) if existing else (), hot(), key=order_key)


async def archive_day(connection: Any, store: ObjectStore, day: date) -> bool:
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    directory = store.settings.archive_dir / str(day)
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "hot.jsonl"
    count = await _export_hot(connection, start, source)
    if not count:
        return False
    old = await connection.fetchrow(
        "SELECT * FROM archive_manifests WHERE day=$1 AND archived_at IS NOT NULL", day
    )
    existing = (
        await store.download(
            old["object_key"],
            directory / ("previous-" + old["manifest"]["sha256"] + ".parquet"),
            expected_manifest=old["manifest"],
        )
        if old
        else None
    )
    encoded = await asyncio.to_thread(
        encode_partition, _source(source, existing), directory / "next.parquet"
    )
    await asyncio.to_thread(verify_roundtrip, encoded.path, _source(source, existing))
    await store.ensure_bucket()
    key = f"events/dt={day}/{encoded.manifest['sha256']}.parquet"
    await store.upload(encoded, key)
    async with connection.transaction():
        await connection.execute("SELECT drop_archived_partition($1,$2)", day, count)
        await connection.execute(
            "INSERT INTO archive_manifests(day,object_key,manifest,verified_at,archived_at) "
            "VALUES($1,$2,$3,now(),now()) ON CONFLICT(day) DO UPDATE SET "
            "object_key=EXCLUDED.object_key,"
            "manifest=EXCLUDED.manifest,verified_at=now(),archived_at=now()",
            day,
            key,
            encoded.manifest,
        )
    COMPRESSION_RATIO.set(encoded.path.stat().st_size / max(source.stat().st_size, 1))
    source.unlink()
    return True


async def _export_hot(connection: Any, start: datetime, path: Path) -> int:
    count = 0
    async with connection.transaction():
        cursor = connection.cursor(
            "SELECT * FROM events WHERE ended_at >= $1 AND ended_at < $2 "
            "ORDER BY ended_at,stream_id,sequence",
            start,
            start + timedelta(days=1),
        )
        with path.open("wb") as handle:
            async for row in cursor:
                handle.write(canonical_json(wire_event(row)) + b"\n")
                count += 1
    return count


async def run_tiering(connection: Any, settings: Settings, as_of: datetime) -> int:
    if not settings.enable_tiering:
        return 0
    store = ObjectStore(settings)
    days = await connection.fetch(
        "SELECT DISTINCT ended_at::date AS day FROM events WHERE ended_at < $1 ORDER BY day",
        (as_of - timedelta(days=settings.hot_retention_days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
    )
    count = 0
    for row in days:
        count += await archive_day(connection, store, row["day"])
    await move_cold(
        connection, store, (as_of - timedelta(days=settings.warm_retention_days)).date()
    )
    return count


async def move_cold(connection: Any, store: ObjectStore, before: date) -> None:
    rows = await connection.fetch(
        "SELECT * FROM archive_manifests WHERE day<$1 AND NOT cold", before
    )
    for row in rows:
        old_key, new_key = row["object_key"], "cold/" + row["object_key"]
        for suffix in (".parquet", ".index.parquet", ".manifest.json"):
            source = old_key.removesuffix(".parquet") + suffix
            target = new_key.removesuffix(".parquet") + suffix
            await asyncio.to_thread(
                store.client.copy_object,
                Bucket=store.settings.s3_bucket,
                Key=target,
                CopySource={"Bucket": store.settings.s3_bucket, "Key": source},
            )
        await store.download(
            new_key,
            store.settings.archive_dir / "cold-verify" / new_key.split("/")[-1],
            force=True,
            expected_manifest=row["manifest"],
        )
        await connection.execute(
            "UPDATE archive_manifests SET cold=true,object_key=$2 WHERE day=$1", row["day"], new_key
        )
