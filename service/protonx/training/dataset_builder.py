import json
import hashlib
from pathlib import Path
from typing import Any

from protonx.contracts import build_fallback_payload
from protonx.contracts import with_compact_fallback_tool
from protonx.model_contract import compact_tool_from_definition
from protonx.model_contract import compact_tool_from_record
from protonx.schemas import ToolDefinition
from protonx.schemas import JsonSchema


DEFAULT_MIXER_SEED_PATH = Path(__file__).with_name("bootstrap_dataset_mixer_for_tools.json")


def _enum_output_value(raw_value: Any) -> str:
    value = str(raw_value)
    enum_value, separator, _description = value.partition(":")
    if separator and enum_value.strip():
        return enum_value.strip()
    return value


def _enum_output_values(enum_values: Any) -> set[str]:
    if not isinstance(enum_values, list):
        return set()
    return {_enum_output_value(value) for value in enum_values}


def _default_arguments(tool: ToolDefinition) -> dict:
    arguments: dict[str, str] = {}
    for field_name in tool.arguments_schema.required:
        property_schema = tool.arguments_schema.properties.get(field_name, {})
        enum_values = property_schema.get("enum")
        if enum_values:
            arguments[field_name] = _enum_output_value(enum_values[0])
            continue
        arguments[field_name] = field_name.replace("_", " ")
    return arguments


def _has_cyrillic(text: str) -> bool:
    return any(char.lower() == "ё" or "а" <= char.lower() <= "я" for char in text)


def _load_mixer_seed(seed_path: Path = DEFAULT_MIXER_SEED_PATH) -> dict[str, Any]:
    if not seed_path.exists():
        return {}
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Dataset mixer seed must be a JSON object.")
    return payload


def _language_key(text: str) -> str:
    return "ru" if _has_cyrillic(text) else "en"


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value).strip().split())
        if not normalized:
            continue
        key = normalized
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _target_languages(seed: dict[str, Any]) -> set[str]:
    raw_languages = seed.get("languages")
    if not isinstance(raw_languages, list):
        return {"en", "ru"}
    languages = {str(language).strip().lower() for language in raw_languages}
    return {language for language in languages if language in {"en", "ru"}} or {"en", "ru"}


def _is_allowed_language_text(text: str, languages: set[str]) -> bool:
    if languages == {"en", "ru"}:
        return True
    language = _language_key(text)
    return language in languages


