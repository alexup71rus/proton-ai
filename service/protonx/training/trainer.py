import json
import hashlib
import math
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import sentencepiece as spm
import torch
from torch import nn

from protonx.config import DATA_DIR, LOG_DIR, ROOT_DIR
from protonx.model_contract import PROMPT_FORMAT_VERSION
from protonx.training.dataset_validation import validate_training_dataset_file
from protonx.training.evaluation import evaluate_holdout
from protonx.training.format import DEFAULT_OUTPUT_FORMAT
from protonx.training.format import serialize_training_parts
from protonx.training.format import serialize_training_record
from protonx.training.common import normalize_artifact_name
from protonx.training.model import TinyRouterConfig, TinyRouterModel
from protonx.training.state import TRAINING_STATE
from protonx.training.state import read_training_state
from protonx.training.state import training_state_path
from protonx.training.state import write_training_state
from protonx.training.tokenizer import train_sentencepiece


IGNORE_INDEX = -100
DEFAULT_OUTPUT_ROOT_DIR = "data"
DEFAULT_ARTIFACT_NAME = "tiny_router_v1"
DEFAULT_VOCAB_SIZE = 512
MAX_GRAD_NORM = 1.0
STATE_WRITE_INTERVAL_SECONDS = 2.0
_LAST_STATE_WRITE_MONOTONIC = 0.0


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
        "\n".join(
            serialize_training_record(record, output_format=DEFAULT_OUTPUT_FORMAT)
            for record in records
        ),
        encoding="utf-8",
    )


def _tool_name_symbols(records: list[dict]) -> list[str]:
    names = {
        str(tool.get("name") or "").strip()
        for record in records
        for tool in record.get("tools", [])
        if str(tool.get("name") or "").strip()
    }
    names.update(
        str(call.get("name") or "").strip()
        for record in records
        for call in record.get("assistant", {}).get("tool_calls", [])
        if isinstance(call, dict) and str(call.get("name") or "").strip()
    )
    return sorted(names)


def _resolve_repo_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _build_output_paths(
    output_root_dir: str | None,
    artifact_name: str,
) -> tuple[Path, str, Path, Path, Path]:
    normalized_artifact_name = normalize_artifact_name(artifact_name)
    resolved_output_root = _resolve_repo_path(output_root_dir) or DATA_DIR
    tokenizers_dir = resolved_output_root / "tokenizers"
    weights_dir = resolved_output_root / "weights"
    corpus_path = tokenizers_dir / f"{normalized_artifact_name}.corpus.txt"
    tokenizer_prefix = tokenizers_dir / normalized_artifact_name
    model_path = weights_dir / f"{normalized_artifact_name}.pt"
    return resolved_output_root, normalized_artifact_name, corpus_path, tokenizer_prefix, model_path


def _load_checkpoint(
    model_path: Path,
    tokenizer_path: Path,
) -> tuple[TinyRouterConfig, TinyRouterModel, spm.SentencePieceProcessor]:
    checkpoint = torch.load(model_path, map_location="cpu")
    if checkpoint.get("prompt_format") != PROMPT_FORMAT_VERSION:
        raise ValueError("Checkpoint prompt format is incompatible with the current runtime")
    expected_tokenizer_sha1 = checkpoint.get("tokenizer_sha1")
    if expected_tokenizer_sha1 and expected_tokenizer_sha1 != _file_sha1(tokenizer_path):
        raise ValueError("Checkpoint tokenizer does not match the selected tokenizer file")

    config = TinyRouterConfig(**checkpoint["config"])
    model = TinyRouterModel(config)
    model.load_state_dict(checkpoint["state_dict"])
    tokenizer = spm.SentencePieceProcessor(model_file=str(tokenizer_path))
    return config, model, tokenizer


def _copy_tokenizer_artifacts(source_model_path: Path, target_prefix: Path) -> Path:
    target_prefix.parent.mkdir(parents=True, exist_ok=True)
    target_model_path = target_prefix.with_suffix(".model")
    shutil.copy2(source_model_path, target_model_path)
    source_vocab_path = source_model_path.with_suffix(".vocab")
    target_vocab_path = target_prefix.with_suffix(".vocab")
    if source_vocab_path.exists():
        shutil.copy2(source_vocab_path, target_vocab_path)
    return target_model_path


