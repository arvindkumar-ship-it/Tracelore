import re
from typing import Any

from pydantic import BaseModel, Field

from .propagation import Candidate

SAFE_NAME = re.compile(r"[^A-Za-z0-9_./{}:>\-]")


class EvidenceItem(BaseModel):
    id: str
    kind: str
    node: str
    text: str
    data: dict[str, Any]


class CandidateView(BaseModel):
    node: str
    score: float
    parts: dict[str, float | bool]


class EvidenceBundle(BaseModel):
    candidates: list[CandidateView]
    evidence: list[EvidenceItem]
    similar_incidents: list[dict[str, Any]] = Field(default_factory=list)


def sanitize_name(value: str) -> str:
    return SAFE_NAME.sub("", value)[:80]


def build_bundle(candidates: list[Candidate], facts: list[dict[str, Any]]) -> EvidenceBundle:
    ordered: list[EvidenceItem] = []
    for candidate in candidates[:5]:
        matching = sorted(
            (fact for fact in facts if fact["node"] == candidate.node),
            key=lambda fact: (fact["kind"], str(fact.get("data", {}))),
        )[:3]
        for fact in matching:
            ordered.append(
                EvidenceItem(
                    id=f"E{len(ordered) + 1}",
                    kind=fact["kind"],
                    node=sanitize_name(candidate.node),
                    text=fact["text"][:500],
                    data=fact["data"],
                )
            )
    return EvidenceBundle(
        candidates=[
            CandidateView(
                node=sanitize_name(candidate.node), score=candidate.score, parts=candidate.parts
            )
            for candidate in candidates[:5]
        ],
        evidence=ordered,
    )
