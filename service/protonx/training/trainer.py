import json
import hashlib
import random
import threading
from pathlib import Path

import sentencepiece as spm
import torch
from torch import nn

from protonx.config import TOKENIZER_DIR, WEIGHTS_DIR
from protonx.model_contract import PROMPT_FORMAT_VERSION
from protonx.training.dataset_validation import validate_training_dataset_file
from protonx.training.format import serialize_training_parts
from protonx.training.format import serialize_training_record
from protonx.training.model import TinyRouterConfig, TinyRouterModel
from protonx.training.state import TRAINING_STATE
from protonx.training.tokenizer import train_sentencepiece


IGNORE_INDEX = -100


def _file_sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _load_records(dataset_path: Path) -> list[dict]:
    validation = validate_training_dataset_file(dataset_path)
    if validation["status"] != "valid":
        first_issue = validation["issues"][0]["message"] if validation["issues"] else "Dataset is invalid"
        raise ValueError(f"Dataset validation failed: {first_issue}")
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


def _tokenize_training_record(
    tokenizer: spm.SentencePieceProcessor,
    record: dict,
) -> tuple[list[int], list[int]]:
    prompt_text, assistant_text = serialize_training_parts(record)
    prompt_ids = tokenizer.encode(prompt_text, out_type=int)
    assistant_ids = tokenizer.encode(assistant_text, out_type=int)
    return prompt_ids, assistant_ids


def _record_sequence_length(
    tokenized_record: tuple[list[int], list[int]],
    eos_id: int,
) -> int:
    prompt_ids, assistant_ids = tokenized_record
    return len(prompt_ids) + len(assistant_ids) + (1 if eos_id >= 0 else 0)


def _batch_records(
    tokenized_records: list[tuple[list[int], list[int]]],
    max_seq_len: int,
    pad_id: int,
    eos_id: int,
    ignore_index: int = IGNORE_INDEX,
) -> tuple[torch.Tensor, torch.Tensor] | None:
    input_batches: list[list[int]] = []
    label_batches: list[list[int]] = []
    for prompt_ids, assistant_ids in tokenized_records:
        full_ids = [*prompt_ids, *assistant_ids]
        if eos_id >= 0:
            full_ids.append(eos_id)
        if len(full_ids) > max_seq_len:
            raise ValueError(
                f"Serialized training record exceeds max_seq_len={max_seq_len}."
            )
        if len(full_ids) < 2:
            continue

        input_ids = full_ids[:-1]
        labels = full_ids[1:]
        prompt_target_length = max(len(prompt_ids) - 1, 0)
        labels = [ignore_index] * prompt_target_length + labels[prompt_target_length:]

        input_batches.append(input_ids)
        label_batches.append(labels)

    if not input_batches:
        return None

    max_len = max(len(seq) for seq in input_batches)
    padded_inputs = [seq + [pad_id] * (max_len - len(seq)) for seq in input_batches]
    padded_labels = [
        seq + [ignore_index] * (max_len - len(seq)) for seq in label_batches
    ]
    return (
        torch.tensor(padded_inputs, dtype=torch.long),
        torch.tensor(padded_labels, dtype=torch.long),
    )


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
        pad_id = tokenizer.pad_id()
        eos_id = tokenizer.eos_id()
        tokenized_records = [
            _tokenize_training_record(tokenizer, record) for record in records
        ]
        max_record_len = max(
            (_record_sequence_length(record, eos_id) for record in tokenized_records),
            default=2,
        )
        config = TinyRouterConfig(
            vocab_size=tokenizer.get_piece_size(),
            hidden_dim=64,
            num_layers=2,
            num_heads=4,
            max_seq_len=max(256, max_record_len),
        )
        model = TinyRouterModel(config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        loss_fn = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)

        step_index = 0
        for epoch in range(1, epochs + 1):
            TRAINING_STATE.current_epoch = epoch
            epoch_records = list(tokenized_records)
            random.shuffle(epoch_records)
            for batch_start in range(0, len(epoch_records), batch_size):
                batch_records = epoch_records[batch_start : batch_start + batch_size]
                batch_tensors = _batch_records(
                    batch_records,
                    config.max_seq_len,
                    pad_id,
                    eos_id,
                )
                if batch_tensors is None:
                    continue
                input_ids, target = batch_tensors
                logits = model(input_ids)
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
        torch.save(
            {
                "config": config.__dict__,
                "state_dict": model.state_dict(),
                "prompt_format": PROMPT_FORMAT_VERSION,
                "tokenizer_sha1": _file_sha1(tokenizer_path),
            },
            model_path,
        )
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

    validation = validate_training_dataset_file(dataset_path)
    if validation["status"] != "valid":
        first_issue = validation["issues"][0]["message"] if validation["issues"] else "Dataset is invalid"
        raise ValueError(f"Dataset validation failed: {first_issue}")

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
