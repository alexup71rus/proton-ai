from __future__ import annotations

import json
import sys
from datetime import datetime


def main() -> None:
    _ = json.loads(sys.stdin.read() or "{}")
    now = datetime.now().astimezone()
    payload = {
        "iso": now.isoformat(),
        "timezone": now.tzname(),
        "unix": int(now.timestamp()),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()