from datetime import UTC, datetime, timedelta

import pytest

from backend.ml.baseline.inference import predict_forecaster
from backend.ml.baseline.paths import endpoint_model_dir
from backend.ml.baseline.serve import PredictInput

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("missing", [0, 300])
async def test_forecaster_requires_recent_contiguous_history(tmp_path, missing):
    at = datetime(2026, 1, 2, tzinfo=UTC)
    directory = endpoint_model_dir(tmp_path, "gateway", "/checkout")
    directory.mkdir(parents=True)
    (directory / "forecaster.onnx").write_bytes(b"never loaded for incomplete history")
    (directory / "normalization.json").write_text("{}")

    class Connection:
        async def fetch(self, *args):
            return [
                {"bucket_start": at - timedelta(minutes=index + 1 + (index >= missing))}
                for index in range(1440)
            ]

    result = await predict_forecaster(
        Connection(), PredictInput(service="gateway", route="/checkout", at=at), tmp_path
    )
    assert result.status == "warming_up" and result.metrics == {}
