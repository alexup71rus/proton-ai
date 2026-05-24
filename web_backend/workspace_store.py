from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from web_backend.config import get_workspace_settings_file
from web_backend.schemas import WorkspaceSettingsPayload, WorkspaceSettingsResponse


def _default_settings() -> WorkspaceSettingsPayload:
    return WorkspaceSettingsPayload()


def _validate_settings(payload: dict[str, Any]) -> WorkspaceSettingsPayload:
    try:
        return WorkspaceSettingsPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid workspace settings: {exc}") from exc


def _read_settings_file() -> WorkspaceSettingsPayload:
    path = get_workspace_settings_file()
    if not path.exists():
        return _default_settings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Workspace settings file is not valid JSON: {path}") from exc

    return _validate_settings(raw)


def _write_settings_file(settings: WorkspaceSettingsPayload) -> WorkspaceSettingsResponse:
    path = get_workspace_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return WorkspaceSettingsResponse(**settings.model_dump(), storage_path=str(path))


def load_workspace_settings() -> WorkspaceSettingsResponse:
    settings = _read_settings_file()
    return _write_settings_file(settings)


def save_workspace_settings(payload: WorkspaceSettingsPayload | dict[str, Any]) -> WorkspaceSettingsResponse:
    settings = payload if isinstance(payload, WorkspaceSettingsPayload) else _validate_settings(payload)
    return _write_settings_file(settings)


def update_workspace_settings(updates: dict[str, Any]) -> WorkspaceSettingsResponse:
    current = _read_settings_file().model_dump()
    merged = current.copy()
    for section, values in updates.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    return save_workspace_settings(merged)