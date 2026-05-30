from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.enum_values import enum_first_output_value
from protonx.enum_values import enum_output_values
from protonx.routing.model_runtime import ModelRuntime
from protonx.training.format import serialize_assistant_payload


SPECIAL_HOLDOUT_REQUESTS: dict[str, list[str]] = {
    "list_downloads": [
        "что сейчас лежит в директории загрузок",
    ],
    "list_directory": [
        "покажи содержимое разрешённой локальной папки",
        "выведи листинг нужной директории проекта",
    ],
    "get_node_version": [
        "сообщи установленный релиз Node.js на этой машине",
        "проверь локальный JavaScript runtime",
    ],
    "get_python_version": [
        "сообщи версию активного интерпретатора Python",
        "покажи релиз текущего Python runtime",
    ],
    "get_current_time": [
        "сообщи локальные дату и время на этой машине",
        "проверь системные часы без внешних сервисов",
    ],
    "get_disk_usage": [
        "сообщи свободное место на домашнем разделе",
        "покажи сколько занято на локальном диске",
    ],
    "docker_list_containers": [
        "покажи состояние контейнеров Docker readonly",
        "выведи список контейнеров без изменения Docker",
    ],
    "check_http_head": [
        "проверь доступность разрешённого endpoint через HEAD",
        "сделай безопасную сетевую HEAD проверку",
    ],
    FALLBACK_TOOL_NAME: [
        "закажи такси до аэропорта",
        "напиши короткое стихотворение о дожде",
        "запусти тесты в проекте",
        "почини ошибку в приложении",
        "выбери сам любой инструмент",
        "проверь что-нибудь непонятное",
        "сделай git push",
        "перезапусти docker compose",
        "открой неизвестный сайт",
        "прочитай секретный файл",
        "сделай установку зависимостей",
        "ответь без инструментов",
    ],
}

ARGUMENT_HOLDOUT_EXAMPLES: dict[str, list[dict[str, Any]]] = {
    "get_node_version": [
        {
            "arguments": {"target": "node"},
            "requests": [
                "какой релиз node runtime сейчас доступен",
                "сообщи nodejs version без запуска npm",
                "проверь именно node --version",
                "выведи версию локальной ноды",
            ],
        },
        {
            "arguments": {"target": "npm"},
            "requests": [
                "какой релиз npm cli сейчас доступен",
                "сообщи npm version без проверки node",
                "проверь именно npm --version",
                "выведи версию локального npm",
            ],
        },
    ],
    "docker_list_containers": [
        {
            "arguments": {"state": "running"},
            "requests": [
                "покажи только контейнеры которые сейчас up",
                "выведи docker ps без остановленных контейнеров",
                "какие docker контейнеры работают в данный момент",
                "посмотри активные контейнеры докера",
            ],
        },
        {
            "arguments": {"state": "all"},
            "requests": [
                "покажи контейнеры включая exited",
                "выведи docker ps --all полностью",
                "какие docker контейнеры существуют вообще",
                "посмотри все контейнеры докера вместе с остановленными",
            ],
        },
    ],
    "check_http_head": [
        {
            "arguments": {"target": "example_com"},
            "requests": [
                "сделай базовую HEAD проверку example.com",
                "example.com отвечает на head или нет",
                "проверь интернет через example dot com",
            ],
        },
        {
            "arguments": {"target": "pypi"},
            "requests": [
                "проверь HEAD доступ до Python package index",
                "pypi.org отвечает на head или нет",
                "сделай сетевую проверку pypi без скачивания",
            ],
        },
        {
            "arguments": {"target": "npm_registry"},
            "requests": [
                "проверь HEAD доступ до npm реестра",
                "registry.npmjs.org отвечает на head или нет",
                "сделай сетевую проверку npm registry без скачивания",
            ],
        },
        {
            "arguments": {"target": "github"},
            "requests": [
                "проверь HEAD доступ до github com",
                "github.com отвечает на head или нет",
                "сделай сетевую проверку github без скачивания",
            ],
        },
    ],
    "list_directory": [
        {
            "arguments": {"directory": "downloads"},
            "requests": [
                "что сейчас находится в пользовательских Downloads",
                "выведи листинг папки скачанных файлов",
                "посмотри локальную директорию загрузок",
            ],
        },
        {
            "arguments": {"directory": "project_root"},
            "requests": [
                "покажи файлы верхнего уровня proton x",
                "что лежит рядом с README проекта",
                "выведи корневую папку этого репозитория",
            ],
        },
        {
            "arguments": {"directory": "service"},
            "requests": [
                "что лежит внутри fastapi model service",
                "выведи листинг каталога service",
                "покажи папку серверной модели",
            ],
        },
        {
            "arguments": {"directory": "web_backend"},
            "requests": [
                "что лежит внутри backend для интерфейса",
                "выведи листинг каталога web backend",
                "покажи папку bff сервиса",
            ],
        },
        {
            "arguments": {"directory": "web_ui"},
            "requests": [
                "что лежит внутри react vite интерфейса",
                "выведи листинг каталога web ui",
                "покажи папку фронтенда",
            ],
        },
        {
            "arguments": {"directory": "data"},
            "requests": [
                "что лежит в локальном каталоге данных обучения",
                "выведи листинг папки весов датасетов и логов",
                "покажи папку data этого проекта",
            ],
        },
    ],
}

