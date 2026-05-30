from protonx.training.evaluation import build_unique_holdout_rows


def test_build_unique_holdout_rows_uses_only_unseen_requests() -> None:
    records = [
        {
            "tools": [
                {"name": "list_downloads", "tags": ["downloads"]},
                {"name": "get_node_version", "tags": ["node version"]},
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "show me downloads",
            "assistant": {"tool_calls": [{"name": "list_downloads", "arguments": {}}]},
        },
        {
            "tools": [
                {"name": "list_downloads", "tags": ["downloads"]},
                {"name": "get_node_version", "tags": ["node version"]},
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "node version",
            "assistant": {"tool_calls": [{"name": "get_node_version", "arguments": {}}]},
        },
    ]

    rows = build_unique_holdout_rows(records)

    assert rows
    assert all(row["tools"] == records[0]["tools"] for row in rows)
    assert {row["assistant"]["tool_calls"][0]["name"] for row in rows} == {
        "list_downloads",
        "get_node_version",
        "__fallback__",
    }
    seen_users = {record["user"].strip().lower() for record in records}
    assert all(row["user"].strip().lower() not in seen_users for row in rows)


def test_build_unique_holdout_rows_include_unavailable_tool_family_fallbacks() -> None:
    records = [
        {
            "tools": [
                {"name": "git_status", "tags": ["статус git"]},
                {"name": "get_node_version", "tags": ["версия node"]},
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "покажи статус git",
            "assistant": {"tool_calls": [{"name": "git_status", "arguments": {}}]},
        },
        {
            "tools": [
                {"name": "docker_list_containers", "tags": ["контейнеры docker"]},
                {"name": "get_node_version", "tags": ["версия node"]},
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "покажи контейнеры docker",
            "assistant": {"tool_calls": [{"name": "docker_list_containers", "arguments": {}}]},
        },
    ]

    rows = build_unique_holdout_rows(records)
    fallback_rows = [
        row
        for row in rows
        if row["assistant"]["tool_calls"][0]["name"] == "__fallback__"
    ]
    git_unavailable = [
        row
        for row in fallback_rows
        if "git" in row["user"].lower()
        and all(not tool["name"].startswith("git_") for tool in row["tools"])
    ]
    docker_unavailable = [
        row
        for row in fallback_rows
        if "docker" in row["user"].lower()
        and all(not tool["name"].startswith("docker_") for tool in row["tools"])
    ]

    assert git_unavailable
    assert docker_unavailable


def test_build_unique_holdout_rows_include_argument_specific_cases() -> None:
    records = [
        {
            "tools": [
                {
                    "name": "list_directory",
                    "tags": ["папка проекта"],
                    "args": {
                        "directory": {
                            "description": "Какую директорию показать.",
                            "enum": [
                                "downloads: папка загрузок",
                                "project_root: корень проекта",
                                "service: сервис модели",
                                "web_backend: backend интерфейса",
                                "web_ui: frontend интерфейса",
                                "data: данные проекта",
                            ],
                        }
                    },
                },
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "покажи папку data",
            "assistant": {"tool_calls": [{"name": "list_directory", "arguments": {"directory": "data"}}]},
        },
        {
            "tools": [
                {
                    "name": "get_node_version",
                    "tags": ["node", "npm"],
                    "args": {
                        "target": {
                            "description": "Версию чего показать.",
                            "enum": [
                                "node: версия Node.js",
                                "npm: версия npm",
                            ],
                        }
                    },
                },
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "покажи node -v",
            "assistant": {"tool_calls": [{"name": "get_node_version", "arguments": {"target": "node"}}]},
        },
        {
            "tools": [
                {
                    "name": "docker_list_containers",
                    "tags": ["docker ps"],
                    "args": {
                        "state": {
                            "enum": [
                                "running: только запущенные",
                                "all: все контейнеры",
                            ]
                        }
                    },
                },
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "покажи docker ps",
            "assistant": {"tool_calls": [{"name": "docker_list_containers", "arguments": {"state": "running"}}]},
        },
        {
            "tools": [
                {
                    "name": "check_http_head",
                    "tags": ["head"],
                    "args": {
                        "target": {
                            "enum": [
                                "example_com: example.com",
                                "pypi: pypi.org",
                                "npm_registry: registry.npmjs.org",
                                "github: github.com",
                            ]
                        }
                    },
                },
                {"name": "__fallback__", "tags": ["fallback"]},
            ],
            "user": "проверь github",
            "assistant": {"tool_calls": [{"name": "check_http_head", "arguments": {"target": "github"}}]},
        },
    ]

    rows = build_unique_holdout_rows(records)
    rows_by_user = {row["user"]: row for row in rows}

    assert rows_by_user["выведи листинг каталога web ui"]["assistant"]["tool_calls"] == [
        {"name": "list_directory", "arguments": {"directory": "web_ui"}}
    ]
    assert rows_by_user["проверь именно npm --version"]["assistant"]["tool_calls"] == [
        {"name": "get_node_version", "arguments": {"target": "npm"}}
    ]
    assert rows_by_user["выведи docker ps --all полностью"]["assistant"]["tool_calls"] == [
        {"name": "docker_list_containers", "arguments": {"state": "all"}}
    ]
    assert rows_by_user["github.com отвечает на head или нет"]["assistant"]["tool_calls"] == [
        {"name": "check_http_head", "arguments": {"target": "github"}}
    ]
