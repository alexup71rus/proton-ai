import json
from typing import Any

from protonx.model_contract import normalize_dataset_row
from protonx.model_contract import serialize_compact_prompt


def _canonical_tool_call(call: dict) -> dict:
    return {
        "name": str(call.get("name") or ""),
        "arguments": dict(call.get("arguments") or {}),
    }


def _canonical_assistant_payload(assistant: dict) -> dict:
    return {
        "tool_calls": [
            _canonical_tool_call(call)
            for call in assistant.get("tool_calls", [])
            if isinstance(call, dict)
        ]
    }


def serialize_assistant_payload(assistant: dict) -> str:
    return json.dumps(
        _canonical_assistant_payload(assistant),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def serialize_training_parts(record: dict) -> tuple[str, str]:
    normalized = normalize_dataset_row(record)
    assistant = serialize_assistant_payload(normalized["assistant"])
    prompt = serialize_compact_prompt(normalized["tools"], normalized["user"])
    return prompt, assistant


def serialize_training_record(record: dict) -> str:
    prompt, assistant = serialize_training_parts(record)
    return prompt + assistant


def serialize_inference_prompt(prompt: dict) -> str:
    return serialize_compact_prompt(prompt["tools"], prompt["user"])


def decode_generated_continuation(
    tokenizer: Any,
    generated: list[int],
    prompt_token_count: int,
    eos_id: int,
) -> str:
    continuation = generated[prompt_token_count:]
    if continuation and continuation[-1] == eos_id:
        continuation = continuation[:-1]
    return tokenizer.decode(continuation).strip()
