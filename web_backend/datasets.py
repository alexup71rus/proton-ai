from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from web_backend.config import get_dataset_dir


def ensure_dataset_dir() -> Path:
    path = get_dataset_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_dataset_files() -> list[Path]:
    return sorted(ensure_dataset_dir().glob("*.jsonl"))


def import_dataset_file(filename: str, content: bytes) -> Path:
    target = ensure_dataset_dir() / Path(filename).name
    target.write_bytes(content)
    return target


def resolve_dataset_path(dataset_name: str) -> Path:
    safe_name = Path(dataset_name).name
    if safe_name != dataset_name or not safe_name.endswith(".jsonl"):
        raise ValueError("Invalid dataset name")
    path = ensure_dataset_dir() / safe_name
    if not path.exists():
        raise FileNotFoundError(dataset_name)
    return path


def summarize_dataset(path: Path) -> dict[str, str | int]:
    stat = path.stat()
    return {
        "name": path.name,
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }
