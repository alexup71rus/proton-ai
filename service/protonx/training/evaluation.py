from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.routing.model_runtime import ModelRuntime
from protonx.training.format import serialize_assistant_payload


SPECIAL_HOLDOUT_REQUESTS: dict[str, list[str]] = {
    "list_downloads": [
        "что сейчас лежит в директории загрузок",
    ],
    "get_node_version": [
        "сообщи установленный релиз Node.js на этой машине",
    ],
    "get_python_version": [
        "сообщи версию активного интерпретатора Python",
    ],
    "get_current_time": [
        "сообщи локальные дату и время на этой машине",
    ],
    "get_disk_usage": [
        "сообщи свободное место на домашнем разделе",
    ],
    FALLBACK_TOOL_NAME: [
        "закажи такси до аэропорта",
        "напиши короткое стихотворение о дожде",
    ],
}


def _normalize_user_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _tool_args(tool: dict[str, Any]) -> dict[str, Any]:
    args = tool.get("args")
    return args if isinstance(args, dict) else {}


def _default_arguments(tool: dict[str, Any]) -> dict[str, str]:
    arguments: dict[str, str] = {}
    for field_name, spec in _tool_args(tool).items():
        if isinstance(spec, list) and spec:
            arguments[field_name] = str(spec[0])
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
        if isinstance(spec, list):
            if value not in spec:
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
            normalized_request = _normalize_user_text(request)
            if normalized_request in seen_users or normalized_request in used_users:
                continue
            used_users.add(normalized_request)
            rows.append(
                {
                    "tools": row_tools,
                    "user": request,
                    "assistant": {
                        "tool_calls": [
                            {
                                "name": tool_name,
                                "arguments": expected_arguments,
                            }
                        ]
                    },
                }
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
