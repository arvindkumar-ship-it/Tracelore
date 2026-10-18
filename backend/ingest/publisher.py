import logging
from typing import Any
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from tracelore.canonical import canonical_json

from backend.common.metrics import PUBLISH_FAILURES

logger = logging.getLogger(__name__)
EVENTS_TOPIC = "tracelore-events"
ANOMALIES_TOPIC = "tracelore-anomalies"
FEATURES_TOPIC = "tracelore-ml-features"


def create_producer(broker: str) -> AIOKafkaProducer:
    return AIOKafkaProducer(
        bootstrap_servers=broker,
        acks="all",
        enable_idempotence=True,
        linger_ms=20,
        request_timeout_ms=5000,
    )


async def enqueue(connection: Any, events: list[dict[str, Any]]) -> None:
    if events:
        await connection.executemany(
            "INSERT INTO event_outbox(event_id,stream_id,body) VALUES($1,$2,$3) "
            "ON CONFLICT DO NOTHING",
            [(UUID(event["event_id"]), event["stream_id"], event) for event in events],
        )


async def publish(producer: Any, events: list[dict[str, Any]]) -> None:
    try:
        futures = [
            await producer.send(
                EVENTS_TOPIC, canonical_json(event), key=event["stream_id"].encode()
            )
            for event in events
        ]
        for future in futures:
            await future
    except KafkaError:
        PUBLISH_FAILURES.inc()
        logger.exception("kafka_publish_failed count=%s", len(events))
        raise


async def relay(connection: Any, producer: Any, limit: int = 1000) -> int:
    async with connection.transaction():
        rows = await connection.fetch(
            "SELECT event_id,body FROM event_outbox WHERE published_at IS NULL "
            "ORDER BY created_at,event_id FOR UPDATE SKIP LOCKED LIMIT $1",
            limit,
        )
        await publish(producer, [row["body"] for row in rows])
        if rows:
            await connection.execute(
                "DELETE FROM event_outbox WHERE event_id=ANY($1::uuid[])",
                [row["event_id"] for row in rows],
            )
    return len(rows)
