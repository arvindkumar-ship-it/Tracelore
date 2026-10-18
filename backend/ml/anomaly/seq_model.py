from typing import Any, cast

import numpy as np
import torch
from torch import nn

CONTEXT, HIDDEN = 64, 64


class SequenceTransformer(nn.Module):
    def __init__(self, vocabulary_size: int) -> None:
        super().__init__()
        if not 3 <= vocabulary_size <= 2000:
            raise ValueError("vocabulary must contain 3..2000 tokens")
        self.tokens = nn.Embedding(vocabulary_size, HIDDEN)
        self.position = nn.Parameter(torch.zeros(1, CONTEXT, HIDDEN))
        layer = nn.TransformerEncoderLayer(HIDDEN, 4, 128, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, 2)
        self.output = nn.Linear(HIDDEN, vocabulary_size)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        length = tokens.shape[1]
        mask = torch.triu(
            torch.full((length, length), float("-inf"), device=tokens.device), diagonal=1
        )
        hidden = self.tokens(tokens) + self.position[:, :length]
        return cast(torch.Tensor, self.output(self.encoder(hidden, mask=mask)))


def train_sequences(
    train: list[list[int]],
    validation: list[list[int]],
    vocabulary_size: int,
    seed: int = 19,
    epochs: int = 20,
) -> tuple[SequenceTransformer, dict[str, Any]]:
    if not train or not validation:
        raise ValueError("time-based train and validation traces are required")
    torch.manual_seed(seed)
    model = SequenceTransformer(vocabulary_size)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    for _ in range(epochs):
        model.train()
        for trace in train:
            if len(trace) < 2:
                continue
            inputs = torch.tensor([trace[:CONTEXT]], dtype=torch.long)
            targets = torch.tensor([trace[1 : CONTEXT + 1]], dtype=torch.long)
            inputs = inputs[:, : targets.shape[1]]
            optimizer.zero_grad()
            loss = nn.functional.cross_entropy(model(inputs).flatten(0, 1), targets.flatten())
            torch.autograd.backward(loss)
            optimizer.step()
    model.eval()
    calibration = sorted(score for trace in validation for score in surprise(model, trace))
    return model, {
        "calibration": calibration,
        "threshold": float(np.quantile(calibration, 0.999)),
        "seed": seed,
    }


def surprise(model: SequenceTransformer, tokens: list[int]) -> list[float]:
    if len(tokens) < 2:
        return []
    inputs = torch.tensor([tokens[:CONTEXT]], dtype=torch.long)
    targets = torch.tensor(tokens[1 : CONTEXT + 1], dtype=torch.long)
    with torch.no_grad():
        log_probabilities = torch.log_softmax(model(inputs[:, : len(targets)]), dim=-1)[0]
        return [
            float(value)
            for value in (-log_probabilities[torch.arange(len(targets)), targets]).tolist()
        ]
