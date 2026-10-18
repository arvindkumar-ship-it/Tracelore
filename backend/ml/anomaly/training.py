import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from backend.ledger.records import wire_event

from .ngram_model import NgramModel
from .tokens import tokenize


async def train_sequences(connection: Any, as_of: datetime) -> int:
    rows = await connection.fetch(
        """
        SELECT e.* FROM events e JOIN (
            SELECT trace_id FROM events r WHERE type='http.request' AND parent_span_id IS NULL
            AND ended_at BETWEEN $1 AND $2 AND status='ok' AND NOT EXISTS (
                SELECT 1 FROM incidents i WHERE r.service=ANY(i.services)
                AND r.ended_at BETWEEN i.start_time
                AND COALESCE(i.closed_at,$2)+interval '30 minutes')
            ORDER BY ended_at DESC LIMIT 5000
        ) selected USING(trace_id) ORDER BY timestamp,ended_at
    """,
        as_of - timedelta(days=7),
        as_of,
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["trace_id"])].append(wire_event(row))
    routes: dict[str, list[list[str]]] = defaultdict(list)
    for events in grouped.values():
        root = next(
            (
                event
                for event in events
                if event["parent_span_id"] is None and event["type"] == "http.request"
            ),
            None,
        )
        if root and not any(event["status"] == "error" for event in events):
            routes[root["attributes"]["route"]].append([tokenize(event) for event in events])
    return await _persist(connection, routes, as_of)


async def _persist(connection: Any, routes: dict[str, list[list[str]]], as_of: datetime) -> int:
    count = 0
    for route, traces in routes.items():
        if len(traces) < 30:
            continue
        split = int(len(traces) * 0.8)
        model = NgramModel()
        await asyncio.to_thread(model.train, traces[:split], traces[split:])
        await connection.execute(
            "INSERT INTO sequence_models(route,kind,version,blob) VALUES($1,'ngram',$2,$3) "
            "ON CONFLICT DO NOTHING",
            route,
            round(as_of.timestamp() * 1_000_000),
            model.to_dict(),
        )
        count += 1
    return count
