from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile
from typing import Any

from web_backend.config import get_dataset_dir
from web_backend.dataset_validation import build_preview_lines, validate_dataset_content


DATASET_SOURCES = {"imported", "tools_bootstrap", "manual", "logs_draft"}


def ensure_dataset_dir() -> Path:
    path = get_dataset_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path(path: Path) -> Path:
    return path.with_suffix(".meta.json")


def _normalize_dataset_name(dataset_name: str) -> str:
    safe_name = Path(dataset_name).name.strip()
    if not safe_name:
        raise ValueError("Dataset name is required")
    if not safe_name.endswith(".jsonl"):
        safe_name = f"{safe_name}.jsonl"
    if Path(safe_name).name != safe_name:
        raise ValueError("Invalid dataset name")
    return safe_name


def _default_dataset_source(path: Path) -> str:
    if path.name == "routing.jsonl":
        return "tools_bootstrap"
    return "imported"


def _load_dataset_source(path: Path) -> str:
    metadata_path = _metadata_path(path)
    if not metadata_path.exists():
        return _default_dataset_source(path)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_dataset_source(path)
    source = metadata.get("source")
    if source not in DATASET_SOURCES:
        return _default_dataset_source(path)
    return source


def _write_dataset_source(path: Path, source: str) -> None:
    if source not in DATASET_SOURCES:
        raise ValueError(f"Unsupported dataset source: {source}")
    _metadata_path(path).write_text(
        json.dumps({"source": source}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_dataset_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_summary(path: Path, content: str) -> dict[str, Any]:
    stat = path.stat()
    validation = validate_dataset_content(content)
    return {
        "name": path.name,
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "row_count": validation["row_count"],
        "validation_status": validation["status"],
        "issue_count": validation["issue_count"],
        "source": _load_dataset_source(path),
    }


def list_dataset_files() -> list[Path]:
    return sorted(ensure_dataset_dir().glob("*.jsonl"))


def import_dataset_file(filename: str, content: bytes) -> Path:
    text = content.decode("utf-8")
    report = validate_dataset_content(text)
    if report["status"] != "valid":
        first_issue = report["issues"][0]["message"] if report["issues"] else "Dataset is invalid"
        raise ValueError(first_issue)
    return write_dataset_file(filename, text, source="imported")


def write_dataset_file(
    dataset_name: str,
    content: str,
    source: str,
    overwrite: bool = False,
) -> Path:
    safe_name = _normalize_dataset_name(dataset_name)
    target = ensure_dataset_dir() / safe_name
    if target.exists() and not overwrite:
        raise ValueError(f"Dataset already exists: {safe_name}")
    target.write_text(content if content.endswith("\n") else f"{content}\n", encoding="utf-8")
    _write_dataset_source(target, source)
    return target


def create_manual_dataset(dataset_name: str, content: str) -> Path:
    report = validate_dataset_content(content)
    if report["status"] != "valid":
        first_issue = report["issues"][0]["message"] if report["issues"] else "Dataset is invalid"
        raise ValueError(first_issue)
    return write_dataset_file(dataset_name, content, source="manual")


def save_bootstrap_dataset(dataset_name: str, generated_path: Path) -> Path:
    content = _read_dataset_text(generated_path)
    report = validate_dataset_content(content)
    if report["status"] != "valid":
        first_issue = report["issues"][0]["message"] if report["issues"] else "Dataset is invalid"
        raise ValueError(first_issue)

    safe_name = _normalize_dataset_name(dataset_name)
    target = ensure_dataset_dir() / safe_name
    if target.exists() and target.resolve() != generated_path.resolve():
        raise ValueError(f"Dataset already exists: {safe_name}")

    if target.resolve() != generated_path.resolve():
        target.write_text(content if content.endswith("\n") else f"{content}\n", encoding="utf-8")
    _write_dataset_source(target, "tools_bootstrap")
    return target


def append_dataset_content(dataset_name: str, content: str) -> Path:
    path = resolve_dataset_path(dataset_name)
    existing = _read_dataset_text(path).strip()
    addition = content.strip()
    merged = addition if not existing else f"{existing}\n{addition}"
    report = validate_dataset_content(merged)
    if report["status"] != "valid":
        first_issue = report["issues"][0]["message"] if report["issues"] else "Dataset is invalid"
        raise ValueError(first_issue)
    path.write_text(f"{merged}\n", encoding="utf-8")
    return path


def resolve_dataset_path(dataset_name: str) -> Path:
    safe_name = _normalize_dataset_name(dataset_name)
    if safe_name != dataset_name and dataset_name.endswith(".jsonl"):
        raise ValueError("Invalid dataset name")
    path = ensure_dataset_dir() / safe_name
    if not path.exists():
        raise FileNotFoundError(dataset_name)
    return path


def duplicate_dataset(dataset_name: str) -> Path:
    source_path = resolve_dataset_path(dataset_name)
    stem = source_path.stem
    for index in range(1, 1000):
        suffix = "-copy" if index == 1 else f"-copy-{index}"
        candidate = ensure_dataset_dir() / f"{stem}{suffix}.jsonl"
        if candidate.exists():
            continue
        copyfile(source_path, candidate)
        _write_dataset_source(candidate, _load_dataset_source(source_path))
        return candidate
    raise ValueError(f"Could not duplicate dataset: {dataset_name}")


def delete_dataset(dataset_name: str) -> str:
    path = resolve_dataset_path(dataset_name)
    path.unlink(missing_ok=False)
    _metadata_path(path).unlink(missing_ok=True)
    return path.name


def summarize_dataset(path: Path) -> dict[str, Any]:
    return _build_summary(path, _read_dataset_text(path))


def get_dataset_validation_report(path: Path) -> dict[str, Any]:
    return validate_dataset_content(_read_dataset_text(path))


def get_dataset_preview(path: Path, limit: int = 5) -> dict[str, Any]:
    content = _read_dataset_text(path)
    return {
        "dataset": _build_summary(path, content),
        "preview_lines": build_preview_lines(content, limit=limit),
        "validation": validate_dataset_content(content),
    }
