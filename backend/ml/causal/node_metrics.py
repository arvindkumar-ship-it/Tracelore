from datetime import datetime
from statistics import median
from typing import Any

from backend.ml.anomaly.bocpd import BOCPD


async def aggregate_nodes(connection: Any, start: datetime) -> None:
    await connection.execute(
        """
        INSERT INTO node_buckets(node_id,bucket_start,count,errors,p95_ms)
        SELECT CASE WHEN type='db.query' THEN 'db:'||COALESCE(attributes->>'db_table','*')
            WHEN type LIKE 'cache.%' THEN 'cache:'||service
            WHEN type LIKE 'queue.%' THEN 'queue:'||(attributes->>'queue')
            WHEN type='http.client' THEN 'svc:'||(attributes->>'downstream_service')
            ELSE 'svc:'||service END,$1,count(*),count(*) FILTER(WHERE status='error'),
            percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms)
        FROM events WHERE ended_at >= $1 AND ended_at < $1+interval '1 minute'
        AND type<>'error' GROUP BY 1
        ON CONFLICT(node_id,bucket_start) DO UPDATE SET count=EXCLUDED.count,
        errors=EXCLUDED.errors,p95_ms=EXCLUDED.p95_ms
    """,
        start,
    )


def estimate_onset(rows: list[dict[str, Any]]) -> tuple[datetime, float] | None:
    if len(rows) < 45:
        return None
    initial = [row["p95_ms"] for row in rows[:40]]
    center = median(initial)
    scale = max(1.4826 * median(abs(value - center) for value in initial), abs(center) * 0.05, 1e-6)
    model = BOCPD()
    for index, row in enumerate(rows):
        residual = (row["p95_ms"] - center) / scale
        output = model.update(residual)
        if index >= 40 and output.short_mass > 0.7:
            onset = max(0, index - output.map_run_length)
            return rows[onset]["bucket_start"], abs(residual)
    return None
