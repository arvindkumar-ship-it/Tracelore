from typing import Any, Literal

from pydantic import BaseModel
from tracelore.canonical import canonical_json, sha256_hex

from backend.common.errors import ApiError, Code

from .aggregate import summarize
from .interventions import Intervention
from .simulate import simulate
from .span_tree import build_trees

MAX_EVENTS = 10_000
ASSUMPTIONS = [
    "Recorded spans describe observed work, not re-execution of application code.",
    "sequential_dependency: non-overlapping later siblings shift with preceding work.",
    "Recorded self time and overlapping siblings are preserved.",
    "Latency scaling alone does not re-evaluate existing timeout policies.",
    "Cache misses are converted in a stable event-hash order; fallback DB siblings are removed.",
]


class CounterfactualReport(BaseModel):
    mode: Literal["simulated"] = "simulated"
    intervention: Intervention
    original: dict[str, float]
    counterfactual: dict[str, float]
    verdict: str
    side_effects: dict[str, float]
    assumptions: list[str]
    unsimulatable_count: int
    unsimulatable_percent: float
    input_digest: str
    result_digest: str


def build_report(events: list[dict[str, Any]], intervention: Intervention) -> CounterfactualReport:
    if not events:
        raise ApiError(Code.NOT_FOUND, "No recorded traces in this window", 404)
    if len(events) > MAX_EVENTS:
        raise ApiError(Code.TOO_LARGE, "Choose a window with at most 10,000 events")
    trees = build_trees(events)
    original = summarize(trees, original=True)
    unknown = simulate(trees, intervention)
    simulated = summarize(trees)
    percent = 100 * len(unknown) / max(len(trees), 1)
    verdict = f"error rate {original['error_rate']:.1%} → {simulated['error_rate']:.1%} (simulated)"
    if percent >= 20:
        verdict = f"Inconclusive: {percent:.1f}% of traces could not be simulated"
    report = CounterfactualReport(
        intervention=intervention,
        original=original,
        counterfactual=simulated,
        verdict=verdict,
        side_effects=_effects(trees, original, simulated),
        assumptions=ASSUMPTIONS,
        unsimulatable_count=len(unknown),
        unsimulatable_percent=percent,
        input_digest=sha256_hex(
            canonical_json(
                {
                    "event_ids": sorted(event["event_id"] for event in events),
                    "intervention": intervention.model_dump(),
                }
            )
        ),
        result_digest="",
    )
    report.result_digest = sha256_hex(
        canonical_json(report.model_dump(mode="json", exclude={"result_digest"}))
    )
    return report


def _effects(trees: Any, before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {
        "total_request_time_delta_ms": after["total_request_time_ms"]
        - before["total_request_time_ms"],
        "p99_delta_ms": after["p99_ms"] - before["p99_ms"],
        "slowest_trace_delta_ms": after["slowest_trace_ms"] - before["slowest_trace_ms"],
        "new_timeouts_count": sum(
            span.new_timeout for tree in trees for span in tree.spans.values()
        ),
        "flipped_to_ok": sum(
            tree.root.original_status == "error" and tree.root.status == "ok" for tree in trees
        ),
        "flipped_to_error": sum(
            tree.root.original_status == "ok" and tree.root.status == "error" for tree in trees
        ),
    }
