from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from web_backend.config import get_tools_file
from web_backend.tool_executor import get_default_tools


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _serialize_tools(tools: list[dict[str, Any]], path: Path) -> str:
    if path.suffix in {".yaml", ".yml"}:
        content = yaml.safe_dump(tools, sort_keys=False, allow_unicode=True)
    else:
        content = json.dumps(tools, ensure_ascii=False, indent=2)
    if not content.endswith("\n"):
        content += "\n"
    return content


def ensure_tools_file() -> Path:
    path = get_tools_file()
    _ensure_parent(path)
    if not path.exists():
        path.write_text(_serialize_tools(get_default_tools(), path), encoding="utf-8")
    return path


def load_tools() -> list[dict[str, Any]]:
    path = ensure_tools_file()
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(raw) or []
    return json.loads(raw)


def save_tools(tools: list[dict[str, Any]]) -> Path:
    path = ensure_tools_file()
    path.write_text(_serialize_tools(tools, path), encoding="utf-8")
    return path
