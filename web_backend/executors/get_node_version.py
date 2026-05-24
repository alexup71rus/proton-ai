from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> None:
    _ = json.loads(sys.stdin.read() or "{}")
    binary = shutil.which("node")
    if not binary:
        raise SystemExit("Node.js is not installed or not available in PATH")

    completed = subprocess.run(
        [binary, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or completed.stdout.strip() or "node --version failed")

    payload = {
        "version": completed.stdout.strip() or completed.stderr.strip(),
        "binary": binary,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()