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
