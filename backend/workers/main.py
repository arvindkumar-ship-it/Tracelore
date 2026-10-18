import asyncio
import signal

from prometheus_client import start_http_server
from redis.asyncio import Redis

from backend.common.db import create_pool
from backend.common.logging import configure_logging
from backend.common.settings import get_settings
from backend.ingest.publisher import create_producer

from .jobs import WorkerJobs
from .scheduler import Scheduler


async def main() -> None:
    configure_logging()
    settings = get_settings()
    pool = await create_pool(settings, owner=True)
    redis = Redis.from_url(settings.redis_url)
    producer = create_producer(settings.kafka_broker)
    await producer.start()
    start_http_server(9100)
    scheduler = Scheduler(pool, WorkerJobs(settings, redis, producer).all())
    for signum in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signum, scheduler.stop.set)
    try:
        await scheduler.run()
    finally:
        await producer.stop()
        await redis.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
