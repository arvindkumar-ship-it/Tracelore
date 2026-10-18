from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
from tracelore.canonical import hash_payload

from backend.ml.anomaly.tokens import tokenize


@dataclass(frozen=True)
class TraceSummary:
    representative_trace: str
    trace_count: int
    quantiles: dict[str, float]
    mode: str = "summarized"


def summarize(events: list[dict[str, Any]], clusters: int = 8) -> list[TraceSummary]:
    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        traces[event["trace_id"]].append(event)
    ids = sorted(traces)
    if not ids:
        return []
    vectors, durations = [], []
    for identifier in ids:
        vector = np.zeros(65)
        for event in traces[identifier]:
            vector[int(hash_payload(tokenize(event))[:8], 16) % 64] += 1
        root = next(
            (event for event in traces[identifier] if event["parent_span_id"] is None),
            traces[identifier][-1],
        )
        durations.append(root["duration_ms"])
        vector[:64] /= max(vector[:64].sum(), 1)
        vector[64] = np.log1p(root["duration_ms"])
        vectors.append(vector)
    matrix = np.asarray(vectors)
    count = min(clusters, len(ids))
    centers = matrix[np.linspace(0, len(ids) - 1, count, dtype=int)].copy()
    for _ in range(20):
        labels = np.argmin(((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2), axis=1)
        updated = np.array(
            [
                matrix[labels == label].mean(axis=0) if np.any(labels == label) else centers[label]
                for label in range(count)
            ]
        )
        if np.allclose(centers, updated, rtol=0, atol=1e-10):
            break
        centers = updated
    return _summaries(ids, matrix, np.asarray(durations), labels, centers)


def _summaries(
    ids: list[str], vectors: Any, durations: Any, labels: Any, centers: Any
) -> list[TraceSummary]:
    results = []
    for label, center in enumerate(centers):
        members = np.flatnonzero(labels == label)
        if not len(members):
            continue
        representative = int(members[np.argmin(((vectors[members] - center) ** 2).sum(axis=1))])
        values = durations[members]
        results.append(
            TraceSummary(
                ids[representative],
                len(members),
                {
                    "p50_ms": float(np.quantile(values, 0.5)),
                    "p95_ms": float(np.quantile(values, 0.95)),
                    "p99_ms": float(np.quantile(values, 0.99)),
                },
            )
        )
    return results
