import warnings
from pathlib import Path
from typing import Any

import torch


def export_opset17(
    model: Any, inputs: tuple[Any, ...], path: Path, input_names: list[str], output_names: list[str]
) -> None:
    fastpath = torch.backends.mha.get_fastpath_enabled()
    torch.backends.mha.set_fastpath_enabled(False)
    try:
        with warnings.catch_warnings():
            # Sequence dimensions are fixed; dynamic batch parity is checked after export.
            warnings.filterwarnings("ignore", message="Converting a tensor to a Python.*")
            warnings.filterwarnings(
                "ignore",
                message="You are using the legacy TorchScript.*",
                category=DeprecationWarning,
            )
            warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"torch\.onnx.*")
            torch.onnx.export(
                model,
                inputs,
                str(path),
                input_names=input_names,
                output_names=output_names,
                dynamic_axes={name: {0: "batch"} for name in input_names + output_names},
                opset_version=17,
                dynamo=False,
            )
    finally:
        torch.backends.mha.set_fastpath_enabled(fastpath)