UNAVAILABLE_HOLDOUT_SCENARIOS: list[dict[str, Any]] = [
    {
        "tool_names": {
            "git_status",
            "git_diff",
            "git_log",
            "git_pull",
            "git_branch",
            "git_checkout_branch",
            "git_stash_changes",
        },
        "requests": [
            "проверь git status без git инструментов",
            "покажи diff репозитория когда git недоступен",
        ],
    },
    {
        "tool_names": {
            "docker_list_containers",
            "docker_show_logs",
            "docker_restart_container",
            "docker_build_image",
            "docker_compose_up",
            "docker_stop_container",
            "docker_pull_image",
        },
        "requests": [
            "покажи docker ps когда docker tool отсутствует",
            "перезапусти docker контейнер без docker инструмента",
        ],
    },
]


def _normalize_user_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _tool_args(tool: dict[str, Any]) -> dict[str, Any]:
    args = tool.get("args")
    return args if isinstance(args, dict) else {}


def _default_arguments(tool: dict[str, Any]) -> dict[str, str]:
    arguments: dict[str, str] = {}
    for field_name, spec in _tool_args(tool).items():
        if isinstance(spec, dict):
            enum_values = spec.get("enum")
            first_enum_value = enum_first_output_value(enum_values)
            if first_enum_value is not None:
                arguments[field_name] = first_enum_value
                continue
            spec = spec.get("type") or "string"
        if isinstance(spec, list) and spec:
            first_enum_value = enum_first_output_value(spec)
            if first_enum_value is not None:
                arguments[field_name] = first_enum_value
            continue
        arguments[field_name] = field_name.replace("_", " ")
    return arguments


def _schema_ok(arguments: dict[str, Any], tool: dict[str, Any]) -> bool:
    specs = _tool_args(tool)
    if not set(specs).issubset(arguments):
        return False
    if not set(arguments).issubset(specs):
        return False

    for key, value in arguments.items():
        spec = specs.get(key)
        if isinstance(spec, dict):
            enum_values = spec.get("enum")
            if enum_values is not None:
                if value not in enum_output_values(enum_values):
                    return False
                continue
            spec = spec.get("type") or "string"
        if isinstance(spec, list):
            if value not in enum_output_values(spec):
                return False
            continue
        if spec == "string" and not isinstance(value, str):
            return False
    return True


