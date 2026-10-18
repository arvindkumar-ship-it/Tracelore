from math import ceil

from .span_tree import TraceTree


def quantile(values: list[int], fraction: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, ceil(fraction * len(ordered)) - 1)] / 1000


def summarize(trees: list[TraceTree], original: bool = False) -> dict[str, float]:
    roots = [tree.root for tree in trees]
    durations = [root.original_duration_us if original else root.duration_us for root in roots]
    errors = sum((root.original_status if original else root.status) == "error" for root in roots)
    return {
        "count": float(len(roots)),
        "error_rate": errors / max(1, len(roots)),
        "p50_ms": quantile(durations, 0.50),
        "p95_ms": quantile(durations, 0.95),
        "p99_ms": quantile(durations, 0.99),
        "total_request_time_ms": sum(durations) / 1000,
        "slowest_trace_ms": max(durations, default=0) / 1000,
    }
