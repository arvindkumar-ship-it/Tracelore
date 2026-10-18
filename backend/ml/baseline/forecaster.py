from typing import cast

import torch
from torch import nn

FEATURES, CONTEXT, HORIZON, PATCH_LENGTH = 5, 1440, 60, 12
PATCH_COUNT, HIDDEN = CONTEXT // PATCH_LENGTH, 64


class PatchForecaster(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Linear(PATCH_LENGTH, HIDDEN)
        self.position = nn.Parameter(torch.zeros(1, PATCH_COUNT, HIDDEN))
        layer = nn.TransformerEncoderLayer(HIDDEN, 4, 128, 0.1, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, 3, enable_nested_tensor=False)
        self.head = nn.Linear(PATCH_COUNT * HIDDEN, HORIZON)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        batch = values.shape[0]
        channels = values.transpose(1, 2).reshape(batch * FEATURES, CONTEXT)
        patches = channels.reshape(batch * FEATURES, PATCH_COUNT, PATCH_LENGTH)
        encoded = self.encoder(self.embedding(patches) + self.position)
        output = self.head(encoded.flatten(1))
        return cast(torch.Tensor, output.reshape(batch, FEATURES, HORIZON).transpose(1, 2))
