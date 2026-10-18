from collections.abc import Callable
from typing import Any

from backend.ledger.records import order_key

from .state import EdgeStats, EndpointStats, SystemState


class ReplayError(ValueError):
    """A ledger event cannot be folded under the current contract."""


def http_request(state: SystemState, event: dict[str, Any]) -> None:
    key = event["service"], event["attributes"]["route"]
    stats = state.endpoints.setdefault(key, EndpointStats())
    duration = round(event["duration_ms"] * 1000)
    stats.count += 1
    stats.errors += event["status"] == "error"
    stats.total_duration_us += duration
    stats.histogram.add(duration)


def http_client(state: SystemState, event: dict[str, Any]) -> None:
    key = event["service"], event["attributes"]["downstream_service"]
    stats = state.edges.setdefault(key, EdgeStats())
    stats.count += 1
    stats.errors += event["status"] == "error"
    stats.total_duration_us += round(event["duration_ms"] * 1000)


def db_query(state: SystemState, event: dict[str, Any]) -> None:
    attributes = event["attributes"]
    table = attributes["db_table"] or "*"
    stats = state.db_tables.setdefault(table, {"reads": 0, "writes": 0, "errors": 0})
    stats["reads" if attributes["operation"] == "select" else "writes"] += 1
    stats["errors"] += event["status"] == "error"


def cache_operation(state: SystemState, event: dict[str, Any]) -> None:
    attributes, cache = event["attributes"], state.cache
    if event["type"] == "cache.get":
        if attributes["hit"]:
            cache.hits += 1
            cache.mark_present(attributes["key_hash"])
        else:
            cache.misses += 1
            cache.present_keys.pop(attributes["key_hash"], None)
    elif event["type"] == "cache.set":
        cache.mark_present(attributes["key_hash"])
    else:
        cache.present_keys.pop(attributes["key_hash"], None)


def queue_operation(state: SystemState, event: dict[str, Any]) -> None:
    queue = event["attributes"]["queue"]
    change = 1 if event["type"] == "queue.publish" else -1
    state.queues[queue] = max(0, state.queues.get(queue, 0) + change)


def error_event(state: SystemState, event: dict[str, Any]) -> None:
    exception = event["attributes"]["exception_type"]
    state.errors_by_type[exception] = state.errors_by_type.get(exception, 0) + 1


REDUCERS: dict[str, Callable[[SystemState, dict[str, Any]], None]] = {
    "http.request": http_request,
    "http.client": http_client,
    "db.query": db_query,
    "cache.get": cache_operation,
    "cache.set": cache_operation,
    "cache.delete": cache_operation,
    "queue.publish": queue_operation,
    "queue.consume": queue_operation,
    "error": error_event,
}


def apply_event(state: SystemState, event: dict[str, Any]) -> None:
    reducer = REDUCERS.get(event["type"])
    if reducer is None:
        raise ReplayError(f"Unknown event type: {event['type']}")
    key = order_key(event)
    if state.last_key is not None and key <= state.last_key:
        raise ReplayError("Events must be strictly ordered")
    reducer(state, event)
    state.last_key = key
    state.event_count += 1