def _dedupe_compact_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in tools:
        name = str(tool.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(tool)
    return deduped


def _dedupe_tool_definitions(tools: list[ToolDefinition]) -> list[ToolDefinition]:
    deduped: list[ToolDefinition] = []
    seen: set[str] = set()
    for tool in tools:
        if not tool.name or tool.name in seen:
            continue
        seen.add(tool.name)
        deduped.append(tool)
    return deduped


def _seed_training_tools(seed: dict[str, Any]) -> list[ToolDefinition]:
    raw_tools = seed.get("training_tools") or []
    if not isinstance(raw_tools, list):
        return []

    tools: list[ToolDefinition] = []
    for raw_tool in raw_tools:
        if not isinstance(raw_tool, dict) or not raw_tool.get("name"):
            continue
        arguments_schema = raw_tool.get("arguments_schema")
        if not isinstance(arguments_schema, dict):
            arguments_schema = {"type": "object", "properties": {}, "required": []}
        tools.append(
            ToolDefinition(
                name=str(raw_tool["name"]),
                description=str(raw_tool.get("description") or raw_tool["name"]),
                tags=[str(tag) for tag in raw_tool.get("tags") or []],
                arguments_schema=JsonSchema.model_validate(arguments_schema),
            )
        )
    return _dedupe_tool_definitions(tools)


def _effective_training_tools(
    tools: list[ToolDefinition],
    seed: dict[str, Any],
    target_rows: int | None,
) -> list[ToolDefinition]:
    if target_rows is not None and target_rows < 1000:
        return _dedupe_tool_definitions(tools)
    return _dedupe_tool_definitions([*tools, *_seed_training_tools(seed)])


def _dedupe_rows_by_user(rows: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        user_text = str(row.get("user") or "")
        key = " ".join(user_text.strip().split())
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _append_punctuation(text: str, punctuation: str) -> str:
    stripped = text.strip()
    if not punctuation or stripped.endswith(("?", "!", ".", ",", ";", ":", "…")):
        return stripped
    return f"{stripped}{punctuation}"


def _apply_case_variant(text: str, case_variant: str) -> str:
    if case_variant == "capitalize" and text:
        return f"{text[0].upper()}{text[1:]}"
    if case_variant == "lower":
        return text.lower()
    if case_variant == "upper":
        return text.upper()
    return text


def _render_request_variants(
    phrase: str,
    templates: list[str],
    punctuation_values: list[str],
    case_variants: list[str],
) -> list[str]:
    rendered: list[str] = []
    for template in templates:
        base = template.format(phrase=phrase).strip()
        for punctuation in punctuation_values:
            punctuated = _append_punctuation(base, punctuation)
            for case_variant in case_variants:
                rendered.append(_apply_case_variant(punctuated, case_variant))
    return _dedupe_texts(rendered)


def _seed_tool_phrases(tool: ToolDefinition, seed: dict[str, Any]) -> dict[str, list[str]]:
    tool_seed = (seed.get("tools") or {}).get(tool.name) or {}
    phrases: dict[str, list[str]] = {"en": [], "ru": []}
    for language in ("en", "ru"):
        raw_phrases = tool_seed.get(language) or []
        if isinstance(raw_phrases, list):
            phrases[language].extend(str(phrase) for phrase in raw_phrases)

    for tag in tool.tags:
        phrases[_language_key(tag)].append(tag)
    phrases["en"].append(tool.name.replace("_", " "))

    return {
        language: _dedupe_texts(language_phrases)
        for language, language_phrases in phrases.items()
    }


def _mixer_user_requests(tool: ToolDefinition, seed: dict[str, Any]) -> list[str]:
    templates_by_language = seed.get("templates") or {}
    punctuation_values = seed.get("punctuation") or ["", "?"]
    case_variants = seed.get("case_variants") or ["as_is"]
    languages = _target_languages(seed)
    if not isinstance(punctuation_values, list):
        punctuation_values = [""]
    if not isinstance(case_variants, list):
        case_variants = ["as_is"]

    requests: list[str] = _mixer_explicit_requests(tool, seed)
    phrases_by_language = _seed_tool_phrases(tool, seed)
    for language, phrases in phrases_by_language.items():
        if language not in languages:
            continue
        templates = templates_by_language.get(language) or ["{phrase}"]
        if not isinstance(templates, list):
            templates = ["{phrase}"]
        for phrase in phrases:
            requests.extend(
                _render_request_variants(
                    phrase,
                    [str(template) for template in templates],
                    [str(value) for value in punctuation_values],
                    [str(value) for value in case_variants],
                )
            )

    requests.extend(_tool_specific_requests(tool, seed))
    return _expand_ru_requests(_dedupe_texts(requests), seed)


def _mixer_explicit_requests(tool: ToolDefinition, seed: dict[str, Any]) -> list[str]:
    tool_seed = (seed.get("tools") or {}).get(tool.name) or {}
    raw_requests = tool_seed.get("requests") or []
    if not isinstance(raw_requests, list):
        return []

    punctuation_values = seed.get("punctuation") or ["", "?"]
    case_variants = seed.get("case_variants") or ["as_is"]
    languages = _target_languages(seed)
    requests: list[str] = []
    for request in raw_requests:
        if not _is_allowed_language_text(str(request), languages):
            continue
        requests.extend(
            _render_request_variants(
                str(request),
                ["{phrase}"],
                [str(value) for value in punctuation_values],
                [str(value) for value in case_variants],
            )
        )
    return _dedupe_texts(requests)


def _pinned_user_requests(tool: ToolDefinition, seed: dict[str, Any]) -> list[str]:
    languages = _target_languages(seed)
    pinned = [
        *tool.tags,
        *_tool_specific_requests(tool, seed),
        *_mixer_explicit_requests(tool, seed),
    ]
    return _dedupe_texts(
        [
            str(request)
            for request in pinned
            if _is_allowed_language_text(str(request), languages)
        ]
    )


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


def _tool_specific_requests(tool: ToolDefinition, seed: dict[str, Any] | None = None) -> list[str]:
    custom_requests: dict[str, list[str]] = {
        "list_downloads": [
            "show me downloads",
            "check downloads",
            "list downloads",
            "open downloads folder",
            "what is in downloads",
            "show my downloaded files",
            "покажи загрузки",
            "проверь загрузки",
            "выведи загрузки",
            "покажи скачанные файлы",
            "что в загрузках",
            "открой папку загрузок",
            "список загрузок",
        ],
        "get_node_version": [
            "версия ноды",
            "какая версия ноды",
            "какая нода установлена",
            "покажи версию ноды",
            "проверь ноду",
            "какая нода",
        ],
        "get_python_version": [
            "покажи версию питона",
            "какая версия питона",
            "какой питон установлен",
            "проверь питон",
            "покажи интерпретатор питона",
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
            "show disk space",
            "check disk space",
            "disk space",
            "free disk space",
            "how much free space is left",
            "disk usage",
            "покажи место на диске",
            "проверь диск",
            "размер диска",
            "сколько свободного места",
            "свободное место на диске",
        ],
    }
    requests = list(custom_requests.get(tool.name, []))
    if seed is None:
        return requests
    languages = _target_languages(seed)
    return [request for request in requests if _is_allowed_language_text(request, languages)]


def _expand_ru_requests(requests: list[str], seed: dict[str, Any]) -> list[str]:
    if "ru" not in _target_languages(seed):
        return requests

    wrappers = seed.get("ru_request_wrappers") or ["{request}"]
    if not isinstance(wrappers, list):
        wrappers = ["{request}"]

    expanded: list[str] = []
    for request in requests:
        if not _has_cyrillic(request):
            continue
        for wrapper in wrappers:
            rendered = str(wrapper).format(request=request).strip()
            if rendered:
                expanded.append(rendered)
    return _dedupe_texts(expanded)


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


def _seed_fallback_requests(seed: dict[str, Any]) -> list[str]:
    fallback_seed = seed.get("fallback") or {}
    punctuation_values = seed.get("punctuation") or ["", "?"]
    case_variants = seed.get("case_variants") or ["as_is"]
    languages = _target_languages(seed)
    raw_requests: list[str] = []
    requests: list[str] = []
    for language in ("en", "ru"):
        if language not in languages:
            continue
        phrases = fallback_seed.get(language) or []
        if not isinstance(phrases, list):
            continue
        for phrase in phrases:
            raw_requests.append(str(phrase))
            requests.extend(
                _render_request_variants(
                    str(phrase),
                    ["{phrase}"],
                    [str(value) for value in punctuation_values],
                    [str(value) for value in case_variants],
                )
            )
    return _expand_ru_requests(_dedupe_texts([*raw_requests, *requests]), seed)


def _seed_unavailable_intent_examples(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> list[dict]:
    seed = seed or {}
    raw_intents = seed.get("unavailable_intents") or []
    if not isinstance(raw_intents, list):
        return []

    punctuation_values = seed.get("punctuation") or ["", "?"]
    case_variants = seed.get("case_variants") or ["as_is"]
    if not isinstance(punctuation_values, list):
        punctuation_values = [""]
    if not isinstance(case_variants, list):
        case_variants = ["as_is"]

    tool_payloads = [compact_tool_from_definition(tool) for tool in tools]
    rows: list[dict] = []
    for raw_intent in raw_intents:
        if not isinstance(raw_intent, dict):
            continue
        unavailable_names = {
            str(name)
            for name in raw_intent.get("tool_names") or []
            if str(name).strip()
        }
        if not unavailable_names:
            continue
        available_payloads = [
            tool_payload
            for tool_payload in tool_payloads
            if str(tool_payload.get("name") or "") not in unavailable_names
        ]
        if not available_payloads:
            continue

        raw_requests = raw_intent.get("requests") or []
        if not isinstance(raw_requests, list):
            continue
        requests: list[str] = []
        for request in raw_requests:
            if not _is_allowed_language_text(str(request), _target_languages(seed)):
                continue
            requests.extend(
                _render_request_variants(
                    str(request),
                    ["{phrase}"],
                    [str(value) for value in punctuation_values],
                    [str(value) for value in case_variants],
                )
            )
        requests = _expand_ru_requests(_dedupe_texts(requests), seed)
        for request in requests:
            rows.append(_fallback_row(available_payloads, request, seed))
    return rows


def _seed_decoy_tools(seed: dict[str, Any]) -> list[dict[str, Any]]:
    raw_decoys = seed.get("decoy_tools") or []
    if not isinstance(raw_decoys, list):
        return []

    decoys: list[dict[str, Any]] = []
    for raw_tool in raw_decoys:
        if not isinstance(raw_tool, dict) or not raw_tool.get("name"):
            continue
        compact_tool = compact_tool_from_record(raw_tool)
        if compact_tool.get("name"):
            decoys.append(compact_tool)
    return _dedupe_compact_tools(decoys)


def _compact_decoy_tools(seed: dict[str, Any], user_text: str) -> list[dict[str, Any]]:
    decoys = _seed_decoy_tools(seed)
    if not decoys:
        return []

    raw_count = seed.get("decoy_tools_per_row", len(decoys))
    max_decoy_count = raw_count if isinstance(raw_count, int) else len(decoys)
    if max_decoy_count <= 0:
        return []
    decoy_count = int(
        hashlib.sha1(f"{user_text}|decoy-count".encode("utf-8")).hexdigest(),
        16,
    ) % (min(max_decoy_count, len(decoys)) + 1)
    if decoy_count <= 0:
        return []

    selected = sorted(
        decoys,
        key=lambda tool: hashlib.sha1(
            f"{user_text}|{tool['name']}".encode("utf-8")
        ).hexdigest(),
    )[:decoy_count]
    return [
        compact_tool_from_record(tool, variation_key=f"{user_text}|decoy|{index}")
        for index, tool in enumerate(selected)
    ]


def _available_tool_count(seed: dict[str, Any], total_count: int, user_text: str) -> int:
    raw_range = seed.get("available_tools_per_row")
    if (
        not isinstance(raw_range, list)
        or len(raw_range) != 2
        or not all(isinstance(value, int) for value in raw_range)
    ):
        return total_count

    minimum = max(1, min(raw_range))
    maximum = max(minimum, max(raw_range))
    maximum = min(maximum, total_count)
    if minimum >= maximum:
        return maximum

    span = maximum - minimum + 1
    offset = int(hashlib.sha1(f"{user_text}|tool-count".encode("utf-8")).hexdigest(), 16) % span
    return minimum + offset


def _select_available_tool_definitions(
    primary: ToolDefinition,
    tools: list[ToolDefinition],
    user_text: str,
    seed: dict[str, Any],
) -> list[ToolDefinition]:
    deduped_tools = _dedupe_tool_definitions(tools)
    count = _available_tool_count(seed, len(deduped_tools), user_text)
    others = [tool for tool in deduped_tools if tool.name != primary.name]
    selected_others = sorted(
        others,
        key=lambda tool: hashlib.sha1(
            f"{user_text}|{primary.name}|{tool.name}".encode("utf-8")
        ).hexdigest(),
    )[: max(0, count - 1)]
    selected = [primary, *selected_others]
    return sorted(
        selected,
        key=lambda tool: hashlib.sha1(
            f"{user_text}|order|{tool.name}".encode("utf-8")
        ).hexdigest(),
    )


def _select_compact_tool_payloads(
    tool_payloads: list[dict[str, Any]],
    user_text: str,
    seed: dict[str, Any],
) -> list[dict[str, Any]]:
    deduped_payloads = _dedupe_compact_tools(tool_payloads)
    count = _available_tool_count(seed, len(deduped_payloads), user_text)
    return sorted(
        deduped_payloads,
        key=lambda tool: hashlib.sha1(
            f"{user_text}|fallback|{tool['name']}".encode("utf-8")
        ).hexdigest(),
    )[:count]


def _compact_available_tools(
    tools: list[ToolDefinition], user_text: str, seed: dict[str, Any] | None = None
) -> list[dict]:
    seed = seed or {}
    return with_compact_fallback_tool(
        [
            compact_tool_from_definition(tool, variation_key=f"{user_text}|{index}")
            for index, tool in enumerate(tools)
        ]
        + _compact_decoy_tools(seed, user_text),
        variation_key=user_text,
    )


def _tool_call_example(
    primary: ToolDefinition,
    available_tools: list[ToolDefinition],
    user_text: str,
    seed: dict[str, Any] | None = None,
    arguments: dict[str, str] | None = None,
) -> dict:
    row_tools = _select_available_tool_definitions(
        primary,
        available_tools,
        user_text,
        seed or {},
    )
    return {
        "tools": _compact_available_tools(row_tools, user_text, seed),
        "user": user_text,
        "assistant": {
            "tool_calls": [
                {"name": primary.name, "arguments": arguments or _default_arguments(primary)}
            ]
        },
    }


def _fallback_row(
    tool_payloads: list[dict], user_text: str, seed: dict[str, Any] | None = None
) -> dict:
    seed = seed or {}
    selected_payloads = _select_compact_tool_payloads(tool_payloads, user_text, seed)
    return {
        "tools": with_compact_fallback_tool(
            [
                compact_tool_from_record(tool_payload, variation_key=f"{user_text}|{index}")
                for index, tool_payload in enumerate(selected_payloads)
            ]
            + _compact_decoy_tools(seed, user_text),
            variation_key=user_text,
        ),
        "user": user_text,
        "assistant": build_fallback_payload(),
    }


def _unsupported_fallback_example(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools],
        "расскажи шутку",
        seed,
    )


def _fallback_example(tools: list[ToolDefinition], seed: dict[str, Any] | None = None) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools],
        "как дела",
        seed,
    )


