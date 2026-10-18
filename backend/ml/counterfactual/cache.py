from math import ceil
from statistics import median

from tracelore.canonical import hash_payload

from .interventions import CacheHitRate
from .span_tree import TraceTree


def apply_cache(trees: list[TraceTree], intervention: CacheHitRate) -> set[str]:
    matching = [
        tree
        for tree in trees
        if tree.root.event["service"] == intervention.service
        and tree.root.event["attributes"].get("route") == intervention.route
    ]
    gets = [
        (tree, span)
        for tree in matching
        for span in tree.spans.values()
        if span.event["type"] == "cache.get"
    ]
    hits = [span.duration_us for _, span in gets if span.event["attributes"]["hit"]]
    misses = [(tree, span) for tree, span in gets if not span.event["attributes"]["hit"]]
    required = max(0, min(len(misses), ceil(intervention.target_hit_rate * len(gets) - len(hits))))
    if not required:
        return set()
    if not hits:
        return {tree.trace_id for tree, _ in misses}
    ordered = sorted(misses, key=lambda pair: hash_payload(pair[1].event["event_id"]))[:required]
    for tree, span in ordered:
        span.duration_us, span.duration_override = round(median(hits)), True
        parent = tree.spans.get(span.event["parent_span_id"])
        if parent:
            for sibling in parent.children:
                if (
                    sibling.event["type"] == "db.query"
                    and sibling.original_start_us >= span.original_start_us
                ):
                    sibling.removed = True
    return set()