def _validate_new_model_config(
    hidden_dim: int,
    num_layers: int,
    num_heads: int,
) -> None:
    if hidden_dim <= 0 or num_layers <= 0 or num_heads <= 0:
        raise ValueError("hidden_dim, num_layers, and num_heads must be positive integers")
    if hidden_dim % num_heads != 0:
        raise ValueError("hidden_dim must be divisible by num_heads")


def _select_training_device() -> torch.device:
    requested_device = os.getenv("PROTONX_TRAIN_DEVICE", "cpu").strip().lower()
    if requested_device in {"cpu", "mps"}:
        if requested_device == "mps" and not torch.backends.mps.is_available():
            return torch.device("cpu")
        return torch.device(requested_device)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _cpu_state_dict(model: TinyRouterModel) -> dict[str, torch.Tensor]:
    return {
        key: value.detach().cpu()
        for key, value in model.state_dict().items()
    }


def _assert_finite_model_parameters(model: TinyRouterModel) -> None:
    for name, value in model.state_dict().items():
        if value.is_floating_point() and not torch.isfinite(value).all():
            raise ValueError(f"Model parameter {name} became non-finite; checkpoint was not saved")


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
    _persist_training_state()


def _persist_training_state(force: bool = False) -> None:
    global _LAST_STATE_WRITE_MONOTONIC
    now = time.monotonic()
    if force or now - _LAST_STATE_WRITE_MONOTONIC >= STATE_WRITE_INTERVAL_SECONDS:
        write_training_state()
        _LAST_STATE_WRITE_MONOTONIC = now


def _process_is_running(process_id: int | None) -> bool:
    if not process_id:
        return False
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def get_training_status() -> dict:
    state = read_training_state()
    if state.get("status") == "running" and not _process_is_running(state.get("process_id")):
        state["status"] = "failed"
        state["error"] = state.get("error") or "Training process is not running"
        TRAINING_STATE.update(**state)
        write_training_state()
    return state


def _finite_loss_value(loss: torch.Tensor) -> float:
    loss_value = float(loss.detach().cpu().item())
    if not math.isfinite(loss_value):
        raise ValueError("Training loss became non-finite; lower learning_rate or reduce batch/model size")
    return loss_value


def _prepare_training_runtime(
    records: list[dict],
    corpus_path: Path,
    tokenizer_prefix: Path,
    resolved_resume_model_path: Path | None,
    resolved_resume_tokenizer_path: Path | None,
    hidden_dim: int,
    num_layers: int,
    num_heads: int,
    vocab_size: int,
) -> tuple[
    TinyRouterConfig,
    TinyRouterModel,
    spm.SentencePieceProcessor,
    Path,
    list[tuple[list[int], list[int]]],
]:
    if resolved_resume_model_path and resolved_resume_tokenizer_path:
        config, model, tokenizer = _load_checkpoint(
            resolved_resume_model_path,
            resolved_resume_tokenizer_path,
        )
        tokenizer_path = resolved_resume_tokenizer_path
    else:
        _write_tokenizer_corpus(records, corpus_path)
        tokenizer_path = train_sentencepiece(
            corpus_path,
            tokenizer_prefix,
            vocab_size=vocab_size,
            user_defined_symbols=_tool_name_symbols(records),
        )
        tokenizer = spm.SentencePieceProcessor(model_file=str(tokenizer_path))
        config = None
        model = None

    tokenized_records = [
        _tokenize_training_record(tokenizer, record) for record in records
    ]
    max_record_len = max(
        (_record_sequence_length(record, tokenizer.eos_id()) for record in tokenized_records),
        default=2,
    )

    if resolved_resume_model_path and resolved_resume_tokenizer_path:
        if max_record_len > config.max_seq_len:
            raise ValueError(
                f"Serialized training record exceeds loaded checkpoint max_seq_len={config.max_seq_len}."
            )
        return config, model, tokenizer, tokenizer_path, tokenized_records

    config = TinyRouterConfig(
        vocab_size=tokenizer.get_piece_size(),
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        max_seq_len=max(256, max_record_len),
    )
    model = TinyRouterModel(config)
    return config, model, tokenizer, tokenizer_path, tokenized_records


