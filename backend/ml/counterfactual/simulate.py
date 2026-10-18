from backend.ml.causal.graph import event_node

from .cache import apply_cache
from .interventions import CacheHitRate, Intervention, LatencyScale, TimeoutChange
from .span_tree import TraceTree
from .timeout import apply_timeout
from .timing import recompute


def simulate(trees: list[TraceTree], intervention: Intervention) -> set[str]:
    unknown: set[str] = {
        tree.trace_id for tree in trees if tree.root.event["type"] != "http.request"
    }
    if isinstance(intervention, TimeoutChange):
        unknown |= apply_timeout(trees, intervention)
    elif isinstance(intervention, CacheHitRate):
        unknown |= apply_cache(trees, intervention)
    elif isinstance(intervention, LatencyScale):
        for tree in trees:
            for span in tree.spans.values():
                event = span.event
                edge = (
                    f"edge:{event['service']}->{event['attributes'].get('downstream_service', '')}"
                )
                if event_node(event) == intervention.node or edge == intervention.node:
                    span.duration_us = round(span.duration_us * intervention.factor)
                    span.duration_override = True
    for tree in trees:
        for root in tree.roots:
            recompute(root)
    return unknown
