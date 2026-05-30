import json
from pathlib import Path

from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.contracts import with_fallback_tool
from protonx.routing.prompt import build_routing_prompt
from protonx.schemas import JsonSchema, ToolDefinition
from protonx.training.dataset_builder import build_examples, build_synthetic_dataset


def test_build_synthetic_dataset_creates_jsonl_rows(tmp_path: Path):
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp", "свет", "лампа"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close", "окно", "открыть"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]
    output_path = tmp_path / "routing.jsonl"
    rows_written = build_synthetic_dataset(tools=tools, output_path=output_path, target_rows=300)
    assert rows_written > 0
    assert output_path.exists()
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any("tool_calls" in row["assistant"] for row in rows)
    assert any(
        row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
        for row in rows
    )
    assert any(
        {tool["name"] for tool in row["tools"]} >= {"window", "light"} for row in rows
    )


def test_build_examples_can_generate_large_mixed_dataset_from_seed():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node version", "версия node", "версия ноды"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_python_version",
            description="Python version",
            tags=["python version", "версия python"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_disk_usage",
            description="Disk usage",
            tags=["disk space", "место на диске"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools, target_rows=500)
    users = {row["user"] for row in rows}

    assert len(rows) == 500
    fallback_count = sum(
        row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
        for row in rows
    )
    assert fallback_count >= 70
    assert any("версия ноды" in user.lower() and "установлена" in user.lower() for user in users)
    assert any("покажи версию ноды" in user.lower() for user in users)
    assert any(user == "какая версия установлена" for user in users)
    assert all(any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in user) for user in users)
    assert not any(user.startswith("Check disk space") for user in users)
    assert any(
        row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
        for row in rows
    )


def test_build_examples_use_schema_valid_arguments_and_vary_tool_position():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "lamp", "свет", "лампа"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "close", "окно", "открыть"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["open", "close"]}},
                required=["state"],
            ),
        ),
    ]

    rows = build_examples(tools, target_rows=300)
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

    rows = build_examples(tools, target_rows=1500)
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
    assert not any(row["user"] == "show me downloads" for row, assistant in tool_rows)
    assert any(row["user"] == "покажи загрузки" for row, assistant in tool_rows)
    assert any(row["user"] == "покажи версию ноды" for row, assistant in tool_rows)
    assert any(row["user"].startswith("какая версия ноды") for row, assistant in tool_rows)


