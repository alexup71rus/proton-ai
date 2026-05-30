import json
from datetime import datetime, timezone
from pathlib import Path

from protonx.config import LOG_DIR


def append_router_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = Path(LOG_DIR) / "router.jsonl"
    payload = dict(record)
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
