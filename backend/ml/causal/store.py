from datetime import datetime, timedelta
from typing import Any

from backend.ledger.records import order_key, wire_event


async def incident_events(connection: Any, start: datetime, end: datetime) -> list[dict[str, Any]]:
    before = await connection.fetch(
        """
        SELECT * FROM events WHERE ended_at>=$1 AND ended_at<$2
        ORDER BY ended_at DESC,stream_id DESC,sequence DESC LIMIT 20000
    """,
        start - timedelta(minutes=60),
        start,
    )
    affected = await connection.fetch(
        """
        SELECT * FROM events WHERE ended_at>=$1 AND ended_at<=$2
        ORDER BY ended_at,stream_id,sequence LIMIT 80000
    """,
        start,
        end,
    )
    return sorted([wire_event(row) for row in [*before, *affected]], key=order_key)
