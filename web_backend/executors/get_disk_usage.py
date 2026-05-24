from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _format_bytes(value: int) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for suffix in suffixes:
        if size < 1024 or suffix == suffixes[-1]:
            return f"{size:.1f} {suffix}"
        size /= 1024
    return f"{size:.1f} TB"


def main() -> None:
    _ = json.loads(sys.stdin.read() or "{}")
    target = Path.home()
    usage = shutil.disk_usage(target)
    payload = {
        "path": str(target),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "total_human": _format_bytes(usage.total),
        "used_human": _format_bytes(usage.used),
        "free_human": _format_bytes(usage.free),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()