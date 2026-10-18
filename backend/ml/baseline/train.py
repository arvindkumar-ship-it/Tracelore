import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .forecaster import CONTEXT, HORIZON, PatchForecaster


class TrainingError(ValueError):
    """There is insufficient clean time-ordered history to train a forecast."""


def windows(values: np.ndarray, stride: int = 60) -> tuple[np.ndarray, np.ndarray]:
    indices = range(0, len(values) - CONTEXT - HORIZON + 1, stride)
    inputs = [values[index : index + CONTEXT] for index in indices]
    targets = [values[index + CONTEXT : index + CONTEXT + HORIZON] for index in indices]
    if not inputs:
        raise TrainingError("at least 1500 consecutive clean minutes are required")
    return np.asarray(inputs, dtype=np.float32), np.asarray(targets, dtype=np.float32)


def train_forecaster(
    values: np.ndarray, destination: Path, seed: int = 19, epochs: int = 20
) -> dict[str, object]:
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    split = int(len(values) * 0.8)
    center, scale = values[:split].mean(axis=0), np.maximum(values[:split].std(axis=0), 1e-6)
    normalized = (values - center) / scale
    train_inputs, train_targets = windows(normalized[:split])
    valid_inputs, valid_targets = windows(normalized[split:])
    model = PatchForecaster()
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(train_inputs), torch.from_numpy(train_targets)),
        batch_size=16,
        shuffle=True,
        generator=generator,
    )
    _optimize(
        model, loader, torch.from_numpy(valid_inputs), torch.from_numpy(valid_targets), epochs
    )
    with torch.no_grad():
        residuals = valid_targets - model(torch.from_numpy(valid_inputs)).numpy()
    metadata: dict[str, object] = {
        "mean": center.tolist(),
        "std": scale.tolist(),
        "low_residual": np.quantile(residuals, 0.025, axis=(0, 1)).tolist(),
        "high_residual": np.quantile(residuals, 0.975, axis=(0, 1)).tolist(),
        "seed": seed,
    }
    destination.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), destination / "forecaster.pt")
    (destination / "normalization.json").write_text(json.dumps(metadata))
    return metadata


def _optimize(
    model: PatchForecaster,
    loader: DataLoader[tuple[torch.Tensor, ...]],
    valid: torch.Tensor,
    targets: torch.Tensor,
    epochs: int,
) -> None:
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    best_loss, stale, best = float("inf"), 0, None
    for _ in range(epochs):
        model.train()
        for inputs, expected in loader:
            optimizer.zero_grad()
            loss = nn.functional.huber_loss(model(inputs), expected)
            torch.autograd.backward(loss)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(nn.functional.huber_loss(model(valid), targets))
        if validation_loss < best_loss:
            best_loss, stale = validation_loss, 0
            best = {name: value.detach().clone() for name, value in model.state_dict().items()}
        else:
            stale += 1
        scheduler.step()
        if stale >= 4:
            break
    if best is not None:
        model.load_state_dict(best)
