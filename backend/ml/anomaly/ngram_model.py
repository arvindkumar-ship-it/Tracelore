from collections import Counter, defaultdict
from math import log
from typing import Any

import numpy as np

from .tokens import END, START, UNKNOWN


class NgramModel:
    def __init__(self, smoothing: float = 0.1) -> None:
        self.smoothing = smoothing
        self.vocabulary = {START, END, UNKNOWN}
        self.counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        self.calibration: list[float] = []
        self.threshold = float("inf")

    def train(self, traces: list[list[str]], validation: list[list[str]]) -> None:
        frequencies = Counter(token for trace in traces for token in trace)
        self.vocabulary |= {token for token, count in frequencies.items() if count >= 5}
        self.counts.clear()
        for trace in traces:
            tokens = [START, START] + [self._known(token) for token in trace] + [END]
            for index in range(2, len(tokens)):
                self.counts[(tokens[index - 2], tokens[index - 1])][tokens[index]] += 1
        self.calibration = sorted(
            score for trace in validation for score in self.score_trace(trace)
        )
        if self.calibration:
            self.threshold = float(np.quantile(self.calibration, 0.999))

    def _known(self, token: str) -> str:
        return token if token in self.vocabulary else UNKNOWN

    def score_trace(self, tokens: list[str]) -> list[float]:
        history, scores = [START, START], []
        for token in [*tokens, END]:
            token = self._known(token)
            counts = self.counts.get((history[-2], history[-1]), Counter())
            probability = (counts[token] + self.smoothing) / (
                sum(counts.values()) + self.smoothing * len(self.vocabulary)
            )
            scores.append(-log(probability))
            history.append(token)
        return scores

    def confidence(self, score: float) -> float:
        if not self.calibration:
            return 0
        return float(np.searchsorted(self.calibration, score, side="right") / len(self.calibration))

    def to_dict(self) -> dict[str, Any]:
        return {
            "smoothing": self.smoothing,
            "vocabulary": sorted(self.vocabulary),
            "counts": [
                [*key, dict(sorted(value.items()))] for key, value in sorted(self.counts.items())
            ],
            "calibration": self.calibration,
            "threshold": self.threshold if self.calibration else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NgramModel":
        model = cls(value["smoothing"])
        model.vocabulary = set(value["vocabulary"])
        model.counts = defaultdict(
            Counter, {(a, b): Counter(counts) for a, b, counts in value["counts"]}
        )
        model.calibration = value["calibration"]
        model.threshold = value["threshold"] if value["threshold"] is not None else float("inf")
        return model
