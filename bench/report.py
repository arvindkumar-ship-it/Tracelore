from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def write_report(directory: Path, results: list[dict[str, Any]]) -> None:
    rows = [
        "# Live fault benchmark",
        "",
        "| Bug | Seed | Detected | Exact start | RCA | Delay (s) | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        rows.append(
            "| "
            + " | ".join(
                str(result.get(key))
                for key in (
                    "bug_id",
                    "seed",
                    "detected",
                    "exact_start",
                    "root_cause_correct",
                    "detection_delay_seconds",
                    "failure",
                )
            )
            + " |"
        )
    rows.extend(_aggregate(results))
    rows.extend(
        [
            "",
            "Controls are listed separately from bug accuracy. Full 24-hour FPR, LLM-off "
            "ablation and real-fix backtests require their separate runs. Missing observations "
            "are failures for accuracy and are never invented timings.",
        ]
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "benchmark.md").write_text("\n".join(rows) + "\n")


def _aggregate(results: list[dict[str, Any]]) -> list[str]:
    bugs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        if not result["control"]:
            bugs[result["bug_id"]].append(result)
    rows = [
        "",
        "| Bug | Runs | Recall mean/min | Exact start mean/min | RCA mean/min |",
        "| --- | --- | --- | --- | --- |",
    ]
    for identifier, values in sorted(bugs.items()):
        cells = []
        for key in ("detected", "exact_start", "root_cause_correct"):
            observations = [float(bool(value[key])) for value in values]
            cells.append(f"{mean(observations):.3f} / {min(observations):.3f}")
        rows.append(f"| {identifier} | {len(values)} | " + " | ".join(cells) + " |")
    scored = [result for values in bugs.values() for result in values]
    if scored:
        for key in ("exact_start", "root_cause_correct"):
            seeds = sorted({result.get("seed", 0) for result in scored})
            per_seed = [
                mean(float(bool(item[key])) for item in scored if item.get("seed", 0) == seed)
                for seed in seeds
            ]
            rows.append(
                f"\n{key}: mean={mean(per_seed):.3f}, minimum seed fraction={min(per_seed):.3f}."
            )
    return rows
