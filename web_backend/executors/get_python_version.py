from __future__ import annotations

import json
import platform
import sys


def main() -> None:
    _ = json.loads(sys.stdin.read() or "{}")
    payload = {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "binary": sys.executable,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()