def run_training(
    dataset_path: Path,
    epochs: int = 1,
    batch_size: int = 1,
    model_name: str = "tiny-router",
    tokenizer_name: str = "sentencepiece-bpe",
    output_root_dir: str = DEFAULT_OUTPUT_ROOT_DIR,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    resume_model_path: str | None = None,
    resume_tokenizer_path: str | None = None,
    hidden_dim: int = 64,
    num_layers: int = 2,
    num_heads: int = 4,
    learning_rate: float = 1e-3,
    vocab_size: int = DEFAULT_VOCAB_SIZE,
) -> dict:
    random.seed(0)
    torch.manual_seed(0)
    TRAINING_STATE.update(status="running", error=None)
    _persist_training_state(force=True)
    try:
        records = _load_records(dataset_path)
        dataset_sha1 = _file_sha1(dataset_path)
        resolved_output_root, normalized_artifact_name, corpus_path, tokenizer_prefix, model_path = _build_output_paths(
            output_root_dir,
            artifact_name,
        )
        resolved_resume_model_path = _resolve_repo_path(resume_model_path)
        resolved_resume_tokenizer_path = _resolve_repo_path(resume_tokenizer_path)
        if bool(resolved_resume_model_path) != bool(resolved_resume_tokenizer_path):
            raise ValueError("resume_model_path and resume_tokenizer_path must be provided together")
        if not resolved_resume_model_path:
            _validate_new_model_config(hidden_dim, num_layers, num_heads)
        TRAINING_STATE.begin_run(
            total_epochs=epochs,
            total_steps=max(1, ((len(records) + batch_size - 1) // batch_size) * epochs),
            batch_size=batch_size,
            model_name=model_name,
            tokenizer_name=tokenizer_name,
            output_root_dir=str(resolved_output_root),
            artifact_name=normalized_artifact_name,
            dataset_path=str(dataset_path),
            dataset_sha1=dataset_sha1,
            dataset_row_count=len(records),
        )
        TRAINING_STATE.update(process_id=os.getpid())
        _persist_training_state(force=True)

        config, model, tokenizer, tokenizer_path, tokenized_records = _prepare_training_runtime(
            records,
            corpus_path,
            tokenizer_prefix,
            resolved_resume_model_path,
            resolved_resume_tokenizer_path,
            hidden_dim,
            num_layers,
            num_heads,
            vocab_size,
        )
        pad_id = tokenizer.pad_id()
        eos_id = tokenizer.eos_id()
        device = _select_training_device()

        model.to(device)
        model.train()
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
        loss_fn = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)

        step_index = 0
        best_epoch = 0
        best_epoch_loss = float("inf")
        for epoch in range(1, epochs + 1):
            TRAINING_STATE.current_epoch = epoch
            _persist_training_state(force=True)
            epoch_records = list(tokenized_records)
            random.shuffle(epoch_records)
            epoch_losses: list[float] = []
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
                input_ids, target = (
                    tensor.to(device, non_blocking=True)
                    for tensor in batch_tensors
                )
                logits = model(input_ids)
                loss = loss_fn(
                    logits.reshape(-1, config.vocab_size),
                    target.reshape(-1),
                )
                loss_value = _finite_loss_value(loss)
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    model.parameters(),
                    max_norm=MAX_GRAD_NORM,
                    error_if_nonfinite=True,
                )
                optimizer.step()
                step_index += 1
                epoch_losses.append(loss_value)
                TRAINING_STATE.current_step = step_index
                TRAINING_STATE.loss = loss_value
                TRAINING_STATE.loss_history.append(loss_value)
                _update_metrics()

            if epoch_losses:
                epoch_loss = sum(epoch_losses) / len(epoch_losses)
                if epoch_loss < best_epoch_loss:
                    best_epoch = epoch
                    best_epoch_loss = epoch_loss

        model_path.parent.mkdir(parents=True, exist_ok=True)
        _assert_finite_model_parameters(model)
        if tokenizer_path != tokenizer_prefix.with_suffix(".model"):
            tokenizer_path = _copy_tokenizer_artifacts(
                tokenizer_path,
                tokenizer_prefix,
            )
        checkpoint_payload = {
            "config": config.__dict__,
            "state_dict": _cpu_state_dict(model),
            "prompt_format": PROMPT_FORMAT_VERSION,
            "output_format": DEFAULT_OUTPUT_FORMAT,
            "training_device": str(device),
            "tokenizer_sha1": _file_sha1(tokenizer_path),
            "dataset_path": str(dataset_path),
            "dataset_sha1": dataset_sha1,
            "dataset_row_count": len(records),
            "output_root_dir": str(resolved_output_root),
            "artifact_name": normalized_artifact_name,
            "best_epoch": best_epoch,
            "best_epoch_loss": best_epoch_loss,
            "evaluation": {},
        }
        torch.save(checkpoint_payload, model_path)
        try:
            evaluation_summary = evaluate_holdout(
                records,
                model_path,
                tokenizer_path,
            )
        except Exception as exc:
            evaluation_summary = {
                "mode": "unique_holdout",
                "error": str(exc),
                "eval_total": 0,
                "eval_valid": 0,
                "eval_exact": 0,
                "eval_positive_total": 0,
                "eval_positive_exact": 0,
                "eval_fallback_total": 0,
                "eval_fallback_exact": 0,
            }
        checkpoint_payload["evaluation"] = evaluation_summary
        torch.save(checkpoint_payload, model_path)
        TRAINING_STATE.apply_evaluation_summary(evaluation_summary)
        TRAINING_STATE.update(
            checkpoint_path=str(model_path),
            model_path=str(model_path),
            tokenizer_path=str(tokenizer_path),
            status="completed",
        )
        _persist_training_state(force=True)
        return TRAINING_STATE.to_dict()
    except Exception as exc:
        TRAINING_STATE.update(status="failed", error=str(exc))
        _persist_training_state(force=True)
        return TRAINING_STATE.to_dict()


