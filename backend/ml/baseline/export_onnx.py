from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

from backend.ml.onnx_export import export_opset17

from .forecaster import CONTEXT, FEATURES, PatchForecaster


def export_model(directory: Path) -> float:
    model = PatchForecaster()
    model.load_state_dict(
        torch.load(directory / "forecaster.pt", weights_only=True, map_location="cpu")
    )
    model.eval()
    example = torch.linspace(-1, 1, CONTEXT * FEATURES).reshape(1, CONTEXT, FEATURES)
    path = directory / "forecaster.onnx"
    export_opset17(model, (example,), path, ["values"], ["forecast"])
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        expected = model(example).numpy()
    difference = float(np.max(np.abs(expected - session.run(None, {"values": example.numpy()})[0])))
    if difference >= 1e-4:
        raise ValueError(f"ONNX parity gate failed: {difference}")
    return difference
