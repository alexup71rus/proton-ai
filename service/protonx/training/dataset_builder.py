import json
from itertools import permutations
from pathlib import Path

from protonx.contracts import build_fallback_payload
from protonx.contracts import with_compact_fallback_tool
from protonx.model_contract import compact_tool_from_definition
from protonx.model_contract import compact_tool_from_record
from protonx.schemas import ToolDefinition


def _default_arguments(tool: ToolDefinition) -> dict:
    arguments: dict[str, str] = {}
    for field_name in tool.arguments_schema.required:
        property_schema = tool.arguments_schema.properties.get(field_name, {})
        enum_values = property_schema.get("enum")
        if enum_values:
            arguments[field_name] = str(enum_values[0])
            continue
        arguments[field_name] = field_name.replace("_", " ")
    return arguments


def _has_cyrillic(text: str) -> bool:
    return any(char.lower() == "ё" or "а" <= char.lower() <= "я" for char in text)


def _tool_aliases(tool: ToolDefinition) -> list[str]:
    unique_aliases: list[str] = []
    seen: set[str] = set()
    for raw_alias in [*tool.tags, tool.name.replace("_", " ")]:
        alias = raw_alias.strip()
        if not alias:
            continue
        normalized = alias.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_aliases.append(alias)

    if not unique_aliases:
        return [tool.name.replace("_", " ")]

    selected_aliases = [unique_aliases[0]]
    first_is_cyrillic = _has_cyrillic(unique_aliases[0])
    for alias in unique_aliases[1:]:
        if _has_cyrillic(alias) != first_is_cyrillic:
            selected_aliases.append(alias)
            break
    for alias in unique_aliases[1:]:
        if alias in selected_aliases:
            continue
        selected_aliases.append(alias)
        if len(selected_aliases) >= 3:
            break
    return selected_aliases[:3]


def _tool_specific_requests(tool: ToolDefinition) -> list[str]:
    custom_requests: dict[str, list[str]] = {
        "list_downloads": [
            "show me downloads",
            "check downloads",
            "list downloads",
            "open downloads folder",
            "what is in downloads",
            "show my downloaded files",
            "покажи загрузки",
            "что в загрузках",
            "открой папку загрузок",
            "список загрузок",
        ],
        "get_node_version": [
            "show me node version",
            "check node",
            "node version",
            "what is the node version",
            "show node js version",
            "покажи версию node",
            "какая версия node",
            "версия node js",
        ],
        "get_python_version": [
            "show me python version",
            "check python",
            "python version",
            "what is the python version",
            "show interpreter version",
            "покажи версию python",
            "какая версия python",
            "какой python установлен",
        ],
        "get_current_time": [
            "show me current time",
            "show me time",
            "what time is it",
            "what time is it now",
            "current time",
            "покажи время",
            "который час",
            "текущее время",
        ],
        "get_disk_usage": [
            "show me disk usage",
            "check disk",
            "show free space",
            "how much free space is left",
            "disk usage",
            "покажи место на диске",
            "сколько свободного места",
            "свободное место на диске",
        ],
    }
    return list(custom_requests.get(tool.name, []))


