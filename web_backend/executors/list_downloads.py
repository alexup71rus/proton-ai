from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    _ = json.loads(sys.stdin.read() or "{}")
    downloads_path = Path.home() / "Downloads"
    if not downloads_path.exists():
        payload = {
            "path": str(downloads_path),
            "count": 0,
            "items": [],
            "truncated": False,
        }
    else:
        entries = sorted(
            downloads_path.iterdir(),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )
        limited_entries = entries[:100]
        payload = {
            "path": str(downloads_path),
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