def _generic_holdout_requests(tool: dict[str, Any]) -> list[str]:
    display_name = str(tool.get("name") or "").replace("_", " ")
    tags = [str(tag).strip() for tag in tool.get("tags", []) if str(tag).strip()]
    alias = next((tag for tag in tags if any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in tag)), display_name)
    return [
        f"покажи {alias}",
        f"проверь {alias}",
    ]


def _holdout_requests_for_tool(tool: dict[str, Any]) -> list[str]:
    tool_name = str(tool.get("name") or "")
    requests = SPECIAL_HOLDOUT_REQUESTS.get(tool_name)
    if requests:
        return list(requests)
    return _generic_holdout_requests(tool)


def _append_holdout_row(
    rows: list[dict[str, Any]],
    seen_users: set[str],
    used_users: set[str],
    row_tools: list[dict[str, Any]],
    tool_name: str,
    arguments: dict[str, Any],
    request: str,
) -> None:
    normalized_request = _normalize_user_text(request)
    if normalized_request in seen_users or normalized_request in used_users:
        return
    used_users.add(normalized_request)
    rows.append(
        {
            "tools": row_tools,
            "user": request,
            "assistant": {
                "tool_calls": [
                    {
                        "name": tool_name,
                        "arguments": dict(arguments),
                    }
                ]
            },
        }
    )