def _build_user_requests(tool: ToolDefinition) -> list[str]:
    arguments = _default_arguments(tool)
    user_requests: list[str] = list(_tool_specific_requests(tool))
    for alias in _tool_aliases(tool):
        is_cyrillic = _has_cyrillic(alias)
        if not arguments:
            if is_cyrillic:
                user_requests.extend(
                    [
                        f"покажи {alias}",
                        f"проверь {alias}",
                        f"выведи {alias}",
                        f"отобрази {alias}",
                    ]
                )
            else:
                user_requests.extend(
                    [
                        f"show me {alias}",
                        f"check {alias}",
                        f"get {alias}",
                        f"display {alias}",
                    ]
                )
            continue

        if len(arguments) == 1 and next(iter(arguments)) == "state":
            state_value = next(iter(arguments.values()))
            if is_cyrillic:
                user_requests.extend(
                    [
                        f"поставь {alias} на {state_value}",
                        f"измени {alias} на {state_value}",
                        f"переключи {alias} на {state_value}",
                        f"сделай {alias} {state_value}",
                    ]
                )
            else:
                user_requests.extend(
                    [
                        f"set {alias} to {state_value}",
                        f"change {alias} to {state_value}",
                        f"switch {alias} to {state_value}",
                        f"make {alias} {state_value}",
                    ]
                )
            continue

        argument_phrase = ", ".join(
            f"{field_name} {value}" for field_name, value in arguments.items()
        )
        if is_cyrillic:
            user_requests.extend(
                [
                    f"используй {alias} с {argument_phrase}",
                    f"запусти {alias} с {argument_phrase}",
                    f"вызови {alias} с {argument_phrase}",
                    f"выполни {alias} с {argument_phrase}",
                ]
            )
        else:
            user_requests.extend(
                [
                    f"use {alias} with {argument_phrase}",
                    f"run {alias} with {argument_phrase}",
                    f"call {alias} with {argument_phrase}",
                    f"execute {alias} with {argument_phrase}",
                ]
            )

    deduped_requests: list[str] = []
    seen_requests: set[str] = set()
    for request in user_requests:
        if request in seen_requests:
            continue
        seen_requests.add(request)
        deduped_requests.append(request)
    return deduped_requests or [f"show me {tool.name.replace('_', ' ')}"]


def _tool_call_example(
    primary: ToolDefinition, alternatives: list[ToolDefinition], user_text: str
) -> dict:
    candidate_tools = [
        compact_tool_from_definition(primary, variation_key=f"{user_text}|0")
    ]
    candidate_tools.extend(
        compact_tool_from_definition(tool, variation_key=f"{user_text}|{index}")
        for index, tool in enumerate(alternatives[:2], start=1)
    )
    if len(candidate_tools) > 1 and primary.name > candidate_tools[1]["name"]:
        candidate_tools[0], candidate_tools[1] = candidate_tools[1], candidate_tools[0]
    return {
        "tools": candidate_tools,
        "user": user_text,
        "assistant": {
            "tool_calls": [
                {"name": primary.name, "arguments": _default_arguments(primary)}
            ]
        },
    }


def _fallback_row(tool_payloads: list[dict], user_text: str) -> dict:
    return {
        "tools": with_compact_fallback_tool(
            [
                compact_tool_from_record(tool_payload, variation_key=f"{user_text}|{index}")
                for index, tool_payload in enumerate(tool_payloads)
            ],
            variation_key=user_text,
        ),
        "user": user_text,
        "assistant": build_fallback_payload(),
    }


def _unsupported_fallback_example(tools: list[ToolDefinition]) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools[:2]],
        "tell me a joke",
    )


def _fallback_example(tools: list[ToolDefinition]) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools[:2]],
        "how are you",
    )


def _fallback_example_ru(tools: list[ToolDefinition]) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools[:2]],
        "как дела",
    )


def _ambiguous_fallback_example(tools: list[ToolDefinition]) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools[:2]],
        "change it",
    )


def _chatty_fallback_examples(tools: list[ToolDefinition]) -> list[dict]:
    tool_payloads = [compact_tool_from_definition(tool) for tool in tools[:2]]
    return [
        _fallback_row(tool_payloads, "hello"),
        _fallback_row(tool_payloads, "hi there"),
        _fallback_row(tool_payloads, "what's up"),
        _fallback_row(tool_payloads, "привет"),
        _fallback_row(tool_payloads, "доброе утро"),
        _fallback_row(tool_payloads, "поболтай со мной"),
    ]


def _hard_negative_examples(tools: list[ToolDefinition]) -> list[dict]:
    tool_map = {tool.name: tool for tool in tools}
    rows: list[dict] = []

    if {"get_node_version", "get_python_version"}.issubset(tool_map):
        candidate_tools = [
            compact_tool_from_definition(tool_map["get_node_version"]),
            compact_tool_from_definition(tool_map["get_python_version"]),
        ]
        rows.append(_fallback_row(candidate_tools, "show me version"))
        rows.append(_fallback_row(candidate_tools, "покажи версию"))

    if {"light", "window", "speaker"}.issubset(tool_map):
        candidate_tools = [
            compact_tool_from_definition(tool_map["light"]),
            compact_tool_from_definition(tool_map["window"]),
            compact_tool_from_definition(tool_map["speaker"]),
        ]
        rows.append(_fallback_row(candidate_tools, "make it quieter"))
        rows.append(_fallback_row(candidate_tools, "сделай потише"))

    if {"window", "file_search"}.issubset(tool_map):
        candidate_tools = [
            compact_tool_from_definition(tool_map["window"]),
            compact_tool_from_definition(tool_map["file_search"]),
        ]
        rows.append(_fallback_row(candidate_tools, "open"))
        rows.append(_fallback_row(candidate_tools, "открой"))

    return rows


