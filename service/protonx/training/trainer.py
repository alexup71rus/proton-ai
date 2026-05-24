import json
import hashlib
import random
import shutil
import threading
from pathlib import Path

import sentencepiece as spm
import torch
from torch import nn

from protonx.config import DATA_DIR, ROOT_DIR
from protonx.contracts import build_fallback_payload
from protonx.model_contract import normalize_dataset_row
from protonx.model_contract import PROMPT_FORMAT_VERSION
from protonx.routing.validate import validate_model_output
from protonx.schemas import JsonSchema, ToolDefinition
from protonx.training.dataset_validation import validate_training_dataset_file
from protonx.training.format import serialize_training_parts
from protonx.training.format import serialize_training_record
from protonx.training.format import decode_generated_continuation
from protonx.training.common import normalize_artifact_name
from protonx.training.model import TinyRouterConfig, TinyRouterModel
from protonx.training.state import TRAINING_STATE
from protonx.training.tokenizer import train_sentencepiece


IGNORE_INDEX = -100
DEFAULT_OUTPUT_ROOT_DIR = "data"
DEFAULT_ARTIFACT_NAME = "tiny_router_v1"


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


def _tool_definition_from_compact_record(tool_payload: dict) -> ToolDefinition:
    compact_args = tool_payload.get("args") or {}
    properties: dict[str, dict] = {}
    required: list[str] = []
    for field_name, spec in compact_args.items():
        required.append(field_name)
        if isinstance(spec, list):
            properties[field_name] = {
                "type": "string",
                "enum": [str(value) for value in spec],
            }
        else:
            properties[field_name] = {"type": "string"}

    return ToolDefinition(
        name=str(tool_payload.get("name") or ""),
        description=str(tool_payload.get("name") or ""),
        tags=[str(tag) for tag in tool_payload.get("tags") or []],
        arguments_schema=JsonSchema(
            type="object",
            properties=properties,
            required=required,
        ),
    )


def _generate_output(
    config: TinyRouterConfig,
    model: TinyRouterModel,
    tokenizer: spm.SentencePieceProcessor,
    prompt_text: str,
) -> str:
    token_ids = tokenizer.encode(prompt_text, out_type=int)[: config.max_seq_len]
    generated = list(token_ids)

    for _ in range(64):
        input_ids = torch.tensor(
            [generated[-config.max_seq_len :]],
            dtype=torch.long,
        )
        with torch.no_grad():
            logits = model(input_ids)
        next_token = int(torch.argmax(logits[0, -1]).item())
        generated.append(next_token)
        if next_token == tokenizer.eos_id():
            break

    candidate = decode_generated_continuation(
        tokenizer,
        generated,
        len(token_ids),
        tokenizer.eos_id(),
    )
    return candidate or json.dumps(build_fallback_payload())


def _evaluate_model(
    records: list[dict],
    config: TinyRouterConfig,
    model: TinyRouterModel,
    tokenizer: spm.SentencePieceProcessor,
) -> dict[str, int]:
    summary = {
        "eval_total": 0,
        "eval_valid": 0,
        "eval_exact": 0,
        "eval_positive_total": 0,
        "eval_positive_exact": 0,
        "eval_fallback_total": 0,
        "eval_fallback_exact": 0,
    }

    for record in records:
        normalized = normalize_dataset_row(record)
        prompt_text, _assistant_text = serialize_training_parts(record)
        raw_output = _generate_output(config, model, tokenizer, prompt_text)
        candidate_tools = [
            _tool_definition_from_compact_record(tool_payload)
            for tool_payload in normalized["tools"]
        ]
        validation = validate_model_output(
            candidate_tools,
            raw_output,
            strict_mode=True,
        )
        expected_name = normalized["assistant"]["tool_calls"][0]["name"]
        predicted_name = None

        summary["eval_total"] += 1
        if validation.valid and validation.parsed_output and validation.parsed_output.get("tool_calls"):
            predicted_name = validation.parsed_output["tool_calls"][0]["name"]
            summary["eval_valid"] += 1

        if predicted_name == expected_name:
            summary["eval_exact"] += 1

        if expected_name == "__fallback__":
            summary["eval_fallback_total"] += 1
            if predicted_name == expected_name:
                summary["eval_fallback_exact"] += 1
        else:
            summary["eval_positive_total"] += 1
            if predicted_name == expected_name:
                summary["eval_positive_exact"] += 1

    return summary


def _prepare_training_runtime(
    records: list[dict],
    corpus_path: Path,
    tokenizer_prefix: Path,
    resolved_resume_model_path: Path | None,
    resolved_resume_tokenizer_path: Path | None,
    hidden_dim: int,
    num_layers: int,
    num_heads: int,
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
        tokenizer_path = train_sentencepiece(corpus_path, tokenizer_prefix, vocab_size=512)
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
) -> dict:
    TRAINING_STATE.update(status="running", error=None)
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

        config, model, tokenizer, tokenizer_path, tokenized_records = _prepare_training_runtime(
            records,
            corpus_path,
            tokenizer_prefix,
            resolved_resume_model_path,
            resolved_resume_tokenizer_path,
            hidden_dim,
            num_layers,
            num_heads,
        )
        pad_id = tokenizer.pad_id()
        eos_id = tokenizer.eos_id()

        model.train()
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

        evaluation = _evaluate_model(records, config, model, tokenizer)
        TRAINING_STATE.apply_evaluation_summary(evaluation)

        model_path.parent.mkdir(parents=True, exist_ok=True)
        if tokenizer_path != tokenizer_prefix.with_suffix(".model"):
            tokenizer_path = _copy_tokenizer_artifacts(
                tokenizer_path,
                tokenizer_prefix,
            )
        torch.save(
            {
                "config": config.__dict__,
                "state_dict": model.state_dict(),
                "prompt_format": PROMPT_FORMAT_VERSION,
                "tokenizer_sha1": _file_sha1(tokenizer_path),
                "dataset_path": str(dataset_path),
                "dataset_sha1": dataset_sha1,
                "dataset_row_count": len(records),
                "output_root_dir": str(resolved_output_root),
                "artifact_name": normalized_artifact_name,
                "evaluation": evaluation,
            },
            model_path,
        )
        TRAINING_STATE.update(
            checkpoint_path=str(model_path),
            status="completed",
            model_path=str(model_path),
            tokenizer_path=str(tokenizer_path),
        )
        return TRAINING_STATE.to_dict()
    except Exception as exc:
        TRAINING_STATE.update(status="failed", error=str(exc))
        return TRAINING_STATE.to_dict()


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
) -> dict:
    if TRAINING_STATE.status == "running":
        return TRAINING_STATE.to_dict()

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

    thread = threading.Thread(
        target=run_training,
        kwargs={
            "dataset_path": dataset_path,
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
        },
        daemon=True,
    )
    thread.start()
    return TRAINING_STATE.to_dict()
