from dataclasses import dataclass
from datetime import datetime, timedelta

from .graph import DependencyGraph


@dataclass(frozen=True)
class Candidate:
    node: str
    score: float
    parts: dict[str, float | bool]


def rank_candidates(
    graph: DependencyGraph,
    onsets: dict[str, datetime],
    magnitudes: dict[str, float],
    granger_scores: dict[str, float] | None = None,
    weights: tuple[float, float, float, float] = (0.4, 0.25, 0.2, 0.15),
) -> list[Candidate]:
    if not onsets:
        return []
    ordered = sorted(onsets, key=lambda node: (onsets[node], node))
    graph_missing = not any(graph.adjacency.values())
    scores, candidates = granger_scores or {}, []
    minimum, maximum = min(magnitudes.values(), default=0), max(magnitudes.values(), default=0)
    for index, node in enumerate(ordered):
        if not graph_missing and any(
            dependency in onsets and onsets[dependency] <= onsets[node] + timedelta(seconds=10)
            for dependency in graph.dependencies(node)
        ):
            continue
        explained = len((graph.affected_dependents(node) | {node}) & onsets.keys()) / len(onsets)
        onset_score = 1 - index / max(len(ordered) - 1, 1)
        magnitude = (magnitudes.get(node, 0) - minimum) / max(maximum - minimum, 1e-6)
        parts: dict[str, float | bool] = {
            "explained_fraction": explained,
            "onset_rank": onset_score,
            "granger": scores.get(node, 0),
            "magnitude": magnitude,
            "graph_missing": graph_missing,
        }
        score = (
            onset_score
            if graph_missing
            else sum(
                weight * part
                for weight, part in zip(
                    weights, (explained, onset_score, scores.get(node, 0), magnitude), strict=True
                )
            )
        )
        candidates.append(Candidate(node, min(1, max(0, score)), parts))
    if not candidates:
        return [Candidate(ordered[0], 0.25, {"cycle_ambiguous": True})]
    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.node))[:5]
