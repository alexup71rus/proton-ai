from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protonx.enum_values import enum_is_supported
from protonx.enum_values import enum_output_values


def _tool_argument_specs(tool: dict[str, Any]) -> dict[str, Any]:
    compact_args = tool.get("args")
    if isinstance(compact_args, dict):
        return compact_args

    schema = tool.get("arguments_schema", {})
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict):
        return {}
    if not isinstance(required, list):
        required = []

    field_names = required or list(properties.keys())
    argument_specs: dict[str, Any] = {}
    for field_name in field_names:
        property_schema = properties.get(field_name, {})
        if not isinstance(property_schema, dict):
            continue
        enum_values = property_schema.get("enum")
        if enum_output_values(enum_values):
            argument_specs[field_name] = {
                "type": property_schema.get("type") or "string",
                "enum": enum_values,
            }
            continue
        argument_specs[field_name] = str(property_schema.get("type") or "string")
    return argument_specs


def _schema_ok(arguments: dict[str, Any], tool: dict[str, Any]) -> bool:
    argument_specs = _tool_argument_specs(tool)
    provided = set(arguments.keys())
    required = set(argument_specs.keys())

    if not required.issubset(provided):
        return False
    if not provided.issubset(required):
        return False

    for key, value in arguments.items():
        spec = argument_specs.get(key)
        if isinstance(spec, dict):
            enum_values = spec.get("enum")
            if enum_values is not None:
                if value not in enum_output_values(enum_values):
                    return False
                continue
            spec = spec.get("type") or "string"
        if isinstance(spec, list):
            if value not in enum_output_values(spec):
                return False
            continue
        if spec == "string" and not isinstance(value, str):
            return False
    return True


def _validate_compact_args(tool: dict[str, Any], line_number: int, add_issue) -> None:
    args = tool.get("args")
    if not isinstance(args, dict):
        add_issue(line_number, f"Tool {tool.get('name', '')} args must be an object.")
        return

    for field_name, spec in args.items():
        if isinstance(spec, str):
            continue
        if isinstance(spec, list) and all(isinstance(value, str) for value in spec):
            continue
        if isinstance(spec, dict):
            spec_type = spec.get("type")
            enum_values = spec.get("enum")
            description = spec.get("description")
            has_valid_type = spec_type is None or isinstance(spec_type, str)
            has_valid_enum = enum_is_supported(enum_values)
            has_valid_description = description is None or isinstance(description, str)
            if (
                has_valid_type
                and has_valid_enum
                and has_valid_description
            ):
                continue
        add_issue(
            line_number,
            f"Tool {tool.get('name', '')}.{field_name} arg spec must be a string, string list, or compact object.",
        )


def _validate_legacy_schema(tool: dict[str, Any], line_number: int, add_issue) -> None:
    name = tool.get("name")
    arguments_schema = tool.get("arguments_schema")
    if not isinstance(arguments_schema, dict):
        add_issue(line_number, f"Tool {name} must define arguments_schema.")
        return
    if arguments_schema.get("type") != "object":
        add_issue(line_number, f"Tool {name} arguments_schema.type must be object.")
        return
    properties = arguments_schema.get("properties", {})
    required = arguments_schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        add_issue(line_number, f"Tool {name} arguments_schema must define properties and required.")
        return
    for field_name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            add_issue(line_number, f"Tool {name}.{field_name} schema must be an object.")
            continue
        if property_schema.get("type") != "string":
            add_issue(line_number, f"Tool {name}.{field_name} schema type must be string.")
            continue
        enum_values = property_schema.get("enum")
        if enum_values is not None and not enum_is_supported(enum_values):
            add_issue(line_number, f"Tool {name}.{field_name} enum must be a string list or value-description object.")


def _parse_compact_row(
    row: dict[str, Any], line_number: int, add_issue
) -> tuple[list[dict[str, Any]], str, dict[str, Any]] | None:
    tools = row.get("tools")
    user = row.get("user")
    assistant = row.get("assistant")

    if not isinstance(tools, list):
        add_issue(line_number, "Compact row must include a tools list.")
        return None
    if not isinstance(user, str) or not user.strip():
        add_issue(line_number, "Compact row must include a non-empty user string.")
        return None
    if isinstance(assistant, str):
        try:
            assistant = json.loads(assistant)
        except json.JSONDecodeError:
            add_issue(line_number, "assistant must be a JSON object or valid JSON string.")
            return None
    if not isinstance(assistant, dict):
        add_issue(line_number, "Compact row must include an assistant object.")
        return None
    return tools, user, assistant


