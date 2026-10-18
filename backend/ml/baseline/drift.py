from datetime import datetime, timedelta
from typing import Any

from .contracts import METRICS
from .store import predict


async def needs_retrain(connection: Any, as_of: datetime) -> bool:
    if await connection.fetchval("SELECT EXISTS(SELECT 1 FROM incidents WHERE status='open')"):
        return False
    trained = await connection.fetchval("SELECT trained_at FROM baseline_versions WHERE active")
    if trained is None or as_of - trained > timedelta(days=7):
        return True
    rows = await connection.fetch(
        "SELECT * FROM metric_buckets WHERE bucket_start >= $1 "
        "AND bucket_start < $2 ORDER BY bucket_start",
        as_of - timedelta(hours=6),
        as_of,
    )
    hours: dict[datetime, list[bool]] = {}
    for row in rows:
        baseline = await predict(connection, row["service"], row["route"], row["bucket_start"])
        if baseline.status != "ready":
            continue
        values = dict(row) | {"error_rate": row["errors"] / max(row["count"], 1)}
        outside = any(
            not baseline.metrics[name].low <= values[name] <= baseline.metrics[name].high
            for name in METRICS
        )
        hours.setdefault(row["bucket_start"].replace(minute=0, second=0, microsecond=0), []).append(
            outside
        )
    return len(hours) >= 6 and all(sum(flags) / len(flags) > 0.2 for flags in hours.values())
