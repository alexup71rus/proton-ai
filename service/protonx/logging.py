import json
from pathlib import Path

from protonx.config import LOG_DIR


def append_router_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = Path(LOG_DIR) / "router.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
