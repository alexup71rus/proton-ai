from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import run
from typing import Any

from web_backend.config import ROOT_DIR


def _empty_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "required": [],
    }


def get_default_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "list_downloads",
            "description": "List files and folders in the current user's Downloads directory.",
            "tags": [
                "downloads",
                "downloads folder",
                "download folder",
                "files",
                "папка загрузок",
                "загрузки",
                "скачанные файлы",
            ],
            "arguments_schema": _empty_schema(),
            "executor_path": "web_backend/executors/list_downloads.py",
        },
        {
            "name": "get_node_version",
            "description": "Read the installed Node.js version available on this machine.",
            "tags": [
                "node",
                "node version",
                "node js",
                "nodejs",
                "node.js",
                "версия node",
                "версия node js",
            ],
            "arguments_schema": _empty_schema(),
            "executor_path": "web_backend/executors/get_node_version.py",
        },
        {
            "name": "get_python_version",
            "description": "Read the Python version available to the executor runtime.",
            "tags": [
                "python",
                "python version",
                "interpreter",
                "версия python",
                "питон",
                "интерпретатор",
            ],
            "arguments_schema": _empty_schema(),
            "executor_path": "web_backend/executors/get_python_version.py",
        },
        {
            "name": "get_current_time",
            "description": "Return the current local date and time of the machine.",
            "tags": [
                "time",
                "current time",
                "date",
                "clock",
                "текущее время",
                "сейчас",
                "дата",
            ],
            "arguments_schema": _empty_schema(),
            "executor_path": "web_backend/executors/get_current_time.py",
        },
        {
            "name": "get_disk_usage",
            "description": "Return disk usage for the current user's home volume.",
            "tags": [
                "disk",
                "disk usage",
                "storage",
                "free space",
                "место на диске",
                "свободное место",
                "диск",
            ],
            "arguments_schema": _empty_schema(),
            "executor_path": "web_backend/executors/get_disk_usage.py",
        },
    ]


def _resolve_executor_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def validate_tool_executor_paths(tools: list[dict[str, Any]]) -> None:
    for tool in tools:
        tool_name = str(tool.get("name") or "")
        executor_path = str(tool.get("executor_path") or "")
        if not executor_path:
            raise ValueError(f"Tool {tool_name or '<unnamed>'} must define executor_path")

        resolved_path = _resolve_executor_path(executor_path)
        if not resolved_path.exists() or not resolved_path.is_file():
            raise ValueError(
                f"Tool {tool_name or '<unnamed>'} executor_path not found: {resolved_path}"
            )


def execute_tool(tool: dict[str, Any], arguments: dict[str, Any] | None = None) -> dict[str, Any] | None:
    tool_name = str(tool.get("name") or "")
    executor_path = str(tool.get("executor_path") or "")
    if not tool_name:
        return None

    if not executor_path:
        return {
            "status": "unsupported",
            "tool_name": tool_name,
            "output": None,
            "error": f"Tool {tool_name} has no executor_path configured",
        }

    path = _resolve_executor_path(executor_path)
    if not path.exists() or not path.is_file():
        return {
            "status": "error",
            "tool_name": tool_name,
            "output": None,
            "error": f"Executor script not found: {path}",
        }

    command = [sys.executable, str(path)] if path.suffix == ".py" else [str(path)]
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "arguments": arguments or {},
        },
        ensure_ascii=False,
    )

    completed = run(
        command,
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT_DIR),
        check=False,
    )

    if completed.returncode != 0:
        message = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Executor exited with code {completed.returncode}"
        )
        return {
            "status": "error",
            "tool_name": tool_name,
            "output": None,
            "error": message,
        }

    stdout = completed.stdout.strip()
    if not stdout:
        return {
            "status": "executed",
            "tool_name": tool_name,
            "output": None,
            "error": None,
        }

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError:
        output = stdout

    return {
        "status": "executed",
        "tool_name": tool_name,
        "output": output,
        "error": None,
    }