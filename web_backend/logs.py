from __future__ import annotations

import json
import textwrap
from typing import Any

from web_backend.config import get_log_file
from web_backend.dataset_validation import build_dataset_fallback_payload
from web_backend.dataset_validation import with_dataset_fallback_tool


def _load_raw_logs(limit: int = 100) -> list[dict[str, Any]]:
    path = get_log_file()
    if not path.exists():
        return []

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows[-limit:][::-1]


def load_human_logs(limit: int = 100) -> list[dict[str, Any]]:
    rows = _load_raw_logs(limit)

    result: list[dict[str, Any]] = []
    for row in rows:
        raw_output = row.get("model_output", "")
        result.append(
            {
                "created_at": row.get("created_at") or row.get("timestamp"),
                "user": row.get("user_text", ""),
                "raw_output_summary": textwrap.shorten(raw_output, width=120, placeholder="..."),
                "raw_output": raw_output,
                "error": row.get("validation_error") or "none",
                "result": row.get("final_action") or "unknown",
            }
        )
    return result


def clear_human_logs() -> int:
    path = get_log_file()
    if not path.exists():
        return 0

    rows_deleted = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    path.write_text("", encoding="utf-8")
    return rows_deleted


def export_failed_cases_as_dataset(tools_registry: list[dict[str, Any]], limit: int = 100) -> list[dict[str, Any]]:
    registry_by_name = {
        tool["name"]: {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "tags": tool.get("tags", []),
            "arguments_schema": tool.get(
                "arguments_schema",
                {"type": "object", "properties": {}, "required": []},
            ),
        }
        for tool in tools_registry
        if tool.get("name")
    }

    dataset_rows: list[dict[str, Any]] = []
    for row in _load_raw_logs(limit):
        if row.get("final_action") != "fallback" and not row.get("validation_error"):
            continue
        user_text = str(row.get("user_text") or "").strip()
        if not user_text:
            continue
        available_tool_names = row.get("available_tools", [])
        available_tools = [
            registry_by_name[name]
            for name in available_tool_names
            if name in registry_by_name
        ]
        dataset_rows.append(
            {
                "tools": with_dataset_fallback_tool(available_tools),
                "user": user_text,
                "assistant": build_dataset_fallback_payload(),
            }
        )
    return dataset_rows
