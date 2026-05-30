from __future__ import annotations

import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = ROOT_DIR / "data" / "train" / "routing"


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return ROOT_DIR / candidate


def _workspace_dataset_dir() -> str | None:
    workspace_path = get_workspace_settings_file()
    if not workspace_path.exists():
        return None
    try:
        raw = json.loads(workspace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    training = raw.get("training")
    if not isinstance(training, dict):
        return None
    dataset_dir = training.get("dataset_dir")
    if not isinstance(dataset_dir, str) or not dataset_dir.strip():
        return None
    return dataset_dir


def get_tools_file() -> Path:
    return Path(os.getenv("PROTON_AI_TOOLS_FILE") or os.getenv("PROTONX_TOOLS_FILE", ROOT_DIR / "data" / "tools" / "tools.json"))


def get_dataset_dir() -> Path:
    env_dataset_dir = os.getenv("PROTON_AI_DATASET_DIR") or os.getenv("PROTONX_DATASET_DIR")
    if env_dataset_dir:
        return _resolve_project_path(env_dataset_dir)
    return _resolve_project_path(_workspace_dataset_dir() or DEFAULT_DATASET_DIR)


def get_log_file() -> Path:
    return Path(os.getenv("PROTON_AI_ROUTER_LOG_FILE") or os.getenv("PROTONX_ROUTER_LOG_FILE", ROOT_DIR / "data" / "logs" / "router.jsonl"))


def get_workspace_settings_file() -> Path:
    return Path(os.getenv("PROTON_AI_WORKSPACE_FILE") or os.getenv("PROTONX_WORKSPACE_FILE", ROOT_DIR / "data" / "workspace" / "settings.json"))


def get_service_base_url() -> str:
    return (os.getenv("PROTON_AI_SERVICE_URL") or os.getenv("PROTONX_SERVICE_URL", "http://127.0.0.1:8000")).rstrip("/")
