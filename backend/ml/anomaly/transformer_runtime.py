import json
from pathlib import Path

import numpy as np

from .tokens import END, START, UNKNOWN


class SequenceRuntime:
    def __init__(self, directory: Path) -> None:
        import onnxruntime

        metadata = json.loads((directory / "sequence.json").read_text())
        self.vocabulary = metadata["vocabulary"]
        self.threshold = float(metadata["threshold"])
        self.calibration = np.asarray(metadata["calibration"])
        self.session = onnxruntime.InferenceSession(
            str(directory / "sequence.onnx"), providers=["CPUExecutionProvider"]
        )

    def score(self, tokens: list[str]) -> list[float]:
        ids = (
            [self.vocabulary[START]]
            + [self.vocabulary.get(token, self.vocabulary[UNKNOWN]) for token in tokens]
            + [self.vocabulary[END]]
        )
        scores = []
        for start in range(1, len(ids), 32):
            targets = list(range(start, min(len(ids), start + 32)))
            windows = np.full((len(targets), 64), self.vocabulary[UNKNOWN], dtype=np.int64)
            positions = []
            for row, index in enumerate(targets):
                context = ids[max(0, index - 64) : index]
                windows[row, : len(context)] = context
                positions.append(len(context) - 1)
            logits = self.session.run(None, {"tokens": windows})[0]
            for row, (index, position) in enumerate(zip(targets, positions, strict=True)):
                values = logits[row, position].astype(np.float64)
                log_normalizer = float(np.log(np.exp(values - values.max()).sum()) + values.max())
                scores.append(log_normalizer - float(values[ids[index]]))
        return scores

    def confidence(self, score: float) -> float:
        return float(
            np.searchsorted(self.calibration, score, side="right") / max(len(self.calibration), 1)
        )
