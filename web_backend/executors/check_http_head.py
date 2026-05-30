from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any


TARGET_URLS = {
    "example_com": "https://example.com",
    "pypi": "https://pypi.org",
    "npm_registry": "https://registry.npmjs.org",
    "github": "https://github.com",
}


def _read_arguments() -> dict[str, Any]:
    payload = json.loads(sys.stdin.read() or "{}")
    if not isinstance(payload, dict):
        return {}
    arguments = payload.get("arguments") or {}
    return arguments if isinstance(arguments, dict) else {}


def main() -> None:
    arguments = _read_arguments()
    target = str(arguments.get("target") or "example_com")
    url = TARGET_URLS.get(target)
    if url is None:
        raise SystemExit(f"Unsupported HTTP target: {target}")

    curl = shutil.which("curl")
    if curl is None:
        payload = {
            "target": target,
            "url": url,
            "available": False,
            "status": None,
            "headers": "",
            "error": "curl is not available in PATH",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return

    completed = subprocess.run(
        [curl, "-I", "--max-time", "5", url],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    headers = completed.stdout.strip()
    status_line = headers.splitlines()[0] if headers else ""
    payload = {
        "target": target,
        "url": url,
        "available": completed.returncode == 0,
        "status": status_line,
        "headers": headers[:12000],
        "error": "" if completed.returncode == 0 else completed.stderr.strip(),
        "truncated": len(headers) > 12000,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