def _dataset_tools(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []

    tool_by_name: dict[str, dict[str, Any]] = {}
    ordered_names: list[str] = []
    for record in records:
        target_names = {
            str(call.get("name") or "")
            for call in record.get("assistant", {}).get("tool_calls", [])
            if isinstance(call, dict) and str(call.get("name") or "")
        }
        if not target_names:
            continue
        for tool in record.get("tools", []):
            name = str(tool.get("name") or "")
            if not name or (name not in target_names and name != FALLBACK_TOOL_NAME) or name in tool_by_name:
                continue
            tool_by_name[name] = tool
            ordered_names.append(name)
    return [tool_by_name[name] for name in ordered_names]


def _representative_tools_by_target(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    representative: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        tool_calls = record.get("assistant", {}).get("tool_calls", [])
        tools = [
            tool
            for tool in record.get("tools", [])
            if str(tool.get("name") or "")
        ]
        if FALLBACK_TOOL_NAME not in representative and any(
            str(tool.get("name") or "") == FALLBACK_TOOL_NAME for tool in tools
        ):
            representative[FALLBACK_TOOL_NAME] = tools
        if not tool_calls:
            continue
        tool_name = str(tool_calls[0].get("name") or "")
        if not tool_name or tool_name in representative:
            continue
        if any(str(tool.get("name") or "") == tool_name for tool in tools):
            representative[tool_name] = tools
    return representative


def build_unique_holdout_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools = _dataset_tools(records)
    if not tools:
        return []
    tools_by_target = _representative_tools_by_target(records)

    seen_users = {
        _normalize_user_text(str(record.get("user") or ""))
        for record in records
        if str(record.get("user") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    used_users: set[str] = set()

    for tool in tools:
        tool_name = str(tool.get("name") or "")
        row_tools = tools_by_target.get(tool_name, tools)
        expected_arguments = _default_arguments(tool)
        for request in _holdout_requests_for_tool(tool):
            _append_holdout_row(
                rows,
                seen_users,
                used_users,
                row_tools,
                tool_name,
                expected_arguments,
                request,
            )
        for example in ARGUMENT_HOLDOUT_EXAMPLES.get(tool_name, []):
            arguments = example.get("arguments", {})
            if not isinstance(arguments, dict) or not _schema_ok(arguments, tool):
                continue
            raw_requests = example.get("requests", [])
            if not isinstance(raw_requests, list):
                continue
            for request in raw_requests:
                _append_holdout_row(
                    rows,
                    seen_users,
                    used_users,
                    row_tools,
                    tool_name,
                    arguments,
                    str(request),
                )

    available_tool_names = {str(tool.get("name") or "") for tool in tools}
    for scenario in UNAVAILABLE_HOLDOUT_SCENARIOS:
        unavailable_names = {
            str(name)
            for name in scenario.get("tool_names", set())
            if str(name)
        }
        if not (available_tool_names & unavailable_names):
            continue
        row_tools = [
            tool
            for tool in tools
            if str(tool.get("name") or "") not in unavailable_names
        ]
        if not any(str(tool.get("name") or "") == FALLBACK_TOOL_NAME for tool in row_tools):
            continue
        for request in scenario.get("requests", []):
            _append_holdout_row(
                rows,
                seen_users,
                used_users,
                row_tools,
                FALLBACK_TOOL_NAME,
                {},
                str(request),
            )

    return rows


def _validate_prediction(
    payload: Any,
    tool_by_name: dict[str, dict[str, Any]],
) -> tuple[bool, str | None]:
    if not isinstance(payload, dict) or set(payload) != {"tool_calls"}:
        return False, "invalid_shape"

    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        return False, "invalid_shape"

    tool_call = tool_calls[0]
    if not isinstance(tool_call, dict) or set(tool_call) - {"name", "arguments"}:
        return False, "invalid_shape"

    tool_name = tool_call.get("name")
    if not isinstance(tool_name, str) or tool_name not in tool_by_name:
        return False, "unknown_tool"

    arguments = tool_call.get("arguments", {})
    if not isinstance(arguments, dict):
        return False, "invalid_shape"
    if not _schema_ok(arguments, tool_by_name[tool_name]):
        return False, "schema_error"

    return True, None


def evaluate_holdout(
    records: list[dict[str, Any]],
    model_path: Path,
    tokenizer_path: Path,
) -> dict[str, Any]:
    rows = build_unique_holdout_rows(records)
    if not rows:
        return {
            "mode": "unique_holdout",
            "eval_total": 0,
            "eval_valid": 0,
            "eval_exact": 0,
            "eval_positive_total": 0,
            "eval_positive_exact": 0,
            "eval_fallback_total": 0,
            "eval_fallback_exact": 0,
            "invalid_json": 0,
            "invalid_shape": 0,
            "unknown_tool": 0,
            "schema_error": 0,
        }

    runtime = ModelRuntime(model_path, tokenizer_path)
    tool_by_name = {
        str(tool.get("name") or ""): tool
        for tool in rows[0]["tools"]
        if str(tool.get("name") or "")
    }

    summary = {
        "mode": "unique_holdout",
        "eval_total": len(rows),
        "eval_valid": 0,
        "eval_exact": 0,
        "eval_positive_total": 0,
        "eval_positive_exact": 0,
        "eval_fallback_total": 0,
        "eval_fallback_exact": 0,
        "invalid_json": 0,
        "invalid_shape": 0,
        "unknown_tool": 0,
        "schema_error": 0,
    }

    for row in rows:
        expected_tool_name = row["assistant"]["tool_calls"][0]["name"]
        expected_text = serialize_assistant_payload(row["assistant"])
        tool_by_name = {
            str(tool.get("name") or ""): tool
            for tool in row["tools"]
            if str(tool.get("name") or "")
        }
        if expected_tool_name == FALLBACK_TOOL_NAME:
            summary["eval_fallback_total"] += 1
        else:
            summary["eval_positive_total"] += 1

        raw_output = runtime.generate({"tools": row["tools"], "user": row["user"]})
        try:
            parsed_output = json.loads(raw_output)
        except json.JSONDecodeError:
            summary["invalid_json"] += 1
            continue

        valid, error = _validate_prediction(parsed_output, tool_by_name)
        if not valid:
            summary[error or "invalid_shape"] += 1
            continue

        summary["eval_valid"] += 1
        serialized_prediction = serialize_assistant_payload(parsed_output)
        if serialized_prediction != expected_text:
            continue

        summary["eval_exact"] += 1
        if expected_tool_name == FALLBACK_TOOL_NAME:
            summary["eval_fallback_exact"] += 1
        else:
            summary["eval_positive_exact"] += 1

    return summary