def _fallback_example_ru(tools: list[ToolDefinition], seed: dict[str, Any] | None = None) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools],
        "как дела",
        seed,
    )


def _ambiguous_fallback_example(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> dict:
    return _fallback_row(
        [compact_tool_from_definition(tool) for tool in tools],
        "измени это",
        seed,
    )


def _chatty_fallback_examples(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> list[dict]:
    tool_payloads = [compact_tool_from_definition(tool) for tool in tools]
    return [
        _fallback_row(tool_payloads, "привет", seed),
        _fallback_row(tool_payloads, "доброе утро", seed),
        _fallback_row(tool_payloads, "поболтай со мной", seed),
    ]


def _hard_negative_examples(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> list[dict]:
    tool_map = {tool.name: tool for tool in tools}
    rows: list[dict] = []

    if {"get_node_version", "get_python_version"}.issubset(tool_map):
        available_tools = [
            compact_tool_from_definition(tool)
            for tool in tools
        ]
        rows.append(_fallback_row(available_tools, "покажи версию", seed))
        rows.append(_fallback_row(available_tools, "какая версия", seed))

    if {"light", "window", "speaker"}.issubset(tool_map):
        available_tools = [
            compact_tool_from_definition(tool)
            for tool in tools
        ]
        rows.append(_fallback_row(available_tools, "сделай потише", seed))

    if {"window", "file_search"}.issubset(tool_map):
        available_tools = [
            compact_tool_from_definition(tool)
            for tool in tools
        ]
        rows.append(_fallback_row(available_tools, "открой", seed))

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


def _arguments_match_schema(tool: ToolDefinition, arguments: dict[str, str]) -> bool:
    if not _supports_probe_arguments(tool, arguments):
        return False

    for field_name, value in arguments.items():
        property_schema = tool.arguments_schema.properties.get(field_name, {})
        enum_values = property_schema.get("enum")
        if enum_values is not None and value not in _enum_output_values(enum_values):
            return False
    return True


def _seed_argument_examples(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> list[dict]:
    seed = seed or {}
    raw_examples_by_tool = seed.get("argument_examples") or {}
    if not isinstance(raw_examples_by_tool, dict):
        return []

    punctuation_values = seed.get("punctuation") or ["", "?"]
    case_variants = seed.get("case_variants") or ["as_is"]
    if not isinstance(punctuation_values, list):
        punctuation_values = [""]
    if not isinstance(case_variants, list):
        case_variants = ["as_is"]

    rows: list[dict] = []
    for tool in tools:
        raw_examples = raw_examples_by_tool.get(tool.name) or []
        if not isinstance(raw_examples, list):
            continue
        for raw_example in raw_examples:
            if not isinstance(raw_example, dict):
                continue
            raw_arguments = raw_example.get("arguments") or {}
            if not isinstance(raw_arguments, dict):
                continue
            arguments = {
                str(field_name): str(value)
                for field_name, value in raw_arguments.items()
                if str(field_name).strip()
            }
            if not _arguments_match_schema(tool, arguments):
                continue

            raw_requests = raw_example.get("requests") or []
            if not isinstance(raw_requests, list):
                continue
            requests: list[str] = []
            for request in raw_requests:
                request_text = str(request)
                if not _is_allowed_language_text(request_text, _target_languages(seed)):
                    continue
                requests.extend(
                    _render_request_variants(
                        request_text,
                        ["{phrase}"],
                        [str(value) for value in punctuation_values],
                        [str(value) for value in case_variants],
                    )
                )
            requests = _expand_ru_requests(_dedupe_texts(requests), seed)
            for user_text in requests:
                rows.append(
                    _tool_call_example(
                        tool,
                        tools,
                        user_text,
                        seed,
                        arguments=arguments,
                    )
                )
    return rows


def _argument_probe_examples(
    tools: list[ToolDefinition], seed: dict[str, Any] | None = None
) -> list[dict]:
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
                    *_compact_available_tools(tools, "найди package.json", seed)
                ],
                "user": "найди package.json",
                "assistant": {
                    "tool_calls": [
                        {"name": "search_files", "arguments": {"query": "package.json"}}
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


def _sample_rows(rows: list[dict], target_rows: int | None) -> list[dict]:
    if target_rows is None or target_rows <= 0 or len(rows) <= target_rows:
        return rows

    preserve_head = min(len(rows), target_rows, 120)
    pinned_rows = rows[:preserve_head]
    remaining_rows = rows[preserve_head:]
    remaining_target = target_rows - preserve_head
    if remaining_target <= 0 or not remaining_rows:
        return pinned_rows[:target_rows]

    sampled: list[dict] = list(pinned_rows)
    for index in range(remaining_target):
        source_index = (index * len(remaining_rows)) // remaining_target
        sampled.append(remaining_rows[source_index])
    return sampled


def _stable_row_shuffle(rows: list[dict], salt: str) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: hashlib.sha1(
            f"{salt}|{json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}".encode(
                "utf-8"
            )
        ).hexdigest(),
    )


def _sample_balanced_rows(
    tool_rows: list[dict],
    special_rows: list[dict],
    target_rows: int | None,
    fallback_ratio: float,
) -> list[dict]:
    if target_rows is None or target_rows <= 0:
        return _stable_row_shuffle(_interleave_rows(tool_rows, special_rows), "all-rows")
    tool_rows_by_name: dict[str, list[dict]] = {}
    class_order: list[str] = []
    for row in tool_rows:
        tool_name = str(row["assistant"]["tool_calls"][0]["name"])
        if tool_name not in tool_rows_by_name:
            tool_rows_by_name[tool_name] = []
            class_order.append(tool_name)
        tool_rows_by_name[tool_name].append(row)

    fallback_target = 0
    if special_rows:
        fallback_target = min(
            len(special_rows),
            max(1, round(target_rows * fallback_ratio)),
        )

    tool_target = target_rows - fallback_target
    sampled_by_name: list[list[dict]] = []
    if class_order:
        base_target = tool_target // len(class_order)
        remainder = tool_target % len(class_order)
        for index, tool_name in enumerate(class_order):
            class_target = base_target + (1 if index < remainder else 0)
            sampled_by_name.append(_sample_rows(tool_rows_by_name[tool_name], class_target))
    if fallback_target:
        sampled_by_name.append(_sample_rows(special_rows, fallback_target))

    if not sampled_by_name:
        return []

    balanced_rows: list[dict] = []
    max_class_rows = max(len(rows) for rows in sampled_by_name)
    for row_index in range(max_class_rows):
        for rows in sampled_by_name:
            if row_index < len(rows):
                balanced_rows.append(rows[row_index])
    return _stable_row_shuffle(balanced_rows[:target_rows], "balanced-rows")


def build_examples(tools: list[ToolDefinition], target_rows: int | None = None) -> list[dict]:
    tool_rows: list[dict] = []
    special_rows: list[dict] = []
    if not tools:
        return []

    seed = _load_mixer_seed()
    tools = _effective_training_tools(tools, seed, target_rows)
    if target_rows is None:
        raw_target_rows = seed.get("target_rows")
        if isinstance(raw_target_rows, int):
            target_rows = raw_target_rows
    fallback_ratio = seed.get("fallback_ratio", 0.2)
    if not isinstance(fallback_ratio, (int, float)):
        fallback_ratio = 0.2

    seed_argument_rows = _seed_argument_examples(tools, seed)
    argument_tool_names = {
        str(row["assistant"]["tool_calls"][0]["name"])
        for row in seed_argument_rows
        if row.get("assistant", {}).get("tool_calls")
    }
    tool_rows.extend(seed_argument_rows)
    pinned_users = {row["user"] for row in tool_rows}
    for primary in tools:
        if primary.name in argument_tool_names:
            continue
        for user_text in _pinned_user_requests(primary, seed):
            if user_text in pinned_users:
                continue
            tool_rows.append(_tool_call_example(primary, tools, user_text, seed))
            pinned_users.add(user_text)

    for primary in tools:
        if primary.name in argument_tool_names:
            continue
        for user_text in _mixer_user_requests(primary, seed):
            if user_text in pinned_users:
                continue
            tool_rows.append(_tool_call_example(primary, tools, user_text, seed))
            pinned_users.add(user_text)

    if not tool_rows:
        for primary in tools:
            for user_text in _build_user_requests(primary):
                tool_rows.append(_tool_call_example(primary, tools, user_text, seed))

    if tools:
        special_rows.append(_fallback_example(tools, seed))
        special_rows.append(_fallback_example_ru(tools, seed))
        special_rows.append(_unsupported_fallback_example(tools, seed))
        special_rows.append(_ambiguous_fallback_example(tools, seed))
        special_rows.extend(_chatty_fallback_examples(tools, seed))
        special_rows.extend(_hard_negative_examples(tools, seed))
        fallback_payloads = [compact_tool_from_definition(tool) for tool in tools]
        for user_text in _seed_fallback_requests(seed):
            special_rows.append(_fallback_row(fallback_payloads, user_text, seed))
        special_rows.extend(_seed_unavailable_intent_examples(tools, seed))
    tool_rows.extend(_argument_probe_examples(tools, seed))
    tool_rows = _dedupe_rows_by_user(tool_rows)
    special_rows = _dedupe_rows_by_user(special_rows)
    return _sample_balanced_rows(tool_rows, special_rows, target_rows, float(fallback_ratio))


def build_synthetic_dataset(
    tools: list[ToolDefinition], output_path: Path, target_rows: int | None = None
) -> int:
    rows = build_examples(tools, target_rows=target_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows_written += 1
    return rows_written
