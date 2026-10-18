import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.common.metrics import BOCPD_ALARMS
from backend.ml.baseline.aggregate import five_second_buckets
from backend.ml.baseline.cache import predict_cached

from .bocpd import BOCPD
from .incidents import save_signals
from .metric_detector import MetricStream


class MetricRuntime:
    def __init__(self, pool: Any, redis: Any) -> None:
        self.pool, self.redis = pool, redis
        self.streams: dict[str, MetricStream] = {}
        self.last_bucket: datetime | None = None
        self.persisted_at: dict[str, datetime] = {}

    async def tick(self, at: datetime) -> None:
        end = at.replace(second=(at.second // 5) * 5, microsecond=0)
        start = max(self.last_bucket or end - timedelta(seconds=5), end - timedelta(minutes=10))
        if start >= end:
            return
        async with self.pool.acquire() as connection:
            buckets = await five_second_buckets(connection, start, end)
            signals = []
            for bucket in buckets:
                baseline = await predict_cached(
                    connection,
                    self.redis,
                    bucket["service"],
                    bucket["route"],
                    bucket["bucket_start"],
                )
                if baseline.status != "ready":
                    continue
                for metric, value in {
                    "p95_ms": bucket["p95_ms"],
                    "error_rate": bucket["errors"] / bucket["count"],
                    "count": bucket["count"] * 12,
                }.items():
                    if metric != "count" and bucket["count"] < 5:
                        continue
                    if metric == "count" and baseline.metrics[metric].expected / 12 < 5:
                        continue
                    key = json.dumps([bucket["service"], bucket["route"], metric])
                    stream = await self._stream(key)
                    if stream.last_seen is not None and bucket["bucket_start"] <= stream.last_seen:
                        continue
                    signal = stream.observe(
                        bucket["service"],
                        bucket["route"],
                        metric,
                        value,
                        baseline.metrics[metric],
                        bucket["bucket_start"],
                    )
                    if signal:
                        BOCPD_ALARMS.inc()
                        signals.append(signal)
                    await self._persist(key, stream)
            if signals:
                await save_signals(connection, signals)
        self.last_bucket = end
        await self.redis.set("detector:last-bucket", end.isoformat(), ex=3600)
        self.streams = {
            key: stream
            for key, stream in self.streams.items()
            if stream.last_seen is None or at - stream.last_seen < timedelta(hours=1)
        }

    async def _stream(self, key: str) -> MetricStream:
        if key not in self.streams:
            stream = MetricStream()
            if saved := await self.redis.get("bocpd:" + key):
                value = json.loads(saved)
                stream.model = BOCPD.from_bytes(base64.b64decode(value["model"]))
                stream.consecutive, stream.residuals = value["consecutive"], value["residuals"]
                stream.last_seen = (
                    datetime.fromisoformat(value["last_seen"]) if value.get("last_seen") else None
                )
                stream.last_alarm = (
                    datetime.fromisoformat(value["last_alarm"]) if value["last_alarm"] else None
                )
            self.streams[key] = stream
        return self.streams[key]

    async def _persist(self, key: str, stream: MetricStream) -> None:
        at = stream.last_seen or datetime.now(UTC)
        if key in self.persisted_at and at - self.persisted_at[key] < timedelta(seconds=30):
            return
        self.persisted_at[key] = at
        await self.redis.set(
            "bocpd:" + key,
            json.dumps(
                {
                    "model": base64.b64encode(stream.model.to_bytes()).decode(),
                    "consecutive": stream.consecutive,
                    "residuals": stream.residuals,
                    "last_alarm": stream.last_alarm.isoformat() if stream.last_alarm else None,
                    "last_seen": stream.last_seen.isoformat() if stream.last_seen else None,
                }
            ),
            ex=3600,
        )
