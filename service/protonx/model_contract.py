"""Compact model-facing contract for the tiny tool router.

The model only sees candidate tools, the user text, and the structured output.
Runtime policy such as fallback copy, OpenAI-compatible wrapping, and validator
decisions stays in code outside the training signal.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from protonx.schemas import JsonSchema, ToolDefinition


PROMPT_FORMAT_VERSION = "compact-v2"
FALLBACK_TOOL_NAME = "__fallback__"
FALLBACK_TOOL_TAGS = [
    "fallback",
    "no tool",
    "unsupported",
    "unknown",
    "ambiguous",
    "chat",
]
FALLBACK_MESSAGE = "I work only with available tools."


def build_fallback_tool() -> ToolDefinition:
    return ToolDefinition(
        name=FALLBACK_TOOL_NAME,
        description="Select when no available tool should be called.",
        tags=list(FALLBACK_TOOL_TAGS),
        arguments_schema=JsonSchema(type="object", properties={}, required=[]),
    )


def build_fallback_tool_call() -> dict[str, Any]:
    return {"name": FALLBACK_TOOL_NAME, "arguments": {}}


def build_fallback_payload() -> dict[str, Any]:
    return {"tool_calls": [build_fallback_tool_call()]}


def build_fallback_response(answer_allowed: bool) -> str | None:
    if not answer_allowed:
        return None
    return FALLBACK_MESSAGE


def is_fallback_tool_name(name: str) -> bool:
    return name == FALLBACK_TOOL_NAME


def with_fallback_tool(tools: list[ToolDefinition]) -> list[ToolDefinition]:
    if any(is_fallback_tool_name(tool.name) for tool in tools):
        return list(tools)
    return [*tools, build_fallback_tool()]


def with_compact_fallback_tool(
    tools: list[dict[str, Any]],
    variation_key: str = "",
) -> list[dict[str, Any]]:
    if any(is_fallback_tool_name(str(tool.get("name") or "")) for tool in tools):
        return list(tools)
    return [
        *tools,
        compact_tool_from_definition(
            build_fallback_tool(),
            variation_key=f"{variation_key}|fallback",
        ),
    ]


def _schema_parts(schema: JsonSchema | dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if isinstance(schema, JsonSchema):
        return schema.properties, schema.required
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict):
        properties = {}
    if not isinstance(required, list):
        required = []
    return properties, required


def compact_args_from_schema(schema: JsonSchema | dict[str, Any]) -> dict[str, Any]:
    properties, required = _schema_parts(schema)
    if not properties:
        return {}

    selected_names = required or list(properties.keys())
    compact_args: dict[str, Any] = {}
    for field_name in selected_names:
        property_schema = properties.get(field_name, {})
        if not isinstance(property_schema, dict):
            continue
        enum_values = property_schema.get("enum")
        if isinstance(enum_values, list) and enum_values:
            compact_args[field_name] = [str(value) for value in enum_values]
            continue
        compact_args[field_name] = str(property_schema.get("type") or "string")
    return compact_args


def _dedupe_tags(tags: list[str]) -> list[str]:
    unique_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        normalized = tag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_tags.append(tag)
    return unique_tags


def _shuffle_tags(tags: list[str], variation_key: str) -> list[str]:
    unique_tags = _dedupe_tags(tags)
    if len(unique_tags) <= 1 or not variation_key:
        return unique_tags

    return sorted(
        unique_tags,
        key=lambda tag: hashlib.sha1(
            f"{variation_key}|{tag}".encode("utf-8")
        ).hexdigest(),
    )


def compact_tool_from_definition(
    tool: ToolDefinition,
    variation_key: str = "",
) -> dict[str, Any]:
    compact_tool: dict[str, Any] = {
        "name": tool.name,
        "tags": _shuffle_tags(list(tool.tags), f"{variation_key}|{tool.name}"),
    }
    compact_args = compact_args_from_schema(tool.arguments_schema)
    if compact_args:
        compact_tool["args"] = compact_args
    return compact_tool


def compact_tool_from_record(
    tool: dict[str, Any],
    variation_key: str = "",
) -> dict[str, Any]:
    compact_tool: dict[str, Any] = {
        "name": str(tool.get("name") or ""),
        "tags": _shuffle_tags(
            list(tool.get("tags") or []),
            f"{variation_key}|{tool.get('name', '')}",
        ),
    }
    if "args" in tool and isinstance(tool.get("args"), dict):
        if tool["args"]:
            compact_tool["args"] = tool["args"]
        return compact_tool

    arguments_schema = tool.get("arguments_schema")
    if isinstance(arguments_schema, dict):
        compact_args = compact_args_from_schema(arguments_schema)
        if compact_args:
            compact_tool["args"] = compact_args
    return compact_tool


def normalize_dataset_row(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("user"), str) and "assistant" in row:
        assistant = row["assistant"]
        if isinstance(assistant, str):
            assistant = json.loads(assistant)
        return {
            "tools": [compact_tool_from_record(tool) for tool in row.get("tools", [])],
            "user": row["user"],
            "assistant": assistant,
        }

    messages = row.get("messages") or []
    assistant = messages[1]["content"]
    if isinstance(assistant, str):
        assistant = json.loads(assistant)
    return {
        "tools": [compact_tool_from_record(tool) for tool in row.get("tools", [])],
        "user": messages[0]["content"],
        "assistant": assistant,
    }


def _format_tool_line(tool: dict[str, Any]) -> str:
    tags = [str(tag) for tag in tool.get("tags", []) if str(tag).strip()]
    if not tags:
        tags = [tool["name"].replace("_", " ")]

    line = f"- {tool['name']}: {' | '.join(tags)}"
    args = tool.get("args") or {}
    if args:
        arg_parts: list[str] = []
        for field_name in sorted(args):
            spec = args[field_name]
            if isinstance(spec, list):
                rendered_spec = " | ".join(str(value) for value in spec)
            else:
                rendered_spec = str(spec)
            arg_parts.append(f"{field_name}={rendered_spec}")
        line += f" ; args: {', '.join(arg_parts)}"
    return line


def serialize_compact_prompt(tools: list[dict[str, Any]], user_text: str) -> str:
    rendered_tools = "\n".join(_format_tool_line(tool) for tool in tools) or "- none"
    return f"TOOLS:\n{rendered_tools}\nUSER:\n{user_text}\nOUTPUT:\n"