def _write_training_job_config(config: dict) -> Path:
    path = training_state_path().with_name("training_job.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _training_job_log_path() -> Path:
    path = LOG_DIR / "training_job.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def start_training_job(
    dataset_path: Path,
    epochs: int = 1,
    batch_size: int = 1,
    model_name: str = "tiny-router",
    tokenizer_name: str = "sentencepiece-bpe",
    output_root_dir: str = DEFAULT_OUTPUT_ROOT_DIR,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    resume_model_path: str | None = None,
    resume_tokenizer_path: str | None = None,
    hidden_dim: int = 64,
    num_layers: int = 2,
    num_heads: int = 4,
    learning_rate: float = 1e-3,
    training_device: str | None = None,
    vocab_size: int = DEFAULT_VOCAB_SIZE,
) -> dict:
    persisted_state = get_training_status()
    if persisted_state.get("status") == "running":
        return persisted_state

    resolved_output_root, normalized_artifact_name, _corpus_path, _tokenizer_prefix, _model_path = _build_output_paths(
        output_root_dir,
        artifact_name,
    )
    if not resume_model_path:
        _validate_new_model_config(hidden_dim, num_layers, num_heads)
    validation = validate_training_dataset_file(dataset_path)
    if validation["status"] != "valid":
        first_issue = validation["issues"][0]["message"] if validation["issues"] else "Dataset is invalid"
        raise ValueError(f"Dataset validation failed: {first_issue}")

    TRAINING_STATE.begin_run(
        total_epochs=epochs,
        total_steps=0,
        batch_size=batch_size,
        model_name=model_name,
        tokenizer_name=tokenizer_name,
        output_root_dir=str(resolved_output_root),
        artifact_name=normalized_artifact_name,
        dataset_path=str(dataset_path),
        dataset_sha1=_file_sha1(dataset_path),
        dataset_row_count=validation["row_count"],
    )
    _persist_training_state(force=True)

    job_config_path = _write_training_job_config(
        {
            "dataset_path": str(dataset_path),
            "epochs": epochs,
            "batch_size": batch_size,
            "model_name": model_name,
            "tokenizer_name": tokenizer_name,
            "output_root_dir": output_root_dir,
            "artifact_name": artifact_name,
            "resume_model_path": resume_model_path,
            "resume_tokenizer_path": resume_tokenizer_path,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "num_heads": num_heads,
            "learning_rate": learning_rate,
            "training_device": training_device,
            "vocab_size": vocab_size,
        }
    )
    env = os.environ.copy()
    if training_device:
        env["PROTONX_TRAIN_DEVICE"] = training_device
    log_file = _training_job_log_path().open("ab")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "protonx.training.job_worker",
            str(job_config_path),
        ],
        cwd=str(ROOT_DIR / "service"),
        env=env,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )
    log_file.close()
    TRAINING_STATE.update(process_id=process.pid)
    _persist_training_state(force=True)
    return TRAINING_STATE.to_dict()
