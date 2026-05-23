from dataclasses import dataclass

import torch
from torch import nn


@dataclass
class TinyRouterConfig:
    vocab_size: int
    hidden_dim: int
    num_layers: int
    num_heads: int
    max_seq_len: int


def build_causal_mask(seq_len: int, device: torch.device) -> torch.Tensor:
    mask = torch.full((seq_len, seq_len), float("-inf"), device=device)
    return torch.triu(mask, diagonal=1)


class TinyRouterBlock(nn.Module):
    def __init__(self, config: TinyRouterConfig):
        super().__init__()
        self.norm_1 = nn.LayerNorm(config.hidden_dim)
        self.attn = nn.MultiheadAttention(
            config.hidden_dim,
            config.num_heads,
            batch_first=True,
        )
        self.norm_2 = nn.LayerNorm(config.hidden_dim)
        self.ff = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim * 4),
            nn.GELU(),
            nn.Linear(config.hidden_dim * 4, config.hidden_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attn_input = self.norm_1(x)
        attn_mask = build_causal_mask(attn_input.shape[1], attn_input.device)
        attn_output, _ = self.attn(
            attn_input,
            attn_input,
            attn_input,
            attn_mask=attn_mask,
            need_weights=False,
        )
        x = x + attn_output
        x = x + self.ff(self.norm_2(x))
        return x


class TinyRouterModel(nn.Module):
    def __init__(self, config: TinyRouterConfig):
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.hidden_dim)
        self.position_embedding = nn.Embedding(config.max_seq_len, config.hidden_dim)
        self.blocks = nn.ModuleList(
            [TinyRouterBlock(config) for _ in range(config.num_layers)]
        )
        self.norm = nn.LayerNorm(config.hidden_dim)
        self.head = nn.Linear(config.hidden_dim, config.vocab_size)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        positions = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)
        for block in self.blocks:
            x = block(x)
        return self.head(self.norm(x))