def _parse_legacy_row(
    row: dict[str, Any], line_number: int, add_issue
) -> tuple[list[dict[str, Any]], str, dict[str, Any]] | None:
    tools = row.get("tools")
    messages = row.get("messages")

    if not isinstance(tools, list):
        add_issue(line_number, "Legacy row must include a tools list.")
        return None
    if not isinstance(messages, list) or len(messages) < 2:
        add_issue(line_number, "messages must contain at least user and assistant entries.")
        return None

    user_message = messages[0]
    assistant_message = messages[1]
    if not isinstance(user_message, dict) or user_message.get("role") != "user":
        add_issue(line_number, "messages[0] must be the user message.")
        return None
    if not isinstance(assistant_message, dict) or assistant_message.get("role") != "assistant":
        add_issue(line_number, "messages[1] must be the assistant message.")
        return None
    if not isinstance(user_message.get("content"), str) or not user_message.get("content", "").strip():
        add_issue(line_number, "User message content must be a non-empty string.")
        return None

    assistant_content = assistant_message.get("content")
    if isinstance(assistant_content, str):
        try:
            assistant_content = json.loads(assistant_content)
        except json.JSONDecodeError:
            add_issue(line_number, "Assistant content must be valid JSON.")
            return None
    if not isinstance(assistant_content, dict):
        add_issue(line_number, "Assistant content must decode to a JSON object.")
        return None

    return tools, user_message["content"], assistant_content


def validate_training_dataset_content(content: str, max_issues: int = 25) -> dict[str, Any]:
    issue_count = 0
    issues: list[dict[str, Any]] = []
    row_count = 0

    def add_issue(line_number: int, message: str) -> None:
        nonlocal issue_count
        issue_count += 1
        if len(issues) < max_issues:
            issues.append({"line_number": line_number, "message": message})

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            continue
        row_count += 1

        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            add_issue(line_number, "Line is not valid JSON.")
            continue

        if not isinstance(row, dict):
            add_issue(line_number, "Dataset row must be a JSON object.")
            continue

        normalized_row: tuple[list[dict[str, Any]], str, dict[str, Any]] | None
        if isinstance(row.get("user"), str) and "assistant" in row:
            normalized_row = _parse_compact_row(row, line_number, add_issue)
        elif "messages" in row:
            normalized_row = _parse_legacy_row(row, line_number, add_issue)
        else:
            add_issue(
                line_number,
                "Row must use compact fields (tools, user, assistant) or legacy messages format.",
            )
            continue

        if normalized_row is None:
            continue

        tools, _user, assistant = normalized_row

        tool_map: dict[str, dict[str, Any]] = {}
        for tool in tools:
            if not isinstance(tool, dict):
                add_issue(line_number, "Each tool must be a JSON object.")
                continue
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                add_issue(line_number, "Each tool must define a non-empty name.")
                continue
            tags = tool.get("tags")
            if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                add_issue(line_number, f"Tool {name} tags must be a list of strings.")
                continue
            if "args" in tool:
                _validate_compact_args(tool, line_number, add_issue)
            elif "arguments_schema" in tool:
                _validate_legacy_schema(tool, line_number, add_issue)
            tool_map[name] = tool

        if not isinstance(assistant.get("tool_calls"), list):
            add_issue(line_number, "Assistant payload must include tool_calls list.")
            continue
        if set(assistant.keys()) != {"tool_calls"}:
            add_issue(line_number, "Assistant payload may only contain tool_calls.")
            continue
        if assistant["tool_calls"] == []:
            add_issue(line_number, "Assistant payload must select a tool or the fallback tool.")
            continue

        saw_fallback = False
        for call in assistant["tool_calls"]:
            if not isinstance(call, dict) or "name" not in call:
                add_issue(line_number, "Each tool call must be an object with name.")
                continue
            if set(call.keys()) - {"name", "arguments"}:
                add_issue(line_number, "Tool call may only contain name and arguments.")
                continue
            tool_name = call["name"]
            if tool_name not in tool_map:
                add_issue(line_number, f"Tool call {tool_name} is not present in row.tools.")
                continue
            arguments = call.get("arguments", {})
            if not isinstance(arguments, dict):
                add_issue(line_number, f"Tool call {tool_name} arguments must be an object.")
                continue
            if not _schema_ok(arguments, tool_map[tool_name]):
                add_issue(line_number, f"Tool call {tool_name} arguments do not match schema.")
            if tool_name == "__fallback__":
                saw_fallback = True

        if saw_fallback and len(assistant["tool_calls"]) != 1:
            add_issue(line_number, "Fallback tool cannot be combined with other tool calls.")

    if row_count == 0:
        add_issue(0, "Dataset must contain at least one JSONL row.")

    return {
        "status": "valid" if issue_count == 0 else "invalid",
        "row_count": row_count,
        "issue_count": issue_count,
        "issues": issues,
    }


def validate_training_dataset_file(dataset_path: Path, max_issues: int = 25) -> dict[str, Any]:
    return validate_training_dataset_content(
        dataset_path.read_text(encoding="utf-8"),
        max_issues=max_issues,
    )
