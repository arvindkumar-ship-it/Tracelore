from typing import Any

from .interventions import Intervention
from .report import build_report


def compare_runs(
    bug_events: list[dict[str, Any]], fixed_events: list[dict[str, Any]], intervention: Intervention
) -> dict[str, Any]:
    if not bug_events or not fixed_events:
        raise ValueError("Backtests require non-empty recorded bug and real-fix runs")
    from .aggregate import summarize
    from .span_tree import build_trees

    simulated = build_report(bug_events, intervention)
    actual = summarize(build_trees(fixed_events), original=True)
    errors = {
        metric: abs(simulated.counterfactual[metric] - actual[metric])
        / max(abs(actual[metric]), 1e-9)
        for metric in ("error_rate", "p95_ms")
    }
    return {
        "relative_error": errors,
        "passed": all(value <= 0.15 for value in errors.values()),
        "simulated": simulated.counterfactual,
        "actual": actual,
    }
