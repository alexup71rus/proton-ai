import json
from pathlib import Path

import sentencepiece as spm
import torch
from torch import nn

from protonx.config import TOKENIZER_DIR, WEIGHTS_DIR
from protonx.training.format import serialize_training_record
from protonx.training.model import TinyRouterConfig, TinyRouterModel
from protonx.training.state import TRAINING_STATE
from protonx.training.tokenizer import train_sentencepiece


def _load_records(dataset_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_tokenizer_corpus(records: list[dict], corpus_path: Path) -> None:
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(
        "\n".join(serialize_training_record(record) for record in records),
        encoding="utf-8",
    )


def run_training(dataset_path: Path) -> dict:
    records = _load_records(dataset_path)
    TRAINING_STATE.status = "started"
    TRAINING_STATE.current_step = 0
    TRAINING_STATE.total_steps = len(records)
    TRAINING_STATE.loss = None

    corpus_path = TOKENIZER_DIR / "routing_corpus.txt"
    model_prefix = TOKENIZER_DIR / "routing_spm"
    _write_tokenizer_corpus(records, corpus_path)
    tokenizer_path = train_sentencepiece(corpus_path, model_prefix, vocab_size=512)

    tokenizer = spm.SentencePieceProcessor(model_file=str(tokenizer_path))
    config = TinyRouterConfig(
        vocab_size=tokenizer.get_piece_size(),
        hidden_dim=64,
        num_layers=2,
        num_heads=4,
        max_seq_len=256,
    )
    model = TinyRouterModel(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for index, record in enumerate(records, start=1):
        text = serialize_training_record(record)
        token_ids = tokenizer.encode(text, out_type=int)[: config.max_seq_len]
        if len(token_ids) < 2:
            continue
        encoded = torch.tensor([token_ids], dtype=torch.long)
        logits = model(encoded[:, :-1])
        target = encoded[:, 1:]
        loss = loss_fn(logits.reshape(-1, config.vocab_size), target.reshape(-1))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        TRAINING_STATE.current_step = index
        TRAINING_STATE.loss = float(loss.item())

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = WEIGHTS_DIR / "tiny_router_v1.pt"
    torch.save({"config": config.__dict__, "state_dict": model.state_dict()}, model_path)
    TRAINING_STATE.status = "completed"
    TRAINING_STATE.model_path = str(model_path)
    TRAINING_STATE.tokenizer_path = str(tokenizer_path)
    return TRAINING_STATE.to_dict()
