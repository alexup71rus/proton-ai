import torch

from protonx.training.model import TinyRouterConfig, TinyRouterModel, build_causal_mask


def test_tiny_router_model_returns_logits_with_vocab_dimension():
    config = TinyRouterConfig(
        vocab_size=64,
        hidden_dim=32,
        num_layers=2,
        num_heads=4,
        max_seq_len=64,
    )
    model = TinyRouterModel(config)
    input_ids = torch.randint(0, 64, (2, 16))
    logits = model(input_ids)
    assert logits.shape == (2, 16, 64)


def test_build_causal_mask_blocks_future_positions():
    mask = build_causal_mask(seq_len=4, device=torch.device("cpu"))
    assert mask.shape == (4, 4)
    assert mask.dtype == torch.bool
    assert mask[0, 3].item() is True
    assert mask[3, 0].item() is False
