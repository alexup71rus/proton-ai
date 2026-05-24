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


def _workspace_settings_path():
    return get_workspace_settings_file()


def _read_settings_payload() -> WorkspaceSettingsPayload:
    path = _workspace_settings_path()
    if not path.exists():
        return _default_settings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Workspace settings file is not valid JSON: {path}") from exc

    return _validate_settings(raw)


def _build_settings_response(settings: WorkspaceSettingsPayload) -> WorkspaceSettingsResponse:
    return WorkspaceSettingsResponse(**settings.model_dump(), storage_path=str(_workspace_settings_path()))


def _write_settings_payload(settings: WorkspaceSettingsPayload) -> WorkspaceSettingsResponse:
    path = _workspace_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return _build_settings_response(settings)


def _merge_settings_payload(current: WorkspaceSettingsPayload, updates: dict[str, Any]) -> WorkspaceSettingsPayload:
    merged = current.model_dump()
    for section, values in updates.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    return _validate_settings(merged)


def load_workspace_settings() -> WorkspaceSettingsResponse:
    settings = _read_settings_payload()
    return _write_settings_payload(settings)


def save_workspace_settings(payload: WorkspaceSettingsPayload | dict[str, Any]) -> WorkspaceSettingsResponse:
    settings = payload if isinstance(payload, WorkspaceSettingsPayload) else _validate_settings(payload)
    return _write_settings_payload(settings)


def update_workspace_settings(updates: dict[str, Any]) -> WorkspaceSettingsResponse:
    merged = _merge_settings_payload(_read_settings_payload(), updates)
    return _write_settings_payload(merged)