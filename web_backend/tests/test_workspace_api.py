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
        "dataset_name": "routing.jsonl",
        "epochs": 1,
        "batch_size": 1,
    }
    assert payload["test"] == {
        "user_text": "сделай свет потеплее",
        "answer_allowed": False,
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
                "dataset_name": "custom.jsonl",
                "epochs": 4,
                "batch_size": 2,
            },
            "test": {
                "user_text": "turn on the lamp",
                "answer_allowed": True,
                "show_debug": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_model"]["label"] == "custom_router"
    assert payload["training"]["epochs"] == 4
    assert payload["test"]["answer_allowed"] is True

    saved = json.loads(workspace_path.read_text(encoding="utf-8"))
    assert saved["selected_model"]["model_path"] == "/tmp/custom_router.pt"
    assert saved["training"]["dataset_name"] == "custom.jsonl"
    assert saved["test"]["show_debug"] is True