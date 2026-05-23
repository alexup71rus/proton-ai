from __future__ import annotations

from pathlib import Path

import web_backend.app as app_module


def test_get_training_status_returns_ui_friendly_shape(monkeypatch, client) -> None:
    monkeypatch.setattr(
        app_module.service_client,
        "get_json",
        lambda path: {
            "status": "idle",
        },
    )

    response = client.get("/api/training/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "idle"
    assert payload["loss_history"] == []
    assert payload["metrics"] == {}
    assert payload["error"] is None
    assert payload["current_epoch"] == 0
    assert payload["batch_size"] == 1


def test_post_training_start_forwards_config(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text('{"x":1}\n', encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        return {"status": "running"}

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 2,
            "batch_size": 4,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
        },
    )

    assert response.status_code == 200
    assert captured["path"] == "/train/start"
    assert captured["payload"] == {
        "dataset_path": str(dataset_path),
        "epochs": 2,
        "batch_size": 4,
        "model_name": "tiny-router",
        "tokenizer_name": "sentencepiece-bpe",
    }


def test_post_training_start_normalizes_partial_service_payload(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text('{"x":1}\n', encoding="utf-8")

    monkeypatch.setattr(
        app_module.service_client,
        "post_json",
        lambda path, payload: {"status": "running", "current_epoch": 1},
    )

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 2,
            "batch_size": 4,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["current_epoch"] == 1
    assert payload["loss_history"] == []
    assert payload["metrics"] == {}
