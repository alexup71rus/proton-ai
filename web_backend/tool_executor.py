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


def _list_directory_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Какую разрешённую директорию показать.",
                "enum": {
                    "downloads": "папка загрузок текущего пользователя",
                    "project_root": "корень текущего проекта Proton-X",
                    "service": "FastAPI сервис модели в папке service",
                    "web_backend": "FastAPI backend для UI",
                    "web_ui": "React/Vite интерфейс оператора",
                    "data": "локальные данные, датасеты и артефакты проекта",
                },
            }
        },
        "required": ["directory"],
    }


def _node_version_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Версию какого инструмента показать.",
                "enum": {
                    "node": "версия Node.js через node --version",
                    "npm": "версия npm через npm --version",
                },
            }
        },
        "required": ["target"],
    }


def _docker_list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "Показать только запущенные или все контейнеры.",
                "enum": {
                    "running": "только запущенные контейнеры, docker ps",
                    "all": "все контейнеры включая остановленные, docker ps --all",
                },
            }
        },
        "required": ["state"],
    }


def _http_head_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Какой разрешённый endpoint проверить.",
                "enum": {
                    "example_com": "https://example.com для базовой проверки интернета",
                    "pypi": "https://pypi.org для проверки Python package index",
                    "npm_registry": "https://registry.npmjs.org для проверки npm registry",
                    "github": "https://github.com для проверки доступности GitHub",
                },
            }
        },
        "required": ["target"],
    }


def get_default_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "list_directory",
            "description": "Показать файлы и папки в одной из разрешённых локальных директорий.",
            "tags": [
                "downloads",
                "downloads folder",
                "download folder",
                "project files",
                "project root",
                "files",
                "directory listing",
                "папка загрузок",
                "загрузки",
                "скачанные файлы",
                "файлы проекта",
                "список файлов",
                "папка проекта",
            ],
            "arguments_schema": _list_directory_schema(),
            "executor_path": "web_backend/executors/list_directory.py",
        },
        {
            "name": "get_node_version",
            "description": "Показать установленную версию Node.js или npm на этой машине.",
            "tags": [
                "node",
                "node version",
                "node js",
                "nodejs",
                "node.js",
                "npm",
                "npm version",
                "npm -v",
                "версия node",
                "версия node js",
                "версия npm",
                "нода",
                "нпм",
            ],
            "arguments_schema": _node_version_schema(),
            "executor_path": "web_backend/executors/get_node_version.py",
        },
        {
            "name": "docker_list_containers",
            "description": "Показать Docker-контейнеры через безопасный readonly docker ps.",
            "tags": [
                "docker",
                "docker ps",
                "containers",
                "container list",
                "докер",
                "контейнеры",
                "список контейнеров",
                "запущенные контейнеры",
            ],
            "arguments_schema": _docker_list_schema(),
            "executor_path": "web_backend/executors/docker_list_containers.py",
        },
        {
            "name": "check_http_head",
            "description": "Проверить доступность разрешённого публичного endpoint через readonly HTTP HEAD.",
            "tags": [
                "internet",
                "http head",
                "curl",
                "connectivity",
                "network check",
                "интернет",
                "подключение",
                "проверить сайт",
                "доступность сайта",
            ],
            "arguments_schema": _http_head_schema(),
            "executor_path": "web_backend/executors/check_http_head.py",
        },
        {
            "name": "get_python_version",
            "description": "Показать версию Python, доступную среде исполнения.",
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
            "description": "Показать текущую локальную дату и время на машине.",
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
            "description": "Показать использование диска для домашнего раздела текущего пользователя.",
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
