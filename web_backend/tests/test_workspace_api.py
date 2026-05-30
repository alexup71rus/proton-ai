from __future__ import annotations

import json
from pathlib import Path


def test_get_workspace_creates_default_file(tmp_path: Path, monkeypatch, client) -> None:
    workspace_path = tmp_path / "workspace.json"
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(workspace_path))

    response = client.get("/api/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage_path"] == str(workspace_path)
    assert payload["selected_model"]["artifact_name"] == "tiny_router_v1"
    assert payload["training"] == {
        "dataset_dir": "data/train/routing",
        "dataset_name": "routing.jsonl",
        "epochs": 1,
        "batch_size": 1,
        "learning_rate": 0.001,
    }
    assert payload["test"] == {
        "user_text": "сделай свет потеплее",
        "show_debug": False,
    }
    assert workspace_path.exists()


def test_put_workspace_persists_settings(tmp_path: Path, monkeypatch, client) -> None:
    workspace_path = tmp_path / "workspace.json"
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(workspace_path))

    response = client.put(
        "/api/workspace",
        json={
            "selected_model": {
                "mode": "loaded",
                "label": "custom_router",
                "model_name": "tiny-router",
                "tokenizer_name": "sentencepiece-bpe",
                "output_root_dir": "data",
                "artifact_name": "custom_router",
                "model_path": "/tmp/custom_router.pt",
                "tokenizer_path": "/tmp/custom_router.model",
                "hidden_dim": 96,
                "num_layers": 3,
                "num_heads": 8,
            },
            "training": {
                "dataset_dir": str(tmp_path / "datasets"),
                "dataset_name": "custom.jsonl",
                "epochs": 4,
                "batch_size": 2,
            },
            "test": {
                "user_text": "turn on the lamp",
                "show_debug": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_model"]["label"] == "custom_router"
    assert payload["training"]["epochs"] == 4
    assert payload["test"] == {
        "user_text": "turn on the lamp",
        "show_debug": True,
    }

    saved = json.loads(workspace_path.read_text(encoding="utf-8"))
    assert saved["selected_model"]["model_path"] == "/tmp/custom_router.pt"
    assert saved["training"]["dataset_dir"] == str(tmp_path / "datasets")
    assert saved["training"]["dataset_name"] == "custom.jsonl"
    assert saved["test"]["show_debug"] is True


def test_list_directories_returns_readable_children(tmp_path: Path, client) -> None:
    child_dir = tmp_path / "weights"
    child_dir.mkdir()
    (tmp_path / "model.pt").write_text("not a directory", encoding="utf-8")

    response = client.get("/api/filesystem/directories", params={"path": str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == str(tmp_path)
    assert payload["parent_path"] == str(tmp_path.parent)
    assert payload["entries"] == [{"name": "weights", "path": str(child_dir)}]


def test_list_directories_rejects_file_path(tmp_path: Path, client) -> None:
    file_path = tmp_path / "model.pt"
    file_path.write_text("not a directory", encoding="utf-8")

    response = client.get("/api/filesystem/directories", params={"path": str(file_path)})

    assert response.status_code == 400


def test_get_model_artifact_status_reports_existing_files(tmp_path: Path, client) -> None:
    weights_dir = tmp_path / "weights"
    tokenizers_dir = tmp_path / "tokenizers"
    weights_dir.mkdir()
    tokenizers_dir.mkdir()
    (weights_dir / "saved_router.pt").write_bytes(b"weights")
    (tokenizers_dir / "saved_router.model").write_bytes(b"tokenizer")

    response = client.get(
        "/api/models/artifact-status",
        params={"output_root_dir": str(tmp_path), "artifact_name": "saved_router"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_name"] == "saved_router"
    assert payload["exists"] is True
    assert payload["model_exists"] is True
    assert payload["tokenizer_exists"] is True
    assert payload["vocab_exists"] is False


def test_post_model_import_rejects_existing_artifact(tmp_path: Path, monkeypatch, client) -> None:
    workspace_path = tmp_path / "workspace.json"
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(workspace_path))
    weights_dir = tmp_path / "weights"
    tokenizers_dir = tmp_path / "tokenizers"
    weights_dir.mkdir()
    tokenizers_dir.mkdir()
    existing_model = weights_dir / "saved_router.pt"
    existing_model.write_bytes(b"existing")

    response = client.post(
        "/api/models/import",
        data={"output_root_dir": str(tmp_path), "artifact_name": "saved_router"},
        files={
            "checkpoint": ("saved_router.pt", b"new checkpoint", "application/octet-stream"),
            "tokenizer": ("saved_router.model", b"new tokenizer", "application/octet-stream"),
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert existing_model.read_bytes() == b"existing"