def test_build_examples_can_generate_large_ru_only_rows_from_seed():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="Downloads",
            tags=["downloads", "папка загрузок", "загрузки", "скачанные файлы"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node version", "версия node", "версия ноды", "нода"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_python_version",
            description="Python version",
            tags=["python version", "версия python", "версия питона", "питон"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_current_time",
            description="Time",
            tags=["current time", "текущее время", "который час", "дата"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_disk_usage",
            description="Disk usage",
            tags=["disk space", "место на диске", "свободное место", "диск"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools, target_rows=3000)
    users = [row["user"] for row in rows]
    class_counts: dict[str, int] = {}
    for row in rows:
        tool_name = row["assistant"]["tool_calls"][0]["name"]
        class_counts[tool_name] = class_counts.get(tool_name, 0) + 1

    assert len(rows) == 3000
    unique_prompts = {
        json.dumps({"tools": row["tools"], "user": row["user"]}, ensure_ascii=False, sort_keys=True)
        for row in rows
    }
    assert len(unique_prompts) == 3000
    assert all(any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in user) for user in users)
    assert class_counts["get_node_version"] >= 120
    assert class_counts["get_python_version"] >= 120
    assert class_counts["get_current_time"] >= 120
    assert class_counts["get_disk_usage"] >= 120
    assert class_counts["list_downloads"] >= 120


def test_build_examples_include_seed_training_tools_as_target_classes():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["версия node"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools, target_rows=1500)
    target_names = {
        row["assistant"]["tool_calls"][0]["name"]
        for row in rows
    }
    docker_rows = [
        row for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == "docker_list_containers"
    ]
    git_rows = [
        row for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == "git_status"
    ]

    assert "docker_list_containers" in target_names
    assert "git_status" in target_names
    assert any("контейнер" in row["user"].lower() for row in docker_rows)
    assert any("статус гита" in row["user"].lower() for row in git_rows)


def test_build_examples_include_unavailable_tool_family_fallback_rows():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["версия node"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools, target_rows=0)
    fallback_rows = [
        row
        for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
    ]
    git_rows = [row for row in fallback_rows if row["user"] == "покажи статус гита"]
    docker_rows = [row for row in fallback_rows if row["user"] == "покажи контейнеры докера"]

    assert git_rows
    assert docker_rows
    assert all(not tool["name"].startswith("git_") for tool in git_rows[0]["tools"])
    assert all(not tool["name"].startswith("docker_") for tool in docker_rows[0]["tools"])


def test_build_examples_support_single_tool_registry():
    tools = [
        ToolDefinition(
            name="get_current_time",
            description="Return the current local date and time of the machine.",
            tags=["current time", "текущее время"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools, target_rows=300)
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

    training_example = build_examples(tools, target_rows=300)[0]
    runtime_prompt = build_routing_prompt(
        user_text="turn on the lamp",
        tools=with_fallback_tool(tools),
    )
    runtime_tool_names = [tool["name"] for tool in runtime_prompt["tools"]]
    training_tool_names = [tool["name"] for tool in training_example["tools"]]
    assert runtime_tool_names[-1] == FALLBACK_TOOL_NAME
    assert training_tool_names[-1] == FALLBACK_TOOL_NAME
    assert set(runtime_tool_names).issubset(set(training_tool_names))
    assert "system" not in runtime_prompt


def test_build_examples_can_include_decoy_tools_without_targeting_them():
    tools = [
        ToolDefinition(
            name="get_current_time",
            description="Return current time",
            tags=["current time", "time"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools, target_rows=120)
    assistant_names = {row["assistant"]["tool_calls"][0]["name"] for row in rows}
    tool_names = {tool["name"] for row in rows for tool in row["tools"]}

    assert "open_browser" in tool_names
    assert "play_music" in tool_names
    assert assistant_names <= {"get_current_time", FALLBACK_TOOL_NAME}


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

    rows = build_examples(tools, target_rows=300)
    fallback_rows = [
        row
        for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
    ]
    assert any(row["user"] == "как дела" for row in fallback_rows)
    assert any(row["user"] == "расскажи шутку" for row in fallback_rows)
    assert any(row["user"] == "измени это" for row in fallback_rows)
    assert all(row["assistant"]["tool_calls"][0]["arguments"] == {} for row in fallback_rows)


def test_build_examples_include_version_hard_negative_when_multiple_version_tools_exist():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node version",
            tags=["node", "node version", "version", "версия node"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="get_python_version",
            description="Python version",
            tags=["python", "python version", "version", "версия python"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools, target_rows=300)
    fallback_rows = {
        row["user"]: row
        for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
    }

    assert "покажи версию" in fallback_rows
    assert fallback_rows["покажи версию"]["assistant"]["tool_calls"] == [
        {"name": FALLBACK_TOOL_NAME, "arguments": {}}
    ]


def test_build_examples_include_ambiguous_hard_negatives_for_overlapping_controls():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light", "brightness", "свет", "яркость"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="window",
            description="Window control",
            tags=["window", "open", "close", "окно", "открыть"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="speaker",
            description="Speaker control",
            tags=["speaker", "volume", "sound", "колонка", "громкость"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
        ToolDefinition(
            name="file_search",
            description="File search",
            tags=["file", "search", "open", "файл", "поиск"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        ),
    ]

    rows = build_examples(tools, target_rows=300)
    fallback_rows = {
        row["user"]: row
        for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
    }

    assert "сделай потише" in fallback_rows
    assert "открой" in fallback_rows


def test_build_examples_include_argument_probe_rows():
    tools = [
        ToolDefinition(
            name="search_files",
            description="Search files",
            tags=["find file", "search file", "найти файл"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"query": {"type": "string"}},
                required=["query"],
            ),
        ),
        ToolDefinition(
            name="search_web",
            description="Search web",
            tags=["search", "google", "поиск"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"q": {"type": "string"}},
                required=["q"],
            ),
        ),
    ]

    rows = build_examples(tools, target_rows=0)
    rows_by_user = {row["user"]: row for row in rows}

    assert rows_by_user["найди package.json"]["assistant"]["tool_calls"][0]["arguments"] == {
        "query": "package.json"
    }
    assert "find node js latest version" not in rows_by_user


def test_build_examples_include_seed_argument_rows_for_concrete_readonly_tools():
    tools = [
        ToolDefinition(
            name="get_node_version",
            description="Node/npm version",
            tags=["node version", "npm version", "версия ноды", "версия npm"],
            arguments_schema=JsonSchema(
                type="object",
                properties={
                    "target": {
                        "type": "string",
                        "description": "Version target.",
                        "enum": [
                            "node: версия Node.js через node --version",
                            "npm: версия npm через npm --version",
                        ],
                    }
                },
                required=["target"],
            ),
        ),
        ToolDefinition(
            name="docker_list_containers",
            description="List Docker containers",
            tags=["docker ps", "контейнеры докера"],
            arguments_schema=JsonSchema(
                type="object",
                properties={
                    "state": {
                        "type": "string",
                        "description": "Container state.",
                        "enum": [
                            "running: только запущенные контейнеры, docker ps",
                            "all: все контейнеры включая остановленные, docker ps --all",
                        ],
                    }
                },
                required=["state"],
            ),
        ),
    ]

    rows = build_examples(tools, target_rows=0)
    rows_by_user = {row["user"]: row for row in rows}

    assert rows_by_user["покажи npm -v"]["assistant"]["tool_calls"][0]["arguments"] == {
        "target": "npm"
    }
    assert rows_by_user["покажи docker ps"]["assistant"]["tool_calls"][0]["arguments"] == {
        "state": "running"
    }
    target_arg = next(
        tool["args"]["target"]
        for tool in rows_by_user["покажи npm -v"]["tools"]
        if tool["name"] == "get_node_version"
    )
    state_arg = next(
        tool["args"]["state"]
        for tool in rows_by_user["покажи docker ps"]["tools"]
        if tool["name"] == "docker_list_containers"
    )
    assert target_arg["enum"] == [
        "node: версия Node.js через node --version",
        "npm: версия npm через npm --version",
    ]
    assert target_arg["description"] == "Version target."
    assert "enum_descriptions" not in target_arg
    assert state_arg["enum"] == [
        "running: только запущенные контейнеры, docker ps",
        "all: все контейнеры включая остановленные, docker ps --all",
    ]


def test_build_examples_skip_argument_probe_rows_when_tools_are_missing_from_registry():
    tools = [
        ToolDefinition(
            name="list_downloads",
            description="List downloads",
            tags=["downloads"],
            arguments_schema=JsonSchema(type="object", properties={}, required=[]),
        )
    ]

    rows = build_examples(tools, target_rows=300)
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

    rows = build_examples(tools, target_rows=300)
    list_downloads_tag_orders = {
        tuple(tool["tags"])
        for row in rows
        for tool in row["tools"]
        if tool["name"] == "list_downloads"
    }

    assert len(list_downloads_tag_orders) >= 2


def test_build_examples_interleave_fallback_rows_into_dataset():
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

    rows = build_examples(tools, target_rows=300)
    first_fallback_index = next(
        index
        for index, row in enumerate(rows)
        if row["assistant"]["tool_calls"][0]["name"] == FALLBACK_TOOL_NAME
    )

    assert first_fallback_index < len(rows) - 4
