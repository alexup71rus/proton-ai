from __future__ import annotations

from typing import Any


def split_legacy_enum_label(value: str) -> tuple[str, str | None]:
    enum_value, separator, enum_description = value.partition(":")
    normalized_value = enum_value.strip()
    normalized_description = enum_description.strip()
    if separator and normalized_value and normalized_description:
        return normalized_value, normalized_description
    return value.strip(), None


def enum_entries(enum_values: Any) -> list[tuple[str, str | None]]:
    if isinstance(enum_values, dict):
        entries: list[tuple[str, str | None]] = []
        for raw_value, raw_description in enum_values.items():
            value = str(raw_value).strip()
            if not value:
                continue
            description = str(raw_description).strip() if raw_description is not None else ""
            entries.append((value, description or None))
        return entries

    if isinstance(enum_values, list):
        return [
            split_legacy_enum_label(str(raw_value))
            for raw_value in enum_values
            if str(raw_value).strip()
        ]

    return []


def enum_output_values(enum_values: Any) -> set[str]:
    return {value for value, _description in enum_entries(enum_values)}


def enum_is_supported(enum_values: Any) -> bool:
    if enum_values is None:
        return True
    if isinstance(enum_values, dict):
        return all(isinstance(key, str) and isinstance(value, str) for key, value in enum_values.items())
    if isinstance(enum_values, list):
        return all(isinstance(value, str) for value in enum_values)
    return False


def normalize_enum_values(enum_values: Any) -> dict[str, str] | None:
    entries = enum_entries(enum_values)
    if not entries:
        return None
    return {value: description or "" for value, description in entries}


def normalize_tool_enum_values(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("arguments_schema")
    if not isinstance(schema, dict):
        return tool
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return tool

    next_tool = dict(tool)
    next_schema = dict(schema)
    next_properties = dict(properties)

    for field_name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        enum_values = property_schema.get("enum")
        normalized_enum = normalize_enum_values(enum_values)
        if normalized_enum is None:
            continue
        next_property_schema = dict(property_schema)
        next_property_schema["enum"] = normalized_enum
        next_properties[field_name] = next_property_schema

    next_schema["properties"] = next_properties
    next_tool["arguments_schema"] = next_schema
    return next_tool
