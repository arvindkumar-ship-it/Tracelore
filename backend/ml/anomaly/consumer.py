import asyncio
import json
import logging
import signal
from datetime import UTC, datetime, timedelta
from typing import Any

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import Redis
from tracelore.canonical import canonical_json

from backend.common.db import create_pool
from backend.common.logging import configure_logging
from backend.common.metrics import DETECTOR_LAG, TRACE_EVICTIONS
from backend.common.settings import Settings, get_settings
from backend.ingest.publisher import ANOMALIES_TOPIC, EVENTS_TOPIC, create_producer

from .contracts import Signal
from .incidents import save_signals
from .metric_runtime import MetricRuntime
from .ngram_model import NgramModel
from .sequence_detector import SequenceDetector
from .trace_assembler import TraceAssembler

logger = logging.getLogger(__name__)
ACK_TRACE = """
for i = 2, #ARGV do redis.call('HDEL', KEYS[1], ARGV[i]) end
if redis.call('HLEN', KEYS[1]) == 0 then
  redis.call('DEL', KEYS[1])
  redis.call('ZREM', KEYS[2], ARGV[1])
end
return 1
"""


class Detector:
    def __init__(self, pool: Any, redis: Any, producer: Any, settings: Settings) -> None:
        self.pool, self.redis, self.producer = pool, redis, producer
        self.assembler = TraceAssembler()
        self.sequences = SequenceDetector()
        self.metrics = MetricRuntime(pool, redis)
        self.stop = asyncio.Event()
        self.models: dict[str, NgramModel] = {}
        self.neural: Any = None
        if settings.sequence_mode == "dual":
            from .transformer_runtime import SequenceRuntime

            self.neural = SequenceRuntime(settings.model_dir / "sequence")

    async def receive(self, event: dict[str, Any], at: datetime) -> None:
        if await self.redis.exists("processed:" + event["event_id"]):
            return
        trace_key = "open-trace:" + event["trace_id"]
        await self.redis.hset(trace_key, event["event_id"], canonical_json(event))
        await self.redis.expire(trace_key, 3600)
        await self.redis.zadd("open-traces", {event["trace_id"]: at.timestamp()})
        self.assembler.add(event, at.timestamp())
        await self.redis.sadd("dirty-buckets", event["ended_at"][:16] + ":00+00:00")
        await self.redis.set("processed:" + event["event_id"], "1", ex=600)
        DETECTOR_LAG.set(max(0, (at - datetime.fromisoformat(event["ended_at"])).total_seconds()))

    async def restore(self) -> None:
        if saved := await self.redis.get("detector:last-bucket"):
            text = saved.decode() if isinstance(saved, bytes) else saved
            self.metrics.last_bucket = datetime.fromisoformat(text) - timedelta(seconds=30)
        for trace_id in await self.redis.zrange("open-traces", 0, 49_999):
            events = await self.redis.hvals("open-trace:" + trace_id.decode())
            score = await self.redis.zscore("open-traces", trace_id)
            for event in events:
                self.assembler.add(json.loads(event), float(score or 0))
        await self.reload_models()

    async def reload_models(self) -> None:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT DISTINCT ON(route) route,blob FROM sequence_models WHERE "
                "kind='ngram' ORDER BY route,version DESC"
            )
        self.models = {row["route"]: NgramModel.from_dict(row["blob"]) for row in rows}

    async def flush(self, at: datetime) -> None:
        for trace_id, events in self.assembler.ready(at.timestamp()):
            try:
                await self._flush_trace(trace_id, events, at)
            except Exception:
                for event in events:
                    self.assembler.add(event, at.timestamp() - 30)
                logger.exception("trace_flush_failed", extra={"trace_id": trace_id})
        TRACE_EVICTIONS.inc(self.assembler.evictions)
        self.assembler.evictions = 0
        await self.metrics.tick(at)

    async def _flush_trace(self, trace_id: str, events: list[dict[str, Any]], at: datetime) -> None:
        persisted = await self.redis.hvals("open-trace:" + trace_id)
        if persisted:
            events = sorted(
                (json.loads(event) for event in persisted),
                key=lambda event: (event["timestamp"], event["ended_at"], event["event_id"]),
            )
        root = next(
            (
                event
                for event in events
                if event["parent_span_id"] is None and event["type"] == "http.request"
            ),
            None,
        )
        model = self.models.get(root["attributes"]["route"]) if root else None
        signals = (
            []
            if model is None
            else (
                await self._dual_signals(events, model, at)
                if self.neural is not None
                else self.sequences.score(events, model, at)
            )
        )
        if signals:
            await self._grade_signals(trace_id, signals, at)
            async with self.pool.acquire() as connection:
                await save_signals(connection, signals)
        await self.redis.eval(
            ACK_TRACE,
            2,
            "open-trace:" + trace_id,
            "open-traces",
            trace_id,
            *(event["event_id"] for event in events),
        )

    async def _grade_signals(self, trace_id: str, signals: list[Signal], at: datetime) -> None:
        from backend.ml.baseline.cache import predict_cached

        window_key = f"sequence-window:{signals[0].service}:{signals[0].route}"
        await self.redis.zadd(window_key, {trace_id: at.timestamp()})
        await self.redis.zremrangebyscore(window_key, 0, at.timestamp() - 30)
        await self.redis.expire(window_key, 60)
        enough_traces = await self.redis.zcard(window_key) >= 3
        async with self.pool.acquire() as connection:
            baseline = await predict_cached(
                connection, self.redis, signals[0].service, signals[0].route, at
            )
        for item in signals:
            item.incident_grade = enough_traces and baseline.status == "ready"
            if not item.incident_grade:
                await self.producer.send_and_wait(
                    ANOMALIES_TOPIC,
                    canonical_json({"severity": "info", "signal": item.model_dump(mode="json")}),
                    key=trace_id.encode(),
                )

    async def _dual_signals(
        self, events: list[dict[str, Any]], model: NgramModel, at: datetime
    ) -> Any:
        from .tokens import tokenize

        scores = await asyncio.to_thread(self.neural.score, [tokenize(event) for event in events])
        return self.sequences.score(
            events, model, at, scores, self.neural.threshold, self.neural.confidence
        )

    async def maintenance(self) -> None:
        tick = 0
        while not self.stop.is_set():
            try:
                await self.flush(datetime.now(UTC))
                if tick % 60 == 0:
                    await self.reload_models()
            except Exception:
                logger.exception("detector_maintenance_failed")
            tick += 1
            try:
                await asyncio.wait_for(self.stop.wait(), 1)
            except TimeoutError:
                continue


async def main() -> None:
    configure_logging()
    settings = get_settings()
    pool, redis = await create_pool(settings), Redis.from_url(settings.redis_url)
    producer = create_producer(settings.kafka_broker)
    consumer = AIOKafkaConsumer(
        EVENTS_TOPIC,
        bootstrap_servers=settings.kafka_broker,
        group_id="tracelore-detector-v1",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await producer.start()
    await consumer.start()
    detector = Detector(pool, redis, producer, settings)
    await detector.restore()
    start_http_server(9101)
    for signum in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signum, detector.stop.set)
    task = asyncio.create_task(detector.maintenance())
    try:
        while not detector.stop.is_set():
            batches = await consumer.getmany(timeout_ms=1000, max_records=1000)
            for messages in batches.values():
                for message in messages:
                    await detector.receive(json.loads(message.value), datetime.now(UTC))
            if batches:
                await consumer.commit()
    finally:
        detector.stop.set()
        await task
        await consumer.stop()
        await producer.stop()
        await redis.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
