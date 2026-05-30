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


def enum_output_value(raw_value: Any) -> str:
    value, _description = split_legacy_enum_label(str(raw_value))
    return value


def enum_output_values(enum_values: Any) -> set[str]:
    return {value for value, _description in enum_entries(enum_values)}


def enum_first_output_value(enum_values: Any) -> str | None:
    entries = enum_entries(enum_values)
    return entries[0][0] if entries else None


def enum_is_supported(enum_values: Any) -> bool:
    if enum_values is None:
        return True
    if isinstance(enum_values, dict):
        return all(isinstance(key, str) and isinstance(value, str) for key, value in enum_values.items())
    if isinstance(enum_values, list):
        return all(isinstance(value, str) for value in enum_values)
    return False
