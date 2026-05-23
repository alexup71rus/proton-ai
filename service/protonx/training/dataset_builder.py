import json
from itertools import permutations
from pathlib import Path

from protonx.contracts import build_fallback_payload, build_system_contract
from protonx.schemas import ToolDefinition


def _default_arguments(tool: ToolDefinition) -> dict:
    arguments: dict[str, str] = {}
    for field_name in tool.arguments_schema.required:
        property_schema = tool.arguments_schema.properties.get(field_name, {})
        enum_values = property_schema.get("enum")
        if enum_values:
            arguments[field_name] = enum_values[0]
    return arguments


def _tool_call_example(primary: ToolDefinition, alternatives: list[ToolDefinition]) -> dict:
    candidate_tools = [primary.model_dump()]
    candidate_tools.extend(tool.model_dump() for tool in alternatives[:2])
    if len(candidate_tools) > 1 and primary.name > candidate_tools[1]["name"]:
        candidate_tools[0], candidate_tools[1] = candidate_tools[1], candidate_tools[0]
    return {
        "system": build_system_contract(False),
        "tools": candidate_tools,
        "messages": [
            {
                "role": "user",
                "content": f"turn on the {primary.tags[1] if len(primary.tags) > 1 else primary.name}",
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "tool_calls": [
                            {"name": primary.name, "arguments": _default_arguments(primary)}
                        ],
                        "answer": False,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }


def _fallback_example(tools: list[ToolDefinition]) -> dict:
    return {
        "system": build_system_contract(True),
        "tools": [tool.model_dump() for tool in tools[:2]],
        "messages": [
            {"role": "user", "content": "how are you"},
            {
                "role": "assistant",
                "content": json.dumps(build_fallback_payload(True), ensure_ascii=False),
            },
        ],
    }


def _ambiguous_fallback_example(tools: list[ToolDefinition]) -> dict:
    return {
        "system": build_system_contract(False),
        "tools": [tool.model_dump() for tool in tools[:2]],
        "messages": [
            {"role": "user", "content": "change it"},
            {
                "role": "assistant",
                "content": json.dumps(build_fallback_payload(False), ensure_ascii=False),
            },
        ],
    }


def build_examples(tools: list[ToolDefinition]) -> list[dict]:
    rows: list[dict] = []
    for primary, secondary in permutations(tools, 2):
        alternatives = [
            secondary,
            *[
                tool
                for tool in tools
                if tool.name not in {primary.name, secondary.name}
            ],
        ]
        rows.append(_tool_call_example(primary, alternatives))
    if tools:
        rows.append(_fallback_example(tools))
        rows.append(_ambiguous_fallback_example(tools))
    return rows


def build_synthetic_dataset(tools: list[ToolDefinition], output_path: Path) -> int:
    rows = build_examples(tools)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows_written += 1
    return rows_written
