from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any


def _read_arguments() -> dict[str, Any]:
    payload = json.loads(sys.stdin.read() or "{}")
    if not isinstance(payload, dict):
        return {}
    arguments = payload.get("arguments") or {}
    return arguments if isinstance(arguments, dict) else {}


def main() -> None:
    arguments = _read_arguments()
    state = str(arguments.get("state") or "running")
    if state not in {"running", "all"}:
        raise SystemExit(f"Unsupported container state: {state}")

    docker = shutil.which("docker")
    if docker is None:
        payload = {
            "available": False,
            "state": state,
            "containers": [],
            "error": "Docker CLI is not available in PATH",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return

    command = [docker, "ps", "--format", "{{json .}}"]
    if state == "all":
        command.insert(2, "--all")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        payload = {
            "available": True,
            "state": state,
            "containers": [],
            "error": completed.stderr.strip() or completed.stdout.strip() or "docker ps failed",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return

    containers = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            containers.append({"raw": line})

    payload = {
        "available": True,
        "state": state,
        "count": len(containers),
        "containers": containers[:100],
        "truncated": len(containers) > 100,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
