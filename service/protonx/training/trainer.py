import json
import threading
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


def _batch_records(tokenizer: spm.SentencePieceProcessor, texts: list[str], max_seq_len: int) -> torch.Tensor | None:
    sequences: list[list[int]] = []
    for text in texts:
        token_ids = tokenizer.encode(text, out_type=int)[:max_seq_len]
        if len(token_ids) >= 2:
            sequences.append(token_ids)
    if not sequences:
        return None
    max_len = max(len(seq) for seq in sequences)
    pad_id = tokenizer.pad_id()
    padded = [seq + [pad_id] * (max_len - len(seq)) for seq in sequences]
    return torch.tensor(padded, dtype=torch.long)


def _update_metrics() -> None:
    if TRAINING_STATE.loss_history:
        TRAINING_STATE.metrics = {
            "avg_loss": sum(TRAINING_STATE.loss_history) / len(TRAINING_STATE.loss_history),
            "best_loss": min(TRAINING_STATE.loss_history),
            "last_loss": TRAINING_STATE.loss_history[-1],
        }
    else:
        TRAINING_STATE.metrics = {}


def run_training(
    dataset_path: Path,
    epochs: int = 1,
    batch_size: int = 1,
    model_name: str = "tiny-router",
    tokenizer_name: str = "sentencepiece-bpe",
) -> dict:
    TRAINING_STATE.status = "running"
    TRAINING_STATE.error = None
    try:
        records = _load_records(dataset_path)
        TRAINING_STATE.current_epoch = 0
        TRAINING_STATE.total_epochs = epochs
        TRAINING_STATE.current_step = 0
        TRAINING_STATE.total_steps = max(1, ((len(records) + batch_size - 1) // batch_size) * epochs)
        TRAINING_STATE.loss = None
        TRAINING_STATE.loss_history = []
        TRAINING_STATE.metrics = {}
        TRAINING_STATE.batch_size = batch_size
        TRAINING_STATE.model_name = model_name
        TRAINING_STATE.tokenizer_name = tokenizer_name

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

        step_index = 0
        for epoch in range(1, epochs + 1):
            TRAINING_STATE.current_epoch = epoch
            for batch_start in range(0, len(records), batch_size):
                batch_records = records[batch_start : batch_start + batch_size]
                encoded = _batch_records(
                    tokenizer,
                    [serialize_training_record(record) for record in batch_records],
                    config.max_seq_len,
                )
                if encoded is None:
                    continue
                logits = model(encoded[:, :-1])
                target = encoded[:, 1:]
                loss = loss_fn(
                    logits.reshape(-1, config.vocab_size),
                    target.reshape(-1),
                )
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                step_index += 1
                TRAINING_STATE.current_step = step_index
                TRAINING_STATE.loss = float(loss.item())
                TRAINING_STATE.loss_history.append(float(loss.item()))
                _update_metrics()

        WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        model_path = WEIGHTS_DIR / "tiny_router_v1.pt"
        torch.save({"config": config.__dict__, "state_dict": model.state_dict()}, model_path)
        TRAINING_STATE.checkpoint_path = str(model_path)
        TRAINING_STATE.status = "completed"
        TRAINING_STATE.model_path = str(model_path)
        TRAINING_STATE.tokenizer_path = str(tokenizer_path)
        return TRAINING_STATE.to_dict()
    except Exception as exc:
        TRAINING_STATE.status = "failed"
        TRAINING_STATE.error = str(exc)
        return TRAINING_STATE.to_dict()


def start_training_job(
    dataset_path: Path,
    epochs: int = 1,
    batch_size: int = 1,
    model_name: str = "tiny-router",
    tokenizer_name: str = "sentencepiece-bpe",
) -> dict:
    if TRAINING_STATE.status == "running":
        return TRAINING_STATE.to_dict()

    TRAINING_STATE.reset()
    TRAINING_STATE.status = "running"
    TRAINING_STATE.error = None
    TRAINING_STATE.total_epochs = epochs
    TRAINING_STATE.batch_size = batch_size
    TRAINING_STATE.model_name = model_name
    TRAINING_STATE.tokenizer_name = tokenizer_name

    thread = threading.Thread(
        target=run_training,
        kwargs={
            "dataset_path": dataset_path,
            "epochs": epochs,
            "batch_size": batch_size,
            "model_name": model_name,
            "tokenizer_name": tokenizer_name,
        },
        daemon=True,
    )
    thread.start()
    return TRAINING_STATE.to_dict()
