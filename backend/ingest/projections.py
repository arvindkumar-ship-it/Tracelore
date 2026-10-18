from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tracelore.canonical import canonical_json

from .publisher import FEATURES_TOPIC


async def enqueue_projection(connection: Any, topic: str, key: str, body: dict[str, Any]) -> None:
    identifier = uuid5(NAMESPACE_URL, canonical_json([topic, key, body]).decode())
    await connection.execute(
        "INSERT INTO projection_outbox(event_id,topic,message_key,body) "
        "VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
        identifier,
        topic,
        key,
        body | {"event_id": str(identifier)},
    )


async def enqueue_features(connection: Any, at: Any) -> None:
    rows = await connection.fetch("SELECT * FROM metric_buckets WHERE bucket_start=$1", at)
    for row in rows:
        body = dict(row)
        body["bucket_start"] = body["bucket_start"].isoformat()
        key = canonical_json([row["service"], row["route"]]).decode()
        await enqueue_projection(connection, FEATURES_TOPIC, key, body)


async def relay_projections(connection: Any, producer: Any) -> int:
    async with connection.transaction():
        rows = await connection.fetch(
            "SELECT * FROM projection_outbox ORDER BY created_at,event_id "
            "FOR UPDATE SKIP LOCKED LIMIT 1000"
        )
        futures = [
            await producer.send(
                row["topic"], canonical_json(row["body"]), key=row["message_key"].encode()
            )
            for row in rows
        ]
        for future in futures:
            await future
        if rows:
            await connection.execute(
                "DELETE FROM projection_outbox WHERE event_id=ANY($1::uuid[])",
                [row["event_id"] for row in rows],
            )
    return len(rows)
