from __future__ import annotations

from pathlib import Path


ARTIFACT_SUFFIXES = (".pt", ".model", ".vocab")


def normalize_artifact_name(artifact_name: str) -> str:
    normalized = artifact_name.strip()
    for suffix in ARTIFACT_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    normalized = normalized.strip().strip("./")
    if not normalized:
        raise ValueError("artifact_name must be a non-empty file stem")
    if Path(normalized).name != normalized:
        raise ValueError("artifact_name must not contain path separators")
    return normalized