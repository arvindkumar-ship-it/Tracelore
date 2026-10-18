import asyncio
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from backend.common.errors import ApiError, Code

from .contracts import METRICS, BaselineRange, MetricRange
from .serve import PredictInput


@lru_cache(maxsize=16)
def load_session(path: str) -> Any:
    import onnxruntime

    return onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])


async def predict_forecaster(connection: Any, body: PredictInput, directory: Path) -> BaselineRange:
    from .paths import endpoint_model_dir

    directory = endpoint_model_dir(directory, body.service, body.route)
    metadata_path = directory / "normalization.json"
    model_path = directory / "forecaster.onnx"
    if not model_path.is_file() or not metadata_path.is_file():
        raise ApiError(Code.UNAVAILABLE, "Train and export a forecaster before selecting it", 503)
    rows = await connection.fetch(
        "SELECT * FROM metric_buckets WHERE service=$1 AND route=$2 "
        "AND bucket_start<$3 ORDER BY bucket_start DESC LIMIT 1440",
        body.service,
        body.route,
        body.at,
    )
    minute = body.at.replace(second=0, microsecond=0)
    if len(rows) != 1440 or any(
        row["bucket_start"] != minute - timedelta(minutes=index + 1)
        for index, row in enumerate(rows)
    ):
        return BaselineRange(
            service=body.service,
            route=body.route,
            at=body.at,
            model="forecaster",
            status="warming_up",
        )
    values = np.array(
        [
            [
                row["count"],
                row["errors"] / max(row["count"], 1),
                row["p50_ms"],
                row["p95_ms"],
                row["p99_ms"],
            ]
            for row in reversed(rows)
        ],
        dtype=np.float32,
    )
    metadata = json.loads(metadata_path.read_text())
    center, scale = np.array(metadata["mean"]), np.array(metadata["std"])
    normalized = ((values - center) / scale).astype(np.float32)[None, :, :]
    forecast = await asyncio.to_thread(_infer, str(model_path), normalized)
    metrics = {
        metric: MetricRange(
            low=max(
                0,
                float(
                    (forecast[index] + metadata["low_residual"][index]) * scale[index]
                    + center[index]
                ),
            ),
            expected=max(0, float(forecast[index] * scale[index] + center[index])),
            high=max(
                0,
                float(
                    (forecast[index] + metadata["high_residual"][index]) * scale[index]
                    + center[index]
                ),
            ),
            scale=max(1e-6, float(scale[index])),
            n=1440,
            source="global",
        )
        for index, metric in enumerate(METRICS)
    }
    return BaselineRange(
        service=body.service,
        route=body.route,
        at=body.at,
        model="forecaster",
        status="ready",
        metrics=metrics,
    )


def _infer(path: str, values: np.ndarray) -> Any:
    return load_session(path).run(None, {"values": values})[0][0, 0]
