import json
import os
from datetime import datetime, timezone
from pathlib import Path

from protonx.config import LOG_DIR


def _router_log_path() -> Path:
    raw_path = os.getenv("PROTON_AI_ROUTER_LOG_FILE") or os.getenv("PROTONX_ROUTER_LOG_FILE")
    if raw_path:
        return Path(raw_path).expanduser()
    return Path(LOG_DIR) / "router.jsonl"


def append_router_log(record: dict) -> None:
    log_path = _router_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
