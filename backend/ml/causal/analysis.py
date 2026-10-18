from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any

from backend.common.time import parse_timestamp
from backend.ledger.records import order_key

from .graph import event_node
from .node_metrics import estimate_onset


def collect_facts(
    events: list[dict[str, Any]], node_rows: list[Any], incident_start: datetime
) -> tuple[dict[str, datetime], dict[str, float], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event_node(event)].append(event)
    onsets, magnitudes, facts = {}, {}, []
    for node, spans in sorted(grouped.items()):
        before = [
            span["duration_ms"]
            for span in spans
            if parse_timestamp(span["ended_at"]) < incident_start
        ]
        expected = median(before) if before else None
        affected = [
            span
            for span in spans
            if parse_timestamp(span["ended_at"]) >= incident_start
            and (
                span["status"] == "error"
                or (expected is not None and span["duration_ms"] > max(expected * 2, expected + 5))
            )
        ]
        if not affected:
            continue
        first = min(affected, key=order_key)
        onsets[node] = parse_timestamp(first["timestamp"])
        magnitudes[node] = max(span["duration_ms"] / max(expected or 1, 1) for span in affected)
        facts.extend(_node_facts(node, first, affected, expected, onsets[node], magnitudes[node]))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in node_rows:
        buckets[row["node_id"]].append(dict(row))
    for node, series in buckets.items():
        if node not in onsets and (estimate := estimate_onset(series)):
            onsets[node], magnitudes[node] = estimate
            facts.append(
                {
                    "kind": "change_point",
                    "node": node,
                    "text": "A bounded change-point model detected a shift.",
                    "data": {"onset": estimate[0].isoformat(), "magnitude": estimate[1]},
                }
            )
    return onsets, magnitudes, facts


def _node_facts(
    node: str,
    first: dict[str, Any],
    affected: list[dict[str, Any]],
    expected: float | None,
    onset: datetime,
    magnitude: float,
) -> list[dict[str, Any]]:
    return [
        {
            "kind": "change_point",
            "node": node,
            "text": "First recorded affected span on this node.",
            "data": {"onset": onset.isoformat(), "magnitude": magnitude},
        },
        {
            "kind": "metric",
            "node": node,
            "text": "Observed latency and errors in affected spans.",
            "data": {
                "observed": median(span["duration_ms"] for span in affected),
                "expected": expected,
                "errors": sum(span["status"] == "error" for span in affected),
                "count": len(affected),
            },
        },
        {
            "kind": "event",
            "node": node,
            "text": "Concrete span supporting the onset estimate.",
            "data": {
                "event_id": first["event_id"],
                "trace_id": first["trace_id"],
                "duration_ms": first["duration_ms"],
                "status": first["status"],
            },
        },
    ]
