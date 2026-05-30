from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DIRECTORIES = {
    "downloads": Path.home() / "Downloads",
    "project_root": ROOT_DIR,
    "service": ROOT_DIR / "service",
    "web_backend": ROOT_DIR / "web_backend",
    "web_ui": ROOT_DIR / "web_ui",
    "data": ROOT_DIR / "data",
}
MAX_ITEMS = 100


def _read_arguments() -> dict[str, Any]:
    payload = json.loads(sys.stdin.read() or "{}")
    if not isinstance(payload, dict):
        return {}
    arguments = payload.get("arguments") or {}
    return arguments if isinstance(arguments, dict) else {}


def main() -> None:
    arguments = _read_arguments()
    directory_key = str(arguments.get("directory") or "downloads")
    target = DIRECTORIES.get(directory_key)
    if target is None:
        raise SystemExit(f"Unsupported directory preset: {directory_key}")

    if not target.exists():
        payload = {
            "directory": directory_key,
            "path": str(target),
            "count": 0,
            "items": [],
            "truncated": False,
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return

    entries = sorted(
        target.iterdir(),
        key=lambda entry: (not entry.is_dir(), entry.name.lower()),
    )
    limited_entries = entries[:MAX_ITEMS]
    payload = {
        "directory": directory_key,
        "path": str(target),
        "count": len(entries),
        "items": [
            {
                "name": entry.name,
                "kind": "directory" if entry.is_dir() else "file",
            }
            for entry in limited_entries
        ],
        "truncated": len(entries) > len(limited_entries),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
