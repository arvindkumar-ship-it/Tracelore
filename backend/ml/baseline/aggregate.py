from datetime import datetime, timedelta
from typing import Any

from backend.ingest.projections import enqueue_features

AGGREGATE_SQL = """
INSERT INTO metric_buckets(service,route,bucket_start,count,errors,p50_ms,p95_ms,p99_ms)
SELECT r.service,r.route,$1,count(e.event_id),count(e.event_id) FILTER(WHERE e.status='error'),
COALESCE(percentile_cont(0.50) WITHIN GROUP(ORDER BY e.duration_ms),0),
COALESCE(percentile_cont(0.95) WITHIN GROUP(ORDER BY e.duration_ms),0),
COALESCE(percentile_cont(0.99) WITHIN GROUP(ORDER BY e.duration_ms),0)
FROM endpoint_registry r LEFT JOIN events e ON e.service=r.service
AND e.attributes->>'route'=r.route
AND e.type='http.request' AND e.ended_at >= $1 AND e.ended_at < $2
WHERE r.first_seen<$2 AND r.last_seen>$1-interval '28 days'
GROUP BY r.service,r.route
ON CONFLICT(service,route,bucket_start) DO UPDATE SET count=EXCLUDED.count,errors=EXCLUDED.errors,
p50_ms=EXCLUDED.p50_ms,p95_ms=EXCLUDED.p95_ms,p99_ms=EXCLUDED.p99_ms
"""


async def aggregate_minute(connection: Any, bucket_start: datetime) -> None:
    start = bucket_start.replace(second=0, microsecond=0)
    async with connection.transaction():
        await connection.execute(AGGREGATE_SQL, start, start + timedelta(minutes=1))
        await enqueue_features(connection, start)


async def backfill(connection: Any, start: datetime, end: datetime) -> int:
    current, count = start.replace(second=0, microsecond=0), 0
    while current < end:
        await aggregate_minute(connection, current)
        current += timedelta(minutes=1)
        count += 1
    return count


async def five_second_buckets(connection: Any, start: datetime, end: datetime) -> list[Any]:
    return list(
        await connection.fetch(
            """
        SELECT r.service,r.route,b.bucket_start,count(e.event_id) AS count,
        count(e.event_id) FILTER(WHERE e.status='error') AS errors,
        COALESCE(percentile_cont(0.95) WITHIN GROUP(ORDER BY e.duration_ms),0) AS p95_ms
        FROM endpoint_registry r CROSS JOIN generate_series($1::timestamptz,
            $2::timestamptz-interval '5 seconds',interval '5 seconds') AS b(bucket_start)
        LEFT JOIN events e ON e.service=r.service AND e.attributes->>'route'=r.route
            AND e.type='http.request' AND e.ended_at>=b.bucket_start
            AND e.ended_at<b.bucket_start+interval '5 seconds'
        WHERE r.first_seen<$2 AND r.last_seen>$1-interval '1 hour'
        GROUP BY r.service,r.route,b.bucket_start ORDER BY b.bucket_start
    """,
            start,
            end,
        )
    )
