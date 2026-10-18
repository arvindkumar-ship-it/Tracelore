import re
from typing import Any

from pydantic import BaseModel, Field

from .evidence import EvidenceBundle

NUMBER = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.I)


class RootCauseReport(BaseModel):
    root_cause_node: str
    mechanism: str = Field(max_length=800)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    suggested_fix: str = Field(max_length=500)
    insufficient_evidence: bool


def _numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _numbers(item)]
    if isinstance(value, list):
        return [number for item in value for number in _numbers(item)]
    return []


def check(report: RootCauseReport, bundle: EvidenceBundle) -> list[str]:
    violations = []
    candidates = {candidate.node: candidate for candidate in bundle.candidates}
    evidence = {item.id: item for item in bundle.evidence}
    if report.root_cause_node not in candidates:
        violations.append("unknown_candidate")
    if any(identifier not in evidence for identifier in report.evidence_ids):
        violations.append("unknown_evidence")
    if len(set(report.evidence_ids)) < 3 and not report.insufficient_evidence:
        violations.append("insufficient_citations")
    numbers = [
        number
        for identifier in report.evidence_ids
        if identifier in evidence
        for number in _numbers(evidence[identifier].data)
    ]
    if any(
        not any(abs(float(match) - number) <= max(abs(number) * 0.01, 1e-9) for number in numbers)
        for match in NUMBER.findall(report.mechanism)
    ):
        violations.append("ungrounded_number")
    candidate = candidates.get(report.root_cause_node)
    if candidate and report.confidence > candidate.score + 0.2 + 1e-9:
        violations.append("overconfident")
    return violations


def rules_report(bundle: EvidenceBundle) -> RootCauseReport:
    if not bundle.candidates:
        return RootCauseReport(
            root_cause_node="",
            mechanism="There is not enough recorded evidence to rank a cause.",
            confidence=0,
            evidence_ids=[],
            suggested_fix="Capture more instrumented requests.",
            insufficient_evidence=True,
        )
    top = bundle.candidates[0]
    evidence = [item.id for item in bundle.evidence if item.node == top.node][:3]
    return RootCauseReport(
        root_cause_node=top.node,
        mechanism="The earliest affected dependency explains the recorded propagation path."
        if not top.parts.get("graph_missing")
        else "The observed onset ranks this node first; a dependency graph is unavailable.",
        confidence=top.score,
        evidence_ids=evidence,
        suggested_fix="Inspect the cited spans and recent changes on this node.",
        insufficient_evidence=len(evidence) < 3,
    )
