import json
from typing import Any

from protonx.model_contract import normalize_dataset_row
from protonx.model_contract import serialize_compact_prompt


OUTPUT_FORMAT_JSON = "json-v1"
OUTPUT_FORMAT_CALL = "call-v1"
DEFAULT_OUTPUT_FORMAT = OUTPUT_FORMAT_CALL


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


def serialize_call_payload(assistant: dict) -> str:
    payload = _canonical_assistant_payload(assistant)
    tool_calls = payload["tool_calls"]
    if not tool_calls:
        return "CALL:__fallback__"

    call = tool_calls[0]
    tool_name = call["name"] or "__fallback__"
    arguments = call["arguments"]
    if not arguments:
        return f"CALL:{tool_name}"
    rendered_arguments = json.dumps(
        arguments,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"CALL:{tool_name}\nARGS:{rendered_arguments}"


def parse_call_payload(raw_output: str) -> dict[str, Any] | None:
    lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
    if not lines or not lines[0].startswith("CALL:"):
        return None

    tool_name = lines[0][len("CALL:") :].strip()
    if not tool_name:
        return None

    arguments: dict[str, Any] = {}
    for line in lines[1:]:
        if not line.startswith("ARGS:"):
            continue
        raw_arguments = line[len("ARGS:") :].strip()
        if not raw_arguments:
            continue
        try:
            parsed_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed_arguments, dict):
            return None
        arguments = parsed_arguments
        break

    return {"tool_calls": [{"name": tool_name, "arguments": arguments}]}


def render_model_output(raw_output: str, output_format: str) -> str | None:
    if output_format == OUTPUT_FORMAT_CALL:
        payload = parse_call_payload(raw_output)
        if payload is None:
            return None
        return serialize_assistant_payload(payload)
    return raw_output.strip()


def serialize_training_parts(
    record: dict,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> tuple[str, str]:
    normalized = normalize_dataset_row(record)
    if output_format == OUTPUT_FORMAT_CALL:
        assistant = serialize_call_payload(normalized["assistant"])
    else:
        assistant = serialize_assistant_payload(normalized["assistant"])
    prompt = serialize_compact_prompt(normalized["tools"], normalized["user"])
    return prompt, assistant


def serialize_training_record(
    record: dict,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> str:
    prompt, assistant = serialize_training_parts(record, output_format=output_format)
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
