import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .contracts import BaselineRange, MetricRange
from .stats_model import Bucket, fit_endpoint, hour_of_week, inverse, transform

NORMAL_BUCKETS = """
SELECT b.* FROM metric_buckets b WHERE bucket_start >= $1 AND bucket_start < $2
AND NOT EXISTS (SELECT 1 FROM incidents i WHERE b.service=ANY(i.services)
AND b.bucket_start BETWEEN i.start_time AND COALESCE(i.closed_at,$2)+interval '30 minutes')
ORDER BY bucket_start
"""


async def train(connection: Any, as_of: datetime, multiplier: float = 4) -> int:
    buckets = await connection.fetch(NORMAL_BUCKETS, as_of - timedelta(days=28), as_of)
    grouped: dict[tuple[str, str], list[Bucket]] = defaultdict(list)
    for row in buckets:
        bucket = Bucket(**dict(row))
        grouped[(bucket.service, bucket.route)].append(bucket)
    fits = await asyncio.to_thread(_fit_all, grouped, multiplier)
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(17031706)")
        version = await connection.fetchval(
            "INSERT INTO baseline_versions(trained_at) VALUES($1) RETURNING version", as_of
        )
        records = _records(fits, version)
        if records:
            await connection.executemany(
                "INSERT INTO "
                "baselines(service,route,slot,metric,median,mad,n,low,high,source,version) "
                "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                records,
            )
        await connection.execute("UPDATE baseline_versions SET active=false WHERE active")
        await connection.execute(
            "UPDATE baseline_versions SET active=true WHERE version=$1", version
        )
    return len(records)


def _fit_all(grouped: dict[tuple[str, str], list[Bucket]], multiplier: float) -> dict[Any, Any]:
    return {key: fit_endpoint(buckets, multiplier) for key, buckets in grouped.items()}


async def predict(connection: Any, service: str, route: str, at: datetime) -> BaselineRange:
    rows = await connection.fetch(
        "SELECT b.* FROM baselines b JOIN baseline_versions v USING(version) "
        "WHERE v.active AND service=$1 AND route=$2 AND slot=$3",
        service,
        route,
        hour_of_week(at),
    )
    result = BaselineRange(
        service=service, route=route, at=at, status="ready" if rows else "warming_up"
    )
    for row in rows:
        result.version = row["version"]
        result.metrics[row["metric"]] = MetricRange(
            low=row["low"],
            high=row["high"],
            expected=inverse(row["median"], row["metric"]),
            scale=row["mad"],
            n=row["n"],
            source=row["source"],
        )
    return result


def _records(fits: dict[Any, Any], version: int) -> list[tuple[Any, ...]]:
    return [
        (
            service,
            route,
            slot,
            metric,
            transform(value.expected, metric),
            value.scale,
            value.n,
            value.low,
            value.high,
            value.source,
            version,
        )
        for (service, route), slots in fits.items()
        for slot, metrics in slots.items()
        for metric, value in metrics.items()
    ]
