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
