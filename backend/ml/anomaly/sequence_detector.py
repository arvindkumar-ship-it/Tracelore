from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .contracts import Signal
from .ngram_model import NgramModel
from .tokens import tokenize


class SequenceDetector:
    def __init__(self) -> None:
        self.windows: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def score(
        self,
        events: list[dict[str, Any]],
        model: NgramModel,
        at: datetime,
        neural_scores: list[float] | None = None,
        neural_threshold: float = float("inf"),
        neural_confidence: Callable[[float], float] | None = None,
    ) -> list[Signal]:
        if not events:
            return []
        root = next(
            (
                event
                for event in events
                if event["type"] == "http.request" and event["parent_span_id"] is None
            ),
            None,
        )
        if root is None:
            return []
        scores = model.score_trace([tokenize(event) for event in events])
        anomalies = [
            (index, score)
            for index, score in enumerate(scores)
            if score > model.threshold
            or (neural_scores is not None and neural_scores[index] > neural_threshold)
        ]
        if not anomalies:
            return []
        key = root["service"], root["attributes"]["route"]
        window = self.windows[key]
        while window and at - window[0] > timedelta(seconds=30):
            window.popleft()
        window.append(at)
        signals = []
        for index, score in anomalies:
            event = events[min(index, len(events) - 1)]
            votes = (["ngram"] if score > model.threshold else []) + (
                ["transformer"]
                if neural_scores is not None and neural_scores[index] > neural_threshold
                else []
            )
            confidence = model.confidence(score)
            if neural_scores is not None and neural_confidence is not None:
                confidence = max(confidence, neural_confidence(neural_scores[index]))
                confidence = min(confidence, 0.99 if len(votes) == 2 else 0.85)
            signals.append(
                Signal(
                    id=f"sequence:{event['event_id']}:{index}",
                    kind="sequence",
                    service=root["service"],
                    route=key[1],
                    detected_at=at,
                    estimated_start=datetime.fromisoformat(event["ended_at"]),
                    event_id=event["event_id"],
                    trace_id=root["trace_id"],
                    surprise=score,
                    confidence=confidence,
                    incident_grade=len(window) >= 3,
                    model_votes=votes,
                    anomaly_kind="missing_end" if index == len(events) else "unexpected",
                )
            )
        return signals
