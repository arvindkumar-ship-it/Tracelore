import asyncio
import json
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer

from backend.common.settings import get_settings
from backend.ingest.publisher import EVENTS_TOPIC, create_producer, publish
from backend.workers.scheduler import Job, run_locked

pytestmark = pytest.mark.integration


async def test_real_kafka(event_factory):
    settings = get_settings()
    producer = create_producer(settings.kafka_broker)
    consumer = AIOKafkaConsumer(
        EVENTS_TOPIC,
        bootstrap_servers=settings.kafka_broker,
        group_id="integration-" + str(uuid4()),
        auto_offset_reset="latest",
        enable_auto_commit=False,
    )
    await producer.start()
    await consumer.start()
    try:
        await consumer.getmany(timeout_ms=1000)
        event = event_factory()
        await publish(producer, [event])
        seen = []
        for _ in range(10):
            batches = await consumer.getmany(timeout_ms=1000)
            seen.extend(
                json.loads(message.value) for messages in batches.values() for message in messages
            )
            if any(item["event_id"] == event["event_id"] for item in seen):
                break
        assert event in seen
    finally:
        await consumer.stop()
        await producer.stop()


async def test_advisory_lock_two_workers(databases):
    entered = asyncio.Event()
    release = asyncio.Event()
    count = 0

    async def run(connection):
        nonlocal count
        count += 1
        entered.set()
        await release.wait()

    job = Job("integration-exclusive-" + str(uuid4()), 1, run)
    first = asyncio.create_task(run_locked(databases[0], job))
    await entered.wait()
    second = await run_locked(databases[0], job)
    release.set()
    await first
    assert count == 1 and second is False
