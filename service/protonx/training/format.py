import json

from protonx.model_contract import normalize_dataset_row
from protonx.model_contract import serialize_compact_prompt


def serialize_training_parts(record: dict) -> tuple[str, str]:
    normalized = normalize_dataset_row(record)
    assistant = json.dumps(normalized["assistant"], ensure_ascii=False, sort_keys=True)
    prompt = serialize_compact_prompt(normalized["tools"], normalized["user"])
    return prompt, assistant


def serialize_training_record(record: dict) -> str:
    prompt, assistant = serialize_training_parts(record)
    return prompt + assistant


def serialize_inference_prompt(prompt: dict) -> str:
    return serialize_compact_prompt(prompt["tools"], prompt["user"])
