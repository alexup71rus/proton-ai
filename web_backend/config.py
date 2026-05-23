from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def get_tools_file() -> Path:
    return Path(os.getenv("PROTONX_TOOLS_FILE", ROOT_DIR / "data" / "tools" / "tools.json"))


def get_dataset_dir() -> Path:
    return Path(os.getenv("PROTONX_DATASET_DIR", ROOT_DIR / "data" / "train" / "routing"))


def get_log_file() -> Path:
    return Path(os.getenv("PROTONX_ROUTER_LOG_FILE", ROOT_DIR / "data" / "logs" / "router.jsonl"))


def get_service_base_url() -> str:
    return os.getenv("PROTONX_SERVICE_URL", "http://127.0.0.1:8000").rstrip("/")
