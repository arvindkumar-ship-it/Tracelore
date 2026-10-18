import asyncio

from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from backend.common.settings import get_settings
from backend.ingest.publisher import ANOMALIES_TOPIC, EVENTS_TOPIC, FEATURES_TOPIC


async def main() -> None:
    client = AIOKafkaAdminClient(bootstrap_servers=get_settings().kafka_broker)
    await client.start()
    try:
        present = set(await client.list_topics())
        topics = [
            NewTopic(name, num_partitions=12, replication_factor=1)
            for name in (EVENTS_TOPIC, ANOMALIES_TOPIC, FEATURES_TOPIC)
            if name not in present
        ]
        if topics:
            await client.create_topics(topics)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
