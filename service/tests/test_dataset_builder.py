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
    assert any("tool_calls" in row["assistant"] for row in rows)
    assert any(row["assistant"].get("fallback") is True for row in rows)
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
        assistant = row["assistant"]
        if assistant["tool_calls"] and assistant["tool_calls"][0]["name"] in {
            "light",
            "window",
        }:
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


def test_build_examples_use_empty_arguments_for_zero_argument_tools_and_more_prompt_variants():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="List files and folders in the current user's Downloads directory.",
            tags=["downloads", "папка загрузок"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_node_version",
            description="Read the installed Node.js version available on this machine.",
            tags=["node version", "версия node"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools)
    tool_rows = []
    for row in rows:
        assistant = row["assistant"]
        if assistant["tool_calls"] and assistant["tool_calls"][0]["name"] in {
            "list_downloads",
            "get_node_version",
        }:
            tool_rows.append((row, assistant))

    assert len(tool_rows) >= 8
    assert all(assistant["tool_calls"][0]["arguments"] == {} for row, assistant in tool_rows)
    assert any(row["user"] == "show me downloads" for row, assistant in tool_rows)
    assert any(row["user"] == "покажи версия node" for row, assistant in tool_rows)


def test_build_examples_support_single_tool_registry():
    tools = [
        ToolDefinition(
            name="get_current_time",
            description="Return the current local date and time of the machine.",
            tags=["current time", "текущее время"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools)
    tool_rows = [
        row
        for row in rows
        if row["assistant"]["tool_calls"]
        and row["assistant"]["tool_calls"][0]["name"] == "get_current_time"
    ]

    assert len(tool_rows) >= 2
    assert all(row["tools"][0]["name"] == "get_current_time" for row in tool_rows)


def test_runtime_prompt_uses_same_compact_tools_contract_as_training_examples():
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
    assert [tool["name"] for tool in runtime_prompt["tools"]] == [
        tool["name"] for tool in training_example["tools"]
    ]
    assert [set(tool["tags"]) for tool in runtime_prompt["tools"]] == [
        set(tool["tags"]) for tool in training_example["tools"]
    ]
    assert "system" not in runtime_prompt


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
        row for row in rows if row["assistant"].get("fallback") is True
    ]
    assert any(row["user"] == "how are you" for row in fallback_rows)
    assert any(row["user"] == "как дела" for row in fallback_rows)
    assert any(row["user"] == "tell me a joke" for row in fallback_rows)
    assert any(row["user"] == "change it" for row in fallback_rows)
    assert all(row["assistant"]["answer"] is True for row in fallback_rows)


def test_build_examples_include_version_hard_negative_when_multiple_version_tools_exist():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node", "node version", "version"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_python_version",
            description="Python version",
            tags=["python", "python version", "version"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools)
    fallback_rows = {row["user"]: row for row in rows if row["assistant"].get("fallback") is True}

    assert "show me version" in fallback_rows
    assert "покажи версию" in fallback_rows
    assert fallback_rows["show me version"]["assistant"]["tool_calls"] == []


def test_build_examples_include_ambiguous_hard_negatives_for_overlapping_controls():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "brightness"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "open", "close"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="speaker",
            description="Speaker control",
            tags=["speaker", "volume", "sound"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="file_search",
            description="File search",
            tags=["file", "search", "open"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools)
    fallback_rows = {row["user"]: row for row in rows if row["assistant"].get("fallback") is True}

    assert "make it quieter" in fallback_rows
    assert "сделай потише" in fallback_rows
    assert "open" in fallback_rows
    assert "открой" in fallback_rows


def test_build_examples_include_argument_probe_rows():
    tools = [
        ToolDefinition(
            name="search_files",
            description="Search files",
            tags=["find file", "search file"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"query": {"type": "string"}},
                required=["query"],
            ),
        ),
        ToolDefinition(
            name="search_web",
            description="Search web",
            tags=["search", "google"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"q": {"type": "string"}},
                required=["q"],
            ),
        ),
    ]

    rows = build_examples(tools)
    rows_by_user = {row["user"]: row for row in rows}

    assert rows_by_user["найди package.json"]["assistant"]["tool_calls"][0]["arguments"] == {
        "query": "package.json"
    }
    assert rows_by_user["find node js latest version"]["assistant"]["tool_calls"][0]["arguments"] == {
        "q": "node js latest version"
    }


def test_build_examples_skip_argument_probe_rows_when_tools_are_missing_from_registry():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="List downloads",
            tags=["downloads"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools)
    users = {row["user"] for row in rows}

    assert "найди package.json" not in users
    assert "find README.md" not in users
    assert "find node js latest version" not in users


def test_build_examples_vary_tag_order_across_rows_for_same_tool():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="List downloads",
            tags=["downloads", "download folder", "files", "папка загрузок"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node", "node version", "node js", "версия node"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools)
    list_downloads_tag_orders = {
        tuple(tool["tags"])
        for row in rows
        for tool in row["tools"]
        if tool["name"] == "list_downloads"
    }

    assert len(list_downloads_tag_orders) >= 2


def test_build_examples_interleave_answer_true_rows_into_dataset():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="List downloads",
            tags=["downloads", "download folder"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node", "node version"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools)
    first_answer_true_index = next(
        index for index, row in enumerate(rows) if row["assistant"]["answer"] is True
    )

    assert first_answer_true_index < len(rows) - 4
