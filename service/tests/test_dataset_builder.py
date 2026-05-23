import json
from pathlib import Path

from protonx.routing.prompt import build_routing_prompt
from protonx.schemas import JsonSchema, ToolDefinition
from protonx.training.dataset_builder import build_examples, build_synthetic_dataset


def test_build_synthetic_dataset_creates_jsonl_rows(tmp_path: Path):
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]
    output_path = tmp_path / "routing.jsonl"
    rows_written = build_synthetic_dataset(tools=tools, output_path=output_path)
    assert rows_written > 0
    assert output_path.exists()
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any('"tool_calls"' in row["messages"][1]["content"] for row in rows)
    assert any('"fallback": true' in row["messages"][1]["content"] for row in rows)
    assert any(
        {tool["name"] for tool in row["tools"]} >= {"window", "light"} for row in rows
    )


def test_build_examples_use_schema_valid_arguments_and_vary_tool_position():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]

    rows = build_examples(tools)
    tool_rows = []
    for row in rows:
        assistant = json.loads(row["messages"][1]["content"])
        if assistant["tool_calls"]:
            tool_rows.append((row, assistant))
    assert any(
        assistant["tool_calls"][0]["arguments"]["state"] == "open"
        for row, assistant in tool_rows
        if assistant["tool_calls"][0]["name"] == "window"
    )
    assert any(
        row["tools"][0]["name"] != assistant["tool_calls"][0]["name"]
        for row, assistant in tool_rows
    )


def test_runtime_prompt_uses_same_system_contract_as_training_examples():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]

    training_example = build_examples(tools)[0]
    runtime_prompt = build_routing_prompt(
        user_text="turn on the lamp",
        tools=tools,
        answer_allowed=False,
    )
    assert runtime_prompt["system"] == training_example["system"]


def test_build_examples_include_unknown_and_ambiguous_fallback_rows():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]

    rows = build_examples(tools)
    fallback_rows = [
        row for row in rows if json.loads(row["messages"][1]["content"]).get("fallback") is True
    ]
    assert any(row["messages"][0]["content"] == "how are you" for row in fallback_rows)
    assert any(row["messages"][0]["content"] == "change it" for row in fallback_rows)
