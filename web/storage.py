import json
import os
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATASET_DIR = DATA_DIR / "train" / "routing"
LOG_FILE = DATA_DIR / "logs" / "router.jsonl"
TOOLS_FILE = Path(
    os.getenv("PROTON_AI_TOOLS_FILE") or os.getenv("PROTONX_TOOLS_FILE", str(DATA_DIR / "tools" / "tools.json"))
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_tools_file() -> Path:
    _ensure_parent(TOOLS_FILE)
    if not TOOLS_FILE.exists():
        if TOOLS_FILE.suffix in {".yaml", ".yml"}:
            TOOLS_FILE.write_text("[]\n", encoding="utf-8")
        else:
            TOOLS_FILE.write_text("[]\n", encoding="utf-8")
    return TOOLS_FILE


def load_tools() -> list[dict[str, Any]]:
    path = ensure_tools_file()
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(raw) or []
    return json.loads(raw)


def save_tools(tools: list[dict[str, Any]]) -> Path:
    path = ensure_tools_file()
    if path.suffix in {".yaml", ".yml"}:
        content = yaml.safe_dump(tools, sort_keys=False, allow_unicode=True)
    else:
        content = json.dumps(tools, ensure_ascii=False, indent=2)
    path.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    return path


def list_dataset_files() -> list[Path]:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(DATASET_DIR.glob("*.jsonl"))


def import_dataset(filename: str, content: bytes) -> Path:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    target = DATASET_DIR / filename
    target.write_bytes(content)
    return target


def read_dataset(path: Path) -> bytes:
    return path.read_bytes()


def load_router_logs(limit: int = 100) -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    rows = [
        json.loads(line)
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows[-limit:][::-1]
