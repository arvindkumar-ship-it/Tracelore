from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from backend.common.metrics import DIGEST_MISMATCH
from backend.common.settings import Settings
from backend.ingest.projections import relay_projections
from backend.ingest.publisher import relay
from backend.ledger.verify import verify_stream
from backend.ml.anomaly.incidents import resolve_stale
from backend.ml.anomaly.training import train_sequences
from backend.ml.baseline.aggregate import aggregate_minute
from backend.ml.baseline.drift import needs_retrain
from backend.ml.baseline.store import train
from backend.ml.causal.graph import refresh_edges
from backend.ml.causal.node_metrics import aggregate_nodes
from backend.ml.causal.rag import index_pending
from backend.ml.causal.rca import analyze_incident
from backend.ml.compression.object_store import ObjectStore
from backend.ml.compression.summary_job import summarize_archives
from backend.ml.compression.tiered_repository import TieredRepository
from backend.ml.compression.tiering import run_tiering
from backend.replay.engine import replay_until
from backend.replay.snapshots import SNAPSHOT_LOCK, Snapshots

from .scheduler import Job


class WorkerJobs:
    def __init__(self, settings: Settings, redis: Any, producer: Any) -> None:
        self.settings, self.redis, self.producer = settings, redis, producer
        self.store = ObjectStore(settings)

    def all(self) -> list[Job]:
        return [
            Job("ensure_partitions", 3600, self.partitions),
            Job("outbox_relay", 1, self.outbox),
            Job("aggregate_minute", 60, self.aggregate),
            Job("node_buckets", 60, self.nodes),
            Job("maybe_snapshot", 60, self.snapshot),
            Job("refresh_dependency_edges", 300, refresh_edges),
            Job("resolve_stale_incidents", 60, self.resolve),
            Job("verify_streams", 600, self.verify),
            Job("rca_for_open_incidents", 60, self.rca),
            Job("drift_check", 86400, self.drift),
            Job("sequence_training", 300, self.sequence_training),
            Job("tiering", 86400, self.tiering),
            Job("rag_index_pending", 300, self.rag),
            Job("summarized_analytics", 86400, self.summaries),
        ]

    async def partitions(self, connection: Any) -> None:
        for offset in range(4):
            await connection.execute(
                "SELECT ensure_partition($1)", datetime.now(UTC).date() + timedelta(days=offset)
            )

    async def outbox(self, connection: Any) -> None:
        deadline = perf_counter() + 0.8
        while await relay(connection, self.producer) == 1000:
            if perf_counter() >= deadline:
                break
        await relay_projections(connection, self.producer)

    async def aggregate(self, connection: Any) -> None:
        start = (
            datetime.now(UTC) - timedelta(seconds=self.settings.late_grace_seconds, minutes=1)
        ).replace(second=0, microsecond=0)
        await aggregate_minute(connection, start)
        dirty = await self.redis.srandmember("dirty-buckets", 500)
        for raw in dirty:
            await aggregate_minute(connection, datetime.fromisoformat(raw.decode()))
            await self.redis.srem("dirty-buckets", raw)

    async def nodes(self, connection: Any) -> None:
        start = (
            datetime.now(UTC) - timedelta(seconds=self.settings.late_grace_seconds, minutes=1)
        ).replace(second=0, microsecond=0)
        await aggregate_nodes(connection, start)

    async def snapshot(self, connection: Any) -> None:
        cut = datetime.now(UTC) - timedelta(seconds=self.settings.late_grace_seconds)
        async with connection.transaction():
            await connection.execute("LOCK TABLE events IN ACCESS SHARE MODE")
            await connection.execute("SELECT pg_advisory_xact_lock($1)", SNAPSHOT_LOCK)
            snapshots = Snapshots(connection)
            previous = await snapshots.latest_before(cut)
            state = await replay_until(TieredRepository(connection, self.store), snapshots, cut)
            if (
                state.event_count - (previous.event_count if previous else 0)
                < self.settings.snapshot_every_events
            ):
                return
            await snapshots.save(state)
            if state.event_count // self.settings.snapshot_every_events % 100 == 0:
                zero = await replay_until(TieredRepository(connection, self.store), None, cut)
                if zero.digest() != state.digest():
                    DIGEST_MISMATCH.inc()
                    raise ValueError("snapshot versus zero replay digest mismatch")

    async def resolve(self, connection: Any) -> None:
        await resolve_stale(connection, datetime.now(UTC))

    async def verify(self, connection: Any) -> None:
        rows = await connection.fetch(
            "SELECT DISTINCT stream_id FROM events WHERE ended_at>now()-interval '1 hour'"
        )
        for row in rows:
            await verify_stream(connection, row["stream_id"])

    async def rca(self, connection: Any) -> None:
        rows = await connection.fetch(
            "SELECT i.id FROM incidents i WHERE i.status='open' AND "
            "i.opened_at<now()-interval '60 seconds' "
            "AND NOT EXISTS(SELECT 1 FROM rca_reports r WHERE r.incident_id=i.id AND "
            "(r.created_at>now()-interval '2 minutes' OR r.created_at>=i.updated_at)) "
            "ORDER BY i.opened_at LIMIT 10"
        )
        for row in rows:
            await analyze_incident(connection, row["id"], self.settings)

    async def drift(self, connection: Any) -> None:
        if await needs_retrain(connection, datetime.now(UTC)):
            await train(connection, datetime.now(UTC), self.settings.baseline_k)

    async def sequence_training(self, connection: Any) -> None:
        await train_sequences(connection, datetime.now(UTC))

    async def tiering(self, connection: Any) -> None:
        await run_tiering(connection, self.settings, datetime.now(UTC))

    async def rag(self, connection: Any) -> None:
        if self.settings.rag_enabled:
            await index_pending(connection)

    async def summaries(self, connection: Any) -> None:
        await summarize_archives(
            connection, self.store, (datetime.now(UTC) - timedelta(days=30)).date()
        )