def _supports_probe_arguments(tool: ToolDefinition, arguments: dict[str, str]) -> bool:
    provided = set(arguments.keys())
    required = set(tool.arguments_schema.required)
    if not required.issubset(provided):
        return False

    for field_name in provided:
        property_schema = tool.arguments_schema.properties.get(field_name)
        if not isinstance(property_schema, dict):
            return False
        if property_schema.get("type") != "string":
            return False
    return True


def _argument_probe_examples(tools: list[ToolDefinition]) -> list[dict]:
    tool_map = {tool.name: tool for tool in tools}
    rows: list[dict] = []

    search_files_tool = tool_map.get("search_files")
    if search_files_tool and _supports_probe_arguments(
        search_files_tool,
        {"query": "package.json"},
    ):
        rows.append(
            {
                "tools": [
                    compact_tool_from_definition(
                        search_files_tool,
                        variation_key="найди package.json|0",
                    )
                ],
                "user": "найди package.json",
                "assistant": {
                    "tool_calls": [
                        {"name": "search_files", "arguments": {"query": "package.json"}}
                    ]
                },
            }
        )
        rows.append(
            {
                "tools": [
                    compact_tool_from_definition(
                        search_files_tool,
                        variation_key="find README.md|0",
                    )
                ],
                "user": "find README.md",
                "assistant": {
                    "tool_calls": [
                        {"name": "search_files", "arguments": {"query": "README.md"}}
                    ]
                },
            }
        )

    search_web_tool = tool_map.get("search_web")
    if search_web_tool and _supports_probe_arguments(
        search_web_tool,
        {"q": "node js latest version"},
    ):
        rows.append(
            {
                "tools": [
                    compact_tool_from_definition(
                        search_web_tool,
                        variation_key="find node js latest version|0",
                    )
                ],
                "user": "find node js latest version",
                "assistant": {
                    "tool_calls": [
                        {"name": "search_web", "arguments": {"q": "node js latest version"}}
                    ]
                },
            }
        )

    return rows


def _interleave_rows(tool_rows: list[dict], special_rows: list[dict], interval: int = 4) -> list[dict]:
    if not special_rows:
        return tool_rows

    merged_rows: list[dict] = []
    special_index = 0
    for row_index, row in enumerate(tool_rows, start=1):
        merged_rows.append(row)
        if row_index % interval == 0 and special_index < len(special_rows):
            merged_rows.append(special_rows[special_index])
            special_index += 1

    merged_rows.extend(special_rows[special_index:])
    return merged_rows


def build_examples(tools: list[ToolDefinition]) -> list[dict]:
    tool_rows: list[dict] = []
    special_rows: list[dict] = []
    if not tools:
        return []

    if len(tools) == 1:
        primary = tools[0]
        for user_text in _build_user_requests(primary):
            tool_rows.append(_tool_call_example(primary, [], user_text))
    else:
        for primary, secondary in permutations(tools, 2):
            alternatives = [
                secondary,
                *[
                    tool
                    for tool in tools
                    if tool.name not in {primary.name, secondary.name}
                ],
            ]
            for user_text in _build_user_requests(primary):
                tool_rows.append(_tool_call_example(primary, alternatives, user_text))

    if tools:
        special_rows.append(_fallback_example(tools))
        special_rows.append(_fallback_example_ru(tools))
        special_rows.append(_unsupported_fallback_example(tools))
        special_rows.append(_ambiguous_fallback_example(tools))
        special_rows.extend(_chatty_fallback_examples(tools))
        special_rows.extend(_hard_negative_examples(tools))
    special_rows.extend(_argument_probe_examples(tools))
    return _interleave_rows(tool_rows, special_rows)


def build_synthetic_dataset(tools: list[ToolDefinition], output_path: Path) -> int:
    rows = build_examples(tools)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows_written += 1
    return rows_written
