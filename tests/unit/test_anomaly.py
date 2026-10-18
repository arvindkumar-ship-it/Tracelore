from datetime import UTC, datetime

import numpy as np
import pytest

from backend.ml.anomaly.bocpd import BOCPD
from backend.ml.anomaly.contracts import Signal
from backend.ml.anomaly.fusion import fuse
from backend.ml.anomaly.ngram_model import NgramModel
from backend.ml.anomaly.trace_assembler import TraceAssembler

pytestmark = pytest.mark.unit


def test_bocpd_step_and_state():
    model = BOCPD()
    random = np.random.default_rng(19)
    for value in random.normal(0, 1, 300):
        model.update(float(value))
    restored = BOCPD.from_bytes(model.to_bytes())
    outputs = [model.update(8) for _ in range(3)]
    assert max(output.short_mass for output in outputs) > 0.7
    assert outputs == [restored.update(8) for _ in range(3)]
    assert len(model.run_probs) <= 500


def test_bocpd_normal_false_alarms():
    model = BOCPD()
    random = np.random.default_rng(103)
    alarms = 0
    for index, value in enumerate(random.normal(0, 1, 10000)):
        output = model.update(float(value))
        if index > 20:
            alarms += output.short_mass > 0.7
    assert alarms < 10
    assert np.isfinite(model.run_probs).all()


def test_ngram_missing_and_unknown():
    model = NgramModel()
    normal = ["root", "cache", "db", "payment", "return"]
    model.train([normal] * 100, [normal] * 30)
    assert max(model.score_trace(normal)) <= model.threshold + 1e-8
    assert max(model.score_trace(normal[:-2] + normal[-1:])) > model.threshold
    assert all(np.isfinite(model.score_trace(["unseen"])))
    assert NgramModel.from_dict(model.to_dict()).score_trace(normal) == model.score_trace(normal)


def test_fusion_noisy_or():
    at = datetime(2026, 1, 1, tzinfo=UTC)
    signals = [
        Signal(
            id=str(index),
            kind="metric",
            service="x",
            route="/x",
            detected_at=at,
            estimated_start=at,
            confidence=0.8,
        )
        for index in range(2)
    ]
    result = fuse(signals, [])
    assert len(result) == 1 and result[0].confidence == pytest.approx(0.96)
    assert fuse(signals, result) == []


def test_assembler_grace_and_cap(event_factory):
    assembler = TraceAssembler(max_open=1)
    event = event_factory()
    assembler.add(event, 100)
    assert assembler.ready(101) == []
    assert assembler.ready(102)[0][0] == event["trace_id"]
    assembler.add(event_factory(), 103)
    assembler.add(event_factory(), 104)
    assert assembler.evictions == 1
