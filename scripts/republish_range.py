import argparse
import asyncio
from datetime import datetime

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ingest.publisher import create_producer, publish
from backend.ledger.repository import iter_events_ordered


async def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently republish a durable ledger range")
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    args = parser.parse_args()
    if args.start.tzinfo is None or args.end.tzinfo is None or args.end <= args.start:
        parser.error("provide an increasing timezone-aware range")
    settings = get_settings()
    pool = await create_pool(settings)
    producer = create_producer(settings.kafka_broker)
    await producer.start()
    try:
        async with pool.acquire() as connection:
            batch = []
            async for event in iter_events_ordered(connection, (args.start, "", 0), args.end):
                batch.append(event)
                if len(batch) == 1000:
                    await publish(producer, batch)
                    batch = []
            await publish(producer, batch)
    finally:
        await producer.stop()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
