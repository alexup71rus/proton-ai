from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any


TARGETS = {
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
}


def _read_arguments() -> dict[str, Any]:
    payload = json.loads(sys.stdin.read() or "{}")
    if not isinstance(payload, dict):
        return {}
    arguments = payload.get("arguments") or {}
    return arguments if isinstance(arguments, dict) else {}


def main() -> None:
    arguments = _read_arguments()
    target = str(arguments.get("target") or "node")
    command = TARGETS.get(target)
    if command is None:
        raise SystemExit(f"Unsupported Node.js version target: {target}")

    binary = shutil.which(command[0])
    if not binary:
        raise SystemExit(f"{command[0]} is not installed or not available in PATH")

    completed = subprocess.run(
        [binary, *command[1:]],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or completed.stdout.strip() or "node --version failed")

    payload = {
        "target": target,
        "version": completed.stdout.strip() or completed.stderr.strip(),
        "binary": binary,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
