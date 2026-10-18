from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.common.metrics import REPLAY_SECONDS
from backend.ledger.records import order_key

from .reducers import ReplayError, apply_event
from .state import SystemState


@dataclass(frozen=True)
class TraceReplay:
    events: list[dict[str, Any]]
    final_state: SystemState
    span_tree: list[dict[str, Any]]


def fold_events(events: list[dict[str, Any]]) -> SystemState:
    state = SystemState()
    for event in sorted(events, key=order_key):
        apply_event(state, event)
    return state


async def replay_until(repo: Any, snapshots: Any, until: datetime) -> SystemState:
    with REPLAY_SECONDS.time():
        state = await snapshots.latest_before(until) if snapshots is not None else None
        state = state or SystemState()
        async for event in repo.iter_events_ordered(after_key=state.last_key, until=until):
            apply_event(state, event)
        return state


async def replay_trace(repo: Any, trace_id: str) -> TraceReplay:
    events = await repo.get_trace_events(trace_id)
    spans = {event["span_id"] for event in events}
    tree = [
        {
            "id": event["span_id"],
            "parent": event["parent_span_id"],
            "event_id": event["event_id"],
            "orphan": event["parent_span_id"] is not None and event["parent_span_id"] not in spans,
        }
        for event in events
    ]
    return TraceReplay(events, fold_events(events), tree)


async def state_at_event(repo: Any, trace_id: str, event_id: str) -> SystemState:
    events = sorted(await repo.get_trace_events(trace_id), key=order_key)
    state = SystemState()
    for event in events:
        apply_event(state, event)
        if event["event_id"] == event_id:
            return state
    raise ReplayError("Event does not belong to this trace")
