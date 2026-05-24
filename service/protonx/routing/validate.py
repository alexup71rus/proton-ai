import json
from dataclasses import dataclass
from typing import Any

from protonx.schemas import ToolDefinition


@dataclass
class ValidationResult:
    valid: bool
    parsed_output: dict[str, Any] | None
    error: str | None
    final_action: str


def _schema_ok(arguments: dict[str, Any], tool: ToolDefinition, strict_mode: bool) -> bool:
    schema = tool.arguments_schema
    properties = schema.properties
    required = set(schema.required)
    provided = set(arguments.keys())

    if not required.issubset(provided):
        return False
    if strict_mode and not provided.issubset(set(properties.keys())):
        return False

    for key, value in arguments.items():
        if key not in properties:
            return False
        property_schema = properties[key]
        expected_type = property_schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            return False
        enum_values = property_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            return False
    return True


def validate_model_output(
    candidate_tools: list[ToolDefinition],
    raw_output: str,
    answer_allowed: bool,
    strict_mode: bool = True,
) -> ValidationResult:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return ValidationResult(False, None, "invalid json", "fallback")

    if "tool_calls" not in payload or "answer" not in payload:
        return ValidationResult(
            False, payload, "missing required top-level fields", "fallback"
        )
    if not isinstance(payload["tool_calls"], list) or not isinstance(payload["answer"], bool):
        return ValidationResult(
            False, payload, "invalid top-level field types", "fallback"
        )

    if payload.get("fallback") is True:
        if payload["tool_calls"] != []:
            return ValidationResult(
                False, payload, "fallback cannot include tool calls", "fallback"
            )
        return ValidationResult(True, payload, None, "fallback")

    if payload["answer"] is True:
        return ValidationResult(
            False, payload, "answer-only responses must use fallback", "fallback"
        )
    if payload["tool_calls"] == []:
        return ValidationResult(
            False, payload, "empty tool_calls must use fallback", "fallback"
        )

    allowed_names = {tool.name: tool for tool in candidate_tools}
    for call in payload["tool_calls"]:
        if not isinstance(call, dict) or "name" not in call:
            return ValidationResult(False, payload, "invalid tool call shape", "fallback")
        name = call["name"]
        if name not in allowed_names:
            return ValidationResult(
                False, payload, "unknown tool outside candidate set", "fallback"
            )
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            return ValidationResult(False, payload, "schema validation failed", "fallback")
        if not _schema_ok(arguments, allowed_names[name], strict_mode):
            return ValidationResult(False, payload, "schema validation failed", "fallback")

    return ValidationResult(True, payload, None, "tool_call")
